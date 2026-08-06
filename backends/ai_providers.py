"""AI Providers - Opencode, Omniroute, Omniroute-Org backends."""

import subprocess
import time
from pathlib import Path
from typing import Any

from models.generation_models import BackendType, GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from utils.logger import get_logger
from .base_backend import BackendHealth, BaseBackend

logger = get_logger("backends.ai_providers")


class AIProviderBackend(BaseBackend):
    """Base for AI provider CLIs like opencode, omniroute."""
    
    cli_command: str = ""
    default_model: str = ""
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.CLI_TOOL
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_image_generation": True,
            "supports_image_editing": True,
            "supports_style_transfer": True,
            "supports_upscaling": True,
            "supports_variations": True,
            "max_resolution": "4096x4096",
            "formats": ["png", "jpg", "webp"],
            "needs_api_key": True,
            "requires_local_install": True
        }
        
    async def health_check(self) -> BackendHealth:
        try:
            if not self.cli_command:
                return BackendHealth.UNHEALTHY
            result = subprocess.run(["which", self.cli_command], capture_output=True, text=True)
            if result.returncode == 0:
                return BackendHealth.HEALTHY
            return BackendHealth.UNHEALTHY
        except Exception as e:
            logger.error(f"{self.name} health check error: {e}")
            return BackendHealth.UNHEALTHY

    async def generate(
        self,
        prompt: str,
        analyzed: AnalyzedInput = None,
        refinement: GenerationResult = None,
        **kwargs
    ) -> GenerationResult:
        start_time = time.time()
        output_path = self._create_output_path(prompt, ".png")
        
        try:
            model = kwargs.get("model", self.default_model)
            command = [self.cli_command, "generate", "--prompt", prompt, "--model", model, "--output", str(output_path)]
            
            logger.info(f"Running {self.name} command: {' '.join(command)}")
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            try:
                timeout_val = getattr(self, 'timeout', 300)
                stdout, stderr = process.communicate(timeout=timeout_val)
                if process.returncode != 0:
                    logger.error(f"{self.name} command failed: {stderr}")
                    return GenerationResult(status=GenerationStatus.FAILED, error=f"{self.name} error: {stderr}", prompt_used=prompt)
                
                if output_path.exists():
                    return GenerationResult(
                        image_path=str(output_path),
                        backend_used=self.name,
                        model_version=model,
                        generation_params={"prompt": prompt, "command": ' '.join(command)},
                        generation_time_ms=int((time.time() - start_time) * 1000),
                        cost_estimate=0.01,
                        prompt_used=prompt,
                        status=GenerationStatus.COMPLETED
                    )
                return GenerationResult(status=GenerationStatus.FAILED, error="No output file generated", prompt_used=prompt)
            except subprocess.TimeoutExpired:
                process.kill()
                return GenerationResult(status=GenerationStatus.FAILED, error="Command timed out", prompt_used=prompt)
        except Exception as e:
            logger.error(f"{self.name} generation error: {e}")
            return GenerationResult(status=GenerationStatus.FAILED, error=str(e), prompt_used=prompt)


class OpencodeBackend(AIProviderBackend):
    cli_command = "opencode"
    default_model = "vision-best"
    @property
    def name(self) -> str: return "opencode"


class OmnirouteBackend(AIProviderBackend):
    cli_command = "omniroute"
    default_model = "free-fast"
    @property
    def name(self) -> str: return "omniroute"


class OmnirouteOrgBackend(AIProviderBackend):
    cli_command = "omniroute-org"
    default_model = "free-fast"
    @property
    def name(self) -> str: return "omniroute-org"
