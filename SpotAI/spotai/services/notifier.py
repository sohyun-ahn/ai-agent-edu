from __future__ import annotations

from dataclasses import dataclass

from spotai.models import CuratedVenue


@dataclass
class TeamsNotifier:
    webhook_url: str | None = None

    def build_message(self, meeting_type: str, selected: CuratedVenue) -> str:
        return (
            f'[SpotAI] Final venue for {meeting_type}: {selected.venue.name} '
            f'({selected.venue.address}) with score {selected.score}'
        )

    def send(self, message: str) -> str:
        # This demo does not post externally unless webhook integration is added.
        if self.webhook_url:
            return f'Teams webhook configured. Message prepared: {message}'
        return f'Mock Teams notification sent: {message}'
