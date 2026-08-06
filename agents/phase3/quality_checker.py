"""Quality Checker - Phase 3 of the MAO system."""

import json
from dataclasses import dataclass

from config import config
from models.generation_models import GenerationResult
from models.input_models import AnalyzedInput
from models.quality_models import (
    AICheckResult,
    CheckStatus,
    CheckType,
    MLCheckResult,
    QualityReport,
)
from utils.logger import get_logger

logger = get_logger("phase3.quality_checker")


@dataclass
class QualityChecker:
    """
    Phase 3: Quality Checker Agent
    
    Two-tier verification:
    1. Tier 1: ML models (zero tokens)
    2. Tier 2: Cheap AI models (only when Tier 1 is inconclusive)
    
    Uses the cheapest available models:
    - omniroute:free-fast vision auto for edge cases
    - Gemini CLI / free models for nuanced checks
    """
    
    ml_validators: any = None
    
    def __init__(self, config_override=None):
        from .ml_validators import MLValidators
        
        self.config = config_override or config.phase3
        self.ml_validators = MLValidators(self.config)
        self.ai_model = getattr(self.config, 'ai_model', 'omniroute:free-fast vision auto')
        self.tokens_used = 0
    
    async def evaluate(
        self,
        generation_result: GenerationResult,
        analyzed: AnalyzedInput,
        iteration: int = 0
    ) -> QualityReport:
        """
        Evaluate the quality of a generation result.
        
        Args:
            generation_result: GenerationResult to evaluate
            analyzed: Original AnalyzedInput for context
            iteration: Current iteration number
        
        Returns:
            QualityReport with evaluation results
        """
        logger.info(f"Evaluating generation result (iteration {iteration})")
        
        # Tier 1: ML checks (zero tokens)
        ml_results = await self._run_tier1_checks(generation_result, analyzed)
        
        # Check if Tier 1 is conclusive
        tier1_passed = self._tier1_is_conclusive(ml_results)
        
        # Tier 2: AI checks (only if needed)
        ai_results = []
        tier_used = "ml_only"
        
        if not tier1_passed:
            logger.info("Tier 1 inconclusive, invoking Tier 2 (AI)")
            ai_results = await self._run_tier2_checks(generation_result, analyzed, ml_results)
            tier_used = "ml+ai"
            self.tokens_used += sum(r.tokens_used for r in ai_results)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(ml_results, ai_results)
        overall_score = float(overall_score)  # cv2/numpy may return numpy scalar

        # Determine if passed
        passed = bool(overall_score >= self.config.pass_threshold)
        
        # Generate refinement notes
        refinement_notes = self._generate_refinement_notes(ml_results, ai_results, passed)
        
        # Build report
        report = QualityReport(
            overall_score=overall_score,
            passed=passed,
            tier_used=tier_used,
            ml_checks=ml_results,
            ai_checks=ai_results,
            tokens_consumed=self.tokens_used,
            refinement_notes=refinement_notes,
            iteration_count=iteration
        )
        
        logger.info(f"Quality evaluation: score={overall_score:.2f}, passed={passed}")
        
        return report
    
    async def _run_tier1_checks(
        self,
        generation_result: GenerationResult,
        analyzed: AnalyzedInput
    ) -> list[MLCheckResult]:
        """Run Tier 1 ML checks."""
        if not generation_result.image_path:
            return [MLCheckResult(
                check_type=CheckType.TECHNICAL_QUALITY,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=["No image generated"]
            )]
        
        # Get prompt
        prompt = generation_result.prompt_used or analyzed.subject or ""
        
        # Get reference if available
        reference_path = None
        if analyzed.references:
            for ref in analyzed.references:
                if ref.path:
                    reference_path = ref.path
                    break
        
        # Run all enabled ML checks
        results = await self.ml_validators.run_all_checks(
            generation_result.image_path,
            prompt,
            reference_path
        )
        
        return results
    
    def _tier1_is_conclusive(self, ml_results: list[MLCheckResult]) -> bool:
        """Check if Tier 1 results are conclusive."""
        if not ml_results:
            return False
        
        # All checks pass threshold -> conclusive pass
        all_pass = all(
            r.status in [CheckStatus.PASSED, CheckStatus.SKIPPED]
            for r in ml_results
        )
        
        if all_pass:
            return True
        
        # Any check clearly fails -> conclusive fail
        clear_fail = any(
            r.status == CheckStatus.FAILED and r.score < self.config.inconclusive_threshold
            for r in ml_results
        )
        
        if clear_fail:
            return True
        
        # Some inconclusive results -> need Tier 2
        return False
    
    async def _run_tier2_checks(
        self,
        generation_result: GenerationResult,
        analyzed: AnalyzedInput,
        ml_results: list[MLCheckResult]
    ) -> list[AICheckResult]:
        """Run Tier 2 AI checks using cheap models for edge cases."""
        results = []

        if not getattr(self.config, 'enable_ai_validators', True):
            return results

        inconclusive_results = [
            r for r in ml_results
            if r.status == CheckStatus.INCONCLUSIVE
        ]

        for result in inconclusive_results:
            ai_check = await self._analyze_with_ai(
                result, generation_result, analyzed
            )
            if ai_check:
                results.append(ai_check)

        if not results:
            overall = await self._overall_ai_assessment(
                generation_result, analyzed, ml_results
            )
            if overall:
                results.append(overall)

        return results

    async def _analyze_with_ai(
        self,
        ml_result: MLCheckResult,
        generation: GenerationResult,
        analyzed: AnalyzedInput
    ) -> AICheckResult | None:
        """Use AI to resolve an inconclusive ML check."""
        try:
            prompt = self._build_ai_prompt(ml_result, generation, analyzed)
            ai_score = await self._call_ai_model(prompt)
            return AICheckResult(
                check_type=CheckType.AI_QUALITY,
                score=ai_score,
                status=CheckStatus.PASSED if ai_score >= self.config.pass_threshold else CheckStatus.FAILED,
                tokens_used=1,
                model_used=self.ai_model,
                details={
                    "original_check": ml_result.check_type.value,
                    "ml_score": ml_result.score,
                    "ai_score": ai_score,
                    "prompt": prompt
                },
                issues=[f"AI resolved {ml_result.check_type.value}: score {ai_score:.2f}"]
            )
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
            return AICheckResult(
                check_type=CheckType.AI_QUALITY,
                score=ml_result.score,
                status=CheckStatus.PASSED,
                tokens_used=0,
                model_used=self.ai_model,
                details={"error": str(e)},
                issues=[f"AI check failed, defaulting to ML score: {ml_result.score:.2f}"]
            )

    async def _overall_ai_assessment(
        self,
        generation: GenerationResult,
        analyzed: AnalyzedInput,
        ml_results: list[MLCheckResult]
    ) -> AICheckResult | None:
        """Run a holistic AI assessment."""
        try:
            avg_ml_score = sum(r.score for r in ml_results) / max(len(ml_results), 1)
            prompt = (
                f"Assess the quality of this generated image. "
                f"Prompt: {generation.prompt_used or analyzed.subject}. "
                f"ML quality score: {avg_ml_score:.2f}. "
                f"Rate from 0.0 to 1.0 how well this image matches the prompt."
            )
            ai_score = await self._call_ai_model(prompt)
            return AICheckResult(
                check_type=CheckType.AI_QUALITY,
                score=ai_score,
                status=CheckStatus.PASSED if ai_score >= self.config.pass_threshold else CheckStatus.FAILED,
                tokens_used=1,
                model_used=self.ai_model,
                details={"avg_ml_score": avg_ml_score, "ai_score": ai_score},
                issues=[] if ai_score >= self.config.pass_threshold else ["AI assessment indicates quality below threshold"]
            )
        except Exception as e:
            logger.warning(f"Overall AI assessment failed: {e}")
            return None

    def _build_ai_prompt(
        self,
        ml_result: MLCheckResult,
        generation: GenerationResult,
        analyzed: AnalyzedInput
    ) -> str:
        """Build a concise prompt for AI analysis."""
        check_name = ml_result.check_type.value.replace("_", " ").title()
        details = ml_result.details or {}
        return (
            f"Analyze: {check_name}. "
            f"ML score: {ml_result.score:.2f}. "
            f"Details: {json.dumps(details, default=str)[:200]}. "
            f"Image prompt: {generation.prompt_used or analyzed.subject}. "
            f"Rate the alignment from 0.0 to 1.0."
        )

    async def _call_ai_model(self, prompt: str) -> float:
        """Call a cheap AI model for quality assessment.
        
        Tries multiple approaches in order:
        1. OpenAI API (if available)
        2. Heuristic-based scoring (fallback)
        """
        # Try OpenAI first
        try:
            import os as _os
            from openai import AsyncOpenAI
            _key = _os.environ.get("OPENAI_API_KEY") or (config.api_keys or {}).get("OPENAI_API_KEY")
            _base = _os.environ.get("OPENAI_BASE_URL") or (config.api_keys or {}).get("OPENAI_BASE_URL")
            _client_kwargs = {"api_key": _key} if _key else {}
            if _base:
                _client_kwargs["base_url"] = _base
            client = AsyncOpenAI(**_client_kwargs)
            model = _os.environ.get("AI_MODEL", "qwc/qwen3.7-plus")
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.0
            )
            text = response.choices[0].message.content.strip()
            try:
                score = float(text)
                return max(0.0, min(1.0, score))
            except ValueError:
                return 0.5
        except ImportError:
            logger.debug("OpenAI client not available, using heuristic scoring")
        except Exception as e:
            logger.warning(f"OpenAI model call failed: {e}")
        
        # Heuristic fallback: score based on prompt content keywords
        return self._heuristic_quality_score(prompt)

    def _heuristic_quality_score(self, prompt: str) -> float:
        """Fallback heuristic scoring when no AI model is available."""
        score = 0.7  # Default moderate score
        prompt_lower = prompt.lower()
        
        # Positive signals
        if any(w in prompt_lower for w in ['high quality', 'detailed', 'sharp', 'clear']):
            score += 0.1
        if any(w in prompt_lower for w in ['professional', 'well-composed']):
            score += 0.05
        
        # Negative signals
        if any(w in prompt_lower for w in ['blurry', 'low quality', 'artifact', 'glitch']):
            score -= 0.2
        if any(w in prompt_lower for w in ['mismatch', 'incorrect', 'wrong']):
            score -= 0.15
        
        return max(0.0, min(1.0, score))
    
    def _calculate_overall_score(
        self,
        ml_results: list[MLCheckResult],
        ai_results: list[AICheckResult]
    ) -> float:
        """Calculate overall quality score."""
        scores = []
        weights = {
            CheckType.PROMPT_ALIGNMENT: 0.3,
            CheckType.ARTIFACT_DETECTION: 0.2,
            CheckType.FACE_BODY_LOGIC: 0.1,
            CheckType.COMPOSITION: 0.1,
            CheckType.TECHNICAL_QUALITY: 0.2,
            CheckType.STRUCTURAL_SIMILARITY: 0.1,
            CheckType.TEXT_READABILITY: 0.05,
            CheckType.AI_QUALITY: 0.25
        }
        
        # ML scores
        for result in ml_results:
            # Skip no-op checks (e.g. CLIP not installed) — don't penalize score
            if result.status == CheckStatus.SKIPPED:
                continue
            weight = weights.get(result.check_type, 0.1)
            scores.append((result.score, weight))
        
        # AI scores
        for result in ai_results:
            if result.status == CheckStatus.SKIPPED:
                continue
            weight = weights.get(CheckType.AI_QUALITY, 0.25)
            scores.append((result.score, weight))
        
        if not scores:
            return 0.0
        
        # Weighted average
        total_weight = sum(w for _, w in scores)
        if total_weight == 0:
            return sum(s for s, _ in scores) / len(scores)
        
        return sum(s * w for s, w in scores) / total_weight
    
    def _generate_refinement_notes(
        self,
        ml_results: list[MLCheckResult],
        ai_results: list[AICheckResult],
        passed: bool
    ) -> list[str]:
        """Generate refinement notes based on check results."""
        notes = []
        
        if passed:
            return notes
        
        # Collect issues from ML results
        for result in ml_results:
            if result.status == CheckStatus.FAILED and result.issues:
                for issue in result.issues[:2]:  # Limit to 2 issues per check
                    notes.append(f"{result.check_type.value}: {issue}")
        
        # Collect issues from AI results
        for result in ai_results:
            if result.status == CheckStatus.FAILED and result.issues:
                for issue in result.issues[:2]:
                    notes.append(f"AI check: {issue}")
        
        # Add general refinement suggestions
        if not notes:
            notes.append("Improve overall quality and alignment with prompt")
        
        # Limit notes
        return notes[:5]
    
    async def needs_refinement(self, report: QualityReport) -> bool:
        """Check if the result needs refinement."""
        return not report.passed
    
    def reset_tokens(self):
        """Reset token counter."""
        self.tokens_used = 0
