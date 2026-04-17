from enum import Enum
from pydantic import BaseModel, Field


class MeetingType(str, Enum):
    company = 'company'
    friends = 'friends'
    date = 'date'
    family = 'family'


class TeamMood(str, Enum):
    casual = 'casual'
    formal = 'formal'
    lively = 'lively'
    quiet = 'quiet'


class ParticipantLocation(BaseModel):
    name: str
    address: str


class RecommendationRequest(BaseModel):
    meeting_type: MeetingType
    team_mood: TeamMood
    address: str | None = None  # Main meeting location
    participants: list[ParticipantLocation] = Field(default_factory=list)
    budget_per_person: int | None = None


class Venue(BaseModel):
    id: str
    name: str
    address: str
    price_level: int
    rating: float
    review_text: str
    provider: str = 'mock'
    category: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    image_tags: list[str] = Field(default_factory=list)


class VenueAnalysis(BaseModel):
    venue_id: str
    sentiment_score: float
    atmosphere: TeamMood
    reasons: list[str]


class CuratedVenue(BaseModel):
    venue: Venue
    analysis: VenueAnalysis
    score: float


class ReservationStatus(BaseModel):
    venue_id: str
    is_available: bool
    source: str


class PipelineLog(BaseModel):
    step: str
    status: str
    detail: str


class RecommendationResponse(BaseModel):
    candidates: list[CuratedVenue]
    reservation_status: dict[str, ReservationStatus]
    notes: list[str] = Field(default_factory=list)
    pipeline_logs: list[PipelineLog] = Field(default_factory=list)
    llm_summary: str | None = None
    candidate_reasons: dict[str, str] = Field(default_factory=dict)
    recovery_guide: str | None = None
    llm_summary: str | None = None
    rag_sources: list[str] = Field(default_factory=list)
