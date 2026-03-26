"""AutoResearch hill climbing for pipeline optimization.

Karpathy's AutoResearch pattern: each run tries ONE variation
(prompt tweak, temperature change, different few-shot selection).
Measures verification pass rate. Keeps if improved, discards if not.
Tracks all experiments in history for analysis.

References:
- [REF-P04] AlphaVerus — self-improving loop architecture
- [REF-T26] DSPy — prompt variation strategies
- [REF-C02] Closed-loop verification — feedback drives improvement
"""

import random
import time
from dataclasses import dataclass, field

from nightjar.tracking import TrackingDB
from nightjar.prompts import PromptTemplate, PromptRegistry


VARIATION_KINDS = ("prompt_tweak", "temperature", "few_shot")

# Prompt tweak strategies — small targeted changes
TWEAK_STRATEGIES = [
    ("Add emphasis on edge cases", "Consider ALL edge cases and boundary conditions. "),
    ("Add emphasis on precision", "Be extremely precise and specific in your analysis. "),
    ("Add step-by-step instruction", "Work through the problem step by step. "),
    ("Add verification focus", "Focus on properties that can be formally verified. "),
    ("Add conciseness instruction", "Be concise — only include what is necessary. "),
    ("Reorder priorities", "Prioritize correctness over completeness. "),
]

# Temperature options to explore
TEMPERATURE_OPTIONS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4]


@dataclass
class Variation:
    """A single experimental variation.

    References:
    - [REF-P04] AlphaVerus — variation strategies
    """

    kind: str  # "prompt_tweak", "temperature", "few_shot"
    description: str
    parameter_name: str
    original_value: str
    new_value: str


@dataclass
class HillClimbConfig:
    """Configuration for hill climbing.

    References:
    - [REF-T26] DSPy SIMBA optimization config
    """

    tracking_db_path: str
    prompt_registry_path: str
    target_prompt: str  # e.g. "analyst", "formalizer", "coder"


@dataclass
class HillClimbResult:
    """Result from a single hill climb step.

    References:
    - [REF-P04] AlphaVerus — experiment result tracking
    """

    variation: Variation
    original_score: float
    new_score: float
    accepted: bool
    timestamp: float = field(default_factory=time.time)


class HillClimber:
    """AutoResearch hill climbing optimizer.

    Each step() call:
    1. Generates ONE random variation
    2. Evaluates current vs. varied configuration
    3. Accepts if improved, discards if not
    4. Records result in history

    References:
    - [REF-P04] AlphaVerus self-improving loop
    - [REF-T26] DSPy — optimization patterns
    """

    def __init__(self, config: HillClimbConfig) -> None:
        self.config = config
        self._tracking = TrackingDB(config.tracking_db_path)
        self._registry = PromptRegistry(config.prompt_registry_path)
        self.history: list[HillClimbResult] = []

    def generate_variation(self, template: PromptTemplate) -> Variation:
        """Generate a single random variation of the template.

        Picks one of: prompt tweak, temperature change, or few-shot selection.
        Only ONE change per step — this is the AutoResearch principle.
        """
        kind = random.choice(VARIATION_KINDS)

        if kind == "prompt_tweak":
            strategy_desc, prefix = random.choice(TWEAK_STRATEGIES)
            return Variation(
                kind="prompt_tweak",
                description=strategy_desc,
                parameter_name="system_prompt",
                original_value=template.system_prompt[:50] + "...",
                new_value=(prefix + template.system_prompt)[:50] + "...",
            )

        elif kind == "temperature":
            current_temp = 0.2  # Default generation temperature
            new_temp = random.choice(
                [t for t in TEMPERATURE_OPTIONS if t != current_temp]
            )
            return Variation(
                kind="temperature",
                description=f"Changed temperature from {current_temp} to {new_temp}",
                parameter_name="temperature",
                original_value=str(current_temp),
                new_value=str(new_temp),
            )

        else:  # few_shot
            return Variation(
                kind="few_shot",
                description="Changed few-shot example selection strategy",
                parameter_name="few_shot_k",
                original_value="3",
                new_value=str(random.choice([1, 2, 5, 7])),
            )

    def evaluate(self, template: PromptTemplate) -> float:
        """Evaluate a template using the tracking DB pass rate as proxy.

        In production, this would run the template on a held-out eval set.
        For MVP, we use the overall tracking DB pass rate.
        """
        return self._tracking.get_pass_rate()

    def step(self) -> HillClimbResult:
        """Run one hill climbing step.

        1. Load current best template
        2. Generate one variation
        3. Evaluate both
        4. Accept if improved
        """
        current = self._registry.get_best(self.config.target_prompt)
        if current is None:
            current = self._registry.get(self.config.target_prompt)
        if current is None:
            raise ValueError(
                f"No template found for '{self.config.target_prompt}'."
            )

        variation = self.generate_variation(current)
        original_score = self.evaluate(current)

        # Apply variation to get candidate
        if variation.kind == "prompt_tweak":
            _, prefix = random.choice(TWEAK_STRATEGIES)
            candidate = PromptTemplate(
                name=current.name,
                version=current.version + len(self.history) + 1,
                system_prompt=prefix + current.system_prompt,
                user_prompt_template=current.user_prompt_template,
                pass_rate=0.0,
                last_optimized=time.time(),
            )
        else:
            # For temperature/few_shot, the template itself doesn't change
            # but we track the experiment for the optimizer to learn from
            candidate = current

        new_score = self.evaluate(candidate)
        accepted = new_score > original_score

        if accepted and variation.kind == "prompt_tweak":
            candidate.pass_rate = new_score
            self._registry.register(candidate)

        result = HillClimbResult(
            variation=variation,
            original_score=original_score,
            new_score=new_score,
            accepted=accepted,
        )
        self.history.append(result)
        return result


def generate_variation(
    config: HillClimbConfig, template: PromptTemplate
) -> Variation:
    """Generate a variation. Convenience wrapper."""
    return HillClimber(config).generate_variation(template)


def run_hill_climb(
    config: HillClimbConfig, steps: int = 10
) -> list[HillClimbResult]:
    """Run multiple hill climbing steps. Convenience wrapper."""
    climber = HillClimber(config)
    results = []
    for _ in range(steps):
        results.append(climber.step())
    return results
