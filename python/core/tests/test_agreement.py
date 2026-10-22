import pytest

from agora_core.agreement import Trust, alpha, pairable_values, trust

# Krippendorff (2011), "Computing Krippendorff's alpha-reliability", the worked
# example with four observers, twelve units and missing values.
ROWS = {
    "A": [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None],
    "B": [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3],
    "C": [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None],
    "D": [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None],
}
DATA = {unit: {coder: values[unit] for coder, values in ROWS.items()} for unit in range(12)}


@pytest.mark.parametrize(
    ("metric", "expected"), [("nominal", 0.743), ("ordinal", 0.815), ("interval", 0.849)]
)
def test_matches_krippendorffs_worked_example(metric: str, expected: float) -> None:
    assert alpha(DATA, metric) == pytest.approx(expected, abs=0.001)  # type: ignore[arg-type]


def test_units_with_one_value_are_left_out() -> None:
    assert pairable_values(DATA) == 40  # unit 12 has a single value


def test_perfect_agreement_is_one_and_no_variation_is_undefined() -> None:
    assert alpha({1: {"a": 0, "b": 0}, 2: {"a": 3, "b": 3}}) == pytest.approx(1.0)
    assert alpha({1: {"a": 2, "b": 2}, 2: {"a": 2, "b": 2}}) is None
    assert alpha({1: {"a": 2}}) is None


def test_trust_thresholds() -> None:
    assert trust(0.81, 40) is Trust.trusted
    assert trust(0.8, 40) is Trust.trusted
    assert trust(0.7, 40) is Trust.provisional
    assert trust(0.667, 40) is Trust.provisional
    assert trust(0.5, 40) is Trust.retired
    assert trust(0.95, 4) is Trust.unrated
    assert trust(None, 100) is Trust.unrated
