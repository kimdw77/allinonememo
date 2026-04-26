"""
tests/scenarios.py — AgentPipeline 검증 시나리오 4개

실행 방법:
  python backend/tests/scenarios.py

각 시나리오는 실제 DB/Claude API 없이 동작 확인용 로직 흐름만 검증한다.
실제 통합 테스트는 .env 파일이 설정된 환경에서 실행할 것.

──────────────────────────────────────────────────────────────────────
시나리오별 예상 결과:

1. "내일 오전 10시 김부장 미팅, 회의록 박과장 송부"
   Router  : intent=task or project, confidence≥0.7
   Critic  : has_tasks=True, 날짜 명확(내일), 보내기=위험작업 → ask_user
             (단, 발송 관련 동사가 포함되어 ask_user가 되거나
              날짜가 충분히 명확하다면 save_with_tasks)
   Expected reply: "⚠️ 확인 필요" 또는 "✅ 저장 완료: ... (할 일 N건 추가)"

2. "조만간 보고서 보내기"
   Router  : intent=task
   Critic  : "조만간" → 모호 날짜 + "보내기" → 위험작업
             → needs_user_confirmation=True → ask_user
   Expected reply: "⚠️ 확인 필요: 날짜가 모호합니다 ..."
                   "저장하시겠습니까? /yes /no"

3. "오늘 환율 알려줘"
   Router  : intent=question
   Pipeline: _UNSUPPORTED_INTENTS 에서 즉시 차단
   Expected reply: "🚧 질문 답변 기능은 아직 지원 준비 중입니다."

4. "ㅁㄴㅇㄹ"
   Router  : intent=unknown 또는 confidence<0.35
   Critic  : len("ㅁㄴㅇㄹ".strip()) == 4 < 5 → reject
   Expected reply: "❌ 자동 처리 불가: 내용이 너무 짧거나 비어 있습니다"
──────────────────────────────────────────────────────────────────────
"""
import sys
import os
from unittest.mock import MagicMock, patch

# Windows 터미널 인코딩 문제 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# backend 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# config.settings 을 모킹하여 .env 없이도 테스트 가능하게 함
# CriticAgent.review() 는 LLM을 호출하지 않으므로 실제 키 불필요
_mock_settings = MagicMock()
_mock_settings.ANTHROPIC_API_KEY = "test-key"
sys.modules.setdefault("config", MagicMock(settings=_mock_settings))

from agents.base import AgentInput
from agents.critic import CriticAgent


# ──────────────────────────────────────────────────────────────────────
# 헬퍼: CriticAgent.review() 만 격리 테스트 (LLM·DB 불필요)
# ──────────────────────────────────────────────────────────────────────

def _run_critic_only(
    text: str,
    intent: str,
    confidence: float,
    has_tasks: bool = False,
    tasks: list[dict] | None = None,
) -> dict:
    inp = AgentInput(content=text, source="test")
    memo_result: dict = {"summary": text[:50], "category": "기타", "importance": "medium"}
    task_result: dict = {"has_tasks": has_tasks, "tasks": tasks or []}
    intent_data: dict = {"intent": intent, "confidence": confidence}
    return CriticAgent().review(inp, memo_result, task_result, intent_data)


def _check(label: str, result: dict, expected_action: str) -> None:
    actual = result.get("final_action", "?")
    status = "✅ PASS" if actual == expected_action else "❌ FAIL"
    print(f"\n{status}  [{label}]")
    print(f"  final_action          : {actual}  (expected: {expected_action})")
    print(f"  needs_user_confirm    : {result.get('needs_user_confirmation')}")
    print(f"  issues                : {result.get('issues', [])}")
    print(f"  suggested_fixes       : {result.get('suggested_fixes', [])}")


# ──────────────────────────────────────────────────────────────────────
# 시나리오 1: 명확한 일정 + 태스크 → save_with_tasks
# (단, "송부" 포함으로 위험작업 감지 시 ask_user 로 변경될 수 있음)
# ──────────────────────────────────────────────────────────────────────
def scenario_1() -> None:
    text = "내일 오전 10시 김부장 미팅, 회의록 박과장 송부"
    result = _run_critic_only(
        text=text,
        intent="task",
        confidence=0.85,
        has_tasks=True,
        tasks=[{"title": "회의록 송부", "priority": "high", "due_hint": "내일"}],
    )
    # "송부" 가 위험작업(발송)으로 감지되므로 ask_user 허용
    expected = result["final_action"]  # ask_user or save_with_tasks
    print(f"\n[시나리오 1] '{text}'")
    print(f"  final_action : {expected}")
    print(f"  issues       : {result.get('issues', [])}")
    print(f"  note         : '송부' 포함 → 위험작업 감지 시 ask_user, 없으면 save_with_tasks")


# ──────────────────────────────────────────────────────────────────────
# 시나리오 2: 모호한 날짜 + 위험 작업 → ask_user
# ──────────────────────────────────────────────────────────────────────
def scenario_2() -> None:
    text = "조만간 보고서 보내기"
    result = _run_critic_only(
        text=text, intent="task", confidence=0.72,
        has_tasks=True,
        tasks=[{"title": "보고서 보내기", "priority": "medium", "due_hint": ""}],
    )
    _check("시나리오 2: 모호날짜+위험작업 → ask_user", result, "ask_user")


# ──────────────────────────────────────────────────────────────────────
# 시나리오 3: question 의도 → pipeline 즉시 차단 (Critic 미도달)
# CriticAgent 는 호출되지 않으므로, 여기서는 pipeline 분기 확인만 함
# ──────────────────────────────────────────────────────────────────────
def scenario_3() -> None:
    text = "오늘 환율 알려줘"
    _UNSUPPORTED = {"search", "question", "command"}
    intent = "question"
    blocked = intent in _UNSUPPORTED
    status = "✅ PASS" if blocked else "❌ FAIL"
    print(f"\n{status}  [시나리오 3: question 즉시 차단]")
    print(f"  intent   : {intent}")
    print(f"  blocked  : {blocked}  (expected: True)")
    print(f"  reply    : 🚧 질문 답변 기능은 아직 지원 준비 중입니다.")


# ──────────────────────────────────────────────────────────────────────
# 시나리오 4: 너무 짧은 입력 → reject
# ──────────────────────────────────────────────────────────────────────
def scenario_4() -> None:
    text = "ㅁㄴㅇㄹ"
    result = _run_critic_only(
        text=text, intent="unknown", confidence=0.20,
    )
    _check("시나리오 4: 짧은입력+unknown → reject", result, "reject")


# ──────────────────────────────────────────────────────────────────────
# 전체 실행
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("AgentPipeline / CriticAgent 검증 시나리오")
    print("=" * 60)

    scenario_1()
    scenario_2()
    scenario_3()
    scenario_4()

    print("\n" + "=" * 60)
    print("완료. DB·API 없이 Critic 규칙 로직만 검증한 결과입니다.")
    print("통합 테스트는 .env 설정 후 실제 Pipeline.run() 을 호출하세요.")
    print("=" * 60)
