"""
agents/pipeline.py — 에이전트 파이프라인 오케스트레이터 (Critic 게이트키퍼 포함)

runPipeline(inp, trace_id) 가 단일 진입점.
RouterAgent 는 의도 분류만 담당하고, 게이트 결정·저장은 이 모듈이 처리한다.

파이프라인 흐름:
  ① insert_thought (status=pending)
  ② RouterAgent.classify_intent()
     → search/question/command: 즉시 "준비 중" 반환
  ③ MemoAgent.analyze()
  ④ TaskExtractorAgent.analyze()
  ⑤ CriticAgent.review()  ← 게이트키퍼 결정
     → "reject"          : thoughts(manual_review) → 거부 메시지
     → "ask_user"        : thoughts(pending_user_confirm) → 확인 요청 메시지
     → "save"            : SaveExecutor.save_memo()
     → "save_with_tasks" : save_memo() + save_tasks()
  ⑥ SaveExecutor.save_agent_run()
  ⑦ update_thought (status=processed)
"""
import asyncio
import logging
from typing import Optional

from agents.base import AgentInput, AgentOutput
from utils.trace_id import set_trace_id

logger = logging.getLogger(__name__)

# 즉시 "준비 중" 응답을 반환하는 의도
_UNSUPPORTED_INTENTS = {"command"}
_UNSUPPORTED_LABELS = {
    "command": "명령 실행",
}


class AgentPipeline:
    def run(self, inp: AgentInput, trace_id: str) -> AgentOutput:
        from agents.router import RouterAgent
        from agents.memo import MemoAgent
        from agents.task_extractor import TaskExtractorAgent
        from agents.critic import CriticAgent
        from executors.save_executor import SaveExecutor
        from db.thoughts import insert_thought, update_thought_status

        set_trace_id(trace_id)

        # ── ① 입력 원본 기록 ───────────────────────────────────────
        thought = insert_thought(
            raw_input=inp.content,
            trace_id=trace_id,
            source=inp.source,
            status="pending",
        )
        thought_id: Optional[str] = thought["id"] if thought else None

        # ── ② 의도 분류 ───────────────────────────────────────────
        intent_data = RouterAgent().classify_intent(inp.content)
        intent = intent_data.get("intent", "memo")
        confidence = float(intent_data.get("confidence", 0.5))
        logger.info(
            "Pipeline | trace=%s intent=%s conf=%.2f",
            trace_id[:8], intent, confidence,
        )

        # 미지원 의도 → 즉시 반환
        if intent in _UNSUPPORTED_INTENTS:
            label = _UNSUPPORTED_LABELS.get(intent, intent)
            return AgentOutput(
                agent_name="pipeline",
                success=True,
                result={"intent": intent, "trace_id": trace_id},
                reply_text=(
                    f"🚧 *{label}* 기능은 아직 지원 준비 중입니다.\n"
                    f"🔎 trace: {trace_id[:8]}"
                ),
            )

        # ── 검색 의도 — 노트 검색 후 즉시 반환 ──────────────────────
        if intent == "search":
            from db.thoughts import update_thought_status
            reply = _handle_search_intent(inp.content)
            update_thought_status(thought_id, "processed")
            return AgentOutput(
                agent_name="pipeline",
                success=True,
                result={"intent": "search", "trace_id": trace_id},
                reply_text=reply,
            )

        # ── 질문 의도 — RAG 기반 답변 후 즉시 반환 ─────────────────
        if intent == "question":
            from db.thoughts import update_thought_status
            reply = _handle_question_intent(inp.content)
            update_thought_status(thought_id, "processed")
            return AgentOutput(
                agent_name="pipeline",
                success=True,
                result={"intent": "question", "trace_id": trace_id},
                reply_text=reply,
            )

        # ── ③ Memo 분석 ────────────────────────────────────────────
        memo_result = MemoAgent().analyze(inp)

        # ── ④ Task 분석 ────────────────────────────────────────────
        task_result = TaskExtractorAgent().analyze(inp)

        # ── ⑤ Critic 게이트 결정 ──────────────────────────────────
        critic_result = CriticAgent().review(inp, memo_result, task_result, intent_data)
        final_action: str = critic_result.get("final_action", "save")
        needs_confirmation: bool = critic_result.get("needs_user_confirmation", False)
        issues: list[str] = critic_result.get("issues", [])
        suggested_fixes: list[str] = critic_result.get("suggested_fixes", [])

        # ── ⑥ 게이트 분기 ─────────────────────────────────────────

        if final_action == "reject":
            update_thought_status(thought_id, "manual_review", issues, suggested_fixes)
            issue_text = issues[0] if issues else "처리할 수 없는 입력입니다"
            return AgentOutput(
                agent_name="pipeline",
                success=True,
                result={"intent": intent, "final_action": "reject", "trace_id": trace_id},
                reply_text=(
                    f"❌ 자동 처리 불가: {issue_text}\n"
                    f"수동 검토로 표시했습니다.\n"
                    f"🔎 trace: {trace_id[:8]}"
                ),
            )

        if final_action == "ask_user":
            update_thought_status(thought_id, "pending_user_confirm", issues, suggested_fixes)
            issue_text = issues[0] if issues else "확인이 필요합니다"
            # TODO: /yes /no 명령 핸들러 (다음 단계에서 구현)
            return AgentOutput(
                agent_name="pipeline",
                success=True,
                result={
                    "intent": intent,
                    "final_action": "ask_user",
                    "thought_id": thought_id,
                    "trace_id": trace_id,
                },
                reply_text=(
                    f"⚠️ 확인 필요: {issue_text}\n"
                    f"저장하시겠습니까? /yes /no\n"
                    f"🔎 trace: {trace_id[:8]}"
                ),
            )

        # ── ⑦ 저장 (save / save_with_tasks) ──────────────────────
        executor = SaveExecutor()

        note = executor.save_memo(memo_result, inp, trace_id)
        note_id: Optional[str] = note["id"] if note else None

        # ── [Phase 9-1] GitHub 동기화 fire-and-forget ─────────────────
        if note:
            _schedule_sync(note, trace_id)
        # ──────────────────────────────────────────────────────────────

        saved_tasks: list[dict] = []
        if final_action == "save_with_tasks" and task_result.get("has_tasks"):
            saved_tasks = executor.save_tasks(
                note_id, task_result.get("tasks", []), inp.source, trace_id
            )

        executor.save_agent_run(
            input_text=inp.content,
            intent=intent,
            confidence=confidence,
            final_action=final_action,
            needs_user_confirmation=needs_confirmation,
            issues=issues,
            note_id=note_id,
            has_tasks=task_result.get("has_tasks", False),
            task_count=len(saved_tasks),
            source=inp.source,
            trace_id=trace_id,
        )

        update_thought_status(thought_id, "processed")

        # ── ⑧ Google Calendar 자동 감지 ──────────────────────────
        calendar_line = ""
        try:
            from services.schedule_detector import detect_schedule
            from services.calendar import create_event
            schedule = detect_schedule(inp.content)
            if schedule and schedule.get("start"):
                event_url = create_event(
                    title=schedule["title"] or title,
                    start=schedule["start"],
                    end=schedule["end"],
                    location=schedule.get("location", ""),
                    description=schedule.get("description", ""),
                )
                if event_url:
                    calendar_line = f"\n📅 캘린더 등록: {schedule['title'] or title}"
                    logger.info("캘린더 자동 등록 완료: %s", event_url)
        except Exception as cal_err:
            logger.warning("캘린더 자동 감지 건너뜀: %s", cal_err)

        # ── ⑨ 응답 메시지 ─────────────────────────────────────────
        title = (memo_result.get("title") or memo_result.get("summary") or inp.content)[:50]

        if saved_tasks:
            reply = f"✅ 저장 완료: {title} (할 일 {len(saved_tasks)}건 추가)"
        else:
            reply = f"✅ 저장 완료: {title}"

        if needs_confirmation and issues:
            reply += f"\n⚠️ {' | '.join(issues[:2])}"

        reply += calendar_line
        reply += f"\n🔎 trace: {trace_id[:8]}"

        return AgentOutput(
            agent_name="pipeline",
            success=note is not None,
            result={
                "intent": intent,
                "final_action": final_action,
                "note_id": note_id,
                "trace_id": trace_id,
                "has_tasks": task_result.get("has_tasks", False),
            },
            reply_text=reply,
        )


def _schedule_sync(note: dict, trace_id: str) -> None:
    """
    GitHub 동기화를 fire-and-forget으로 예약.
    (b) pipeline 응답을 막지 않음 — create_task 결과를 await 안 함
    (c) done_callback 으로 예외 로깅 보장 — silently 사라지지 않음
    (d) trace_id 인자 명시적 전달 (ContextVar 자동 전파 이중 보장)
    """
    try:
        from workers.sync_worker import enqueue_sync
        loop = asyncio.get_running_loop()
        task = loop.create_task(enqueue_sync(note, trace_id))
        task.add_done_callback(_log_sync_task_result)
    except RuntimeError:
        # 이벤트 루프 없음 (테스트 환경, RouterAgent.run() 동기 래퍼 경유 등)
        logger.warning("sync_worker: 이벤트 루프 없음, 동기화 건너뜀 trace=%s", trace_id[:8])
    except Exception as e:
        logger.error("sync_worker 예약 실패: %s trace=%s", e, trace_id[:8])


def _log_sync_task_result(task: asyncio.Task) -> None:
    """create_task 완료 콜백 — 예외가 silently 사라지지 않도록 보장."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("sync_task 비동기 예외: %s", exc, exc_info=exc)


def _handle_search_intent(query: str) -> str:
    """노트 벡터 검색 → 텔레그램 응답 텍스트 반환."""
    try:
        results: list[dict] = []
        try:
            from services.embedder import embed_query
            from db.notes import vector_search_notes
            vector = embed_query(query)
            results = vector_search_notes(vector, limit=5)
        except Exception:
            from db.notes import get_notes
            results = get_notes(query=query, limit=5)

        if not results:
            return f"🔍 *{query[:30]}* 검색 결과가 없습니다."

        lines = [f"🔍 *{query[:30]}* 검색 결과 ({len(results)}건)\n"]
        for n in results:
            summary = (n.get("summary") or n.get("raw_content") or "")[:70]
            cat = n.get("category", "기타")
            lines.append(f"• [{cat}] {summary}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("search_intent 처리 실패: %s", e)
        return "🔍 검색 중 오류가 발생했습니다."


def _handle_question_intent(question: str) -> str:
    """저장된 노트를 컨텍스트로 Claude에게 질문 → 텔레그램 응답 텍스트 반환."""
    try:
        context_notes: list[dict] = []
        try:
            from services.embedder import embed_query
            from db.notes import vector_search_notes
            vector = embed_query(question)
            context_notes = vector_search_notes(vector, limit=5)
        except Exception:
            from db.notes import get_notes
            context_notes = get_notes(query=question, limit=5)

        if not context_notes:
            return "🤔 관련 저장 내용이 없어 답변하기 어렵습니다."

        context = "\n\n".join(
            f"[{n.get('category', '기타')}] {n.get('summary', n.get('raw_content', ''))[:300]}"
            for n in context_notes
        )

        import anthropic
        from config import settings
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    f"다음 메모를 기반으로 질문에 간결하게 답하라. "
                    f"메모에 없는 내용은 '저장된 정보에 없습니다'라고 답하라.\n\n"
                    f"메모:\n{context}\n\n질문: {question}"
                ),
            }],
        )
        answer = resp.content[0].text if resp.content else "답변을 생성할 수 없습니다."
        return f"🤔 *질문 답변*\n\n{answer}"
    except Exception as e:
        logger.error("question_intent 처리 실패: %s", e)
        return "🤔 답변 생성 중 오류가 발생했습니다."
