"""
services/scheduler_instance.py — APScheduler 싱글톤
main.py 에서 set_scheduler()로 등록, 다른 모듈에서 get_scheduler()로 참조
"""
from typing import Optional

_scheduler = None


def get_scheduler():
    return _scheduler


def set_scheduler(s) -> None:
    global _scheduler
    _scheduler = s
