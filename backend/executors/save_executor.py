"""
executors/save_executor.py — 저장 전담 실행기
메모 저장은 필수(실패 시 None 반환). 태스크·agent_run 저장은 실패해도 전체 요청 유지.
모든 함수에 trace_id를 받아 관련 레코드를 동일 trace로 묶는다.
"""
import logging
from typing import Optional

from agents.base import AgentInput

logger = logging.getLogger(__name__)


class SaveExecutor:

    def save_memo(
        self,
        memo_result: dict,
        inp: AgentInput,
        trace_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        메모 저장. 실패 시 None 반환.
        memo_result: MemoAgent.analyze() 반환값
        trace_id: 동일 파이프라인 실행을 묶는 추적 ID
        """
        try:
            from db.notes import insert_note
            return insert_note(
                source=inp.source,
                raw_content=memo_result.get("raw_text", inp.content),
                summary=memo_result.get("summary", ""),
                highlights=memo_result.get("highlights", []),
                keywords=memo_result.get("keywords", []),
                category=memo_result.get("category", "기타"),
                content_type=memo_result.get("content_type", "other"),
                url=memo_result.get("url"),
                metadata={
                    **(inp.metadata or {}),
                    "importance": memo_result.get("importance", "medium"),
                },
                trace_id=trace_id,
                file_url=(inp.metadata or {}).get("file_url"),
            )
        except Exception as e:
            logger.error("save_memo 실패: %s", e)
            return None

    def save_tasks(
        self,
        note_id: Optional[str],
        tasks: list[dict],
        source: str = "",
        trace_id: Optional[str] = None,
    ) -> list[dict]:
        """태스크 저장. 실패해도 예외를 전파하지 않음."""
        try:
            from db.tasks import insert_tasks
            return insert_tasks(tasks, source=source, note_id=note_id, trace_id=trace_id)
        except Exception as e:
            logger.error("save_tasks 실패 (무시): %s", e)
            return []

    def save_agent_run(
        self,
        input_text: str,
        intent: str,
        confidence: float,
        final_action: str,
        needs_user_confirmation: bool = False,
        issues: Optional[list[str]] = None,
        note_id: Optional[str] = None,
        has_tasks: bool = False,
        task_count: int = 0,
        source: str = "",
        trace_id: Optional[str] = None,
    ) -> None:
        """agent_runs 로깅. 실패해도 예외를 전파하지 않음."""
        logger.info(
            "agent_run | trace=%s intent=%s conf=%.2f action=%s confirm=%s tasks=%d",
            (trace_id or "")[:8], intent, confidence,
            final_action, needs_user_confirmation, task_count,
        )
        try:
            from db.agent_runs import insert_agent_run
            insert_agent_run(
                input_text=input_text,
                intent=intent,
                confidence=confidence,
                final_action=final_action,
                needs_user_confirmation=needs_user_confirmation,
                issues=issues,
                note_id=note_id,
                has_tasks=has_tasks,
                task_count=task_count,
                source=source,
                trace_id=trace_id,
            )
        except Exception as e:
            logger.error("save_agent_run 실패 (무시): %s", e)
