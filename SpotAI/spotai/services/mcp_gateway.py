from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from spotai.models import RecommendationRequest, ReservationStatus, Venue
from spotai.services.map_search import MapSearchService
from spotai.services.notifier import TeamsNotifier
from spotai.services.reservation_service import ReservationService


@dataclass
class MCPToolGateway:
    map_service: MapSearchService
    reservation_service: ReservationService
    notifier: TeamsNotifier
    use_mcp_tools: bool = False
    mcp_base_url: str | None = None
    mcp_search_path: str = '/tools/search'
    mcp_reservation_path: str = '/tools/reservation'
    mcp_notify_path: str = '/tools/notify'

    last_tool_debug: dict[str, str] | None = None

    def search_venues(self, request: RecommendationRequest) -> list[Venue]:
        self.last_tool_debug = None
        if not self.use_mcp_tools or not self.mcp_base_url:
            venues = self.map_service.find_venues(request)
            self.last_tool_debug = self.map_service.last_search_debug
            return venues

        payload = {
            'meeting_type': request.meeting_type.value,
            'team_mood': request.team_mood.value,
            'budget_per_person': request.budget_per_person,
            'participants': [p.model_dump() for p in request.participants],
        }
        data = self._post_json(self.mcp_search_path, payload)
        self.last_tool_debug = data.get('search_debug')
        return [Venue.model_validate(v) for v in data.get('venues', [])]

    def check_reservation(self, venue_ids: list[str]) -> dict[str, ReservationStatus]:
        if not self.use_mcp_tools or not self.mcp_base_url:
            return self.reservation_service.check_availability(venue_ids)

        data = self._post_json(self.mcp_reservation_path, {'venue_ids': venue_ids})
        raw = data.get('reservation_status', {})
        return {k: ReservationStatus.model_validate(v) for k, v in raw.items()}

    def send_notification(self, message: str) -> str:
        if not self.use_mcp_tools or not self.mcp_base_url:
            return self.notifier.send(message)

        data = self._post_json(self.mcp_notify_path, {'message': message})
        return data.get('result', 'MCP notify request sent')

    def _post_json(self, path: str, payload: dict) -> dict:
        url = f"{self.mcp_base_url.rstrip('/')}/{path.lstrip('/')}"
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        request = Request(
            url,
            data=body,
            method='POST',
            headers={'Content-Type': 'application/json'},
        )
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        return data
