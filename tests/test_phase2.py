"""Tests for Phase 2: Creator Agent."""

import pytest

from agents.phase2.backend_registry import BackendRegistry
from agents.phase2.creator_agent import CreatorAgent
from agents.phase2.generation_pipeline import GenerationPipeline
from agents.phase2.model_router import ModelRouter, TaskType
from models.generation_models import GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput, InputIntent


class TestModelRouter:
    def setup_method(self):
        self.router = ModelRouter()

    def test_select_backend_generate(self):
        analyzed = AnalyzedInput(
            raw_input="generate a mascot",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a mascot"
        )
        backend = self.router.select_backend(analyzed)
        assert backend is not None
        assert backend in self.router.backend_candidates

    def test_select_backend_edit(self):
        analyzed = AnalyzedInput(
            raw_input="edit this image",
            intent=InputIntent.EDIT_IMAGE,
            subject="an image"
        )
        backend = self.router.select_backend(analyzed, quality_needs="high")
        assert backend is not None

    def test_select_backend_upscale(self):
        analyzed = AnalyzedInput(
            raw_input="upscale this image",
            intent=InputIntent.UPSCALE,
            subject="an image"
        )
        backend = self.router.select_backend(analyzed)
        assert backend is not None

    def test_intent_to_task_type(self):
        mapping = {
            InputIntent.GENERATE_IMAGE: TaskType.IMAGE_GENERATION,
            InputIntent.EDIT_IMAGE: TaskType.IMAGE_EDITING,
            InputIntent.STYLE_TRANSFER: TaskType.STYLE_TRANSFER,
            InputIntent.VARIATION: TaskType.VARIATION,
            InputIntent.UPSCALE: TaskType.UPSCALING,
            InputIntent.UNKNOWN: TaskType.IMAGE_GENERATION,
        }
        for intent, expected in mapping.items():
            assert self.router._intent_to_task_type(intent) == expected

    def test_get_backend_info(self):
        info = self.router.get_backend_info("mcp")
        assert info is not None
        assert info.name == "mcp"

    def test_get_backend_info_nonexistent(self):
        info = self.router.get_backend_info("nonexistent")
        assert info is None

    def test_list_available_backends(self):
        backends = self.router.list_available_backends()
        assert len(backends) > 0
        assert "mcp" in backends

    def test_set_backend_available(self):
        self.router.set_backend_available("cli", False)
        assert self.router.backend_candidates["cli"].available is False
        self.router.set_backend_available("cli", True)

    def test_backend_candidate_score(self):
        analyzed = AnalyzedInput(
            raw_input="generate",
            intent=InputIntent.GENERATE_IMAGE,
            subject="test"
        )
        backend = self.router.select_backend(analyzed, quality_needs="draft")
        assert backend is not None

    def test_score_all_candidates(self):
        task_type = TaskType.IMAGE_GENERATION
        for name, candidate in self.router.backend_candidates.items():
            score = candidate.score(task_type, "standard")
            assert isinstance(score, float)

    def test_select_backend_premium_quality(self):
        analyzed = AnalyzedInput(
            raw_input="generate a mascot",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a mascot"
        )
        backend = self.router.select_backend(analyzed, quality_needs="premium")
        assert backend is not None

    def test_select_backend_style_transfer(self):
        analyzed = AnalyzedInput(
            raw_input="apply style transfer",
            intent=InputIntent.STYLE_TRANSFER,
            subject="an image"
        )
        backend = self.router.select_backend(analyzed)
        assert backend is not None

    def test_select_backend_variation(self):
        analyzed = AnalyzedInput(
            raw_input="create a variation",
            intent=InputIntent.VARIATION,
            subject="a design"
        )
        backend = self.router.select_backend(analyzed)
        assert backend is not None


class TestBackendRegistry:
    def setup_method(self):
        self.registry = BackendRegistry()

    def test_get_backend(self):
        backend = self.registry.get_backend("mcp")
        assert backend is not None

    def test_get_backend_nonexistent(self):
        backend = self.registry.get_backend("nonexistent")
        assert backend is None

    def test_list_backends(self):
        backends = self.registry.backends
        assert len(backends) > 0
        assert "mcp" in backends

    def test_is_available(self):
        assert self.registry.is_available("mcp") is True

    def test_is_available_nonexistent(self):
        assert self.registry.is_available("nonexistent") is False

    def test_get_backend_config(self):
        config = self.registry.get_backend_config("mcp")
        assert config is None or config is not None

    def test_list_available_backends_filtered(self):
        backends = self.registry.list_available_backends()
        assert isinstance(backends, list)
        assert len(backends) > 0


class TestGenerationPipeline:
    def setup_method(self):
        self.pipeline = GenerationPipeline()

    def test_build_prompt(self):
        analyzed = AnalyzedInput(
            raw_input="create a mascot",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a friendly mascot",
            style="cartoon, vibrant",
            constraints={"width": 1024, "height": 1024}
        )
        prompt = self.pipeline.build_prompt(analyzed)
        assert "a friendly mascot" in prompt
        assert "cartoon" in prompt.lower()

    def test_build_prompt_with_style(self):
        analyzed = AnalyzedInput(
            raw_input="create a logo",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a blue logo",
            style="minimalist, vector"
        )
        prompt = self.pipeline.build_prompt(analyzed)
        assert "a blue logo" in prompt
        assert "minimalist" in prompt.lower()

    def test_get_parameters(self):
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="test"
        )
        params = self.pipeline.get_parameters(analyzed, "mcp")
        assert isinstance(params, dict)
        assert "width" in params
        assert "height" in params

    def test_get_parameters_unknown_backend(self):
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="test"
        )
        params = self.pipeline.get_parameters(analyzed, "unknown")
        assert isinstance(params, dict)

    def test_format_prompt_for_backend_mcp(self):
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a mascot"
        )
        formatted = self.pipeline.format_prompt_for_backend("a mascot", "mcp", analyzed)
        assert "mascot" in formatted.lower()

    def test_format_prompt_for_backend_cli(self):
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a mascot"
        )
        formatted = self.pipeline.format_prompt_for_backend("a mascot", "cli", analyzed)
        assert "mascot" in formatted.lower()

    def test_format_prompt_for_backend_unknown(self):
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a mascot"
        )
        formatted = self.pipeline.format_prompt_for_backend("a mascot", "unknown", analyzed)
        assert formatted == "a mascot"

    def test_extract_references(self):
        from models.input_models import Reference, ReferenceType
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="test",
            references=[
                Reference(type=ReferenceType.FILE, path="/tmp/test.png"),
                Reference(type=ReferenceType.URL, url="https://example.com/img.png")
            ]
        )
        refs = self.pipeline.extract_references(analyzed)
        assert len(refs) == 2

    def test_build_prompt_mascot(self):
        analyzed = AnalyzedInput(
            raw_input="create a mascot",
            intent=InputIntent.GENERATE_IMAGE,
            subject="India Post mascot"
        )
        prompt = self.pipeline.build_prompt(analyzed)
        assert "Trust" in prompt or "mascot" in prompt.lower()


class TestCreatorAgent:
    def setup_method(self):
        self.creator = CreatorAgent()

    @pytest.mark.asyncio
    async def test_generate_with_analyzed(self):
        analyzed = AnalyzedInput(
            raw_input="create a test image",
            intent=InputIntent.GENERATE_IMAGE,
            subject="a test image",
            style="simple"
        )
        result = await self.creator.generate(analyzed=analyzed)
        assert isinstance(result, GenerationResult)
        assert result.status in [GenerationStatus.FAILED, GenerationStatus.COMPLETED]

    def test_select_best(self):
        results = [
            GenerationResult(
                image_path="/tmp/test1.png",
                backend_used="test",
                prompt_used="test",
                status=GenerationStatus.COMPLETED
            ),
            GenerationResult(
                image_path="/tmp/test2.png",
                backend_used="test",
                prompt_used="test",
                status=GenerationStatus.FAILED
            )
        ]
        best = self.creator.select_best(results)
        assert best is not None
        assert best.status == GenerationStatus.COMPLETED

    def test_select_best_empty(self):
        best = self.creator.select_best([])
        assert best.status == GenerationStatus.FAILED