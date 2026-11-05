import math

import wasmtime

from asystem.model import WASM_MATH_FUNCTIONS, WASM_MATH_MODULE

BINARY = {"add": "f64.add", "sub": "f64.sub", "mul": "f64.mul", "div": "f64.div", "min": "f64.min", "max": "f64.max"}
UNARY = {"neg": "f64.neg", "abs": "f64.abs", "sqrt": "f64.sqrt", "floor": "f64.floor", "ceil": "f64.ceil", "trunc": "f64.trunc", "nearest": "f64.nearest"}
COMPARE = {"lt": "f64.lt", "le": "f64.le", "gt": "f64.gt", "ge": "f64.ge", "eq": "f64.eq", "ne": "f64.ne"}


def build_wasm(features, outputs, lets=()):
    names = [name for name, _ in lets]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate let name in [{names}]")
    if features < 1 or not outputs:
        raise ValueError(f"a module needs features and outputs, got features [{features}] outputs [{len(outputs)}]")
    scope = []
    used = set()
    let_text = []
    for name, expression in lets:
        let_text.append(f"(local.set ${name} {_emit(expression, features, scope, used)})")
        scope.append(name)
    output_text = [f"(f64.store (i32.add (local.get $row_out) (i32.const {8 * index})) {_emit(expression, features, scope, used)})" for index, expression in enumerate(outputs)]
    declared = "".join(f"(local ${name} f64)" for name in names)
    imported = "\n  ".join(f'(import "{WASM_MATH_MODULE}" "{name}" (func $asystem_math_{name} (param f64) (result f64)))' for name in sorted(used))
    text = f"""
(module
  {imported}
  (memory (export "memory") 1)
  (func (export "predict") (param $x i32) (param $n i32) (param $y i32)
    (local $i i32)
    (local $row_in i32)
    (local $row_out i32)
    {declared}
    (block $done
      (loop $next
        (br_if $done (i32.ge_u (local.get $i) (local.get $n)))
        (local.set $row_in (i32.add (local.get $x) (i32.mul (local.get $i) (i32.const {8 * features}))))
        (local.set $row_out (i32.add (local.get $y) (i32.mul (local.get $i) (i32.const {8 * len(outputs)}))))
        {" ".join(let_text)}
        {" ".join(output_text)}
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $next)))))
"""
    return wasmtime.wat2wasm(text)


def const(value):
    return ("const", value)


def feature(index):
    return ("x", index)


def var(name):
    return ("var", name)


def add(left, right):
    return ("add", left, right)


def sub(left, right):
    return ("sub", left, right)


def mul(left, right):
    return ("mul", left, right)


def div(left, right):
    return ("div", left, right)


def minimum(left, right):
    return ("min", left, right)


def maximum(left, right):
    return ("max", left, right)


def neg(operand):
    return ("neg", operand)


def absolute(operand):
    return ("abs", operand)


def sqrt(operand):
    return ("sqrt", operand)


def floor(operand):
    return ("floor", operand)


def ceil(operand):
    return ("ceil", operand)


def trunc(operand):
    return ("trunc", operand)


def nearest(operand):
    return ("nearest", operand)


def lt(left, right):
    return ("lt", left, right)


def le(left, right):
    return ("le", left, right)


def gt(left, right):
    return ("gt", left, right)


def ge(left, right):
    return ("ge", left, right)


def eq(left, right):
    return ("eq", left, right)


def ne(left, right):
    return ("ne", left, right)


def atan(operand):
    return ("atan", operand)


def cos(operand):
    return ("cos", operand)


def exp(operand):
    return ("exp", operand)


def log(operand):
    return ("log", operand)


def sin(operand):
    return ("sin", operand)


def tanh(operand):
    return ("tanh", operand)


def select(condition, taken, otherwise):
    return ("select", condition, taken, otherwise)


def _emit(node, features, scope, used):
    kind = node[0]
    if kind == "const":
        if not math.isfinite(node[1]):
            raise ValueError(f"constant is not finite [{node[1]}]")
        return f"(f64.const {float(node[1])!r})"
    if kind == "x":
        if not 0 <= node[1] < features:
            raise ValueError(f"feature index out of range [{node[1]}] features [{features}]")
        return f"(f64.load (i32.add (local.get $row_in) (i32.const {8 * node[1]})))"
    if kind == "var":
        if node[1] not in scope:
            raise ValueError(f"unknown let [{node[1]}] in scope [{scope}]")
        return f"(local.get ${node[1]})"
    if kind in BINARY:
        return f"({BINARY[kind]} {_emit(node[1], features, scope, used)} {_emit(node[2], features, scope, used)})"
    if kind in WASM_MATH_FUNCTIONS:
        used.add(kind)
        return f"(call $asystem_math_{kind} {_emit(node[1], features, scope, used)})"
    if kind in UNARY:
        return f"({UNARY[kind]} {_emit(node[1], features, scope, used)})"
    if kind == "select":
        condition, taken, otherwise = node[1], node[2], node[3]
        if condition[0] not in COMPARE:
            raise ValueError(f"unknown comparison [{condition[0]}]")
        test = f"({COMPARE[condition[0]]} {_emit(condition[1], features, scope, used)} {_emit(condition[2], features, scope, used)})"
        return f"(select {_emit(taken, features, scope, used)} {_emit(otherwise, features, scope, used)} {test})"
    raise ValueError(f"unknown node [{kind}]")
