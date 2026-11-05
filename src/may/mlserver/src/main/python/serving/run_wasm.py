import json
import math
import struct


def load_wasm(path, signature_json):
    import wasmtime

    fuel = 1_000_000
    memory_bytes = 1 << 20

    def math_function(name):
        function = getattr(math, name)

        def call(value):
            if name == "log" and value == 0.0:
                return -math.inf
            try:
                return function(value)
            except OverflowError:
                return math.inf
            except ValueError:
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
    for name in ("atan", "cos", "exp", "log", "sin", "tanh"):
        linker.define_func("asystem_math", name, wasmtime.FuncType([wasmtime.ValType.f64()], [wasmtime.ValType.f64()]), math_function(name))

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
