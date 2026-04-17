from __future__ import annotations

import json
from dataclasses import dataclass

from spotai.models import CuratedVenue, RecommendationRequest

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


@dataclass
class LLMReasoner:
    api_key: str | None = None
    model: str = 'gpt-4o-mini'

    def _client(self):
        if not self.api_key or OpenAI is None:
            return None
        return OpenAI(api_key=self.api_key)

    def normalize_bulk_text(self, raw_text: str) -> str:
        if not raw_text.strip():
            return raw_text

        client = self._client()
        if client is None:
            return raw_text

        prompt = (
            '다음 참석자 입력 텍스트를 표준 포맷으로 정규화해줘. '\
            '출력은 줄바꿈 기준 name:address 형식만 반환하고 설명은 하지 마.\n\n'
            f'입력:\n{raw_text}'
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            text = response.choices[0].message.content.strip()
            return text or raw_text
        except Exception:
            return raw_text

    def summarize_recommendation(
        self,
        request: RecommendationRequest,
        curated: list[CuratedVenue],
    ) -> str:
        if not curated:
            return '추천할 후보가 없어 요약을 생성하지 못했습니다.'

        top = curated[0]
        fallback = (
            f"{request.meeting_type.value} 모임에는 {top.venue.name}이(가) 가장 적합합니다. "
            f"분위기={top.analysis.atmosphere.value}, 점수={top.score}"
        )

        client = self._client()
        if client is None:
            return fallback

        compact = [
            {
                'name': c.venue.name,
                'address': c.venue.address,
                'score': c.score,
                'atmosphere': c.analysis.atmosphere.value,
                'reasons': c.analysis.reasons,
            }
            for c in curated[:5]
        ]

        prompt = (
            '너는 장소 추천 어시스턴트다. 아래 후보를 바탕으로 한국어 3문장 이내 요약을 작성해라. '\
            '첫 문장은 최종 추천 1곳과 이유, 둘째 문장은 대안, 셋째 문장은 주의사항을 포함해라.\n\n'
            f'요청: meeting_type={request.meeting_type.value}, team_mood={request.team_mood.value}\n'
            f'후보: {json.dumps(compact, ensure_ascii=False)}'
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            text = response.choices[0].message.content.strip()
            return text or fallback
        except Exception:
            return fallback

    def candidate_reason(self, request: RecommendationRequest, item: CuratedVenue) -> str:
        fallback = (
            f"{item.venue.name}은(는) {request.meeting_type.value} 목적에서 "
            f"{item.analysis.atmosphere.value} 분위기와 점수 {item.score}로 추천됩니다."
        )

        client = self._client()
        if client is None:
            return fallback

        prompt = (
            '다음 후보 1개에 대해 한국어 1문장 추천 근거를 작성해라.\n'
            f"모임유형={request.meeting_type.value}, 팀분위기={request.team_mood.value}\n"
            f"후보명={item.venue.name}, 분위기={item.analysis.atmosphere.value}, "
            f"점수={item.score}, 분석근거={item.analysis.reasons}"
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
            )
            text = response.choices[0].message.content.strip()
            return text or fallback
        except Exception:
            return fallback

    def recovery_guide(self, primary_error: str, fallback_error: str) -> str:
        base = (
            '검색 실패가 발생했습니다. API 키 유효성, 호출 권한, 일일 호출량 제한, '
            '네트워크 연결 상태를 순서대로 점검해 주세요.'
        )

        client = self._client()
        if client is None:
            return base

        prompt = (
            '아래 오류를 보고 한국어 복구 가이드를 4줄 이내로 작성해라. '\
            '각 줄은 체크리스트 형태로 작성하라.\n\n'
            f'primary_error={primary_error}\n'
            f'fallback_error={fallback_error}'
        )

        try:
            response = client.responses.create(
                model=self.model,
                input=prompt,
                max_output_tokens=220,
            )
            text = response.output_text.strip()
            return text or base
        except Exception:
            return base
