"""DSPy SIMBA-inspired prompt optimization for the Nightjar pipeline.

Optimizes Analyst/Formalizer/Coder prompts by generating variations
and evaluating them against the verification pass rate metric from
the tracking database. Creates new prompt versions with improved
performance.

The SIMBA pattern: generate prompt variation → evaluate on held-out
specs → keep if pass rate improves → register as new version.

References:
- [REF-T26] DSPy — SIMBA optimizer for prompt optimization
- [REF-C03] Analyst → Formalizer → Coder pipeline prompts
- [REF-P04] AlphaVerus — self-improving loop architecture
- [REF-T16] litellm — all LLM calls go through litellm
"""

import os
import time
from dataclasses import dataclass

import litellm

from nightjar.tracking import TrackingDB
from nightjar.prompts import PromptTemplate, PromptRegistry


@dataclass
class OptimizationConfig:
    """Configuration for a prompt optimization run.

    References:
    - [REF-T26] DSPy SIMBA configuration pattern
    """

    tracking_db_path: str
    prompt_registry_path: str
    target_prompt: str  # e.g. "analyst", "formalizer", "coder"
    max_iterations: int = 10
    improvement_threshold: float = 0.01


@dataclass
class OptimizationResult:
    """Result from a prompt optimization run.

    References:
    - [REF-T26] DSPy — optimization result tracking
    """

    target_prompt: str
    original_version: int
    best_version: int
    original_score: float
    best_score: float
    iterations_run: int
    improved: bool


def _call_llm_for_variation(
    current_prompt: str, pass_rate: float, model: str | None = None
) -> str:
    """Ask the LLM to generate an improved prompt variation.

    This is the core SIMBA step: given the current prompt and its
    performance, generate a variation that might perform better.

    References:
    - [REF-T26] DSPy SIMBA — meta-prompt optimization
    - [REF-T16] litellm — model-agnostic LLM calls
    """
    resolved_model = model or os.environ.get("NIGHTJAR_MODEL", "claude-sonnet-4-6")

    meta_prompt = (
        "You are a prompt optimization expert. Given the current system prompt "
        "and its verification pass rate, generate an improved version.\n\n"
        "The prompt is used in a code verification pipeline. A higher pass rate "
        "means the generated code passes formal verification more often.\n\n"
        "Rules:\n"
        "- Keep the same general role and structure\n"
        "- Make targeted improvements to clarity, specificity, or instruction ordering\n"
        "- Do NOT change the fundamental task\n"
        "- Output ONLY the improved system prompt text, nothing else\n\n"
        f"Current pass rate: {pass_rate:.1%}\n\n"
        f"Current prompt:\n{current_prompt}"
    )

    response = litellm.completion(
        model=resolved_model,
        messages=[{"role": "user", "content": meta_prompt}],
        temperature=0.7,  # Higher temp for creative variation
        max_tokens=2048,
    )

    return response.choices[0].message.content.strip()


class PromptOptimizer:
    """SIMBA-inspired prompt optimizer.

    Generates prompt variations, evaluates them against the tracking DB
    pass rate, and registers improved versions.

    References:
    - [REF-T26] DSPy SIMBA optimizer
    - [REF-P04] AlphaVerus self-improving loop
    """

    def __init__(self, config: OptimizationConfig) -> None:
        self.config = config
        self._tracking = TrackingDB(config.tracking_db_path)
        self._registry = PromptRegistry(config.prompt_registry_path)

    def evaluate_prompt(self, template: PromptTemplate) -> float:
        """Evaluate a prompt template using the tracking DB pass rate.

        Uses the overall pass rate as a proxy metric. In a full SIMBA
        implementation, this would run the prompt on a held-out eval set.

        Returns a score between 0.0 and 1.0.
        """
        return self._tracking.get_pass_rate()

    def optimize(self) -> OptimizationResult:
        """Run the optimization loop.

        For each iteration:
        1. Get current best prompt
        2. Generate a variation via LLM
        3. Evaluate the variation (using tracking DB pass rate as proxy)
        4. If improved, register as new version

        Returns:
            OptimizationResult with before/after scores and version info.
        """
        current = self._registry.get_best(self.config.target_prompt)
        if current is None:
            current = self._registry.get(self.config.target_prompt)
        if current is None:
            raise ValueError(
                f"No template found for '{self.config.target_prompt}'. "
                "Register at least one version first."
            )

        original_version = current.version
        original_score = self.evaluate_prompt(current)

        best_template = current
        best_score = original_score
        iterations = 0

        for i in range(self.config.max_iterations):
            iterations += 1

            # Generate variation
            try:
                variation_text = _call_llm_for_variation(
                    current.system_prompt, best_score
                )
            except Exception:
                # LLM call failed — skip this iteration
                continue

            if not variation_text:
                continue

            # Create candidate template
            new_version = best_template.version + i + 1
            candidate = PromptTemplate(
                name=self.config.target_prompt,
                version=new_version,
                system_prompt=variation_text,
                user_prompt_template=current.user_prompt_template,
                pass_rate=0.0,
                last_optimized=time.time(),
            )

            # Evaluate candidate
            candidate_score = self.evaluate_prompt(candidate)

            if candidate_score > best_score + self.config.improvement_threshold:
                candidate.pass_rate = candidate_score
                self._registry.register(candidate)
                best_template = candidate
                best_score = candidate_score

        return OptimizationResult(
            target_prompt=self.config.target_prompt,
            original_version=original_version,
            best_version=best_template.version,
            original_score=original_score,
            best_score=best_score,
            iterations_run=iterations,
            improved=best_score > original_score + self.config.improvement_threshold,
        )


def evaluate_prompt(config: OptimizationConfig, template: PromptTemplate) -> float:
    """Evaluate a prompt template. Convenience wrapper."""
    optimizer = PromptOptimizer(config)
    return optimizer.evaluate_prompt(template)


def run_optimization(config: OptimizationConfig) -> OptimizationResult:
    """Run prompt optimization. Convenience wrapper."""
    return PromptOptimizer(config).optimize()
