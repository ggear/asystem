# Data Science Delivery Plan

Status: 2026-11-04. The `mlmodels` module owns this plan and the specification. The rules are in `../doc/model.md`; this plan holds only what is done, what is not, the issues found and the
open decisions, and MUST NOT restate the specification. Each notebook's own plan sits beside it in
`src/rue/mlmodels/src/main/notebook/<module>/<model>/<notebook>/plan.md`.

## 1. Implemented

- The vocabulary is scikit-learn's, mapped onto MLServer's and MLflow's (`model.md` 4.1): a project has a flavour and a signature (`signature.json`,
  the V2 model metadata), and `workbench.model`, `workbench.notebook`, the notebooks, the plans and the committed rackmains default project use those
  words. The `wasm` flavour's module ABI is `predict(X) -> y`, with state carried as the `state_in` and `state_out` vectors.
- A workspace holds `notebook.ipynb`, `plan.md`, `data` and at most one model file (WS007), and `write_project` copies that file into the project
  and hashes it. Every non-`static` project names its `provenance.implementation` (PJ002).
- The checks of `model.md` section 10: `lint_project` and `verify_project` (PJ001 to PJ012), `workbench.notebook` (NB001 to NB010) and
  `workbench.workspace` (WS001 to WS007), with unit tests that plant each fault, run in `fab build`, and a test that fails when the
  specification and the code disagree on the identifiers, flavours, splits or sections.
- The helpers of `model.md` 10.2 in `workbench.model`, `workbench.notebook` and the `workbench` package, used by all the notebooks. `workbench` is one module per
  concern (`config`, `env`, `data`, `project`, `plot`) with an `__init__.py` that holds only the shared path, as `wrangle` is laid out.
- Notebooks carry no path block and no star import: `notebook.sh` installs the `asystem` kernel with the `PYTHONPATH`, and the IDE source roots
  provide it (NB011, NB012).
- `package_project`, which replaces the golden-to-steps loop in every Package cell, and `python -m workbench.model lint`, which prints every
  finding with its identifier.
- `python -m workbench.notebook new <module> <model> <notebook> <flavour>`, which scaffolds a notebook, a plan and the data directories that already pass
  `model.md` section 10.
- `python -m workbench.model generate`, which writes Rust request and response
  types from `signature.json` (rackmains' `contract.rs`). A Go generator was removed, since no Go consumer exists.
- Acceptance (`model.md` 6.8, R14): a notebook-defined `acceptance_checks` function run by `evaluate_acceptance`, which computes each check's outcome and budget from its value, limit and direction, writes `evaluation.json` into the project (AC001 to AC003, PM004), and has `register_project` log `acceptance_passed`, `acceptance_budget` and each measured value. `weewx/console/battery` uses it and records a failed verdict until a labelled `backtest` run exists.
- `register_project` registers a non-`pyfunc` project through `create_model_version` on the run's artifact path, since MLflow 3 refuses `register_model` for plain artifacts.
- `model.sh unittest` (R15), run by `fab unittest`: it runs every notebook whose inputs changed through Package, writes `project/` and `metadata.json`, and checks the metadata. `fab release` runs `check-release` on a consumer's embedded project and `model.sh release` for the workspaces.
- Version-free projects (`model.md` 3.4, R16): identity is the SHA-256 of `project.json`, the release version is a label in `metadata.json` and the registry tags, and the registry holds the aliases `preview` and `release`.
- A test that fails when the requirements and their checks (`model.md` 10.1 and 10.3) disagree.
- Notebook lint in `fab build`: `ruff` on the code cells, then `workbench.notebook` and `workbench.workspace` (`model.md` 6.7).
- The `mlflow` and `mlserver` modules, with the artifact mount removed, `--serve-artifacts`, allowed hosts, real health checks, `exec`
  with `pipefail` and a 30 s stop grace.
- `workbench.model` in `mlmodels` (write, verify, register, pull, and the command), with unit tests.
- The per-model layout, the data cache and its unit tests, and `notebook.sh`.
- The `mlserver` bootstrap pull into a local model directory.
- `src/max/rackmains/generate.sh` as the first consumer `generate.sh`, which embeds the released project (`model.md` 8.1).
- The rackmains project: the `static` project `rackmains_ups_battery`, built by the `rackmains/ups/battery` notebook from the guard thresholds with four golden steps, embedded into `src/max/rackmains/src/build/resources/model/` once released.
- Models, each in its own notebook directory under a module (`model.md` 6.1): `weewx/console/battery` (flavour `pyfunc`), `rackmains/ups/battery` (flavour
  `static` now, `wasm` for the fitted model) and `example/static/constant` (flavour `static`), and the placeholders `homeassistant/hotwater/temp`
  (flavour `wasm`) and `weewx/forecast/roof` (flavour `onnx`), each scaffolded with its plan.
- Worked examples for every flavour under the module `example` (`model.md` 6.9): `static/constant`, `wasm/accumulate`, `wasm/saturate` (binds the host `tanh`), `onnx/linear` and `pyfunc/linear`, each with a plan,
  data under every split, a passing acceptance check and a golden file. `onnx` stamping (`metadata_props`) and the `wasm` ABI (`memory`, `predict(x, n, y)`) are built, and
  `onnx`, `onnxruntime` and `wasmtime` are pinned in `py_deps_prod.txt`.
- Replay through the reference consumers: `python -m workbench.model replay` in process, and the Python, Go and Rust consumers under `src/main/python/consumer`, `src/main/go/consumer` and `src/main/rust/consumer`, each with a `run_` file per flavour.
- `src/max/rackmains/src/main/rust/rackmains/src/contract.rs` is generated from the embedded project's `signature.json` by `generate.sh`.
- The notebook libraries and `jupyterlab` live in `mlmodels`, not in the `mlflow` image.

## 2. Datasets

| Notebook | `training` | `validation` | `backtest` | `golden` | Registers |
|---|---|---|---|---|---|
| `weewx/console/battery` | `console_battery_voltage_2024-06-06_2024-10-25`, the 2024 run | `console_battery_voltage_2026-08-13_2026-10-30`, the 2026 run, used to check the fit | None | `console_battery_voltage_golden` | `weewx_console_battery`, a `coefficients` project, registered with `preview` once it has a `served` target |
| `example/static/constant` | None | None | None | `static_constant_golden` | `example_static_constant`, a `static` project, then pulls it back and compares |
| `rackmains/ups/battery` | None yet; discharges to the floor | None yet; a repeat at another load | None yet; the outage CSV files from `max` | `ups_battery_golden`, four rows | `rackmains_ups_battery`, the `static` default, embedded only, never registered |
| `homeassistant/hotwater/temp` | None yet | None yet | None yet | None yet | A placeholder |
| `weewx/forecast/roof` | None yet | None yet | None yet | None yet | A placeholder |

## 3. To do

In order. Each item is done when its worked example (4) runs and passes.

1. The first release, run by a person: release `mlserver`, then `mlmodels`, then read `model.sh status`. It registers every workspace that has a `served` target and publishes it.
2. A rehearsal of `fab systest` end to end, which sets `preview` in the production registry. Only the container runs of the consumers, the stub-server runs of `run_served` and the unit tests are done.
3. `weewx/console/battery` passes acceptance and can be served. Its arctan is now fitted to the 2024 training run and the 36 control points of the incumbent Home Assistant curve (a degree 3 `compensation`), the two sources weighted equally in total, and scored on the `backtest` run, the 2026 readings labelled by that curve, which is held out. The rmse is 4.04 against the limit of 5 (budget 0.81). It still reads up to 6 points above the incumbent between 3.80 and 3.88 V, which the Evaluate plots show. The check measures agreement with what runs today, not battery truth. Open: register and release it, which needs the `nginx` release (the proxy body limit) first.
4. The Rust loader in `rackmains`, copied from the Rust reference consumer's `run_` files, and the first release of `rackmains/ups/battery`, which `rackmains` embeds.
5. The `wasm` builder is built (`workbench.wasm.build_wasm`, section 7), with the maths imports of `model.md` 4.1 (thirteen one-argument functions and `atan2` and `pow`) and a tracing layer (`workbench.wasm.trace`, `model.md` 4.4) that turns an ordinary Python function into the tree. Built in the Python host (`workbench.replay`), the `run_wasm` files that `mlserver` carries, and the Go and Rust reference consumers. The Go (`wazero`) and Rust (`wasmi`) reference consumers provide them too. A test asserts the three hosts and `WASM_MATH_FUNCTIONS` list the same names and arities. To do: write the maths functions that matter in the module itself (`model.md` 4.5) where the host differences prove significant, which no builder does yet; move `weewx/console/battery` from `pyfunc` to `wasm` with `trace` and a golden tolerance on its arctan output; use the builder in `homeassistant/hotwater/temp`, the first project that needs it. The ABI (`model.md` 4.1) and the `wasmtime`, `wasmi` and `wazero` hosts are built, and `example/wasm/accumulate` and `example/wasm/saturate` are traced from Python functions (`model.md` 4.4).
6. The serving runtime in `mlserver`: built. Open: the `ProjectRuntime` serves one row per request, as the signature has no batch dimension, and gRPC is untested.
7. `register_project` logs a `pyfunc` project with `mlflow.pyfunc.log_model` (the project in `artifacts`, a column signature from `signature.json`) and every other flavour as plain artifacts. It refuses a `pyfunc` signature with a state vector, since MLflow's column signature has no vector. MLServer's MLflow runtime loading it is untested.
8. Existing experiments keep their pre-proxy artifact location, the laptop path of the share, so their artifacts are not reachable
   through `--serve-artifacts`; they are to be migrated or left read-only.

## 3a. Built

Built and tested as of 2026-11-04: the `mlserver` sync loop (poll, fall back, remember failures, unload, labels) with its own unit and system tests; the `mlflow` system test; `metadata.json`, targets, the inputs hash and the version-free project; `model.sh` (`unittest`, which skips a notebook whose inputs are unchanged, `systest`, `release`, `publish`, `status`); the reference consumers in Python, Go and Rust, one `run_` file per flavour and one entry point, `load`, built into one `Dockerfile` image and run for `static`, `wasm` and `onnx` in all three languages; `deploy.sh`; the fab hooks; the embed; and the `mlmodels` system test of the targets.

Decided on 2026-11-04 and not to be revisited without cause: no emulated second architecture (a second architecture is a `fab systest` on a host of that architecture); no static floor or second copy in a consumer; `mlmodels` uses the production `mlflow` and `mlserver` as `supervisor` uses `vernemq`; a breaking signature change is a new model name.

## 3b. The `mlmodels` module

The required behaviour is `model.md` section 11 and is not restated here. This section records what the module looks like and what was learned by testing the design against the repository and a live MLServer.

### Tree

`src/rue/mlmodels/`: no `.group`; `run_deps.txt` listing `mlflow`, `mlserver` and `influxdb3`; `deploy.sh`; `Dockerfile` with `docker_deps_base.txt` and `docker_deps_build.txt` (the reference consumers' test image, never released); `CLAUDE.md`; `src/main/python/{workbench,consumer}` and `py_deps.txt`; `src/main/{go,rust}/consumer`; `src/main/notebook/<module>/<model>/<notebook>/` (notebook, `plan.md`, `data/`, model file, `project/`, `metadata.json`); `src/build/resources/{model.sh,notebook.sh,doc,plans}`; `src/test/python/unit` and `src/test/python/system`. `mlflow` keeps its container files, `.env_all`, `.env_prod`, `generate.sh` and the nginx body-limit key, and has its own system test; the notebook libraries moved out of its image.

### Verified, and decisions the tests produced

- **MLServer 1.7.1, with the `serving` runtime and `parallel_workers` 0.** A directory added at runtime appears as `UNAVAILABLE`, `load` makes it `READY` and `infer` answers 200. `unload` and removing the directory takes it out of the index and `infer` returns 404. A reload in place, with the same or a new label, served 1,071 requests with no errors. A failed reload leaves the old model serving. So the loop needs no restart.
- **Fab.** A module with no `.group` reads as -1, sorts first and is skipped at install, but step 4 of `_release` still cleans, generates, builds and packages it, and a missing ssh is not an error. `_get_versions_next_release()` writes the root `.version`. From the repository root `fab deploy` runs `deploy.sh` only for modules with uncommitted changes, so a rollback is run in the module.
- **Gates raise.** Today a failed acceptance is only recorded and the notebook run still succeeds, and the Package cells use bare `assert`s, so a failure shows as a cell traceback with no stage. A `GateError` names the stage, gate and cause, so the unit and system test summaries say what failed and why.
- **Three test levels and no emulation.** `fab unittest` runs the notebooks with no container. `fab systest` runs the notebooks again if they are not current, pushes the previews to `mlflow` and `mlserver` in that order, waiting for each, then runs isolated local-architecture containers per declared target. Release changes tags. The emulated second architecture added minutes and could not show a CPU-specific result, and `wasm` is deterministic by its ABI, so it is retired. A second architecture is a `fab systest` on a host of that architecture.
- **The production registry and the production `mlserver` hold both aliases, and `mlmodels` uses them as production services, as `supervisor` uses `vernemq`.** `release` is served as `<name>` and `preview` as `<name>_preview`; `preview` is set only by the notebooks' register function and `release` only by the `mlmodels` release function, so the aliases say which models production consumers use and which only a system test may call. A served target is tested against `<name>_preview` on the production `mlserver`, because the project is under test, not `mlserver`, and no `mlserver` is started for a test. An embedded target needs an isolated runtime of its language, so it runs in a local reference consumer container. The `mlflow` and `mlserver` modules test themselves, in their own modules.
- **Reference consumers are the reference consumers.** The existing replay runners already do this for `static` and `wasm`; the plan cuts them to the load, verify, predict and replay a consumer needs, adds the `served` and Python reference consumers, and has the system test run them, so what the tests exercise is what a consumer is told to implement. `onnx` for Go and Rust is built.
- **No fab selection change.** Consumers embed at generate and `check-release` stops a stale release, as nginx pulls certificates at generate. `mlmodels` logs the stale consumers, and each is released by its own `fab release`. A selection hook can be added later if the log is not enough.
- **Publish at release and at deploy.** The release does it so nothing has to be remembered, as `install_pre.sh` does for discovery, and `deploy.sh` repeats it for a rollback, as `certificates.sh push` does. Both are the same idempotent function.
- **An unreachable `mlserver` does not block a release.** The registry is the source and the loop converges. A reachable `mlserver` that never shows the label fails the release, which also catches the first release before the loop exists.
- **A breaking signature change is a new model name.** That gates served clients, which cannot be compiled, as well as embedded ones.
- **`mlserver` release.** The container is recreated and its data directory is per version, so a release re-syncs every model before the server starts. This is the one interruption in the design. A registry that is down at that moment leaves nothing loaded; both services run on `may`, and `mlflow` releases first.
- **Examples** are fixtures: tested, never released. **Placeholder workspaces** have no project and are skipped. **The first release** registers every workspace that has a project.
- **Embedded-only projects never touch the registry.** Only a project with a `served` target is registered, previewed and released there; an embedded-only one is released by git alone, so `mlserver` is not loaded with models nobody calls. A consumer's `static` floor has no target and is never released.
- **`fab generate` runs no notebook.** It validates and embeds, which is cheap and runs in every build; `fab unittest` runs the notebooks and writes `project/` and the hashes, as a notebook always writes its model file, so the diff is read before a commit.
- **Accepted for now.** A revert needs `fab deploy` in the module; the stale log is the only prompt to release a consumer; a model with no usable version is logged and unserved.

### Open

- Whether to add the optional fab selection hook for stale consumers after living with the log.
- Whether `targets` should also be derived by discovery from the consumers' `default` slots, as `letsencrypt` discovers its consumers, once there is more than one.

## 4. Worked examples

Each flow below gets one runnable example that follows the spec end to end: a notebook directory under `src/main/notebook/<module>/<model>`, with its
plan and its data under splits, and a consumer for each environment it targets, with tests that run under `fab unittest`. An example is a complete
model and not a snippet, so it proves the spec by passing its own golden and replay tests.

| Flow | Flavour | Producer | Consumers | What It Proves |
|---|---|---|---|---|
| Constants end to end | `static` | `example/static/constant`, and the rackmains default model | Python loader, Rust loader (rackmains), Go loader | R1, R3, R8: the project layout, validation at load, the fallback floor |
| Stateless formula | `wasm` | A formula with an embedded consumer; none yet | Served, Python, Rust (`wasmi`), Go (`wazero`) | R2, R4, R5: one host ABI, identical golden results on every host and both architectures |
| Stateful model | `wasm` | `rackmains/ups/battery`: load integrated over time on battery into remaining seconds and percent; candidate `homeassistant/hotwater/temp` (4.1) | The rackmains guard in Rust (`wasmi`), served, Python | R3, R4, R8: carried state, replay of recorded outages, the `static` default as the floor |
| Learned model | `onnx` | `example/onnx/regression`: a scikit-learn regression; candidate `weewx/forecast/roof` (4.1) | Served (`onnxruntime`), Python, Rust (`ort`) | R4, R11: the converter, the pinned library and the same golden results across engines |
| Python-only model | `pyfunc` | `weewx/console/battery`: the arctan fit as `model.py`; a statsmodels-style `example/pyfunc/forecast` for a library with no converter | Served and Python, with a `static` floor | R2, R8: a served-only model and a consumer that survives losing it |
| Embedded release | Any | Any released model | A consumer `generate.sh` | R7: embed from the committed `project/`, verify on every build, a stale consumer is selected for release |
| Served sync | Any | Any released model | The `mlserver` sync loop | R7: poll the aliases, reload without a restart, fall back to the previous release |
| Promotion | Any | Any model | The registry | R5: `preview` to `release` only after the gates and `fab release` |
| Data splits and cache | Any | Any notebook | `query_influxdb3`, `data_path` | R6: one split per dataset, a re-query is a diff, `force` overwrites |
| Failure paths | Any | A deliberately bad project | Each consumer | R8, R9, R10: an invalid project is refused, a signature change fails the pull, every decision records the version and hash |

### 4.1 Candidate worked examples

Real projects with data in InfluxDB, checked on 2026-10-31. The history starts 2026-08-13, about 79 days from late winter to early summer, so
neither candidate can learn a seasonal effect. A candidate replaces the producer of one row of the table above when it is built; the row's
flow and what it proves stay the same.

| Candidate | Flow | Flavour | Replaces | Data Checked | Cautions |
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

## 5. Issues found while implementing the rackmains project

1. **A signature error had no representation in the golden.** A step now has a `response` or an `error` of `signature` (`model.md` 3.1).
2. **Nothing checked a `static` project against its signature.** Constants had to cover every required output, and every golden response had to equal them (PJ008, PJ012).
3. **Nothing checked the golden against the signature:** step inputs and outputs, required fields, an error step, a first call with no state (PJ010, PJ011).
4. **The registered name and the signature name could drift.** They are now checked (PJ004).
5. **Naming was a convention only.** Outputs now have to start with the module and end with their unit suffix (PJ007).
6. **A consumer's model is only as good as its first release.** With no default or floor, `rackmains` cannot build its contract until `rackmains/ups/battery` is released, and the Rust loader is not built.

## 6. Further tooling

1. Use the generated types in `rackmains` once its Rust loader is built, and generate the Go types into the first Go consumer.
2. A `fab systest` on a host of the other architecture, since the consumers run on the local architecture only. A learned `onnx` model needs a golden tolerance first, since the replay compares exactly, and the native ONNX Runtime library is pinned by version in `.env_fab` but not yet by hash per architecture (R11).
3. Scaffolds that run: the scaffold writes a runnable `static` notebook, and the other flavours a notebook that stops at Package until the fit
   is written.

## 7. Decisions and open decisions

Decided on 2026-11-04: the `wasm` builder is Python in `workbench` (`wasm.py`, `build_wasm`), and emits a compiled module per model, with the fitted values built in as constants. It writes WebAssembly text from a small expression tree (`const`, `x`, `var`, arithmetic, `min`, `max`, `select` on a comparison) and compiles it with `wasmtime.wat2wasm`, so it adds no toolchain. Only `model.wasm` ships; consumers never build. A second project that needs the same builder is the point to move it to `_`, and logic too large for an expression tree is the point to write a Rust crate. Added on 2026-11-05: a notebook MAY write the formula once as a Python function and trace it (`trace`, operators on symbolic values, `select`, `clip`), the same function serving `curve_fit`; the tree helpers take numbers and arrays as well, with numpy giving the IEEE result a host gives. Subexpressions are not shared and floor division is not traced.

Open:

- The tolerance for narrowing float64 where an engine lacks a kernel (`Atan` in `onnxruntime`), to be set when the first `onnx` graph is
  built.
