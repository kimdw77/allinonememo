"""
agents/router.py — 의도 분류 전담 에이전트 (단일 책임)

classify_intent(content) 가 이 클래스의 핵심 공개 API다.
파이프라인 오케스트레이션(게이트 결정·저장)은 agents/pipeline.py 가 담당한다.

run() 은 하위 호환성을 위해 남겨두되 내부적으로 AgentPipeline 에 위임한다.
"""
import json
import logging
import re

import anthropic

from agents.base import AgentInput, AgentOutput, BaseAgent
from config import settings

logger = logging.getLogger(__name__)

_ROUTE_PROMPT = """다음 텍스트의 의도를 분류하라. JSON으로만 응답. 설명 없이 JSON만.

텍스트: {content}

의도 분류:
- "memo"     : 일반 메모, 링크, 아이디어, 정보 저장 (기본값)
- "task"     : 해야 할 일, 계획, 실행 항목이 명확히 포함된 내용
- "project"  : 아이디어 + 할 일 + 계획이 복합적으로 포함된 내용
- "search"   : 검색 요청 ("찾아줘", "검색", "알려줘" 등)
- "question" : 질문·답변 요청 ("왜", "어떻게", "뭐야" 등)
- "command"  : 시스템 명령 ("삭제해줘", "수정해줘" 등)
- "unknown"  : 위 어디에도 해당 없음

{{"intent":"memo|task|project|search|question|command|unknown","confidence":0.0-1.0,"reason":"한 줄 이유"}}"""

_UNSUPPORTED_INTENTS = {"search", "question", "command", "unknown"}
_UNSUPPORTED_LABELS = {
    "search": "검색",
    "question": "질문 답변",
    "command": "명령 실행",
    "unknown": "해당 기능",
}


class RouterAgent(BaseAgent):
    name = "router"

    def classify_intent(self, content: str) -> dict:
        """Haiku로 빠르게 의도 분류. 실패 시 기본값 memo."""
        try:
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": _ROUTE_PROMPT.format(content=content[:500]),
                }],
            )
            raw = response.content[0].text if response.content else ""
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.error("Router 의도 분류 실패: %s", e)
        return {"intent": "memo", "confidence": 0.5, "reason": "분류 실패, 기본값"}

    def run(self, inp: AgentInput) -> AgentOutput:
        """
        하위 호환용. 내부적으로 AgentPipeline 에 위임한다.
        직접 파이프라인을 제어하려면 AgentPipeline().run(inp, trace_id) 를 사용할 것.
        """
        from agents.pipeline import AgentPipeline
        from utils.trace_id import new_trace_id
        return AgentPipeline().run(inp, trace_id=new_trace_id())
