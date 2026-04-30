"""
tests/test_github_sync.py — Phase 9-1 단위 테스트
GitHub API·DB 없이 로직만 검증 (LLM·네트워크 불필요)

실행 방법:
  cd backend
  pytest tests/test_github_sync.py -v
"""
import os
import sys
from unittest.mock import MagicMock, patch

# backend 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# config.settings 모킹 (실제 .env 없이도 동작)
_mock_settings = MagicMock()
_mock_settings.GITHUB_TOKEN = "ghp_test"
_mock_settings.GITHUB_REPO = "kimdw77/my-kms"
_mock_settings.GITHUB_BRANCH = "main"
_mock_settings.WIKI_DEFAULT_DOMAIN = "personal"
_mock_settings.SYNC_LAG_ALERT_SECONDS = 30
_mock_settings.SYNC_FAIL_RATE_ALERT_PERCENT = 5.0
sys.modules.setdefault("config", MagicMock(settings=_mock_settings, KST=__import__("datetime").timezone(__import__("datetime").timedelta(hours=9))))

from utils.slug import to_slug
from services.github_sync import determine_domain, validate_routing, make_filepath, render_note_markdown


# ── 픽스처 ────────────────────────────────────────────────────────────

def _note(
    title: str = "테스트 노트",
    keywords: list[str] | None = None,
    category: str = "기타",
    summary: str = "요약 내용",
    raw_content: str = "본문 내용",
    created_at: str = "2026-04-30T09:00:00+09:00",
    note_id: str = "test-uuid-1234",
    trace_id: str = "trace-abcd",
) -> dict:
    return {
        "id": note_id,
        "title": title,
        "keywords": keywords or [],
        "category": category,
        "summary": summary,
        "raw_content": raw_content,
        "created_at": created_at,
        "updated_at": created_at,
        "trace_id": trace_id,
        "source": None,
        "file_url": None,
        "related_links": None,
    }


# ── slug 변환 테스트 ──────────────────────────────────────────────────

def test_slug_english_only():
    assert to_slug("Hello World") == "hello-world"

def test_slug_korean_transliteration():
    result = to_slug("AI 전략 회의")
    assert isinstance(result, str)
    assert len(result) > 0
    assert " " not in result
    assert result == result.lower()

def test_slug_mixed():
    result = to_slug("2026년 4월 AI 에이전트")
    assert "-" in result
    assert " " not in result

def test_slug_empty_returns_untitled():
    assert to_slug("") == "untitled"
    assert to_slug("   ") == "untitled"

def test_slug_special_chars_stripped():
    result = to_slug("hello/world:test?foo")
    assert "/" not in result
    assert ":" not in result
    assert "?" not in result

def test_slug_max_length():
    long_title = "가" * 200
    result = to_slug(long_title, max_length=80)
    assert len(result) <= 80


# ── 폴더 결정 로직 테스트 ─────────────────────────────────────────────

def test_determine_domain_kita_keyword():
    note = _note(keywords=["kita", "무역"])
    assert determine_domain(note) == "kita"

def test_determine_domain_hoewonsa_keyword():
    note = _note(keywords=["회원사", "정책"])
    assert determine_domain(note) == "kita"

def test_determine_domain_personal_keyword():
    note = _note(keywords=["personal", "일상"])
    assert determine_domain(note) == "personal"

def test_determine_domain_gae_in_keyword():
    note = _note(keywords=["개인", "메모"])
    assert determine_domain(note) == "personal"

def test_determine_domain_kita_category():
    note = _note(category="무역정책")
    assert determine_domain(note) == "kita"

def test_determine_domain_kita_category_suculip():
    note = _note(category="수출입동향")
    assert determine_domain(note) == "kita"

def test_determine_domain_default_personal():
    note = _note(keywords=[], category="기타")
    assert determine_domain(note) == "personal"

def test_determine_domain_keyword_overrides_category():
    """명시적 태그가 카테고리보다 우선."""
    note = _note(keywords=["personal"], category="무역정책")
    assert determine_domain(note) == "personal"


# ── 오라우팅 검증 테스트 (HARNESS 3-3) ───────────────────────────────

def test_validate_routing_normal_personal():
    note = _note(keywords=["일상"], raw_content="오늘 점심 먹었다")
    result = validate_routing(note, "personal")
    assert result["blocked"] is False

def test_validate_routing_kita_to_kita_allowed():
    note = _note(keywords=["kita-internal", "기밀"], raw_content="내부 보고서")
    result = validate_routing(note, "kita")
    assert result["blocked"] is False

def test_validate_routing_kita_internal_keyword_to_personal_blocked():
    """kita-internal 키워드가 personal로 가려 하면 차단."""
    note = _note(keywords=["kita-internal"])
    result = validate_routing(note, "personal")
    assert result["blocked"] is True
    assert "kita-internal" in result["detected_keywords"]
    assert "personal" in result["reason"]

def test_validate_routing_gibil_keyword_blocked():
    note = _note(keywords=["기밀", "보고서"])
    result = validate_routing(note, "personal")
    assert result["blocked"] is True

def test_validate_routing_content_scan():
    """키워드에는 없지만 본문에 kita-internal 포함 시 차단."""
    note = _note(keywords=[], raw_content="이 문서는 대외비 자료입니다")
    result = validate_routing(note, "personal")
    assert result["blocked"] is True

def test_validate_routing_no_false_positive():
    """일반 내용에 오탐 없음."""
    note = _note(keywords=["기술", "AI"], raw_content="머신러닝 최신 동향 분석")
    result = validate_routing(note, "personal")
    assert result["blocked"] is False


# ── 파일 경로 생성 테스트 ─────────────────────────────────────────────

def test_make_filepath_personal():
    note = _note(title="AI 전략", created_at="2026-04-30T09:00:00+09:00")
    path = make_filepath(note, "personal")
    assert path.startswith("personal/notes/2026-04-30-")
    assert path.endswith(".md")

def test_make_filepath_kita():
    note = _note(title="무역 정책", created_at="2026-04-30T09:00:00+09:00")
    path = make_filepath(note, "kita")
    assert path.startswith("kita/notes/2026-04-30-")
    assert path.endswith(".md")

def test_make_filepath_same_note_same_path():
    """동일 노트를 두 번 호출해도 경로가 동일 (중복 생성 방지)."""
    note = _note(title="동일 제목 노트", created_at="2026-04-30T10:00:00+09:00")
    path1 = make_filepath(note, "personal")
    path2 = make_filepath(note, "personal")
    assert path1 == path2

def test_make_filepath_no_spaces():
    note = _note(title="공백 있는 제목 노트")
    path = make_filepath(note, "personal")
    assert " " not in path


# ── 마크다운 렌더링 테스트 ────────────────────────────────────────────

def test_render_note_markdown_frontmatter():
    note = _note(title="테스트 노트", keywords=["AI", "전략"], category="기술")
    md = render_note_markdown(note, "personal", trace_id="trace-test-1234")
    assert "title:" in md
    assert "domain: personal" in md
    assert "confidentiality: personal" in md
    assert "type: note" in md

def test_render_note_markdown_kita_confidentiality():
    note = _note(title="회원사 보고서", category="무역정책")
    md = render_note_markdown(note, "kita", trace_id="trace-kita-5678")
    assert "domain: kita" in md
    assert "confidentiality: kita-internal" in md

def test_render_note_markdown_body():
    note = _note(summary="요약 텍스트", raw_content="본문 텍스트")
    md = render_note_markdown(note, "personal")
    assert "요약 텍스트" in md
    assert "본문 텍스트" in md

def test_render_note_markdown_related_links():
    note = _note()
    note["related_links"] = {
        "articles": [{"title": "관련 기사", "url": "https://example.com"}]
    }
    md = render_note_markdown(note, "personal")
    assert "관련 기사" in md
    assert "https://example.com" in md

def test_render_note_markdown_no_crash_on_none_fields():
    """선택 필드가 None이어도 렌더링 오류 없음."""
    note = {
        "id": "test-id",
        "title": None,
        "keywords": None,
        "category": None,
        "summary": None,
        "raw_content": None,
        "created_at": None,
        "updated_at": None,
        "trace_id": None,
        "source": None,
        "file_url": None,
        "related_links": None,
    }
    md = render_note_markdown(note, "personal")
    assert isinstance(md, str)
    assert len(md) > 0


# ── 전체 실행 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
