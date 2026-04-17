from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from spotai.config import settings
from spotai.models import MeetingType, ParticipantLocation, RecommendationRequest, TeamMood
from spotai.services.analysis_agent import PhotoReviewAnalysisAgent
from spotai.services.curation_agent import RecommendationCurationAgent
from spotai.services.llm_reasoner import LLMReasoner
from spotai.services.notifier import TeamsNotifier
from spotai.services.orchestrator import SpotAIOrchestrator
from spotai.services.reservation_service import ReservationService
from spotai.services.tavily_search import TavilyVenueSearch

try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
except Exception:
    openai_client = None

app = FastAPI(title='SpotAI Meeting Venue Agent')
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

MEETING_TYPE_LABELS = {
    'company': '회식',
    'friends': '친구 모임',
    'date': '데이트',
    'family': '가족 모임',
}

TEAM_MOOD_LABELS = {
    'casual': '캐주얼',
    'formal': '격식',
    'lively': '활발함',
    'quiet': '조용함',
}

orchestrator = SpotAIOrchestrator(
    mcp_gateway=None,  # Not used - using Tavily directly
    analysis_agent=PhotoReviewAnalysisAgent(),
    curation_agent=RecommendationCurationAgent(),
    llm_reasoner=LLMReasoner(api_key=settings.openai_api_key, model=settings.openai_model),
    tavily_search=TavilyVenueSearch(
        tavily_api_key=settings.tavily_api_key,
        openai_client=openai_client,
        kakao_api_key=settings.kakao_map_api_key,
    ) if settings.tavily_api_key and openai_client else None,
)

input_normalizer = LLMReasoner(api_key=settings.openai_api_key, model=settings.openai_model)

last_response = None
last_meeting_type = None
last_participants: list[ParticipantLocation] = []


def build_view_candidates(result):
    if not result:
        return []

    view_candidates = []
    for item in result.candidates[:5]:
        status = result.reservation_status.get(item.venue.id)
        name_encoded = quote(item.venue.name, safe='')
        lat = item.venue.latitude
        lng = item.venue.longitude
        if lat and lng:
            # 좌표가 있으면 핀 직접 이동 (정확한 장소)
            map_url = f'https://map.kakao.com/link/map/{name_encoded},{lat},{lng}'
        else:
            # 좌표 없으면 장소명만 키워드 검색
            map_url = f'https://map.kakao.com/?q={name_encoded}'
        view_candidates.append(
            {
                'venue_id': item.venue.id,
                'name': item.venue.name,
                'address': item.venue.address,
                'score': item.score,
                'atmosphere_kr': TEAM_MOOD_LABELS.get(item.analysis.atmosphere.value, item.analysis.atmosphere.value),
                'sentiment': item.analysis.sentiment_score,
                'reservation_text': '예약 가능' if status and status.is_available else '예약 확인 필요',
                'map_url': map_url,
                'provider': item.venue.provider,
                'category': item.venue.category or '분류 정보 없음',
                'latitude': item.venue.latitude,
                'longitude': item.venue.longitude,
                'reason': result.candidate_reasons.get(item.venue.id, ''),
            }
        )
    return view_candidates


def build_view_participants(participants: list[ParticipantLocation]) -> list[dict[str, str]]:
    return [
        {
            'name': p.name,
            'address': p.address,
        }
        for p in participants
    ]


def parse_bulk_participants(participants_raw: str) -> list[ParticipantLocation]:
    participants: list[ParticipantLocation] = []
    participants_raw = input_normalizer.normalize_bulk_text(participants_raw)

    compact_pattern = re.compile(r'^참가자\s*[-:]\s*(.+?)\s*[:：]\s*(.+)$')
    for idx, row in enumerate(participants_raw.splitlines()):
        line = row.strip()
        if not line:
            continue

        compact_match = compact_pattern.match(line)
        if compact_match:
            names_raw = compact_match.group(1).strip()
            address = compact_match.group(2).strip()
            names = [name.strip() for name in names_raw.split(',') if name.strip()]
            if names and address:
                for name in names:
                    participants.append(ParticipantLocation(name=name, address=address))
                continue

        if ':' in line:
            name, address = line.split(':', maxsplit=1)
        else:
            name, address = f'참석자 {idx + 1}', line
        participants.append(ParticipantLocation(name=name.strip(), address=address.strip()))

    return participants


def build_context(
    result,
    notification: str | None,
    participants: list[ParticipantLocation] | None = None,
) -> dict[str, Any]:
    participants = participants or []
    view_candidates = build_view_candidates(result)
    view_participants = build_view_participants(participants)
    providers = sorted({item.get('provider', 'unknown') for item in view_candidates})
    has_mock_results = any(item.get('provider') == 'mock' for item in view_candidates)
    search_debug = orchestrator.mcp_gateway.last_tool_debug or {} if orchestrator.mcp_gateway else {}

    return {
        'result': result,
        'notification': notification,
        'view_candidates': view_candidates,
        'view_participants': view_participants,
        'pipeline_logs': result.pipeline_logs if result else [],
        'llm_summary': result.llm_summary if result else None,
        'recovery_guide': result.recovery_guide if result else None,
        'providers_used': providers,
        'has_mock_results': has_mock_results,
        'search_debug': search_debug,
        'meeting_labels': MEETING_TYPE_LABELS,
        'mood_labels': TEAM_MOOD_LABELS,
        'kakao_map_js_key': settings.kakao_map_js_key,
        'has_live_search': bool(settings.naver_search_client_id and settings.naver_search_client_secret),
    }


@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='index.html',
        context=build_context(None, None),
    )


@app.post('/recommend', response_class=HTMLResponse)
def recommend(
    request: Request,
    meeting_type: str = Form(...),
    team_mood: str = Form(...),
    budget_per_person: int | None = Form(default=None),
    input_mode: str = Form(default='bulk'),
    participants_raw: str = Form(default=''),
    participant_names: list[str] = Form(default=[]),
    participant_addresses: list[str] = Form(default=[]),
):
    global last_response, last_meeting_type, last_participants

    participants: list[ParticipantLocation] = []
    if input_mode == 'individual':
        for idx, address in enumerate(participant_addresses):
            clean_address = address.strip()
            if not clean_address:
                continue
            name = participant_names[idx].strip() if idx < len(participant_names) else ''
            participants.append(
                ParticipantLocation(
                    name=name or f'참석자 {idx + 1}',
                    address=clean_address,
                )
            )
    else:
        participants = parse_bulk_participants(participants_raw)

    # Extract address from participants (all participants share the same address)
    meeting_address = None
    if participants:
        meeting_address = participants[0].address

    req = RecommendationRequest(
        meeting_type=MeetingType(meeting_type),
        team_mood=TeamMood(team_mood),
        address=meeting_address,
        participants=participants,
        budget_per_person=budget_per_person,
    )

    result = orchestrator.run(req)
    last_response = result
    last_meeting_type = meeting_type
    last_participants = participants

    return templates.TemplateResponse(
        request=request,
        name='index.html',
        context=build_context(result, None, participants),
    )


@app.post('/select', response_class=HTMLResponse)
def select_venue(request: Request, venue_id: str = Form(...)):
    if last_response is None or last_meeting_type is None:
        return templates.TemplateResponse(
            request=request,
            name='index.html',
            context=build_context(None, '먼저 추천을 실행해 주세요.', []),
        )

    message = orchestrator.notify_selection(last_meeting_type, venue_id, last_response)

    return templates.TemplateResponse(
        request=request,
        name='index.html',
        context=build_context(last_response, message, last_participants),
    )


@app.get('/api/last-run-log', response_class=JSONResponse)
def last_run_log():
    if not last_response:
        return JSONResponse({'message': 'No run executed yet.'})

    return JSONResponse(
        {
            'search_debug': orchestrator.mcp_gateway.last_tool_debug or {},
            'pipeline_logs': [log.model_dump() for log in last_response.pipeline_logs],
            'notes': last_response.notes,
            'llm_summary': last_response.llm_summary,
            'candidate_reasons': last_response.candidate_reasons,
            'recovery_guide': last_response.recovery_guide,
        }
    )
