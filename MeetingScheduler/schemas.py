"""
데이터 모델 정의
"""
from pydantic import BaseModel, Field
from datetime import datetime, time
from typing import Optional
from enum import Enum


class Priority(str, Enum):
    """참가자 우선순위"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Participant(BaseModel):
    """회의 참가자 정보"""
    name: str = Field(..., description="참가자 이름")
    email: str = Field(..., description="참가자 이메일")
    department: str = Field(..., description="부서")
    priority: Priority = Field(default=Priority.MEDIUM, description="우선순위")


class TimeSlot(BaseModel):
    """시간대 정보"""
    start_time: datetime = Field(..., description="시작 시간")
    end_time: datetime = Field(..., description="종료 시간")
    available_participants: list[str] = Field(..., description="가능한 참가자 목록")


class CalendarEvent(BaseModel):
    """캘린더 이벤트"""
    title: str = Field(..., description="일정 제목")
    start_time: datetime = Field(..., description="시작 시간")
    end_time: datetime = Field(..., description="종료 시간")
    is_fixed: bool = Field(default=False, description="변경 불가능 여부")
    is_external: bool = Field(default=False, description="외부 일정 여부")
    participant: str = Field(..., description="참가자 이름")


class ScheduleData(BaseModel):
    """일정 데이터"""
    participant_name: str = Field(..., description="참가자 이름")
    events: list[CalendarEvent] = Field(default_factory=list, description="일정 목록")


class MeetingRecommendation(BaseModel):
    """회의 추천 정보"""
    recommended_time: datetime = Field(..., description="추천 시간")
    available_participants: list[str] = Field(..., description="가능한 참가자 목록")
    excluded_participants: list[str] = Field(default_factory=list, description="제외된 참가자 목록")
    confidence_score: float = Field(..., description="추천도 (0-1)")
    reason: str = Field(..., description="추천 사유")


class AgentState(BaseModel):
    """Agent의 상태"""
    step: str = Field(default="input", description="현재 단계")
    participants: list[Participant] = Field(default_factory=list, description="회의 참가자 목록")
    required_duration_minutes: int = Field(default=60, description="회의 필요 시간")
    preferred_date_range: tuple[datetime, datetime] = Field(
        default=None, description="선호 날짜 범위"
    )
    calendar_data: dict[str, ScheduleData] = Field(default_factory=dict, description="수집된 캘린더 데이터")
    fixed_schedules: list[CalendarEvent] = Field(default_factory=list, description="변경 불가능 일정")
    common_available_slots: list[TimeSlot] = Field(default_factory=list, description="공통 가능 시간")
    has_common_slot: bool = Field(default=False, description="공통 가능 시간 존재 여부")
    final_recommendation: Optional[MeetingRecommendation] = Field(
        default=None, description="최종 추천 일정"
    )
    checkpoint_data: dict = Field(default_factory=dict, description="체크포인트 데이터")
    error_log: list[str] = Field(default_factory=list, description="에러 로그")


class MeetingScheduleOutput(BaseModel):
    """최종 회의 일정 출력"""
    meeting_time: datetime = Field(..., description="확정된 회의 시간")
    participants: list[str] = Field(..., description="참석 예정자")
    excluded_participants: list[str] = Field(default_factory=list, description="참석하지 않는 인원")
    meeting_link: str = Field(default="", description="회의 링크 (Teams 등)")
    status: str = Field(..., description="상태 (confirmed, tentative, failed)")
    notes: str = Field(default="", description="추가 설명")
