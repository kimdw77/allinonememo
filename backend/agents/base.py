"""
agents/base.py — 에이전트 공통 인터페이스
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentInput:
    content: str
    source: str = "telegram"
    chat_id: Optional[int] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentOutput:
    agent_name: str
    success: bool
    result: dict = field(default_factory=dict)
    reply_text: Optional[str] = None


class BaseAgent:
    name: str = "base"

    def run(self, inp: AgentInput) -> AgentOutput:
        raise NotImplementedError
