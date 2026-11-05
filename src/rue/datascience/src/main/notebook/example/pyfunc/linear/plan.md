# linear

The plan for the `example_pyfunc_linear` worked example. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `example` |
| **Model** | `pyfunc` |
| **Notebook** | `src/rue/datascience/src/main/notebook/example/pyfunc/linear/notebook.ipynb` |
| **Registered Model** | `example_pyfunc_linear` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | A Python runtime, `mlflow.pyfunc`. `pyfunc` is Python only, so there is no Rust or Go runtime |
| **Worked Example** | The reference for a `pyfunc` project (`plans/datascience.md` 4) |

**Status, 2026-11-03.** The notebook fits, builds, accepts, packages and replays the golden through the library runtime. Registering needs the MLflow server.

## Intent

Scale each input by a fitted gain and add a fitted offset, as an MLflow `PythonModel` in `model.py`. It is a hello world: the data is a synthetic line with fixed noise, so every number is reproducible and nothing queries a database.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `example_pyfunc_in` | FP64 | The number to scale |
| Output | `example_pyfunc_out` | FP64 | Gain times input plus offset |

`model.py` calls `set_model`. It imports `polars` beyond the base packages (`mlflow`, `numpy`, `pandas`), so the notebook declares `PYTHON_DEPS = ["polars"]` and the project records `runtime.python` (`model.md` 3.5). The `mlserver` image needs `polars` at the project wide pin before the served target can load it.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `pyfunc_linear_training` | Ten labelled points at x 0 to 9 on the line 2.5x + 1 with fixed noise; the only data the fit sees (R6) |
| `validation` | `pyfunc_linear_validation` | Five more points at x 10 to 14 |
| `backtest` | `pyfunc_linear_backtest` | Ten further points at x 15 to 24, held back for acceptance |
| `golden` | `pyfunc_linear_golden` | Six exactly representable inputs from -1 to 10, then a request with the input missing, which must give a signature error |

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `example_pyfunc_out`: the `rmse` on `validation` and on `backtest` must not exceed 0.5. The noise is about 0.03, so the budget is about 0.07.

## Parity

`python -m workbench.model replay` runs the golden through the Python runtime and compares every response exactly. The Rust and Go replays are in `src/may/mlflow/src/main/{rust,go}/modelreplay`, and the parity test runs all of them over this project.

## To do

1. None. An example is a fixture, tested by `fab unittest` and `fab systest` and never released.
