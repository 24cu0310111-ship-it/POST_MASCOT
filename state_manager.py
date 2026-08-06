"""State Manager - Tracks conversation state across refinement loops."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from models.generation_models import GenerationResult
from models.input_models import AnalyzedInput
from models.quality_models import QualityReport
from utils.logger import get_logger

logger = get_logger("state_manager")


@dataclass
class IterationState:
    """State for a single refinement iteration."""
    iteration: int
    generation: GenerationResult | None = None
    quality_report: QualityReport | None = None
    refinement_notes: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionState:
    """Full session state across all iterations."""
    session_id: str
    analyzed_input: AnalyzedInput | None = None
    iterations: list[IterationState] = field(default_factory=list)
    final_result: dict | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def current_iteration(self) -> int:
        return len(self.iterations)

    def add_iteration(self, state: IterationState):
        self.iterations.append(state)
        self.updated_at = time.time()

    def get_iteration(self, iteration: int) -> IterationState | None:
        for s in self.iterations:
            if s.iteration == iteration:
                return s
        return None


class StateManager:
    """Manages conversation state, iteration history, and undo/redo."""

    def __init__(self, storage_dir: str = "./state_storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: dict[str, SessionState] = {}
        self.history: list[SessionState] = []

    def create_session(self, session_id: str | None = None) -> SessionState:
        import uuid
        session_id = session_id or str(uuid.uuid4())
        session = SessionState(session_id=session_id)
        self.active_sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionState | None:
        return self.active_sessions.get(session_id) or self._load_session(session_id)

    def save_session(self, session: SessionState):
        self.active_sessions[session.session_id] = session
        self._persist_session(session)

    def delete_session(self, session_id: str):
        self.active_sessions.pop(session_id, None)
        session_file = self.storage_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()

    def log_iteration(
        self,
        session_id: str,
        iteration: int,
        generation: GenerationResult = None,
        quality: QualityReport = None,
        notes: list[str] = None
    ) -> IterationState:
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)

        state = IterationState(
            iteration=iteration,
            generation=generation,
            quality_report=quality,
            refinement_notes=notes or []
        )
        session.add_iteration(state)
        self.save_session(session)
        return state

    def set_analyzed_input(self, session_id: str, analyzed: AnalyzedInput):
        session = self.get_session(session_id)
        if session:
            session.analyzed_input = analyzed
            self.save_session(session)

    def set_final_result(self, session_id: str, result: dict):
        session = self.get_session(session_id)
        if session:
            session.final_result = result
            self.save_session(session)

    def undo_iteration(self, session_id: str) -> IterationState | None:
        session = self.get_session(session_id)
        if session and session.iterations:
            removed = session.iterations.pop()
            self.save_session(session)
            return removed
        return None

    def go_to_iteration(self, session_id: str, iteration: int) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        session.iterations = [s for s in session.iterations if s.iteration <= iteration]
        self.save_session(session)
        return True

    def get_generation_history(self, session_id: str) -> list[GenerationResult]:
        session = self.get_session(session_id)
        if not session:
            return []
        return [
            s.generation for s in session.iterations
            if s.generation is not None
        ]

    def get_iteration_history(self, session_id: str) -> list[IterationState]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.iterations

    def get_session_summary(self, session_id: str) -> dict | None:
        session = self.get_session(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "total_iterations": len(session.iterations),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "intent": session.analyzed_input.intent.value if session.analyzed_input else None,
            "subject": session.analyzed_input.subject if session.analyzed_input else None,
            "has_final_result": session.final_result is not None
        }

    def list_sessions(self) -> list[dict]:
        summaries = []
        for session_id in self.active_sessions:
            summary = self.get_session_summary(session_id)
            if summary:
                summaries.append(summary)
        for session_file in self.storage_dir.glob("*.json"):
            session_id = session_file.stem
            if session_id not in self.active_sessions:
                session = self._load_session(session_id)
                if session:
                    summaries.append(self.get_session_summary(session_id))
        return summaries

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        cutoff = time.time() - (max_age_hours * 3600)
        for session_id in list(self.active_sessions.keys()):
            session = self.active_sessions[session_id]
            if session.updated_at < cutoff:
                self.delete_session(session_id)

    def _persist_session(self, session: SessionState):
        session_file = self.storage_dir / f"{session.session_id}.json"
        try:
            data = {
                "session_id": session.session_id,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "metadata": session.metadata,
                "iterations": [
                    {
                        "iteration": s.iteration,
                        "refinement_notes": s.refinement_notes,
                        "timestamp": s.timestamp,
                        "generation": s.generation.to_dict() if s.generation else None,
                        "quality": s.quality_report.to_dict() if s.quality_report else None
                    }
                    for s in session.iterations
                ]
            }
            if session.analyzed_input:
                data["analyzed_input"] = session.analyzed_input.to_dict()
            if session.final_result:
                data["final_result"] = session.final_result
            session_file.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to persist session {session.session_id}: {e}")

    def _load_session(self, session_id: str) -> SessionState | None:
        session_file = self.storage_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        try:
            data = json.loads(session_file.read_text())
            session = SessionState(
                session_id=session_id,
                created_at=data.get("created_at", time.time()),
                updated_at=data.get("updated_at", time.time()),
                metadata=data.get("metadata", {})
            )
            for it_data in data.get("iterations", []):
                state = IterationState(
                    iteration=it_data["iteration"],
                    refinement_notes=it_data.get("refinement_notes", []),
                    timestamp=it_data.get("timestamp", time.time())
                )
                if it_data.get("generation"):
                    state.generation = GenerationResult.from_dict(it_data["generation"])
                if it_data.get("quality"):
                    state.quality_report = QualityReport.from_dict(it_data["quality"])
                session.iterations.append(state)
            if data.get("analyzed_input"):
                session.analyzed_input = AnalyzedInput.from_dict(data["analyzed_input"])
            session.final_result = data.get("final_result")
            self.active_sessions[session_id] = session
            return session
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None


state_manager = StateManager()