"""Small numerical capability: declared arithmetic and types, never arbitrary code."""

import ast
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext

CAPABILITY_VERSION = "council-calculation-v1"
LIMITS = {
    "expression_characters": 500,
    "nodes": 128,
    "depth": 16,
    "quantities": 8,
    "decimal_precision": 34,
    "power": 8,
    "absolute_magnitude": "1e100",
}

# A separate angle/index axis retains quantity distinctions that SI dimensions
# alone intentionally do not make. These are limited declared types, not a
# general derivation engine.
UNITS = {
    "1": ("1", {}),
    "%": ("0.01", {}),
    "pp": ("0.01", {}),
    "s": ("1", {"time": 1}),
    "ms": ("0.001", {"time": 1}),
    "min": ("60", {"time": 1}),
    "h": ("3600", {"time": 1}),
    "m": ("1", {"length": 1}),
    "cm": ("0.01", {"length": 1}),
    "kg": ("1", {"mass": 1}),
    "K": ("1", {"temperature": 1}),
    "J": ("1", {"energy": 1}),
    "W": ("1", {"energy": 1, "time": -1}),
    "kW": ("1000", {"energy": 1, "time": -1}),
    "B": ("1", {"bytes": 1}),
    "MB": ("1000000", {"bytes": 1}),
    "MiB": ("1048576", {"bytes": 1}),
    "GB": ("1000000000", {"bytes": 1}),
    "GiB": ("1073741824", {"bytes": 1}),
    "USD": ("1", {"money_USD": 1}),
    "rad": ("1", {"angle": 1}),
    "T": ("1", {"magnetic_field": 1}),
    "rad/(T*m)": ("1", {"angle": 1, "magnetic_field": -1, "length": -1}),
}
KIND_TYPES = {
    "angle": {"angle": 1},
    "index": {"index": 1},
    "energy": {"energy": 1},
    "power": {"energy": 1, "time": -1},
    "time": {"time": 1},
    "length": {"length": 1},
    "memory": {"bytes": 1},
    "money": {"money_USD": 1},
    "fraction": {},
    "percentage_points": {},
    "number": {},
    "temperature": {"temperature": 1},
    "magnetic_field": {"magnetic_field": 1},
    "verdet": {"angle": 1, "magnetic_field": -1, "length": -1},
}


class Unsupported(ValueError):
    pass


class Inconsistent(ValueError):
    pass


def decimal(value):
    if not isinstance(value, str) or len(value) > 80:
        raise Unsupported("A bounded decimal string is required")
    result = Decimal(value)
    if not result.is_finite() or abs(result) > Decimal("1e100"):
        raise Unsupported("The number exceeds the declared magnitude bound")
    if result and result.adjusted() < -100:
        raise Unsupported("The number exceeds the declared precision range")
    return result


def combine(left, right, sign=1):
    result = dict(left)
    for name, exponent in right.items():
        result[name] = result.get(name, 0) + sign * exponent
    return {k: v for k, v in result.items() if v}


@dataclass
class Value:
    number: Decimal
    dimensions: dict


def calculation(spec):
    """Return a scoped result; the caller supplies admitted source provenance."""
    base = {
        "capability_version": CAPABILITY_VERSION,
        "origin": "local_calculation",
        "scope": spec.get("scope", "Declared calculation"),
        "limitations": "Checks declared inputs, arithmetic and quantity types only; inputs, derivation and applicability are not independently verified.",
    }
    try:
        expression = spec.get("expression", "")
        if not expression or len(expression) > LIMITS["expression_characters"]:
            raise Unsupported("Missing or oversized expression")
        tree = ast.parse(expression, mode="eval")
        if len(list(ast.walk(tree))) > LIMITS["nodes"]:
            raise Unsupported("Expression exceeds the node bound")
        quantities = spec.get("quantities", [])
        if len(quantities) > LIMITS["quantities"]:
            raise Unsupported("Too many input quantities")
        values = {}
        for q in quantities:
            if q["name"] in values:
                raise Inconsistent("Duplicate quantity name")
            if q.get("value") is None:
                raise Unsupported("An input quantity is unknown")
            unit = q.get("unit", "1")
            kind = q.get("quantity_kind", "number")
            if unit not in UNITS or kind not in KIND_TYPES:
                raise Unsupported(
                    "Unit or quantity kind is outside the capability registry"
                )
            factor, dimensions = UNITS[unit]
            dimensions = dict(dimensions)
            if unit == "1" and kind in ("angle", "index"):
                dimensions = KIND_TYPES[kind]
            elif kind != "number" and dimensions != KIND_TYPES[kind]:
                raise Inconsistent("Input unit and declared quantity kind disagree")
            with localcontext() as input_context:
                input_context.prec = LIMITS["decimal_precision"]
                values[q["name"]] = Value(
                    decimal(q["value"]) * Decimal(factor), dimensions
                )

        def visit(node, depth=0):
            if depth > LIMITS["depth"]:
                raise Unsupported("Expression exceeds the depth bound")
            if isinstance(node, ast.Name) and node.id in values:
                return values[node.id]
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return Value(decimal(ast.get_source_segment(expression, node)), {})
            if isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.UAdd, ast.USub)
            ):
                item = visit(node.operand, depth + 1)
                return Value(
                    -item.number if isinstance(node.op, ast.USub) else item.number,
                    item.dimensions,
                )
            if not isinstance(node, ast.BinOp):
                raise Unsupported(
                    "Only declared names, constants and arithmetic are supported"
                )
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if left.dimensions != right.dimensions:
                    raise Inconsistent(
                        "Addition/subtraction combines incompatible units or quantity kinds"
                    )
                result = Value(
                    left.number + right.number
                    if isinstance(node.op, ast.Add)
                    else left.number - right.number,
                    left.dimensions,
                )
            elif isinstance(node.op, ast.Mult):
                result = Value(
                    left.number * right.number,
                    combine(left.dimensions, right.dimensions),
                )
            elif isinstance(node.op, ast.Div):
                if not right.number:
                    raise Inconsistent("Division by zero")
                result = Value(
                    left.number / right.number,
                    combine(left.dimensions, right.dimensions, -1),
                )
            elif isinstance(node.op, ast.Pow):
                if (
                    right.dimensions
                    or right.number != right.number.to_integral_value()
                    or abs(right.number) > LIMITS["power"]
                ):
                    raise Unsupported("Only bounded integer powers are supported")
                power = int(right.number)
                result = Value(
                    left.number**power,
                    {k: v * power for k, v in left.dimensions.items() if v * power},
                )
            else:
                raise Unsupported("Unsupported arithmetic operation")
            decimal(str(result.number))
            return result

        with localcontext() as context:
            context.prec = LIMITS["decimal_precision"]
            value = visit(tree.body)
            unit = spec.get("output_unit", "1")
            kind = spec.get("output_kind", "number")
            if unit not in UNITS or kind not in KIND_TYPES:
                raise Unsupported("Output unit or kind is unsupported")
            factor, dimensions = UNITS[unit]
            if unit == "1" and kind in ("angle", "index"):
                dimensions = KIND_TYPES[kind]
            if value.dimensions != dimensions or (
                kind != "number" and dimensions != KIND_TYPES[kind]
            ):
                raise Inconsistent(
                    "Calculated output disagrees with the declared unit or quantity kind"
                )
            result = value.number / Decimal(factor)
            expected = spec.get("expected_value")
            tolerance = decimal(spec.get("absolute_tolerance", "0"))
            if tolerance < 0:
                raise Unsupported("A tolerance cannot be negative")
            state = (
                "pass"
                if expected is None or abs(result - decimal(expected)) <= tolerance
                else "fail"
            )
            return {
                **base,
                "state": state,
                "value": format(result, "f"),
                "unit": unit,
                "absolute_tolerance": str(tolerance),
                "reason": "Declared calculation agrees"
                if state == "pass"
                else "Declared arithmetic result differs from the expected value",
            }
    except Inconsistent as exc:
        return {**base, "state": "fail", "reason": str(exc)}
    except (
        Unsupported,
        SyntaxError,
        InvalidOperation,
        ArithmeticError,
        RecursionError,
        ValueError,
    ) as exc:
        return {**base, "state": "unknown", "reason": str(exc)[:240]}
