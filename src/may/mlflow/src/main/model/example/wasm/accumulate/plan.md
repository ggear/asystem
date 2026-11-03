# accumulate

The plan for the `example_wasm_accumulate` worked example. It follows `spec.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `example` |
| **Model** | `wasm` |
| **Notebook** | `src/may/mlflow/src/main/model/example/wasm/accumulate/notebook.ipynb` |
| **Registered Model** | `example_wasm_accumulate` (`spec.md` 6.1) |
| **Project Flavor** | `wasm` (`spec.md` 3.2) |
| **Consumers** | A Python, a Rust and a Go host: `wasmtime`, `wasmi` and `wazero` |
| **Worked Example** | The reference for a `wasm` project (`plans/mlflow.md` 4) |

**Status, 2026-11-03.** The notebook fits, builds, accepts, packages and replays the golden through the library runtime. Registering needs the MLflow server.

## Intent

Scale each input by a fitted gain, add a fitted offset and carry a running total of the outputs as state, in a hand-written WebAssembly module with the gain and offset built in. It is a hello world: the data is a synthetic line with fixed noise, so every number is reproducible and nothing queries a database.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `example_wasm_in` | FP64 | The number to scale |
| Input | `example_wasm_state_in` | FP64 vector | The running total from the previous call, optional |
| Output | `example_wasm_out` | FP64 | Gain times input plus offset |
| Output | `example_wasm_state_out` | FP64 vector | The previous total plus this output |

The module follows the ABI in `spec.md` 4.1: it exports `memory` and `predict(x, n, y)`, reads the features as `n` rows of float64 at `x` and writes `n` rows of outputs at `y`.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `wasm_accumulate_training` | Ten labelled points at x 0 to 9 on the line 2.5x + 1 with fixed noise; the only data the fit sees (R6) |
| `validation` | `wasm_accumulate_validation` | Five more points at x 10 to 14 |
| `backtest` | `wasm_accumulate_backtest` | Ten further points at x 15 to 24, held back for acceptance |
| `golden` | `wasm_accumulate_golden` | Three calls that carry the total, then a request with the required input missing, which must give a signature error |

## Acceptance

The notebook owns the limits (`spec.md` 6.8). Two gating checks on `example_wasm_out`: the `rmse` on `validation` and on `backtest` must not exceed 0.5. The noise is about 0.03, so the budget is about 0.07.

## Parity

`python -m asystem.model replay` runs the golden through the Python runtime and compares every response exactly. The Rust and Go replays are in `src/may/mlflow/src/main/{rust,go}/modelreplay`, and the parity test runs all of them over this project.

## To do

1. Register and promote against a live MLflow server (blocked on the server's allowed hosts, `plans/mlflow.md`).
