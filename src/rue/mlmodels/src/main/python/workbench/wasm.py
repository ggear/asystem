import math
from numbers import Real

import numpy
import wasmtime

from workbench.model import WASM_MATH_FUNCTIONS, WASM_MATH_MODULE

BINARY = {"add": "f64.add", "sub": "f64.sub", "mul": "f64.mul", "div": "f64.div", "min": "f64.min", "max": "f64.max"}
UNARY = {"neg": "f64.neg", "abs": "f64.abs", "sqrt": "f64.sqrt", "floor": "f64.floor", "ceil": "f64.ceil", "trunc": "f64.trunc", "nearest": "f64.nearest"}
COMPARE = {"lt": "f64.lt", "le": "f64.le", "gt": "f64.gt", "ge": "f64.ge", "eq": "f64.eq", "ne": "f64.ne"}


def train_wasm_build(features, outputs, lets=()):
    names = [name for name, _ in lets]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate let name in [{names}]")
    outputs = [_node(expression) for expression in outputs]
    lets = [(name, _node(expression)) for name, expression in lets]
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
    imported = "\n  ".join(f'(import "{WASM_MATH_MODULE}" "{name}" (func $asystem_math_{name} (param{" f64" * WASM_MATH_FUNCTIONS[name]}) (result f64)))' for name in sorted(used))
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


class Sym:
    __array_ufunc__ = None

    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return f"Sym({self.node!r})"

    def __bool__(self):
        raise TypeError("an expression has no truth value, use select(condition, taken, otherwise)")

    def __add__(self, other):
        return add(self, other)

    def __radd__(self, other):
        return add(other, self)

    def __sub__(self, other):
        return sub(self, other)

    def __rsub__(self, other):
        return sub(other, self)

    def __mul__(self, other):
        return mul(self, other)

    def __rmul__(self, other):
        return mul(other, self)

    def __truediv__(self, other):
        return div(self, other)

    def __rtruediv__(self, other):
        return div(other, self)

    def __neg__(self):
        return neg(self)

    def __abs__(self):
        return absolute(self)

    def __pow__(self, other):
        if isinstance(other, int | float) and float(other).is_integer() and 2 <= other <= 8:
            result = self
            for _ in range(int(other) - 1):
                result = mul(result, self)
            return result
        return power(self, other)

    def __rpow__(self, other):
        return power(other, self)

    def __lt__(self, other):
        return lt(self, other)

    def __le__(self, other):
        return le(self, other)

    def __gt__(self, other):
        return gt(self, other)

    def __ge__(self, other):
        return ge(self, other)


def train_wasm_trace(function, features):
    result = function(*[feature(index) for index in range(features)])
    outputs = list(result) if isinstance(result, list | tuple) else [result]
    return [Sym(_node(output)) for output in outputs]


def const(value):
    return Sym(("const", value))


def feature(index):
    return Sym(("x", index))


def var(name):
    return Sym(("var", name))


def add(left, right):
    return _apply("add", numpy.add, left, right)


def sub(left, right):
    return _apply("sub", numpy.subtract, left, right)


def mul(left, right):
    return _apply("mul", numpy.multiply, left, right)


def div(left, right):
    return _apply("div", numpy.divide, left, right)


def minimum(left, right):
    return _apply("min", numpy.minimum, left, right)


def maximum(left, right):
    return _apply("max", numpy.maximum, left, right)


def clip(operand, low, high):
    return minimum(maximum(operand, low), high)


def neg(operand):
    return _apply("neg", numpy.negative, operand)


def absolute(operand):
    return _apply("abs", numpy.abs, operand)


def sqrt(operand):
    return _apply("sqrt", numpy.sqrt, operand)


def floor(operand):
    return _apply("floor", numpy.floor, operand)


def ceil(operand):
    return _apply("ceil", numpy.ceil, operand)


def trunc(operand):
    return _apply("trunc", numpy.trunc, operand)


def nearest(operand):
    return _apply("nearest", numpy.rint, operand)


def lt(left, right):
    return _compare("lt", numpy.less, left, right)


def le(left, right):
    return _compare("le", numpy.less_equal, left, right)


def gt(left, right):
    return _compare("gt", numpy.greater, left, right)


def ge(left, right):
    return _compare("ge", numpy.greater_equal, left, right)


def eq(left, right):
    return _compare("eq", numpy.equal, left, right)


def ne(left, right):
    return _compare("ne", numpy.not_equal, left, right)


def acos(operand):
    return _apply("acos", numpy.arccos, operand)


def asin(operand):
    return _apply("asin", numpy.arcsin, operand)


def atan(operand):
    return _apply("atan", numpy.arctan, operand)


def atan2(left, right):
    return _apply("atan2", numpy.arctan2, left, right)


def cos(operand):
    return _apply("cos", numpy.cos, operand)


def cosh(operand):
    return _apply("cosh", numpy.cosh, operand)


def exp(operand):
    return _apply("exp", numpy.exp, operand)


def log(operand):
    return _apply("log", numpy.log, operand)


def log10(operand):
    return _apply("log10", numpy.log10, operand)


def log2(operand):
    return _apply("log2", numpy.log2, operand)


def power(left, right):
    return _apply("pow", numpy.power, left, right)


def sin(operand):
    return _apply("sin", numpy.sin, operand)


def sinh(operand):
    return _apply("sinh", numpy.sinh, operand)


def tan(operand):
    return _apply("tan", numpy.tan, operand)


def tanh(operand):
    return _apply("tanh", numpy.tanh, operand)


def select(condition, taken, otherwise):
    if _is_node(condition):
        return Sym(("select", _node(condition), _node(taken), _node(otherwise)))
    result = numpy.where(condition, numpy.asarray(taken, dtype=float), numpy.asarray(otherwise, dtype=float))
    return float(result) if result.ndim == 0 else result


def _apply(kind, function, *operands):
    if any(_is_node(operand) for operand in operands):
        return Sym((kind, *[_node(operand) for operand in operands]))
    with numpy.errstate(all="ignore"):
        result = function(*[numpy.asarray(operand, dtype=float) for operand in operands])
    return float(result) if result.ndim == 0 else result


def _compare(kind, function, left, right):
    if _is_node(left) or _is_node(right):
        return Sym((kind, _node(left), _node(right)))
    result = function(numpy.asarray(left, dtype=float), numpy.asarray(right, dtype=float))
    return bool(result) if result.ndim == 0 else result


def _is_node(value):
    return isinstance(value, Sym | tuple)


def _node(value):
    if isinstance(value, Sym):
        return value.node
    if isinstance(value, tuple):
        return value
    if isinstance(value, Real):
        return ("const", float(value))
    raise TypeError(f"not a number or an expression [{type(value).__name__}]")


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
        if len(node) - 1 != WASM_MATH_FUNCTIONS[kind]:
            raise ValueError(f"maths function [{kind}] takes [{WASM_MATH_FUNCTIONS[kind]}] arguments, got [{len(node) - 1}]")
        used.add(kind)
        return f"(call $asystem_math_{kind} {' '.join(_emit(child, features, scope, used) for child in node[1:])})"
    if kind in UNARY:
        return f"({UNARY[kind]} {_emit(node[1], features, scope, used)})"
    if kind == "select":
        condition, taken, otherwise = node[1], node[2], node[3]
        if condition[0] not in COMPARE:
            raise ValueError(f"unknown comparison [{condition[0]}]")
        test = f"({COMPARE[condition[0]]} {_emit(condition[1], features, scope, used)} {_emit(condition[2], features, scope, used)})"
        return f"(select {_emit(taken, features, scope, used)} {_emit(otherwise, features, scope, used)} {test})"
    raise ValueError(f"unknown node [{kind}]")
