import pytest

from zerowall.review_audits import audit_result, evaluate_descriptor
from zerowall.review_calculations import calculation


def q(name, value, unit="1", kind="number"):
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "quantity_kind": kind,
        "basis": "Declared test input",
    }


def check(expression, quantities=(), **kwargs):
    return calculation(
        {"expression": expression, "quantities": list(quantities), **kwargs}
    )


def test_percentage_points_and_relative_change_have_distinct_denominators():
    inputs = [q("a", "93.3", "%", "fraction"), q("b", "86.8", "%", "fraction")]
    assert (
        check(
            "a-b",
            inputs,
            output_unit="pp",
            output_kind="percentage_points",
            expected_value="6.5",
        )["state"]
        == "pass"
    )
    assert (
        check("a-b", inputs, output_unit="pp", expected_value="0.7")["state"] == "fail"
    )
    assert (
        check("(a-b)/b", inputs, output_unit="%", expected_value="6.5")["state"]
        == "fail"
    )


def test_valid_calculation_does_not_certify_its_applicability():
    result = check(
        "1-cold/hot",
        [q("cold", "300", "K", "temperature"), q("hot", "6000", "K", "temperature")],
        expected_value="0.95",
    )
    assert result["state"] == "pass"
    assert "applicability" in result["limitations"]


def test_angle_and_index_are_not_conflated_by_dimensionlessness():
    inputs = [
        q("V", "2", "rad/(T*m)", "verdet"),
        q("B", "3", "T", "magnetic_field"),
        q("L", "4", "m", "length"),
    ]
    assert (
        check(
            "V*B*L", inputs, output_unit="rad", output_kind="angle", expected_value="24"
        )["state"]
        == "pass"
    )
    assert check("V*B*L", inputs, output_kind="index")["state"] == "fail"


def test_energy_power_and_binary_memory_units_are_distinct():
    assert (
        check(
            "e/t",
            [q("e", "60", "J", "energy"), q("t", "2", "s", "time")],
            output_unit="W",
            output_kind="power",
            expected_value="30",
        )["state"]
        == "pass"
    )
    assert (
        check("e+t", [q("e", "1", "J", "energy"), q("t", "1", "s", "time")])["state"]
        == "fail"
    )
    assert (
        check(
            "m",
            [q("m", "1", "MiB", "memory")],
            output_unit="MB",
            output_kind="memory",
            expected_value="1.048576",
        )["state"]
        == "pass"
    )


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').getcwd()",
        "a[0]",
        "(lambda: 1)()",
        "2**999999",
        "1e200",
        "[1]*999999",
        "x",
        "True",
    ],
)
def test_unsupported_or_oversized_expressions_are_unknown(expression):
    assert check(expression)["state"] == "unknown"


def test_declared_invalid_and_missing_values_are_scoped_results():
    assert check("1/0")["state"] == "fail"
    assert check("a", [q("a", None)])["state"] == "unknown"
    assert check("a", [q("a", "1", "unknown")])["state"] == "unknown"


def test_static_resource_is_not_invented_operating_consumption():
    result = evaluate_descriptor(
        {
            "kind": "resource",
            "boundary": "Declared device",
            "resources": [
                {
                    "name": "bias",
                    "direction": "static_requirement",
                    "value": "1",
                    "unit": "T",
                }
            ],
        },
        [],
    )
    assert result["state"] == "pass"
    assert "continuous" in result["limitations"]
    assert (
        evaluate_descriptor({"kind": "resource", "boundary": "", "resources": []}, [])[
            "state"
        ]
        == "incomplete"
    )


def test_citation_identity_is_not_source_retrieval_or_support():
    descriptor = {
        "kind": "citation",
        "claim_id": "C1",
        "claim_revision": 1,
        "reference": "A plausible DOI",
    }
    assert evaluate_descriptor(descriptor, [])["reason"] == "Source not checked"
    evidence = [
        {
            "id": "E1",
            "claim_id": "C1",
            "claim_revision": 1,
            "content": "A narrow supplied passage",
            "integrity": "pass",
        }
    ]
    assert evaluate_descriptor(descriptor, evidence)["state"] == "unknown"


def test_revision_change_invalidates_a_previous_numeric_check():
    descriptor = {
        "id": "A1",
        "kind": "calculation",
        "claim_id": "C1",
        "claim_revision": 1,
        "scope": "Arithmetic only",
        "expression": "2+2",
    }
    assert (
        audit_result(
            descriptor, {"claim_id": "C1", "revision": 1, "text": "2+2=4"}, []
        )["state"]
        == "pass"
    )
    assert (
        audit_result(
            descriptor, {"claim_id": "C1", "revision": 2, "text": "2+2=5"}, []
        )["state"]
        == "unknown"
    )


def test_declared_rounding_tolerance_is_not_a_false_contradiction():
    assert (
        check("1/3", expected_value="0.3333", absolute_tolerance="0.0001")["state"]
        == "pass"
    )
    assert (
        check("1/3", expected_value="0.3333", absolute_tolerance="-1")["state"]
        == "unknown"
    )
