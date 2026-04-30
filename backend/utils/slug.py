"""
utils/slug.py — 한글·영문 혼용 제목을 파일명 안전 slug로 변환
"""
from slugify import slugify


def to_slug(title: str, max_length: int = 40) -> str:
    """
    한글·영문 혼용 제목 → 파일명 안전 slug (한글 보존).

    예: "복부지방감소를 위한 운동" → "복부지방감소를-위한-운동"
    예: "AI 에이전트 전략" → "ai-에이전트-전략"
    예: "2026년 4월 회의록" → "2026년-4월-회의록"
    """
    if not title:
        return "untitled"
    result = slugify(title, allow_unicode=True, separator="-",
                     max_length=max_length, word_boundary=True)
    return result or "untitled"
