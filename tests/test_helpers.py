"""Unit tests for helper utilities in app/services/helpers.py."""
from __future__ import annotations

import pytest
from datetime import datetime

from app.services.helpers import (
    extract_number,
    is_latest_question,
    is_decree_question,
    parse_law_date,
    extract_date_score,
    is_followup_question,
    keyword_bonus,
    is_vague_question,
    check_confidence_threshold,
    build_prompt,
)


class TestExtractNumber:
    def test_extract_single_number(self):
        assert extract_number("ما هو القانون رقم 123؟") == "123"

    def test_extract_number_with_multiple_digits(self):
        assert extract_number("القانون 620") == "620"

    def test_extract_no_number(self):
        assert extract_number("ما هي القوانين الجديدة؟") is None

    def test_extract_first_number(self):
        assert extract_number("بين 100 و 200") == "100"


class TestIsLatestQuestion:
    def test_latest_arabic(self):
        assert is_latest_question("ما هو أحدث قانون؟") is True

    def test_newest_english(self):
        assert is_latest_question("What is the newest decree?") is True

    def test_recent(self):
        assert is_latest_question("give me recent tenders") is True

    def test_not_latest(self):
        assert is_latest_question("ما هو قانون الاستثمار؟") is False


class TestIsDecreeQuestion:
    def test_decree_arabic(self):
        assert is_decree_question("ما هو مرسوم رقم 50؟") is True

    def test_decree_english(self):
        assert is_decree_question("Tell me about the decree") is False

    def test_not_decree(self):
        assert is_decree_question("قانون الضرائب") is False


class TestParseLawDate:
    def test_parse_dd_mm_yyyy(self):
        result = parse_law_date("15/05/2024")
        assert result == datetime(2024, 5, 15)

    def test_parse_yyyy_mm_dd(self):
        result = parse_law_date("2024-05-15")
        assert result == datetime(2024, 5, 15)

    def test_parse_empty(self):
        assert parse_law_date(None) == datetime.min

    def test_parse_invalid(self):
        assert parse_law_date("invalid date") == datetime.min


class TestExtractDateScore:
    def test_recent_date_high_score(self):
        from datetime import timedelta
        recent = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        score = extract_date_score(recent)
        assert score > 0.8

    def test_old_date_low_score(self):
        score = extract_date_score("2010-01-01")
        assert score < 0.5

    def test_no_date(self):
        assert extract_date_score(None) == 0.0


class TestIsFollowupQuestion:
    def test_followup_arabic(self):
        assert is_followup_question("أخبرني أكثر عن هذا") is True

    def test_followup_english(self):
        assert is_followup_question("Tell me more") is True

    def test_not_followup(self):
        assert is_followup_question("قوانين الاستثمار") is False


class TestKeywordBonus:
    def test_all_keywords_match(self):
        content = "قانون الاستثمار ضريبة جديدة"
        bonus = keyword_bonus("قانون الاستثمار", content)
        assert bonus > 0

    def test_no_keywords_match(self):
        bonus = keyword_bonus("قوانين مغلقة", "قانون الاستثمار")
        assert bonus == 0.0

    def test_caps_at_one(self):
        content = " ".join(["word"] * 15)
        bonus = keyword_bonus(content, content)
        assert bonus == 1.0


class TestIsVagueQuestion:
    def test_vague_greeting(self):
        assert is_vague_question("مرحبا") is True

    def test_vague_hello(self):
        assert is_vague_question("hello") is True

    def test_specific_question(self):
        assert is_vague_question("ما هو قانون الاستثمار؟") is False

    def test_too_short_and_vague(self):
        assert is_vague_question("تفاصيل") is True


class TestCheckConfidenceThreshold:
    def test_above_threshold(self):
        sources = [{"percentage": 50}]
        assert check_confidence_threshold(sources) is True

    def test_below_threshold(self):
        sources = [{"percentage": 20}]
        assert check_confidence_threshold(sources, threshold=30.0) is False

    def test_empty_sources(self):
        assert check_confidence_threshold([]) is False


class TestBuildPrompt:
    def test_basic_prompt(self):
        sources = [{"excerpt": "Test content"}]
        prompt = build_prompt("What is X?", sources)
        assert "What is X?" in prompt
        assert "SOURCE 1" in prompt

    def test_with_history(self):
        sources = [{"excerpt": "Content"}]
        history = [{"role": "user", "content": "Previous Q"}]
        prompt = build_prompt("Current Q?", sources, history)
        assert "USER: Previous Q" in prompt
        assert "QUESTION:" in prompt