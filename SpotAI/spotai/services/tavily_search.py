"""Tavily-based real-time venue search using LLM analysis."""

import json
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

from spotai.models import CuratedVenue, RecommendationRequest, Venue, VenueAnalysis, TeamMood


class TavilyVenueSearch:
    """Searches real-time venue information using Tavily + LLM analysis"""

    def __init__(self, tavily_api_key: str, openai_client, kakao_api_key: str | None = None):
        self.tavily_api_key = tavily_api_key
        self.openai_client = openai_client
        self.kakao_api_key = kakao_api_key
        self.client = TavilyClient(api_key=tavily_api_key) if TavilyClient else None

    def _resolve_address_coordinates(self, address: str) -> tuple[float, float] | None:
        """Resolve an address to coordinates using Kakao Local API."""
        if not self.kakao_api_key:
            return None

        headers = {'Authorization': f'KakaoAK {self.kakao_api_key}'}

        address_query = quote(address, safe='')
        address_url = (
            'https://dapi.kakao.com/v2/local/search/address.json'
            f'?query={address_query}&size=1'
        )
        try:
            req = Request(address_url, headers=headers)
            with urlopen(req, timeout=4) as res:
                payload = json.loads(res.read().decode('utf-8'))
            docs = payload.get('documents', [])
            if docs:
                item = docs[0]
                return float(item['y']), float(item['x'])
        except Exception:
            return None

        return None

    def _resolve_coordinates(
        self,
        name: str,
        meeting_anchor: tuple[float, float] | None,
        fallback_address: str | None = None,
    ) -> tuple[float, float] | None:
        """Resolve place coordinates with keyword=name only.

        If multiple Kakao results are returned, choose the one closest to
        the user's input location (meeting_anchor).
        """
        if not self.kakao_api_key:
            return None

        headers = {'Authorization': f'KakaoAK {self.kakao_api_key}'}
        keyword_query = quote(name, safe='')
        keyword_url = (
            'https://dapi.kakao.com/v2/local/search/keyword.json'
            f'?query={keyword_query}&size=15'
        )

        try:
            req = Request(keyword_url, headers=headers)
            with urlopen(req, timeout=4) as res:
                payload = json.loads(res.read().decode('utf-8'))
            docs = payload.get('documents', [])
            if not docs:
                if fallback_address:
                    return self._resolve_address_coordinates(fallback_address)
                return None

            if meeting_anchor is None:
                item = docs[0]
                return float(item['y']), float(item['x'])

            anchor_lat, anchor_lng = meeting_anchor
            best = min(
                docs,
                key=lambda d: (
                    (float(d['y']) - anchor_lat) ** 2 + (float(d['x']) - anchor_lng) ** 2
                ),
            )
            return float(best['y']), float(best['x'])
        except Exception:
            if fallback_address:
                return self._resolve_address_coordinates(fallback_address)
            return None

    def search_venues(
        self,
        request: RecommendationRequest,
    ) -> Optional[list[CuratedVenue]]:
        """Search venues using Tavily and analyze with LLM"""
        
        if not self.client or not self.openai_client:
            return None

        # Extract meeting address with fallback
        meeting_address = request.address
        if not meeting_address and request.participants:
            meeting_address = request.participants[0].address
        
        # Default to Posco DX if no address provided
        if not meeting_address:
            meeting_address = "포스코DX 판교사무소"

        # 1. Tavily로 실시간 검색
        search_query = f"{meeting_address} {request.meeting_type.value} 맛집 {request.team_mood.value} 분위기"
        
        try:
            response = self.client.search(
                query=search_query,
                max_results=10,
                search_depth="advanced"
            )
        except Exception as e:
            print(f"Tavily search failed: {e}")
            return None

        if not response.get('results'):
            return None

        # 2. 검색 결과를 LLM에 전달
        search_results_text = "\n".join([
            f"- {r.get('title', '')}: {r.get('content', '')}\n  URL: {r.get('url', '')}"
            for r in response['results'][:5]
        ])

        prompt = f"""다음 검색 결과를 바탕으로 {request.meeting_type.value} 모임에 적합한 장소 5개를 JSON으로 추천해줘.
팀 분위기: {request.team_mood.value}
예산: {request.budget_per_person if request.budget_per_person else '무제한'}원

검색 결과:
{search_results_text}

중요: 좌표(latitude/longitude)는 추정하지 말고 생략해도 된다.

아래 JSON 형식으로 정확히 반환해 (설명 없이 JSON만):
[
  {{
    "name": "장소 정확한 이름 (지점명 포함, 예: 스시야 강남본점)",
    "address": "도로명 또는 지번 주소 (정확히)",
    "category": "카테고리",
    "atmosphere": "분위기",
    "score": 85,
    "reasons": ["이유1", "이유2"],
        "url": "참고 URL"
  }}
]"""

        try:
            llm_response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2500,
            )
            
            response_text = llm_response.choices[0].message.content
            
            # JSON 추출 (마크다운 코드블럭 제거)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # JSON이 잘린 경우 복구 시도
            response_text = response_text.strip()
            if response_text and not response_text.endswith(']'):
                last_brace = response_text.rfind('},')
                if last_brace != -1:
                    response_text = response_text[: last_brace + 1] + '\n]'
                elif response_text.count('{') > response_text.count('}'):
                    response_text = response_text[: response_text.rfind('{')] + '\n]'
            
            venues_data = json.loads(response_text)
            
            meeting_anchor = self._resolve_address_coordinates(meeting_address)

            # 3. CuratedVenue 객체로 변환
            curated = []
            for idx, item in enumerate(venues_data[:5]):
                coords = self._resolve_coordinates(
                    item['name'],
                    meeting_anchor,
                    item.get('address'),
                )
                lat, lng = (coords if coords else (None, None))
                venue = Venue(
                    id=f"tavily_{idx}",
                    name=item["name"],
                    address=item["address"],
                    category=item.get("category", "음식점"),
                    price_level=2,
                    rating=4.0,
                    review_text=item.get("url", ""),
                    provider="tavily",
                    latitude=lat,
                    longitude=lng,
                )
                
                analysis = VenueAnalysis(
                    venue_id=f"tavily_{idx}",
                    sentiment_score=min(100, item.get("score", 80)) / 100,
                    atmosphere=TeamMood.casual,  # Default to casual
                    reasons=item.get("reasons", []),
                )
                
                curated_venue = CuratedVenue(
                    venue=venue,
                    analysis=analysis,
                    score=min(100, item.get("score", 80)),
                )
                curated.append(curated_venue)
            
            return curated if curated else None
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            return None
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return None
