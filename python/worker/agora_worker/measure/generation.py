"""Generate a behaviour's scenarios with petri_bloom: understanding, then ideation.

petri_bloom runs in memory on a copy of the behaviour, so nothing is written to the
container's disk. Its model calls happen outside an Inspect eval, so their token
usage is read from Inspect's usage record for the current task.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inspect_ai.model import Model
from inspect_ai.model._model import init_model_usage, model_usage
from inspect_petri import judge_dimensions
from petri_bloom import Behavior
from petri_bloom._scenarios.scenarios import run_scenarios_async

from agora_core.measure.suites import presence_dimension, scenario_ids
from agora_core.synthetic import scan_text


class GeneratedContentError(RuntimeError):
    """The generated scenarios contain something that looks like real personal data."""


@dataclass
class GenerationOutcome:
    generated: Behavior
    usage: dict[str, dict[str, int]] = field(default_factory=dict)
    limit_reached: bool = False
    log_uri: str | None = None

    @property
    def tokens(self) -> int:
        return sum(u["input"] + u["output"] for u in self.usage.values())


def generated_texts(generated: Behavior) -> list[tuple[str, str]]:
    """Every piece of generated text, named for error messages."""
    texts = [
        ("understanding", generated.understanding or ""),
        ("scientific motivation", generated.scientific_motivation or ""),
    ]
    texts += [(f"scenario {s.name}", s.seed) for s in generated.scenarios or []]
    builtin = {dimension.name for dimension in judge_dimensions()}
    texts += [
        (f"dimension {d.name}", d.rubric or "")
        for d in generated.dimensions or []
        if d.name not in builtin  # Petri's own rubrics, added verbatim by petri_bloom
    ]
    for analysis in generated.transcript_analyses or []:
        texts.append(
            (f"analysis of {analysis.name}", f"{analysis.summary}\n{analysis.attribution}")
        )
    return texts


def check_synthetic(generated: Behavior) -> None:
    findings = [
        finding.describe()
        for name, text in generated_texts(generated)
        for finding in scan_text(text, check_names=False, path=name)
    ]
    if findings:
        raise GeneratedContentError(
            "the generated scenarios look like they contain real personal data: "
            + "; ".join(findings[:5])
        )


async def generate_scenarios(definition: Behavior, model: Model) -> GenerationOutcome:
    init_model_usage({})
    generated = await run_scenarios_async(definition, scenarios_model=model)
    usage = {
        name: {"input": u.input_tokens, "output": u.output_tokens}
        for name, u in model_usage().items()
    }
    presence_dimension(generated)
    if not scenario_ids(generated):
        raise RuntimeError("Bloom generated no scenarios")
    check_synthetic(generated)
    return GenerationOutcome(generated=generated, usage=usage)
