# Model Delivery Specification

## 1. Scope

This specification defines how a model is fitted, packaged, tested, registered and run in the estate, served in MLServer or embedded in
a Python, Rust or Go consumer. It applies to every model fitted in the `datascience` module. It contains nothing specific to a
single model. Each notebook keeps its plan with it, in `src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/plan.md`; the plan for the rackmains UPS battery model is `rackmains/ups/battery/plan.md`.

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
| Flavour | What a project holds and what runs it, as an MLflow flavour: `static`, `wasm`, `onnx` or `pyfunc` |
| Signature | `signature.json`, the MLServer V2 model metadata and the MLflow model signature: every input, output and state slot |
| Golden | Fixed requests and the exact responses they must produce |
| Workspace | The directory `src/main/notebook/<module>/<model>/<notebook>/` holding one notebook, its plan, its data and, for a flavour that has one, its model file. Several models sit under a module, and several notebooks under a model |
| Consumer | A service that calls a model, served or embedded |
| Served | Run by MLServer behind the V2 inference API |
| Embedded | Run in the consumer's own process |
| Split | One of `training`, `validation`, `backtest` or `golden`, naming the purpose of a dataset |
| Acceptance | The check a notebook defines and runs through the shipped runtime, whose outcome is recorded in `evaluation.json`, and which a project must pass to be released |
| Budget | A dimensionless score for an acceptance check, being how much of its limit the measurement used. Every check passes at a budget of 1 or less, whatever the model |
| Parity gate | Replay of golden sequences through every reference consumer a project's targets name, which MUST reproduce every response and state exactly or within the golden tolerance |
| Alias | An MLflow registry alias on a registered model: `preview` for the version under test and `release` for the live one (11.3). MLflow reserves `v<N>` and `latest` |

## 2. Requirements

| # | Area | Requirement | Rationale |
|---|---|---|---|
| R1 | Standard | Every model MUST have one signature, one project layout and one manifest of SHA-256 hashes, whatever its flavour | A consumer moves between served and embedded without change |
| R2 | Standard | The flavour MUST follow the model and MUST NOT follow the environment. The flavours are `static` (constants), `wasm` (formula or stateful, as a WebAssembly module), `onnx` (learned) and `pyfunc` (Python-only libraries, served or in Python, never embedded in Rust or Go) | The environment does not dictate the maths |
| R3 | Standard | Feature engineering MUST live in the project. A request MUST be one sample of numbers plus the state the caller carries. A consumer MUST NOT hold model logic | Recorded once at source, replayable |
| R4 | Parity | Every number reported or shipped for a project, the fit included, MUST come from the shipped runtime of its flavour. A faster proxy MAY choose the fit, and the runtime MUST then reproduce the result. Exploration MAY use plain Python | No gap between pre-prod and prod numbers |
| R5 | Parity | A project MUST NOT be released until its acceptance has passed, every target declared in its metadata has passed its system test on the local architecture, and a person has run `fab release`, which is the review | A mismatch is caught before it ships |
| R6 | Parity | Every dataset MUST be held under exactly one split, with each run wholly in one split. Held-out data MUST NOT be used to fit | An error estimate stays honest |
| R7 | Delivery | A serving runtime MUST poll the registry, serve the newest verified `release` of every model, fall back to the next most recent verified release when the newest cannot be used, and never stop serving a working model because another failed. An embedded consumer MUST take its project from the committed `datascience` tree, and a release MUST NOT ship a project that differs from it | A served model is a verified release, and an embedded one is exactly the committed one |
| R8 | Delivery | A consumer MUST validate a project at load and MUST NOT use an invalid one, and MUST NOT depend on a served model. There is no fallback project: a consumer whose model is broken is broken, and its build and tests are what catch it. A served model that is down is down | A bad project never answers |
| R9 | Delivery | Every decision MUST record the content hash of the project that produced it, and a served decision also the `model_version` label of the answer | Any outcome can be traced and replayed |
| R10 | Change | A change of behaviour, being a new WebAssembly ABI version, a runtime or engine version or a breaking signature change, MUST be a code release of the runtime and its consumers, and a breaking signature change MUST be a new model name. A refit MUST replace only the model file and the hashes that cover it | A refit changes data, a release changes behaviour |
| R11 | Change | Every runtime library MUST be pinned by version. Any upgrade MUST re-run `fab systest` | Parity holds only while the runtimes do not move |
| R12 | Standard | Every name MUST follow section 6.1: lowercase `<module>_<dimension>` style with a unit suffix on numeric measures | A name tells you the owner and what is measured |
| R13 | Standard | Every project, notebook and workspace MUST pass the checks of section 10 | The requirements are enforced by tools and not by reading |
| R14 | Parity | A project that is not `static` MUST carry an evaluation from an acceptance check its notebook defines, run through its shipped runtime, and MUST NOT be given the alias `release` unless every gating check has passed | Every model is enforced against its own limits, and the outcome is recorded the same way for all |
| R15 | Parity | A notebook MUST run through its Package section from committed data, and a re-run MUST write the project its `metadata.json` hashes describe. A gate that is not met MUST fail the run, and a project whose acceptance failed MUST NOT be released | A notebook is evidence anyone can reproduce, and every gate fails loudly where it is not met |
| R16 | Standard | A project MUST be version-free and content-addressed. Its release version is a label in `metadata.json` and in registry tags, issued as the release version of the `fab release` that changed its inputs, and an unchanged project MUST keep its label | The artifact that was tested is the artifact that ships |
| R17 | Standard | The registry MUST be written only through `asystem.model`, from `metadata.json` and the project, and never read back for a decision except by a serving runtime choosing what to load. A serving runtime MUST refuse a model whose evaluation did not pass | The registry is a mirror of git |

## 3. Project

### 3.1 Files

A project is a directory read the same way by every environment and written and checked by `asystem.model`.

| File | Flavours | Content |
|---|---|---|
| `project.json` | All | Spec version, name, model version, signature version, `flavour`, provenance, the SHA-256 of every other file, optional constants, and for `wasm` and `pyfunc` the `runtime` (3.5) |
| `signature.json` | All | The MLServer V2 model metadata, which is also the MLflow model signature. It MUST be identical in the project, the consumer and the logged MLflow model, apart from its `versions` list |
| `golden.json` | All | Named sequences of requests and responses, each request carrying the previous response's state. A response is exact unless the file states a tolerance for an `FP64` output |
| `evaluation.json` | All but `static` | Each acceptance check with its measured value, limit, outcome and budget, the SHA-256 of each dataset used, the verdict and the worst budget, specified in 6.8 |
| `model.wasm` | `wasm` | The WebAssembly module, with its fitted attributes built in |
| `model.py` | `pyfunc` | The Python model, in MLflow's models-from-code form |
| `model.onnx` | `onnx` | The ONNX model at a pinned opset |
| `MLmodel`, `artifacts/*` | `pyfunc` | The MLflow model descriptor, written when the project is logged, with the project files carried under `artifacts/` |

The manifest's provenance `implementation` MUST name what is inside the container for every flavour but `static`: the builder of a `wasm` module, the converter and opset of an `onnx` graph, or the pinned requirements of a `pyfunc` model. The manifest's provenance `source` MUST be `static`, `manual` or `mlflow`, and `provenance.inputs` MUST list the data files used. A
manifest MAY carry `constants`; they MUST name signature outputs and are merged into every response.

A golden step MUST have either a `response` or an `error`. An `error` of `signature` means the request does not satisfy the signature, because a required input is
missing, and the model MUST refuse it.

### 3.2 Flavours

| Flavour | What It Is | Model Logic Lives in | Learns from Data? | Carries State? | Runs Where | Use When |
|---|---|---|---|---|---|---|
| `static` | Constants and nothing else | The manifest's `constants` | No | No | Everywhere, with a plain loader | Constants and tunables that are reviewed and versioned |
| `wasm` | A WebAssembly module | `model.wasm` | Fitted offline, attributes built in | Yes, a fixed-length vector | Python, Rust, Go and served, through a WebAssembly host | A formula, curve, lookup, integrator, decay or latch |
| `onnx` | An ONNX model file | `model.onnx` | Yes | Optional | Python and served (`onnxruntime`), Rust (`ort`), Go (`onnxruntime_go`) | A tree, regression or small network from scikit-learn, XGBoost and the like |
| `pyfunc` | An MLflow Python model | A Python class and its libraries | Yes | Optional | Served in MLServer, or in Python; never Rust or Go | A library with no converter, or arbitrary Python |

### 3.3 Requirements per flavour

`static`
- MUST have no model file: the constants are the manifest's `constants`, declared in the notebook's Setup section.
- MUST answer the same constants for every valid request, MUST give a constant for every required output, and MUST still validate the request.
- MUST be written with `write_project` like any other flavour, and released and embedded through the same path.

`wasm`
- MUST satisfy the ABI and the determinism rules of section 4, float64, one numeric sample in and a fixed-length state.
- MUST NOT use strings, timestamp parsing or variable-length windows.
- MAY import the maths functions of 4.1, and MUST state a golden tolerance for every output that depends on one (4.2).
- MUST record the hash of `model.wasm` in the manifest, and MUST be committed beside the notebook as `model.wasm`.

`onnx`
- MUST be committed beside the notebook as `model.onnx`.
- MUST pin the opset and use one allow-listed operator set, float64 where each engine has a kernel.
- MUST NOT use an operator over a variable-length input.
- MUST use the same `onnxruntime` shared library everywhere it can, pinned by version.

`pyfunc`
- MUST be written as `model.py` beside the notebook, in the form MLflow calls models from code (`set_model`), and logged with `mlflow.pyfunc.log_model`, with the project in `artifacts` and a signature built from `signature.json`.
- MUST declare every package its `model.py` imports beyond the Python standard library and the base packages (`mlflow`, `numpy`, `pandas`), as `runtime.python` (3.5), and MUST NOT declare one it does not import.
- MUST NOT be embedded in Rust or Go.

### 3.4 Versions

A project carries no version. Its identity is the SHA-256 of its `project.json`, and its release version is a label in `metadata.json` and the registry tags (11.2, 11.3). A served model is loaded as `release` only, so an unversioned call reaches it.

### 3.5 Runtime dependencies

A project states what a runtime must provide beyond the base, so a missing dependency is a finding at build time and not a failure when a model is first served. The manifest carries it as `runtime`, which is part of `project.json` and so of the content hash, and `metadata.json` repeats it.

| Flavour | `runtime` | Source | Runtime provides |
|---|---|---|---|
| `static`, `onnx` | None, and a manifest that carries one is a finding | | `static` needs only the loader, and `onnx` needs `onnxruntime` and its allow-listed operators, which a graph cannot extend |
| `wasm` | `{"wasm": [<import name>, ...]}` | Derived from the module's imports by `write_project`, never written by a notebook | The six `asystem_math` functions of 4.1, which every host provides, so the list is a record and a check that equals the module and is never installed |
| `pyfunc` | `{"python": [<package>, ...]}` | `PYTHON_DEPS` in the notebook's Setup cell, passed to `package_project` as `python_deps` | The base packages `mlflow`, `numpy` and `pandas`, plus the declared packages |

- A `python` entry is a package name and never a version. Its version is the one global pin in the root `py_deps_prod.txt`, the same pin `fab` gives every module that lists the name in its `py_deps.txt` (R11), and a name with no pin fails the Package stage. Names are matched ignoring case and `-`, `_` and `.`.
- A `python` list is sorted and unique, and excludes the standard library and the base packages. Lint (PJ017) reads the imports of `model.py` and fails in both directions: an import with no entry, and an entry nothing imports. A package whose import name differs from its package name (`scikit-learn` and `sklearn`) is matched through a short table in `asystem.model`.
- `fab systest` installs the base pins and every workspace's declared packages at their global pins into the test image, so an embedded Python target fails if the list is incomplete. For a `served` target, MD005 requires every declared package to be named in `mlserver`'s own `py_deps.txt`, from which `fab generate` writes its pins from the same global file, so the served image carries exactly the version the notebook was tested against.
- Adding a dependency is a change of behaviour (R10), made in this order: add the package to the project wide pins, add its name to `mlserver`'s `py_deps.txt` (no version, since `fab generate` pins it), then release `mlserver`, add the name to `PYTHON_DEPS`, and rerun the notebook, which changes the content hash. A consumer that embeds the project in Python adds the same names to its own `py_deps.txt`. A Rust or Go consumer never embeds a `pyfunc`, and needs for a `wasm` project only the six functions of 4.1.

## 4. WebAssembly models

A `wasm` project is a WebAssembly module, `model.wasm`, that satisfies one ABI. Python, Rust and Go run the same bytes in a WebAssembly
host and produce the same numbers. The specification fixes the ABI and the determinism rules; how a module is made is the choice of the
project that needs it. A module is hand-written, or produced by `build_wasm` in `workbench`, which writes a compiled module per model from a small expression tree (constants, features, named intermediate values, arithmetic, `min`, `max` and a select on a comparison) and compiles it with `wasmtime`. A notebook builds the tree with the helpers of `workbench.wasm`, such as `add`, `mul`, `lt` and `select`. The
manifest's `provenance.implementation` names what made it, and no implementation has a name in this specification.

### 4.1 ABI

- A module MUST export `predict`, as a scikit-learn estimator does. It takes `X` of shape `(n_samples, n_features)` and returns `y` of shape
  `(n_samples, n_outputs)`, both float64 (`FP64`). The features are the signature's scalar inputs followed by the elements of the state input, and the outputs are
  the signature's scalar outputs followed by the elements of the state output, each in signature order.
- Samples are independent, so `predict` holds no state between calls and the caller carries state from each response to the next request (R3).
- A module is a fitted estimator. `fit` is not part of the ABI: fitting is offline, and the fitted attributes are built into the module.
- A call MUST be bounded in time and memory. A host MUST meter fuel and cap memory.
- A module MUST import nothing from its host except the maths functions `atan`, `cos`, `exp`, `log`, `sin` and `tanh`, each imported from the module `asystem_math` with the type `(f64) -> f64`. A host that runs a module MUST provide all of them, and they MUST give IEEE results for a value outside the domain: `log(0)` is negative infinity, `log` of a negative value and `sin` of an infinity are NaN, and an overflowing `exp` is positive infinity. The Python host (`wasmtime`, in `asystem.replay` and the `run_wasm` files, which `mlserver` carries), the Go host (`wazero`) and the Rust host (`wasmi`) provide them from their standard libraries, and a module that imports any of them can be run only by a host that does.
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
| Flavour | The estimator class | `implementation` in `model-settings.json` | A flavour |
| Signature | The shape of `X` and `y` | Model metadata | The model signature |
| Project | A fitted estimator | A model | A logged model |

### 4.2 Determinism

- A module MUST use float64 (`FP64`) only, and MUST NOT use relaxed SIMD, threads or any operation with a result that differs between CPUs.
- A function with no exact cross-platform result is imported from `asystem_math` (4.1), and each host calls its own maths library, so its result MAY differ between hosts in the last bits. A golden tolerance MUST be stated for every output that depends on one. A model MUST NOT branch on the result of such a function where a difference in the last bits would change the branch taken, or MUST use a lookup table or a polynomial built from basic operations in its place.
- The golden sequences and the parity gate prove it: the module MUST reproduce every response and state exactly in every reference consumer a target names,
  except for an output with a stated tolerance.
- A tolerance is stated in `golden.json` as `"tolerance": {"<output>": {"absolute": <a>, "relative": <r>}}`, for an `FP64` output only, with either bound or both. A value
  matches when it differs from the golden value by no more than `absolute + relative * |golden value|`, and an `INT64` output and any output without a tolerance match exactly.
  A learned `onnx` graph, whose float32 kernels differ between CPUs, MUST state one, and a notebook SHOULD choose the smallest bound its own error on `validation` allows
  and say why in its plan. The same rule applies to every runtime of the gate, so it cannot be loosened for one host.

### 4.3 Requirements

- Each project MUST record the hash of its `model.wasm`, so every host runs the same bytes.
- A new ABI version or a new host runtime version MUST be a code release of the runtime and every consumer (R10). A refit replaces `model.wasm` only.
- The builder is `workbench.wasm.build_wasm` in the `datascience` module. Third-party libraries fit the numbers that go into the module, and the fitted values are built in as constants.

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
| statsmodels, Prophet | No | No | Yes: served or in Python | No ONNX converter is known |
| JAX, MLX | Maybe: train with it, then export the weights of a small net (linear layers, an MLP) into a module's matrix and activation code, using the imported `tanh` and `exp` with a stated golden tolerance, or lookup tables or polynomials | No | Maybe: a custom `pyfunc`, served or in Python, with a `static` floor | JAX converters are fragile and MLX has no exporter, so neither ships as `onnx`; bigger models are retrained in PyTorch or scikit-learn; nothing Metal-specific ships |

A library marked No under a flavour MUST NOT ship in that flavour; training in it is permitted. A runtime SHOULD be the smallest that runs
its flavour: `static` needs none, `wasm` needs one small host per language, `onnx` needs an engine.

### 5.3 Notebook tooling

| Need | Yes | No |
|---|---|---|
| Run a Notebook | `jupyterlab` and `nbconvert --execute` through `notebook.sh`, kernel `asystem` | The Conda Python, which lacks the dependencies |
| Parameterise a Headless Run | `papermill`, once pinned | Editing cells to change inputs |
| Review a Notebook Diff | Commit without outputs, or pair with `jupytext` | Committing large embedded outputs |
| Check Every Notebook | `fab unittest`, which runs `model.sh unittest` | Trusting a committed project nobody has reproduced |
| Refresh Served Models | The `mlserver` sync loop (11.4) | Restarting the whole `mlflow` image to change a model |
| Write the Registry | `register_preview` and the `datascience` release function only (R17) | Hand edits of versions, aliases or tags in the MLflow UI |
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
| Registered Model | `<module>_<model>_<notebook>`, also the name `mlserver` serves it under | `rackmains_ups_battery`, `weewx_console_battery`, `weewx_forecast_roof`, `homeassistant_hotwater_temp`, `example_static_constant` |
| Dataset | `<model>_<notebook>_<dimension>...`, ending `_<start>_<end>` with the first and last date it covers unless it is `golden` | `console_battery_voltage_2024-06-06_2024-10-25`, `ups_battery_golden` |
| Signature Input | The owning service's metric name, unchanged | `weatherstation_console_battery_voltage` |
| Signature Output, State Slot or Constant | `<module>_<dimension>...` with a unit suffix | `weewx_console_battery_capacity_pct`, `rackmains_battery_remaining_seconds` |
| Model Plan | `plan.md` in the notebook directory | `rackmains/ups/battery/plan.md` |
| Split | One of `training`, `validation`, `backtest`, `golden` | `training` |
| Project Flavour | The lowercase flavour value | `wasm` |
| Timestamp | `YYYY-MM-DD_HH-MM-SS`, Perth time | `2026-10-31_15-17-42` |

### 6.2 Layout

```
src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/notebook.ipynb
src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/plan.md
src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/metadata.json
src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/project/
src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/model.<wasm|onnx|py>
src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/data/<split>/<timestamp>/<dataset>.csv
```

- `<module>`, `<model>` and `<notebook>` MUST be named as section 6.1 requires.
- A notebook directory MUST hold one notebook named `notebook.ipynb`, its `plan.md`, its `metadata.json` and `project/` once released, its `data` and at most one model file (`model.wasm`, `model.onnx` or `model.py`, as the flavour requires), and nothing else. The data belongs to
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
| `src/rue/datascience/target/notebook/<module>/<model>/<notebook>/notebook.ipynb` | An executed notebook | `notebook.sh`; not committed | A person reading the run |
| MLflow Run and Registered Model `<name>` | The logged project and the aliases `preview` and `release` | The notebooks' register function sets `preview`; the `datascience` release function sets `release` | The `mlserver` sync loop, and a system test through `<name>_preview` |
| `<consumer>/src/build/resources/model/` | The embedded copy of the released `project/`, committed | The consumer's `generate.sh`, through `python -m asystem.model embed` | The consumer's build, tests and image |
| `/asystem/mnt/models/<name>/` in `mlserver` | The served copy of the `release` project | `mlserver`'s start-up pull | The serving runtime |

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
- MUST declare the model name, version and dataset names as constants in the Setup cell, and for a `pyfunc` also `PYTHON_DEPS`, the packages its `model.py` imports beyond the base (3.5).
- MUST fit only on `training`, and MAY load `validation` to check the fit.
- MUST write its golden inputs and expected outputs under the `golden` split and build `golden.json` from that file.
- MUST list the data files used in `provenance.inputs`.
- SHOULD keep logic in `workbench` and keep cells thin.
- MUST run with the `asystem (Python 3.12)` kernel, never the Conda Python.

### 6.7 Notebook style guide

**File**
- A notebook MUST be Jupyter notebook format 4 and MUST be committed without outputs and without execution counts. Committed outputs bloat
  diffs, can leak data and are not reproducible.
- A notebook MUST NOT contain secrets, absolute paths or notebook magics. Paths MUST come from `data_path` and `NOTEBOOK_DIR`.
- A notebook MUST be deterministic: a random operation MUST use a fixed seed.

**Cell order**
1. The title cell, a markdown cell.
2. One markdown section cell per section, each followed by the code cells of that section.

**The title cell**
- MUST hold the heading `# <module> / <model> / <notebook>`, the only level-one heading in the notebook.
- MUST follow it with one line stating the notebook's intent.
- MUST then hold a table with the header Term and In This Notebook and one row for each of Intent, Project Flavour and Data Splits, in that
  order. Each row uses the terms of this specification and cites its section where one applies.
- MUST bold only the Term column of that table. It is the one place a bold cell is used.

**Sections**
- A section heading MUST be level two, `## <Section>`, in Title Case, and MUST be one of the names below, in this order. A section that
  does not apply MUST be omitted and the order kept.

| Section | Stage (7.1) | Required | What It Holds |
|---|---|---|---|
| Setup | None | Always | The `workbench` imports, `env` and the constants |
| Capture Data | 1 | When the notebook reads data | Queries and loads, through `query_influxdb3` and `data_path` |
| Explore | 2 | May | Plots and checks; nothing reported from it ships (R4) |
| Fit | 3 | When the model is fitted | The fit, on `training` only (R6) |
| Evaluate | 4 | When the model is fitted | Checks on `validation` and `backtest` through the shipped runtime |
| Package | 5 | Always | The golden file, the signature, `write_project` and `verify_project` |
| Register | 6 | When the project is registered | `register_project` with the alias `preview`, run by `fab systest` and never by `fab unittest` |
| Pull | 8 | Where a round trip is tested | `pull_model` and the comparison with what was registered |

- A section cell MUST hold the heading and two dot points: `- **Stage:** <number>, <stage name>` (or `none` for Setup) and
  `- **Intent:** <one sentence beginning with a verb>`.
- A section Intent SHOULD cite the requirement or section it serves, such as (R6) or section 6.5.
- A section MUST NOT use a heading deeper than level two.
- A code cell MUST do one thing, and SHOULD be no longer than a screen.

**Code**
- A notebook MUST import from `workbench.<module>` by name, never with `*`, and MUST NOT extend `sys.path`. The kernel carries the
  `PYTHONPATH`: `notebook.sh` installs it and the IDE source roots provide it.
- Python MUST be formatted with `ruff format` at the repo line length of 200 and MUST NOT be hand-wrapped; the formatter decides the layout.
- Constants MUST be UPPER_CASE (`WORKSPACE`, `MODEL_NAME`, `TRAINING`, `VALIDATION`, `GOLDEN`). A notebook MUST NOT carry a flag
  that switches the network on, since `query_influxdb3` reads the committed file when it is present (6.5).
- MUST run through its Package section from committed data (R15). The Register section, and anything after it, writes to the registry, and a check must not write, so `notebook.sh` stops before it
  unless `REGISTER=1`. An acceptance that fails is recorded as the verdict and does not stop the run.
- MUST write its project only through `scratch_project_dir`, which `model.sh` redirects to `target/model-output` with `MODEL_OUTPUT_DIR`, and never into a consumer's tree.
- A polars frame SHOULD be named with the suffix `_pl` and a path with the suffix `_path`.
- Imports SHOULD sit at the top of the cell that first needs them.
- A comment MUST NOT restate the code; narrative belongs in the section's markdown cell.

**Lint**

`fab build` lints every notebook under `src/main/notebook/*/*/*/` the way it lints Python, and rewrites the source:
- `ruff check --fix` and `ruff format` run on the code cells, with the repo `ruff.toml`. E402 is ignored in notebooks, because an import sits at the top of the cell that first needs it, not of the notebook.
- `python -m asystem.notebook --fix` strips outputs and execution counts and checks the notebook rules of section 10. The executed copy
  is kept under `target/notebook`, never in the tree.
- `python -m asystem.workspace` checks each workspace against the rules of section 10.
- `ruff check --fix` and `ruff format` also run on a workspace's `model.py`, which is not type checked.

A finding other than NB002 fails the build. Notebooks are not type checked, since `pyright` does not check `.ipynb` files from the command
line. Notebooks are not run by `fab build`; `notebook.sh` runs one headless, and `model.sh unittest` runs them all.

**Markdown**
- Identifiers, paths, commands and values MUST be in backticks.
- A table MUST have a Title Case header and Title Case first-column labels, and each other cell MUST begin with a capital.
- A table MUST NOT bold a cell, except as the title cell requires.

### 6.8 Acceptance

A gate that is not met raises (11.5), so a failed acceptance fails the run as well as blocking the release.

Each notebook owns what its model must achieve and how it is measured, and the library enforces that it was done and records the outcome the same way for every model type. This mirrors the golden builder: the notebook defines a function with no arguments, as `golden_samples` is for `golden_data`, and the library validates and stores what it returns.

- A notebook of a non-`static` flavour MUST define `acceptance_checks()`, measure the shipped model on `validation` or `backtest` data inside it, and return a non-empty list of checks. It passes the function and the dataset paths to `evaluate_acceptance(check, datasets)`, then hands the result to `package_project` as `evaluation`. A project without one fails AC001.
- A check is `split` (`validation` or `backtest`), `output` (a signature output), `name` (the naming style), `value` (a number, or null when it could not be measured), `limit`, `direction` (`max` for a value that must not exceed the limit, `min` for one that must not fall below it) and optionally `gate`, which defaults to true. A `training` check does not exist, since the fit is not judged on its own data, and `golden` is judged by exact parity.
- The library, not the notebook, decides the outcome: a check passes when its value is within its limit, and a null value fails. `measure(truth, predicted)` is an optional helper with the scikit-learn names `rmse`, `mae`, `max_abs_error`, `bias`, `p95_abs_error`, `r2` and `pearson_r`. A notebook MAY compute anything else, such as a one-sided error, a recall or a worst run.
- Every required scalar output MUST have a gating check. A `backtest` check SHOULD gate, and a `validation` check gates only for a model with no `backtest` run yet, which its plan MUST say.
- The budget is the standard score, the same for every model type: for a `max` check it is the value divided by the limit, floored at zero, and for a `min` check it is the limit divided by the value. A check passes exactly when its budget is 1 or less. The evaluation records the worst budget of the gating checks, or null if any gating check could not be measured. A lower budget means a larger margin. It compares a model with its own limits, not one model's accuracy with another's.
- `register_project` logs the run metrics `acceptance_passed` (1 or 0) and `acceptance_budget`, each measured value as `<split>/<output>/<name>`, each dataset with `mlflow.log_input` under the split as its context, and the tags `acceptance` and `acceptance_budget`. The release function copies both tags onto the released version.
- `evaluate_acceptance` prints the standard line `acceptance [passed|failed] budget [<worst budget>]` and then raises when a gating check failed, so a failed verdict is visible in a log and the run still fails.
- The limits live in the notebook's function, so a changed limit is a change to that notebook, and the release review reads that diff. A notebook owns its limits, and a limit loosened there is accepted unless a review catches it: no tool compares limits between versions. The evaluation does not need to say what was required, only that the enforced checks passed.

### 6.9 Worked examples

The module `example` holds one hello-world project for each flavour. Each is fully worked, with a notebook, a plan, data under every split,
an acceptance check and a golden file, and each is replayed in every runtime that supports its flavour. A new flavour, runtime or runner SHOULD be
tried on these first.

| Notebook | Flavour | Shows | Python | Rust | Go |
|---|---|---|---|---|---|
| `example/static/constant` | `static` | A constant and the register and pull path | Yes | Yes | Yes |
| `example/wasm/accumulate` | `wasm` | A fitted line built into a module, with a state vector | `wasmtime` | `wasmi` | `wazero` |
| `example/wasm/saturate` | `wasm` | A fitted `tanh` curve whose module imports `tanh` from the host, so `runtime.wasm` is `["tanh"]` and the golden states a tolerance | `wasmtime` | `wasmi` | `wazero` |
| `example/onnx/linear` | `onnx` | A fitted line as a graph at a pinned opset | `onnxruntime` | `ort` | `onnxruntime_go` |
| `example/pyfunc/linear` | `pyfunc` | A fitted line as a `PythonModel` | `mlflow.pyfunc` | No | No |

The Rust and Go runtimes are the reference consumers under `src/main/python/consumer`, `src/main/go/consumer` and `src/main/rust/consumer` in the `datascience` module (11.8). Each takes a project directory, checks each file against the hash in `project.json` (PJ003), replays its golden
exactly or within the golden tolerance, and exits 0, or exits 1 on a difference or a flavour it does not support.

## 7. Lifecycle

### 7.1 Model lifecycle

| # | Stage | Who Runs It | Command or Hook | Output | Gate to the Next Stage |
|---|---|---|---|---|---|
| 1 | Capture data | Notebook | `query_influxdb3(...)`, or a file saved with `data_path` | `data/<split>/<ts>/<name>.csv` | The split is right and each run is wholly in one split |
| 2 | Explore | Notebook | Plain Python | Ideas, plots | None |
| 3 | Fit | Notebook | A builder (`wasm`), `skl2onnx` (`onnx`), `model.py` (`pyfunc`) | Fitted attributes | Fit error on `training` is sane |
| 4 | Evaluate | Notebook | Shipped runtime over `validation` and `backtest` | Metrics, `evaluation.json`, golden sequences | Every gating acceptance check passes |
| 5 | Package | Notebook | `package_project`, `record_project` | `project/` and `metadata.json` in the workspace | Manifest, hashes, signature and golden agree, and the signature only grew |
| 6 | Register | Notebook | `register_preview(...)` | A registry version with the alias `preview`, for a project with a `served` target | The registry shows it with its tags |
| 7 | Test targets | `fab systest` | 11.5 | The targets that passed, in `metadata.json` | Every declared target passed |
| 8 | Release | `fab release` | 11.6 | The release version in `metadata.json`, `release` moved, `preview` removed | The label is `READY` in the production index |
| 9 | Embed | The consumer's `generate.sh` | `python -m asystem.model embed <consumer dir> <source dir> <name>` | The released `project/` copied unchanged into the consumer's `src/build/resources/model/`, unstaged | The hash of the copy equals `content_sha256` in the workspace's `metadata.json` |
| 10 | Release the consumer | A person | The consumer's own `fab release` | A release of the consumer | `check-release` and the consumer's own tests |

### 7.2 Fab lifecycle

Each task includes the ones before it.

| `fab` Task | Model Hook |
|---|---|
| `generate` | Each consumer's `generate.sh` embeds the released project and verifies it. No notebook runs |
| `build` (Default) | The loader compiles against the signature |
| `unittest` | `model.sh unittest` runs the notebooks to Package and writes `project/` and the hashes (11.5), then the unit tests of every module |
| `systest` | `model.sh systest` registers the previews, then the system tests run, `datascience`'s against the production services (11.5) |
| `package`, `execute` | None for `datascience`, whose `Dockerfile` is a test environment |
| `release` | `check-release` on a consumer's embedded project, then `model.sh release <version>` for `datascience` (11.6) |
| `pull` | Backs up git-ignored files, `git pull --all` and installs the pinned dependencies. It does not pull models |
| `deploy` | `datascience`'s `deploy.sh` runs `model.sh publish` and `status` |

### 7.3 Consequences

- Builds do not call MLflow. Only `datascience` writes to it, and `mlserver` and the system test read from it.
- A served model is taken from the registry by the sync loop, so moving the alias changes what is served without a consumer release. An embedded
  consumer needs the embed, a commit and its own release.
- A breaking signature change is a new model name, served side by side while consumers move.

## 8. Procedure: adding a model

1. Pick the flavour from section 3.2.
2. Create `src/rue/datascience/src/main/notebook/<module>/<model>/<notebook>/` with `python -m asystem.notebook new`, and name it as section 6.1 requires.
3. Write the signature with `build_signature`, `signature_input`, `signature_output` and `signature_state`. An input name MUST be a metric name
   from its owning service, required outputs MUST be the ones the consumer cannot act without, and state slots are numbered in order.
4. Put data under splits, with `query_influxdb3`, `read_data`, `golden_data` or `data_path`.
5. Write the notebook to sections 6.6 and 6.7, and fit on `training`.
6. Evaluate on `validation` and `backtest` through the shipped runtime, define `acceptance_checks` to section 6.8 and run it with `evaluate_acceptance`, and generate the golden sequences from it. The golden sequences
   include a first call with no state, boundary values, a missing input that gives a signature error and a long gap. Build each step with
   `golden_step` and the document with `golden_document`.
7. Package with `package_project` and `record_project`, which copy the model file and the evaluation into the project, run `verify_project` and so every project check of section 10, and write `project/` and `metadata.json` with the targets the project is for.
8. Run `fab unittest`, read the diff, and commit. Run `fab systest` to test each target, and `fab release` to release (11.5, 11.6).
9. For an embedded consumer, add the embed to its `generate.sh` as in section 8.1, load the project through the reference consumer of its language and flavour (11.8), and carry the state between calls and
   record the project hash wherever a decision is logged.
10. To refit, put new data under splits, fit and repeat steps 6 to 8. The signature MUST only grow. A served rollback is `fab deploy` in the module after reverting; an embedded rollback reverts the project in the tree and releases the consumer.

### 8.1 The consumer's `generate.sh`

`<name>` is the registered model and `<dir>` the consumer's model directory, normally `src/build/resources/model`. The consumer holds one copy, the released
`project/` of the workspace, and no other. A signature that grows additively is picked up by the next embed, and the consumer is rebuilt against it.

```bash
export PYTHONPATH="${ROOT_DIR}/../../all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}"
python -m asystem.model embed "${ROOT_DIR}" "${ROOT_DIR}/../.." <name>
[ ! -f "<dir>/project.json" ] || python -m asystem.model verify "<dir>"
```

The pull needs `MLFLOW_TRACKING_URI` in the environment, read from the generated `.env`, which carries it from the `mlflow` run dependency. Every command MUST do nothing
harmful when no model is registered or no project exists yet.

## 9. Module requirements

MLflow owns data and lifecycle, MLServer only serves, and nothing is shared by a mount.

| Thing | Where | Requirement |
|---|---|---|
| Notebooks and Their Data | `datascience` module, `src/main/notebook/<module>/<model>/<notebook>` | Fitting and registering MUST sit in the `datascience` module, apart from the tracking and serving containers; notebooks MUST be thin |
| The `library` Package | `datascience` module, `src/main/python/workbench` | MUST have one module per concern (`config`, `env`, `data`, `project`, `plot`), an `__init__.py` holding only the shared path, and no logic in notebooks that belongs here |
| Project Code | `_` module, `asystem.model` | One implementation, unit tested, and also a command: `python -m asystem.model` |
| Tracking DB, Registry, Artifact Storage | `mlflow` only | MUST run `--serve-artifacts` with `--artifacts-destination` on its own volume and `--default-artifact-root mlflow-artifacts:/`, so no client writes a path or needs a share |
| Allowed Hosts | `mlflow` `.env_all` | MUST set `--allowed-hosts` and `--cors-allowed-origins`, since MLflow 3 rejects an unknown `Host` header |
| Models in `mlserver` | A local volume | MUST be pulled by the sync loop (section 11.4), MUST replace a model only after its new copy verified, MUST NOT stop serving on a failed pull, and MUST bound every call with a timeout |
| Embedded Copies | The consumer's tree | MUST be pulled by the consumer's `generate.sh`, reviewed as a diff, and never fetched at build or run time |
| Server Start | `mlflow` entrypoint | MUST run under `exec` with `pipefail`, and a failed `mlflow db upgrade` MUST stop the start |
| Bootstrap and Checks | `mlflow`, `mlserver` | `bootstrap.sh` runs in a separate `<name>_bootstrap` container, so any probe in `checkalive.sh` MUST address the service by `${<NAME>_SERVICE}:${<NAME>_HTTP_PORT}` and never `localhost`, which `checkexecuting.sh` and `checkhealthy.sh` may use only for checks that run inside the service container |
| Serving Start | `mlserver` | `checkalive` MUST be `/v2/health/live`, `checkexecuting` MUST add `/v2/health/ready`, and `checkhealthy` MUST add that every model in `/v2/repository/index` is `READY`, each through `${MLSERVER_SERVICE}:${MLSERVER_HTTP_PORT}` |
| Serving Runtime | `mlserver`, `serving` | MUST load a project only after every file matches its manifest hash and its acceptance passed; MUST write `model-settings.json` (name, the release label, signature) and a `settings.json` fixing the container ports; MUST answer `/v2/models/<name>/infer` for every flavour with the same outputs as `replay`; MUST refuse a request missing a required input. It is self-contained, since the image carries no `asystem` library, so a unit test MUST compare it with `replay` per flavour |
| Serving Release | `mlserver` | A promotion MUST need neither a release nor a restart of `mlserver`: the sync loop loads it within one poll interval, and `healthy` MUST mean every model in the repository index is `READY`. The `<name>_bootstrap` container only reports what is served |
| Artifact Upload | `nginx` proxy for `mlflow` | MUST accept a request body large enough for a project and its model file, through `MLFLOW_HTTP_MAX_BODY` in `mlflow`'s `.env_all` and the generated `client_max_body_size`, since the proxy's default cap of 25k refuses a `golden.json` with `413` |
| Telemetry | `mlflow`, `mlserver`, scripts | MUST be off: `MLFLOW_DISABLE_TELEMETRY=true` in `mlflow`'s `.env_all`, which every dependent inherits, passed through each compose file and exported by `model.sh` and `notebook.sh` |
| Registry Address | Every client | MUST use the proxy name from `MLFLOW_TRACKING_URI`; the published `host:port` answers `/health` only and returns `403 Invalid Host header` elsewhere, and a client MUST report that as a finding |
| Declared Models | `mlserver` | There MUST be no list of served models: every registered model carrying the datascience tags and an alias `release` or `preview` is served |
| Serving Smoke Test | `fab test-sys` in `mlserver` | MUST wait on `mlserver_bootstrap` like the other modules, read the port and registry address from the generated `.env`, and, once models are registered, MUST start with the `example` models, replay each project's `golden.json` through `/v2/models/<name>/infer` and fail on a model that is not `ready` or whose served label differs from its release label |
| Status and Rollback | `model.sh` | `status` MUST read without writing and show each model's release label, aliases, hashes and whether it is `READY` on `mlserver`. A rollback is a revert in git followed by `fab deploy` in the module |
| Health | Both services | MUST be real checks with every `curl` bounded; `mlflow` healthy MUST also read the registry and experiments API |
| Shutdown | Both services | MUST have a stop grace period |

## 10. Checks

A project, a notebook and a workspace MUST pass the checks below (R13). Each check has an identifier, which the tool prints with its
finding. A project is checked by `verify_project`, which `write_project`, `package_project`, `register_project` and `pull_model` call, and by
`python -m asystem.model verify` and `python -m asystem.model lint`, which prints every finding. A release is checked by `check_release`, which `fab release` runs through `check-release` for a consumer and `model.sh release` for a workspace. A notebook is checked by `python -m asystem.notebook` and a workspace by `python -m asystem.workspace`,
both run by `fab build`.

### 10.1 Invariants

| Id | Invariant | Enforces |
|---|---|---|
| PJ001 | A project has a manifest with a supported spec version | R1 |
| PJ002 | The flavour and the provenance source are known, the provenance inputs are a list, and a flavour but `static` states its implementation as more than one word and not a placeholder | R1 |
| PJ003 | Every file the flavour requires is in the manifest, exists, and matches its SHA-256 | R1 |
| PJ004 | The project name follows the naming style and equals the signature name | R12 |
| PJ005 | The signature version equals the manifest's, and the model version is among the signature's versions | R1, R10 |
| PJ006 | The signature is complete: datatype, shape, unit, required flag and description on every input and output, unique names, state slots numbered from 0 | R1 |
| PJ007 | Every output starts with the module and ends with the unit suffix of its unit | R12 |
| PJ008 | Constants name signature outputs, and a `static` project gives a constant for every required output | R8 |
| PJ010 | Every golden step has a response or an error, names only signature inputs and outputs, and gives every required input and output | R3, R4 |
| PJ011 | The golden holds a step that expects a signature error, and a first call with no state when the signature has state | R8 |
| PJ012 | Every golden response of a `static` project equals the constants | R4 |
| PJ015 | A golden tolerance names an `FP64` signature output and gives a non-negative `absolute` or `relative` bound, or both | R5 |
| PJ016 | A `wasm` module imports only the maths functions of 4.1, each as `(f64) -> f64` | R4 |
| PJ017 | A `wasm` project's `runtime` equals its module's imports, a `pyfunc` project's `runtime` lists exactly the packages its `model.py` imports beyond the standard library and the base, and no other flavour has a `runtime` | R11 |
| AC001 | A project that is not `static` holds an evaluation, and every required scalar output has a gating check in it | R14 |
| AC002 | A check names a known split, a name in the naming style, an output in the signature, a numeric or null value, a limit and direction, and a boolean gate | R14 |
| AC003 | The recorded outcome, budget and verdict follow from each check's value and limit, the evaluation holds dataset hashes for every split it uses, and a check with a measured value has at least one dataset recorded for its split | R14 |
| CP004 | A consumer's embedded project hashes to the released project of its model | R7 |
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
| NB011 | A notebook imports from `workbench.<module>` by name and never with `*` | R13 |
| NB012 | A notebook does not extend `sys.path`, since the kernel carries it | R13 |
| PM004 | The project has an evaluation and every gating criterion passed, which `check_release` also applies to a consumer's embedded project | R14, R15 |
| RP001 | A replayed step that expects a signature error does not supply every required input | R8 |
| RP002 | A replayed step supplies every required input | R8 |
| RP003 | A runtime reproduces every golden response exactly | R5 |
| MD001 | A released workspace has a `metadata.json` that is valid JSON of the supported schema | R1 |
| MD002 | Every metadata field is present and of its type, a released version is a release version, a snapshot version is a snapshot version, and a released project has no snapshot version | R1 |
| MD003 | A `project/` sits beside the metadata and its `project.json` hash equals `content_sha256` | R1 |
| MD004 | Every target is a `served` target or an `embedded` target with a reference consumer for the flavour, and every passed target is declared | R1 |
| MD005 | The metadata `runtime` equals the project's, every Python package in it has a global pin, and for a `served` target is named in `mlserver`'s `py_deps.txt` | R11 |
| WS001 | The module, model and notebook directories follow the naming style | R12 |
| WS002 | A notebook directory holds exactly one notebook, named `notebook.ipynb` | R13 |
| WS003 | A notebook directory holds only the notebook, `plan.md`, `metadata.json`, `project`, `data` and a model file | R13 |
| WS004 | The data directory holds only the four splits | R6 |
| WS005 | A split holds only timestamp directories | R6 |
| WS006 | A dataset is a csv named `<model>_<notebook>_...`, and one that is not `golden` ends with its date range | R12 |
| WS007 | A notebook directory holds at most one model file of `model.wasm`, `model.onnx` and `model.py` | R13 |

The identifiers, the flavours of 3.2, the splits of 6.3 and the sections of 6.7 are mirrored in code, and a test fails if the specification
and the code disagree in either direction.

### 10.2 Helpers

Common operations are in two places, so a notebook states what it means and not how it is done.

| Where | Helper | Does |
|---|---|---|
| `asystem.model` | `registered_name`, `check_name` | Derives a registered name from a model and a notebook, and checks the naming style |
| `asystem.model` | `build_signature`, `signature_input`, `signature_output`, `signature_state` | Builds `signature.json` with every field the checks need |
| `asystem.model` | `golden_step`, `golden_document`, `golden_from_samples` | Builds V2 requests and responses from named values or from dataset samples, with the datatype taken from the signature |
| `asystem.model` | `package_project`, `write_project` | Builds the golden from samples and writes the project with its evaluation and its `runtime` (`python_deps` for a `pyfunc`, the module's imports for a `wasm`), then runs every project check |
| `asystem.model` | `file_sha256`, `project_content_sha256` | Hash a file, and hash a project's content, so two registrations of the same content match |
| `asystem.model` | `lint_project`, `verify_project` | Reports or raises every finding of 10.1 |
| `asystem.model` | `register_project`, `pull_model` | Registers a project, logging its measured criteria as run metrics, and pulls one by selector |
| `asystem.model` | `content_sha256`, `register_preview`, `register_project` | Hash a project, and register one with its tags and the alias `preview` |
| `asystem.model` | `registry_address` | Resolves the registry address, through `release`, `publish` and `status` |
| `asystem.model` | `diff_signature` | Names every difference between two signatures, which a signature that only grew MUST NOT have |
| `asystem.model` | `render_rust` | Generate Rust request and response types from `signature.json`, through `python -m asystem.model generate` |
| `asystem.model` | `measure`, `evaluate_acceptance` | Measures a prediction against its truth with numpy, and runs a notebook's acceptance check into `evaluation.json` with the outcome and budget of each check |
| `asystem.model` | `check_release` | Check that a project verifies and its acceptance passed, which a consumer's embedded project must also satisfy |
| `asystem.replay` | `replay_project`, `require_replay`, `model_predict` | Replay a project's golden through its runtime in process and compare every response exactly or within the golden tolerance (RP001 to RP005), raising `GateError` when it differs, and load a model file as a predict function |
| `asystem.metadata`, `asystem.release` | `record_project`, `record_passed`, `lint_metadata`, `release_workspaces`, `publish_workspace`, `embed_consumer`, `status_lines` | Write `project/` and `metadata.json`, record a passed target, lint the metadata, release and publish workspaces, embed a consumer and report drift, through `python -m asystem.model` |
| `asystem.notebook`, `asystem.workspace` | `lint_notebook`, `fix_notebook`, `lint_workspace` | Report the findings of 10.1 for a notebook or a workspace, and strip a notebook's outputs |
| `asystem.notebook` | `scaffold_notebook` | Writes a notebook, a plan and the data directories that already pass section 10, through `python -m asystem.notebook new <module> <model> <notebook> <flavour>` |
| `workbench.data` | `data_path`, `read_data`, `ensure_data`, `golden_data`, `query_influxdb3` | Resolves a dataset path, reads one, reads or writes a dataset when it is absent, and queries with the cache |
| `workbench.project` | `scratch_project_dir`, `provenance`, `record_project` | Resolves a scratch project directory, or the same under `MODEL_OUTPUT_DIR`, builds `provenance` from data paths and records the project and its hashes in the workspace |
| `workbench.env`, `workbench.plot` | `init_env`, `show_plot` | Loads the module environment, and plots a series |

A notebook SHOULD use these helpers and MUST NOT reimplement them.

### 10.3 Coverage of the requirements

Each requirement is checked by the identifiers below, or by review where no tool can check it. A test fails if this table and the
Enforces column of 10.1 disagree.

| Requirement | Checked By |
|---|---|
| R1 | PJ001, PJ002, PJ003, PJ005, PJ006, MD001, MD002, MD003, MD004 |
| R2 | Review |
| R3 | PJ010 |
| R4 | PJ010, PJ012, PJ016 |
| R5 | PJ015, RP003 |
| R6 | WS004, WS005 |
| R7 | CP004 |
| R8 | PJ008, PJ011, RP001, RP002 |
| R9 | Review |
| R10 | PJ005 |
| R11 | PJ017, MD005 |
| R12 | NB008, PJ004, PJ007, WS001, WS006 |
| R13 | NB001, NB002, NB003, NB004, NB005, NB006, NB007, NB009, NB010, NB011, NB012, WS002, WS003, WS007 |
| R14 | AC001, AC002, AC003, PM004 |
| R15 | PM004 |
| R16 | Review |
| R17 | Review |

### 10.4 Output of test runs

Every run of a notebook, a unit test or a system test, in any flavour and language, prints in the shape of `go test -v`, so the output of a Python, Go and Rust run reads the same.

```
=== RUN   notebook example/wasm/saturate
    setup        ... done (0.44s)
    fit          ... done (0.00s)
    metadata     ... done [wasm] (0.00s)
--- PASS: notebook example/wasm/saturate (1.34s)
```

- A subject opens with `=== RUN   <name>` and closes with `--- PASS: <name> (<seconds>s)`, `--- FAIL: ...` or `--- SKIP: <name> (<reason>)`. A run ends with `PASS` or `FAIL` and a line `ok  <TAB><suite><TAB><seconds>s` or `FAIL<TAB><suite><TAB><seconds>s`.
- A stage is one line indented four spaces: the name padded to 12, ` ... `, `done` or `FAILED`, an optional detail in brackets and the seconds in brackets. A stage with nothing to do still prints, so a `compile` stage reads `done [interpreted]` for Python.
- A notebook's stages are its sections of 6.7, lowercased, then `metadata`. A reference consumer's `main` prints `verify`, `load` and `replay` with the same shape in Python, Go and Rust, and a system test prints `compile` (`interpreted` or `prebuilt`), for a `served` target `registry` and `serve`, and then the consumer's own lines.
- A finding or an error is still printed as `ERROR <message>` on standard error. `asystem.report` writes this shape for Python, and the three consumers repeat it in their own language, since a consumer MUST NOT import `asystem`.

## 11. The datascience release model

`datascience` follows the pattern of the schema and certificate modules: the declaration is in git, `generate` reflects it into committed artifacts, a release ships what is committed, live state changes only through idempotent verbs, and `status` verifies.

### 11.1 Ownership

- A module `src/rue/datascience` MUST own the notebooks, their data, this specification and its plans, `model.sh`, `notebook.sh` and the reference consumers (11.8). It MUST run-depend on `mlflow`, `mlserver` and `influxdb3`, and release independently of them and of the consumers.
- `mlflow` and `mlserver` MUST be only a container and its configuration. `mlserver` keeps its `serving` and `registry` packages, which MUST NOT be named `mlserver` or `mlflow`.
- `datascience` MUST use `mlflow` and `mlserver` as production services, through the connection variables of its run dependencies and the `*_PROD` endpoints, as `supervisor` uses `vernemq`. It MUST NOT start, build or test them.
- Each of `mlflow` and `mlserver` MUST test itself, in its own module. `mlserver` MUST test its `serving` and `registry` packages, its sync loop (fallback, a failed reload, an unreachable registry, an alias moved back, a failed version not retried) and its container, and `mlflow` MUST test its container and configuration. The tests of a project belong to `datascience`.
- `asystem.model`, `asystem.replay` and `asystem.notebook` MUST stay in the shared library, since fab and every consumer's `generate.sh` import it.
- `datascience` MUST have no `.group`, so it runs before every grouped module in each fab phase and has no per-host install. It MUST read its configuration from the generated `.env` and use the `*_PROD` variables for the production services.

### 11.2 Versions and metadata

- A project MUST NOT carry a version. Its signature, golden file and model file hold no stamp, and its content hash, `content_sha256`, is the SHA-256 of its `project.json`, which lists the hash of every other file.
- Each workspace MUST hold `metadata.json` and a committed `project/`. `metadata.json` MUST hold `schema`, `inputs_sha256`, `content_sha256`, `runtime`, `released_version`, `snapshot_version`, `released_by`, `released_at`, `environment`, the registry uri, name and version, `targets`, and the targets that passed. It MUST hold only facts that cannot be derived from the project, MUST be validated by the library, and MUST be written only by tooling, never by a notebook. A `metadata.json` without its `project/` MUST be a finding.
- `targets` MUST list the environments the project is to run in, each `{"kind": "served"}` or `{"kind": "embedded", "language": "python"|"go"|"rust"}`. The notebook MUST declare them where it packages the project, tooling MUST copy them into `metadata.json`, and the library MUST check each against the matrix of 11.8. A project with no target MUST NOT be released.
- `snapshot_version` MUST be the repository snapshot version, from the root `.version`, in force when the project's content was first recorded. It MUST be kept while the content hash is unchanged, MUST be null for a released project, and MUST NOT be written into any file of `project/`.
- `inputs_sha256` MUST cover the code cells, the data files and the versions of a named list of runtime packages, and MUST NOT cover markdown or the source of `library` or `asystem`. A notebook whose inputs hash is unchanged MUST NOT be rerun. A notebook that never calls `package_project` is a scaffold with nothing to package, and `model.sh` MUST skip it in `unittest` and `systest` alike, so it is reported as `--- SKIP:` with the reason `nothing packaged`.
- `released_version` is the release version of the `fab release` that changed the project. If a rerun reproduces the content hash, the version MUST be kept and only the test results recorded again. A change of a runtime package version MUST rerun and retest.
- A signature change MUST be additive to be released: a new optional input, or a new output. Any other change is a breaking change, and a breaking change MUST be a new notebook, and so a new model name, while the old one stays released until its consumers move. A release MUST refuse a breaking change.
- A workspace in the module `example` is a test fixture and MUST NOT be released. A workspace that produces no project MUST be skipped. The notebook name `preview` is reserved.

### 11.3 Registry

- Each registered model has the aliases `preview` (the version under test) and `release` (live), which are independent pointers. They are the MLflow aliases, so a consumer resolves one as `models:/<name>@<alias>`, and the version tags mirror them. The artifact moved to `release` MUST be the one that was tested, found by its content hash.
- **Who sets them, and who may consume them.** Only the register function of the notebook library MAY set `preview`, and only the release function of `datascience` MAY set `release` or remove `preview`; no other code MAY set either. A production consumer MUST use `release`. Only a system test MAY use `preview`.
- The version tags MUST mirror `metadata.json`: the whole file as one compact JSON tag, and `release_version`, `content_sha256` and `project_flavour` as scalars. A model is a datascience model when it carries `content_sha256` and `project_flavour`. The flow MUST be from git to the registry only.
- A version registered before its release MUST carry the tag `snapshot_version` from `metadata.json`, which the release function MUST remove when it sets `release_version`. The tag is set when the version is first registered and is not changed by a later registration of the same content.
- The tags MUST be set before `release` is moved, so a reader never sees an alias without its tags. A version that has carried `release` MUST NOT be deleted.
- The registry MUST be written only through `asystem.model`.

### 11.4 Serving

- `mlserver` MUST run a loop every `MLSERVER_POLL_SECONDS` (default 30) that reads the registry's aliases in one call and serves every datascience model: the alias `release` as `<name>`, and the alias `preview` as `<name>_preview` when it differs from `release`. It unloads the rest. There MUST be no list of served models.
- It MUST download a model only when its alias version or content hash differs from what it holds, verify every file against the manifest and the acceptance verdict, swap the directory by rename, and then call `POST /v2/repository/models/<name>/load` on localhost.
- **Fallback.** For each model it MUST try the version the alias points at first and, when that cannot be downloaded, verified or loaded, the released versions older than it, newest first, and serve the first that works. A version that failed MUST be remembered, with its content hash, and not retried every poll. A model with no usable version MUST be logged as an error and left unserved, and MUST NOT stop any other model. An alias moved back to an older version MUST be followed.
- A failed reload MUST leave the model that is serving untouched. A failure to reach the registry MUST leave every loaded model serving. At start the loop MUST run once before `mlserver start`, with the same fallback, and the server MUST start whatever the outcome.
- The version label in `/v2/repository/index` MUST be the release version for `<name>` and `preview-<hash8>` for `<name>_preview`, so the index shows exactly what is live. A poll that changes nothing MUST NOT log at INFO.
- `healthy` MUST mean every model in the repository index is `READY`. A release of `mlserver` MUST need no action by `datascience`.

### 11.5 Testing

- **`fab unittest`** is the pre-release test. It MUST run every notebook whose inputs changed through its Package section and no further, run its acceptance check, lint the notebooks, and replay each project's golden file in process in Python, exactly or within the golden tolerance. It MUST write `project/` and the hashes in `metadata.json` for a notebook it reran, so the diff is read before a commit, MUST NOT start a container and MUST NOT write to any service.
- **`fab systest`** tests the projects, not `mlserver`, and MUST NOT depend on what an earlier run left behind. It MUST run the notebooks through their Register section, and wait for each push before it runs any test:
  1. **mlflow.** The notebooks' register function MUST register each project that has a `served` target with its tags and set `preview` in the production registry. A project with only `embedded` targets MUST NOT be registered. The system test MUST wait until the registry returns that version under `preview` with its tags.
  2. **mlserver.** For a project with a `served` target it MUST wait until the production `mlserver` shows `<name>_preview` as `READY` in its index under the expected `preview-<hash8>` label. For an `embedded` target it MUST build the reference consumer container and wait for it to be ready to run.
  3. Only then MUST it run the targets, on the local architecture. It MUST NOT emulate another architecture.
  - A `served` target MUST be called through the `served` reference consumer against `<name>_preview` on the production `mlserver`. No `mlserver` is started for a test.
  - An `embedded` target MUST run in an isolated container the reference consumer of its language and flavour (11.8) on the project's own model, so a WebAssembly project for Go runs as WebAssembly in the Go reference consumer.
  - A target with no reference consumer MUST fail with a finding.
- The system test MUST remove `preview` in every outcome, using the library, MUST NOT move `release`, and neither level MUST write to git. A step that does not complete within its bound MUST fail the run with the step named, and no later step may run.
- A run on another architecture is a run of `fab systest` on a host of that architecture. The specification requires no emulation.
- The targets that passed MUST be recorded in `metadata.json`, and a release MUST require every declared target to have passed.
- **Gates fail loudly.** Every gate in the notebook library MUST raise `GateError` when it is not met: the notebook lint and layout, the project lint and verify, the acceptance check, the golden replay, the signature compatibility check, the comparison with a consumer's `default` slot, and each step of `fab systest`. A gate MUST NOT print a verdict and carry on, return a flag for the notebook to test, or be left to an assertion in a cell, and a notebook MUST NOT assert a gate itself.
  - A `GateError` MUST carry the stage, the gate and the cause. The stage is a notebook section (Setup, Capture Data, Explore, Fit, Evaluate, Package, Register) or a system-test step (notebooks, mlflow, mlserver, target). The cause names the rule codes and the values. The message MUST bracket every interpolated value.
  - `evaluate_acceptance` MUST write `evaluation.json` and print the standard acceptance line, and then raise when a gating check failed or could not be measured, so the verdict can be read and the run still fails. 
  - `fab unittest` and `fab systest` MUST run every notebook and target to its first failed gate, MUST NOT run a later stage of the one that failed, and MUST finish by listing each failure with the notebook or target, the stage, the gate and the cause, and fail.
  - The release MUST NOT proceed past a failed gate.

### 11.6 Release and deployment

| Verb | Behaviour in `datascience` | As in |
|---|---|---|
| `fab generate` | Runs no notebook. It checks `metadata.json` against `project/`, checks the signature against the released one (11.2), and embeds the committed `project/` into each consumer through the consumer's `generate.sh` (11.7) | `fab generate` reflecting a schema; `certificates.sh pull` at generate |
| `fab unittest` | Runs the notebooks whose inputs changed to Package, writes `project/` and the hashes in `metadata.json` (with `released_version` empty for unreleased content) as a notebook writes its model file, and replays in process, with no service written | The unit tests of the other modules |
| `fab systest` | Runs the notebooks through Register, which sets `preview`, waits for `mlflow` and then for the production `mlserver`, then tests each target (11.5) | `fab schema`, describe and verify |
| `fab release` | After both tests, writes the release version into `metadata.json` for changed content, then, through the release function of the library, moves `release` to each tested version and removes `preview`, logs the stale consumers, and the commit and tag carry `metadata.json` and `project/`. It does not change a consumer | `install_pre.sh` publishing discovery when the version changes |
| `fab deploy` | Runs `deploy.sh`, which runs `model.sh publish`, the same idempotent publish, for a rollback after a revert or for drift. It is run in the module, since from the repository root fab selects only modules with uncommitted changes | `certificates.sh push`; `mutate.sh` run by hand |
| `model.sh status` | Verifies and never writes: it compares `metadata.json`, the tags, the aliases, the index and every consumer's embedded project | `verify.sh` |

- **Publish.** For each released workspace that has a `served` target it MUST find the registry version by content hash, registering it with its tags if absent, set the tags, then move `release`, remove any `preview`, and wait for the expected label to be `READY` in the production index, within 90 seconds. It MUST be idempotent. A crash after `release` has moved MUST converge when it is run again.
- If production `mlserver` is unreachable, publish MUST warn and continue, since the registry is the source and the loop will converge. If it is reachable and the label does not appear, publish MUST fail and, where the index shows no sync loop, MUST say that `mlserver` is to be released first. A failed publish MUST stop the release before the tag.
- The release version used to stamp `metadata.json` MUST be read without changing the repository version.
- `status` MUST warn when a model's served label differs from its `release` label, which means an older release is serving because the newest failed, and when a `preview` alias remains.
- A signature check against the released `project/` MUST run in `fab generate`, so a breaking change fails before a release is attempted.

### 11.7 Embedded consumers and clients

- A consumer's `generate.sh` MUST embed: copy `project/` into the consumer's `src/build/resources/model/`, and nothing else, when the SHA-256 of its `project.json` differs from `content_sha256` in the workspace's `metadata.json`, taking the model name from its own `generate.sh`. A change that leaves the content hash alone MUST NOT touch a consumer. A model never released leaves the directory as it is, and a consumer that needs the model cannot build until one is released. A copy that is newer than `metadata.json` after a revert MUST be embedded back. A consumer has no static floor and no second copy.
- fab's `check-release` MUST fail a consumer release whose project files do not verify against its own `project.json`, or whose `project.json` hash differs from the workspace's `content_sha256`, so a consumer cannot ship a stale or edited model, and MUST be the only model step fab adds for a consumer. A consumer MUST be released by its own `fab release`, when its owner chooses, and `datascience` MUST only log which consumers are stale and what they embed. `fab pull` MUST NOT pull models.
- A consumer's loader MUST follow the reference consumer of its language and flavour (11.8). A consumer built against a project whose signature changed additively MUST compile or load unchanged, and one that needs a new output MUST be released after the model that provides it.
- A served client MUST call `<name>` without a version, bound the call by a timeout, and treat an unreachable server or a non-200 answer as no answer. It MUST record the `model_version` label of the answer. An embedded consumer MUST record the hash of its `project.json` with every decision (R9). The release version of a hash is resolved from `metadata.json` at the consumer's release tag or from the registry's `content_sha256` tag, and `model.sh status` MUST print it for each consumer.
- A release of an embedded consumer and a release of `mlserver` MUST NOT require each other or `datascience`: each ships committed or registry state that is already verified.

### 11.8 Reference consumers

- `datascience` MUST own one reference consumer per language under `src/main/python/consumer/`, `src/main/go/consumer/` and `src/main/rust/consumer/`, one `main` that loads and verifies a project, replays the golden file and, given a server and a model name, calls a served model instead, plus one file per flavour prefixed `run_`, named idiomatically for its language. The `main` of every language MUST have the same shape: `main` reads `<project dir> [<server> <name>]` and exits 2 on any other arguments, 1 on a finding or an error and 0 otherwise, printing each as `ERROR <message>`; `load_project` verifies the files and the acceptance verdict and returns the manifest and the signature text; `replay` walks the golden steps and reports `RP001`, `RP002`, `RP003` and `RP005`; `new_predictor` chooses the `run_` file by flavour; `within` applies the golden tolerance; and `read_json` reads a file. Go reads a `_wasm.go` suffix as a build constraint, so its WebAssembly file is `run_webassembly.go`. A flavour file MUST be self-contained and MAY repeat what its siblings repeat, so that it can be cut and pasted into another source tree: it MUST depend on nothing but its arguments (the model path, the signature and, for `static`, the constants) and the language's standard library or runtime, never on the loader, so an embedding module copies the flavour files it needs into its own source and calls them from its own project loading. A reference consumer is a small repeatable codebase that shows what a consuming module implements, and MUST NOT be a library. It MUST load a project directory, verify every file against its manifest hash and the acceptance verdict, predict, replay the golden file, and exit non-zero with the findings on any difference. It MUST depend only on its runtime and the standard library, MUST NOT import `asystem`, and MUST be short enough to read in one sitting.
- Every `run_` file MUST have one entry point, `load_<flavour>` in Python and Rust and `load<Flavour>` in Go, taking the source and the signature, both as text, and returning a predict function (in Python by raising on failure, in Go as a value and an error, in Rust as a `Result`): the constants as JSON for `static`, the model file path for `wasm`, `onnx` and `pyfunc`, and the inference URL of a served model for `served`. The signature is passed as JSON text so that a file parses only what it needs. A `run_` file MUST hold nothing but its imports and that one function (and in Rust the two type aliases of its result), with every constant, type and helper inside it as a local or a closure, so that the whole file is one call to copy. A predict function takes the named input values and returns the named output values, and fails with an error rather than returning a partial answer.
- The matrix, which the library MUST check a target against:

| Language | `static` | `wasm` | `onnx` | `pyfunc` | `served` |
|---|---|---|---|---|---|
| Python | Yes | `wasmtime` | `onnxruntime` | `mlflow.pyfunc` | HTTP client |
| Go | Yes | `wazero` | `onnxruntime_go` | Never | Yes |
| Rust | Yes | `wasmi` | `ort` | Never | Yes |

- The module MUST have one `Dockerfile` that builds every reference consumer into one image on the local architecture, the Python reference consumer installed with the pinned runtime packages and the Go and Rust reference consumers compiled, under `/asystem/bin/<language>`, with the pinned ONNX Runtime shared library for the Go and Rust `onnx` files at `ONNXRUNTIME_LIB`. `fab systest` MUST build it once and run each embedded target in a container of it with the project mounted read-only. The module's `Dockerfile` is a test environment and MUST NOT be released to a host. The Python reference consumer and the `serving` loader of `mlserver` MUST agree, and a test MUST compare them.
