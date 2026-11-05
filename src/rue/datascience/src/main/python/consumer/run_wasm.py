import json
import math
import struct


def load_wasm(path, signature_json):
    import wasmtime

    fuel = 1_000_000
    memory_bytes = 1 << 20

    def math_function(name):
        function = getattr(math, name)

        def call(*values):
            try:
                return function(*values)
            except OverflowError:
                if name == "pow":
                    return -math.inf if values[0] < 0 and values[1] % 2 == 1 else math.inf
                return math.copysign(math.inf, values[0]) if name == "sinh" else math.inf
            except ValueError:
                if name in ("log", "log2", "log10") and values[0] == 0.0:
                    return -math.inf
                if name == "pow" and values[0] == 0.0 and values[1] < 0:
                    return -math.inf if math.copysign(1.0, values[0]) < 0 and values[1] % 2 == 1 else math.inf
                return math.nan

        return call

    signature = json.loads(signature_json)
    state_in = [entry for entry in signature["inputs"] if entry["shape"] == [-1]]
    state_slots = len(signature["parameters"].get("state", []))
    scalars_in = [entry for entry in signature["inputs"] if entry["shape"] != [-1]]
    outputs = signature["outputs"]
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module.from_file(engine, path)
    linker = wasmtime.Linker(engine)
    arities = {"acos": 1, "asin": 1, "atan": 1, "atan2": 2, "cos": 1, "cosh": 1, "exp": 1, "log": 1, "log10": 1, "log2": 1, "pow": 2, "sin": 1, "sinh": 1, "tan": 1, "tanh": 1}
    for name, arity in arities.items():
        linker.define_func("asystem_math", name, wasmtime.FuncType([wasmtime.ValType.f64()] * arity, [wasmtime.ValType.f64()]), math_function(name))

    def predict(inputs):
        store = wasmtime.Store(engine)
        store.set_fuel(fuel)
        store.set_limits(memory_size=memory_bytes)
        instance = linker.instantiate(store, module)
        exports = instance.exports(store)
        memory = exports["memory"]
        function = exports["predict"]
        assert isinstance(memory, wasmtime.Memory) and isinstance(function, wasmtime.Func)
        row = [float(inputs[entry["name"]][0]) if entry["name"] in inputs else float("nan") for entry in scalars_in]
        for entry in state_in:
            row.extend(float(value) for value in inputs.get(entry["name"], [0.0] * state_slots))
        features = len(row)
        y_ptr = features * 8
        memory.write(store, struct.pack(f"<{features}d", *row), 0)
        function(store, 0, 1, y_ptr)
        width = sum(1 if entry["shape"] != [-1] else state_slots for entry in outputs)
        values = struct.unpack(f"<{width}d", memory.read(store, y_ptr, y_ptr + width * 8))
        result, position = {}, 0
        for entry in outputs:
            count = state_slots if entry["shape"] == [-1] else 1
            chunk = values[position : position + count]
            result[entry["name"]] = [int(value) for value in chunk] if entry["datatype"] == "INT64" else list(chunk)
            position += count
        return result

    return predict
