"""
utils/trace_id.py — 파이프라인 추적 ID 유틸리티

newTraceId()        : 새 UUID v4 생성
getCurrentTraceId() : 현재 컨텍스트의 trace_id 반환 (ContextVar 기반)
withTrace()         : trace_id를 컨텍스트에 주입하는 contextmanager

파이썬 contextvars.ContextVar는 asyncio·threading 양쪽에서 안전하게 동작한다.
AsyncLocalStorage 폴백이 필요한 환경이라면 trace_id를 함수 인자로 명시적 전달해도 무방.
"""
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

_trace_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    """새 UUID v4 trace_id 생성"""
    return str(uuid.uuid4())


def get_current_trace_id() -> str | None:
    """현재 컨텍스트의 trace_id 반환. 설정되지 않은 경우 None."""
    return _trace_var.get()


def set_trace_id(trace_id: str) -> None:
    """현재 컨텍스트의 trace_id를 직접 설정 (컨텍스트 매니저 없이 사용할 때)."""
    _trace_var.set(trace_id)


@contextmanager
def with_trace(trace_id: str) -> Generator[None, None, None]:
    """
    trace_id를 컨텍스트에 주입하고 블록 종료 시 원래 값으로 복원.
    중첩 호출이 안전하다.

    사용 예:
        with with_trace(new_trace_id()):
            ...  # get_current_trace_id()가 주입된 값 반환
    """
    token = _trace_var.set(trace_id)
    try:
        yield
    finally:
        _trace_var.reset(token)
