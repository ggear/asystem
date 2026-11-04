# MLflow Model Delivery Plan

Status: 2026-10-31. The rules are in `../doc/spec.md`; this plan holds only what is done, what is not, the issues found and the
open decisions, and MUST NOT restate the specification. Each notebook's own plan sits beside it in
`src/may/mlflow/src/main/model/<module>/<model>/<notebook>/plan.md`.

## 1. Implemented

- The vocabulary is scikit-learn's, mapped onto MLServer's and MLflow's (`spec.md` 4.1): a project has a flavor and a signature (`signature.json`,
  the V2 model metadata), and `asystem.model`, `asystem.notebook`, the notebooks, the plans and the committed rackmains default project use those
  words. The `wasm` flavor's module ABI is `predict(X) -> y`, with state carried as the `state_in` and `state_out` vectors.
- A workspace holds `notebook.ipynb`, `plan.md`, `data` and at most one model file (WS007), and `write_project` copies that file into the project
  and hashes it. Every non-`static` project names its `provenance.implementation` (PJ002).
- The checks of `spec.md` section 10: `lint_project` and `verify_project` (PJ001 to PJ012), `asystem.notebook` (NB001 to NB010) and
  `asystem.workspace` (WS001 to WS007), with unit tests that plant each fault, run in `fab build`, and a test that fails when the
  specification and the code disagree on the identifiers, flavors, splits or sections.
- The helpers of `spec.md` 10.2 in `asystem.model`, `asystem.notebook` and the `library` package, used by all three notebooks. `library` is one module per
  concern (`config`, `env`, `data`, `project`, `plot`) with an `__init__.py` that holds only the shared path, as `wrangle` is laid out.
- Notebooks carry no path block and no star import: `notebook.sh` installs the `asystem` kernel with the `PYTHONPATH`, and the IDE source roots
  provide it (NB011, NB012).
- `package_project`, which replaces the golden-to-steps loop in every Package cell, and `python -m asystem.model lint`, which prints every
  finding with its identifier.
- `python -m asystem.notebook new <module> <model> <notebook> <flavor>`, which scaffolds a notebook, a plan and the data directories that already pass
  `spec.md` section 10.
- `diff_signature`, which a failed pull now reports, and `python -m asystem.model generate`, which writes Rust and Go request and response
  types from `signature.json`. The Rust output compiles and the Go output passes `go vet` and `gofmt`; neither is wired into a consumer yet.
- `check_gate` and `python -m asystem.model promote`, run by `src/main/resources/promote.sh`, which set the alias `release` only when a parity
  gate file passes for this project (R5).
- Acceptance (`spec.md` 6.8, R14): a notebook-defined `acceptance_checks` function run by `evaluate_acceptance`, which computes each check's outcome and budget from its value, limit and direction, writes `evaluation.json` into the project (AC001 to AC003, PM004), and has `register_project` log `acceptance_passed`, `acceptance_budget` and each measured value. `weewx/console/battery` uses it and records a failed verdict until a labelled `backtest` run exists.
- `register_project` registers a non-`pyfunc` project through `create_model_version` on the run's artifact path, since MLflow 3 refuses `register_model` for plain artifacts.
- `model.sh check` (R15), run by `fab release` and by `mlflow`'s `deploy.sh`: it runs every notebook through Package into `target/model-output`, compares each committed consumer `default` slot with `compare_project` (CP001 to CP003) and checks each `release` slot with `check_release`. `fab release` also runs `check_release` on a module's own `release` slot and cannot skip it with `FAB_SKIP_TESTS`. `deploy.sh` then runs `model.sh refresh`, which re-runs the `mlserver` bootstrap pull on the `may` host without pushing an image. `notebook.sh` stops before Register unless `REGISTER=1`, and `register_project` reuses a version for an unchanged project.
- Versions (`spec.md` 3.4, R16): the model version stamped into `model.py` and `wasm` modules, `.version` per workspace, `restamp_project`, the next number from the registered model's high-water mark and `m<N>` aliases, `promote_project` recording `service_version` from the latest release tag and writing the next `.version`, `resolve`, `list` and `status` commands, and `pull` printing the registry tags. MLflow reserves the alias form `v<N>`, hence `m<N>`.
- A test that fails when the requirements and their checks (`spec.md` 10.1 and 10.3) disagree.
- Notebook lint in `fab build`: `ruff` on the code cells, then `asystem.notebook` and `asystem.workspace` (`spec.md` 6.7).
- The `mlflow` and `mlserver` modules, with the artifact mount removed, `--serve-artifacts`, allowed hosts, real health checks, `exec`
  with `pipefail` and a 30 s stop grace.
- `asystem.model` in `_` (write, verify, register, pull, and the command), with unit tests.
- The per-model layout, the data cache and its unit tests, and `notebook.sh`.
- The `mlserver` bootstrap pull into a local model directory.
- `src/max/rackmains/generate.sh` as the first consumer `generate.sh`, with the `default` and `release` slots (`spec.md` 8.1).
- The rackmains default model: the `static` project `rackmains_ups_battery` `static-1`, built by the `rackmains/ups/battery` notebook from the guard
  thresholds and written to `src/max/rackmains/src/build/resources/model/default/`, with four golden steps and passing every check.
- Models, each in its own notebook directory under a module (`spec.md` 6.1): `weewx/console/battery` (flavor `pyfunc`), `rackmains/ups/battery` (flavor
  `static` now, `wasm` for the fitted model) and `example/static/constant` (flavor `static`), and the placeholders `homeassistant/hotwater/temp`
  (flavor `wasm`) and `weewx/forecast/roof` (flavor `onnx`), each scaffolded with its plan.
- Worked examples for every flavor under the module `example` (`spec.md` 6.9): `static/constant`, `wasm/accumulate`, `onnx/linear` and `pyfunc/linear`, each with a plan,
  data under every split, a passing acceptance check and a golden file. `onnx` stamping (`metadata_props`) and the `wasm` ABI (`memory`, `predict(x, n, y)`) are built, and
  `onnx`, `onnxruntime` and `wasmtime` are pinned in `py_deps_prod.txt`.
- Replay and the parity gate: `python -m asystem.model replay` and `gate` (Python, `wasmtime`, `onnxruntime`, `mlflow.pyfunc`), a Rust runner (`wasmi`) and a Go runner
  (`wazero`) under `src/test/replay`, and `model.sh parity`, run by `model.sh check`, which writes a gate file for every project the notebooks produce (the examples, `weewx/console/battery` and the `rackmains` default) for this machine's architecture and, with `SERVICE_LOCAL_RUNTIME=emulated` (the default), every other architecture in `.hosts` in a container, then merges them. The runners check file hashes too, and unit tests build them and replay a passing, an unsupported, a mismatched and a tampered project. A planted wrong
  golden value fails all three runtimes.
- `src/max/rackmains/src/main/rust/rackmains/src/contract.rs` is generated from the `default` slot's `signature.json` by `generate.sh`.
- `mlflow` has `influxdb3` as a run dependency for the notebooks' query, and the data libraries and `jupyterlab` are in its image.

## 2. Datasets

| Notebook | `training` | `validation` | `backtest` | `golden` | Registers |
|---|---|---|---|---|---|
| `weewx/console/battery` | `console_battery_voltage_2024-06-06_2024-10-25`, the 2024 run | `console_battery_voltage_2026-08-13_2026-10-30`, the 2026 run, used to check the fit | None | `console_battery_voltage_golden` | `weewx_console_battery`, a `coefficients` project, alias `candidate` |
| `example/static/constant` | None | None | None | `static_constant_golden` | `example_static_constant`, a `static` project, then pulls it back and compares |
| `rackmains/ups/battery` | None yet; discharges to the floor | None yet; a repeat at another load | None yet; the outage CSV files from `max` | `ups_battery_golden`, four rows | `rackmains_ups_battery`, the `static` default, alias `candidate` |
| `homeassistant/hotwater/temp` | None yet | None yet | None yet | None yet | A placeholder |
| `weewx/forecast/roof` | None yet | None yet | None yet | None yet | A placeholder |

## 3. To do

In order. Each item is done when its worked example (4) runs and passes.

1. Serve a model: the `mlserver` bootstrap already refuses a pulled model whose `evaluation.json` did not pass, but `mlserver` is a stub that prints its version and sleeps, with no `mlserver start`, model repository or settings. It needs per-model `model-settings.json` with `version` read from the `MODEL_VERSION` line, a real health check, `mlserver` depending on the bootstrap, and only `pyfunc` through MLServer's MLflow runtime. Serve `release` only, so the unversioned URL reaches it: MLServer sends an unversioned call to the highest loaded version.
2. Give a model its first passing acceptance. `weewx/console/battery` has a provisional `backtest` check and records a failed verdict, since: its `validation` run only falls to 55 % and rises again, so a time-normalised truth like the `training` run's is false, and no row can be set without a labelled run or a reference gauge. A bound set after seeing a measurement, with a `reason`, is provisional.
3. Worked examples for every flow in section 4, built first where they need nothing new and then alongside each feature below, so the code
   describes the spec and implements it.
4. A builder for the first `wasm` project that needs one. The ABI (`spec.md` 4.1), the `wasmtime`, `wasmi` and `wazero` hosts and the `wasmtime` pin are built, and `example/wasm/accumulate` is hand-written WebAssembly text.
5. The serving runtime in `mlserver`: `model-settings.json` generated from each pulled project's signature, a `ProjectRuntime` that verifies
   hashes at load and merges constants, `mlserver start` under `exec` once a model exists, and health checks on `/v2/health/live` and
   `/v2/health/ready`. Until then those checks are trivially true.
6. A pin for `skl2onnx`, added when a fitted `scikit-learn` model is converted.
7. `fab generate` in `mlflow`, `mlserver` and each consumer, so the generated `.env`, health scripts and compose inputs match.
8. `register_project` logs a `pyfunc` project with `mlflow.pyfunc.log_model` (the project in `artifacts`, a column signature from `signature.json`) and every other flavor as plain artifacts. It refuses a `pyfunc` signature with a state vector, since MLflow's column signature has no vector. MLServer's MLflow runtime loading it is untested.
9. Existing experiments keep their pre-proxy artifact location, the laptop path of the share, so their artifacts are not reachable
   through `--serve-artifacts`; they are to be migrated or left read-only.
10. A release of `mlflow`, since the running server predates the allowed-hosts setting.

## 4. Worked examples

Each flow below gets one runnable example that follows the spec end to end: a notebook directory under `src/main/model/<module>/<model>`, with its
plan and its data under splits, and a consumer for each environment it targets, with tests that run under `fab unittest`. An example is a complete
model and not a snippet, so it proves the spec by passing its own golden and replay tests.

| Flow | Flavor | Producer | Consumers | What It Proves |
|---|---|---|---|---|
| Constants end to end | `static` | `example/static/constant`, and the rackmains default model | Python loader, Rust loader (rackmains), Go loader | R1, R3, R8: the project layout, validation at load, the fallback floor |
| Stateless formula | `wasm` | A formula with an embedded consumer; none yet | Served, Python, Rust (`wasmi`), Go (`wazero`) | R2, R4, R5: one host ABI, identical golden results on every host and both architectures |
| Stateful model | `wasm` | `rackmains/ups/battery`: load integrated over time on battery into remaining seconds and percent; candidate `homeassistant/hotwater/temp` (4.1) | The rackmains guard in Rust (`wasmi`), served, Python | R3, R4, R8: carried state, replay of recorded outages, the `static` default as the floor |
| Learned model | `onnx` | `example/onnx/regression`: a scikit-learn regression; candidate `weewx/forecast/roof` (4.1) | Served (`onnxruntime`), Python, Rust (`ort`) | R4, R11: the converter, the pinned library and the same golden results across engines |
| Python-only model | `pyfunc` | `weewx/console/battery`: the arctan fit as `model.py`; a statsmodels-style `example/pyfunc/forecast` for a library with no converter | Served and Python, with a `static` floor | R2, R8: a served-only model and a consumer that survives losing it |
| Embedded pull | Any | Any registered model | A consumer `generate.sh` | R7: pull only on `fab pull`, commit the result, verify on every other build |
| Served pull | Any | Any registered model | `mlserver` bootstrap | R7: pull by alias at start, and do not start when a pull fails |
| Promotion | Any | Any registered model | The registry | R5: `candidate` to `release` only after review and the parity gate |
| Data splits and cache | Any | Any notebook | `query_influxdb3`, `data_path` | R6: one split per dataset, a re-query is a diff, `force` overwrites |
| Failure paths | Any | A deliberately bad project | Each consumer | R8, R9, R10: an invalid project is refused, a signature change fails the pull, every decision records the version and hash |

### 4.1 Candidate worked examples

Real projects with data in InfluxDB, checked on 2026-10-31. The history starts 2026-08-13, about 79 days from late winter to early summer, so
neither candidate can learn a seasonal effect. A candidate replaces the producer of one row of the table above when it is built; the row's
flow and what it proves stay the same.

| Candidate | Flow | Flavor | Replaces | Data Checked | Cautions |
|---|---|---|---|---|---|
| `homeassistant/hotwater/temp` (plan: `homeassistant/hotwater/temp/plan.md`) | Stateful model | `wasm` | `rackmains/ups/battery` in the Stateful model row | `compensation_sensor_landing_festoons_plug_temperature`: 137,618 readings, median 20 s apart and at most 7 h, 17.2 to 66.5 °C. `roof_max_solar_radiation`: 12,281 readings, 0 to 1,050. The booster's on and off commands from the `water_heating_turn_on_water_heater_booster` and `_turn_off_` automations | No flow meter, so a flow split has to be constructed or hand-annotated. The booster plug's own power sensor has 35 readings, all under 2 W, so it cannot be used for booster state. Solar is a radiation proxy only. The owning module is assumed to be `homeassistant` and is to be confirmed |
| `weewx/forecast/roof` (plan: `weewx/forecast/roof/plan.md`) | Learned model | `onnx` | `example/onnx/regression` in the Learned model row | `roof_temperature`: 19,690 readings, 6.4 to 30.8 °C. The Bureau forecasts `bom_darlington_temp_max_0` to `_7` and `_min_0` to `_7`, and `_later`: 22,488 readings each. `roof_max_solar_radiation`: 12,281 readings. `bom_darlington_temp`: 22,644 readings | About 79 days, so about 79 realised days per horizon, from one site. The Bureau's station is not on the roof. The owning module of the `roof_*` and `bom_*` entities is to be confirmed |

**Why `hotwater/temp` replaces the rackmains example.** The Stateful model row is meant to prove carried state, replay of recorded runs and the
`static` fallback. The rackmains fit is blocked on trial 5, a discharge to the knee, which does not exist yet, while `homeassistant/hotwater/temp` has 79 days of
data now and a real confounder. `rackmains` stays a project and the consumer of the Constants end to end row. It leaves the Stateful model row
only as the example.

**What `hotwater/temp` does.** The sensor is on the pipe leaving the hot water heater. The model tracks the pipe's temperature as a state machine,
carrying its state between calls:
- **Cooled:** no hot water has flowed for a while, the pipe cools toward ambient along a decay, and the reading is not the water temperature.
  The model reports the state and no water temperature.
- **Flowing:** hot water is flowing through the pipe, the reading follows the water, and the model reports the water temperature.
- **Heated, no flow:** the tank is being heated, by the booster or by solar, and the pipe warms by conduction without any flow. This state
  MUST NOT be reported as Flowing.

The confounder is visible in the data. On 2026-10-26 the pipe sat at 20.5 °C overnight and then rose steadily from 03:30 to about 45 °C by
05:25, about 0.2 °C per minute and 25 °C in two hours. That has the shape of the tank being heated and not of flow, though there is no flow
meter to confirm it. The booster's turn-on automation has 36 rows at each of 04:00 and 05:00 local and 42 at 15:00, and the pipe rises
again at 12:10 and from 14:50 on the same day. Rates between consecutive readings are mostly slow: about 86,000 of 137,600 are within 0.5 °C per
minute and 250 rise faster than 2 °C per minute, while 20,900 fall faster than 0.5 °C per minute, which a flow split has to explain.

Inputs the model takes are the pipe temperature, the clock, the solar radiation, the booster's last on or off command, and an ambient
temperature. State holds a smoothed temperature, a rate of change, the time since the last flow-like event and the last flowing
temperature. Outputs are a state code, a flow flag, a cooled flag and the water temperature while flowing. Names follow section 6.1, and the
unit suffix for degrees is `_celsius`.

**What `forecast/roof` does.** It predicts what the roof sensor will actually read from the Bureau of Meteorology forecast, by adjusting the
forecast up or down. The adjustment comes from the recent roof readings measured against the forecasts made for them, which captures the sensor's
calibration, and from local conditions such as solar radiation and wind. The recent error is carried as state, and the model is trained with
scikit-learn and converted with `skl2onnx`. It is the real replacement for the synthetic learned model, and runs served, in Python and in
Rust through `ort`.

## 5. Issues found while implementing the rackmains default

1. **One slot was not enough.** A pull replaces its target directory, so the consumer needs separate `default` and `release` slots. The
   specification now says so (`spec.md` 6.4, 8.1).
2. **A signature error had no representation in the golden.** A step now has a `response` or an `error` of `signature` (`spec.md` 3.1).
3. **The signature differs by `versions` between a default and a fitted project,** so equality of signatures had to ignore that list
   (`same_signature`, 3.1).
4. **Nothing checked a `static` project against its signature.** Constants had to cover every required output, and every golden
   response had to equal them (PJ008, PJ012).
5. **Nothing checked the golden against the signature:** step inputs and outputs, required fields, an error step, a first call with no
   state (PJ010, PJ011). The first two notebooks failed these and were corrected.
6. **The registered name and the signature name could drift.** They are now checked (PJ004).
7. **Naming was a convention only.** Outputs now have to start with the module and end with their unit suffix (PJ007).
8. **A notebook writes into another module's tree** when it writes a consumer's `default` slot. `consumer_project_dir` makes the path
   explicit, but the coupling remains.
9. **The default project is not yet in the image, and no Rust loader reads it.** The guard does not yet validate it at start.

## 6. Further tooling

1. Use the generated types in `rackmains` once its Rust loader is built, and generate the Go types into the first Go consumer.
2. A real-host run of the parity gate. `model.sh parity` covers both architectures, the second by emulation (`spec.md` 7.4), which cannot show a result that depends on the CPU. A learned `onnx` model needs a golden tolerance first, since the replay compares exactly, and the Rust `ort` and Go `onnxruntime_go` runtimes for `onnx` are not built. Native libraries are not yet pinned by hash per architecture (R11).
3. Scaffolds that run: the scaffold writes a runnable `static` notebook, and the other flavors a notebook that stops at Package until the fit
   is written.

## 7. Open decisions

- Where a `wasm` builder lives. The first project that needs one owns it, and a second project is the point to share it; the `_` module has no Rust today.
- Whether the first builder emits a compiled module per model or a shared interpreter with the graph in a data section.
- The tolerance for narrowing float64 where an engine lacks a kernel (`Atan` in `onnxruntime`), to be set when the first `onnx` graph is
  built.
