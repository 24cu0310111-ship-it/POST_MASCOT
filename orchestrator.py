"""MAOrchestrator - Main entry point for the Multi-Agent Orchestrator system."""

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

from agents.phase1 import InputAnalyzer
from agents.phase2 import CreatorAgent
from agents.phase3 import QualityChecker, RefinementLoop
from config import config
from models.generation_models import GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput, ClarificationRequest
from models.quality_models import QualityReport
from utils.logger import get_logger, setup_logging

logger = get_logger("orchestrator")


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    max_iterations: int = 3
    auto_refine: bool = True
    quality_threshold: float = 0.7
    debug: bool = False


@dataclass
class FinalResult:
    """Final result of the orchestration process."""
    success: bool
    analyzed_input: AnalyzedInput | None = None
    generation_result: GenerationResult | None = None
    quality_report: QualityReport | None = None
    clarification_request: ClarificationRequest | None = None
    error: str | None = None
    iteration_count: int = 0
    total_tokens_used: int = 0
    total_time_ms: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "success": self.success,
            "error": self.error,
            "iteration_count": self.iteration_count,
            "total_tokens_used": self.total_tokens_used,
            "total_time_ms": self.total_time_ms
        }
        
        if self.analyzed_input:
            result["analyzed_input"] = self.analyzed_input.to_dict()
        
        if self.generation_result:
            result["generation_result"] = self.generation_result.to_dict()
        
        if self.quality_report:
            result["quality_report"] = self.quality_report.to_dict()
        
        if self.clarification_request:
            result["clarification_request"] = self.clarification_request.to_dict()
        
        return result


@dataclass
class MAOrchestrator:
    """
    Multi-Agent Orchestrator (MAO)
    
    The top-level controller that wires the three phases together:
    1. Input Analyzer (Phase 1)
    2. Creator Agent (Phase 2)
    3. Quality Checker (Phase 3)
    
    Coordinates the complete workflow with refinement loop.
    """
    
    phase1: InputAnalyzer = field(default_factory=InputAnalyzer)
    phase2: CreatorAgent = field(default_factory=CreatorAgent)
    phase3: QualityChecker = field(default_factory=QualityChecker)
    refinement_loop: RefinementLoop = field(default_factory=RefinementLoop)
    config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    
    def __init__(self, config_override: OrchestratorConfig = None):
        """
        Initialize the orchestrator.
        
        Args:
            config_override: Optional custom configuration
        """
        # Setup logging
        setup_logging(log_level=config.log_level, console=True)
        
        # Initialize phases
        self.phase1 = InputAnalyzer()
        self.phase2 = CreatorAgent()
        self.phase3 = QualityChecker()
        self.refinement_loop = RefinementLoop()
        
        # Set configuration
        self.config = config_override or OrchestratorConfig()
        
        # Override refinement loop settings from config
        self.refinement_loop.max_iterations = self.config.max_iterations
        self.refinement_loop.auto_refine = self.config.auto_refine
        
        logger.info("MAO Orchestrator initialized")
    
    async def run(
        self,
        user_input: str,
        references: list[dict] = None,
        max_iterations: int = None
    ) -> FinalResult:
        """
        Run the complete orchestration workflow.
        
        Args:
            user_input: Raw user input text
            references: Optional list of reference dictionaries
            max_iterations: Override max iterations (default: from config)
        
        Returns:
            FinalResult with the complete output
        """
        start_time = time.time()
        
        logger.info(f"Starting MAO workflow for input: {user_input[:100]}...")
        
        try:
            # Phase 1: Input Analysis
            analyzed = await self.phase1.analyze(user_input, references)
            
            # Check if input is sufficient
            if not analyzed.is_sufficient:
                logger.info("Input context insufficient, requesting clarification")
                clarification = self.phase1.generate_clarification(analyzed)
                
                total_time_ms = int((time.time() - start_time) * 1000)
                
                return FinalResult(
                    success=False,
                    analyzed_input=analyzed,
                    clarification_request=clarification,
                    error="Input context insufficient",
                    total_time_ms=total_time_ms
                )
            
            # Set max iterations if specified
            if max_iterations is not None:
                self.refinement_loop.max_iterations = max_iterations
            
            # Run Phase 2 + Phase 3 refinement loop
            result, quality = await self.refinement_loop.run_loop(
                self.phase2,
                self.phase3,
                analyzed
            )
            
            # Final user review gate
            final_result = await self.present_to_user(result, quality)
            
            total_time_ms = int((time.time() - start_time) * 1000)
            total_tokens = quality.tokens_consumed if quality else 0
            iteration_count = quality.iteration_count if quality else 0
            
            return FinalResult(
                success=final_result.success,
                analyzed_input=analyzed,
                generation_result=result,
                quality_report=quality,
                error=final_result.error,
                iteration_count=iteration_count,
                total_tokens_used=total_tokens,
                total_time_ms=total_time_ms
            )
            
        except Exception as e:
            logger.error(f"MAO workflow error: {e}")
            total_time_ms = int((time.time() - start_time) * 1000)
            
            return FinalResult(
                success=False,
                error=str(e),
                total_time_ms=total_time_ms
            )
    
    async def present_to_user(
        self,
        result: GenerationResult,
        quality: QualityReport
    ) -> FinalResult:
        """
        Present the result to the user for final review.
        
        Args:
            result: GenerationResult to present
            quality: QualityReport for the result
        
        Returns:
            FinalResult with user decision
        """
        if not result or result.status != GenerationStatus.COMPLETED:
            return FinalResult(
                success=False,
                error="No valid generation result"
            )
        
        # Image was generated — always present it to the user
        # Quality score is informational; the user decides
        if quality and quality.passed:
            logger.info("Quality check passed, presenting to user")
        else:
            logger.info("Quality check below threshold, presenting to user for review")
        
        return FinalResult(
            success=True,
            generation_result=result,
            quality_report=quality
        )
    
    async def run_single_generation(
        self,
        user_input: str,
        references: list[dict] = None
    ) -> FinalResult:
        """
        Run a single generation without refinement loop.
        
        Args:
            user_input: Raw user input
            references: Optional references
        
        Returns:
            FinalResult with single generation
        """
        start_time = time.time()
        
        try:
            # Phase 1
            analyzed = await self.phase1.analyze(user_input, references)
            
            if not analyzed.is_sufficient:
                clarification = self.phase1.generate_clarification(analyzed)
                return FinalResult(
                    success=False,
                    analyzed_input=analyzed,
                    clarification_request=clarification,
                    error="Input context insufficient"
                )
            
            # Phase 2
            result = await self.phase2.generate(analyzed)
            
            if result.status != GenerationStatus.COMPLETED:
                return FinalResult(
                    success=False,
                    analyzed_input=analyzed,
                    generation_result=result,
                    error=result.error or "Generation failed"
                )
            
            # Phase 3
            quality = await self.phase3.evaluate(result, analyzed, 0)
            
            total_time_ms = int((time.time() - start_time) * 1000)
            
            return FinalResult(
                success=quality.passed,
                analyzed_input=analyzed,
                generation_result=result,
                quality_report=quality,
                iteration_count=0,
                total_tokens_used=quality.tokens_consumed,
                total_time_ms=total_time_ms
            )
            
        except Exception as e:
            return FinalResult(
                success=False,
                error=str(e),
                total_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def clarify_and_run(
        self,
        user_input: str,
        references: list[dict] = None,
        clarification_responses: dict[str, str] = None
    ) -> FinalResult:
        """
        Run with clarification responses.
        
        Args:
            user_input: Raw user input
            references: Optional references
            clarification_responses: Responses to clarification questions
        
        Returns:
            FinalResult after incorporating clarifications
        """
        # First run to get clarification request
        first_result = await self.run(user_input, references)
        
        if first_result.success or not first_result.clarification_request:
            return first_result
        
        # If clarification is needed and responses are provided
        if clarification_responses:
            # Update the user input with clarification responses
            enhanced_input = self._enhance_input_with_clarifications(
                user_input,
                first_result.analyzed_input,
                clarification_responses
            )
            
            # Run again with enhanced input
            return await self.run(enhanced_input, references)
        
        return first_result
    
    def _enhance_input_with_clarifications(
        self,
        original_input: str,
        analyzed: AnalyzedInput,
        responses: dict[str, str]
    ) -> str:
        """Enhance user input with clarification responses."""
        enhanced = original_input
        
        # Add missing information from responses
        for field_name, response in responses.items():
            if field_name == "subject":
                enhanced = f"{enhanced} Subject: {response}"
            elif field_name == "style":
                enhanced = f"{enhanced} Style: {response}"
            elif field_name == "intent":
                enhanced = f"{response} {enhanced}"
            else:
                enhanced = f"{enhanced} {field_name}: {response}"
        
        return enhanced
    
    async def generate_multiple_variants(
        self,
        user_input: str,
        count: int = 4,
        references: list[dict] = None
    ) -> list[FinalResult]:
        """
        Generate multiple variants of the same input.
        
        Args:
            user_input: Raw user input
            count: Number of variants
            references: Optional references
        
        Returns:
            List of FinalResult objects
        """
        results = []
        
        for i in range(count):
            # Add variant number to input
            variant_input = f"{user_input} (variant {i+1})"
            result = await self.run_single_generation(variant_input, references)
            results.append(result)
        
        return results
    
    def select_best_variant(self, results: list[FinalResult]) -> FinalResult:
        """
        Select the best variant from multiple results.
        
        Args:
            results: List of FinalResult objects
        
        Returns:
            The best FinalResult
        """
        # Filter successful results
        successful = [r for r in results if r.success and r.quality_report]
        
        if not successful:
            # Return the one with least errors
            return max(results, key=lambda r: r.quality_report.overall_score if r.quality_report else 0)
        
        # Select by quality score
        return max(successful, key=lambda r: r.quality_report.overall_score if r.quality_report else 0)
    
    def get_status(self) -> dict:
        """Get current status of the orchestrator."""
        return {
            "phase1_ready": True,
            "phase2_ready": True,
            "phase3_ready": True,
            "refinement_loop": self.refinement_loop.get_progress(),
            "config": {
                "max_iterations": self.config.max_iterations,
                "auto_refine": self.config.auto_refine,
                "quality_threshold": self.config.quality_threshold
            }
        }
    
    def cleanup(self):
        """Clean up temporary files."""
        logger.info("Cleaning up temporary files...")
        
        # Clean up temp directories
        temp_dirs = ["./temp_references", "./temp_generation"]
        for temp_dir in temp_dirs:
            try:
                import shutil
                if Path(temp_dir).exists():
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up {temp_dir}: {e}")


# Global orchestrator instance
orchestrator = MAOrchestrator()


async def main():
    """Example usage of the MAO orchestrator."""
    # Example: Generate an India Post mascot
    user_input = """
    Generate a mascot for India Post that represents Trust & Reliability, 
    Public Service, Inclusivity, Indian Culture & Heritage, Digital Innovation, 
    Friendly Personality, and Nationwide Connectivity. 
    The mascot should be in a modern Indian cartoon style, vibrant colors,
    1024x1024 resolution.
    """
    
    # Run the orchestrator
    result = await orchestrator.run(user_input)
    
    if result.success:
        print(f"Success! Generated image at: {result.generation_result.image_path}")
        print(f"Quality score: {result.quality_report.overall_score:.2f}")
        print(f"Tokens used: {result.total_tokens_used}")
        print(f"Time taken: {result.total_time_ms}ms")
    else:
        print(f"Failed: {result.error}")
        if result.clarification_request:
            print("\nClarification questions:")
            for question in result.clarification_request.questions:
                print(f"  - {question}")


if __name__ == "__main__":
    asyncio.run(main())
