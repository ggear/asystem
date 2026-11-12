# Model Delivery Specification

## 1. Scope

This specification defines how a model is fitted, packaged, tested, registered and run, whether served by MLServer or embedded in a Python, Rust or Go consumer. It applies to every model fitted in the `mlmodels` module and contains nothing specific to one model. A notebook's title cell holds its intent, data, status and future, and no separate plan is kept (6.7).

The key words MUST, MUST NOT, SHOULD and MAY are to be read as in RFC 2119.

### 1.1 Terms

| Term | Meaning |
|---|---|
| Model | A function from one sample of numbers and a carried state to outputs and a new state |
| Sample | One record of numbers: the inputs of one request, or one row of a dataset |
| Input, Output | A named column of the signature, being a feature of `X` or an output of `y` |
| State | The slots a model carries between samples, passed by the caller as one vector input and one vector output |
| Runtime | What executes a project: a WebAssembly host, `onnxruntime`, `mlflow.pyfunc` or an MLServer runtime |
| Project | The directory holding a model, its signature, its golden sequences and its manifest |
| Flavour | What a project holds and what runs it: `static`, `wasm`, `onnx` or `pyfunc` |
| Signature | `signature.json`: the MLServer V2 model metadata and the MLflow model signature, listing every input, output and state slot |
| Signature version | The integer `signature_version` of every project's `signature.json`, from 1000, raised by a breaking change of a served project and never reused |
| Served name | The registered model name and the name `mlserver` serves a served project under, `<module>_<model>_<notebook>_<signature version>`, with `_preview` appended for the preview |
| Golden | Fixed requests and the exact responses they must produce |
| Workflow | The ordered stages of a notebook, Setup through Pull, each a level two heading calling its `<stage>_<what>` functions from `mlmodels.workflow` |
| Stage | One step of the workflow, such as Collect or Define, or one row of 7.1 |
| Workspace | The directory `src/main/notebook/<module>/<model>/<notebook>/` holding one notebook, its data and its models. Several models sit under a module and several notebooks under a model |
| Consumer | A service that calls a model, served or embedded |
| Loader | The single file per language, `loader.py`, `loader.rs` or `loader.go`, that `mlmodels` writes into a consumer to verify, load and run a project of any flavour its language supports (10.9) |
| Served | Run by MLServer behind the V2 inference API |
| Embedded | Run in the consumer's own process |
| Local | Run only in the notebook that fits it: never registered, served, embedded or released, though a notebook MAY read its constants from the committed project |
| Split | One of `training`, `validation`, `backtest` or `monitoring`, naming the purpose of a dataset |
| Acceptance | The check a notebook defines and runs through the shipped runtime, recorded in `evaluation.json`, which a project must pass to be released |
| Budget | A dimensionless score for an acceptance check: the share of its limit the measurement used. A check passes at a budget of 1 or less |
| Parity gate | Replay of the golden sequences through the reference consumer a target names and through each consumer's embedded copy, which MUST reproduce every response and state exactly or within the golden tolerance |
| Alias | An MLflow registry alias on a registered model: `preview` for the version under test and `release` for the live one (10.3). MLflow reserves `v<N>` and `latest` |

## 2. Requirements

| # | Area | Requirement | Rationale |
|---|---|---|---|
| R1 | Standard | Every model MUST have one signature, one project layout and one manifest of SHA-256 hashes, whatever its flavour | A consumer moves between served and embedded without change |
| R2 | Standard | The flavour MUST follow the model and MUST NOT follow the environment. The flavours are `static` (constants), `wasm` (formula or stateful, as a WebAssembly module), `onnx` (learned) and `pyfunc` (Python-only libraries, served or in Python, never embedded in Rust or Go) | The environment does not dictate the maths |
| R3 | Standard | Feature engineering MUST live in the project. A request MUST be one sample of numbers plus the state the caller carries. A consumer MUST NOT hold model logic | Recorded once at source, replayable |
| R4 | Parity | Every number reported or shipped for a project, the fit included, MUST come from the shipped runtime of its flavour. A faster proxy MAY choose the fit, and the runtime MUST then reproduce the result. Exploration MAY use plain Python | No gap between pre-prod and prod numbers |
| R5 | Parity | A project MUST NOT be released until its acceptance has passed, every target declared in its metadata has passed its system test on the local architecture, and a person has run `fab release`, which is the review | A mismatch is caught before it ships |
| R6 | Parity | Every split MUST be declared by `prepare_split`, which fails when two splits share rows without a declared overlap and when a live run is any split but `monitoring`. Held-out data MUST NOT be used to fit | An error estimate stays honest |
| R7 | Delivery | A serving runtime MUST poll the registry, serve the newest verified `release` of every model, fall back to the next most recent verified release when the newest cannot be used, and never stop serving a working model because another failed. An embedded consumer MUST take its project from the committed `mlmodels` tree, and a release MUST NOT ship a project that differs from it | A served model is a verified release, and an embedded one is exactly the committed one |
| R8 | Delivery | A consumer MUST validate a project at load through the bundled loader, MUST NOT use an invalid one and MUST NOT depend on a served model. There is no fallback project: a consumer whose model is broken is broken, and its build and tests catch it. A served model that is down is down | A bad project never answers |
| R9 | Delivery | Every decision MUST record the content hash of the project that produced it, and a served decision also the `model_version` label of the answer | Any outcome can be traced and replayed |
| R10 | Change | A change of behaviour, being a new WebAssembly ABI version, a runtime or engine version or a breaking signature change, MUST be a code release of the runtime and its consumers, and a breaking signature change of a served project MUST raise its signature version and so its served name, while one of an `embedded` project MAY be made in place (10.2). A refit MUST replace only the model file and the hashes that cover it | A refit changes data, a release changes behaviour |
| R11 | Change | Every runtime library MUST be pinned by version. Any upgrade MUST re-run `fab systest` | Parity holds only while the runtimes do not move |
| R12 | Standard | Every name MUST follow 6.1: lowercase `<module>_<dimension>` style with a unit suffix on numeric measures | A name tells its owner and what is measured |
| R13 | Standard | Every project, notebook and workspace MUST pass the checks of section 9 | The requirements are enforced by tools and not by reading |
| R14 | Parity | A project that is not `static` MUST carry an evaluation from an acceptance check its notebook defines, run through its shipped runtime, and MUST NOT be given the alias `release` unless every gating check has passed | Every model is enforced against its own limits, and the outcome is recorded the same way for all |
| R15 | Parity | A notebook MUST run through its Package stage from committed data, and a re-run MUST write the project its `metadata.json` hashes describe. A gate that is not met MUST fail the run, and a project whose acceptance failed MUST NOT be released | A notebook is evidence anyone can reproduce. A `pyfunc` file is rewritten by every execution and not compared with the committed copy, since a float level difference in a fit would otherwise block every run |
| R16 | Standard | A project MUST be version-free and content-addressed. Its release version is a label in `metadata.json` and in registry tags, issued as the release version of the `fab release` that changed its inputs, and an unchanged project MUST keep its label | The artifact that was tested is the artifact that ships. `target` stays in `metadata.json` and out of `project.json`, so a change of target does not change the project's hash |
| R17 | Standard | The registry MUST be written only through `mlmodels._registry`, from `metadata.json` and the project, and never read back for a decision except by a serving runtime choosing what to load. A serving runtime MUST refuse a model whose evaluation did not pass | The registry is a mirror of git |
| R18 | Standard | A consumer's loader MUST be the one `mlmodels` writes, unedited and current, and a consumer's model file MUST name the released project it was generated from | The loader is the one place a project is verified and run, so a drifted copy runs a different loader than the one tested |
| R19 | Standard | The loaders and the reference consumers MUST stay consistent across languages and flavours: the same concepts, names, verbs, stages, errors, outputs and behaviour, each in its language's own case and idiom. A difference MUST be accepted only where the language or flavour makes the common design impossible, MUST be the smallest that works and MUST be recorded in 10.9.1 | One contract tested in three languages is one behaviour to reason about |

## 3. Project

A project is a directory read the same way by every environment and written and checked by `mlmodels`.

### 3.1 Files

| File | Flavours | Content |
|---|---|---|
| `project.json` | All | The schema (2), name, `flavour`, the `model_id` of the notebook model it was packaged from, the `model` file name where the flavour has one, optional constants, the `runtime` of `wasm` and `pyfunc` (3.4), provenance and, last, `files`: the SHA-256 of every other file keyed by its path |
| `signature.json` | All | The MLServer V2 model metadata, which is also the MLflow model signature. It MUST be identical in the workspace, the project, the consumer and the logged MLflow model, apart from its `versions` list. Every project's carries `signature_version` as its second key (MD006) |
| `golden.json` | All | Named sequences of requests and responses, each request carrying the previous response's state. A response is exact unless the file states a tolerance for an `FP64` output |
| `evaluation.json` | All but `static` | Each acceptance check with its measured value, limit, outcome and budget, the SHA-256 of each dataset used, the verdict and the worst budget (6.8) |
| `model.wasm` | `wasm` | The WebAssembly module, with its fitted attributes built in |
| `model.py` | `pyfunc` | The Python model, in MLflow's models-from-code form |
| `model.onnx` | `onnx` | The ONNX model at a pinned opset |
| `MLmodel`, `artifacts/*` | `pyfunc` | The MLflow model descriptor and the project files, written when the project is logged |

**Identity.** A project carries no version. Its identity is the SHA-256 of its `project.json`, and its release version is a label in `metadata.json` and the registry tags (10.2, 10.3). A served model is loaded as `release` only, so an unversioned call reaches it.

**JSON documents.** Every JSON document `mlmodels` writes MUST start with `"schema"`, the version of that document's layout (PJ001). Fields run from identity to detail with the largest or most volatile last: in `metadata.json` the `version`, the two hashes, the `target` and the `release` record; in `project.json` the identity, then the model file, constants, runtime and provenance, and last `files`; in `evaluation.json` the verdict and worst budget before the datasets and checks. Every such document MUST be written by `mlmodels._document.write_json`, which keeps key order, indents two spaces, writes a list of scalars on one line and writes an object of scalars and lists of scalars on one line when it fits in 200 characters.

**Workspace signature.** A workspace holds `signature.json` beside its notebook. It is the one place the names, units, datatypes and descriptions of the inputs, outputs and state are declared. It is committed, holds no value and is therefore safe where `project/` is git-ignored. A notebook refers to inputs and outputs only through `ws.inputs` and `ws.outputs` and never by a literal string. `package_project` writes the same document into the project, and MD003 fails the notebook if the two differ. The file is part of `inputs_sha256`, so editing it re-runs the notebook, and `metadata.json` does not repeat the names. A workspace's `signature.json` also holds `signature_version` as its second key, which a breaking change of a served project raises (10.2) and which an `embedded` or `local` project carries unchanged. An input name MUST be a metric name from its owning service, required outputs MUST be those the consumer cannot act without, and state slots are numbered in order.

**Provenance.** `implementation` MUST name what is inside the container for every flavour but `static`: the builder of a `wasm` module, the converter and opset of an `onnx` graph, or the pinned requirements of a `pyfunc` model. `source` MUST be `static`, `manual` or `mlflow`, and `provenance.inputs` MUST list the data files used. A manifest MAY carry `constants`, which MUST name signature outputs and are merged into every response.

**Golden steps.** A step MUST have either a `response` or an `error`. An `error` of `signature` means the request omits a required input, and the model MUST refuse it.

### 3.2 Flavours

| Flavour | What It Is | Model Logic Lives in | Learns from Data? | Carries State? | Runs Where | Use When |
|---|---|---|---|---|---|---|
| `static` | Constants and nothing else | The manifest's `constants` | No | No | Everywhere, with a plain loader | Constants and tunables that are reviewed and versioned |
| `wasm` | A WebAssembly module | `model.wasm` | Fitted offline, attributes built in | Yes, a fixed-length vector | Python, Rust, Go and served, through a WebAssembly host | A formula, curve, lookup, integrator, decay or latch |
| `onnx` | An ONNX model file | `model.onnx` | Yes | Optional | Python and served (`onnxruntime`), Rust (`ort`), Go (`onnxruntime_go`) | A tree, regression or small network from scikit-learn, XGBoost and the like |
| `pyfunc` | An MLflow Python model | A Python class and its libraries | Yes | Optional | Served in MLServer, or in Python; never Rust or Go | A library with no converter, or arbitrary Python |

### 3.3 Requirements per flavour

`static`
- MUST have no model file: the constants are the manifest's `constants`, which `define_model` takes as its source (6.7.6).
- MUST answer the same constants for every valid request, MUST give a constant for every required output and MUST still validate the request.
- MUST be packaged with `package_model` and released and embedded through the same path as any flavour.

`wasm`
- MUST satisfy the ABI and determinism rules of section 4: float64, one numeric sample in, a fixed-length state.
- MUST NOT use strings, timestamp parsing or variable-length windows.
- MAY import the maths functions of 4.1 and MUST state a golden tolerance for every output that depends on one (4.2).
- MUST record the hash of `model.wasm` in the manifest and MUST be committed as `model/<model>/model.wasm` by `define_model`, which traces it from a Python function (6.4).

`onnx`
- MUST be committed as `model/<model>/model.onnx` by `define_model`, which takes the bytes of the graph.
- MUST pin the opset, use one allow-listed operator set and use float64 where each engine has a kernel.
- MUST NOT use an operator over a variable-length input.
- MUST use the same pinned `onnxruntime` shared library everywhere it can.

`pyfunc`
- MUST be written as `model/<model>/model.py` by `define_model` in MLflow's models-from-code form (`set_model`) and logged with `mlflow.pyfunc.log_model`, with the project in `artifacts` and a signature built from `signature.json`.
- MUST declare as `runtime.python` (3.4) every package its `model.py` imports beyond the standard library and the base packages (`mlflow`, `numpy`, `pandas`), and MUST NOT declare one it does not import.
- MUST NOT be embedded in Rust or Go.

### 3.4 Runtime dependencies

A project states what a runtime must provide beyond the base, so a missing dependency is a finding at build time and not a failure when a model is first served. The manifest carries it as `runtime`, which is part of `project.json` and so of the content hash. `metadata.json` does not repeat it.

| Flavour | `runtime` | Source | Runtime provides |
|---|---|---|---|
| `static`, `onnx` | None, and a manifest that carries one is a finding | | `static` needs only the loader, and `onnx` needs `onnxruntime` and its allow-listed operators, which a graph cannot extend |
| `wasm` | `{"wasm": [<import name>, ...]}` | Derived from the module's imports by `package_model`, never written by a notebook | The `asystem_math` functions of 4.1, which every host provides, so the list is a record and a check and is never installed |
| `pyfunc` | `{"python": [<package>, ...]}` | Derived by `package_model` from the imports of the model file | The base packages `mlflow`, `numpy` and `pandas`, plus the declared packages |

- A `python` entry is a package name and never a version. Its version is the one global pin in the root `py_deps_prod.txt`, the pin `fab` gives every module that lists the name in its `py_deps.txt` (R11), and a name with no pin fails the Package stage. Names match ignoring case and `-`, `_` and `.`.
- A `python` list is sorted and unique and excludes the standard library and the base packages. PJ017 reads the imports of `model.py` and fails in both directions: an import with no entry, and an entry nothing imports. A package whose import name differs from its package name is matched through a table in code.
- `fab systest` installs the base pins and every workspace's declared packages at their global pins into the test image, so an embedded Python target fails if the list is incomplete.
- Adding a dependency is a change of behaviour (R10). It changes the content hash and rewrites the requirements file of 3.5, and the consuming modules then pin it through `fab pull` and are released.
- Every notebook run prints a `requirements` stage before `metadata`, so it appears even when MD005 fails. Its detail is `N to add`, followed by the target and names when N is not zero. For a `served` or `embedded` Python host it reports only a package with no pin (`! name`, to add to the root `py_deps_prod.txt`). For an `embedded` Rust or Go host, whose `Cargo.toml` or `go.mod` cannot take a merged list, it names the file and each library the file lacks (`+ name`). The stage reports and never fails.

### 3.5 Host requirements

`metadata.json` carries the project-specific part of what a host must install. `mlmodels` derives the rest and writes it beside the metadata.

| In the project's `project.json` | Not in `project.json` |
|---|---|
| `runtime.python`: the package names a `pyfunc` project imports beyond the base, with no versions | The host library of a flavour and language: `wasmtime`, `wasmi`, `wazero`, `onnxruntime`, `ort` |
| `runtime.wasm`: the `asystem_math` functions a module imports, a record that nothing installs | The base packages `mlflow`, `numpy` and `pandas`, which every Python host carries |
| `target`: where the project runs, which says which host to look at | Every version: Python pins in the root `py_deps_prod.txt`, crate versions in `Cargo.toml` and `Cargo.lock`, module versions in `go.mod`, the native `onnxruntime` library in `.env_fab` (`ONNXRUNTIME_VERSION`) |

**Requirements files.** For a `served` or `embedded` Python target, `record_project` writes `py_deps.txt` beside `metadata.json`: the manifest's runtime names plus the host library of the flavour (`wasmtime` for `wasm`, `onnxruntime` for `onnx`), sorted, one name a line, with no versions. A target in another language has no file, and a file left from an earlier target is removed. A `local` project has none. The Rust and Go libraries are derived by the `requirements` stage and checked by hand against the consumer's `Cargo.toml` and `go.mod`, so no file records them. MD005 fails the notebook if a requirements file is missing, stale or different from what the metadata derives.

**Taking them in.**
- For `served` and `embedded` Python targets, `fab pull` writes each module's pinned `.py_deps.txt` from its hand-written `py_deps.txt` plus the `py_deps.txt` of every project that targets it. `mlserver` takes every project with a `served` target, and any other module takes the projects of the notebook module of its own name with an `embedded` Python target (`mlmodels` those of `example`). Each name is pinned from the root `py_deps_prod.txt`, and a name with no pin stops the pull. A module's own `py_deps.txt` keeps what the module needs whatever the projects are, such as the host libraries `mlserver` carries to serve any `onnx` or `wasm` project. The module is repackaged when its pinned list moves.
- For `embedded` Rust and Go targets, the `requirements` stage names the file and each library it lacks, and a person adds them. A Rust or Go consumer never embeds a `pyfunc`, and for a `wasm` project needs only its host library (`wasmi`, `wazero`) and the maths functions of 4.1.
- The bundled loader (10.9) adds host requirements of its own, which `embed` checks against the consumer's manifest: for Rust the crates and features `serde`, `serde_json`, `sha2`, `wasmi` (`model-wasm`) and `ort` (`model-onnx`), and for Go `wazero` and `onnxruntime_go`, every Go consumer needing ONNX.

## 4. WebAssembly models

A `wasm` project is a module, `model.wasm`, that satisfies one ABI. Python, Rust and Go run the same bytes in a WebAssembly host and produce the same numbers. The specification fixes the ABI and the determinism rules, and a module is hand-written or built by `define_model` (4.3). `provenance.implementation` names what made it, and no implementation has a name in this specification.

### 4.1 ABI

- A module MUST export `predict`, as a scikit-learn estimator does. It takes `X` of shape `(n_samples, n_features)` and returns `y` of shape `(n_samples, n_outputs)`, both float64 (`FP64`). The features are the signature's scalar inputs followed by the elements of the state input, and the outputs are the signature's scalar outputs followed by the elements of the state output, each in signature order. Column `j` of `X` is the `j`-th feature, and a V2 request is stacked into `X` in that order.
- Samples are independent. `predict` holds no state between calls, and the caller carries state from each response to the next request (R3).
- A module is a fitted estimator. `fit` is not part of the ABI: fitting is offline, and the fitted attributes are built into the module.
- A call MUST be bounded in time and memory. A host MUST meter fuel and cap memory.
- A module MUST export its linear memory as `memory` and `predict` as `predict(x: i32, n: i32, y: i32)`. The host writes `n` rows of float64 features, row-major, at byte offset `x`, calls `predict` and reads `n` rows of float64 outputs from byte offset `y`. A host puts `x` at 0 and `y` immediately after the features.
- A module MUST import nothing from its host except the maths functions below, each imported from the module `asystem_math` with the type `(f64, ...) -> f64` of its arity. A host that runs a module MUST provide all of them with IEEE (C99) results outside the domain: `log(0)` is negative infinity; `log` of a negative value, `asin` of a value above one and `sin` of an infinity are NaN; an overflowing `exp` or `cosh` is positive infinity; an overflowing `sinh` takes the sign of its argument; `pow(0, y)` is infinity for a negative `y`. The Python (`wasmtime`), Go (`wazero`) and Rust (`wasmi`) hosts provide them from their standard libraries.

  | Arity | Functions |
  |---|---|
  | 1 | `acos`, `asin`, `atan`, `cos`, `cosh`, `exp`, `log` (natural), `log10`, `log2`, `sin`, `sinh`, `tan`, `tanh` |
  | 2 | `atan2(y, x)`, `pow(base, exponent)` |

  `sqrt`, `abs`, `floor`, `ceil`, `trunc`, `nearest`, `min` and `max` are WebAssembly instructions, exact on every host, and are never imported. The set is closed, owned in code and mirrored by all three hosts, and a test asserts the sets and arities are equal. Adding a function is an ABI change and a release of every consumer (R10).
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

- A module MUST use float64 only and MUST NOT use relaxed SIMD, threads or any operation whose result differs between CPUs.
- A function with no exact cross-platform result is imported from `asystem_math`, and each host calls its own maths library, so results MAY differ between hosts in the last bits. A golden tolerance MUST be stated for every output that depends on one. A model MUST NOT branch on such a result where a last-bit difference would change the branch, and MUST use a lookup table or a polynomial of basic operations instead. Where the differences grow significant, because a tolerance wide enough to hold them hides a real fault or a branch or step amplifies them, the algorithm SHOULD be written into the module with `f64` arithmetic only and no import, so every host gives the same result with no tolerance and no ABI change.
- A consumer MUST parse a JSON number to the nearest float64, since an exact comparison without a tolerance fails on a one-bit parse error. Rust's `serde_json` needs its `float_roundtrip` feature.
- The golden sequences and the parity gate prove determinism: the module MUST reproduce every response and state exactly in every reference consumer a target names, except for an output with a stated tolerance.
- A tolerance is stated in `golden.json` as `"tolerance": {"<output>": {"absolute": <a>, "relative": <r>}}`, for an `FP64` output only, with either bound or both. A value matches when it differs from the golden value by no more than `absolute + relative * |golden value|`. An `INT64` output and any output without a tolerance match exactly. A learned `onnx` graph, whose float32 kernels differ between CPUs, MUST state one, and a notebook SHOULD choose the smallest bound its own error on `validation` allows and say why in its title cell. The same rule applies to every runtime of the gate.

### 4.3 Building

- The builder is `define_model` over `mlmodels._wasm`. It compiles with `wasmtime`, adds no toolchain, ships only `model.wasm` and is never run by a consumer. Third-party libraries fit the numbers, and the fitted values are built in as constants. The builder becomes private to a second project that needs it, and logic too large for an expression tree is written as a Rust crate.
- A notebook builds a module from an expression tree (constants, features, named intermediate values, arithmetic, `min`, `max` and a select on a comparison) with the operators of `mlmodels.maths`, or traces it from an ordinary Python function:
  - The operators of `mlmodels.maths` MUST give on numbers the result a host gives.
  - A function MUST NOT use Python control flow on a symbolic value. A branch is a `select` of two arms, both evaluated, and a comparison is valid only as the condition of a `select`.
  - A function MUST NOT call numpy or `math` functions on a symbolic value.
  - A traced function MUST be checked against the module, by the golden samples replayed through it or by a sweep that includes the bounds. The plain call differs from a host only by the tolerance of 4.2.
- Each project MUST record the hash of its `model.wasm`, so every host runs the same bytes. A new ABI version or host runtime version MUST be a code release of the runtime and every consumer (R10), and a refit replaces `model.wasm` only.

## 5. Libraries

Yes means preferred, Maybe means it works within the stated limit, and No means it cannot be done or MUST NOT be.

### 5.1 Runtime libraries

The `wasm` column is the third-party WebAssembly host that runs `model.wasm`. The `static` column is the bundled loader (10.9), which every flavour of a language shares.

| Environment | `static` | `wasm` | `onnx` | `pyfunc` | Notes |
|---|---|---|---|---|---|
| MLServer (Served) | Yes: the bundled Python loader in a custom runtime | Yes: `wasmtime` in the custom runtime. Maybe: `wasmer` | Yes: `onnxruntime` in a custom runtime. Maybe: MLServer's MLflow runtime, if it maps names and types cleanly | Yes: MLServer's MLflow runtime | The bundled Python loader imports only the standard library at module level, and each flavour imports its own library inside its entry point |
| Python (Embedded) | Yes: the bundled Python loader | Yes: `wasmtime` | Yes: `onnxruntime` | Yes: `mlflow.pyfunc` in process | |
| Rust (Embedded) | Yes: `serde_json` and `sha2` | Yes: `wasmi`, pure Rust and fuel-metered. Maybe: `wasmtime`, where speed outweighs size | Yes: `ort`, loading the pinned wheel's library with one thread. Maybe: `tract` unoptimised, where memory is tight | No | `tract` optimised gave off-by-one results. `pyfunc` needs the Python stack |
| Go (Embedded) | Yes: `encoding/json` and `crypto/sha256` | Yes: `wazero`, pure Go with no cgo | Maybe: `onnxruntime_go`, which needs cgo and a native library, only when a Go consumer needs a learned model. Maybe: a pure-Go engine, for trivial graphs only | No | `wasmtime-go` needs cgo. `pyfunc` cannot be embedded |

### 5.2 Authoring and training libraries

`static` needs no library. A `wasm` module is produced by a builder its project chooses, and the libraries here fit the numbers that go into it. A library marked No under a flavour MUST NOT ship in that flavour, though training in it is permitted. A runtime SHOULD be the smallest that runs its flavour.

| Library or Tool | `wasm` | `onnx` | `pyfunc` | Notes |
|---|---|---|---|---|
| NumPy, SciPy, polars | Yes: fit with `scipy.optimize.least_squares` and numeric derivatives, then build a module | No | Maybe: any use | The default for formula models. Polars for data, pandas only where a library needs it |
| scikit-learn | Maybe: linear models and small nets only, by exporting weights as for JAX and MLX; prefer `onnx` | Yes: `skl2onnx`, most estimators and pipelines | Maybe: any use | The preferred stack for tabular learned models |
| XGBoost, LightGBM, CatBoost | No | Yes: `onnxmltools` | Maybe: any use | CPU training on the laptop is enough at this scale |
| PyTorch | Maybe: linear models and small nets only, as above | Maybe: `torch.onnx` | Maybe: any use | Only if a network is ever needed. The MPS backend is beta on Apple Silicon |
| TensorFlow, Keras | Maybe: linear models and small nets only, as above | Maybe: `tf2onnx` | Maybe: any use | Nothing that needs `tensorflow-metal` ships, since it is weakly maintained |
| statsmodels, Prophet | No | No | Yes: served or in Python | No ONNX converter is known |
| JAX, MLX | Maybe: train, then export the weights of a small net into a module's matrix and activation code, using the imported `tanh` and `exp` with a stated golden tolerance, or lookup tables or polynomials | No | Maybe: a custom `pyfunc`, served or in Python, with a `static` floor | JAX converters are fragile and MLX has no exporter. Bigger models are retrained in PyTorch or scikit-learn. Nothing Metal-specific ships |

## 6. Workspace and data

### 6.1 Naming

- A name MUST use lowercase letters, digits and underscores only.
- A workspace is `<module>/<model>/<notebook>`. The module is the one that consumes the model, such as `rackmains`, `homeassistant` or `wrangle`, or `example` for a worked example named for the flavour it shows. A model groups related notebooks. A model and a notebook MUST be named for the quantity they output, in its standard term, and never for how they are built, so `portfolio/withdrawal` and not `portfolio/annuity`.
- A name a source publishes MUST be used as published wherever it appears: the entity id without its domain, which is the `entity_id` in InfluxDB and the same name in PostgreSQL. A dataset column, a query, a signature input and a signature output that carry its value MUST use that name unchanged, so data maps from a source through a dataset and a model and back without a lookup. The name MUST flow unaltered through every stage: feature engineering MAY add a column and MUST NOT rename one (NB017), and a required input is a column of every dataset (WS012). A labelled training column carries the output's name. A served model's output MUST be named for the entity that holds it at the source, without its `mlserver_` prefix. A wrong name MUST be changed at the source and then everywhere, and MUST NOT be bridged by an alias.
- A name no source publishes MUST NOT start with the module. It is made of dimensions from general to specific, normally led by the model. A numeric measure MUST end with a unit suffix, such as `_volts`, `_hertz`, `_pct`, `_seconds`, `_wh` or `_celsius`, and the same quantity MUST use the same words in every project.
- A notebook name MUST NOT be all digits or end in `_<digits>` (WS015), so a trailing number in a registered name is always a signature version.

| What | Form | Example |
|---|---|---|
| Workspace | `<module>/<model>/<notebook>`, one `notebook.ipynb` per directory | `homeassistant/hotwater/temp` |
| Registered Model | The served name `<module>_<model>_<notebook>_<signature version>` for a served project, also the name `mlserver` serves it under | `homeassistant_weatherstation_battery_1000` |
| Signature Name | The published name, otherwise dimensions with no module prefix | `weatherstation_console_battery_voltage`, `hotwater_out`, `guard_shed_max_seconds` |
| Dataset | `<model>_<notebook>_<dimension>...`, with no date, since the range a run covers is in its `params` and its query | `weatherstation_battery` |
| Dataset Column | A signature or source name unchanged, and `time` for the reading time | `weatherstation_console_battery_voltage`, `time` |
| Split | One of `training`, `validation`, `backtest`, `monitoring` | `training` |
| Project Flavour | The lowercase flavour value | `wasm` |
| Timestamp | `YYYY-MM-DD_HH-MM-SS`, Perth time | `2026-10-31_15-17-42` |

### 6.2 Layout

```
src/rue/mlmodels/src/main/notebook/<module>/<model>/<notebook>/notebook.ipynb
src/rue/mlmodels/src/main/notebook/<module>/<model>/<notebook>/signature.json
src/rue/mlmodels/src/main/notebook/<module>/<model>/<notebook>/metadata.json
src/rue/mlmodels/src/main/notebook/<module>/<model>/<notebook>/project/
src/rue/mlmodels/src/main/notebook/<module>/<model>/<notebook>/model/<id>/model.<wasm|onnx|py>
src/rue/mlmodels/src/main/notebook/<module>/<model>/<notebook>/data/<run>/<dataset>.csv
```

- `<module>`, `<model>` and `<notebook>` MUST be named as 6.1 requires.
- A notebook directory MUST hold one notebook named `notebook.ipynb`, its `signature.json`, its `metadata.json` and `project/` once packaged, the requirements files, its `data` and its `model` directory, and nothing else (WS003). The data belongs to the notebook and MUST NOT be shared between notebooks. There is no `plan.md`, and WS003 rejects one.
- `<run>` is an integer of 1000 or more, unique per workspace and never reused, with gaps allowed since a retired run is deleted (WS005). A run is the data of one period in the one schema every run of the workspace shares, and MAY hold several datasets. A run is not specific to a split. Every run of a dataset MUST have the same columns (WS009), so a schema change MUST be followed by rewriting every older run to the new schema, with nulls or guesses, and the guessed columns MUST be listed in the json's `inferred` (WS010). A run is frozen unless its `collect_run` call gives `live=True`, and any run MAY be live whatever its number.
- Every `<dataset>.csv` has a `<dataset>.json` beside it, written with the csv. It records the `source`, the `query`, its `params`, the `database`, the free text `label` of the run, whether it is `live`, the capture time, the row count, the SHA-256 of the csv (WS008) and `inferred`, the columns filled with guesses where a source had no value, so a guess is never mistaken for a reading.
- A file under `data/` is source. It MUST be committed like a project, so a dataset is reproducible and a re-query is a diff.

### 6.3 Splits

A split is a use of data. The notebook forms its splits in memory from runs in its Prepare stage, and nothing in a csv is specific to one. The notebook decides how each project forms them, and MAY reuse or slice a run when data is scarce.

| Split | Used for | Never Used for |
|---|---|---|
| `training` | Fitting the model | Judging the result |
| `validation` | Every decision around the fit: tuning, selection and thresholds, and the folds of cross-validation. An estimate from it is optimistic, since decisions were made on it | Fitting |
| `backtest` | The final held-out whole runs, judged once after every decision, and replayed in time order, as the service would run, for a model that carries state | Fitting, tuning or any decision |
| `monitoring` | What a released model saw and produced in production, one row per prediction with its inputs, its outputs and the released `version`, to watch input drift, output distribution and change between versions | Fitting, tuning or judging a candidate |

`prepare_split` MUST fail when two splits share rows unless the pair is declared in `overlap`, MUST fail when `backtest` shares a row with `training` or `validation` whatever is declared, since a backtest no decision has used is the only independent estimate, and MUST fail when a run that is refreshed live is given to any split but `monitoring`. A row held out for `validation` or `backtest` MUST NOT be in `training` once it has been used to make a decision.

**Cross-validation.** Standard validation is the one-fold case, a single `prepare_split` declaration. Cross-validation makes that declaration once per fold with `prepare_folds(ws, selection, k=..., gap=..., scheme=...)`, which partitions the selection, in its row order, into `k` contiguous blocks and sets `ws.training` and `ws.validation` for each fold under the guards above.
- The `blocked` scheme holds each block out in turn and trains on the rest. The `forward` scheme trains only on earlier blocks and validates on each later block in turn, and MUST be used when later rows depend on earlier ones, as a time series does.
- `gap` rows either side of a held-out block (only before it for `forward`) are left out of training, so adjacent readings cannot leak. Rows are never shuffled.
- Folds partition only the data a model may learn from, so `backtest` and `monitoring` MUST be declared outside them, with `prepare_split` after the loop.
- `prepare_folds` MUST fail for a `k` under 2, more folds than rows, a fold with no training rows and a live run.

### 6.4 What is on disk

| Path | What It Is | Written by | Read by |
|---|---|---|---|
| `<module>/<model>/<notebook>/notebook.ipynb` | The notebook, committed without outputs | By hand | `notebook.sh <module>/<model>/<notebook>` or the IDE |
| `<module>/<model>/<notebook>/model/<id>/model.wasm`, `model.onnx`, `model.py` and `model.json` | A defined model and its document, with a label, flavour, the runs it was fitted on and the SHA-256 of the model file, committed so a refit is a reviewable diff | `define_model`, rewritten by every execution | `package_model`, WS011, and a person reviewing the diff |
| `<module>/<model>/<notebook>/signature.json` | The declared names, units and datatypes of the inputs, outputs and state; committed, no values (3.1) | By hand, or the skeleton from `notebook.sh new` | `setup_workspace`, and MD003 |
| `<module>/<model>/<notebook>/py_deps.txt` | The Python library names the project's target needs, no versions (3.5) | `record_project` | `fab pull` |
| `<module>/<model>/<notebook>/data/<run>/<dataset>.csv` and `.json` | The rows of one run in the workspace schema, and how they were collected | `collect_run`, or by hand | `prepare_split` |
| `src/rue/mlmodels/target/notebook/<module>/<model>/<notebook>/notebook.ipynb` | An executed notebook, not committed | `notebook.sh` | A person reading the run |
| MLflow Run and Registered Model `<name>` | The logged project and the aliases `preview` and `release` | `register_model` sets `preview`, and the release function sets `release` | The `mlserver` sync loop, and a system test through `<name>_preview` |
| `<consumer>/src/build/resources/model/<notebook>/` | The embedded copy of the released `project/`, committed | The consumer's `generate.sh`, through `python -m mlmodels embed` | The consumer's build, tests and image |
| `<consumer>/src/main/<language>/<service>/model/` | The consumer's one embed-owned directory: the loader `loader.<ext>`, a generated `<notebook>.<ext>` per model, the root file that lists them (`mod.rs`, `__init__.py`) and, for `mlserver`, `vocabulary.py`, committed. Go holds `model/loader.go` and one package `model/<notebook>/<notebook>.go` per model | The consumer's `generate.sh`, through `python -m mlmodels embed` or `embed-loader` | The consumer's code, CP005 and CP006 |
| `/asystem/mnt/models/<name>/` in `mlserver` | The served copy of the `release` project | `mlserver`'s start-up pull | The serving runtime |

### 6.5 Runs

`collect_run(ws, run, *, label, name=None, source=None, query=None, params=None, database=None, csv=None, build=None, live=False)` registers the polars frame of `data/<run>/<name>.csv` as `ws.runs[(run, name)]` and returns nothing, so a cell that ends in it prints no table. The `name` defaults to `<model>_<notebook>`.
- `source` is one of `influxdb3`, `postgres`, `csv` (copy a local file in) or `builder` (a function the notebook gives, for synthetic data), and is required only when the csv is absent.
- `params` is a dict of the notebook's own literals, such as a time range, formatted into the `{name}` placeholders of `query` before it runs, so one query text serves several runs. It MUST NOT come from outside the notebook. The json records the formatted `query` and the `params`.
- It MUST read the csv if it is present and the run is not live, and MUST NOT touch the network in that case.
- It MUST otherwise capture and write the csv through a temporary file renamed into place, so a failed query writes nothing, and then write the json beside it.
- It MUST raise a `GateError` when a cached csv was captured with another `source`, `query` or `params` than the call gives, since stale data must not pass silently. A frozen run is refreshed on purpose by deleting its csv and json and running the notebook, then reading the git diff.
- When `live` is true it MUST capture again into the same run and overwrite the files on every execution, and the run MAY be given only to `monitoring`.
- It MUST accept a `run` that is an integer from 1000 and MUST require a non-empty `label`, the readable intent of the run. The label MUST read `<first date> to <last date>, <coverage>, <modelled|measured>`: the date bounds of the rows, a short `<coverage>` phrase of the notebook's own saying what part of the phenomenon the run covers (`full discharge`, `daily temperature swing`), and whether its labels come from a fitted model or from measurement. A live run SHOULD end at `LIVE_QUERY` in place of its last date. The label is not linted.
- It MUST read the `postgres` connection from the module environment, which needs `postgres` in `run_deps.txt`.

Real personal financial data MUST NOT enter git. The `data/` captures of a workspace that holds it MUST be git-ignored in the root `.gitignore`, and so MUST its `project/` and `model/` when its constants derive from it. `metadata.json` holds the version, hashes, target and release record and no value, so it stays committed. A checkout without the `project/` rebuilds it with `fab unittest`, and a release stops with a `GateError` until it has. A committed dataset or project in such a workspace MUST be synthetic, and the notebook rebuilds it when absent so a fresh checkout still runs. Such a workspace MUST say so in the Data dot points of its title cell, the first opening with `Personal data` and naming what is git-ignored, the `data/` captures and, when the constants derive from them, the `project/` (NB014).

### 6.6 Notebook conventions

A model notebook:
- MUST NOT declare the model name, a dataset name, a run or a query as a constant, since `setup_workspace` takes the name from the workspace and `collect_run` takes the rest as literals. A `pyfunc` MUST import the packages it needs inside the model (3.4).
- MUST define its splits with `prepare_split` in its Prepare stage, MUST fit only on its `training` split and MAY use its `validation` split to check the fit.
- MUST give `package_model` golden inputs in its Package stage, with the expected outputs taken from running the defined model. Golden is a project file (3.1), not a split, so no golden dataset is kept under `data/`. The golden sequences SHOULD include a first call with no state, boundary values, a missing required input that gives a signature error and a long gap, named by the `sequence` column.
- MUST list the data files used in `provenance.inputs`.
- SHOULD keep logic in `mlmodels` and cells thin.
- MUST run with the `asystem (Python 3.12)` kernel, never the Conda Python.

### 6.7 Notebook style guide

**File**
- A notebook MUST be Jupyter notebook format 4 and MUST be committed without outputs and without execution counts.
- A notebook MUST NOT contain secrets, absolute paths or notebook magics. Paths MUST come from `collect_run` and the workspace `ws.path`.
- A notebook MUST be deterministic: a random operation MUST use a fixed seed.

**Cell order**
1. The title cell, a markdown cell.
2. One markdown stage cell per stage, each followed by at most one code cell, which holds the whole of that stage.

**The title cell**
- It MUST hold the heading `# <module> / <model> / <notebook>`, the only level-one heading in the notebook, and then only bold labels on their own line, each followed by short dot points. The labels are Intent, Data, Status and Future, SHOULD come in that order, and Intent and Data MUST be present.
- A dot point is a short sentence of at most 25 words (NB004) and MAY have sub-bullets indented two spaces, each also a short sentence. Every top-level Future dot point MUST open with `Overall:` or `Phase <n>:`, end with a colon and group its points as sub-bullets. `Overall:` comes first and applies to every phase, and a notebook with no natural phases uses only `Overall:`.
- A dot point MUST NOT open with a label and a colon, restate another dot point, or state the flavour, the target or the runtime, which `setup_workspace` prints from `metadata.json` and the project at the head of every run. The cell holds no table, no prose and no label other than the four.

| Label | Required | Dot points |
|---|---|---|
| Intent | Always | One lead-in dot point, `<Verb> <outputs> from <inputs>, and must:`, then sub-points that each open with a verb and state one requirement of the model |
| Data | Always | Where each split comes from and how it was made, which are held back for acceptance, and any stand-in data and until when. For a workspace of real personal financial data the first dot point opens with `Personal data` (6.5) |
| Status | When unfinished or compared | What is a placeholder, undefined or not yet loaded, what the model gives up and, when the notebook compares candidate models, which is selected for release and the measured reason |
| Future | When planned | A change already prepared or intended and not yet used, the to do it needs, the decisions still open and when the data for it can be had |

- The Intent states the purpose of the model, not its contract, which `signature.json` already holds (names, units, optional inputs, ranges and steps). The lead-in opens with a verb that says what the model does (`Estimates` for a quantity it infers, `Predicts` for a forecast, `Gives` for constants), names the outputs, names the inputs after `from` when they matter, and ends `and must:`. Several outputs MAY instead be named one to a sub-point.
- Each Intent sub-point opens with a verb (`Hold steady`, `React quickly`, `Report zero`) and states one requirement: what the model computes, how accurate or stable it is, what it does when its input fails or stops, or what it is for. A requirement a gate enforces SHOULD name its limit. Requirements that belong together are one sub-point, and a sub-point restates neither the signature nor another sub-point.
- The Intent MUST name every output of the workspace `signature.json`, in backticks, as a name, a brace list `x_{low,high}_pct` or a pattern `wasm_*`, and MUST NOT name an input or output the signature lacks (NB013). A scaffold name that stands in for an undefined signature is named in the lead-in and said to be one.
- A dot point MUST NOT describe `golden` beyond what is particular to it, since 6.6 already requires it.
- A notebook that compares candidates MUST say in Status which is selected for release and why, against the acceptance limits of 6.8, and its Evaluate stage MUST show the comparison. A reviewer checks it, since no tool can tell a candidate from a variant.
- The to do of a notebook is its Future dot points, and nothing outside the notebook records it.

**Stages**
- A stage heading MUST be level two, `## <Stage> ([<number>](<url>#<anchor>))`, where `<url>` is the GitHub URL of this document on `master`, `<Stage>` is Title Case and one of the names in 6.7.1 to 6.7.10 in that order, and `<number>` and `<anchor>` are those of its subsection. A stage that does not apply MUST be omitted and the order kept. A stage MUST NOT use a heading deeper than level two.
- A stage cell MUST hold the heading and nothing else. What a stage is for is stated once, in its subsection, and the notebook's own purpose is the title cell's Intent.
- A stage MUST hold at most one code cell (NB015), one block of code that does the one thing the stage is for.
- A `mlmodels` function a notebook calls MUST be named `<stage>_<what>` for the stage it is called from, in lowercase: `setup_workspace`, `collect_run`, `prepare_split`, `prepare_folds`, `define_model`, `evaluate_model`, `evaluate_gate`, `package_model`, `register_model`, `pull_model`. The symbolic maths of `mlmodels.maths` (`tanh`, `add`, `const`), in which a traced function is written, keep their plain names.
- A stage MUST pass data to a later stage only through a field of `ws`, and `ws` has no field a notebook may add: the fields `setup_workspace` and the `mlmodels` functions set (`ws.runs`, `ws.training`, `ws.validation`, `ws.backtest`, `ws.monitoring`, `ws.folds`, `ws.models`), and `ws.params`, one dict of JSON values (numbers, strings and lists) that a stage writes and a later one reads, for the constants and fitted or tuned parameters a model is defined from. A name a code cell binds at module level MUST NOT be read by a later stage (NB018), so a stage can be read and re-run from `ws` alone. A notebook MUST read a split as `ws.training` and a signature name as `ws.inputs[0]`, never through an alias. Functions and imports are code, not data, and MAY be used across stages.

**Code**
- A notebook MUST import from `mlmodels` by name, never with `*`, and MUST NOT extend `sys.path`. The kernel carries the `PYTHONPATH`, which `notebook.sh` installs and the IDE source roots provide.
- Python MUST be formatted with `ruff format` at the repo line length of 200 and MUST NOT be hand-wrapped.
- Constants MUST be UPPER_CASE. A notebook MUST NOT carry a flag that switches the network on, since `collect_run` reads the committed file when it is present (6.5). The one exception is `live=True` on a run kept live, which makes every execution query the source and rewrite that run. A notebook with one needs the source reachable wherever it runs, and nothing it fits, evaluates or packages may read that run.
- A notebook MUST run through its Package stage from committed data (R15). The Register stage and anything after it writes to the registry, and a check MUST NOT write, so `notebook.sh` stops before it unless `REGISTER=1`. An acceptance that fails is recorded as the verdict and does not stop the run.
- A notebook MUST write its project only through `ws.project_dir`, which `setup_workspace` takes from `scratch_project_dir` and `model.sh` redirects to `target/model-output` with `MODEL_OUTPUT_DIR`, and never into a consumer's tree.
- A polars frame SHOULD be named with the suffix `_pl` and a path with the suffix `_path`. Imports SHOULD sit at the top of the cell that first needs them. A comment MUST NOT restate the code, and narrative belongs in the stage's markdown cell.

**Lint**

`fab build` lints every notebook under `src/main/notebook/*/*/*/` as it lints Python, and rewrites the source:
- `ruff check --fix` and `ruff format` run on the code cells with the repo `ruff.toml`. E402 is ignored in notebooks.
- `python -m mlmodels notebook --fix` strips outputs and execution counts and checks the notebook rules of section 9. The executed copy is kept under `target/notebook`, never in the tree.
- `python -m mlmodels workspace` checks each workspace against the rules of section 9.
- `ruff check --fix` and `ruff format` also run on a workspace's `model.py`, which is not type checked.

A finding other than NB002 fails the build. Notebooks are not type checked, since `pyright` does not check `.ipynb` files from the command line, and `fab build` does not run them. `notebook.sh` runs one headless, and `model.sh unittest` runs them all.

**Markdown**
- Identifiers, paths, commands and values MUST be in backticks.
- A table MUST have a Title Case header and Title Case first-column labels, each other cell MUST begin with a capital, and no cell MAY be bold.

#### 6.7.1 Setup

Required always. Returns the workspace with its environment, signature, input and output names and project directory (3.1), and prints the signature names, the run table and the model table. It takes no target, which Package sets.

#### 6.7.2 Collect

Stage 1 of 7.1. Required when the notebook reads data. Collects each run (6.5). All data a notebook uses MUST be collected here and reach every later stage through `ws`, so no later stage reads a file, queries a source or holds a data literal. The one exception is a named constant lifted directly from an external model, with a comment saying where it comes from, used to compare with or define that model as the incumbent. Each collection is self-contained, stating its run, label, dataset name, source and query as literals, so a run is defined in one place. Only a run declared live is refreshed. Setup prints each run's label and row count.

#### 6.7.3 Prepare

Stage 2 of 7.1. Required when the model is fitted or evaluated. One declaration forms the splits of 6.3 in memory from the collected runs, or one per fold when cross-validating, and each is available on `ws` by its split name. It enforces R6.

#### 6.7.4 Explore

Stage 3 of 7.1. Optional. Plots and checks on the training split. It MAY plot or score a prototype of a later model on any collected run for context, never to fit. A derived frame it builds is its own, since a later stage does not read it (NB018). Every plot SHOULD take a title, a short sentence stating the outcome the data shows, without a colon. Nothing reported from it ships (R4).

#### 6.7.5 Train

Stage 4 of 7.1. Required when the model is fitted. Plain Python on `training` only (R6), on the real feature names. It informs what Define freezes and calls no function that writes. A notebook that cross-validates runs its folds here, recording each fold's metrics, then declares its final splits and fits once on all the training data.

#### 6.7.6 Define

Stage 5 of 7.1. Required always. Freezes a model into `ws.models[model]` and writes `model/<model>/` (6.4).
- `model` is an integer of 1000 or more, unique in the notebook and never reused, as a run is. `label` is a short free text saying what the model is, shown in the model table, and SHOULD read `<form>[, <qualifier>]*`: the model's form first as a short noun phrase, then any qualifiers after commas. A model that reproduces an existing implementation is named for its source in a short acronym. The label names neither the runs nor the flavour and is not linted.
- `source` is the model as a value in the form its flavour takes: for `pyfunc`, text or a named function taking the inputs in signature order and returning the outputs in signature order, receiving `None` for an omitted optional input; for `wasm`, a named function, which is traced (4.3); for `onnx`, the bytes of the graph; and for `static`, the constants.
- `constants` are the fitted values, plain numbers, text, lists and dicts, and are the only free names a model function may read. Define MUST raise a `GateError` when a function reads any other free name that is not an import or a builtin. A `wasm` function MAY also read a function of the notebook or an operator of `mlmodels.maths`, checked the same way.
- Define MUST load the written file through the same runtime code a consumer uses, predict once, and raise a `GateError` when the outputs lack a required output of `signature.json` or give one it does not declare. A failed Define MUST leave no model directory.
- `runs` defaults to the runs of `ws.training`, and records what a model fitted per fold or on another selection was fitted on.
- A `pyfunc` file is rewritten by every execution and never compared with the committed copy. The git diff is the review of a refit, and R15 is the check that a re-run reproduces the hashes.

#### 6.7.7 Evaluate

Stage 6 of 7.1. Required when the model is fitted. Each model MUST be scored through the same runtime code that serves it.
- A prediction over a split gives one column per signature output, alongside the split's other columns that are neither inputs nor outputs, which are the incumbent. The truth stays in the split under the output's name. A signature with `state` is replayed in time order with the state carried, and a row missing a required input predicts null.
- Metrics use scikit-learn's names: `rmse`, `mae`, `max_abs_error`, `bias`, `p95_abs_error`, `r2` and `pearson_r`.
- The gate runs the acceptance checks of 6.8 for one model, logs one line per check with its label, split, name, measured value, limit and outcome, and records the outcome on the model with each fold's size, `gap`, scheme and metrics. A failing model prints and continues. Each cross-validated metric MUST be gated by checks named `<metric>_mean` and `<metric>_worst` (AC004).
- A summary logs one line per defined model with its id, label, flavour and verdict, naming the checks a failed model failed.
- The comparison plot shows each model's predictions for the first output with its verdict, and each model's difference from a reference model. No model is truth, and the incumbent is an ordinary model that MAY be the reference. A plot cell carries collapsed output metadata (NB016).

#### 6.7.8 Package

Stage 7 of 7.1. Required always. Promotes one model to the committed `project/` (R1, R3, R14) and sets the `target` that `metadata.json` holds. It logs the model, flavour, target, the short project hash and the golden steps replayed, and returns nothing.
- It MUST raise a `GateError` when the model directory of another model is on disk that this run did not define (R15), when a model that is not `static` has no gate result, or when a gating check failed.
- Golden takes only inputs, and the expected outputs come from running the model. Each row expects `ok` or `error`, an `error` being a request that omits a required input. An optional `sequence` column names each sequence, with the state reset between sequences, and an empty state input is carried from the previous output of its sequence.
- `project.json` records the `model_id` the project came from, and its `trained_on`, `notes` and `implementation` are derived from the model's record. The `runtime.python` of a `pyfunc` is read from the imports of its file.
- The model file in `project/` MUST be byte-identical to the one in `model/<model>/`.

#### 6.7.9 Register

Stage 8 of 7.1. Required when the target is `served`, and an `embedded` or `local` notebook omits it. Registers the packaged model with the alias `preview` and logs the version with its registry address. It is run by `fab systest` and never by `fab unittest` (10.5) and MUST raise a `GateError` when the model is not the packaged one.

#### 6.7.10 Pull

Not a stage of 7.1. Required where a round trip is tested. Pulls the preview back and compares its files with the project.

### 6.8 Acceptance

Each notebook owns what its model must achieve and how it is measured. The library enforces that it was done and records the outcome the same way for every model type. The notebook defines a function with no arguments, and the library validates and stores what it returns. A gate that is not met raises (10.5) at Package, so a failed acceptance blocks the release, while `evaluate_gate` records the verdict and the run continues.

- A notebook of a non-`static` flavour MUST define `acceptance_checks()`, measure the shipped model on `validation` or `backtest` data inside it with `evaluate_model`, return a non-empty list of checks and pass the function to `evaluate_gate(ws, model, checks)`. A project without one fails AC001.
- A check is `split` (`validation` or `backtest`), `output` (a signature output), `name` (the naming style), `value` (a number, or null when it could not be measured), `limit`, `direction` (`max` for a value that must not exceed the limit, `min` for one that must not fall below it) and optionally `gate`, which defaults to true. A `training` check does not exist, since the fit is not judged on its own data, and `golden` is judged by exact parity.
- The library, not the notebook, decides the outcome: a check passes when its value is within its limit, and a null value fails. A notebook MAY compute anything else, such as a one-sided error, a recall or a worst run.
- Every required scalar output MUST have a gating check. A `backtest` check gates. A `validation` check gates only for a model with no `backtest` yet, which its title cell MUST say and which the evaluation records as `independent` false (AC005). A model with a `backtest` marks its `validation` checks `gate` false.
- The budget is the standard score, the same for every model type. For a `max` check it is the value divided by the limit, floored at zero, and for a `min` check it is the limit divided by the value. A check passes exactly when its budget is 1 or less. The evaluation records the worst budget of the gating checks, or null if any gating check could not be measured. A lower budget means a larger margin. It compares a model with its own limits, not one model's accuracy with another's.
- `register_project` logs the run metrics `acceptance_passed` (1 or 0) and `acceptance_budget`, each measured value as `<split>/<output>/<name>`, each dataset with `mlflow.log_input` under the split as its context, and the tags `acceptance` and `acceptance_budget`. The release function copies both tags onto the released version.
- `evaluate_gate` returns the evaluation, and `package_model` raises `GateError` when a gating check failed, so the run fails.
- The limits live in the notebook's function, so a changed limit is a change to that notebook and the release review reads that diff. No tool compares limits between versions, and a limit loosened there is accepted unless a review catches it.

**Gates for what the data can show.** What a check may measure depends on the reference available, and a notebook MUST NOT call something truth that is not.
- *Truth available.* A label measured independently of any model is truth, and the gates are the error against it (`rmse`, `mae`, `max_abs_error`) together with a stability check such as bounce.
- *No truth.* Labels may be the output of a deployed system, such as the `template_` and `mlserver_` columns every dataset keeps. That output is an observation of a model, so the system it came from is defined as a model of its own, the incumbent, and is never a baseline. It gates only on parity, an `rmse` against the deployed output with a tight limit, because that proves the model reproduces what runs. Every other model gates on what needs no truth: stability (bounce, or rises on a one-way discharge) and the range and steps of the output.
- *Reported, not gated.* Agreement with the incumbent and any shape test, such as the correlation of output with elapsed time, are checks with `gate` false and a reference limit. They show change from what runs today and are not a claim of accuracy. A shape test is worth gating only on a full run, since a partial one cannot show it.
- *Backtest.* A run no decision has touched that covers a full cycle is the first place truth-like gates are meaningful: error against the time-normalised capacity and linearity then gate, and the `validation` checks stop gating (AC005). Quality and the gates improve as more runs accumulate, each allocated to one split and never moved.

### 6.9 Worked examples

The module `example` holds one worked project for each flavour, each with a notebook, an acceptance check and a golden file, replayed in every runtime that supports its flavour. A new flavour, runtime or runner SHOULD be tried on these first.

| Notebook | Flavour | Shows | Python | Rust | Go |
|---|---|---|---|---|---|
| `example/static/constant` | `static` | A constant and the register and pull path | Yes | Yes | Yes |
| `example/wasm/accumulate` | `wasm` | A fitted line built into a module, with a state vector | `wasmtime` | `wasmi` | `wazero` |
| `example/wasm/saturate` | `wasm` | A fitted `tanh` curve whose module imports `tanh` from the host, so `runtime.wasm` is `["tanh"]` and the golden states a tolerance | `wasmtime` | `wasmi` | `wazero` |
| `example/onnx/linear` | `onnx` | A fitted line as a graph at a pinned opset | `onnxruntime` | `ort` | `onnxruntime_go` |
| `example/pyfunc/linear` | `pyfunc` | A fitted line as a `PythonModel` | `mlflow.pyfunc` | No | No |

The reference consumers are under `src/main/python/mlmodels/runtime`, `src/main/go/mlmodels/runtime` and `src/main/rust/mlmodels/src/runtime` (10.8). Each takes a project directory, checks each file against the hash in `project.json` (PJ003), replays its golden exactly or within the golden tolerance, and exits 0, or exits 1 on a difference or a flavour it does not support.

## 7. Lifecycle

### 7.1 Model lifecycle

| # | Stage | Who Runs It | Command or Hook | Output | Gate to the Next Stage |
|---|---|---|---|---|---|
| 1 | Collect | Notebook | `collect_run(...)` | `data/<run>/<name>.csv` and its json | The run is in the workspace schema |
| 2 | Prepare | Notebook | `prepare_split(...)` | The splits in memory | No two splits share rows undeclared, and a live run is only `monitoring` |
| 3 | Explore | Notebook | Plain Python | Ideas, plots | None |
| 4 | Train | Notebook | Plain Python | Fitted values | Fit error on `training` is sane |
| 5 | Define | Notebook | `define_model(...)` | `model/<id>/` and `ws.models[<id>]` | The model loads through its runtime code and its outputs match the signature |
| 6 | Evaluate | Notebook | `evaluate_model(...)`, `evaluate_gate(...)` | Metrics, the verdict on `ws.models[<id>]` | Every gating acceptance check of the candidate passes |
| 7 | Package | Notebook | `package_model(...)` | `project/` and `metadata.json` in the workspace | Manifest, hashes, signature and golden agree, the signature only grew at its signature version, and no undefined model directory remains |
| 8 | Register | Notebook | `register_model(...)` | A registry version with the alias `preview`, for a project with a `served` target | The registry shows it with its tags |
| 9 | Test target | `fab systest` | 10.5 | None recorded, a failure fails the run | The declared target passed |
| 10 | Release | `fab release` | 10.6 | The release version in `metadata.json`, `release` moved, `preview` removed | The label is `READY` in the production index |
| 11 | Embed | The consumer's `generate.sh` | `python -m mlmodels embed <consumer dir> <source dir> <name>`, or `python -m mlmodels embed-loader <consumer dir> --language python` for a consumer that loads any model at run time | The released `project/` copied unchanged into the consumer's `src/build/resources/model/<notebook>/`, with the loader and the generated model file beside its code, unstaged | The hash of the copy equals `content_sha256` in the workspace's `metadata.json`, and CP005 and CP006 hold |
| 12 | Release the consumer | A person | The consumer's own `fab release` | A release of the consumer | `check-release` and the consumer's own tests |

### 7.2 Consequences

- Builds do not call MLflow. Only `mlmodels` writes to it, and `mlserver` and the system test read from it.
- A served model is taken from the registry by the sync loop, so moving the alias changes what is served without a consumer release. An embedded consumer needs the embed, a commit and its own release.
- A breaking signature change of a served model raises its signature version, so it is served under a new name beside the previous version while consumers move, and the version before that is retired when a newer one is released (10.6). An embedded model changes in place (10.2).
- A revert needs `fab deploy` in the module, the log of stale consumers is the only prompt to release one, and a model with no usable version is logged and unserved.

## 8. Module requirements

MLflow owns data and lifecycle, MLServer only serves, and nothing is shared by a mount.

| Thing | Where | Requirement |
|---|---|---|
| Notebooks and Their Data | `mlmodels` | Fitting and registering MUST sit in the `mlmodels` module, apart from the tracking and serving containers, and notebooks MUST be thin |
| The Library Package | `mlmodels` | MUST be one implementation, unit tested, with one module per concern, no logic in notebooks that belongs here, and one command, `python -m mlmodels`. `mlmodels.testing` is its one public module besides the notebook API, for tests |
| Tracking DB, Registry, Artifact Storage | `mlflow` only | MUST serve artifacts through its proxy, so no client writes a path or needs a share |
| Allowed Hosts | `mlflow` | MUST allow the hosts and origins its clients use |
| Models in `mlserver` | A local volume | MUST be pulled by the sync loop (10.4), replaced only after the new copy verified, MUST NOT stop serving on a failed pull, and every call MUST be bounded by a timeout |
| Embedded Copies | The consumer's tree | MUST be pulled by the consumer's `generate.sh`, reviewed as a diff, and never fetched at build or run time |
| Embedded Loader | A consumer | MUST hold the loader `mlmodels` writes, unedited and current, with the dependencies and features it needs declared in its manifest (10.9), and MUST keep its own policy, thresholds and request translation outside the `model/` directory |
| Server Start | `mlflow` | MUST stop the start when its database upgrade fails |
| Probes | `mlflow`, `mlserver` | MUST address the service by its service name and port and never `localhost`, except a check that runs inside the service container, since `bootstrap.sh` runs in a separate container |
| Serving Start | `mlserver` | `checkalive` MUST be server live, `checkexecuting` MUST add server ready, and `checkhealthy` MUST add that every model in the repository index is `READY` |
| Serving Runtime | `mlserver` | MUST load a project through the bundled loader, only after every file matches its manifest hash and its acceptance passed, MUST answer the V2 inference API for every flavour with the same outputs as `replay`, MUST refuse a request missing a required input, and MUST be self-contained, with a unit test comparing it with `replay` per flavour |
| Serving Release | `mlserver` | A promotion MUST need neither a release nor a restart of `mlserver` |
| Artifact Upload | The `mlflow` proxy | MUST accept a request body large enough for a project and its model file, since the proxy's default cap of 25k refuses a `golden.json` with `413` |
| Telemetry | `mlflow`, `mlserver`, scripts | MUST be off |
| Registry Address | Every client | MUST use the proxy name from `MLFLOW_TRACKING_URI`, and MUST report a refusal from the published host and port as a finding, since it answers `/health` only and returns `403 Invalid Host header` elsewhere |
| Declared Models | `mlserver` | There MUST be no list of served models: every registered model carrying the mlmodels tags and an alias `release` or `preview` is served |
| Serving Smoke Test | `mlserver` system test | MUST start with the `example` models, replay each project's `golden.json` through the inference API and fail on a model that is not `ready` or whose served label differs from its release label |
| Status and Rollback | `model.sh` | `status` MUST read without writing and show each model's release label, aliases, hashes and whether it is `READY` on `mlserver`. A rollback is a revert in git followed by `fab deploy` in the module |
| Health | Both services | MUST be real checks with every call bounded, and `mlflow` healthy MUST also read the registry and experiments API |
| Shutdown | Both services | MUST have a stop grace period |

## 9. Checks

A project, a notebook and a workspace MUST pass the checks below (R13). Each check has an identifier, which the tool prints with its finding.
- A project is checked by `verify_project`, which `write_project`, `package_project`, `register_project` and `registry_pull` call, and by `python -m mlmodels verify` and `lint`, which print every finding.
- A release is checked by `check_release`, which `fab release` runs through `check-release` for a consumer and `model.sh release` for a workspace.
- A notebook is checked by `python -m mlmodels notebook` and a workspace by `python -m mlmodels workspace`, both run by `fab build`.
- `embed`, `embed-loader` and `verify` write and check a consumer's loader, model files and project slot, and `check-release` runs CP004, CP005 and CP006 on them.

A notebook states what it means and not how it is done, through the stage functions of 6.7 imported from `mlmodels` by name. The `_`-prefixed modules behind them are the library, and a notebook MUST NOT reimplement them. `mlmodels.testing` is the one public module beside them, for tests and not for notebooks: `example_project` copies a committed worked example (6.9) for a consumer's tests to serve and replay, and `build_project` packages a small project of any flavour when a test needs a variant, so no consumer needs a copy of a project or an import of a `_` module.

The identifiers, the flavours of 3.2, the splits of 6.3 and the stages of 6.7 are mirrored in code, and a test fails if the specification and the code disagree in either direction.

### 9.1 Invariants

| Id | Invariant | Enforces |
|---|---|---|
| PJ001 | A project has a manifest, and every JSON document in it starts with a supported `schema` | R1 |
| PJ002 | The flavour and the provenance source are known, the provenance inputs are a list, and a flavour but `static` states its implementation as more than one word and not a placeholder | R1 |
| PJ003 | Every file the flavour requires, `signature.json`, `golden.json` and the `model` file, is in `files`, exists, and matches its SHA-256 | R1 |
| PJ004 | The project name follows the naming style and equals the signature name | R12 |
| PJ006 | The signature is complete: datatype, shape, unit, required flag and description on every input and output, unique names, state slots numbered from 0 | R1 |
| PJ007 | Every output ends with the unit suffix of its unit | R12 |
| PJ008 | Constants name signature outputs, and a `static` project gives a constant for every required output | R8 |
| PJ010 | Every golden step has a response or an error, names only signature inputs and outputs, and gives every required input and output | R3, R4 |
| PJ011 | The golden holds a step that expects a signature error, and a first call with no state when the signature has state | R8 |
| PJ012 | Every golden response of a `static` project equals the constants | R4 |
| PJ015 | A golden tolerance names an `FP64` signature output and gives a non-negative `absolute` or `relative` bound, or both | R5 |
| PJ016 | A `wasm` module imports only the maths functions of 4.1, each as `(f64, ...) -> f64` of its arity | R4 |
| PJ017 | A `wasm` project's `runtime` equals its module's imports, a `pyfunc` project's `runtime` lists exactly the packages its `model.py` imports beyond the standard library and the base, and no other flavour has a `runtime` | R11 |
| AC001 | A project that is not `static` holds an evaluation, and every required scalar output has a gating check in it | R14 |
| AC002 | A check names a known split, a name in the naming style, an output in the signature, a numeric or null value, a limit and direction, and a boolean gate | R14 |
| AC003 | The recorded outcome, budget and verdict follow from each check's value and limit, the evaluation holds dataset hashes for every split it uses, and a check with a measured value has at least one dataset recorded for its split | R14 |
| AC004 | A cross-validated evaluation numbers its folds from 0, names a known scheme, gives a gap and sizes, records the same numeric metrics in every fold, and gates each metric with checks named `<metric>_mean` and `<metric>_worst` | R14 |
| AC005 | The evaluation's `independent` is true exactly when a backtest dataset is recorded, and a `validation` check gates only when it is not | R14 |
| CP004 | A consumer's embedded project, in `src/build/resources/model/<notebook>/`, hashes to the released project of its model | R7 |
| CP005 | A consumer's `loader.<ext>` equals the current `mlmodels` loader with its banner, and each of its model files names the released project it was generated from | R18 |
| CP006 | A consumer's model files are unique, none uses a reserved name (`loader`, `model`, `mod`, `__init__`) or a keyword of its language, each belongs to a released workspace, and its generated directory holds no file that `embed` does not own | R18 |
| NB001 | The notebook is format 4 | R13 |
| NB002 | The notebook has no outputs and no execution counts | R13 |
| NB003 | The notebook has exactly one level-one title, `# <module> / <model> / <notebook>`, matching its directories | R13 |
| NB004 | The title cell is the heading and then only a bold label of Intent, Data, Status or Future on its own line and dot points of at most 25 words, each of which MAY have indented sub-bullets of the same length, with Intent and Data present and every top-level Future dot point opening with `Overall:` or `Phase <n>:` | R13 |
| NB005 | The stages are the names of 6.7, in order, none deeper than level two, with Setup present | R13 |
| NB006 | Every stage cell is only its heading, with the link to its 6.7 subsection | R13 |
| NB007 | A code cell has no magics, shell lines, absolute paths or literal secrets | R13 |
| NB008 | `setup_workspace` is called with the workspace, which fixes the registered name that 6.1 requires | R12 |
| NB009 | No table cell is bold | R13 |
| NB015 | A stage holds at most one code cell | R13 |
| NB016 | A code cell that calls a plot function has its output collapsed | R13 |
| NB017 | A code cell does not rename a column | R12 |
| NB018 | A name a code cell binds at module level is not read by a later stage | R13 |
| NB014 | The first Data dot point of a workspace whose `data/` captures or `project/` git ignores opens with `Personal data`, and for the `project/` a Data dot point names it | R13 |
| NB011 | A notebook imports from `mlmodels` by name and never with `*` | R13 |
| NB012 | A notebook does not extend `sys.path`, since the kernel carries it | R13 |
| NB013 | The Intent names every output of the workspace `signature.json`, as a name, a brace list `name_{a,b}_x` or a pattern `prefix_*`, and no name with the model prefix that the signature lacks | R13 |
| PM004 | A project that is not `static` has an evaluation and every gating criterion passed (a `static` project with no evaluation passes), which `check_release` also applies to a consumer's embedded project | R14, R15 |
| RP001 | A replayed step that expects a signature error does not supply every required input | R8 |
| RP002 | A replayed step supplies every required input | R8 |
| RP003 | A runtime reproduces every golden response exactly | R5 |
| RP005 | A runtime gives an answer to every replayed step | R5 |
| MD001 | A released workspace has a `metadata.json` that is valid JSON of the supported schema | R1 |
| MD002 | Every metadata field is present and of its type, the `version` of an unreleased project is a snapshot version or null, that of a released project is a release version, and a `release` holds a timestamp and a signature | R1 |
| MD003 | A `project/` sits beside the metadata, its `project.json` hash equals `content_sha256`, and the workspace `signature.json` equals the project's | R1 |
| MD004 | The target is `served`, `local`, or `embedded` with a reference consumer for the flavour | R1 |
| MD005 | Every Python package in the project's `runtime` has a global pin, and each requirements file (3.5) equals the names derived from the project and the target, with none left for a language the target does not use | R11 |
| MD006 | A workspace's `signature.json` holds an integer `signature_version` of 1000 or more, whatever its target. `baseline` is present only on a served target | R10 |
| WS001 | The module, model and notebook directories follow the naming style | R12 |
| WS002 | A notebook directory holds exactly one notebook, named `notebook.ipynb` | R13 |
| WS003 | A notebook directory holds only the notebook, `signature.json`, `metadata.json`, the requirements files, `project`, `data` and `model` | R13 |
| WS005 | The data directory holds only run directories numbered from 1000, gaps allowed | R6 |
| WS006 | A dataset is a csv named `<model>_<notebook>_...`, and with a json of the same name | R12 |
| WS011 | The model directory holds only model directories numbered from 1000, each with a `model.json` that names its id and, for a model that is not `static`, the model file the json hashes | R13, R15 |
| WS012 | Every required input of a workspace with a model that is not `static` is a column of every dataset of every run | R12 |
| WS013 | A notebook name is unique within its module among the workspaces that load in the same language, an `embedded` target loading in its own language and a `served` one in Python, and a `local` target is exempt | R12 |
| WS014 | A workspace with an `embedded` target, outside the module `example`, has a module of its own name under `src/<host>/` to embed it | R12 |
| WS015 | A notebook name is not all digits and does not end in `_<digits>`, so a trailing number in a registered name is always a signature version | R10, R12 |
| WS008 | Every csv has a json beside it that names its run, label and live flag and holds the SHA-256 of the csv | R6 |
| WS009 | Every run of a dataset has the same columns | R6 |
| WS010 | Every column a json lists as `inferred` is a column of its csv | R6 |

### 9.2 Coverage of the requirements

Each requirement is checked by the identifiers below, or by review where no tool can check it. A test fails if this table and the Enforces column of 9.1 disagree.

| Requirement | Checked By |
|---|---|
| R1 | PJ001, PJ002, PJ003, PJ006, MD001, MD002, MD003, MD004 |
| R2 | Review |
| R3 | PJ010 |
| R4 | PJ010, PJ012, PJ016 |
| R5 | PJ015, RP003, RP005 |
| R6 | WS005, WS008, WS009, WS010 |
| R7 | CP004 |
| R8 | PJ008, PJ011, RP001, RP002 |
| R9 | Review |
| R10 | MD006, WS015 |
| R11 | PJ017, MD005 |
| R12 | NB008, NB017, PJ004, PJ007, WS001, WS006, WS012, WS013, WS014, WS015 |
| R13 | NB001, NB002, NB003, NB004, NB005, NB006, NB007, NB009, NB011, NB012, NB013, NB014, NB015, NB016, NB018, WS002, WS003, WS011 |
| R14 | AC001, AC002, AC003, AC004, AC005, PM004 |
| R15 | PM004, WS011 |
| R16 | Review |
| R17 | Review |
| R18 | CP005, CP006 |
| R19 | Review |

### 9.3 Output of test runs

Every run of a notebook, a unit test or a system test, in any flavour and language, prints in the shape of `go test -v`, so Python, Go and Rust output reads the same.

```
=== RUN   notebook example/wasm/saturate
    setup        ... done [1 in 1 out] (0.44s)
    train        ... done [1 cell] (0.00s)
    requirements ... done [0 to add] (0.00s)
    metadata     ... done [wasm] (0.00s)
--- PASS: notebook example/wasm/saturate (1.34s)
```

- A subject opens with `=== RUN` and closes with `--- PASS`, `--- FAIL` or `--- SKIP` and its seconds. A run ends with `PASS` or `FAIL` and a suite line with its seconds.
- A stage is one indented line giving its name, `done` or `FAILED`, a bracketed value and its seconds. A `done` line is never bare: a stage with nothing to say prints `[none]`, and a notebook stage with no detail of its own prints the number of cells it ran. The library functions of the workflow hand their detail to the run (`setup` the size of the signature, `collect` the runs and rows, `prepare` the rows of each split, `define` the models, `evaluate` the candidate and its verdict, `package` the candidate, flavour and golden steps, `register` and `pull` what they did).
- A notebook's stages are those of 6.7 lowercased, then `requirements` and `metadata` (3.4). A reference consumer prints `verify`, `load` and `replay`, and a system test also prints `compile` and, for a `served` target, `registry` and `serve`.
- A finding is printed on standard error as `ERROR <rule> [<message>]` and an error as `ERROR [<message>]`. A consumer repeats this shape in its own language and MUST NOT import `asystem`.

## 10. The mlmodels release model

`mlmodels` follows the pattern of the schema and certificate modules: the declaration is in git, `generate` reflects it into committed artifacts, a release ships what is committed, live state changes only through idempotent verbs, and `status` verifies.

### 10.1 Ownership

- The module `src/rue/mlmodels` MUST own the notebooks, their data, this specification, `model.sh`, `notebook.sh`, the reference consumers (10.8) and the loaders (10.9). It MUST run-depend on `mlflow`, `mlserver` and `influxdb3`, and release independently of them and of the consumers.
- `mlflow` and `mlserver` MUST be only a container and its configuration. `mlserver` keeps its `serving` and `registry` packages, which MUST NOT be named `mlserver` or `mlflow`.
- `mlmodels` MUST use `mlflow` and `mlserver` as production services, through the connection variables of its run dependencies and the `*_PROD` endpoints, as `supervisor` uses `vernemq`. It MUST NOT start, build or test them.
- Each of `mlflow` and `mlserver` MUST test itself in its own module. `mlserver` MUST test its `serving` and `registry` packages, its sync loop (fallback, a failed reload, an unreachable registry, an alias moved back, a failed version not retried) and its container, and `mlflow` MUST test its container and configuration. The tests of a project belong to `mlmodels`.
- `mlmodels` and its commands MUST live in the `mlmodels` module. fab and every consumer's `generate.sh` reach them as a command with that module's `src/main/python` on `PYTHONPATH`, and `replay` MUST run a model through the same Python loader that the reference consumer and `mlserver` use.
- `mlmodels` MUST have no `.group`, so it runs before every grouped module in each fab phase and has no per-host install. It MUST read its configuration from the generated `.env` and use the `*_PROD` variables for the production services.

### 10.2 Versions and metadata

- A project MUST NOT carry a release version. Its golden file and model file hold no stamp, its signature holds only the signature version (3.1), and its content hash, `content_sha256`, is the SHA-256 of its `project.json`, which lists the hash of every other file.
- Each workspace MUST hold `metadata.json` and a committed `project/`. `metadata.json` MUST hold `schema`, `version`, `content_sha256`, `inputs_sha256`, `target` and `release`, in that order, then `baseline` for a served target that has been released, and nothing the project or git can derive: not the `runtime`, which is in `project.json`, nor who released it, which is in the release commit. It MUST be validated by the library and written only by tooling, never by a notebook. A `metadata.json` without its `project/` MUST be a finding. The layout is `schema` 2, and the library reads no other. `baseline` is the `signature.json` of the last release of a served target: `fab release` writes it with `release`, packaging seeds it from `release` when it is absent and never clears it, and a content change leaves it in place while setting `release` to null. It is the only record the compatibility check has between one release and the next.
- `target` MUST be the one environment the project is to run in: `{"kind": "served"}`, `{"kind": "embedded", "language": "python"|"go"|"rust"}` or `{"kind": "local"}`. The notebook MUST declare it where it packages the project, tooling MUST copy it into `metadata.json`, and the library MUST check it against the matrix of 10.8. A project has exactly one, so a fixture that is to run in several languages is several notebooks. A `local` project is skipped by `fab systest` and `fab release`, is never registered and so can never be pulled by `mlserver`, and keeps a null `release`. Promoting it replaces `local` with the target it is to run in, and nothing else about the project changes. A notebook with nothing to record is not a project and belongs outside `mlmodels`.
- `version` MUST be the repository snapshot version, from the root `.version`, in force when the project's content was first recorded, until the project is released, and then the release version. It MUST be kept while the content hash is unchanged, MUST be null only for content recorded when the root version was not a snapshot, and MUST NOT be written into any file of `project/`.
- `release` MUST be null until the project is released, and then `{"timestamp": <UTC, to the second>, "signature": <the project's signature.json>}`, written by `fab release` alone. A project is released exactly when it is not null. If a rerun reproduces the content hash, `version` and `release` MUST be kept. A change of a runtime package version MUST rerun and retest.
- `inputs_sha256` MUST cover the code cells, the data files of the frozen runs, the workspace `signature.json` and the versions of a named list of runtime packages, and MUST NOT cover a live run, which reaches only `monitoring` and so cannot change a model, nor markdown, nor the source of the `mlmodels` library or `asystem`. A notebook whose inputs hash is unchanged MUST NOT be rerun. A notebook that never calls `package_model` is a scaffold with nothing to package, and `model.sh` MUST skip it in `unittest` and `systest` alike, reported as `--- SKIP:` with the reason `nothing packaged`.
- A signature change at the same `signature_version` as the `baseline` MUST be additive to be packaged: a new optional input, or a new output. A higher version MAY make any change, and a lower one MUST be refused. A breaking change therefore raises `signature_version` in place, and the registry serves the old and the new version side by side (10.4, 10.6). The check runs once, in `record_project`, against `baseline`, and a signature with no version, released or new, is a finding.
- **Exception, an `embedded` target.** Its only consumer is the module of its own name (WS014), embedded and released with the model, so no consumer runs an older signature than the one the next release carries and nothing is served by alias. A breaking signature change MAY be made in place under the same name, and `package_model` MUST NOT refuse it for that target. The consumer is then re-embedded and released with the model, which CP004 and CP005 enforce, and a `served` target keeps the rule above.
- A workspace in the module `example` is a test fixture and MUST NOT be released. A workspace that produces no project MUST be skipped. The notebook name `preview` is reserved.

### 10.3 Registry

- Each registered model has the aliases `preview` (the version under test) and `release` (live), which are independent pointers. They are the MLflow aliases, so a consumer resolves one as `models:/<name>@<alias>`, and the version tags mirror them. The artifact moved to `release` MUST be the one that was tested, found by its content hash.
- Only `register_model` MAY set `preview`, and only the release function of `mlmodels` MAY set `release`, remove `preview`, or remove `release` from a retired signature version (10.6). A production consumer MUST use `release`, and only a system test MAY use `preview`.
- The version tags MUST mirror `metadata.json`: the whole file as one compact JSON tag, and `release_version` (its `version`), `released_at` (its `release.timestamp`), `inputs_sha256`, `content_sha256` and `project_flavour` as scalars. A model is a mlmodels model when it carries `content_sha256` and `project_flavour`. The flow MUST be from git to the registry only.
- A version registered before its release MUST carry the tag `snapshot_version`, the `version` of `metadata.json`, which the release function MUST remove when it sets `release_version`. The tag is set when the version is first registered and is not changed by a later registration of the same content.
- The tags MUST be set before `release` is moved, so a reader never sees an alias without its tags. A version that has carried `release` MUST NOT be deleted.
- The registry MUST be written only through `mlmodels._registry`.
- **Review and serving only.** `mlmodels` owns the workflow, and MLflow is used for two things: review, where it records what git already holds so a reviewer can inspect and compare it, and serving, where it hands a verified release to `mlserver`. A tracking feature is adopted only where it makes that record more informative. No stage, validation or evaluation feature of MLflow MAY decide what is released, served or embedded, or replace the acceptance gate of 6.8, the release function or the alias rules above.
- **What a run records.** `register_model` takes it from the workspace, so a notebook adds nothing: the run params (the model, its label and flavour, the runs fitted on, the fitted constants, `ws.params`, each split's rows and, when cross-validating, the fold scheme and gap), the fold metrics, each split's datasets as their real frames so MLflow holds their schema, the evaluation figures and the predictions of each acceptance split as a table, and the git commit. Each model version carries its signature as its description. Everything is derived from the workspace and the project, and none of it is read back for a decision.

### 10.4 Serving

- `mlserver` MUST run a loop every `MLSERVER_POLL_SECONDS` (default 30) that reads the registry's aliases in one call and serves every mlmodels model: the alias `release` as `<name>`, and the alias `preview` as `<name>_preview` when it differs from `release`. It unloads the rest. There MUST be no list of served models.
- It MUST download a model only when its alias version or content hash differs from what it holds, verify every file against the manifest and the acceptance verdict, swap the directory by rename, and then call `POST /v2/repository/models/<name>/load` on localhost.
- **Fallback.** For each model it MUST try the version the alias points at first and, when that cannot be downloaded, verified or loaded, the released versions older than it, newest first, and serve the first that works. A version that failed MUST be remembered, with its content hash, and not retried every poll. A model with no usable version MUST be logged as an error and left unserved, and MUST NOT stop any other model. An alias moved back to an older version MUST be followed.
- A served project is registered under its served name, so each signature version is its own registered model with its own versions and aliases, and a fallback never crosses a signature change. A signature version stays served while its registered model holds a `release` alias: the loop has no rule of retirement, the release function removes the alias (10.6), and the loop unloads the model on its next poll with no restart. It MUST delete a model's files only when the server accepted the unload or was unreachable, and keep them for the next poll when the server refused.
- A failed reload MUST leave the model that is serving untouched. A failure to reach the registry MUST leave every loaded model serving. At start the loop MUST run once before `mlserver start`, with the same fallback, and the server MUST start whatever the outcome.
- The version label in `/v2/repository/index` MUST be the release version for `<name>` and `preview-<hash8>` for `<name>_preview`, so the index shows exactly what is live. A poll that changes nothing MUST NOT log at INFO, and a change MUST be reported as a `=== RUN   sync <served name>` or `unload <served name>` block with a stage for each step, in the shape the notebook run uses.
- `healthy` MUST mean every model in the repository index is `READY`. A release of `mlserver` MUST need no action by `mlmodels`.
- A model added at runtime appears `UNAVAILABLE` until loaded, a reload in place MUST serve without errors, and a failed reload MUST leave the old model serving, so the loop needs no restart.
- A release of `mlserver` recreates its container and re-syncs every model before the server starts, which is the one interruption in the design, so `mlflow` MUST release first and both are released on `may`. A registry that is down at that moment leaves nothing loaded.

### 10.5 Testing

- **`fab unittest`** is the pre-release test. It MUST run every notebook whose inputs changed through its Package stage and no further, run its acceptance check, lint the notebooks, and replay each project's golden file in process in Python, exactly or within the golden tolerance. It MUST write `project/` and the hashes in `metadata.json` for a notebook it reran, so the diff is read before a commit, MUST NOT start a container and MUST NOT write to any service.
- **`fab systest`** tests the projects, not `mlserver`, and MUST NOT depend on what an earlier run left behind. It MUST run the notebooks through their Register stage and wait for each push before it runs any test:
  1. *mlflow.* `register_model` MUST register each project that has a `served` target with its tags and set `preview` in the production registry. A project with an `embedded` or `local` target MUST NOT be registered. The system test MUST wait until the registry returns that version under `preview` with its tags.
  2. *mlserver.* For a project with a `served` target it MUST wait until the production `mlserver` shows `<served name>_preview` as `READY` in its index under the expected `preview-<hash8>` label or, when the project is the released one and so has no preview of its own (10.4), `<served name>` as `READY` under its release version. For an `embedded` target it MUST build the reference consumer container and wait for it to be ready to run.
  3. Only then MUST it run the target, on the local architecture. It MUST NOT emulate another architecture, since emulation added minutes and could not show a result specific to a CPU, and `wasm` is deterministic by its ABI. A run on another architecture is a run of `fab systest` on a host of that architecture.
  - A `served` target MUST be called through the `served` reference consumer against `<served name>_preview` on the production `mlserver`. No `mlserver` is started for a test.
  - An `embedded` target MUST run in an isolated container the reference consumer of its language and flavour (10.8) on the project's own model, so a WebAssembly project for Go runs as WebAssembly in the Go reference consumer, and on every consumer slot of that name. A consumer's own unit test MUST replay its compiled loader once through `<notebook>::load`, so the typed conversions are exercised.
  - A target with no reference consumer MUST fail with a finding.
- The system test MUST remove `preview` in every outcome using the library, MUST NOT move `release`, and neither level MUST write to git. The removal MUST cover every served workspace and not only those a test reached: `model.sh systest` clears them when its notebooks fail, the test session clears them on its way out whatever failed, and `model.sh clear-previews` does it by hand. The check that the image is built for this version MUST name the likely cause when another release has moved the repository version on mid-run. A step that does not complete within its bound MUST fail the run with the step named, and no later step may run.
- A passed target is not recorded. `fab release` runs `fab systest` first and stops at the first failed gate, so a release is only reached by content that passed, and `model.sh release` MUST be run only through `fab release`.
- **Gates fail loudly.** Every gate in the notebook library MUST raise `GateError` when it is not met: the notebook lint and layout, the project lint and verify, the acceptance check, the golden replay, the signature compatibility check, the comparison with a consumer's `default` slot, and each step of `fab systest`. A gate MUST NOT print a verdict and carry on, return a flag for the notebook to test, or be left to an assertion in a cell, and a notebook MUST NOT assert a gate itself.
  - A `GateError` MUST carry the stage, the gate and the cause. The stage is one of the workflow stages (Setup, Collect, Prepare, Explore, Train, Define, Evaluate, Package, Register, Pull), a release step (Release, Embed, Image, Metadata) or a system-test step (notebooks, mlflow, mlserver, target). The cause names the rule codes and the values. The message MUST bracket every interpolated value.
  - `package_model` MUST write `evaluation.json` and then raise when a gating check failed or could not be measured, so the verdict can be read and the run still fails.
  - `fab unittest` and `fab systest` MUST run every notebook and target to its first failed gate, MUST NOT run a later stage of the one that failed, and MUST finish by listing each failure with the notebook or target, the stage, the gate and the cause, and fail.
  - The release MUST NOT proceed past a failed gate.

### 10.6 Release and deployment

| Verb | Behaviour in `mlmodels` | As in |
|---|---|---|
| `fab generate` | Runs no notebook. Checks `metadata.json` against `project/`, checks the signature against the released one (10.2), and embeds the committed `project/` and the loader into each consumer through the consumer's `generate.sh` (10.7), formatting them and writing nothing when nothing changed | `fab generate` reflecting a schema; `certificates.sh pull` at generate |
| `fab build` | The loader compiles against the signature | |
| `fab unittest` | Runs the notebooks whose inputs changed to Package, writes `project/` and the hashes in `metadata.json` (with `release` null for unreleased content), and replays in process, with no service written. Then the unit tests of every module | The unit tests of the other modules |
| `fab systest` | Runs the notebooks through Register, which sets `preview`, waits for `mlflow` and then for the production `mlserver`, packages the `mlmodels` image, then tests each target but `local` (10.5) | `fab schema`, describe and verify |
| `fab package` | Builds the `mlmodels` image through the shared packaging step, with the `PINS` build argument from `model.sh docker-args`. `execute` has nothing to run for `mlmodels`, whose `Dockerfile` is a test environment | |
| `fab release` | After both tests, runs `check-release` on each of a consumer's embedded projects, which fails a stale loader or model file (CP005, CP006). For `mlmodels` it then writes the release version into `metadata.json` for changed content, moves `release` to each tested version through the release function, removes `preview`, writes `baseline`, retires older signature versions (10.6), logs the stale consumers, and the commit and tag carry `metadata.json` and `project/`. It does not change a consumer | `install_pre.sh` publishing discovery when the version changes |
| `fab pull` | Backs up git-ignored files, runs `git pull --all`, merges each project's requirements files into the modules that take them and installs the pinned dependencies. It does not pull models | |
| `fab deploy` | Runs `deploy.sh`, which runs `model.sh publish`, the same idempotent publish, for a rollback after a revert or for drift. It is run in the module, since from the repository root fab selects only modules with uncommitted changes | `certificates.sh push`; `mutate.sh` run by hand |
| `model.sh status` | Verifies and never writes: compares `metadata.json`, the tags, the aliases, the index and every consumer's embedded project | `verify.sh` |

- **Report.** The release MUST report in the shape of a Go test, as the notebook run does. It prints a `--- SKIP:` line for each workspace it skips, with the reason `fixture`, `unpackaged` or `local`. For every other workspace it prints a `=== RUN   release <name>` block with a stage each for the version (released now or kept), the target and the model. A served target adds stages for the registry model and version, the tags, the alias, the wait for `mlserver` and the retirement. While it waits for `mlserver` it MUST print a `poll [n/N] seconds` note every 5 seconds with the state and label the index shows, so a model coming up is visible. A line MUST stay short enough for a terminal, and the release ends with the version and the number of workspaces released.
- **Staleness.** Before it stamps or publishes anything, the release MUST check every packaged workspace that is not a fixture or `local`, and fail with the stage `Release` and the gate `stale`, naming each, when its inputs hash no longer matches `metadata.json` or its metadata lint finds anything. A release that skipped the tests with `FAB_SKIP_TESTS` therefore still cannot ship a project older than its notebook. The check reads no service and replaces neither the unit nor the system test.
- **Publish.** For each released workspace with a `served` target it MUST find the registry version by content hash, registering it with its tags if absent, set the tags, then move `release`, remove any `preview`, and wait for the expected label to be `READY` in the production index within 90 seconds. It MUST be idempotent, and a crash after `release` has moved MUST converge when it is run again. If production `mlserver` is unreachable, publish MUST warn and continue, since the registry is the source and the loop will converge. If it is reachable and the label does not appear, publish MUST fail and, where the index shows no sync loop, MUST say that `mlserver` is to be released first. A failed publish MUST stop the release before the tag.
- The release version that stamps `metadata.json` MUST be read without changing the repository version.
- `status` MUST warn when a model's served label differs from its `release` label, which means an older release is serving because the newest failed, and when a `preview` alias remains.
- **Signature check.** The compatibility check against `baseline` runs once, when a project is packaged, and `fab release` does not repeat it, so a breaking change at the same signature version fails before a release is attempted.
- **Retirement.** Once a published served name is `READY`, the release function MUST rank the registered models of the workspace, `<stem>_<digits>`, that hold a `release` alias, keep the two newest and the one just published, and remove `release` from the others. It MUST skip, with a warning, a version that a repository source still pins as `/v2/models/<served name>/`, and MUST do nothing when `mlserver` is unreachable. A registry version is never deleted. `status` MUST also warn when more than two versions of a model are live, when the registry holds a version newer than git, when a pin is not live, and when a pin is the older of the two live versions.

### 10.7 Embedded consumers and clients

- A consumer's `generate.sh` MUST embed with `python -m mlmodels embed` for a fixed model, or write the loader alone with `python -m mlmodels embed-loader` for a consumer that loads any model at run time (`mlserver`), and MUST NOT edit what they write. Every command MUST do nothing harmful when no model is registered or no project exists yet, and a repeat run that changes nothing MUST write nothing.
- The embed copies `project/` into the consumer's `src/build/resources/model/<notebook>/` and writes everything generated for it into one embed-owned directory, `src/main/<language>/<service>/model/`, taking the model name from the consumer's own `generate.sh`. The owned directory holds the loader, the generated model files, the root file and any vocabulary the consumer needs from `mlmodels` (`mlserver`'s registry aliases, tags and labels), each copied under its own name with no rename, and holds nothing hand-written.
- An embed MUST replace the directory whole, as `replace_path` does for a vendored component: it MUST write every file whose bytes differ from what the released projects would produce, MUST remove every file and empty directory in it that the current release does not produce, so a file renamed, split or dropped between versions leaves nothing behind, MUST refuse an empty or missing source and then leave the directory as it is, and MUST write nothing when nothing differs. Every file in a project slot MUST be compared and any difference repaired, every generated file MUST be formatted by the language's formatter so the build does not rewrite it, and the model files MUST be derived from the slots, so the directory is a function of the slots and the loader alone.
- A change that leaves the content hash alone MUST NOT touch a consumer. Only a released version is embedded, and a model never released leaves the consumer as it is, so a consumer that needs the model cannot build until one is released. `embed` MUST refuse a slot that holds another project under the same notebook name, a reserved or keyword name, and a manifest that lacks or differs from the loader's dependencies and features, and MUST edit no manifest.
- fab's `check-release` MUST fail a consumer release whose project files do not verify against its own `project.json`, or whose `project.json` hash differs from the workspace's `content_sha256`, so a consumer cannot ship a stale or edited model, and MUST be the only model step fab adds for a consumer. A consumer MUST be released by its own `fab release`, when its owner chooses, and `mlmodels` MUST only log which consumers are stale and what they embed. `fab pull` MUST NOT pull models.
- A consumer's loader MUST be the bundled loader (10.9), unedited, and `fab release` MUST fail a stale loader or model file (CP005, CP006). A consumer built against a project whose signature changed additively MUST compile or load unchanged, and one that needs a new output MUST be released after the model that provides it.
- A served client MUST call its served name, which pins the signature version it supports, without a registry version, MUST be released to move to a newer signature version, bound the call by a timeout, and treat an unreachable server or a non-200 answer as no answer. It MUST record the `model_version` label of the answer. An embedded consumer MUST record the hash of its `project.json` with every decision (R9). The release version of a hash is resolved from `metadata.json` at the consumer's release tag or from the registry's `content_sha256` tag, and `model.sh status` MUST print it for each consumer.
- A release of an embedded consumer and a release of `mlserver` MUST NOT require each other or `mlmodels`: each ships committed or registry state that is already verified.

### 10.8 Reference consumers

- `mlmodels` MUST own one reference consumer and one loader per language under `src/main/python/mlmodels/runtime/`, `src/main/go/mlmodels/runtime/` and `src/main/rust/mlmodels/src/runtime/`. Each is a `main` that loads and verifies a project, replays the golden file and, given a server and a model name, calls a served model instead, over the loader file of its language, `runtime/loader.<ext>`, which `embed` copies and which the reference `main` uses in place.
- The `main` of every language MUST have the same shape. It takes `<project dir> [<server> <name>]`, exits 2 on any other arguments, 1 on a finding or an error and 0 otherwise, prints each finding as `ERROR <rule> [<message>]` and each error as `ERROR [<message>]`, verifies every file against its manifest hash and the acceptance verdict, replays the golden steps reporting `RP001`, `RP002`, `RP003` and `RP005`, and applies the golden tolerance.
- Each loader MUST be one file holding the common code (manifest, hashes, signature check, `Model`, `ModelError`, replay) and then one entry point per flavour, `load_<flavour>` (`load<Flavour>` in Go: `loadStatic`, `loadWasm`, `loadOnnx`), taking the source and the signature as text and returning a predict function: the constants as JSON for `static`, the model file path for `wasm`, `onnx` and `pyfunc`. Python carries `static`, `wasm`, `onnx` and `pyfunc`, and Rust and Go `static`, `wasm` and `onnx`. A flavour entry point keeps its constants, types and helpers local, so an unused one costs nothing where the language lets it (10.9). The `served` entry point is reference-only and MUST NOT be part of the loader. A predict function takes the named input values, returns the named output values and fails with an error rather than returning a partial answer.
- A reference consumer is a small repeatable codebase that shows what a consuming module implements. It is copied into a consumer and MUST NOT be depended on, MUST depend only on its runtime and the standard library, MUST NOT import `asystem` and MUST be short enough to read in one sitting.
- The library MUST check a target against this matrix:

| Language | `static` | `wasm` | `onnx` | `pyfunc` | `served` |
|---|---|---|---|---|---|
| Python | Yes | `wasmtime` | `onnxruntime` | `mlflow.pyfunc` | HTTP client |
| Go | Yes | `wazero` | `onnxruntime_go` | Never | Yes |
| Rust | Yes | `wasmi` | `ort` | Never | Yes |

- The module MUST have one `Dockerfile` that builds every reference consumer into one image on the local architecture: the Python reference consumer installed with the pinned runtime packages, and the Go and Rust reference consumers compiled under `/asystem/bin/<language>`, with the pinned ONNX Runtime shared library for the Go and Rust `onnx` files at `ONNXRUNTIME_LIB`. `fab` MUST build it with the shared packaging step and the `PINS` build argument before `systest` runs, and the system test MUST only check that the image exists and run each embedded target in a container of it with the project mounted read-only. `PINS` is the consumer base packages plus every Python package a workspace declares in its `runtime`, each at its project-wide pin, and a declared package with no pin MUST fail the build. The `Dockerfile` is a test environment and MUST NOT be released to a host. `mlserver` MUST get its Python loader from `embed-loader` when it is generated and never hold its own.

### 10.9 The loader contract

One interface in every language, with the same verbs in each language's idiom: `load(dir)`, `info()`, `signature()`, `predict(Tensors) -> Tensors` and `verify()`, where `load` is `build(dir, read_project(dir))`, so a reference consumer can report hash verification and driver construction as separate stages. `Tensors` is the wire form that `golden.json` uses, a name to values map of `f64`. There is no second API and no generics.

1. `load(dir)` MUST check every manifest hash, that the flavour is supported by the bundle and, for a flavour other than `static`, an `evaluation.json` that passed, and MUST build the flavour driver, so a bad `wasm` or `onnx` file fails at load. A flavour compiled out of the build (the Rust features `model-wasm` and `model-onnx`) or missing its library MUST be a `Load` error naming it. It MUST fail with a typed error and never panic.
2. `info` MUST give the name, flavour and `content_sha256`, the SHA-256 of `project.json`. A project carries no version.
3. `predict` MUST be pure: the state is the caller's, passed as `model_state_in` and returned as `model_state_out`. It MUST be safe to call concurrently.
4. `verify()` MUST replay `golden.json` through the loaded model. The consumer decides when to call it, normally in its own unit test.
5. Tensors are `f64`. An `INT64` output with a NaN, a fractional value or a magnitude above 2^53 MUST be an error and never a cast, and a state input whose length differs from the signature's slots MUST be a `Signature` error.
6. Errors MUST be one type, `ModelError`, with `kind`, `gate` and `cause`, the kinds being `Load`, `Signature`, `Runtime` and `Verify`, and the text `<kind> <gate> [<cause>]`, every value bracketed.
7. Policy MUST never enter the loader: thresholds and decisions stay in the consumer.

A consumer of a fixed model also gets a generated `<notebook>` file holding the name constants, `Request` and `Response` with their conversions to and from `Tensors`, and a `load` that fails when `signature.json` differs from those constants in either direction. It is a helper beside the loader and never part of it.

Dependencies follow each language's own mechanism and the loader adds none. Python's flavours import their library inside their entry point, and `mlserver` carries the host libraries. For Rust the consumer's `Cargo.toml` MUST declare `serde` with `derive`, `serde_json` with `float_roundtrip`, `sha2`, the optional `wasmi` and `ort`, and the features `model-wasm` and `model-onnx`, at the versions of the `mlmodels` reference crate. For Go the consumer's `go.mod` MUST require the reference versions of `wazero` and `onnxruntime_go`, and since a single Go file cannot make cgo optional, every Go consumer MUST build with cgo and carry the pinned ONNX Runtime library. `embed` MUST compare the manifest against the reference, fail naming each package or feature that is missing or differs, and MUST NOT edit it.

#### 10.9.1 Consistency

The loaders and their reference consumers MUST be one design in three languages (R19), and the flavours of one language MUST be one design too.

- **Common denominator first.** A new behaviour, name, error, stage, file or helper MUST be added to every language and flavour that can carry it, with the same meaning, order of work and text, and MUST NOT be added to one alone. A change to one loader MUST be made to the others in the same change, or recorded here as a deviation with its reason.
- **Same concept, same name.** A concept has one name in every language, spelled in each language's own case (`read_project` in Rust and Python and `ReadProject` in Go), and the verbs, error kinds, rule codes, stage names and the text of every error and report line are identical. The flavour entry points, `load_<flavour>(source, signature_json)`, have the same shape for every flavour in a language.
- **Same behaviour.** What a loader accepts, refuses, converts and reports MUST NOT depend on the language or the flavour: the hash and acceptance checks, the `f64` tensors, the integer rule, the state length check, the golden tolerance and the three reported stages of a reference `main`.
- **A difference is a violation unless forced.** It is accepted only where the language or flavour makes the common design impossible or unreasonable, and then it MUST be the smallest that works, be local to the code that needs it and be listed below with its reason. Convenience, taste and habit are not reasons. A deviation that is not listed MUST be fixed or added to this list before a release.
- **Accepted differences:**
  - Failure style: Rust returns `Result`, Go returns `(value, error)` and Python raises, with the same error type and text.
  - Case: Go exports with a capital, and Rust and Python use snake case.
  - Layout: Go's reference `main.go` sits at the module root because a directory cannot hold `package main` and `package runtime`, Rust's reference crate has a `lib.rs` so the loader's public items are not dead code in a binary, and Python's `main` is the package's `__main__.py`.
  - Optional flavours: Rust gates `wasm` and `onnx` behind the cargo features `model-wasm` and `model-onnx`, Python imports a flavour's library inside its entry point, and Go requires ONNX because one file cannot make cgo optional.
  - Content edit on copy: Go's loader is copied with its one `package runtime` line rewritten to `package model`, since a Go file's package is its directory's, and no file is renamed.
  - Package per model: Go holds a package per generated model file, because one Go package cannot declare two models, while Rust and Python modules keep their names apart.
  - Root file: Rust and Python need a generated `mod.rs` or `__init__.py`, and Go has none.
  - Flavour set: `pyfunc` runs only in Python, since it needs the Python stack.
  - Optional fields: `Option` in Rust, a pointer in Go and `None` in Python.
