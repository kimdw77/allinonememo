"""
utils/slug.py — 한글·영문 혼용 제목을 URL-safe slug로 변환
"""
from slugify import slugify


def to_slug(title: str, max_length: int = 80) -> str:
    """
    한글·영문 혼용 제목 → URL-safe slug (음성 변환).

    예: "AI 에이전트 전략" → "ai-eijenteu-jeonlyag"
    예: "2026년 4월 회의록" → "2026nyeon-4wol-hoeuilog"

    python-slugify 기본 transliterator(text-unidecode)가 한글을 음성 변환.
    의미 번역이 아닌 음성 변환이므로 영단어 그대로 남기는 것이 명확할 때는
    영문 키워드를 앞에 붙여서 전송하면 된다.
    """
    if not title:
        return "untitled"
    result = slugify(title, allow_unicode=False, separator="-", max_length=max_length)
    return result or "untitled"
