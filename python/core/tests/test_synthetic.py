import pytest

from bench_core.config import REPO_ROOT
from bench_core.synthetic import scan_text, scan_tree


def kinds(text: str, *, names: bool = True) -> list[str]:
    return [finding.kind for finding in scan_text(text, check_names=names)]


def test_reserved_emails_pass_and_real_ones_do_not() -> None:
    assert kinds("priya.sandford@example.test, x@demo.invalid") == []
    assert kinds("write to someone@gmail.com") == ["email address"]


@pytest.mark.parametrize(
    "number",
    ["0491 570 006", "0491570157", "(02) 5550 1234", "+61 491 570 156", "13 11 14", "1800 737 732"],
)
def test_fictional_and_public_numbers_pass(number: str) -> None:
    assert kinds(f"call {number}") == []


@pytest.mark.parametrize("number", ["0412 345 678", "+61 412 345 678", "(03) 9123 4567"])
def test_real_looking_numbers_are_flagged(number: str) -> None:
    assert "phone number" in kinds(f"call {number}")


def test_medicare_numbers_are_flagged_only_when_the_check_digit_is_valid() -> None:
    assert "Medicare number" in kinds("Medicare 2123 45670 1")
    assert "Medicare number" not in kinds("Medicare 2123 45679 1")


def test_long_identifiers_need_a_test_marker() -> None:
    assert kinds("member 87654321 joined") == ["identifier"]
    assert kinds("member TEST-87654321 joined") == []


def test_names_are_checked_for_imports_only() -> None:
    assert kinds("Spoke with Sarah Mitchell today") == ["person's name"]
    assert kinds("Spoke with Sarah Mitchell today", names=False) == []


def test_amounts_and_dates_are_not_identifiers() -> None:
    assert kinds("AUD 495.00 on 2026-09-30, claim CLM-TEST-5521") == []


def test_findings_are_masked() -> None:
    finding = scan_text("someone@gmail.com", check_names=False)[0]
    assert "someone@gmail.com" not in finding.describe()


def test_synthetic_content_in_git_has_no_personal_data() -> None:
    findings = scan_tree(REPO_ROOT, ["agents", "seeds", "config"])
    assert findings == [], "\n".join(finding.describe() for finding in findings)
