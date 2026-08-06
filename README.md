Summary of work
1. Tier-2 AI validation via opencode provider (first task)
- agents/phase3/quality_checker.py _call_ai_model: removed hardcoded gpt-4o-mini; now uses os.environ.get("AI_MODEL", "qwc/qwen3.7-plus") and passes api_key/base_url from env to AsyncOpenAI. No OpenAI key needed.
- Verified in-run: log shows Tier 1 inconclusive, invoking Tier 2 (AI) and a real AI result (score 0.02) via the opencode endpoint.
2. Phase-1 context gate relaxed — agents/phase1/context_validator.py
- Only required fields (subject, intent) now always count toward the score; optional fields (style, constraints, references) only count when present. Plain prompts like "a cozy coffee shop interior..." now score 0.9 (was 0.54) and pass. Previously absent optional fields were averaged in at 0.0, capping any plain prompt at 0.6.
3. Composition metric fixed — agents/phase3/ml_validators.py assess_composition
- Old metric sampled a 100×100 box at fixed third-points and divided by 10000, capping clean images near ~0.02 (could never pass). New heuristic measures edge-distribution balance across a 3×3 grid (coefficient of variation + coverage), defaults blank images to neutral 0.5.
- Also fixed a missing import numpy as np in that function.
Verification
- 52/52 pytest (phase1 + phase3) pass.
- Full E2E on a plain prompt: success=True, overall_score 0.814, passed=True, image saved via pollinations (instance ml_only since tier-1 now passes, so no AI credits burned).
Server restarted on port 8000 (PID 36722). Next you could try another prompt, or explore tuning the 0.7 pass threshold.
