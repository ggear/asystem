# Library Refactor Plan

Status: 2026-11-10, built through phase 8 and `fab test-unit` green, with the deviations of section 11. System verification is recorded at the end of section 11. The sections above are the design as written and the code follows it except where section 11 says otherwise. This plan is distinct from `mlmodels.md`, which holds what is built and open today. The rules stay in `../doc/model.md` until a phase changes
them, and the changes the spec needs are listed in section 9 and made phase by phase, never ahead of the code. The worked notebook is `homeassistant/weatherstation/battery`.

## 1. Goals

- The notebook holds the logic. The mlmodels is a small public API of stage-prefixed functions, in lifecycle order, with the spec codified behind it.
- The file system holds the bare minimum that repeatability needs: the data runs, the defined models, the one promoted project and the release state.
- A name a source publishes flows unaltered through every section: source, dataset, notebook, signature, model, evaluation.
- Several models live in one workspace, each with an id, each evaluated through the same runtime code that serves it.
- Less mlmodels, less spec, fewer checks, with no loss of repeatability or readability.

## 2. The pipeline

```
Setup → Collect → Prepare → Explore → Train → Define → Evaluate → Package → Register
                                         │        │         │          │
                                  pure python   models    models     one model
                                  informs Define by id    by id      promoted to project/
```

| Stage | Function | What it does |
|---|---|---|
| Setup | `setup_workspace(path)` | Reads the signature and prints the workspace: signature names, the run table and the model table. It no longer takes a target. |
| Collect | `collect_run(ws, run=1000, label=..., live=False, ...)` | Captures a run into `data/<run>/`. `label` is required, as the readable intent of the run. |
| Prepare | `prepare_split`, `prepare_folds`, `prepare_plot` | Unchanged. |
| Explore | `explore_plot` | Plots on `ws.training` and the other splits directly, with real names. |
| Train | Plain Python | Fits and explores in pure Python, on real feature names, and informs what Define freezes. It calls no mlmodels function that writes. |
| Define | `define_model(ws, model=1000, flavour, source, label=, ...)` | Freezes a model into `ws.models[id]` and writes `model/<id>/`. |
| Evaluate | `evaluate_model`, `evaluate_metrics`, `evaluate_gate`, `evaluate_models`, `evaluate_plot` | Scores each model through the runtime loader (5.1). |
| Package | `package_model(ws, model, golden=, target=)` | Promotes one model to the committed `project/`. |
| Register | `register_model(ws, model)` | Registers that model with the alias `preview`. |
| Pull | `pull_model(ws, model)` | Pulls the registered model back and compares it, where a round trip is tested. |

**Define** is the stage name because every other stage is a verb, and `Model` would be the one noun, too generic beside Evaluate and Package. `define_model` reads beside `collect_run` and
`evaluate_model`.

`define_model`:
- `model` is an integer id from 1000, unique in the notebook, and numbers a model as `run` numbers a run. Both are keyword-only at the call, so a bare `1000` is never ambiguous.
- `source` is the string form of the model: Python text for `pyfunc`, JSON for `static`, a Python function for `wasm` that `define_model` traces, and bytes for `onnx`.
- `label` is free text saying what the model is, shown in the model table.
- It loads the written file through the same `load_<flavour>` of `mlmodels.runtime` that the consumers use, checks the model's real outputs against `signature.json`, and raises a `GateError` on a mismatch.
- `constants` is a dict of the fitted values, written into the model file as module-level names. A Train function reads notebook globals (`fit_arctan_coefficients`), so its text alone is not
  a model. `define_model` parses `source` with `ast` and raises a `GateError` when the function uses a free name that is not a constant, an import or a builtin. The `wasm` tracer takes the same
  `constants`.
- The runs the model was fitted on are taken from `ws.training`, or from `runs=` where a model is fitted per fold or on another selection. The package's `runtime.python` is read from the imports of `source`, so `PYTHON_DEPS` goes.

Each model's evaluation is kept on `ws.models[id]`, and `package_model` raises a `GateError` when the candidate has no `evaluate_gate` result.

`evaluate_model` returns predictions named by the signature's outputs, next to any incumbent columns, and the metrics the notebook's checks compute. A signature with `state` is
replayed in time order with the state carried by the mlmodels. A failing model prints and continues. Only the Package of the chosen candidate raises on a failed gate.

`package_model` writes `project/` from model `<id>`: the model file, the signature, a golden file and an evaluation. `golden=` takes only an input frame, and the expected outputs come
from running the model. The frame has an `expect` column of `ok` or `error`, outputs being computed for `ok` rows and the model's refusal checked for `error` rows, and an optional `sequence`
column naming each sequence, with state reset where its value changes and rows kept in order within it. `project.json` records the `model` id the project came from. `trained_on`, `notes`, `implementation`, `source` and `sequence` are derived from the model's own record and no longer passed.

## 3. Runs and models on disk

```
notebook.ipynb
signature.json
metadata.json                         schema, version, content_sha256, inputs_sha256, target, release
py_deps.txt                           the Python names fab pull merges, when the target is python
data/<run>/<dataset>.csv + .json      inputs, committed, frozen unless live
model/<id>/<model file> + model.json  outputs, committed, rewritten by every execution
project/                              the promoted candidate, as today
```

**Runs.** An id is an integer of 1000 or more, unique in the notebook and never reused. Gaps are allowed, since a retired run is deleted, so an id names a run and does not count them. The json records a free-text `label` and `"live"`. A run is frozen unless its `collect_run` call gives `live=True`, and any run MAY be live whatever
its number, so liveness no longer follows run order. A live run is recaptured on every execution, MAY be given only to `monitoring`, and is frozen by removing the argument. There is no `force`:
a frozen run is refreshed on purpose by deleting its csv and json and running the notebook, then reading the git diff. A run that must keep up with its source is `live`. A live run is excluded from `inputs_sha256`, since it can reach only `monitoring` and so cannot change a model, and otherwise
`metadata.json` would change on every execution. A notebook with a live run needs its source reachable wherever it runs, as the spec already accepts for a run kept live today.

**Models.** An id follows the same rule as a run's: 1000 or more, unique, never reused, gaps allowed. `model.json` holds `schema`, `model`, `label`, `flavour`, the runs it was fitted on and the SHA-256 of the model file. Unlike a run, a model is
written by every execution and not read if present, since a fit is cheap and a query is not. The git diff is the review of a refit, and R15 (a re-run reproduces the hashes) is the
reproducibility check. A model directory the notebook did not define in a run is a `GateError`, so a retired model is retired by deleting it. `define_model` does not compare `source`
with the committed file, because a float-level difference in a fit would then block every run.

**Why the two are alike and unlike.** Both are keyed by an integer from 1000, labelled, hashed in a json beside the data and retired by deletion. A run is an input the notebook reads when
present. A model is an output the notebook always writes. The candidate's model file is in both `model/<id>/` and `project/`, byte-identical and checked equal, since `project/` is self
contained for consumers to embed and is git-ignored in the personal-data workspaces.

**Dropped.** A model file beside the notebook (`model.py`, `model.wasm`, `model.onnx`), `PYTHON_DEPS`, the hand-built `golden_samples()` dict, and `cargo_deps.txt` and `go_deps.txt`, which
only the MD005 equality check reads, since `requirements()` already derives the same names and compares them with the consumer's `Cargo.toml` and `go.mod`.

**Kept.** `target` stays in `metadata.json`, set by `package_model(target=)`, and so does `py_deps.txt`. `fab pull` (`model_py_deps` in `fabfile.py`) reads both, and the personal-data
workspaces git-ignore `project/`, so a checkout without it would otherwise merge a different `.py_deps.txt`. `metadata.json` is the document that stays committed when `project/` is ignored
(spec 6.5), and `project.json` stays free of the target, so a change of target does not change the project's hash.

## 4. Names flow unaltered

Section 6.1 of the spec already requires a dataset column, a query, a signature input and a signature output to carry a source name unchanged. The battery notebook breaks it by renaming to
`Timestamp`, `Voltage` and `Capacity`. The rule to state is that a name flows through every section unaltered, that feature engineering MAY add columns, named under 6.1, and that it MUST NOT
rename one. A labelled training column carries the output's name.

Checked by tools:
- `.rename(` in a notebook code cell is a finding.
- Every signature input is a column of every run, and every signature output is a column of a run that is labelled.
- `define_model` fails when the model's real outputs differ from the signature.

Left to the spec, as too fuzzy to lint: that every string literal in a code cell belongs to the workspace's vocabulary.

## 5. The public API and the layout

```
mlmodels/
  __init__.py  __main__.py
  setup.py  collect.py  prepare.py  explore.py  define.py  evaluate.py  package.py  register.py  pull.py  maths.py
  _workspace.py  _project.py  _signature.py  _registry.py  _release.py  _wasm.py  _document.py  _lint.py  ...
runtime/    <flavour>.py  __main__.py
```

- The eight stage modules (Train has no public function, since it is plain Python) hold only the `<stage>_<what>` functions a notebook calls. Everything else is a `_`-prefixed module, the convention of `wrangle` (`_sources`, `_state`, `_logs`). Review holds the
  boundary, and `ruff`'s private-import rule can flag a `_` import from outside `mlmodels`. There is no third package.
- `mlmodels/__init__.py` re-exports the public functions. The runtime stays lazy so `mlflow` is not imported at the top, and an `if TYPE_CHECKING:` block of explicit imports lets the IDE follow them,
  which the `MLMODELS_API` string map does not.
- One command, `python -m mlmodels <command>`, replaces `mlmodels.model`, `mlmodels.notebook`, `mlmodels.workspace` and `mlmodels.runner`. Callers to change: `model.sh`, `notebook.sh`,
  rackmains' `generate.sh`, `fabfile.py` and the system tests.
- `runtime`, which was `consumer`, keeps its role: it runs models for the notebook, and is the copy-and-paste example for a consumer of a downloaded model. `mlserver`'s `generate.sh` copies its flavour files, and
  the regeneration MUST be byte-identical after the cleanup. `load_pyfunc` patches MLflow's `color_warning` with `unittest.mock` only to silence a warning. Replace it with a logging or warnings
  filter, after checking what is emitted, so the consumer needs no `mock`.

### 5.1 The public functions

Grammar: the first token is the stage, as its notebook section is named; the second is the object it acts on, from a closed set reused across stages (`workspace`, `run`, `split`, `folds`, `model`,
`models`, `plot`, `metrics`, `gate`); there is no third token, so a variant is an argument. Singular acts on one object and plural on all. The arguments run `ws`, then the id, then keywords only. The two functions that are pure over data take it and no `ws`: `explore_plot(frame, x, y, ...)` and `evaluate_metrics(truth, predicted)`.

| Stage | Function | Does | Replaces |
|---|---|---|---|
| Setup | `setup_workspace(path)` | Reads the signature and prints the workspace, the run table and the model table | `setup_workspace`, without `target` |
| Collect | `collect_run(ws, run, label, live, ...)` | Captures or reads one run | `collect_run`, without `force` |
| Prepare | `prepare_split(ws, ...)` | Forms the splits in memory | same |
| Prepare | `prepare_folds(ws, ...)` | Forms the cross-validation folds | same |
| Prepare | `prepare_plot(ws, ...)` | Plots the splits | same |
| Explore | `explore_plot(frame, x, y, ...)` | Plots a frame on real feature names | `explore_plot` |
| Define | `define_model(ws, model, flavour, source, label, constants, runs)` | Freezes a model by id and writes `model/<id>/` | new; absorbs `train_wasm_build` and `train_wasm_trace` |
| Evaluate | `evaluate_model(ws, model, split)` | Predicts through the runtime loader | `evaluate_predict` |
| Evaluate | `evaluate_metrics(truth, predicted)` | Computes rmse, mae, bias and the rest; a pure function | `evaluate_measure` |
| Evaluate | `evaluate_gate(ws, model, checks)` | Runs a model's acceptance checks and records the outcome | `evaluate_check` |
| Evaluate | `evaluate_models(ws)` | Prints one table across every defined model | new |
| Evaluate | `evaluate_plot(ws, models, split)` | One figure: truth and each model's predictions above, each model's error and the gate's limit below, sharing the x axis | `evaluate_curves`, `evaluate_error_plot` |
| Package | `package_model(ws, model, golden, target)` | Promotes one model to `project/` | `package_workspace` |
| Register | `register_model(ws, model)` | Registers it with the alias `preview` | `register_workspace` |
| Pull | `pull_model(ws, model)` | Pulls it back and compares, for a round trip | spec 6.7.9; not exported today |

- That is sixteen functions and `GateError`. Only Evaluate has an explicit gate function; every other stage raises `GateError` itself, from `prepare_split`, `define_model` and the rest.
- `evaluate_plot` has no mode. The limit on its lower panel is taken from the model's `evaluate_gate` result in `ws`, and is left out for a model with no gate yet.
- `mlmodels.maths` (`select`, `clip`, `tanh` and the other operators) is the one module outside the stage prefix. It is the vocabulary a traced `wasm` function body uses, not a workflow call. The
  expression-tree builders of `wasm.py` become private.
- `ws` members (`ws.inputs`, `ws.outputs`, `ws.training`, `ws.run(id)`, `ws.models[id]`) are data and not calls.

**Requirements of the interface.** These are design rules held by the layout and by review. None gets a test of its own: a test of names, imports or file shape asserts structure and not behaviour.
- **Public means stage-prefixed.** The public set of `mlmodels` is exactly the functions named `<stage>_<what>`, for a stage of section 2, plus `GateError`. `mlmodels/__init__.py` lists them in
  lifecycle order, as `fabfile.py` lists its tasks, so the file reads as the workflow.
- **One module per stage.** `setup.py`, `collect.py` and so on hold only that stage's public functions, in the order a notebook calls them. A stage module imports `_` modules and never another
  stage module. This is the answer to a single large library: one file per stage keeps each readable, and the ordered `__init__` gives the single entry point.
- **Followable from the IDE.** A notebook's `from mlmodels import define_model` MUST resolve by go-to-definition in IntelliJ, which the lazy `MLMODELS_API` map does not. The `TYPE_CHECKING`
  imports provide it, and the `pyright` run of the build already fails on an unresolved name.
- **Private is unreachable from a notebook.** A `_` module is not imported outside `mlmodels` or by a notebook. Docs, errors, linting and the codified spec live there, so the notebook sees
  none of them except through a stage function.
- **Streamlined calls.** A stage function takes `ws` first, except the two pure functions of 5.1, then at most the arguments of its own decision, all keyword-only after the id. A function needing more than six arguments is split or
  derives them (the twelve of `package_workspace` is the example). Nothing a notebook passes can be derived from `signature.json`, the runs or the model.
- **Every failure names its stage.** An error a stage function raises is a `GateError` of the stage, the gate and the cause, with every interpolated value in square brackets, so the cell traceback
  says what to fix.
- **A stage function prints what it did.** One summary, a table for runs and models, and no more, so the executed notebook reads as the record and a rerun is comparable by eye.
- **The name `mlmodels` stays.** A rename touches every `PYTHONPATH` caller and every notebook import for no gain, and `from mlmodels import ...` reads as the notebook's toolkit.

## 6. The battery notebook

Runs, with the old number in brackets:

| Run | Content |
|---|---|
| 1000, 1001, 1002 | The 2024 shape (1), the 2026 labelled discharge (2) and the hand built capture (3) |
| 1004 | The fresh discharge from the highest voltage after the battery replacement, `live=True`, with a query selecting from that voltage |
| 1003 | The old run 4, queried from its start (2026-11-08) to now so the replacement voltage jump is captured, frozen |

Notebook changes:
- Drop the `data_*_pl` aliases and use `ws.training` and `ws.validation`. Drop every rename. Explore uses `time` and the real feature names, with its plots collapsed.
- Train holds the pure-Python fits, one function per variant that Evaluate scores today. Define turns each into a model by id, and Evaluate compares them with `evaluate_models`.
- Package selects the fixed-width arctan with the plateau shelf. The title cell's Data and Future text is rewritten for the new runs.
- The incumbent column keeps its source name, `template_weatherstation_console_battery_capacity_pct`.

## 7. Ergonomics

- A `label` on every run and model, shown by `setup_workspace` (a run table with `run`, `label`, the `time` span, rows, `live` and each column's min, max and nulls) and by `evaluate_models`
  (a model table with id, label, flavour, hash and verdict).
- Plot cells carry collapsed-output metadata, set by the scaffold and checked by lint. IntelliJ honouring it is not yet confirmed.
- The five arguments dropped from `package_workspace` are the gain: the call states a model id and a golden input frame.
- A pyfunc helper builds the `PythonModel` class from a pure function, taking the input and output names from the signature, so a notebook carries no template and its names cannot drift from `signature.json`. It is part of Define (`define_model` accepts the function's source for `pyfunc`), and an explicit full `model.py` text is still accepted.

## 8. Build order

Each phase leaves `fab unittest` green. It changes, in the same step, the spec section it affects, `mlmodels.md` and the module `CLAUDE.md`, and it migrates every notebook mechanically to
the new names and layout (the renames touch `setup_workspace` in 19 notebooks, `package_workspace` in 15 and `register_workspace` in 12), so no shim is left for the review pass to delete. Phase 6
is then only the substantive rewrite of the battery notebook and the labels.

1. **Runs.** Renumber to 1000, add `label` and `live`, drop `force`, exclude live runs from `inputs_sha256`, add the run summary and migrate the sidecars. Spec: 3.1, 6.2, 6.3, 6.5, 6.6, 6.7.2, 10.1 (WS005, WS008).
2. **Layout.** Split `model.py` and `stage.py` into the public stages and the `_` modules, add the single command and fix its callers, and resolve the duplicate `record_project`. Spec: 10.2,
   11.1.
3. **Define and Evaluate.** `define_model` with `constants`, `evaluate_model`, `evaluate_models`, `ws.models`, `model/<id>/` and the orphan check, the notebook lint and `notebook.sh new` scaffold for the new section list (Define for every flavour, and what it means for `static`), and a check that two `pyfunc` models loaded in one process do not interfere through MLflow's single `__mlflow_model__` slot. Spec: new 6.7 Define, 6.7.5, 6.7.6, 7.1, 6.2, 6.4.
4. **Package, Register and metadata.** Take a model id, set `target` from `package_model`, derive provenance and `runtime`, and stop writing `cargo_deps.txt` and `go_deps.txt` (with MD005 reduced to the Python file). Spec: 3.1, 3.5, 6.7.7, 6.7.8, 11.2.
5. **Lint and tests.** Add the names checks, remove the checks that can no longer fail, and prove each new rule fails when it is removed. Test only logic: a gate, a decision rule, a parser or a state rule, through its caller's boundary. No test asserts names, imports, file layout or a message. Spec: 6.1, 10.1, 10.3.
6. **Notebooks.** The battery notebook rewritten as section 6 says, a hand-written `label` for every existing run (from the notebook's Data bullets), and a check that every other notebook reads as the spec now describes.
7. **Consumer cleanup.** Remove `mock`, and check the `mlserver` copies regenerate byte-identically.
8. **Review pass, aggressive.** The ten passes of the repo `CLAUDE.md` *Code review and refactoring*, over the whole of `mlmodels` as it stands after phases 1 to 7, in the order given, and fixing what
   is found. Aggressive means:
   - Correctness first, reading the logic and not the tests: state crossing a process or notebook run, half-finished runs, a run interrupted between writing a csv and its json, a model directory left
     by a failed `define_model`, idempotency of a rerun, and any error path that reports success.
   - Dead code by reference count: every function, constant, flag and parameter used only by tests is deleted or moved into the test, and the `force`, `PYTHON_DEPS`, `MLMODELS_API` and model-file-beside-notebook
     paths are confirmed gone.
   - Every helper with one call site outside tests is inlined or made a closure, unless it is a pure function with a real input space.
   - One reader per persisted document (`metadata.json`, `project.json`, `signature.json`, `model.json`, a run's json), one owner per constant, and no vocabulary declared twice.
   - Names renamed on sight for one prefix per domain and the same word in every file, and tests renamed with their code.
   - Layout against `wrangle` and `media`: public first, then `_` helpers, then types, then constants; a file split when it holds two concepts, merged when tiny.
   - No comments except a documented contract, and every test asserting behaviour and not wording or shape, with each new rule shown to bite by deleting it.
   - The standards (`ruff`, `pyright`, the convention tests), the full suite once, and the real built artefact in its container for the consumers.
   The report lists the defects found and fixed, then the simplifications, then what was left and why, then what was not checked.

Phases 1, 3 and 4 change the on-disk format, so each migrates every notebook's data and `metadata.json` in the same step as its code. The renumbering of phase 1 MUST also rename the git-ignored
`data/` directories of `wrangle/household` and `wrangle/portfolio` on the machine that holds them, which git cannot carry, and say so.

## 9. Spec changes, made phase by phase

| Section | Change |
|---|---|
| 1.1 Terms | Add Define, Model Id, Run Label and Live Run. |
| 2 Requirements | R3 states that feature engineering lives in the model and not in the request. R6 reads "a live run" and not "the latest run". R15 covers a model directory reproduced by a re-run. Add a requirement that names flow unaltered (R12). |
| 3.1, 3.1.1 | The source `model` id is in `project.json`, and `target` stays in `metadata.json`. `package_model` replaces `write_project` as the writer. |
| 3.3 | `pyfunc` `runtime.python` is derived from the imports of the model source, and `PYTHON_DEPS` goes. A `pyfunc` model MAY be defined from a pure function, wrapped by the mlmodels from the signature. |
| 6.1 | State that a name flows unaltered through every section, and that engineered columns are added and never renamed. |
| 6.2 | A run id is an integer of 1000 or more, unique and never reused, with gaps allowed (WS005 checks only that). A run is frozen unless it is `live`. Add `model/<id>/` and its json. Remove the model file beside the notebook (WS007). |
| 6.3 | A live run MAY be given only to `monitoring`, whatever its number. |
| 6.4 | Add `model/<id>/`. Drop the model file beside the notebook. |
| 6.5 | `collect_run` takes `label` and `live`, and has no `force`. Add how a frozen run is refreshed. Add the run summary. |
| 6.6 | Remove the `PYTHON_DEPS` rule and the golden-in-the-notebook rule. |
| 4.4 | Tracing takes `constants`, and is reached through `define_model` and not `train_wasm_trace`. |
| 6.7.7 | A golden frame carries `expect` and an optional `sequence` column, and outputs come from the model. |
| 6.7 | Add Define, with Train described as pure Python. Rewrite Evaluate for models by id and Package and Register for one id. Add the collapsed-plot rule. |
| 6.8 | Acceptance checks are run by `evaluate_gate(ws, model, checks)` for one model, and only the candidate's gate blocks Package. |
| 6.9 | The worked examples define their models by id. |
| 7.1 | Insert Define as stage 5 and renumber. |
| 7.2 | `model.sh` is reached through `python -m mlmodels`. |
| 8 | Adding a model follows the new stage list. |
| 10.1 | Add the names checks, the orphan check and the byte-equal candidate check, each a gate with logic that can fail on real input. Remove WS007 and the checks that can no longer fail. |
| 10.2 | Rewrite the helper table for the stage modules and the single command. |
| 10.3 | Rebuild the requirement-to-check table for the changed and removed checks, including the NB section list. |
| 11.2 | `inputs_sha256` excludes live runs. |
| 11 | Name the single command, and state that release and `fab pull` read `target` from `metadata.json`. |

## 10. Decisions and open decisions

Decided on 2026-11-09:
- Register logs the candidate only, as today. Comparison stays in the notebook (`evaluate_models`).
- `define_model` does not compare `source` with the committed file (section 3).
- The pyfunc wrapper is built by a helper from a pure function and the signature (section 7).
- The build-side commands are the single `python -m mlmodels <command>` (section 5), and the package keeps the name `mlmodels`.
- A released project records its source model id in `project.json`, so reuse of an id with different content shows in the project's hash history.
- A golden frame states refusals with an `expect` column and sequences with a `sequence` column (section 2).
- The word is `gate`, not `guard`: `GateError`, `evaluate_gate` and the spec's gate columns keep one vocabulary, and the public functions are those of 5.1.
- An id, of a run or a model, is 1000 or more, unique and never reused. Gaps are allowed.
- A live run is excluded from `inputs_sha256`. `define_model` takes `constants` and checks the function's free names, and takes an optional `runs=`. `label` is required on `collect_run`.
- Notebooks are migrated mechanically in each phase that renames something, never left for a final phase.
- A live run reaches only `monitoring`, so the current discharge cannot evaluate a model until it is frozen.
- `collect_run` does not warn when it overwrites a csv git already holds.

- `target` stays in `metadata.json` and `py_deps.txt` stays committed, since `fab pull` reads both and `project/` is git-ignored in the personal-data workspaces. `cargo_deps.txt` and `go_deps.txt` are dropped.

Open: none.

## 11. Deviations from the plan

What was built differs from sections 1 to 10 as below. Each is a decision taken while building, with its reason.

**Phase 1, Runs**
- The run labels were written in phase 1 and not phase 6, because WS008 requires a label on every sidecar. Each is drawn from the notebook's Data bullets and describes synthetic data only for the personal-data workspaces.
- The git-ignore rules for `household` and `portfolio` data were `data/*/*/`, which matched the old `data/<split>/<run>/` layout and not `data/<run>/`, so real data would have been committed. They are now `data/*/`, and the lint probe path in NB014 follows.
- The run table prints each column's range and null count, not a min and max of every type; text columns print their lexical range.

**Phase 2, Layout**
- The single command is flat for the model commands (`verify`, `lint`, `embed` and so on) and prefixed for the notebook tools (`notebook new|lint`, `workspace`, `run`). The plan named no subcommand shape.
- `mlmodels/__init__.py` re-exports through an `if TYPE_CHECKING:` block of `x as x` imports, since ruff otherwise removes them as unused.
- `maths.py` is a re-export of operators that live in `_wasm.py`, because the expression tree class and its operators reference each other.
- Underscore-prefixed names imported across modules were renamed to plain names (`capture_source`, `describe_workspace`) so the private-import rule has no exceptions, and `DATA_*` constants live in `_config.py`.

**Phase 3, Define and Evaluate**
- `project.json` records the source model as `model_id`, because `model` already names the model file.
- A traced `wasm` function may read a function of the notebook, a module or an operator of `mlmodels.maths`, and each such function is checked for free names in turn. The plan allowed constants, imports and builtins only, which would have made the `accumulate` fixture's helper functions impossible.
- A `pyfunc` function must be named and its free names must be constants, so a package it needs is imported inside the function. A text source is checked the same way after its constants are prepended.
- `define_model` accepts a source that gives only the required outputs of the signature, and refuses an output the signature does not declare. The plan said any mismatch raises, but `rackmains` is `static` with four constants of seventeen outputs.
- An `error` golden row is checked as a request that omits a required input, and the model is not called with it. The plan said the model's refusal is checked, but no flavour refuses a request, because the consumers validate the required inputs before they call the model.
- `package_model` keeps `tolerance=`, since a `wasm` or `onnx` golden that crosses hosts needs one. A state input left empty is carried from the previous output of its sequence, and one given is used as given.
- `evaluate_plot` takes `truth=`, naming the column to compare with when the split has no column of the output's name. The battery split carries only the incumbent.
- `evaluate_model` returns `time`, the predictions and the incumbent columns, and leaves the truth in the split.
- `pull_model` compares the preview's file hashes with the project's and has no notebook that calls it.
- `provenance.inputs` lists the datasets of the model's runs that no split other than `training` holds, so an `economy` or `costs` dataset that is not a split still counts.
- The scaffold's Define cell for `static` is filled and for other flavours is a heading only, as their Train is.
- WS007 was removed, the model directory has WS011, and the plot and rename rules are NB016 and NB017.

**Phase 4, Package, Register and metadata**
- `cargo_deps.txt` and `go_deps.txt` are removed with their MD005 comparison, and `fab pull` text in the spec says the Rust and Go libraries are checked by hand.

**Phase 5, Lint and tests**
- The names check does not require every signature output to be a column of a labelled run. The battery's output is derived in Explore from the voltage and is in no run. `define_model` is the check that outputs are real, and WS012 checks the required inputs against every dataset of a workspace with a model that is not `static`.
- The plan said no test asserts a message. The existing collect log test still asserts the bracketed run, source and cache state, kept from before and to be removed in a later pass if the convention changes.

**Phase 6, Notebooks**
- Run 1003 is collected and frozen but no split holds it, since a split takes one selection and the discharge after the replacement is too short to gate on. It is in the run table.
- The query of run 1004 is `QUERY` with its lower bound replaced by a subquery, not a literal, to keep one query body.
- The two stateful exponential prototypes stay as plain Python in Evaluate and print their rmse and bounce. They are not models, because they need the reading time and the held state.
- The five candidates are models 1000 to 1004, and the shelf arctan is 1004. Both polynomials return floats that the `INT64` output truncates, so their figures differ slightly from the earlier ones; the selected model's figures are unchanged.

**Phase 7, Consumer cleanup**
- `load_pyfunc` no longer imports `mock`. A warnings filter does not hold because MLflow inserts its own `once` filter, so the load records the warnings and re-emits all but the type hint ones. The `mlserver` copies are byte identical to the reference.

**Phase 8, Review**
- The review pass found and fixed: an interrupted capture (a csv with no json) read back as untyped strings; five single-use helpers; three unused definitions; a mismatched ignore pattern. It left the many small single-use `_lint_*` rule functions, which each name a rule of the spec, and `clear_preview`, `demo_project`, which the system and `mlserver` tests use.
- Not checked: the `rackmains` and `mlserver` builds, a release.

**System verification, 2026-11-10**
- `fab test-sys` passed. The notebooks ran through Register, `household/income` was skipped as having nothing packaged, and the image built.
- Every target ran its project and replayed the golden in the container: Rust (`example/onnx/linear`, `example/static/constant`, `rackmains/ups/battery`), Go (`example/wasm/saturate`), Python (`example/pyfunc/linear`, `example/wasm/accumulate`), and served through the production `mlserver` for the six `homeassistant` and `wrangle` projects.

**Post phase 8, 2026-11-10**
- `ws.params` is the one `ws` field a notebook writes, a dict of JSON values for the constants and fitted or tuned parameters that Train hands to Define and that Evaluate and Package read back. `Workspace` refuses any other new attribute, and NB018 fails a notebook that binds a name in one section and reads it in a later one. Functions and imports are exempt.
- The `training_pl`, `validation_pl` and `backtest_pl` aliases and the `INPUT` and `OUTPUT` constants are gone, so a notebook reads `ws.training` and `ws.inputs[0]`. All 19 notebooks were migrated, and the battery notebook repeats the sampling and normalising lines in Train rather than carry a frame from Explore.
- The Python consumer's entry point is `mlmodels/runtime/__main__.py`, run as `python -m mlmodels.runtime`. The Go and Rust entry points stay `main.go` and `main.rs`.
- 98 redundant `.gitkeep` files were removed. The 14 that remain are in directories that are otherwise empty or hold only git-ignored files.
- The library `workbench` is renamed `mlmodels`, with `mlmodels/workflow/` for the nine stage modules, `mlmodels/runtime/` for the reference runtime (one module per flavour and a `__main__`), and `maths` at the top. The Go and Rust runtimes sit in `src/main/go/runtime` and `src/main/rust/runtime`, and keep the module and crate name `consumer`, since a Go module named `runtime` clashes with the standard library.
- A notebook "section" is now a "stage" in the spec, the lint and the code, and the spec's terms table defines Workflow and Stage.
- The `run_` and `load_` file prefixes are dropped, and the entry points stay `load_<flavour>`. `mlserver` copies the flavour files to `serving/<flavour>.py`.
- System verification repeated after these renames: `fab test-unit` and `fab test-sys` in `mlmodels` and `fab test-unit` in `mlserver` pass. The `rackmains` build is still not checked.
