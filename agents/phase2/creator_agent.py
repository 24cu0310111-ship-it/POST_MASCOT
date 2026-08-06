"""Creator Agent - Phase 2 of the MAO system."""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from config import config
from models.generation_models import GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from utils.logger import get_logger

logger = get_logger("phase2.creator_agent")


@dataclass
class CreatorAgent:
    """
    Phase 2: Creator Agent
    
    Responsibilities:
    1. Receive analyzed input from Phase 1
    2. Select the best generation backend via Model Router
    3. Execute the generation pipeline
    4. Return the generated output with metadata
    """
    
    model_router: any = None
    backend_registry: any = None
    generation_pipeline: any = None
    
    def __init__(self, config_override=None):
        from .backend_registry import BackendRegistry
        from .generation_pipeline import GenerationPipeline
        from .model_router import ModelRouter
        
        self.config = config_override or config.phase2
        self.model_router = ModelRouter(self.config)
        self.backend_registry = BackendRegistry(self.config)
        self.generation_pipeline = GenerationPipeline(self.config)
        self.temp_dir = Path("./temp_generation")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate(
        self,
        analyzed: AnalyzedInput,
        refinement: GenerationResult = None
    ) -> GenerationResult:
        """
        Generate an image based on analyzed input.
        
        Args:
            analyzed: AnalyzedInput from Phase 1
            refinement: Optional previous GenerationResult for refinement
        
        Returns:
            GenerationResult with the generated image
        """
        start_time = time.time()
        
        logger.info(f"Starting generation for: {analyzed.subject}")
        
        try:
            # Step 1: Select backend
            backend = self.model_router.select_backend(analyzed)
            logger.info(f"Selected backend: {backend}")
            
            # Step 2: Get backend instance
            backend_instance = self.backend_registry.get_backend(backend)
            if not backend_instance:
                raise ValueError(f"Backend {backend} not available")
            
            # Step 3: Build prompt
            prompt = self.generation_pipeline.build_prompt(analyzed, refinement)
            logger.info(f"Generated prompt: {prompt[:100]}...")
            
            # Step 4: Generate image
            result = await backend_instance.generate(
                prompt=prompt,
                analyzed=analyzed,
                refinement=refinement
            )
            
            # Step 5: Update result with metadata
            result.generation_time_ms = int((time.time() - start_time) * 1000)
            result.backend_used = backend
            result.prompt_used = prompt
            
            logger.info(f"Generation completed in {result.generation_time_ms}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e),
                prompt_used=prompt if 'prompt' in locals() else ""
            )
    
    async def generate_multiple(
        self,
        analyzed: AnalyzedInput,
        count: int = 4,
        refinement: GenerationResult = None
    ) -> list[GenerationResult]:
        """
        Generate multiple variants of an image.
        
        Args:
            analyzed: AnalyzedInput from Phase 1
            count: Number of variants to generate
            refinement: Optional previous GenerationResult
        
        Returns:
            List of GenerationResult objects
        """
        results = []
        tasks = []
        
        for i in range(count):
            # Add variation to prompt
            if analyzed.subject:
                modified_analyzed = AnalyzedInput(
                    raw_input=f"{analyzed.raw_input} variant {i+1}",
                    intent=analyzed.intent,
                    subject=f"{analyzed.subject} variant {i+1}",
                    style=analyzed.style,
                    constraints=analyzed.constraints,
                    references=analyzed.references
                )
            else:
                modified_analyzed = analyzed
            
            task = self.generate(modified_analyzed, refinement)
            tasks.append(task)
        
        # Run in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Generation variant failed: {result}")
                valid_results.append(GenerationResult(
                    status=GenerationStatus.FAILED,
                    error=str(result)
                ))
            else:
                valid_results.append(result)
        
        return valid_results
    
    def select_best(self, results: list[GenerationResult]) -> GenerationResult:
        """
        Select the best result from multiple generations.
        
        Args:
            results: List of GenerationResult objects
        
        Returns:
            The best GenerationResult
        """
        # Simple selection: pick the first successful one
        for result in results:
            if result.status == GenerationStatus.COMPLETED:
                return result
        
        # If none completed, return the first one
        return results[0] if results else GenerationResult(
            status=GenerationStatus.FAILED,
            error="No results to select from"
        )
