"""Tests for Phase 3: Quality Checker."""

import pytest

from agents.phase3.ml_validators import MLValidators
from agents.phase3.quality_checker import QualityChecker
from agents.phase3.refinement_loop import RefinementLoop
from models.generation_models import GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput, InputIntent
from models.quality_models import CheckStatus, CheckType, MLCheckResult, QualityReport


class TestMLValidators:
    def setup_method(self):
        self.validators = MLValidators()

    def test_init(self):
        assert self.validators is not None
        assert isinstance(self.validators.enabled_checks, list)

    @pytest.mark.asyncio
    async def test_check_technical_quality_nonexistent(self):
        result = await self.validators.check_technical_quality("/nonexistent/path.png")
        assert result.status == CheckStatus.FAILED
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_detect_artifacts_unavailable(self):
        result = await self.validators.detect_artifacts("/nonexistent/path.png")
        assert result.status in [CheckStatus.FAILED, CheckStatus.SKIPPED]

    @pytest.mark.asyncio
    async def test_check_body_logic(self):
        result = await self.validators.check_body_logic("/nonexistent/path.png")
        assert result.check_type == CheckType.FACE_BODY_LOGIC

    @pytest.mark.asyncio
    async def test_check_text_accuracy_no_text(self):
        result = await self.validators.check_text_accuracy("/nonexistent/path.png", "")
        assert result.status == CheckStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_assess_composition_unavailable(self):
        result = await self.validators.assess_composition("/nonexistent/path.png")
        assert result.check_type == CheckType.COMPOSITION

    def test_add_remove_check(self):
        self.validators.add_check(CheckType.COMPOSITION)
        assert CheckType.COMPOSITION in self.validators.enabled_checks
        self.validators.remove_check(CheckType.COMPOSITION)
        assert CheckType.COMPOSITION not in self.validators.enabled_checks

    @pytest.mark.asyncio
    async def test_run_all_checks_empty_enabled(self):
        self.validators.enabled_checks = []
        results = await self.validators.run_all_checks("/nonexistent/path.png", "test")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_clip_score_unavailable(self):
        result = await self.validators.clip_score("/nonexistent/path.png", "test prompt")
        assert result.check_type == CheckType.PROMPT_ALIGNMENT
        assert result.status in [CheckStatus.SKIPPED, CheckStatus.FAILED]

    @pytest.mark.asyncio
    async def test_structural_similarity_unavailable(self):
        result = await self.validators.structural_similarity(
            "/nonexistent/a.png", "/nonexistent/b.png"
        )
        assert result.check_type == CheckType.STRUCTURAL_SIMILARITY


class TestQualityChecker:
    def setup_method(self):
        self.checker = QualityChecker()

    def test_init(self):
        assert self.checker is not None
        assert self.checker.ml_validators is not None

    @pytest.mark.asyncio
    async def test_evaluate_no_image(self):
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="test"
        )
        result = GenerationResult(
            image_path="",
            backend_used="test",
            prompt_used="test",
            status=GenerationStatus.FAILED
        )
        report = await self.checker.evaluate(result, analyzed)
        assert isinstance(report, QualityReport)
        assert report.passed is False

    def test_calculate_overall_score(self):
        ml_results = [
            MLCheckResult(
                check_type=CheckType.TECHNICAL_QUALITY,
                score=0.9,
                status=CheckStatus.PASSED
            )
        ]
        score = self.checker._calculate_overall_score(ml_results, [])
        assert 0 <= score <= 1

    def test_generate_refinement_notes_passed(self):
        ml_results = [
            MLCheckResult(
                check_type=CheckType.TECHNICAL_QUALITY,
                score=0.9,
                status=CheckStatus.PASSED
            )
        ]
        notes = self.checker._generate_refinement_notes(ml_results, [], True)
        assert len(notes) == 0

    def test_generate_refinement_notes_failed(self):
        ml_results = [
            MLCheckResult(
                check_type=CheckType.TECHNICAL_QUALITY,
                score=0.2,
                status=CheckStatus.FAILED,
                issues=["Resolution too low"]
            )
        ]
        notes = self.checker._generate_refinement_notes(ml_results, [], False)
        assert len(notes) > 0

    def test_reset_tokens(self):
        self.checker.tokens_used = 100
        self.checker.reset_tokens()
        assert self.checker.tokens_used == 0

    @pytest.mark.asyncio
    async def test_needs_refinement(self):
        report = QualityReport(overall_score=0.3, passed=False)
        assert await self.checker.needs_refinement(report) is True

        report = QualityReport(overall_score=0.9, passed=True)
        assert await self.checker.needs_refinement(report) is False

    @pytest.mark.asyncio
    async def test_tier1_is_conclusive_all_pass(self):
        results = [
            MLCheckResult(check_type=CheckType.TECHNICAL_QUALITY, score=0.9, status=CheckStatus.PASSED)
        ]
        assert self.checker._tier1_is_conclusive(results) is True

    @pytest.mark.asyncio
    async def test_tier1_is_conclusive_clear_fail(self):
        results = [
            MLCheckResult(check_type=CheckType.TECHNICAL_QUALITY, score=0.1, status=CheckStatus.FAILED)
        ]
        assert self.checker._tier1_is_conclusive(results) is True

    @pytest.mark.asyncio
    async def test_tier1_is_conclusive_inconclusive(self):
        results = [
            MLCheckResult(check_type=CheckType.TECHNICAL_QUALITY, score=0.5, status=CheckStatus.INCONCLUSIVE)
        ]
        assert self.checker._tier1_is_conclusive(results) is False

    @pytest.mark.asyncio
    async def test_tier1_is_conclusive_empty(self):
        assert self.checker._tier1_is_conclusive([]) is False

    def test_build_ai_prompt(self):
        ml_result = MLCheckResult(
            check_type=CheckType.TECHNICAL_QUALITY,
            score=0.5,
            status=CheckStatus.INCONCLUSIVE
        )
        generation = GenerationResult(prompt_used="test prompt")
        analyzed = AnalyzedInput(raw_input="test", subject="test subject")
        prompt = self.checker._build_ai_prompt(ml_result, generation, analyzed)
        assert "Technical Quality" in prompt
        assert "test prompt" in prompt


class TestRefinementLoop:
    def setup_method(self):
        self.loop = RefinementLoop()

    def test_init_defaults(self):
        assert self.loop is not None
        assert self.loop.max_iterations == 3
        assert self.loop.auto_refine is True
        assert self.loop.current_iteration == 0

    def test_can_continue(self):
        self.loop.max_iterations = 3
        self.loop.current_iteration = 0
        assert self.loop.can_continue() is True
        self.loop.current_iteration = 2
        assert self.loop.can_continue() is False

    def test_get_history_empty(self):
        assert self.loop.get_history() == []

    def test_get_history(self):
        self.loop.refinement_history.append({"iteration": 0, "score": 0.5})
        history = self.loop.get_history()
        assert len(history) == 1

    def test_reset(self):
        self.loop.current_iteration = 5
        self.loop.refinement_history = [{"test": "data"}]
        self.loop.reset()
        assert self.loop.current_iteration == 0
        assert len(self.loop.refinement_history) == 0

    def test_get_progress(self):
        progress = self.loop.get_progress()
        assert "current_iteration" in progress
        assert "max_iterations" in progress
        assert "auto_refine" in progress
        assert "history_count" in progress

    def test_set_max_iterations(self):
        self.loop.set_max_iterations(5)
        assert self.loop.max_iterations == 5

    def test_set_auto_refine(self):
        self.loop.set_auto_refine(False)
        assert self.loop.auto_refine is False

    @pytest.mark.asyncio
    async def test_build_refinement_prompt_with_notes(self):
        from models.quality_models import QualityReport
        report = QualityReport(
            refinement_notes=["fix colors", "improve resolution"]
        )
        prompt = await self.loop.build_refinement_prompt("original prompt", report)
        assert "original prompt" in prompt
        assert "fix colors" in prompt

    @pytest.mark.asyncio
    async def test_build_refinement_prompt_no_notes(self):
        from models.quality_models import QualityReport
        report = QualityReport(refinement_notes=[])
        prompt = await self.loop.build_refinement_prompt("original prompt", report)
        assert prompt == "original prompt"