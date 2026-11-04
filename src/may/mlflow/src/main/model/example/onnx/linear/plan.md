# linear

The plan for the `example_onnx_linear` worked example. It follows `spec.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `example` |
| **Model** | `onnx` |
| **Notebook** | `src/may/mlflow/src/main/model/example/onnx/linear/notebook.ipynb` |
| **Registered Model** | `example_onnx_linear` (`spec.md` 6.1) |
| **Project Flavor** | `onnx` (`spec.md` 3.2) |
| **Consumers** | A Python runtime, `onnxruntime`. A Rust and a Go runtime are not built (`spec.md` 5.1) |
| **Worked Example** | The reference for a `onnx` project (`plans/mlflow.md` 4) |

**Status, 2026-11-03.** The notebook fits, builds, accepts, packages and replays the golden through the library runtime. Registering needs the MLflow server.

## Intent

Scale each input by a fitted gain and add a fitted offset, as an ONNX graph of a `Mul` and an `Add` at a pinned opset. It is a hello world: the data is a synthetic line with fixed noise, so every number is reproducible and nothing queries a database.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `example_onnx_in` | FP64 | The number to scale |
| Output | `example_onnx_out` | FP64 | Gain times input plus offset |

The graph is opset 21 at IR version 10, and its version is the metadata property `asystem.model_version`. The golden states an absolute tolerance of 1e-9 on `example_onnx_out`, to show the form a learned graph needs, though this graph's float64 arithmetic is exact.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `onnx_linear_training` | Ten labelled points at x 0 to 9 on the line 2.5x + 1 with fixed noise; the only data the fit sees (R6) |
| `validation` | `onnx_linear_validation` | Five more points at x 10 to 14 |
| `backtest` | `onnx_linear_backtest` | Ten further points at x 15 to 24, held back for acceptance |
| `golden` | `onnx_linear_golden` | Six exactly representable inputs from -1 to 10, then a request with the input missing, which must give a signature error |

## Acceptance

The notebook owns the limits (`spec.md` 6.8). Two gating checks on `example_onnx_out`: the `rmse` on `validation` and on `backtest` must not exceed 0.5. The noise is about 0.03, so the budget is about 0.07.

## Parity

`python -m asystem.model replay` runs the golden through the Python runtime and compares every response exactly. The Rust and Go replays are in `src/may/mlflow/src/main/{rust,go}/modelreplay`, and the parity test runs all of them over this project.

## To do

1. Register and promote against a live MLflow server (blocked on the server's allowed hosts, `plans/mlflow.md`).
