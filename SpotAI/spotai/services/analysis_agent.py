from __future__ import annotations

from dataclasses import dataclass

from spotai.models import TeamMood, Venue, VenueAnalysis


@dataclass
class PhotoReviewAnalysisAgent:
    """Analyze review text and image tags to estimate sentiment and atmosphere."""

    def analyze(self, venue: Venue) -> VenueAnalysis:
        text = venue.review_text.lower()
        tags = {tag.lower() for tag in venue.image_tags}

        sentiment = min(0.99, 0.5 + ((venue.rating - 3.0) / 2.0) * 0.45)

        if {'private-room', 'calm', 'soft-light'} & tags:
            mood = TeamMood.formal
            reasons = ['Photo tags indicate private and calm seating']
        elif {'noisy', 'open-kitchen'} & tags:
            mood = TeamMood.lively
            reasons = ['Photo tags indicate lively and active environment']
        elif 'cozy' in text or 'warm-light' in tags:
            mood = TeamMood.casual
            reasons = ['Reviews and images indicate a casual atmosphere']
        else:
            mood = TeamMood.quiet
            reasons = ['No strong lively cues detected; treated as quiet']

        if 'busy' in text:
            reasons.append('Reviews mention busy times around evening')

        return VenueAnalysis(
            venue_id=venue.id,
            sentiment_score=round(sentiment, 2),
            atmosphere=mood,
            reasons=reasons,
        )
