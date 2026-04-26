"""
agents/task_extractor.py — 텍스트에서 실행 가능한 태스크 추출·저장
"""
import json
import logging
import re
from typing import Optional

import anthropic

from agents.base import AgentInput, AgentOutput, BaseAgent
from config import settings

logger = logging.getLogger(__name__)

_TASK_PROMPT = """다음 내용에서 실행 가능한 행동 항목(Task)을 추출하라. JSON 배열로만 응답.

내용: {content}

각 태스크 형식:
{{"title":"동사로 시작하는 태스크 제목","description":"상세 설명","priority":"high|medium|low","project":"관련 프로젝트명(없으면 빈 문자열)","due_hint":"기한 힌트(없으면 빈 문자열)"}}

추출 기준:
- 명확한 행동이 있는 항목만 추출
- "해야 함", "확인", "보내기", "작성", "예약", "준비", "알아보기", "검토" 등 포함 시 후보로 판단
- 단순 정보·감상은 제외

태스크가 없으면 빈 배열 [] 반환.
JSON 배열만 반환. 설명 없음."""


def _call_extract_api(content: str) -> list[dict]:
    """Claude API로 태스크 추출. 파싱 실패 시 빈 리스트."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": _TASK_PROMPT.format(content=content[:1500]),
        }],
    )
    raw = response.content[0].text if response.content else "[]"
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    array_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    return json.loads(array_match.group()) if array_match else []


class TaskExtractorAgent(BaseAgent):
    name = "task_extractor"

    def analyze(self, inp: AgentInput) -> dict:
        """
        태스크 추출만 수행. DB 저장 없음.
        파이프라인(RouterAgent)에서 SaveExecutor 호출 전 단계로 사용.
        반환: {has_tasks: bool, tasks: list[dict]}
        """
        try:
            tasks_data = _call_extract_api(inp.content)
            return {
                "has_tasks": len(tasks_data) > 0,
                "tasks": tasks_data,
            }
        except Exception as e:
            logger.error("TaskExtractorAgent.analyze 실패: %s", e)
            return {"has_tasks": False, "tasks": []}

    def run(self, inp: AgentInput) -> AgentOutput:
        """직접 명령어(/task) 전용: 추출 후 즉시 DB 저장."""
        try:
            from db.tasks import insert_tasks

            tasks_data = _call_extract_api(inp.content)

            if not tasks_data:
                return AgentOutput(
                    agent_name=self.name,
                    success=True,
                    result={"tasks": []},
                    reply_text=None,
                )

            note_id: Optional[str] = inp.metadata.get("note_id") if inp.metadata else None
            saved = insert_tasks(tasks_data, source=inp.source, note_id=note_id)

            _priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            lines = [f"📋 *태스크 {len(saved)}개 추출*"]
            for t in saved:
                icon = _priority_icon.get(t.get("priority", "medium"), "🟡")
                lines.append(f"{icon} {t['title']}")

            return AgentOutput(
                agent_name=self.name,
                success=True,
                result={"tasks": saved},
                reply_text="\n".join(lines),
            )

        except Exception as e:
            logger.error("TaskExtractorAgent 실패: %s", e)
            return AgentOutput(
                agent_name=self.name,
                success=False,
                result={},
                reply_text=None,
            )
