"""Tests for Phase 1: Input Analyzer."""

import pytest

from agents.phase1.context_validator import ContextValidator
from agents.phase1.input_analyzer import InputAnalyzer
from agents.phase1.reference_resolver import ReferenceResolver
from models.input_models import (
    AnalyzedInput,
    ClarificationRequest,
    InputIntent,
    ReferenceType,
)


class TestInputAnalyzer:
    def setup_method(self):
        self.analyzer = InputAnalyzer()

    def test_parse_input_generate_intent(self):
        result = self.analyzer._parse_input("generate a mascot for India Post")
        assert result.intent == InputIntent.GENERATE_IMAGE
        assert "mascot" in result.subject.lower()

    def test_parse_input_edit_intent(self):
        result = self.analyzer._parse_input("edit the logo to make it brighter")
        assert result.intent == InputIntent.EDIT_IMAGE

    def test_parse_input_style_transfer(self):
        result = self.analyzer._parse_input("apply style transfer to this image")
        assert result.intent == InputIntent.STYLE_TRANSFER

    def test_parse_input_variation(self):
        result = self.analyzer._parse_input("create a variation of this design")
        assert result.intent == InputIntent.VARIATION

    def test_parse_input_upscale(self):
        result = self.analyzer._parse_input("upscale this image to 4k")
        assert result.intent == InputIntent.UPSCALE

    def test_extract_style_keywords(self):
        result = self.analyzer._parse_input(
            "generate a cartoon mascot in vibrant colors"
        )
        assert result.style is not None
        assert "cartoon" in result.style
        assert "vibrant" in result.style

    def test_extract_constraints_dimensions(self):
        result = self.analyzer._parse_input(
            "generate a mascot 1024x1024 format png"
        )
        assert result.constraints.get("width") == 1024
        assert result.constraints.get("height") == 1024
        assert result.constraints.get("format") == "png"

    def test_extract_references_from_text(self):
        result = self.analyzer._parse_input(
            "generate a mascot like https://example.com/image.png"
        )
        assert len(result.references) > 0
        assert result.references[0].type == ReferenceType.URL

    def test_needs_clarification_no_subject(self):
        analyzed = AnalyzedInput(
            raw_input="generate",
            intent=InputIntent.GENERATE_IMAGE,
            subject="",
            context_score=0.2,
            missing_fields=["subject"]
        )
        assert self.analyzer.needs_clarification(analyzed)

    def test_generate_clarification(self):
        analyzed = AnalyzedInput(
            raw_input="make something",
            intent=InputIntent.GENERATE_IMAGE,
            subject="",
            context_score=0.2,
            missing_fields=["subject"]
        )
        clarification = self.analyzer.generate_clarification(analyzed)
        assert isinstance(clarification, ClarificationRequest)
        assert len(clarification.questions) > 0

    @pytest.mark.asyncio
    async def test_analyze_full_flow(self):
        result = await self.analyzer.analyze(
            "create a cartoon mascot for India Post in red and gold colors"
        )
        assert isinstance(result, AnalyzedInput)
        assert result.intent == InputIntent.GENERATE_IMAGE
        assert result.subject is not None
        assert result.context_score > 0


class TestContextValidator:
    def setup_method(self):
        self.validator = ContextValidator()

    def test_validate_complete_input(self):
        analyzed = AnalyzedInput(
            raw_input="create a red mascot",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a red mascot",
            style="cartoon",
            constraints={"width": 1024}
        )
        result = self.validator.validate(analyzed)
        assert result.context_score > 0.5
        assert len(result.missing_fields) == 0

    def test_validate_incomplete_input(self):
        analyzed = AnalyzedInput(
            raw_input="",
            intent=InputIntent.UNKNOWN,
            subject="",
            context_score=0.0
        )
        result = self.validator.validate(analyzed)
        assert result.context_score < 0.5
        assert len(result.missing_fields) > 0

    def test_is_sufficient_above_threshold(self):
        assert self.validator.is_sufficient(0.8)

    def test_is_sufficient_below_threshold(self):
        assert not self.validator.is_sufficient(0.3)

    def test_get_missing_fields(self):
        analyzed = AnalyzedInput(
            raw_input="",
            intent=InputIntent.UNKNOWN,
            subject="",
            context_score=0.0
        )
        missing = self.validator.get_missing_fields(analyzed)
        assert len(missing) > 0


class TestReferenceResolver:
    def setup_method(self):
        self.resolver = ReferenceResolver()

    @pytest.mark.asyncio
    async def test_resolve_batch_empty(self):
        results = await self.resolver.resolve_batch([])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_resolve_batch_file(self):
        results = await self.resolver.resolve_batch([
            {"type": "file", "path": "/nonexistent/test.png"}
        ])
        assert len(results) == 1
        assert results[0].type == ReferenceType.FILE

    @pytest.mark.asyncio
    async def test_resolve_batch_url(self):
        results = await self.resolver.resolve_batch([
            {"type": "url", "url": "https://example.com/image.png"}
        ])
        assert len(results) == 1
        assert results[0].type == ReferenceType.URL

    def test_get_cached_path_none(self):
        assert self.resolver.get_cached_path("https://nonexistent.com") is None