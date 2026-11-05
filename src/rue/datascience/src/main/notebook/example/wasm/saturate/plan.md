# saturate

The plan for the `example_wasm_saturate` worked example. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `example` |
| **Model** | `wasm` |
| **Notebook** | `src/rue/datascience/src/main/notebook/example/wasm/saturate/notebook.ipynb` |
| **Registered Model** | `example_wasm_saturate` (`model.md` 6.1) |
| **Project Flavour** | `wasm` (`model.md` 3.2) |
| **Consumers** | A Python, a Rust and a Go host: `wasmtime`, `wasmi` and `wazero` |
| **Worked Example** | The reference for a `wasm` project (`plans/datascience.md` 4) |

**Status, 2026-11-04.** The notebook fits, builds, accepts, packages and replays the golden through the library runtime. Registering needs the MLflow server.

## Intent

Squash each input through a fitted `tanh` curve, height times `tanh` of rate times input, in a module built by `workbench.wasm.build_wasm` with the height and rate built in. It is the worked example of a module that binds a host function: it imports `tanh` from `asystem_math` (`model.md` 4.1), so `write_project` records `runtime.wasm` as `["tanh"]` (3.5) and every host must provide `tanh`. The data is a synthetic curve with fixed noise, so every number is reproducible and nothing queries a database.

Each host calls its own `tanh`, so its result may differ in the last bits and the golden file states a tolerance for the output (`model.md` 4.2).

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `example_saturate_in` | FP64 | The number to squash |
| Output | `example_saturate_out` | FP64 | Height times `tanh` of rate times input |

The module follows the ABI in `model.md` 4.1: it exports `memory` and `predict(x, n, y)`, and imports only `asystem_math.tanh` as `(f64) -> f64`.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `wasm_saturate_training` | Ten labelled points at x -2.5 to 2 on the curve 4 tanh(0.5x) with fixed noise; the only data the fit sees (R6) |
| `validation` | `wasm_saturate_validation` | Five more points at x 2.5 to 4.5 |
| `backtest` | `wasm_saturate_backtest` | Ten further points at x 5 to 9.5, held back for acceptance |
| `golden` | `wasm_saturate_golden` | Seven inputs from -3 to 6 across both signs and the saturated tail, then a request with the input missing, which must give a signature error |

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `example_saturate_out`: the `rmse` on `validation` and on `backtest` must not exceed 0.5. The noise is about 0.03, so the budget is about 0.07.

## Parity

The golden tolerance is an absolute 1e-12. The Python, Rust and Go hosts replay the golden file, each with its own `tanh`, and the parity test runs all of them over this project.

## To do

1. None. An example is a fixture, tested by `fab unittest` and `fab systest` and never released.
