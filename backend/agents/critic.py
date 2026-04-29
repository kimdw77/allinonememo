"""
agents/critic.py — 아이디어·계획·내용에 대한 비판적 검토 및 피드백

두 가지 모드:
  review()  — 파이프라인 품질 게이트 (규칙 기반, LLM 호출 없음, 빠름)
  run()     — /critique 명령어 전용 (LLM 기반, 상세 피드백)
"""
import json
import logging
import re

import anthropic

from agents.base import AgentInput, AgentOutput, BaseAgent
from config import settings

logger = logging.getLogger(__name__)

# ── 품질 게이트 규칙 ──────────────────────────────────────────────
_AMBIGUOUS_DATES = re.compile(
    r'다음\s*주|나중에|조만간|언제|곧|이번에|언젠가|추후|향후|이따가'
)
_DANGEROUS_OPS = re.compile(
    r'삭제|발송|공개|보내기|전달|취소|제거|폐기|배포|게시'
)

_CRITIC_PROMPT = """다음 내용을 비판적으로 검토하라. 한국어로 응답. JSON으로만 응답.

내용: {content}

{{"strengths":["강점1","강점2"],"weaknesses":["약점1","약점2"],"suggestions":["개선안1","개선안2"],"verdict":"한 줄 총평","score":1-10}}

평가 기준:
- strengths: 내용의 실질적 장점 (최소 1개, 최대 3개)
- weaknesses: 보완이 필요한 부분 (최소 1개, 최대 3개)
- suggestions: 구체적이고 실행 가능한 개선 제안 (최소 1개, 최대 3개)
- score: 전반적 완성도 1~10점

JSON만 반환. 설명 없음."""


class CriticAgent(BaseAgent):
    name = "critic"

    def review(
        self,
        inp: AgentInput,
        memo_result: dict,
        task_result: dict,
        intent_data: dict,
    ) -> dict:
        """
        파이프라인 품질 게이트 (규칙 기반, LLM 호출 없음).
        반환: {approved, needs_user_confirmation, issues, suggested_fixes, final_action}
        final_action: "save" | "save_with_tasks" | "ask_user" | "reject"
        """
        issues: list[str] = []
        suggested_fixes: list[str] = []
        needs_confirmation = False

        # 1. 빈 내용 또는 너무 짧은 입력 → reject
        stripped = inp.content.strip()
        if not stripped or len(stripped) < 5:
            return {
                "approved": False,
                "needs_user_confirmation": False,
                "issues": ["내용이 너무 짧거나 비어 있습니다"],
                "suggested_fixes": ["구체적인 내용을 입력해 주세요"],
                "final_action": "reject",
            }

        # 1-b. unknown 의도 → reject (분류 불가 입력)
        if intent_data.get("intent") == "unknown":
            return {
                "approved": False,
                "needs_user_confirmation": False,
                "issues": ["입력 내용을 인식할 수 없습니다"],
                "suggested_fixes": ["더 구체적인 내용을 입력해 주세요"],
                "final_action": "reject",
            }

        # 1-c. 극히 낮은 신뢰도 → reject (0.35 미만)
        if float(intent_data.get("confidence", 1.0)) < 0.35:
            return {
                "approved": False,
                "needs_user_confirmation": False,
                "issues": [f"입력 의도를 신뢰할 수 없습니다 (신뢰도 {intent_data.get('confidence', 0):.0%})"],
                "suggested_fixes": ["더 명확하게 입력해 주세요"],
                "final_action": "reject",
            }

        # 2. 모호한 날짜 표현
        if _AMBIGUOUS_DATES.search(inp.content):
            issues.append("날짜가 모호합니다 (다음 주, 나중에 등)")
            suggested_fixes.append("구체적인 날짜를 명시해 주세요")
            needs_confirmation = True

        # 3. 위험한 외부 작업 표현
        if _DANGEROUS_OPS.search(inp.content):
            issues.append("위험한 작업이 포함될 수 있습니다 (삭제·발송·공개 등)")
            suggested_fixes.append("의도한 작업이 맞는지 확인해 주세요")
            needs_confirmation = True

        # 4. 낮은 분류 신뢰도
        confidence = intent_data.get("confidence", 1.0)
        if confidence < 0.6:
            issues.append(f"분류 신뢰도가 낮습니다 ({confidence:.0%})")
            needs_confirmation = True

        # 5. 우선순위 높은 태스크에 기한 없음
        tasks = task_result.get("tasks", [])
        unclear_high = [
            t for t in tasks
            if t.get("priority") == "high" and not t.get("due_hint")
        ]
        if unclear_high:
            issues.append("우선순위 높은 태스크의 기한이 불명확합니다")
            suggested_fixes.append("기한을 추가하면 더 효과적으로 관리할 수 있습니다")
            needs_confirmation = True

        # final_action 결정
        has_tasks = task_result.get("has_tasks", False)
        if needs_confirmation:
            final_action = "ask_user"
        elif has_tasks:
            final_action = "save_with_tasks"
        else:
            final_action = "save"

        return {
            "approved": not needs_confirmation,
            "needs_user_confirmation": needs_confirmation,
            "issues": issues,
            "suggested_fixes": suggested_fixes,
            "final_action": final_action,
        }

    def run(self, inp: AgentInput) -> AgentOutput:
        try:
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{
                    "role": "user",
                    "content": _CRITIC_PROMPT.format(content=inp.content[:2000]),
                }],
            )

            raw = response.content[0].text if response.content else ""
            cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            result = json.loads(match.group()) if match else {}

            strengths = result.get("strengths", [])
            weaknesses = result.get("weaknesses", [])
            suggestions = result.get("suggestions", [])
            verdict = result.get("verdict", "")
            score = result.get("score", "-")

            lines: list[str] = [f"🔍 *Critic 분석* (점수: {score}/10)\n"]
            if strengths:
                lines.append("✅ *강점*")
                lines.extend(f"• {s}" for s in strengths)
            if weaknesses:
                lines.append("\n⚠️ *약점*")
                lines.extend(f"• {w}" for w in weaknesses)
            if suggestions:
                lines.append("\n💡 *개선 제안*")
                lines.extend(f"• {s}" for s in suggestions)
            if verdict:
                lines.append(f"\n📌 *총평:* {verdict}")

            return AgentOutput(
                agent_name=self.name,
                success=True,
                result=result,
                reply_text="\n".join(lines),
            )

        except Exception as e:
            logger.error("CriticAgent 실패: %s", e)
            return AgentOutput(
                agent_name=self.name,
                success=False,
                result={},
                reply_text="❌ 검토 중 오류가 발생했습니다.",
            )
