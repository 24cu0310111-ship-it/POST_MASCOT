"""Tests for Orchestrator and State Manager."""

import tempfile

import pytest

from models.generation_models import GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput, ClarificationRequest, InputIntent
from models.quality_models import QualityReport
from orchestrator import FinalResult, MAOrchestrator, OrchestratorConfig
from state_manager import StateManager


class TestFinalResult:
    def test_init_defaults(self):
        result = FinalResult(success=False)
        assert result.success is False
        assert result.analyzed_input is None
        assert result.generation_result is None
        assert result.quality_report is None
        assert result.clarification_request is None
        assert result.error is None
        assert result.iteration_count == 0
        assert result.total_tokens_used == 0
        assert result.total_time_ms == 0

    def test_to_dict_minimal(self):
        result = FinalResult(success=True, total_time_ms=100)
        d = result.to_dict()
        assert d["success"] is True
        assert d["total_time_ms"] == 100
        assert "analyzed_input" not in d
        assert "generation_result" not in d

    def test_to_dict_full(self):
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="test subject",
            context_score=0.8
        )
        gen = GenerationResult(
            image_path="/tmp/test.png",
            backend_used="test",
            prompt_used="test",
            status=GenerationStatus.COMPLETED
        )
        quality = QualityReport(overall_score=0.9, passed=True)
        clarification = ClarificationRequest(
            missing_fields=["style"],
            questions=["What style?"],
            suggestions=["cartoon, realistic"]
        )
        result = FinalResult(
            success=True,
            analyzed_input=analyzed,
            generation_result=gen,
            quality_report=quality,
            clarification_request=clarification,
            error="some error",
            iteration_count=2,
            total_tokens_used=10,
            total_time_ms=500
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["analyzed_input"]["raw_input"] == "test"
        assert d["generation_result"]["image_path"] == "/tmp/test.png"
        assert d["quality_report"]["overall_score"] == 0.9
        assert d["clarification_request"]["missing_fields"] == ["style"]
        assert d["error"] == "some error"
        assert d["iteration_count"] == 2
        assert d["total_tokens_used"] == 10
        assert d["total_time_ms"] == 500


class TestOrchestratorConfig:
    def test_defaults(self):
        config = OrchestratorConfig()
        assert config.max_iterations == 3
        assert config.auto_refine is True
        assert config.quality_threshold == 0.7
        assert config.debug is False

    def test_custom(self):
        config = OrchestratorConfig(
            max_iterations=5,
            auto_refine=False,
            quality_threshold=0.9,
            debug=True
        )
        assert config.max_iterations == 5
        assert config.auto_refine is False
        assert config.quality_threshold == 0.9
        assert config.debug is True


class TestMAOrchestrator:
    def setup_method(self):
        self.config = OrchestratorConfig(max_iterations=1)
        self.orchestrator = MAOrchestrator(self.config)

    def test_init(self):
        assert self.orchestrator.phase1 is not None
        assert self.orchestrator.phase2 is not None
        assert self.orchestrator.phase3 is not None
        assert self.orchestrator.refinement_loop is not None
        assert self.orchestrator.config.max_iterations == 1

    def test_get_status(self):
        status = self.orchestrator.get_status()
        assert "phase1_ready" in status
        assert "phase2_ready" in status
        assert "phase3_ready" in status
        assert "refinement_loop" in status
        assert "config" in status

    def test_cleanup(self):
        self.orchestrator.cleanup()

    @pytest.mark.asyncio
    async def test_run_insufficient_input(self):
        result = await self.orchestrator.run("hi")
        assert isinstance(result, FinalResult)
        assert result.success is False
        assert result.clarification_request is not None

    @pytest.mark.asyncio
    async def test_present_to_user_completed(self):
        result = GenerationResult(
            image_path="/tmp/test.png",
            backend_used="test",
            prompt_used="test",
            status=GenerationStatus.COMPLETED
        )
        quality = QualityReport(overall_score=0.9, passed=True)
        final = await self.orchestrator.present_to_user(result, quality)
        assert final.success is True

    @pytest.mark.asyncio
    async def test_present_to_user_failed_quality(self):
        result = GenerationResult(
            image_path="/tmp/test.png",
            backend_used="test",
            prompt_used="test",
            status=GenerationStatus.COMPLETED
        )
        quality = QualityReport(overall_score=0.3, passed=False)
        final = await self.orchestrator.present_to_user(result, quality)
        assert final.success is True
        assert final.generation_result is not None

    @pytest.mark.asyncio
    async def test_present_to_user_no_result(self):
        final = await self.orchestrator.present_to_user(None, None)
        assert final.success is False

    def test_enhance_input_with_clarifications(self):
        analyzed = AnalyzedInput(
            raw_input="make something",
            intent=InputIntent.GENERATE_IMAGE,
            subject="",
            context_score=0.2
        )
        enhanced = self.orchestrator._enhance_input_with_clarifications(
            "make something",
            analyzed,
            {"subject": "a mascot", "style": "cartoon"}
        )
        assert "a mascot" in enhanced
        assert "cartoon" in enhanced

    def test_select_best_variant(self):
        results = [
            FinalResult(
                success=True,
                quality_report=QualityReport(overall_score=0.9, passed=True)
            ),
            FinalResult(
                success=True,
                quality_report=QualityReport(overall_score=0.5, passed=False)
            )
        ]
        best = self.orchestrator.select_best_variant(results)
        assert best.quality_report.overall_score == 0.9


class TestStateManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = StateManager(storage_dir=self.temp_dir)

    def test_create_session(self):
        session = self.manager.create_session("test-001")
        assert session.session_id == "test-001"
        assert "test-001" in self.manager.active_sessions

    def test_get_session(self):
        self.manager.create_session("test-002")
        session = self.manager.get_session("test-002")
        assert session is not None
        assert session.session_id == "test-002"

    def test_get_session_not_found(self):
        session = self.manager.get_session("nonexistent")
        assert session is None

    def test_delete_session(self):
        self.manager.create_session("test-003")
        self.manager.delete_session("test-003")
        assert self.manager.get_session("test-003") is None

    def test_log_iteration(self):
        self.manager.create_session("test-004")
        state = self.manager.log_iteration(
            "test-004",
            iteration=0,
            notes=["test note"]
        )
        assert state.iteration == 0
        assert "test note" in state.refinement_notes

    def test_set_analyzed_input(self):
        self.manager.create_session("test-005")
        analyzed = AnalyzedInput(
            raw_input="test",
            intent=InputIntent.GENERATE_IMAGE,
            subject="test"
        )
        self.manager.set_analyzed_input("test-005", analyzed)
        session = self.manager.get_session("test-005")
        assert session.analyzed_input is not None
        assert session.analyzed_input.subject == "test"

    def test_set_final_result(self):
        self.manager.create_session("test-006")
        result = {"image_path": "/tmp/test.png", "score": 0.9}
        self.manager.set_final_result("test-006", result)
        session = self.manager.get_session("test-006")
        assert session.final_result is not None
        assert session.final_result["score"] == 0.9

    def test_undo_iteration(self):
        self.manager.create_session("test-007")
        self.manager.log_iteration("test-007", iteration=0, notes=["note1"])
        self.manager.log_iteration("test-007", iteration=1, notes=["note2"])
        session = self.manager.get_session("test-007")
        assert len(session.iterations) == 2
        removed = self.manager.undo_iteration("test-007")
        assert removed.iteration == 1
        session = self.manager.get_session("test-007")
        assert len(session.iterations) == 1

    def test_undo_iteration_empty(self):
        self.manager.create_session("test-008")
        removed = self.manager.undo_iteration("test-008")
        assert removed is None

    def test_go_to_iteration(self):
        self.manager.create_session("test-009")
        self.manager.log_iteration("test-009", iteration=0)
        self.manager.log_iteration("test-009", iteration=1)
        self.manager.log_iteration("test-009", iteration=2)
        success = self.manager.go_to_iteration("test-009", 1)
        assert success is True
        session = self.manager.get_session("test-009")
        assert len(session.iterations) == 2

    def test_get_generation_history(self):
        self.manager.create_session("test-010")
        gen = GenerationResult(
            image_path="/tmp/test.png",
            backend_used="test",
            prompt_used="test",
            status=GenerationStatus.COMPLETED
        )
        self.manager.log_iteration("test-010", iteration=0, generation=gen)
        history = self.manager.get_generation_history("test-010")
        assert len(history) == 1
        assert history[0].image_path == "/tmp/test.png"

    def test_get_iteration_history(self):
        self.manager.create_session("test-011")
        self.manager.log_iteration("test-011", iteration=0)
        self.manager.log_iteration("test-011", iteration=1)
        history = self.manager.get_iteration_history("test-011")
        assert len(history) == 2

    def test_get_session_summary(self):
        self.manager.create_session("test-012")
        summary = self.manager.get_session_summary("test-012")
        assert summary is not None
        assert summary["session_id"] == "test-012"
        assert summary["total_iterations"] == 0
        assert summary["has_final_result"] is False

    def test_list_sessions(self):
        self.manager.create_session("test-013")
        self.manager.create_session("test-014")
        sessions = self.manager.list_sessions()
        ids = [s["session_id"] for s in sessions]
        assert "test-013" in ids
        assert "test-014" in ids

    def test_persistence(self):
        self.manager.create_session("test-015")
        self.manager.log_iteration("test-015", iteration=0, notes=["persist test"])
        new_manager = StateManager(storage_dir=self.temp_dir)
        session = new_manager.get_session("test-015")
        assert session is not None
        assert len(session.iterations) == 1
        assert session.iterations[0].refinement_notes == ["persist test"]

    def test_cleanup_old_sessions(self):
        self.manager.create_session("test-016")
        session = self.manager.get_session("test-016")
        session.updated_at = 0
        self.manager.active_sessions["test-016"] = session
        self.manager.cleanup_old_sessions(max_age_hours=0)
        assert self.manager.get_session("test-016") is None