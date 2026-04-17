from __future__ import annotations

from dataclasses import dataclass

from spotai.models import CuratedVenue, RecommendationRequest, TeamMood, Venue, VenueAnalysis


MEETING_MOOD_PRIORITY = {
    'company': [TeamMood.formal, TeamMood.casual, TeamMood.quiet, TeamMood.lively],
    'friends': [TeamMood.lively, TeamMood.casual, TeamMood.quiet, TeamMood.formal],
    'date': [TeamMood.quiet, TeamMood.formal, TeamMood.casual, TeamMood.lively],
    'family': [TeamMood.casual, TeamMood.quiet, TeamMood.formal, TeamMood.lively],
}


@dataclass
class RecommendationCurationAgent:
    """Filter and rank venues using team mood and meeting intent."""

    def curate(
        self,
        request: RecommendationRequest,
        venues: list[Venue],
        analyses: list[VenueAnalysis],
    ) -> list[CuratedVenue]:
        analysis_map = {a.venue_id: a for a in analyses}
        priority = MEETING_MOOD_PRIORITY[request.meeting_type.value]

        curated: list[CuratedVenue] = []
        for venue in venues:
            analysis = analysis_map.get(venue.id)
            if not analysis:
                continue

            mood_bonus = 0.2 if analysis.atmosphere == request.team_mood else 0.0
            intent_bonus = max(0.0, 0.15 - (priority.index(analysis.atmosphere) * 0.04))
            budget_penalty = 0.0

            if request.budget_per_person is not None:
                expected_price = venue.price_level * 15000
                if expected_price > request.budget_per_person:
                    budget_penalty = 0.1

            score = analysis.sentiment_score + mood_bonus + intent_bonus - budget_penalty
            curated.append(CuratedVenue(venue=venue, analysis=analysis, score=round(score, 3)))

        curated.sort(key=lambda item: item.score, reverse=True)
        return curated
