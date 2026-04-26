"""
agents/weekly_report.py — 주간 노트·태스크 집계 보고서 생성
기존 weekly_insight.py를 에이전트로 확장 (태스크 통계 포함)
"""
import logging
from datetime import datetime, timedelta, timezone

import anthropic

from agents.base import AgentInput, AgentOutput, BaseAgent
from config import settings

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_REPORT_PROMPT = """지난 한 주 기록을 분석하여 한국어로 주간 보고서를 작성하라.

## 노트 ({note_count}개):
{notes_text}

## 태스크 ({task_count}개 중 완료 {done_count}개):
{tasks_text}

## 작성 규칙:
- 한국어, 텔레그램 친화적 텍스트
- 500자 이내로 간결하게
- 아래 구조 준수

🗓 주간 보고서 ({date_range})

📊 이번 주 요약
• 노트: {note_count}개 | 태스크: {task_count}개 (완료: {done_count}개)
• 주요 카테고리: (상위 3개)
• 핵심 키워드: (5개)

💡 핵심 인사이트
(2-3문장으로 주요 흐름·패턴)

✅ 완료된 주요 태스크
(완료 태스크 요약, 없으면 생략)

📌 다음 주 집중 포인트
(미완료 태스크·노트 기반 추천 1-2가지)

다음 주도 꾸준히 기록해보세요! 💪"""


class WeeklyReportAgent(BaseAgent):
    name = "weekly_report"

    def run(self, inp: AgentInput) -> AgentOutput:
        try:
            from db.notes import get_notes
            from db.tasks import get_tasks_this_week

            now = datetime.now(KST)
            week_ago = now - timedelta(days=7)

            all_notes = get_notes(limit=200)
            recent_notes = [
                n for n in all_notes
                if _parse_kst(n.get("created_at", ""), KST) >= week_ago
            ]

            tasks = get_tasks_this_week()
            done_tasks = [t for t in tasks if t.get("status") == "done"]

            if not recent_notes and not tasks:
                report = "📭 이번 주에는 저장된 기록이 없습니다. 이번 주도 활발히 기록해보세요!"
                return AgentOutput(
                    agent_name=self.name,
                    success=True,
                    result={"report": report, "note_count": 0, "task_count": 0},
                    reply_text=report,
                )

            notes_text = _build_notes_text(recent_notes)
            tasks_text = _build_tasks_text(tasks)
            date_range = f"{week_ago.strftime('%m/%d')}~{now.strftime('%m/%d')}"

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                messages=[{
                    "role": "user",
                    "content": _REPORT_PROMPT.format(
                        note_count=len(recent_notes),
                        task_count=len(tasks),
                        done_count=len(done_tasks),
                        notes_text=notes_text[:2500],
                        tasks_text=tasks_text[:500],
                        date_range=date_range,
                    ),
                }],
            )

            report = response.content[0].text.strip() if response.content else ""
            if not report:
                report = "📭 주간 보고서를 생성할 수 없습니다."

            return AgentOutput(
                agent_name=self.name,
                success=True,
                result={
                    "report": report,
                    "note_count": len(recent_notes),
                    "task_count": len(tasks),
                    "done_count": len(done_tasks),
                },
                reply_text=report,
            )

        except Exception as e:
            logger.error("WeeklyReportAgent 실패: %s", e)
            return AgentOutput(
                agent_name=self.name,
                success=False,
                result={},
                reply_text="❌ 주간 보고서 생성 실패",
            )


def _parse_kst(created_at: str, tz: timezone) -> datetime:
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(tz)
    except Exception:
        return datetime.min.replace(tzinfo=tz)


def _build_notes_text(notes: list[dict]) -> str:
    lines: list[str] = []
    for n in notes:
        summary = (n.get("summary") or "")[:80]
        cat = n.get("category", "기타")
        kw = ", ".join((n.get("keywords") or [])[:4])
        lines.append(f"[{cat}] {summary} ({kw})")
    return "\n".join(lines)


def _build_tasks_text(tasks: list[dict]) -> str:
    _icon = {"done": "✅", "in_progress": "🔄", "todo": "⬜"}
    lines: list[str] = []
    for t in tasks:
        icon = _icon.get(t.get("status", "todo"), "⬜")
        lines.append(f"{icon} {t['title']} [{t.get('priority', 'medium')}]")
    return "\n".join(lines)


async def send_weekly_report() -> None:
    """스케줄러용: 주간 보고서 생성 후 텔레그램 전송"""
    try:
        import httpx
        from config import settings as s

        out = WeeklyReportAgent().run(AgentInput(content="", source="scheduler"))
        if not out.reply_text:
            return

        url = f"https://api.telegram.org/bot{s.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": s.TELEGRAM_ALLOWED_USER_ID,
                "text": out.reply_text,
            })
        logger.info("주간 보고서 전송 완료 (노트 %d개, 태스크 %d개)",
                    out.result.get("note_count", 0), out.result.get("task_count", 0))
    except Exception as e:
        logger.error("주간 보고서 전송 실패: %s", e)
