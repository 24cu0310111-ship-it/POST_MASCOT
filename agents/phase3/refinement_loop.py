"""Refinement Loop - Part of Phase 3 Quality Checker."""

from dataclasses import dataclass, field

from config import config
from models.generation_models import GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from models.quality_models import QualityReport
from utils.logger import get_logger

logger = get_logger("phase3.refinement_loop")


@dataclass
class RefinementLoop:
    """
    Manages the iterative refinement cycle.
    
    Responsibilities:
    1. Manage iteration count and limits
    2. Append refinement context to prevent repeating mistakes
    3. Track token consumption
    4. Provide user control over the loop
    """
    
    max_iterations: int = 3
    auto_refine: bool = True
    current_iteration: int = 0
    refinement_history: list[dict] = field(default_factory=list)
    
    def __init__(self, config_override=None):
        self.config = config_override or config.phase3
        self.max_iterations = getattr(self.config, 'max_iterations', 3)
        self.auto_refine = getattr(self.config, 'auto_refine', True)
        self.current_iteration = 0
        self.refinement_history: list[dict] = []
    
    async def run_loop(
        self,
        creator_agent: any,
        quality_checker: any,
        analyzed: AnalyzedInput
    ) -> tuple:
        """
        Run the complete refinement loop.
        
        Args:
            creator_agent: CreatorAgent instance
            quality_checker: QualityChecker instance
            analyzed: AnalyzedInput from Phase 1
        
        Returns:
            Tuple of (final GenerationResult, final QualityReport)
        """
        logger.info("Starting refinement loop")
        
        result: GenerationResult = None
        quality: QualityReport = None
        
        for iteration in range(self.max_iterations):
            self.current_iteration = iteration
            
            # Generate
            logger.info(f"Iteration {iteration + 1}/{self.max_iterations}: Generating...")
            result = await creator_agent.generate(analyzed, result)
            
            if result.status != GenerationStatus.COMPLETED:
                logger.error(f"Generation failed: {result.error}")
                break
            
            # Evaluate
            logger.info(f"Iteration {iteration + 1}/{self.max_iterations}: Evaluating...")
            quality = await quality_checker.evaluate(result, analyzed, iteration)
            
            # Check if we should stop
            if quality.passed:
                logger.info("Quality check passed, stopping refinement loop")
                break
            
            # Check if we should continue
            if not self.auto_refine:
                logger.info("Auto-refine disabled, stopping loop")
                break
            
            # Prepare for next iteration
            if result.refinement_notes:
                result.refinement_notes.extend(quality.refinement_notes)
            else:
                result.refinement_notes = quality.refinement_notes
            
            # Record history
            self.refinement_history.append({
                "iteration": iteration,
                "image_path": result.image_path,
                "quality_score": quality.overall_score,
                "refinement_notes": quality.refinement_notes
            })
            
            logger.info(f"Iteration {iteration + 1} completed. Score: {quality.overall_score:.2f}")
            logger.info(f"Refinement notes: {quality.refinement_notes}")
        
        return result, quality
    
    def can_continue(self) -> bool:
        """Check if we can continue refining."""
        return self.current_iteration < self.max_iterations - 1
    
    def get_history(self) -> list[dict]:
        """Get the refinement history."""
        return self.refinement_history
    
    def reset(self):
        """Reset the refinement loop."""
        self.current_iteration = 0
        self.refinement_history = []
    
    def get_progress(self) -> dict:
        """Get current progress information."""
        return {
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "auto_refine": self.auto_refine,
            "history_count": len(self.refinement_history)
        }
    
    def set_max_iterations(self, max_iterations: int):
        """Set maximum iterations."""
        self.max_iterations = max_iterations
    
    def set_auto_refine(self, auto_refine: bool):
        """Enable or disable auto-refine."""
        self.auto_refine = auto_refine
    
    async def build_refinement_prompt(
        self,
        original_prompt: str,
        quality_report: QualityReport
    ) -> str:
        """
        Build a refined prompt based on quality feedback.
        
        Args:
            original_prompt: The original generation prompt
            quality_report: QualityReport with refinement notes
        
        Returns:
            Refined prompt
        """
        if not quality_report.refinement_notes:
            return original_prompt
        
        # Build refined prompt
        refined_parts = [original_prompt]
        refined_parts.append("\n\nRefinements based on quality feedback:")
        
        for note in quality_report.refinement_notes[:3]:
            refined_parts.append(f"- {note}")
        
        return " ".join(refined_parts)
