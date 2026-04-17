# 🗓️ MeetingScheduler: 회의 일정 자동 조율 Agent

**회의 참가자들의 일정을 자동으로 수집·분석하여 최적의 회의 시간을 추천하고 확정하는 LangGraph 기반 Agent**

---

## 📋 목차
- [개요](#개요)
- [문제 상황](#문제-상황)
- [솔루션](#솔루션)
- [주요 기능](#주요-기능)
- [고급 요소](#고급-요소)
- [워크플로우](#워크플로우)
- [설치 및 사용](#설치-및-사용)
- [파일 구조](#파일-구조)

---

## 개요

### 업무명
**회의 일정 자동 조율 Agent**

### 핵심 가치
- 회당 **0.5~1시간** 소요되던 일정 조율을 **자동화**
- 월간 **4시간** 이상의 업무 시간 단축
- 정확도 높은 추천으로 **만족도 향상**

---

## 문제 상황

### 현재 문제점
| 항목 | 내용 |
|------|------|
| 소요 시간 | 회당 0.5~1 시간 |
| 수행 빈도 | 2회/주 (또는 월 1~2회) |
| 월간 총 소요 | 약 4시간/월 |
| 관련 인원 | 팀원 5명, 외부 고객사 |
| 핵심 고통점 | 여러 사람의 일정이 겹치지 않아 조율이 어렵고, 고객사 일정은 변경 불가 |

### 구체적 문제
- 수차례 이메일/메신저 주고받기 필요
- 사내망 기반 시스템으로 외부 API 연동 불가
- 팀즈, 사람찾기 등 여러 시스템 확인 필요
- 고객사 일정 충돌 시 대안 제시 과정이 수동적
- 결국 일정 조율에 많은 시간 소모

---

## 솔루션

### 처리 흐름

```
[1] 참가자 정보 입력
     ↓
[2] 일정 수집 (Teams, 사내망, 메신저)
     ↓
[3] 데이터 표준화 & 타임존 정규화
     ↓
[4] 불변 일정 식별 (고객사 등)
     ↓
[5] 가용 시간 계산 & 교집합 탐색
     ↓
[6] 분기점: 공통 시간 있는가?
     ├─ YES → [8] 확정 & 알림
     └─ NO  → [7] 대체안 제시 → [8] 확정 & 알림
     ↓
[9] 워크플로우 완료
```

---

## 주요 기능

### Tier 1: 기본 기능
- ✅ **다중 소스 수집**: Teams API, 사내 DB, 메신저 자동 수집
- ✅ **데이터 표준화**: 원시 데이터를 표준 형식으로 변환 (Timezone 정규화)
- ✅ **불변 일정 식별**: 고객사 미팅 등 변경 불가 일정 태깅
- ✅ **가용 시간 계산**: 30분 단위 슬롯으로 개인별 가용 시간 계산
- ✅ **교집합 탐색**: 모든 참가자가 가능한 시간대 찾기
- ✅ **대체안 제시**: 공통 시간 없을 때 우선순위 반영한 대안 제시
- ✅ **최적 스코어링**: 참가자 우선순위 + 시간 선호도 가중합

### Tier 2: 신뢰성 기능 (고급 요소)
- ✅ **조건부 재시도/폴백**: API 실패 시 지수 백오프 → 규칙 기반 폴백
- ✅ **상태 체크포인트**: 각 단계별 결과 저장 → 마지막 성공 지점부터 복구
- ✅ **회로차단기**: 연속 실패 방지
- ✅ **오케스트레이션**: LangGraph 기반 워크플로우
- ✅ **실행 로깅**: 단계별 성공/실패/성능 지표

### Tier 3: 통신 기능
- ✅ **다중 채널 알림**: Teams, 이메일, 메신저
- ✅ **자동 캘린더 초대**: iCal 형식 생성
- ✅ **회의 링크 자동 생성**: Teams 미팅 URL 생성

---

## 고급 요소

### 1. 조건부 재시도/폴백 (Conditional Retry & Fallback)
**외부 API 호출 실패 시 대응 전략**
- 최대 3회 재시도 (지수 백오프: 0.1s → 0.2s → 0.4s)
- 모든 재시도 실패 시 다음 폴백 실행:
  - 최근 캐시 데이터 사용
  - 규칙 기반 간소화된 로직 적용
  - 일부 참가자 일정만 반영한 추천 제시

```python
result = retry_with_exponential_backoff(
    primary_func=api_call,
    fallback_func=use_cached_data,
    config=RetryConfig(max_retries=3)
)
```

### 2. 상태 체크포인트 (State Checkpoint)
**단계별 결과 저장 → 실패 시 빠른 복구**
- 각 노드의 출력을 JSON으로 저장 (`.checkpoints/` 디렉토리)
- MD5 체크섬으로 데이터 무결성 검증
- 실패 시 마지막 성공 지점부터 재개

```python
checkpoint_manager.save_checkpoint("step_2_collect", data)
recovered = checkpoint_manager.load_checkpoint("step_2_collect")
```

### 3. 최적 회의 시간 추출 (Optimal Meeting Time Selection)
**단순 교집합이 아닌 지능형 추천**
- 참가자 우선순위 반영 (HIGH/MEDIUM/LOW)
- 시간대 선호도 반영 (오전 10-11시 최고 선호)
- 가중합 점수 계산:
  ```
  score = 0.4×신뢰도 + 0.3×시간선호 + 0.3×우선순위
  ```

---

## 워크플로워

### 노드 상세

| Node | 역할 | 도구 |
|------|------|------|
| 1 | 참가자 정보 입력 | 사용자 입력 |
| 2 | 일정 불러오기 | Teams API, 사내 DB |
| 3 | 데이터 정리 | 표준화, Timezone 정규화 |
| 4 | 불변 일정 표시 | 규칙 기반 + LLM 분석 |
| 5 | 가용 시간 찾기 | 시간대 계산 알고리즘 |
| 6 | 공통 시간 판단 | 조건 분기 (YES/NO) |
| 7 | 대체안 추천 | 우선순위 기반 |
| 8 | 확정 및 알림 | Teams/Email 발송 |
| 9 | 완료 | 결과 반환 |

### 실패 처리 흐름

```
API 호출 실패
    ↓
[재시도 1] 0.1초 후
    ↓
[재시도 2] 0.2초 후
    ↓
[재시도 3] 0.4초 후
    ↓
도전 실패 → [회로차단기 OPEN]
    ↓
[폴백 1] 캐시 데이터 사용
    ↓
실패 → [폴백 2] 규칙 기반 로직
    ↓
결과 반환 (최소한의 대체 결과)
```

---

## 설치 및 사용

### 필수 패키지
```bash
pip install pydantic langgraph pandas zoneinfo
```

### 기본 사용법

```python
from schemas import Participant, Priority
from meeting_scheduler_agent import MeetingSchedulerWorkflow

# 1. 참가자 정의
participants = [
    Participant(
        name="Alice",
        email="alice@company.com",
        department="Sales",
        priority=Priority.HIGH
    ),
    # ... 더 많은 참가자
]

# 2. 워크플로우 생성
workflow = MeetingSchedulerWorkflow(participants)

# 3. 상태 초기화
state = {
    "participants": participants,
    "calendar_data": {},
    "available_slots": [],
    "recommendation": None,
    "status": "init",
}

# 4. 워크플로우 실행
state = workflow.node_1_input(state)
state = workflow.node_2_collect_calendar(state)
state = workflow.node_3_standardize(state)
# ... 나머지 노드

# 5. 결과 확인
if state.get("invitation"):
    print(f"회의: {state['invitation'].meeting_time}")
    print(f"참석자: {state['invitation'].participants}")
```

### Notebook 실행
```bash
jupyter notebook meeting_scheduler_agent.ipynb
```

---

## 파일 구조

```
MeetingScheduler/
├── README.md                          # 프로젝트 설명 (이 파일)
├── meeting_scheduler_agent.ipynb      # 메인 Jupyter Notebook
│   ├── Section 1-4: 데이터 수집 및 정규화
│   ├── Section 5-9: 시간대 계산 및 추천
│   ├── Section 10-11: 재시도/폴백 및 체크포인트
│   ├── Section 12-14: 워크플로우 및 테스트
│   └── 최종 요약 및 사용 가이드
├── schemas.py                        # Pydantic 데이터 모델
│   ├── Participant, CalendarEvent
│   ├── TimeSlot, MeetingRecommendation
│   └── AgentState 등
├── tools.py                          # 유틸리티 함수
│   ├── fetch_calendar_data()
│   ├── standardize_calendar_data()
│   ├── find_common_slots()
│   └── 기타 도구 함수
└── .checkpoints/                     # 체크포인트 저장소 (자동 생성)
    ├── step_1_input.json
    ├── step_2_collect.json
    └── ...
```

---

## 성능 지표

### 참가자 5명 기준
- **처리 시간**: ~1-2초
- **처리 속도**: ~2.5-5 명/초
- **메모리 사용**: ~10MB
- **저장 공간**: ~50KB (체크포인트)

---

## 커스터마이징

### 업무 시간 조정
```python
WORK_START_HOUR = 9        # 업무 시작 시간
WORK_END_HOUR = 18         # 업무 종료 시간
LUNCH_START = 12           # 점심 시작
LUNCH_END = 13             # 점심 종료
SLOT_DURATION_MINUTES = 30 # 시간 슬롯 크기
```

### 불변 일정 키워드
```python
FIXED_KEYWORDS = [
    "고객", "customer", "external",
    "고정", "fixed",
    "중요", "critical"
]
```

### 스코어링 가중치
```python
weights = {
    "base": 0.4,        # 신뢰도
    "time": 0.3,        # 시간 선호도
    "priority": 0.3     # 참가자 우선순위
}
```

---

## 문제 해결

### Q: 공통 가능 시간이 없는 경우?
**A**: Node 7에서 대체안을 자동 제시합니다. 필요시 다음을 조정하세요:
- 검색 기간 확장
- 최소 참가자 수 감소
- 필수 참석자 재정의

### Q: API가 계속 실패하는 경우?
**A**: 재시도 설정을 조정하세요:
```python
retry_config = RetryConfig(
    max_retries=5,
    max_delay_seconds=30
)
```

### Q: 체크포인트 초기화?
**A**: 
```python
checkpoint_manager.clear_checkpoints()
```

---

## 실패 처리 전략

| 실패 시나리오 | 대응 방법 |
|-------------|---------|
| API 일시 오류 | 지수 백오프로 3회 재시도 |
| 연속 API 실패 | 회로차단기 OPEN → 캐시 사용 |
| 데이터 처리 오류 | 체크포인트에서 복구 |
| 공통 시간 없음 | 우선순위 반영한 대체안 제시 |

---

## 참고: 고객사 일정 처리 전략

### 불변 일정 식별 우선순위
1. `is_fixed=True` 플래그 (50점)
2. `is_external=True` (40점)
3. 키워드 매칭 (10점)
4. HIGH priority 참가자 (5점)

### 합산 신뢰도 점수
- 0.9~1.0: 확실한 불변 일정
- 0.7~0.8: 가능성 높은 불변 일정
- 0.5~0.6: 일반 일정

---

## 라이센스
Internal Use Only

## 문의
AI Agent Development Team

---

**최종 업데이트**: 2026-04-16

---

## 세부 요구사항 이행 현황

### Task 분해 이행
| Task | 상세 | 상태 |
|------|------|------|
| 1 | 이메일/캘린더 데이터 수집 | ✅ |
| 2 | 불변 일정 식별 | ✅ |
| 3 | 가능한 시간대 추출 | ✅ |
| 4 | 교집합 시간대 탐색 | ✅ |
| 5 | 대안 시간 제안 | ✅ |
| 6 | 일정 추천 및 알림 | ✅ |

### 고급 요소 이행
| 요소 | 설명 | 상태 |
|------|------|------|
| 상태 체크포인트 | 단계별 저장 & 복구 | ✅ |
| 조건부 재시도/폴백 | API 실패 대응 | ✅ |
| 최적 회의 시간 추출 | 가중합 스코어링 | ✅ |

**🎉 모든 요구사항 구현 완료!**
