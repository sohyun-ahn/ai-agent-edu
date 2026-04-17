"""
회의 일정 조율 도구 함수들
"""
from datetime import datetime, timedelta
from typing import Optional, dict, list
from schemas import (
    Participant, CalendarEvent, ScheduleData, TimeSlot,
    MeetingRecommendation, Priority
)
import json
from collections import defaultdict


def fetch_calendar_data(participant: Participant) -> ScheduleData:
    """
    참가자의 캘린더 데이터 불러오기 (시뮬레이션)
    실제로는 Teams API, Outlook API 등을 사용
    """
    # 시뮬레이션: 샘플 일정 데이터
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    sample_events = {
        "Alice": [
            CalendarEvent(
                title="Customer Meeting",
                start_time=today + timedelta(days=1, hours=10),
                end_time=today + timedelta(days=1, hours=11),
                is_fixed=True,
                is_external=True,
                participant="Alice"
            ),
            CalendarEvent(
                title="Team Standup",
                start_time=today + timedelta(days=1, hours=9),
                end_time=today + timedelta(days=1, hours=9, minutes=30),
                is_fixed=False,
                is_external=False,
                participant="Alice"
            ),
        ],
        "Bob": [
            CalendarEvent(
                title="One-on-one",
                start_time=today + timedelta(days=1, hours=14),
                end_time=today + timedelta(days=1, hours=15),
                is_fixed=False,
                is_external=False,
                participant="Bob"
            ),
        ],
        "Charlie": [
            CalendarEvent(
                title="Project Review",
                start_time=today + timedelta(days=1, hours=15),
                end_time=today + timedelta(days=1, hours=16, minutes=30),
                is_fixed=False,
                is_external=False,
                participant="Charlie"
            ),
        ],
    }
    
    events = sample_events.get(participant.name, [])
    return ScheduleData(participant_name=participant.name, events=events)


def identify_fixed_schedules(calendar_data: dict[str, ScheduleData]) -> list[CalendarEvent]:
    """
    변경 불가능한 일정 식별 (외부 미팅, 고객사 일정 등)
    LLM 또는 규칙 기반으로 분석 가능
    """
    fixed_schedules = []
    for participant_name, schedule_data in calendar_data.items():
        for event in schedule_data.events:
            # 외부 일정이거나 명시적으로 is_fixed=True인 경우
            if event.is_fixed or event.is_external:
                fixed_schedules.append(event)
    return fixed_schedules


def standardize_schedule_data(calendar_data: dict[str, ScheduleData]) -> dict[str, ScheduleData]:
    """
    원시 캘린더 데이터를 표준화된 형식으로 변환
    Timezone 처리, 형식 정규화 등
    """
    standardized = {}
    for participant_name, schedule_data in calendar_data.items():
        # 시간 정렬
        sorted_events = sorted(
            schedule_data.events,
            key=lambda e: e.start_time
        )
        standardized[participant_name] = ScheduleData(
            participant_name=participant_name,
            events=sorted_events
        )
    return standardized


def find_common_available_slots(
    participants: list[Participant],
    calendar_data: dict[str, ScheduleData],
    required_duration_minutes: int,
    date_range: tuple[datetime, datetime],
    fixed_schedules: list[CalendarEvent] = None
) -> list[TimeSlot]:
    """
    모든 참가자가 가능한 시간대 추출
    """
    if fixed_schedules is None:
        fixed_schedules = []
    
    common_slots = []
    
    # 날짜 범위로 시간대 생성 (30분 단위)
    current_time = date_range[0].replace(hour=9, minute=0)  # 업무 시작 시간
    end_time = date_range[1].replace(hour=18, minute=0)     # 업무 종료 시간
    
    while current_time < end_time:
        slot_end = current_time + timedelta(minutes=required_duration_minutes)
        
        if slot_end > end_time:
            break
        
        # 모든 참가자가 이 시간에 가능한지 확인
        available_participants = []
        is_available_for_all = True
        
        for participant in participants:
            participant_data = calendar_data.get(participant.name)
            if not participant_data:
                continue
            
            # 이 시간에 다른 일정이 없는지 확인
            has_conflict = False
            for event in participant_data.events:
                # 시간이 겹치는지 확인
                if (event.start_time < slot_end and event.end_time > current_time):
                    has_conflict = True
                    break
            
            if not has_conflict:
                available_participants.append(participant.name)
            else:
                is_available_for_all = False
        
        # 모든 참가자가 가능한 경우에만 추가
        if len(available_participants) == len([p for p in participants if p.name in [ap for ap in available_participants]]):
            common_slots.append(TimeSlot(
                start_time=current_time,
                end_time=slot_end,
                available_participants=available_participants
            ))
        
        current_time += timedelta(minutes=30)
    
    return common_slots


def find_alternative_slots(
    participants: list[Participant],
    calendar_data: dict[str, ScheduleData],
    required_duration_minutes: int,
    date_range: tuple[datetime, datetime],
    common_slots: list[TimeSlot],
    fixed_schedules: list[CalendarEvent] = None
) -> list[MeetingRecommendation]:
    """
    대체 회의 시간 추천 (일부 인원 제외, 우선순위 반영)
    """
    if fixed_schedules is None:
        fixed_schedules = []
    
    recommendations = []
    
    # 우선순위가 높은 참가자순으로 정렬
    sorted_participants = sorted(
        participants,
        key=lambda p: (p.priority == Priority.HIGH, p.priority == Priority.MEDIUM),
        reverse=True
    )
    
    # 날짜 범위로 시간대 생성
    current_time = date_range[0].replace(hour=9, minute=0)
    end_time = date_range[1].replace(hour=18, minute=0)
    
    candidate_slots = []
    while current_time < end_time:
        slot_end = current_time + timedelta(minutes=required_duration_minutes)
        if slot_end > end_time:
            break
        
        available_count = 0
        available_participants = []
        excluded_participants = []
        
        for participant in sorted_participants:
            participant_data = calendar_data.get(participant.name)
            if not participant_data:
                available_count += 1
                available_participants.append(participant.name)
                continue
            
            has_conflict = False
            for event in participant_data.events:
                if event.start_time < slot_end and event.end_time > current_time:
                    has_conflict = True
                    break
            
            if not has_conflict:
                available_count += 1
                available_participants.append(participant.name)
            else:
                excluded_participants.append(participant.name)
        
        # 60% 이상의 참가자가 가능한 경우만 고려
        if available_count >= len(sorted_participants) * 0.6:
            confidence = available_count / len(sorted_participants)
            candidate_slots.append({
                "time": current_time,
                "available": available_participants,
                "excluded": excluded_participants,
                "confidence": confidence
            })
        
        current_time += timedelta(minutes=30)
    
    # 상위 3개의 추천 생성
    sorted_candidates = sorted(
        candidate_slots,
        key=lambda x: (len(x["available"]), x["confidence"]),
        reverse=True
    )[:3]
    
    for i, candidate in enumerate(sorted_candidates):
        reason = f"우선순위 {len(candidate['available'])}/{len(participants)} 가능, "
        reason += f"제외: {', '.join(candidate['excluded']) if candidate['excluded'] else '없음'}"
        
        recommendations.append(MeetingRecommendation(
            recommended_time=candidate["time"],
            available_participants=candidate["available"],
            excluded_participants=candidate["excluded"],
            confidence_score=candidate["confidence"],
            reason=reason
        ))
    
    return recommendations


def select_optimal_meeting_time(
    common_slots: list[TimeSlot],
    recommendations: list[MeetingRecommendation],
    has_common_slot: bool
) -> Optional[MeetingRecommendation]:
    """
    최적 회의 시간 선택
    - 공통 가능 시간이 있으면 가장 빠른 시간
    - 없으면 우선순위 반영한 추천 중 최고 순위 선택
    """
    if has_common_slot and common_slots:
        # 가장 빠른 공통 시간 선택
        earliest_slot = min(common_slots, key=lambda s: s.start_time)
        return MeetingRecommendation(
            recommended_time=earliest_slot.start_time,
            available_participants=earliest_slot.available_participants,
            excluded_participants=[],
            confidence_score=1.0,
            reason="모든 참가자가 가능한 시간"
        )
    elif recommendations:
        # 추천 중 최고 점수 선택
        return recommendations[0]
    
    return None


def send_meeting_invitation(
    meeting_time: MeetingRecommendation,
    participants: list[Participant]
) -> dict:
    """
    회의 초대장 발송
    실제로는 Teams API, 이메일 등을 사용
    """
    return {
        "status": "sent",
        "meeting_time": meeting_time.recommended_time.isoformat(),
        "participants": meeting_time.available_participants,
        "excluded_participants": meeting_time.excluded_participants,
        "teams_link": f"https://teams.microsoft.com/l/meetup-join/{meeting_time.recommended_time.timestamp()}",
        "message": f"회의 일정: {meeting_time.recommended_time.strftime('%Y-%m-%d %H:%M')}",
        "timestamp": datetime.now().isoformat()
    }


def save_checkpoint(state: dict, checkpoint_key: str) -> dict:
    """
    체크포인트 저장 (실패 시 복구용)
    """
    return {
        "checkpoint_key": checkpoint_key,
        "timestamp": datetime.now().isoformat(),
        "state_snapshot": state
    }


def load_checkpoint(checkpoint_data: dict, checkpoint_key: str) -> Optional[dict]:
    """
    체크포인트 로드
    """
    if checkpoint_key in checkpoint_data:
        return checkpoint_data[checkpoint_key]
    return None


def retry_with_fallback(
    primary_func,
    fallback_func,
    max_retries: int = 3,
    *args,
    **kwargs
):
    """
    재시도 및 폴백 로직
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            last_error = e
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            continue
    
    # 모든 재시도 실패 시 폴백
    try:
        return fallback_func(*args, **kwargs)
    except Exception as e:
        return {
            "status": "failed",
            "error": str(last_error),
            "fallback_error": str(e)
        }
