from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from spotai.models import RecommendationRequest, Venue


class MapProviderError(RuntimeError):
    pass


@dataclass
class MapSearchService:
    primary_provider: str
    fallback_provider: str
    naver_search_client_id: str | None = None
    naver_search_client_secret: str | None = None
    kakao_api_key: str | None = None
    enable_mock_data: bool = True
    last_search_debug: dict[str, str] | None = None

    def find_venues(self, request: RecommendationRequest) -> list[Venue]:
        built_query = self._build_query(request)
        self.last_search_debug = {
            'primary_provider': self.primary_provider,
            'fallback_provider': self.fallback_provider,
            'used_provider': '',
            'primary_error': '',
            'fallback_error': '',
            'mock_fallback': 'false',
            'query': built_query,
            'result_count': '0',
        }
        try:
            venues = self._search(self.primary_provider, request)
            self.last_search_debug['used_provider'] = self.primary_provider
            self.last_search_debug['result_count'] = str(len(venues))
            return venues
        except MapProviderError as primary_error:
            self.last_search_debug['primary_error'] = str(primary_error)
            try:
                venues = self._search(self.fallback_provider, request)
                self.last_search_debug['used_provider'] = self.fallback_provider
                self.last_search_debug['result_count'] = str(len(venues))
                return venues
            except MapProviderError as fallback_error:
                self.last_search_debug['fallback_error'] = str(fallback_error)
                if self.enable_mock_data:
                    self.last_search_debug['used_provider'] = 'mock'
                    self.last_search_debug['mock_fallback'] = 'true'
                    mock = self._mock_results(request, self.fallback_provider)
                    self.last_search_debug['result_count'] = str(len(mock))
                    return mock
                raise

    def _search(self, provider: str, request: RecommendationRequest) -> list[Venue]:
        if provider == 'naver':
            return self._search_naver(request)
        if provider == 'kakao':
            return self._search_kakao(request)
        raise MapProviderError(f'Unsupported map provider: {provider}')

    def _build_query(self, request: RecommendationRequest) -> str:
        anchor = request.participants[0].address if request.participants else '서울'
        meeting_keywords = {
            'company': '회식 맛집',
            'friends': '모임 맛집',
            'date': '데이트 맛집',
            'family': '가족 식당',
        }
        mood_keywords = {
            'casual': '캐주얼',
            'formal': '격식있는',
            'lively': '분위기 좋은',
            'quiet': '조용한',
        }
        return f"{anchor} {meeting_keywords[request.meeting_type.value]} {mood_keywords[request.team_mood.value]}"

    def _search_naver(self, request: RecommendationRequest) -> list[Venue]:
        if not self.naver_search_client_id or not self.naver_search_client_secret:
            raise MapProviderError('Naver local search credentials are not configured')

        query = quote(self._build_query(request))
        url = f'https://openapi.naver.com/v1/search/local.json?query={query}&display=8&start=1&sort=random'
        http_request = Request(
            url,
            headers={
                'X-Naver-Client-Id': self.naver_search_client_id,
                'X-Naver-Client-Secret': self.naver_search_client_secret,
            },
        )

        try:
            with urlopen(http_request, timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            body = exc.read().decode('utf-8', errors='ignore')
            raise MapProviderError(f'Naver local search failed (HTTP {exc.code}): {body[:300]}') from exc
        except URLError as exc:
            raise MapProviderError(f'Naver local search network error: {exc.reason}') from exc
        except Exception as exc:
            raise MapProviderError(f'Naver local search failed: {exc}') from exc

        venues = [self._venue_from_naver(item, index) for index, item in enumerate(payload.get('items', []), start=1)]
        venues = self._dedupe_venues(venues)
        if not venues:
            raise MapProviderError('Naver local search returned no venues')
        return venues

    def _search_kakao(self, request: RecommendationRequest) -> list[Venue]:
        if not self.kakao_api_key:
            raise MapProviderError('Kakao local search credentials are not configured')

        query = quote(self._build_query(request))
        url = f'https://dapi.kakao.com/v2/local/search/keyword.json?query={query}&size=8'
        http_request = Request(
            url,
            headers={
                'Authorization': f'KakaoAK {self.kakao_api_key}',
            },
        )

        try:
            with urlopen(http_request, timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            body = exc.read().decode('utf-8', errors='ignore')
            raise MapProviderError(f'Kakao local search failed (HTTP {exc.code}): {body[:300]}') from exc
        except URLError as exc:
            raise MapProviderError(f'Kakao local search network error: {exc.reason}') from exc
        except Exception as exc:
            raise MapProviderError(f'Kakao local search failed: {exc}') from exc

        venues = [self._venue_from_kakao(item, index) for index, item in enumerate(payload.get('documents', []), start=1)]
        venues = self._dedupe_venues(venues)
        if not venues:
            raise MapProviderError('Kakao local search returned no venues')
        return venues

    def _venue_from_naver(self, item: dict, index: int) -> Venue:
        title = self._clean_text(item.get('title', f'네이버 결과 {index}'))
        category = self._clean_text(item.get('category', ''))
        description = self._clean_text(item.get('description', ''))
        address = item.get('roadAddress') or item.get('address') or '주소 정보 없음'

        return Venue(
            id=f"naver-{index}-{self._slug(title)}",
            name=title,
            address=address,
            price_level=self._infer_price_level(category),
            rating=4.1,
            review_text=description or f'{category} 카테고리 기반 추천 장소입니다.',
            provider='naver',
            category=category or None,
            image_tags=self._infer_tags(category, description),
        )

    def _venue_from_kakao(self, item: dict, index: int) -> Venue:
        title = self._clean_text(item.get('place_name', f'카카오 결과 {index}'))
        category = self._clean_text(item.get('category_name', ''))
        address = item.get('road_address_name') or item.get('address_name') or '주소 정보 없음'

        return Venue(
            id=f"kakao-{index}-{self._slug(title)}",
            name=title,
            address=address,
            price_level=self._infer_price_level(category),
            rating=4.0,
            review_text=f'{category} 카테고리 기반 추천 장소입니다.',
            provider='kakao',
            category=category or None,
            longitude=float(item['x']) if item.get('x') else None,
            latitude=float(item['y']) if item.get('y') else None,
            image_tags=self._infer_tags(category, ''),
        )

    def _dedupe_venues(self, venues: list[Venue]) -> list[Venue]:
        deduped: list[Venue] = []
        seen: set[tuple[str, str]] = set()
        for venue in venues:
            key = (venue.name, venue.address)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(venue)
        return deduped

    def _mock_results(self, request: RecommendationRequest, provider: str) -> list[Venue]:
        anchor = request.participants[0].address if request.participants else '서울'
        label = {
            'company': '회식',
            'friends': '모임',
            'date': '데이트',
            'family': '가족',
        }[request.meeting_type.value]
        return [
            Venue(
                id=f'{provider}-sample-1',
                name=f'{anchor} {label} 추천 샘플 1',
                address=f'{anchor} 인근',
                price_level=2,
                rating=4.0,
                review_text='실 API 키가 없어 샘플 데이터를 표시합니다.',
                provider='mock',
                image_tags=['sample'],
            )
        ]

    def _clean_text(self, value: str) -> str:
        text = re.sub(r'<[^>]+>', '', value or '')
        return unescape(text).strip()

    def _slug(self, value: str) -> str:
        cleaned = re.sub(r'[^0-9A-Za-z가-힣]+', '-', value).strip('-').lower()
        return cleaned or 'venue'

    def _infer_price_level(self, category: str) -> int:
        text = category.lower()
        if '파인다이닝' in category or '와인' in category or '호텔' in category:
            return 4
        if '고기' in category or '해산물' in category or '일식' in category:
            return 3
        if '카페' in category or '분식' in category or '패스트푸드' in text:
            return 1
        return 2

    def _infer_tags(self, category: str, description: str) -> list[str]:
        source = f'{category} {description}'.lower()
        tags: list[str] = []
        if '술집' in source or '바' in source:
            tags.append('lively')
        if '카페' in source or '데이트' in source:
            tags.append('warm-light')
        if '한정식' in source or '파인다이닝' in source:
            tags.append('private-room')
        if not tags:
            tags.append('group-seat')
        return tags
