# MLflow Model Delivery Specification

Status: Draft, 2026-11-02. What is implemented, what is not and what is open is in `plans/mlflow.md`.

## 1. Scope

This specification defines how a model is fitted, packaged, tested, registered and run in the estate, served in MLServer or embedded in
a Python, Rust or Go consumer. It applies to every model fitted in the `mlflow` module. It contains nothing specific to a
single model. Each notebook keeps its plan with it, in `src/may/mlflow/src/main/model/<module>/<model>/<notebook>/plan.md`; the plan for the rackmains UPS battery model is `rackmains/ups/battery/plan.md`.

The key words MUST, MUST NOT, SHOULD and MAY are to be read as in RFC 2119.

### 1.1 Terms

| Term | Meaning |
|---|---|
| Model | A function from one sample of numbers and a carried state to outputs and a new state |
| Sample | One record of numbers: the inputs of one request, or one row of a dataset |
| Input, Output | A named column of the signature, being a feature of `X` or an output of `y` |
| State | The slots a model carries between samples, passed by the caller as one vector input and one vector output |
| Runtime | What executes a project: a WebAssembly host, `onnxruntime`, `mlflow.pyfunc` or an MLServer runtime |
| Project | The directory that holds a model, its signature, its golden sequences and its manifest |
| Flavor | What a project holds and what runs it, as an MLflow flavor: `static`, `wasm`, `onnx` or `pyfunc` |
| Signature | `signature.json`, the MLServer V2 model metadata and the MLflow model signature: every input, output and state slot |
| Golden | Fixed requests and the exact responses they must produce |
| Workspace | The directory `src/main/model/<module>/<model>/<notebook>/` holding one notebook, its plan, its data and, for a flavor that has one, its model file. Several models sit under a module, and several notebooks under a model |
| Consumer | A service that calls a model, served or embedded |
| Served | Run by MLServer behind the V2 inference API |
| Embedded | Run in the consumer's own process |
| Split | One of `training`, `validation`, `backtest` or `golden`, naming the purpose of a dataset |
| Acceptance | The check a notebook defines and runs through the shipped runtime, whose outcome is recorded in `evaluation.json`, and which a project must pass to be released |
| Budget | A dimensionless score for an acceptance check, being how much of its limit the measurement used. Every check passes at a budget of 1 or less, whatever the model |
| Parity gate | Replay of golden sequences and recorded runs through every runtime in use, on x86_64 and aarch64, which MUST reproduce every response and state exactly |
| Alias | An MLflow registry alias on a registered model: `candidate`, `release`, or `m<N>` for the promoted model version `N`. MLflow reserves `v<N>` and `latest` |
| Model version | The identity of a promoted model, an integer of 1000 or more, per registered model. A candidate carries a placeholder `<N>-SNAPSHOT` until register stamps it |
| Service version | The latest release tag when a model was promoted, recorded for audit and never used in a decision |

## 2. Requirements

| # | Area | Requirement | Rationale |
|---|---|---|---|
| R1 | Standard | Every model MUST have one signature, one project layout and one manifest of SHA-256 hashes, whatever its flavor | A consumer moves between served and embedded without change |
| R2 | Standard | The flavor MUST follow the model and MUST NOT follow the environment. The flavors are `static` (constants), `wasm` (formula or stateful, as a WebAssembly module), `onnx` (learned) and `pyfunc` (Python-only libraries, served or in Python, never embedded in Rust or Go) | The environment does not dictate the maths |
| R3 | Standard | Feature engineering MUST live in the project. A request MUST be one sample of numbers plus the state the caller carries. A consumer MUST NOT hold model logic | Recorded once at source, replayable |
| R4 | Parity | Every number reported or shipped for a project, the fit included, MUST come from the shipped runtime of its flavor. A faster proxy MAY choose the fit, and the runtime MUST then reproduce the result. Exploration MAY use plain Python | No gap between pre-prod and prod numbers |
| R5 | Parity | A project MUST NOT be given the alias `release` until a person has reviewed it and the parity gate has passed on every host and both architectures | A mismatch is caught before it ships |
| R6 | Parity | Every dataset MUST be held under exactly one split, with each run wholly in one split. Held-out data MUST NOT be used to fit | An error estimate stays honest |
| R7 | Delivery | A serving runtime MUST pull its project at bootstrap and MUST NOT load a model whose pull failed. An embedded consumer MUST pull only when `fab pull` runs and MUST commit the result | A served model is exactly the promoted one, and an embedded one is exactly the committed one |
| R8 | Delivery | A consumer MUST validate a project at load and MUST NOT use an invalid one. An embedded consumer that cannot do without an answer MUST fall back from its shipped `release` project to the last valid answer and then the `static` default, and MUST NOT depend on a served model. A served model that is down is down | A critical consumer always holds a full set of required outputs |
| R9 | Delivery | Every decision MUST record the model version and project hash that produced it | Any outcome can be traced and replayed |
| R10 | Change | A change of behaviour, being a new WebAssembly ABI version, a runtime or engine version or a signature version, MUST be a code release of the runtime and its consumers. A refit MUST replace only the model file and the hashes that cover it | A refit changes data, a release changes behaviour |
| R11 | Change | Every runtime library MUST be pinned, and native libraries MUST be pinned by hash per architecture. Any upgrade MUST re-run the parity gate | Parity holds only while the runtimes do not move |
| R12 | Standard | Every name MUST follow section 6.1: lowercase `<module>_<dimension>` style with a unit suffix on numeric measures | A name tells you the owner and what is measured |
| R13 | Standard | Every project, notebook and workspace MUST pass the checks of section 10 | The requirements are enforced by tools and not by reading |
| R14 | Parity | A project that is not `static` MUST carry an evaluation from an acceptance check its notebook defines, run through its shipped runtime, and MUST NOT be given the alias `release` unless every gating check has passed | Every model is enforced against its own limits, and the outcome is recorded the same way for all |
| R15 | Parity | A notebook MUST run through its Package section from committed data, and a re-run MUST reproduce a committed `static` project exactly and the signature and acceptance verdict of any other. A project whose acceptance failed MUST NOT be released | A notebook is evidence anyone can reproduce, and a failed acceptance blocks the release and not the run |
| R16 | Standard | A promoted model MUST have a model version of 1000 or more, issued in sequence by the library and never reused, MUST carry it inside its model file, and MUST have the release version it was promoted under recorded in the registry | Any outcome traces to one model, whoever holds the file |
| R17 | Standard | The registry MUST be written only through `asystem.model`, by `register_project` and `promote_project`. A reader MAY then trust what it holds, except that a serving runtime MUST refuse a model whose evaluation did not pass | Every guarantee is made once, at write time, and a hand edit cannot put a failed model into service |

## 3. Project

### 3.1 Files

A project is a directory read the same way by every environment and written and checked by `asystem.model`.

| File | Flavors | Content |
|---|---|---|
| `project.json` | All | Spec version, name, model version, signature version, `flavor`, provenance, the SHA-256 of every other file, and optional constants |
| `signature.json` | All | The MLServer V2 model metadata, which is also the MLflow model signature. It MUST be identical in the project, the consumer and the logged MLflow model, apart from its `versions` list |
| `golden.json` | All | Named sequences of requests and responses, each request carrying the previous response's state. A response is exact unless the file states a tolerance for an `FP64` output |
| `evaluation.json` | All but `static` | Each acceptance check with its measured value, limit, outcome and budget, the SHA-256 of each dataset used, the verdict and the worst budget, specified in 6.8 |
| `model.wasm` | `wasm` | The WebAssembly module, with its fitted attributes built in |
| `model.py` | `pyfunc` | The Python model, in MLflow's models-from-code form |
| `model.onnx` | `onnx` | The ONNX model at a pinned opset |
| `MLmodel`, `artifacts/*` | `pyfunc` | The MLflow model descriptor, written when the project is logged, with the project files carried under `artifacts/` |

The manifest's provenance `implementation` MUST name what is inside the container for every flavor but `static`: the builder of a `wasm` module, the converter and opset of an `onnx` graph, or the pinned requirements of a `pyfunc` model. The manifest's provenance `source` MUST be `static`, `manual` or `mlflow`, and `provenance.inputs` MUST list the data files used. A
manifest MAY carry `constants`; they MUST name signature outputs and are merged into every response.

A golden step MUST have either a `response` or an `error`. An `error` of `signature` means the request does not satisfy the signature, because a required input is
missing, and the model MUST refuse it.

### 3.2 Flavors

| Flavor | What It Is | Model Logic Lives in | Learns from Data? | Carries State? | Runs Where | Use When |
|---|---|---|---|---|---|---|
| `static` | Constants and nothing else | The manifest's `constants` | No | No | Everywhere, with a plain loader | A default, a floor, or tunables that are reviewed and versioned |
| `wasm` | A WebAssembly module | `model.wasm` | Fitted offline, attributes built in | Yes, a fixed-length vector | Python, Rust, Go and served, through a WebAssembly host | A formula, curve, lookup, integrator, decay or latch |
| `onnx` | An ONNX model file | `model.onnx` | Yes | Optional | Python and served (`onnxruntime`), Rust (`ort`), Go (`onnxruntime_go`) | A tree, regression or small network from scikit-learn, XGBoost and the like |
| `pyfunc` | An MLflow Python model | A Python class and its libraries | Yes | Optional | Served in MLServer, or in Python; never Rust or Go | A library with no converter, or arbitrary Python |

### 3.3 Requirements per flavor

`static`
- MUST have no model file: the constants are the manifest's `constants`, declared in the notebook's Setup section.
- MUST answer the same constants for every valid request, MUST give a constant for every required output, and MUST still validate the request.
- MUST be shipped with every consumer that must act without the network, as its floor.
- MUST be written with `write_project` and committed in the consumer's `default` slot, `src/build/resources/model/default/`.

`wasm`
- MUST satisfy the ABI and the determinism rules of section 4, float64, one numeric sample in and a fixed-length state.
- MUST NOT use strings, timestamp parsing or variable-length windows.
- MUST use a lookup table in place of any function with no exact cross-platform result.
- MUST record the hash of `model.wasm` in the manifest, and MUST be committed beside the notebook as `model.wasm`.
- MUST carry its model version as the custom section `asystem.model_version` (3.4), which a host MUST read before it instantiates the module and MUST compare with the manifest, refusing the module on a difference.

`onnx`
- MUST be committed beside the notebook as `model.onnx`.
- MUST pin the opset and use one allow-listed operator set, float64 where each engine has a kernel.
- MUST NOT use an operator over a variable-length input.
- MUST use the same `onnxruntime` shared library everywhere it can, pinned by hash per architecture.

`pyfunc`
- MUST be written as `model.py` beside the notebook, in the form MLflow calls models from code (`set_model`), and logged with `mlflow.pyfunc.log_model`, with the project in `artifacts` and a signature built from `signature.json`.
- MUST carry its model version as the one line `MODEL_VERSION = "<version>"` in `model.py` (3.4), which a loader MUST compare with the manifest.
- MUST NOT be embedded in Rust or Go, or relied on without the network; a caller that needs an answer without the network MUST keep a
  `static` floor.

### 3.4 Versions

- The model version is `^\d{4,}$` once promoted, `<N>-SNAPSHOT` for a candidate or a notebook in development, and `static-<N>` for a `static` floor, which is never promoted and never numbered by the registry. PJ014 requires the `static` form.
- Each workspace holds `.version`, the model version in development as `<N>-SNAPSHOT`, which a notebook reads with `development_version`. `promote` writes `<N+1>-SNAPSHOT` into it, as `fab release` does to the repository `.version`.
- A model file carries its version: `pyfunc` as the one line `MODEL_VERSION = "<version>"` in `model.py`, and `wasm` as the custom section `asystem.model_version`. `onnx` as the `metadata_props` entry `asystem.model_version`. `stamp_model`, `read_stamp` and `content_sha256` write, read and hash it, and PJ013 requires the stamp to equal the manifest.
- `register_project` takes the next model version from the registered model, being the larger of the high-water mark tag `model_version_high_water` and the highest `m<N>` alias, plus one, starting at 1000. It restamps a copy of the project with that number, rewriting the model file, manifest, signature versions and golden responses. A project whose content hash is unchanged, ignoring the stamp, reuses its version.
- `promote_project` refuses unless the candidate is stamped with the next number (PM005) and a release tag can be read (PM006). It then sets the aliases `m<N>` and `release`, raises the high-water mark, and tags the version `model_version`, `service_version`, `acceptance`, `acceptance_budget` and `reviewed_by`. The number is therefore never reused, even if an alias is deleted.
- `pull_model` and `resolve_model` take the selector `release`, `latest` (the highest `m<N>`), or a number. A pull checks the stamp against the registered model version, and an embedded pull accepts promoted selectors only and refuses a project whose acceptance failed or is missing (PM004), so an alias moved by hand cannot bring one in. `python -m asystem.model pull` prints the registry tags of what it pulled.
- A served model is loaded as `release` only, so an unversioned call reaches it. MLServer sends an unversioned call to the highest loaded version, which is why a second version may only be an older one.

## 4. WebAssembly models

A `wasm` project is a WebAssembly module, `model.wasm`, that satisfies one ABI. Python, Rust and Go run the same bytes in a WebAssembly
host and produce the same numbers. The specification fixes the ABI and the determinism rules; how a module is made is the choice of the
project that needs it. A module MAY be compiled from Rust or hand-written, or produced by a builder that emits a small interpreter and a graph. The
manifest's `provenance.implementation` names what made it, and no implementation has a name in this specification.

### 4.1 ABI

- A module MUST export `predict`, as a scikit-learn estimator does. It takes `X` of shape `(n_samples, n_features)` and returns `y` of shape
  `(n_samples, n_outputs)`, both float64 (`FP64`). The features are the signature's scalar inputs followed by the elements of the state input, and the outputs are
  the signature's scalar outputs followed by the elements of the state output, each in signature order.
- Samples are independent, so `predict` holds no state between calls and the caller carries state from each response to the next request (R3).
- A module is a fitted estimator. `fit` is not part of the ABI: fitting is offline, and the fitted attributes are built into the module.
- A call MUST be bounded in time and memory. A host MUST meter fuel and cap memory.
- A module MUST import nothing from its host.
- A module MUST export its linear memory as `memory` and `predict` as `predict(x: i32, n: i32, y: i32)`. The host writes `n` rows of float64 features, row-major, at byte offset `x`, calls `predict`, and reads `n` rows of float64 outputs from byte offset `y`. A host puts `x` at 0 and `y` immediately after the features.
- The signature's tensors are named columns, so column `j` of `X` is the `j`-th feature in signature order, and a V2 request is stacked into `X` in that order.
- A signature tensor of datatype `INT64` travels as float64, exact to 2^53, and the runtime casts it back by the signature. A larger value is invalid.

The vocabulary is scikit-learn's, mapped onto MLServer's and MLflow's:

| Here | scikit-learn | MLServer V2 | MLflow |
|---|---|---|---|
| Sample | A row of `X` | One entry of each input tensor in a request | One row of the model input |
| Input, Output | A feature, an output of `y` | A named input or output tensor | A named column of the signature |
| State | Not modelled | A vector input and a vector output carried by the caller | Two ordinary columns |
| `predict` | `predict` | `MLModel.predict` of a custom runtime | `PythonModel.predict` |
| Flavor | The estimator class | `implementation` in `model-settings.json` | A flavor |
| Signature | The shape of `X` and `y` | Model metadata | The model signature |
| Project | A fitted estimator | A model | A logged model |

### 4.2 Determinism

- A module MUST use float64 (`FP64`) only, and MUST NOT use relaxed SIMD, threads or any operation with a result that differs between CPUs.
- A function with no exact cross-platform result, such as `tanh`, `exp` or `atan`, MUST be replaced by a lookup table or a polynomial, or a golden
  tolerance MUST be stated.
- The golden sequences and the parity gate prove it: the module MUST reproduce every response and state exactly on every host and both
  architectures, except for an output with a stated tolerance.
- A tolerance is stated in `golden.json` as `"tolerance": {"<output>": {"absolute": <a>, "relative": <r>}}`, for an `FP64` output only, with either bound or both. A value
  matches when it differs from the golden value by no more than `absolute + relative * |golden value|`, and an `INT64` output and any output without a tolerance match exactly.
  A learned `onnx` graph, whose float32 kernels differ between CPUs, MUST state one, and a notebook SHOULD choose the smallest bound its own error on `validation` allows
  and say why in its plan. The same rule applies to every runtime of the gate, so it cannot be loosened for one host.

### 4.3 Requirements

- Each project MUST record the hash of its `model.wasm`, so every host runs the same bytes.
- A module MUST carry the custom section `asystem.model_version` holding its model version as UTF-8 text, and a host MUST read it from the bytes before instantiation, so the version it reports is the one in the binary it runs.
- A new ABI version or a new host runtime version MUST be a code release of the runtime and every consumer (R10). A refit replaces `model.wasm` only.
- A builder lives in the repository of the project that needs it and is not a requirement of this specification. Third-party libraries fit the
  numbers that go into the module.

## 5. Libraries

In these tables Yes: is the preferred choice, Maybe: works with the limit stated, and No cannot be done or MUST NOT be.

### 5.1 Runtime libraries

The `wasm` column is the third-party WebAssembly host that runs `model.wasm`; the `static` column is the plain project loader.

| Environment | `static` | `wasm` | `onnx` | `pyfunc` | Notes |
|---|---|---|---|---|---|
| MLServer (Served) | Yes: a Python loader in a custom runtime | Yes: `wasmtime` in the custom runtime. Maybe: `wasmer` | Yes: `onnxruntime` in a custom runtime. Maybe: MLServer's MLflow runtime, if it maps names and types cleanly | Yes: MLServer's MLflow runtime | The Python loader needs only `json` and `hashlib` |
| Python (Embedded) | Yes: the same Python loader | Yes: `wasmtime` | Yes: `onnxruntime` | Yes: `mlflow.pyfunc` in process | |
| Rust (Embedded) | Yes: `serde_json` and `sha2` | Yes: `wasmi`, pure Rust and fuel-metered. Maybe: `wasmtime`, where speed outweighs size | Yes: `ort`, loading the pinned wheel's library with one thread. Maybe: `tract` unoptimised, where memory is tight | No | `tract` optimised is not a choice: it gave off-by-one results. `pyfunc` needs the Python stack, so it cannot be embedded |
| Go (Embedded) | Yes: `encoding/json` and `crypto/sha256` | Yes: `wazero`, pure Go with no cgo | Maybe: `onnxruntime_go`, which needs cgo and a native library, only when a Go consumer needs a learned model. Maybe: a pure-Go engine, for trivial graphs only | No | `wasmtime-go` is not a choice, since it needs cgo. `pyfunc` cannot be embedded |

### 5.2 Authoring and training libraries

`static` needs no library: it is written by hand with `write_project`. A `wasm` module is produced by a builder chosen by its project; the
libraries here fit the numbers that go into it.

| Library or Tool | `wasm` | `onnx` | `pyfunc` | Notes |
|---|---|---|---|---|
| NumPy, SciPy, polars | Yes: fit and then build a module with `scipy.optimize.least_squares` and numeric derivatives | No | Maybe: any use | The default for formula models; polars for data, pandas only where a library needs it |
| scikit-learn | Maybe: linear models and small nets only, by exporting weights as for JAX and MLX; prefer `onnx` | Yes: `skl2onnx`, most estimators and pipelines | Maybe: any use | The preferred training stack for tabular learned models |
| XGBoost, LightGBM, CatBoost | No | Yes: `onnxmltools` | Maybe: any use | CPU training on the laptop is enough at this scale |
| PyTorch | Maybe: linear models and small nets only, by exporting weights as for JAX and MLX; prefer `onnx` | Maybe: `torch.onnx` | Maybe: any use | Only if a network is ever needed; the MPS backend is beta on Apple Silicon |
| TensorFlow, Keras | Maybe: linear models and small nets only, by exporting weights as for JAX and MLX; prefer `onnx` | Maybe: `tf2onnx` | Maybe: any use | Nothing that needs `tensorflow-metal` ships, since it is weakly maintained |
| statsmodels, Prophet | No | No | Yes: served or in Python | No ONNX converter is known; keep a `static` floor |
| JAX, MLX | Maybe: train with it, then export the weights of a small net (linear layers, an MLP) into a module's matrix and activation code, using lookup tables or polynomials for `tanh` and `exp` or a stated golden tolerance | No | Maybe: a custom `pyfunc`, served or in Python, with a `static` floor | JAX converters are fragile and MLX has no exporter, so neither ships as `onnx`; bigger models are retrained in PyTorch or scikit-learn; nothing Metal-specific ships |

A library marked No under a flavor MUST NOT ship in that flavor; training in it is permitted. A runtime SHOULD be the smallest that runs
its flavor: `static` needs none, `wasm` needs one small host per language, `onnx` needs an engine.

### 5.3 Notebook tooling

| Need | Yes | No |
|---|---|---|
| Run a Notebook | `jupyterlab` and `nbconvert --execute` through `notebook.sh`, kernel `asystem` | The Conda Python, which lacks the dependencies |
| Parameterise a Headless Run | `papermill`, once pinned | Editing cells to change inputs |
| Review a Notebook Diff | Commit without outputs, or pair with `jupytext` | Committing large embedded outputs |
| Check Every Notebook | `model.sh check`, run by `fab release` and `deploy.sh` | Trusting a committed project nobody has reproduced |
| Refresh Served Models | `model.sh refresh`, run by `deploy.sh` | Restarting the whole `mlflow` image to change a model |
| Write the Registry | `register_project` and `promote_project` only (R17) | Hand edits of versions, aliases or tags in the MLflow UI |
| Register and Alias | `asystem.model.register_project` over `mlflow` | Hand-copying files between hosts |

## 6. Workspace layout and data

### 6.1 Naming

Every name MUST follow the module and dimension style the metrics use: `<module>_<dimension>[_<dimension>...]`.

- A name MUST use lowercase letters, digits and underscores only. It MUST NOT use hyphens, spaces or camel case.
- The first token MUST be the module that owns the thing named, such as `rackmains`, `weewx` or `homeassistant`, or `example` for a worked example.
- The following tokens are dimensions, from general to specific. A numeric measure MUST end with a unit suffix, such as `_volts`,
  `_hertz`, `_pct`, `_seconds`, `_wh` or `_celsius`.
- A name a service already publishes MUST be used as published. A model MUST NOT rename a service's metric.
- A workspace has three levels, so several models can sit under one module and several notebooks under one model: the module, the model
  (a group of related notebooks) and the notebook.

| What | Form | Examples |
|---|---|---|
| Module Directory | `<module>`, or `example` for a worked example | `rackmains`, `weewx`, `homeassistant`, `example` |
| Model Directory | `<model>`, a group of related notebooks | `ups`, `console`, `forecast`, `hotwater`, `static` |
| Notebook Directory | `<notebook>`, one notebook per directory, the notebook itself being `notebook.ipynb` | `battery`, `roof`, `temp`, `constant` |
| Registered Model | `<module>_<model>_<notebook>`, also the name used in `MLSERVER_MODELS` | `rackmains_ups_battery`, `weewx_console_battery`, `weewx_forecast_roof`, `homeassistant_hotwater_temp`, `example_static_constant` |
| Dataset | `<model>_<notebook>_<dimension>...`, ending `_<start>_<end>` with the first and last date it covers unless it is `golden` | `console_battery_voltage_2024-06-06_2024-10-25`, `ups_battery_golden` |
| Signature Input | The owning service's metric name, unchanged | `weatherstation_console_battery_voltage` |
| Signature Output, State Slot or Constant | `<module>_<dimension>...` with a unit suffix | `weewx_console_battery_capacity_pct`, `rackmains_battery_remaining_seconds` |
| Model Plan | `plan.md` in the notebook directory | `rackmains/ups/battery/plan.md` |
| Split | One of `training`, `validation`, `backtest`, `golden` | `training` |
| Project Flavor | The lowercase flavor value | `wasm` |
| Timestamp | `YYYY-MM-DD_HH-MM-SS`, Perth time | `2026-10-31_15-17-42` |

### 6.2 Layout

```
src/may/mlflow/src/main/model/<module>/<model>/<notebook>/notebook.ipynb
src/may/mlflow/src/main/model/<module>/<model>/<notebook>/plan.md
src/may/mlflow/src/main/model/<module>/<model>/<notebook>/.version
src/may/mlflow/src/main/model/<module>/<model>/<notebook>/model.<wasm|onnx|py>
src/may/mlflow/src/main/model/<module>/<model>/<notebook>/data/<split>/<timestamp>/<dataset>.csv
```

- `<module>`, `<model>` and `<notebook>` MUST be named as section 6.1 requires.
- A notebook directory MUST hold one notebook named `notebook.ipynb`, its `plan.md`, its `.version`, its `data` and at most one model file (`model.wasm`, `model.onnx` or `model.py`, as the flavor requires), and nothing else. The data belongs to
  the notebook and MUST NOT be shared between notebooks.
- `plan.md` MUST state the notebook's intent, signature, data, status and open decisions in the terms of this specification, and MUST NOT
  restate this specification.
- `<timestamp>` names one capture. The same timestamp MAY appear under several splits so a capture can be split across them.
- A file under a split is source. It MUST be committed like a project, so a dataset is reproducible and a re-query is a diff.

### 6.3 Splits

| Split | Used for | Never Used for |
|---|---|---|
| `training` | Fitting the model | Judging the result |
| `validation` | Tuning the choices around the fit, and a first error estimate on unseen data | Fitting |
| `backtest` | Replaying whole recorded history through a finished model, sample by sample, as the service would | Fitting |
| `golden` | Fixed inputs with exact expected outputs, checked on every runtime and architecture | Fitting or tuning |

A run held out for `validation` or `backtest` MUST NOT be moved into `training` after it has been used to make a decision.

### 6.4 What is on disk

| Path | What It Is | Written by | Read by |
|---|---|---|---|
| `<module>/<model>/<notebook>/notebook.ipynb` | The notebook, committed without outputs | By hand | `notebook.sh <module>/<model>/<notebook>` or the IDE |
| `<module>/<model>/<notebook>/model.wasm`, `model.onnx` | The model, committed so a refit is a reviewable diff | The notebook's Fit and Package cells | `write_project`, which copies it into the project, and a person reviewing the diff |
| `<module>/<model>/<notebook>/model.py` | The Python model | By hand, or by the notebook when it builds the fitted attributes in | `write_project`, which copies it into the project, and `ruff` |
| `<module>/<model>/<notebook>/plan.md` | The notebook's plan | By hand | A person; the notebook's intent, signature, data, status and open decisions |
| `<module>/<model>/<notebook>/data/training/<ts>/<dataset>.csv` | Rows the fit sees | `query_influxdb3(..., "training", ...)`, or by hand | The notebook's fit cells |
| `<module>/<model>/<notebook>/data/validation/<ts>/<dataset>.csv` | Rows held out for tuning and a first error estimate | `query_influxdb3(..., "validation", ...)` | The notebook's evaluate cells |
| `<module>/<model>/<notebook>/data/backtest/<ts>/<dataset>.csv` | Whole recorded runs | Copied from the consumer, or a query | The evaluate and replay cells, and the consumer's replay test |
| `<module>/<model>/<notebook>/data/golden/<ts>/<dataset>.csv` | Fixed inputs with exact expected outputs | Generated from the shipped runtime, then committed | `write_project` (becomes `golden.json`) and the consumer's golden test |
| `src/may/mlflow/target/notebook/<module>/<model>/<notebook>/notebook.ipynb` | An executed notebook | `notebook.sh`; not committed | A person reading the run |
| MLflow Run and Registered Model `<name>` | The logged project and the aliases `candidate` and `release` | `register_project` | `pull_model`, the `mlserver` bootstrap |
| `<consumer>/src/build/resources/model/default/` | The `static` default project, committed | The model's notebook, through `write_project` | The consumer's build, tests and image |
| `<consumer>/src/build/resources/model/release/` | The embedded copy of the `release` project, committed | The consumer's `generate.sh` with the pull flag | The consumer's build, tests and image |
| `/asystem/mnt/models/<name>/` in `mlserver` | The served copy of the `release` project | `mlserver`'s bootstrap | The serving runtime |

### 6.5 The data cache

`query_influxdb3(env, query, workspace, split, name, timestamp=None, database=None, force=False)`, where `workspace` is `<module>/<model>/<notebook>`:
- MUST read `data/<split>/<timestamp>/<name>.csv` if it is present, and MUST NOT touch the network in that case.
- MUST otherwise query and write the file through a temporary file renamed into place, so a failed query writes nothing.
- MUST use the newest capture of that name when no `timestamp` is given, or start a new one.
- MUST query again and overwrite the file when `force` is true.
- MUST accept only the four splits.

`data_path(workspace, split, name, timestamp=None)` returns the same path, for a file that did not come from a query.

### 6.6 Notebook conventions

What a model notebook does. How it is laid out is section 6.7.

A model notebook:
- MUST declare the model name, version and dataset names as constants in the Setup cell.
- MUST fit only on `training`, and MAY load `validation` to check the fit.
- MUST write its golden inputs and expected outputs under the `golden` split and build `golden.json` from that file.
- MUST list the data files used in `provenance.inputs`.
- SHOULD keep logic in `library` and keep cells thin.
- MUST run with the `asystem (Python 3.12)` kernel, never the Conda Python.

### 6.7 Notebook style guide

**File**
- A notebook MUST be Jupyter notebook format 4 and MUST be committed without outputs and without execution counts. Committed outputs bloat
  diffs, can leak data and are not reproducible.
- A notebook MUST NOT contain secrets, absolute paths or notebook magics. Paths MUST come from `data_path` and `MODEL_DIR`.
- A notebook MUST be deterministic: a random operation MUST use a fixed seed.

**Cell order**
1. The title cell, a markdown cell.
2. One markdown section cell per section, each followed by the code cells of that section.

**The title cell**
- MUST hold the heading `# <module> / <model> / <notebook>`, the only level-one heading in the notebook.
- MUST follow it with one line stating the notebook's intent.
- MUST then hold a table with the header Term and In This Notebook and one row for each of Intent, Project Flavor and Data Splits, in that
  order. Each row uses the terms of this specification and cites its section where one applies.
- MUST bold only the Term column of that table. It is the one place a bold cell is used.

**Sections**
- A section heading MUST be level two, `## <Section>`, in Title Case, and MUST be one of the names below, in this order. A section that
  does not apply MUST be omitted and the order kept.

| Section | Stage (7.1) | Required | What It Holds |
|---|---|---|---|
| Setup | None | Always | The `library` imports, `env` and the constants |
| Capture Data | 1 | When the notebook reads data | Queries and loads, through `query_influxdb3` and `data_path` |
| Explore | 2 | May | Plots and checks; nothing reported from it ships (R4) |
| Fit | 3 | When the model is fitted | The fit, on `training` only (R6) |
| Evaluate | 4 | When the model is fitted | Checks on `validation` and `backtest` through the shipped runtime |
| Package | 5 | Always | The golden file, the signature, `write_project` and `verify_project` |
| Register | 6 | When the project is registered | `register_project` with the alias `candidate` |
| Pull | 8 | Where a round trip is tested | `pull_model` and the comparison with what was registered |

- A section cell MUST hold the heading and two dot points: `- **Stage:** <number>, <stage name>` (or `none` for Setup) and
  `- **Intent:** <one sentence beginning with a verb>`.
- A section Intent SHOULD cite the requirement or section it serves, such as (R6) or section 6.5.
- A section MUST NOT use a heading deeper than level two.
- A code cell MUST do one thing, and SHOULD be no longer than a screen.

**Code**
- A notebook MUST import from `library.<module>` by name, never with `*`, and MUST NOT extend `sys.path`. The kernel carries the
  `PYTHONPATH`: `notebook.sh` installs it and the IDE source roots provide it.
- Python MUST be formatted with `ruff format` at the repo line length of 200 and MUST NOT be hand-wrapped; the formatter decides the layout.
- Constants MUST be UPPER_CASE (`WORKSPACE`, `MODEL_NAME`, `MODEL_VERSION`, `TRAINING`, `VALIDATION`, `GOLDEN`). A notebook MUST NOT carry a flag
  that switches the network on, since `query_influxdb3` reads the committed file when it is present (6.5).
- MUST run through its Package section from committed data (R15). The Register section, and anything after it, writes to the registry, and a check must not write, so `notebook.sh` stops before it
  unless `REGISTER=1`. An acceptance that fails is recorded as the verdict and does not stop the run.
- MUST write a consumer's slot through `consumer_project_dir`, which `model.sh check` redirects to `target/model-output` with `MODEL_OUTPUT_DIR`, so a check never rewrites the tree.
- A polars frame SHOULD be named with the suffix `_pl` and a path with the suffix `_path`.
- Imports SHOULD sit at the top of the cell that first needs them.
- A comment MUST NOT restate the code; narrative belongs in the section's markdown cell.

**Lint**

`fab build` lints every notebook under `src/main/model/*/*/*/` the way it lints Python, and rewrites the source:
- `ruff check --fix` and `ruff format` run on the code cells, with the repo `ruff.toml`. E402 is ignored in notebooks, because an import sits at the top of the cell that first needs it, not of the notebook.
- `python -m asystem.notebook --fix` strips outputs and execution counts and checks the notebook rules of section 10. The executed copy
  is kept under `target/notebook`, never in the tree.
- `python -m asystem.workspace` checks each workspace against the rules of section 10.
- `ruff check --fix` and `ruff format` also run on a workspace's `model.py`, which is not type checked.

A finding other than NB002 fails the build. Notebooks are not type checked, since `pyright` does not check `.ipynb` files from the command
line. Notebooks are not run by `fab build`; `notebook.sh` runs one headless, and `model.sh check` runs them all.

**Markdown**
- Identifiers, paths, commands and values MUST be in backticks.
- A table MUST have a Title Case header and Title Case first-column labels, and each other cell MUST begin with a capital.
- A table MUST NOT bold a cell, except as the title cell requires.

### 6.8 Acceptance

Each notebook owns what its model must achieve and how it is measured, and the library enforces that it was done and records the outcome the same way for every model type. This mirrors the golden builder: the notebook defines a function with no arguments, as `golden_samples` is for `golden_data`, and the library validates and stores what it returns.

- A notebook of a non-`static` flavor MUST define `acceptance_checks()`, measure the shipped model on `validation` or `backtest` data inside it, and return a non-empty list of checks. It passes the function and the dataset paths to `evaluate_acceptance(check, datasets)`, then hands the result to `package_project` as `evaluation`. A project without one fails AC001.
- A check is `split` (`validation` or `backtest`), `output` (a signature output), `name` (the naming style), `value` (a number, or null when it could not be measured), `limit`, `direction` (`max` for a value that must not exceed the limit, `min` for one that must not fall below it) and optionally `gate`, which defaults to true. A `training` check does not exist, since the fit is not judged on its own data, and `golden` is judged by exact parity.
- The library, not the notebook, decides the outcome: a check passes when its value is within its limit, and a null value fails. `measure(truth, predicted)` is an optional helper with the scikit-learn names `rmse`, `mae`, `max_abs_error`, `bias`, `p95_abs_error`, `r2` and `pearson_r`. A notebook MAY compute anything else, such as a one-sided error, a recall or a worst run.
- Every required scalar output MUST have a gating check. A `backtest` check SHOULD gate, and a `validation` check gates only for a model with no `backtest` run yet, which its plan MUST say.
- The budget is the standard score, the same for every model type: for a `max` check it is the value divided by the limit, floored at zero, and for a `min` check it is the limit divided by the value. A check passes exactly when its budget is 1 or less. The evaluation records the worst budget of the gating checks, or null if any gating check could not be measured. A lower budget means a larger margin. It compares a model with its own limits, not one model's accuracy with another's.
- `register_project` logs the run metrics `acceptance_passed` (1 or 0) and `acceptance_budget`, each measured value as `<split>/<output>/<name>`, each dataset with `mlflow.log_input` under the split as its context, and the tags `acceptance` and `acceptance_budget`. `promote_project` copies both tags onto the promoted version.
- `evaluate_acceptance` prints the standard line `acceptance [passed|failed] budget [<worst budget>]`, which `model.sh check` repeats for every notebook so a failed verdict is visible in a release or deploy log.
- The limits live in the notebook's function, so a changed limit is a change to that notebook, and the release review reads that diff. A notebook owns its limits, and a limit loosened there is accepted unless a review catches it: no tool compares limits between versions. The evaluation does not need to say what was required, only that the enforced checks passed.

### 6.9 Worked examples

The module `example` holds one hello-world project for each flavor. Each is fully worked, with a notebook, a plan, data under every split,
an acceptance check and a golden file, and each is replayed in every runtime that supports its flavor. A new flavor, runtime or runner SHOULD be
tried on these first.

| Notebook | Flavor | Shows | Python | Rust | Go |
|---|---|---|---|---|---|
| `example/static/constant` | `static` | A constant and the register and pull path | Yes | Yes | Yes |
| `example/wasm/accumulate` | `wasm` | A fitted line built into a module, with a state vector | `wasmtime` | `wasmi` | `wazero` |
| `example/onnx/linear` | `onnx` | A fitted line as a graph at a pinned opset | `onnxruntime` | No | No |
| `example/pyfunc/linear` | `pyfunc` | A fitted line as a `PythonModel` | `mlflow.pyfunc` | No | No |

The Rust and Go runners are `src/test/replay/rust` and `src/test/replay/go` in the `mlflow` module. Each takes a project directory, checks each file against the hash in `project.json` (PJ003), replays its golden
exactly, prints one result row and exits 0, exits 1 on a difference, or exits 2 for a flavor it does not support. `model.sh build` builds them, and `model.sh parity` writes a
gate file for every project under `target/model-output/project`, and `model.sh check` runs it after the notebooks. A runtime that cannot run a flavor is
absent from that project's gate file, and promotion requires only the runtimes the flavor supports (7.4).

## 7. Lifecycle

### 7.1 Model lifecycle

| # | Stage | Who Runs It | Command or Hook | Output | Gate to the Next Stage |
|---|---|---|---|---|---|
| 1 | Capture data | Notebook | `query_influxdb3(...)`, or a file saved with `data_path` | `data/<split>/<ts>/<name>.csv` | The split is right and each run is wholly in one split |
| 2 | Explore | Notebook | Plain Python | Ideas, plots | None |
| 3 | Fit | Notebook | A builder (`wasm`), `skl2onnx` (`onnx`), `model.py` (`pyfunc`) | Fitted attributes | Fit error on `training` is sane |
| 4 | Evaluate | Notebook | Shipped runtime over `validation` and `backtest` | Metrics, `evaluation.json`, golden sequences | Every gating acceptance check passes |
| 5 | Package | Notebook | `write_project`, then `verify_project` | Project directory | Manifest, hashes, signature and golden agree |
| 6 | Register | Notebook | `register_project(...)` | Registered version stamped with the next model version, alias `candidate` | The project verifies on the server side too |
| 7 | Review and promote | A person | `promote.sh` sets the aliases `m<N>` and `release` and records the service version | The version consumers follow | The acceptance passed and the merged parity gate (7.4) passed on every host the flavor supports and both architectures |
| 8 | Pull, embedded | The consumer's `generate.sh` | `python -m asystem.model pull <name> release <dir>/release --signature <dir>/default/signature.json` | The project in the consumer's `release` slot, unstaged, and its registry tags printed | The signature is unchanged, the hashes match and the stamp equals the registered model version |
| 8 | Pull, served | `mlserver` bootstrap | `mlflow artifacts download models:/<name>@release` | `/asystem/mnt/models/<name>` | The download succeeded and its `evaluation.json` passed, else the bootstrap container fails and the model is not loaded |
| 9 | Commit and release | A person | `git`, then the fab lifecycle | A release of the consumer | The consumer's own tests and the gate |

### 7.2 Fab lifecycle

Each task includes the ones before it.

| `fab` Task | What It Runs, in Order | Model Hook | Pulls from MLflow? |
|---|---|---|---|
| `generate` | Each module's `generate.py`, then its `generate.sh` with the pull flag false | `generate.sh` runs `verify` on the committed project and does nothing if there is none | No |
| `build` (Default) | `setup`, `clean`, `generate`, then lint, format, type check and compile | The loader compiles against the signature | No |
| `unittest` | `build`, then each module's unit tests (`unit_test.py`, `cargo test`, Go) | Project library tests in `_` and `mlflow`; the consumer's loader, golden and replay tests | No |
| `systest` | `build`, then, for a module with `model.sh`, `model.sh check`, then bring the module up on a synthetic host and run its system test | The consumer runs with the committed project against its mock. `mlflow` runs every notebook, compares the committed slots and replays every project in each runtime on each architecture (7.4) | No |
| `package` | `build`, then build the image | The project, and the pinned host library, go into the image | No |
| `execute` | `generate`, then run the module locally | For `mlserver`, the bootstrap pulls `release` into the container | Served pull only |
| `release` | Before tagging, for a module with `model.sh`, `model.sh check`; for a module with a committed `release` slot, `check_release` on it. Then per host: `package`, save the image, copy it, run `install.sh install` | A failed notebook run, comparison or replay, or a failed acceptance, stops the release. The consumer ships whatever project is in its tree; `mlserver` pulls at bootstrap after install | Served pull only |
| `pull` | Backup of git-ignored files, `git pull --all`, install pinned dependencies, then `generate` for every module with the pull flag true | `generate.sh` runs `pull`, then `verify` | Embedded pull happens here and only here |
| `deploy` | `generate`, then each module's `deploy.sh` if it has one | `mlflow`'s `deploy.sh` runs `model.sh check`, as `release` does, then `model.sh refresh`, which re-runs the `mlserver` bootstrap pull and restarts it, and pushes no image | Served pull only |

### 7.3 Consequences

- Builds do not call MLflow. Only `fab pull` calls MLflow for an embedded model, and every other build verifies the project in the tree.
- `fab pull` also backs up git-ignored files and runs `git pull --all`, whose autostash unstages the index. To refresh only a project,
  run `PYTHONPATH=src/all/_/src/build/python python -m asystem.model pull <name> release <dir>/release --signature <dir>/default/signature.json` with
  `MLFLOW_TRACKING_URI` set, then review the diff.
- A served runtime takes `release` at bootstrap, which runs when its container starts, so moving the alias changes what the next
  bootstrap pulls and a served refit needs no consumer release. An embedded consumer needs the pull, a commit and a release.
- A signature change fails the pull's signature comparison by design. It is a new `signature_version`, a release of the consumer, and a
  new model name or version served side by side while consumers move.

### 7.4 The parity gate

The gate file is the evidence for R5. It is one JSON document for one project:

```
{"project_sha256": "<SHA-256 of project.json>",
 "results": [{"host": "python", "arch": "x86_64", "passed": true}],
 "skipped": ["go"]}
```

- `host` is the runtime (`python`, `rust` or `go`) and `arch` is `x86_64` or `aarch64`. `skipped` names a runtime that does not support the flavor.
- `model.sh parity` writes `target/gate/<arch>/<workspace>.json` for each architecture it runs and the merged `target/gate/<workspace>.json`. `model.sh check` runs it.
  `SERVICE_LOCAL_RUNTIME`, which a system test uses too, chooses the architectures. `emulated`, the default, runs this machine's architecture natively and every other
  architecture of `.hosts` in a container for that platform, built from `src/test/replay/Dockerfile`, which installs the pinned Python libraries and builds the Rust and Go
  runners for it. `native` runs this machine's architecture only, and a promotion then needs `--archs` for that architecture.
- A gate file from a real host of another architecture is merged by hand with `python -m asystem.model gate-merge --out <file> <gate> <gate>`. It refuses files for
  different projects, keeps a failure if either file has one, and drops a skipped runtime that ran in any file. Emulation runs the real instruction set but not the real
  hardware, so a result that depends on the CPU, as a transcendental function can, needs a run on a real host.
- `promote.sh --gate <file> --reviewed-by <name>` requires a passed row for each runtime the flavor supports, `PROJECT_RUNTIMES`, on each architecture of `--archs`. A
  `static` or `wasm` project needs `python`, `rust` and `go`; an `onnx` or `pyfunc` project needs `python`. `--hosts` overrides it.
- The gate is bound to the project by hash, so a change to the project, including a restamp, needs a new gate.

## 8. Procedure: adding a model

1. Pick the flavor from section 3.2.
2. Create `src/may/mlflow/src/main/model/<module>/<model>/<notebook>/` with `notebook.ipynb`, `plan.md` and `data/`, and name them as section 6.1 requires.
3. Write the signature with `build_signature`, `signature_input`, `signature_output` and `signature_state`. An input name MUST be a metric name
   from its owning service, required outputs MUST be the ones the consumer cannot act without, and state slots are numbered in order.
4. Put data under splits, with `query_influxdb3`, `read_data`, `golden_data` or `data_path`.
5. Write the notebook to sections 6.6 and 6.7, and fit on `training`.
6. Evaluate on `validation` and `backtest` through the shipped runtime, define `acceptance_checks` to section 6.8 and run it with `evaluate_acceptance`, and generate the golden sequences from it. The sequences MUST
   include a first call with no state, boundary values, a missing input that gives a signature error and a long gap. Build each step with
   `golden_step` and the document with `golden_document`.
7. Package with `write_project`, which copies the workspace's model file and the evaluation into the project, then runs `verify_project` and so every project check of section 10. A static default is written to the
   consumer with `consumer_project_dir`.
8. Register with `register_project(project_dir, name, tracking_uri)`. It logs and registers the project and sets the alias `candidate`, and an unchanged project, by the SHA-256 of its `project.json` in the tag `project_sha256`, reuses its version. A
   person sets `release` after review. The experiment MUST be created after the proxy is on, since older experiments keep their old
   artifact location.
9. Ship it. For a served model, add the registered name to `MLSERVER_MODELS` in `src/may/mlserver/.env_all`. For embedded, give the consumer a
   `generate.sh` as in section 8.1.
10. Consume it through a loader that validates the project at start, applies the fallback order, carries the state between calls and
    records the model version and project hash wherever a decision is logged.
11. Test in the consumer: replay the golden sequences and any recorded runs through the consumer's own runtime on both architectures.
12. To refit, put new data under splits, fit, and repeat steps 6 to 9 under a new `model_version`. `release` MUST move only when the
    gate passes. A served rollback moves the alias; an embedded rollback reverts the project in the tree and releases.

### 8.1 The consumer's `generate.sh`

`<name>` is the registered model and `<dir>` the consumer's model directory, normally `src/build/resources/model`. The consumer holds two
slots, `default` for the `static` project and `release` for the pulled one. They are separate because a pull replaces its slot. The
pulled signature is compared with the `default` signature, so both slots carry one signature (R1).

```bash
export PYTHONPATH="${ROOT_DIR}/../../all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}"
[ "${1}" == "True" ] && python -m asystem.model pull <name> release "<dir>/release" --signature "<dir>/default/signature.json"
python -m asystem.model verify "<dir>/default"
python -m asystem.model verify "<dir>/release"
```

The pull needs `MLFLOW_TRACKING_URI` in the environment, read from the `mlflow` module's `.env_all`. Every command MUST do nothing
harmful when no model is registered or no project exists yet.

## 9. Module requirements

MLflow owns data and lifecycle, MLServer only serves, and nothing is shared by a mount.

| Thing | Where | Requirement |
|---|---|---|
| Notebooks and Their Data | `mlflow` module, `src/main/model/<module>/<model>/<notebook>` | Fitting and registering MUST sit with the tracking service; notebooks MUST be thin |
| The `library` Package | `mlflow` module, `src/main/python/library` | MUST have one module per concern (`config`, `env`, `data`, `project`, `plot`), an `__init__.py` holding only the shared path, and no logic in notebooks that belongs here |
| Project Code | `_` module, `asystem.model` | One implementation, unit tested, and also a command: `python -m asystem.model` |
| Tracking DB, Registry, Artifact Storage | `mlflow` only | MUST run `--serve-artifacts` with `--artifacts-destination` on its own volume and `--default-artifact-root mlflow-artifacts:/`, so no client writes a path or needs a share |
| Allowed Hosts | `mlflow` `.env_all` | MUST set `--allowed-hosts` and `--cors-allowed-origins`, since MLflow 3 rejects an unknown `Host` header |
| Models in `mlserver` | A local volume | MUST pull by alias at bootstrap, MUST fail the bootstrap on a failed pull or on a pulled `evaluation.json` whose `passed` is not true, and MUST bound every call with a timeout |
| Embedded Copies | The consumer's tree | MUST be pulled by the consumer's `generate.sh`, reviewed as a diff, and never fetched at build or run time |
| Server Start | `mlflow` entrypoint | MUST run under `exec` with `pipefail`, and a failed `mlflow db upgrade` MUST stop the start |
| Bootstrap and Checks | `mlflow`, `mlserver` | `bootstrap.sh` runs in a separate `<name>_bootstrap` container, so any probe in `checkalive.sh` MUST address the service by `${<NAME>_SERVICE}:${<NAME>_HTTP_PORT}` and never `localhost`, which `checkexecuting.sh` and `checkhealthy.sh` may use only for checks that run inside the service container |
| Serving Start | `mlserver` | MUST NOT report healthy until `/v2/health/ready` passes and every name in `MLSERVER_MODELS` is ready; a stub that only runs the process MUST NOT pass `checkhealthy.sh` as `true` once a model is listed |
| Serving Release | `mlserver` | A release MUST run the bootstrap to completion and `mlserver` MUST wait for it (`service_completed_successfully`), so a failed pull or a failed acceptance stops the start. A restart for a promotion MUST NOT depend on a stopped `*_bootstrap` container still existing, because none remains after an install |
| Registry Address | Every client | MUST use the proxy name from `MLFLOW_TRACKING_URI`; the published `host:port` answers `/health` only and returns `403 Invalid Host header` elsewhere, and a client MUST report that as a finding |
| Declared Models | `MLSERVER_MODELS` | SHOULD be generated from the registry's `release` aliases and not hand-listed, so a served model is declared once |
| Serving Smoke Test | `fab systest` in `mlserver` | MUST start with the `example` models, replay each project's `golden.json` through `/v2/models/<name>/infer` and fail on a model that is not `ready` or whose served version differs from its stamp |
| Status and Rollback | `model.sh` | `status` MUST read without writing and show each model's versions, aliases, hashes and whether it is `ready` on `mlserver`; `rollback` MUST move `release` only to a version whose acceptance passed and wait for `ready` |
| Health | Both services | MUST be real checks with every `curl` bounded; `mlflow` healthy MUST also read the registry and experiments API |
| Shutdown | Both services | MUST have a stop grace period |

## 10. Checks

A project, a notebook and a workspace MUST pass the checks below (R13). Each check has an identifier, which the tool prints with its
finding. A project is checked by `verify_project`, which `write_project`, `package_project`, `register_project` and `pull_model` call, and by
`python -m asystem.model verify` and `python -m asystem.model lint`, which prints every finding. Promotion is checked by
`check_gate` and `check_acceptance`, which `python -m asystem.model promote` calls. It is run with `src/main/resources/promote.sh` in the `mlflow` module, since `fab`
is for commands every module shares and promotion is specific to MLflow. A notebook is checked by `python -m asystem.notebook` and a workspace by `python -m asystem.workspace`,
both run by `fab build`.

### 10.1 Invariants

| Id | Invariant | Enforces |
|---|---|---|
| PJ001 | A project has a manifest with a supported spec version | R1 |
| PJ002 | The flavor and the provenance source are known, the provenance inputs are a list, and a flavor but `static` states its implementation as more than one word and not a placeholder | R1 |
| PJ003 | Every file the flavor requires is in the manifest, exists, and matches its SHA-256 | R1 |
| PJ004 | The project name follows the naming style and equals the signature name | R12 |
| PJ005 | The signature version equals the manifest's, and the model version is among the signature's versions | R1, R10 |
| PJ006 | The signature is complete: datatype, shape, unit, required flag and description on every input and output, unique names, state slots numbered from 0 | R1 |
| PJ007 | Every output starts with the module and ends with the unit suffix of its unit | R12 |
| PJ008 | Constants name signature outputs, and a `static` project gives a constant for every required output | R8 |
| PJ009 | The golden model version equals the manifest's | R1 |
| PJ010 | Every golden step has a response or an error, names only signature inputs and outputs, and gives every required input and output | R3, R4 |
| PJ011 | The golden holds a step that expects a signature error, and a first call with no state when the signature has state | R8 |
| PJ012 | Every golden response of a `static` project equals the constants | R4 |
| PJ013 | The stamp in a `pyfunc` or `wasm` model file equals the manifest model version | R16 |
| PJ014 | A `static` project's model version is `static-<number>` | R16 |
| PJ015 | A golden tolerance names an `FP64` signature output and gives a non-negative `absolute` or `relative` bound, or both | R5 |
| AC001 | A project that is not `static` holds an evaluation, and every required scalar output has a gating check in it | R14 |
| AC002 | A check names a known split, a name in the naming style, an output in the signature, a numeric or null value, a limit and direction, and a boolean gate | R14 |
| AC003 | The recorded outcome, budget and verdict follow from each check's value and limit, the evaluation holds dataset hashes for every split it uses, and a check with a measured value has at least one dataset recorded for its split | R14 |
| CP001 | A re-run of a `static` project writes the same manifest and file hashes as the committed one | R15 |
| CP002 | A re-run of any other project writes a signature with no difference from the committed one | R15 |
| CP003 | A re-run of any other project reaches the same acceptance verdict as the committed one | R15 |
| NB001 | The notebook is format 4 | R13 |
| NB002 | The notebook has no outputs and no execution counts | R13 |
| NB003 | The notebook has exactly one level-one title, `# <module> / <model> / <notebook>`, matching its directories | R13 |
| NB004 | The title table has the header Term and In This Notebook and the three rows in order, with a bold Term column | R13 |
| NB005 | The sections are the names of 6.7, in order, none deeper than level two, with Setup present | R13 |
| NB006 | Every section has Stage and Intent dot points | R13 |
| NB007 | A code cell has no magics, shell lines, absolute paths or literal secrets | R13 |
| NB008 | `WORKSPACE` and `MODEL_NAME` are the workspace and the registered name that 6.1 requires | R12 |
| NB009 | No table cell is bold outside the title table | R13 |
| NB010 | The notebook's `plan.md` exists | R13 |
| NB011 | A notebook imports from `library.<module>` by name and never with `*` | R13 |
| NB012 | A notebook does not extend `sys.path`, since the kernel carries it | R13 |
| PM001 | Promotion needs the parity gate to have passed for every host on every architecture | R5 |
| PM002 | The gate is for this project, by the SHA-256 of its `project.json` | R5 |
| PM003 | A person is named as the reviewer | R5 |
| PM004 | The project has an evaluation and every gating criterion passed, which `check_release` also applies to a consumer's `release` slot | R14, R15 |
| PM005 | The candidate is stamped with the next model version, and a `static` project is not promoted | R16 |
| PM006 | A release tag can be read to record as the service version | R16 |
| RP001 | A replayed step that expects a signature error does not supply every required input | R8 |
| RP002 | A replayed step supplies every required input | R8 |
| RP003 | A runtime reproduces every golden response exactly | R5 |
| RP004 | A runner gives a result row for a project it supports | R5 |
| RP005 | A runner reports no error replaying the golden | R5 |
| WS001 | The module, model and notebook directories follow the naming style | R12 |
| WS002 | A notebook directory holds exactly one notebook, named `notebook.ipynb` | R13 |
| WS003 | A notebook directory holds only the notebook, `plan.md`, `.version`, `data` and a model file | R13 |
| WS004 | The data directory holds only the four splits | R6 |
| WS005 | A split holds only timestamp directories | R6 |
| WS006 | A dataset is a csv named `<model>_<notebook>_...`, and one that is not `golden` ends with its date range | R12 |
| WS007 | A notebook directory holds at most one model file of `model.wasm`, `model.onnx` and `model.py` | R13 |
| WS008 | A `.version` file holds the model version in development as `<number>-SNAPSHOT` | R16 |

The identifiers, the flavors of 3.2, the splits of 6.3 and the sections of 6.7 are mirrored in code, and a test fails if the specification
and the code disagree in either direction.

### 10.2 Helpers

Common operations are in two places, so a notebook states what it means and not how it is done.

| Where | Helper | Does |
|---|---|---|
| `asystem.model` | `registered_name`, `check_name` | Derives a registered name from a model and a notebook, and checks the naming style |
| `asystem.model` | `build_signature`, `signature_input`, `signature_output`, `signature_state` | Builds `signature.json` with every field the checks need |
| `asystem.model` | `golden_step`, `golden_document`, `golden_from_samples` | Builds V2 requests and responses from named values or from dataset samples, with the datatype taken from the signature |
| `asystem.model` | `package_project`, `write_project` | Builds the golden from samples and writes the project with its evaluation, then runs every project check |
| `asystem.model` | `file_sha256`, `project_content_sha256` | Hash a file, and hash a project's content with the version stamp neutralised, so two registrations of the same content match |
| `asystem.model` | `lint_project`, `verify_project` | Reports or raises every finding of 10.1 |
| `asystem.model` | `register_project`, `pull_model` | Registers a project, stamping the next model version and logging its measured criteria as run metrics, and pulls one by selector |
| `asystem.model` | `stamp_model`, `read_stamp`, `content_sha256`, `restamp_project`, `next_model_version` | Write, read and hash the version in a model file, restamp a project copy, and issue the next number |
| `asystem.model` | `resolve_model`, `list_models`, `service_version`, `slot_versions` | Look up a model by selector, list the registry, read the latest release tag and list the versions in the consumer slots, through `resolve`, `list` and `status` |
| `asystem.model` | `diff_signature`, `same_signature` | Names every difference between two signatures apart from `versions`, which a failed pull reports |
| `asystem.model` | `render_rust`, `render_go` | Generate request and response types from `signature.json`, through `python -m asystem.model generate` |
| `asystem.model` | `measure`, `evaluate_acceptance` | Measures a prediction against its truth with numpy, and runs a notebook's acceptance check into `evaluation.json` with the outcome and budget of each check |
| `asystem.model` | `compare_project`, `check_release` | Compare a re-run with the committed project (CP001 to CP003), and check that a `release` slot's acceptance passed |
| `asystem.replay` | `replay_project`, `gate_project`, `merge_gates`, `model_predict` | Replay a project's golden through its runtime and compare every response exactly, write the gate file from the Python result and the Rust and Go runners (RP001 to RP005), merge the files of several architectures, and load a model file as a predict function, through `python -m asystem.model replay`, `gate` and `gate-merge` |
| `asystem.model` | `check_gate`, `check_acceptance`, `promote_project` | Check a parity gate file and the acceptance verdict, and set the alias `release` only when both pass |
| `asystem.notebook`, `asystem.workspace` | `lint_notebook`, `fix_notebook`, `lint_workspace` | Report the findings of 10.1 for a notebook or a workspace, and strip a notebook's outputs |
| `asystem.notebook` | `scaffold_notebook` | Writes a notebook, a plan and the data directories that already pass section 10, through `python -m asystem.notebook new <module> <model> <notebook> <flavor>` |
| `library.data` | `data_path`, `read_data`, `ensure_data`, `golden_data`, `query_influxdb3` | Resolves a dataset path, reads one, reads or writes a dataset when it is absent, and queries with the cache |
| `library.project` | `consumer_project_dir`, `scratch_project_dir`, `provenance`, `development_version` | Resolves a consumer's `default` or `release` slot, or the same under `MODEL_OUTPUT_DIR`, and builds `provenance` from data paths |
| `library.env`, `library.plot` | `init_env`, `show_plot` | Loads the module environment, and plots a series |

A notebook SHOULD use these helpers and MUST NOT reimplement them.

### 10.3 Coverage of the requirements

Each requirement is checked by the identifiers below, or by review where no tool can check it. A test fails if this table and the
Enforces column of 10.1 disagree.

| Requirement | Checked By |
|---|---|
| R1 | PJ001, PJ002, PJ003, PJ005, PJ006, PJ009 |
| R2 | Review |
| R3 | PJ010 |
| R4 | PJ010, PJ012 |
| R5 | PJ015, PM001, PM002, PM003, RP003, RP004, RP005 |
| R6 | WS004, WS005 |
| R7 | Review |
| R8 | PJ008, PJ011, RP001, RP002 |
| R9 | Review |
| R10 | PJ005 |
| R11 | Review |
| R12 | NB008, PJ004, PJ007, WS001, WS006 |
| R13 | NB001, NB002, NB003, NB004, NB005, NB006, NB007, NB009, NB010, NB011, NB012, WS002, WS003, WS007 |
| R14 | AC001, AC002, AC003, PM004 |
| R15 | CP001, CP002, CP003, PM004 |
| R16 | PJ013, PJ014, PM005, PM006, WS008 |
| R17 | Review |
