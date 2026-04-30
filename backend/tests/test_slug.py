"""
tests/test_slug.py — to_slug() 단위 테스트

실행 방법:
  cd backend
  pytest tests/test_slug.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.slug import to_slug


# ── 한글 보존 ─────────────────────────────────────────────────────────

def test_korean_preserved():
    """한글 단어가 음차 없이 그대로 보존되어야 함"""
    result = to_slug("복부지방감소를 위한 운동")
    assert result == "복부지방감소를-위한-운동"


def test_korean_channel_title():
    """채널명·접속사 포함 한글 제목"""
    result = to_slug("테토누님 채널에서 소개하는")
    assert result == "테토누님-채널에서-소개하는"


def test_korean_spaces_to_hyphen():
    """공백이 하이픈으로 변환"""
    result = to_slug("복부 지방 감소")
    assert "복부" in result
    assert "-" in result
    assert " " not in result


# ── 영문 회귀 ────────────────────────────────────────────────────────

def test_english_lowercased():
    """영문 제목은 소문자 변환"""
    assert to_slug("Hello World") == "hello-world"


def test_english_special_chars_removed():
    """영문 특수문자 제거"""
    assert to_slug("Hello, World!") == "hello-world"


def test_english_numbers_preserved():
    """숫자 보존"""
    result = to_slug("AI Agent 2026")
    assert "2026" in result
    assert "ai" in result


def test_mixed_korean_english():
    """한글+영문 혼용"""
    result = to_slug("AI 에이전트 전략")
    assert "ai" in result
    assert "에이전트" in result


# ── max_length 동작 ────────────────────────────────────────────────

def test_long_korean_truncated_at_word_boundary():
    """긴 한글 제목이 단어 경계에서 잘림"""
    long_title = "복부지방감소를 위한 전통적인 크런치 운동의 한계를 지적하는 내용"
    result = to_slug(long_title)
    assert len(result) <= 40
    # 단어 경계 보존: 하이픈으로 끝나지 않음
    assert not result.endswith("-")


def test_short_title_not_truncated():
    """짧은 제목은 max_length에 걸리지 않음"""
    result = to_slug("AI 전략")
    assert len(result) <= 40
    assert "ai" in result
    assert "전략" in result


def test_custom_max_length():
    """max_length 파라미터 직접 지정"""
    result = to_slug("가나다라마바사아자차카타파하 ABCDEFGHIJKLMNOPQRSTUVWXYZ", max_length=20)
    assert len(result) <= 20


# ── 엣지 케이스 ───────────────────────────────────────────────────────

def test_empty_string():
    assert to_slug("") == "untitled"


def test_only_special_chars():
    assert to_slug("!@#$%") == "untitled"


def test_whitespace_only():
    assert to_slug("   ") == "untitled"
