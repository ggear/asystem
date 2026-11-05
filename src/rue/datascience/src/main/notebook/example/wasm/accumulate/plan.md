# accumulate

The plan for the `example_wasm_accumulate` worked example. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `example` |
| **Model** | `wasm` |
| **Notebook** | `src/rue/datascience/src/main/notebook/example/wasm/accumulate/notebook.ipynb` |
| **Registered Model** | `example_wasm_accumulate` (`model.md` 6.1) |
| **Project Flavour** | `wasm` (`model.md` 3.2) |
| **Consumers** | A Python, a Rust and a Go host: `wasmtime`, `wasmi` and `wazero` |
| **Worked Example** | The reference for a `wasm` project (`plans/datascience.md` 4) |

**Status, 2026-11-03.** The notebook fits, builds, accepts, packages and replays the golden through the library runtime. Registering needs the MLflow server.

## Intent

Scale each input by a fitted gain, add a fitted offset and carry a running total and peak of the outputs as state, in a WebAssembly module with the gain and offset built in. The line and the state are one Python function, `accumulate(x, total, peak, gain, offset)`, which `workbench.wasm.trace` turns into the module (`model.md` 4.4). The data is a synthetic line with fixed noise, so every number is reproducible and nothing queries a database.

It is also the test of the tracer and the three hosts. Beside the line, the function returns 28 check outputs, each computed by one family of the tracer, so a fault in any of them fails the notebook:

| Family | Checks |
|---|---|
| Comparison and `select` | `band` (`<`, `>`), `band_inclusive` (`<=`, `>=`), `equal` and `unequal` (`eq`, `ne`), `bounded` (`clip`, so `minimum` and `maximum`) |
| Rounding and arithmetic | `floor`, `ceil`, `trunc` of the negated value, `nearest` on ties, `magnitude` (`sqrt`, `abs`, negation), `polynomial` (`**` by 2 and 3, written as multiplications) |
| Power | `power_const` (`**` by 1.5), `power_base` (`2.0 **` a value) and `power_unit` (`power`), all importing `pow` |
| Host maths | the thirteen one-argument functions of `model.md` 4.1, and `atan2`, each on the input scaled into 0 to 1 so `acos` and `asin` are in domain |
| State | two slots, `total` (a sum) and `peak` (`maximum`), so the state vector has more than one element and the features are `x`, `total` and `peak` |

The module imports all fifteen `asystem_math` functions, and `write_project` records them as `runtime.wasm` (`model.md` 3.5). Every host must provide each of them.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `example_wasm_in` | FP64 | The number to scale |
| Input | `example_wasm_state_in` | FP64 vector | The running total and peak from the previous call, optional |
| Output | `example_wasm_out` | FP64 | Gain times input plus offset |
| Output | `example_wasm_<check>` | FP64 | One per check above, in the order the function returns them |
| Output | `example_wasm_state_out` | FP64 vector | The previous total plus this output, and the larger of the previous peak and this output |

The module follows the ABI in `model.md` 4.1: it exports `memory` and `predict(x, n, y)`, reads the features as `n` rows of float64 at `x` and writes `n` rows of outputs at `y`.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `wasm_accumulate_training` | Ten labelled points at x 0 to 9 on the line 2.5x + 1 with fixed noise; the only data the fit sees (R6) |
| `validation` | `wasm_accumulate_validation` | Five more points at x 10 to 14 |
| `backtest` | `wasm_accumulate_backtest` | Ten further points at x 15 to 24, held back for acceptance |
| `golden` | `wasm_accumulate_golden` | Six calls from 1 to 14 and back to 2 that carry the total and peak, crossing both bounds and the tie values of `nearest`, then a request with the required input missing, which must give a signature error |

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `example_wasm_out`: the `rmse` on `validation` and on `backtest` must not exceed 0.5. The noise is about 0.03, so the budget is about 0.07. Each check output also has a gating `rmse` of at most 1e-9 against the plain Python call of the same function on `validation` and `backtest`, which is the differential test of the tracer.

The golden states a tolerance of 1e-9, absolute and relative, for the outputs that depend on a host maths function or a power. The rest, the line, the comparisons, the rounding, `sqrt` and the state, match exactly on every host.

## Parity

`python -m asystem.model replay` runs the golden through the Python runtime and compares every response exactly. The Rust and Go replays are in `src/may/mlflow/src/main/{rust,go}/modelreplay`, and the parity test runs all of them over this project.

## To do

1. None. An example is a fixture, tested by `fab unittest` and `fab systest` and never released.
