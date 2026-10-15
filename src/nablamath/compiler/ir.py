"""Backend-neutral SSA-like IR for NablaMath arithmetic expressions.

The IR is deliberately tiny: every instruction references only earlier instruction
IDs, common subexpressions are interned, and the complete program has a stable
content hash. Backends may execute the same program exactly (Python/Fraction)
or approximately (accelerators using floating-point arrays).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from typing import Mapping

from ..expression import Binary, Expr, Number, Symbol


@dataclass(frozen=True)
class Instruction:
    id: int
    op: str
    args: tuple[int, ...] = ()
    value: Fraction | str | None = None

    def to_data(self) -> dict[str, object]:
        value: object = self.value
        if isinstance(value, Fraction):
            value = {"numerator": value.numerator, "denominator": value.denominator}
        return {"id": self.id, "op": self.op, "args": list(self.args), "value": value}


@dataclass(frozen=True)
class Program:
    symbols: tuple[str, ...]
    instructions: tuple[Instruction, ...]
    output: int
    schema_version: int = 1

    def validate(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported IR schema")
        if (not isinstance(self.symbols, tuple)
                or any(not isinstance(name, str) or not name.isidentifier() for name in self.symbols)
                or tuple(sorted(set(self.symbols))) != self.symbols):
            raise ValueError("Symbols must be unique sorted identifiers")
        if not isinstance(self.instructions, tuple) or not 1 <= len(self.instructions) <= 10000:
            raise ValueError("IR requires 1..10000 instructions")
        for position, instruction in enumerate(self.instructions):
            if not isinstance(instruction, Instruction) or not isinstance(instruction.op, str):
                raise ValueError("Typed instruction with string opcode required")
            if type(instruction.id) is not int or instruction.id != position:
                raise ValueError("Instruction IDs must match execution order")
            if not isinstance(instruction.args, tuple) or any(type(arg) is not int for arg in instruction.args):
                raise ValueError("Instruction arguments must be integer IDs")
            if instruction.op == "number":
                if instruction.args or not isinstance(instruction.value, Fraction):
                    raise ValueError("IR number must be an exact Fraction")
            elif instruction.op == "symbol":
                if instruction.args or instruction.value not in self.symbols:
                    raise ValueError("IR symbol must be declared")
            elif instruction.op not in {"+", "-", "*", "/", "**"} or len(instruction.args) != 2 or instruction.value is not None:
                raise ValueError("Invalid arithmetic instruction")
            if any(arg >= position or arg < 0 for arg in instruction.args):
                raise ValueError("IR must be topologically ordered")
            if instruction.op == "**":
                exponent = self.instructions[instruction.args[1]]
                if (exponent.op != "number" or exponent.value.denominator != 1
                        or abs(exponent.value.numerator) > 1024):
                    raise ValueError("IR powers require a bounded literal integer exponent")
        if type(self.output) is not int or not 0 <= self.output < len(self.instructions):
            raise ValueError("Invalid IR output")

    @classmethod
    def from_data(cls, data: dict) -> "Program":
        """Decode the versioned, validated executable IR without eval or imports."""
        if not isinstance(data, dict) or set(data) != {"schema_version", "symbols", "instructions", "output"}:
            raise ValueError("Invalid IR manifest")
        if not isinstance(data["symbols"], list) or not isinstance(data["instructions"], list):
            raise ValueError("Invalid IR sequences")
        if len(data["instructions"]) > 10000:
            raise ValueError("IR instruction limit exceeded")
        instructions = []
        for row in data["instructions"]:
            if not isinstance(row, dict) or set(row) != {"id", "op", "args", "value"} or not isinstance(row["args"], list) or len(row["args"]) > 2 or not isinstance(row["op"], str):
                raise ValueError("Invalid IR instruction manifest")
            value = row["value"]
            if row["op"] == "number":
                if (not isinstance(value, dict) or set(value) != {"numerator", "denominator"}
                        or any(type(v) is not int or v.bit_length() > 4096 for v in value.values())
                        or value["denominator"] <= 0):
                    raise ValueError("Invalid exact IR literal")
                fraction = Fraction(value["numerator"], value["denominator"])
                if fraction.numerator != value["numerator"] or fraction.denominator != value["denominator"]:
                    raise ValueError("IR literal must be canonical")
                value = fraction
            instructions.append(Instruction(row["id"], row["op"], tuple(row["args"]), value))
        program = cls(tuple(data["symbols"]), tuple(instructions), data["output"], data["schema_version"])
        program.validate()
        return program

    def to_data(self) -> dict[str, object]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "symbols": list(self.symbols),
            "instructions": [instruction.to_data() for instruction in self.instructions],
            "output": self.output,
        }

    @property
    def content_id(self) -> str:
        canonical = json.dumps(self.to_data(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def lower_expr(expr: Expr) -> Program:
    """Lower an expression to deterministic topological IR with structural CSE."""
    symbols: set[str] = set()

    def collect(node: Expr) -> None:
        if isinstance(node, Symbol):
            symbols.add(node.name)
        elif isinstance(node, Binary):
            collect(node.left)
            collect(node.right)

    collect(expr)
    declared = tuple(sorted(symbols))
    memo: dict[Expr, int] = {}
    instructions: list[Instruction] = []

    def emit(node: Expr) -> int:
        existing = memo.get(node)
        if existing is not None:
            return existing
        if isinstance(node, Number):
            instruction = Instruction(len(instructions), "number", value=node.value)
        elif isinstance(node, Symbol):
            instruction = Instruction(len(instructions), "symbol", value=node.name)
        else:
            left = emit(node.left)
            right = emit(node.right)
            instruction = Instruction(len(instructions), node.op, (left, right))
        instructions.append(instruction)
        memo[node] = instruction.id
        return instruction.id

    output = emit(expr)
    program = Program(declared, tuple(instructions), output)
    program.validate()
    return program


def bind_symbols(program: Program, values: Mapping[str, object]) -> tuple[object, ...]:
    missing = [name for name in program.symbols if name not in values]
    extra = sorted(set(values) - set(program.symbols))
    if missing:
        raise ValueError("Símbolos sem valor: " + ", ".join(missing))
    if extra:
        raise ValueError("Símbolos desconhecidos: " + ", ".join(extra))
    return tuple(values[name] for name in program.symbols)


__all__ = ["Instruction", "Program", "lower_expr", "bind_symbols"]