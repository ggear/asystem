# example / static / constant

The plan for the `example_static_constant` worked example. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `example` |
| **Model** | `static` |
| **Notebook** | `src/rue/datascience/src/main/notebook/example/static/constant/notebook.ipynb` |
| **Registered Model** | `example_static_constant` (`model.md` 6.1) |
| **Project Flavour** | `static` (`model.md` 3.2) |
| **Consumers** | A Python, a Rust and a Go loader |
| **Worked Example** | The constants flow (`plans/datascience.md` 4) |

**Status, 2026-11-03.** The notebook writes, verifies and replays the project through the Python, Rust and Go runners, and registers and pulls it back. No production consumer loads it yet.

## Intent

The smallest complete model: one constant, to prove the register and pull path end to end with no fitting. It is the reference for what a
project looks like, and the first of the worked examples, under the module `example`, whose models are `static`, `wasm`, `onnx` and `pyfunc`.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `example_static_in` | FP64 | Unused |
| Output | `example_static_out` | INT64 | A constant, 7 |

## Data

| Split | Dataset | Content |
|---|---|---|
| `golden` | `static_constant_golden` | The one input and expected output that becomes `golden.json` |

Every other split is unused.

## To do

1. A Rust and a Go loader that validate the project at load and replay the golden sequence (`model.md` R8). The Python replay is built (`python -m asystem.model replay`).
