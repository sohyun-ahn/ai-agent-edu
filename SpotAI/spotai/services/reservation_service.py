from __future__ import annotations

import random
from dataclasses import dataclass

from spotai.models import ReservationStatus


@dataclass
class ReservationService:
    provider_name: str = 'naver-reservation'

    def check_availability(self, venue_ids: list[str]) -> dict[str, ReservationStatus]:
        result: dict[str, ReservationStatus] = {}
        for venue_id in venue_ids:
            is_available = random.random() > 0.25
            result[venue_id] = ReservationStatus(
                venue_id=venue_id,
                is_available=is_available,
                source=self.provider_name,
            )
        return result
