from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from spotai.models import PipelineLog, RecommendationRequest, RecommendationResponse
from spotai.services.analysis_agent import PhotoReviewAnalysisAgent
from spotai.services.curation_agent import RecommendationCurationAgent
from spotai.services.llm_reasoner import LLMReasoner
from spotai.services.mcp_gateway import MCPToolGateway

try:
    from langgraph.graph import END, START, StateGraph
except Exception:
    StateGraph = None
    START = 'START'
    END = 'END'


class OrchestratorState(TypedDict):
    request: RecommendationRequest
    venues: list[Any]
    analyses: list[Any]
    curated: list[Any]
    reservation_status: dict[str, Any]
    notes: list[str]
    pipeline_logs: list[PipelineLog]
    llm_summary: str | None
    candidate_reasons: dict[str, str]
    recovery_guide: str | None


@dataclass
class SpotAIOrchestrator:
    analysis_agent: PhotoReviewAnalysisAgent
    curation_agent: RecommendationCurationAgent
    llm_reasoner: LLMReasoner
    tavily_search: Any = None  # Optional TavilyVenueSearch
    mcp_gateway: Any = None  # Optional MCPToolGateway (deprecated - using Tavily directly)

    def __post_init__(self):
        self._graph = self._build_graph() if StateGraph is not None else None

    def _build_graph(self):
        graph = StateGraph(OrchestratorState)
        graph.add_node('search', self._node_search)
        graph.add_node('analysis', self._node_analysis)
        graph.add_node('curation', self._node_curation)
        graph.add_node('reservation', self._node_reservation)
        graph.add_node('llm', self._node_llm)

        graph.add_edge(START, 'search')
        graph.add_edge('search', 'analysis')
        graph.add_edge('analysis', 'curation')
        graph.add_edge('curation', 'reservation')
        graph.add_edge('reservation', 'llm')
        graph.add_edge('llm', END)
        return graph.compile()

    def _initial_state(self, request: RecommendationRequest) -> OrchestratorState:
        return {
            'request': request,
            'venues': [],
            'analyses': [],
            'curated': [],
            'reservation_status': {},
            'notes': [],
            'pipeline_logs': [
                PipelineLog(
                    step='input',
                    status='ok',
                    detail=(
                        f"meeting_type={request.meeting_type.value}, "
                        f"team_mood={request.team_mood.value}, participants={len(request.participants)}"
                    ),
                )
            ],
            'llm_summary': None,
            'candidate_reasons': {},
            'recovery_guide': None,
        }

    def _node_search(self, state: OrchestratorState) -> OrchestratorState:
        """Search venues using Tavily + LLM analysis"""
        venues = []
        debug = {'used_provider': 'tavily'}
        status = 'ok'
        
        if self.tavily_search:
            curated_venues = self.tavily_search.search_venues(state['request'])
            if curated_venues:
                # Tavily already returns CuratedVenue objects - store directly in curated
                state['curated'] = curated_venues
                state['venues'] = [c.venue for c in curated_venues]
                state['analyses'] = [c.analysis for c in curated_venues]
                debug['result_count'] = len(curated_venues)
                debug['query'] = f"{state['request'].address} {state['request'].meeting_type.value}"
                status = 'ok'
            else:
                status = 'error'
                debug['error'] = 'Tavily search returned no results'
        else:
            status = 'error'
            debug['error'] = 'Tavily search not configured'
        
        state['pipeline_logs'].append(
            PipelineLog(
                step='search',
                status=status,
                detail=(
                    f"query={debug.get('query', '')}; "
                    f"provider={debug.get('used_provider', '')}; "
                    f"result_count={debug.get('result_count', len(state['venues']))}"
                ),
            )
        )
        
        return state

    def _node_analysis(self, state: OrchestratorState) -> OrchestratorState:
        # Skip if already analyzed by Tavily (curated already set)
        if state['curated']:
            state['pipeline_logs'].append(
                PipelineLog(step='analysis', status='skip', detail='already analyzed by Tavily LLM')
            )
            return state
        analyses = [self.analysis_agent.analyze(venue) for venue in state['venues']]
        state['analyses'] = analyses
        state['pipeline_logs'].append(
            PipelineLog(step='analysis', status='ok', detail=f'analysis_count={len(analyses)}')
        )
        return state

    def _node_curation(self, state: OrchestratorState) -> OrchestratorState:
        # Skip if already curated by Tavily
        if state['curated']:
            state['pipeline_logs'].append(
                PipelineLog(step='curation', status='skip', detail='already curated by Tavily LLM')
            )
            return state
        curated = self.curation_agent.curate(
            state['request'],
            state['venues'],
            state['analyses'],
        )
        state['curated'] = curated
        state['pipeline_logs'].append(
            PipelineLog(step='curation', status='ok', detail=f'curated_count={len(curated)}')
        )
        return state

    def _node_reservation(self, state: OrchestratorState) -> OrchestratorState:
        reservation_status = {}
        if self.mcp_gateway:
            reservation_status = self.mcp_gateway.check_reservation(
                [item.venue.id for item in state['curated']]
            )
        
        state['reservation_status'] = reservation_status
        state['pipeline_logs'].append(
            PipelineLog(
                step='reservation',
                status='ok',
                detail=f'reservation_count={len(reservation_status)}',
            )
        )
        return state

    def _node_llm(self, state: OrchestratorState) -> OrchestratorState:
        reasons: dict[str, str] = {}
        for item in state['curated'][:5]:
            reasons[item.venue.id] = self.llm_reasoner.candidate_reason(state['request'], item)

        summary = self.llm_reasoner.summarize_recommendation(state['request'], state['curated'])

        state['candidate_reasons'] = reasons
        state['llm_summary'] = summary
        state['pipeline_logs'].append(
            PipelineLog(step='llm', status='ok', detail='candidate reason generation + final summary complete')
        )
        return state

    def run(self, request: RecommendationRequest) -> RecommendationResponse:
        state = self._initial_state(request)
        if self._graph is not None:
            state = self._graph.invoke(state)
        else:
            state = self._node_search(state)
            state = self._node_analysis(state)
            state = self._node_curation(state)
            state = self._node_reservation(state)
            state = self._node_llm(state)

        notes = [
            '검색은 재시도/폴백 처리를 포함해 완료되었습니다.',
            '리뷰 + 사진 분석으로 장소 분위기를 분류했습니다.',
            '모임 유형, 팀 분위기, 예산 적합도를 반영해 순위를 계산했습니다.',
            'LangGraph 워크플로우에서 단계별 노드를 실행했습니다.',
            'LLM으로 후보별 추천 근거와 최종 요약을 생성했습니다.',
        ]

        if state['curated'] and all(item.venue.provider == 'mock' for item in state['curated']):
            notes.append('현재는 API 자격 증명이 없어 샘플 후보를 표시 중입니다.')
        else:
            notes.append('실제 지도 검색 API 결과를 기반으로 후보를 표시합니다.')

        if state['recovery_guide']:
            notes.append('검색 실패 복구 가이드를 생성했습니다.')

        return RecommendationResponse(
            candidates=state['curated'],
            reservation_status=state['reservation_status'],
            notes=notes,
            pipeline_logs=state['pipeline_logs'],
            llm_summary=state['llm_summary'],
            candidate_reasons=state['candidate_reasons'],
            recovery_guide=state['recovery_guide'],
        )

    def notify_selection(self, meeting_type: str, venue_id: str, response: RecommendationResponse) -> str:
        selected = next((v for v in response.candidates if v.venue.id == venue_id), None)
        if not selected:
            return 'No matching venue found for notification.'
        message = self.mcp_gateway.notifier.build_message(meeting_type, selected)
        return self.mcp_gateway.send_notification(message)
