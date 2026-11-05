# rackmains / ups / battery

The plan for the rackmains UPS battery model. It follows `model.md`, the specification for MLflow model projects, and holds only what
is specific to this model: its design, signature, data, fit, thresholds, trials and tests.

| Term | In This Plan |
|---|---|
| **Module** | `rackmains` |
| **Model** | `ups` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/rackmains/ups/battery/notebook.ipynb` |
| **Registered Model** | `rackmains_ups_battery` (`model.md` 6.1) |
| **Project Flavours** | `static` for the default model of day one, `wasm` for the fitted model (`model.md` 3.2) |
| **Consumer** | The rackmains guard, a Rust service on `max` (`src/max/rackmains`) |
| **Service Plan** | `src/max/rackmains/src/build/resources/plans/rackmains.md`, which holds the unit, the metric names, the outage CSV and the guard |
| **Worked Example** | The stateful model flow (`plans/mlmodels.md` 4) |

**Status, 2026-10-31.** Nothing here is built except the default model of day one, which is built as a `static` project and written into the
rackmains consumer (see "What is implemented"). The rackmains service plan is deleted once the
publisher and guard are released, and this plan outlives it; see "Deleting this plan" in the service plan for what then moves here.

---

## Context

- **rackmains** is a Rust service in a container on the host `max` (`src/max/rackmains`). It reads the rack's UPS through the NUT
  driver socket, publishes every metric on MQTT for Home Assistant, writes a CSV during a battery drain, and runs the **guard**, a
  thread that shuts the servers down early in a power cut (the rackmains service plan).
- **The unit** is a PowerShield Defender RackMount 800 on one 12 V 9 Ah battery ("The unit" in the rackmains service plan). It reports no current
  or power, only load as a whole percent of its rating.
- **The model** owns every parameter the guard acts on and estimates how much usable battery is left. rackmains sends it raw data and
  acts on what comes back, and holds no threshold of its own. Until a fitted model exists rackmains ships a static response, so the
  guard works without it. The seam in rackmains is "The model seam, in rackmains" in the rackmains service plan.
- **Hosts.** The followers are `mad`, `may` and `meg`; `meg` hosts the broker and Home Assistant, and `may` hosts InfluxDB, MLflow and
  mlserver. MLflow (`MLFLOW_TRACKING_URI`) is where fits run and models are registered, and mlserver can serve them (`model.md` 9).
- **Metric names** follow the module and dimension style of `model.md` 6.1, `rackmains_<group>_<metric>`; "Metrics, MQTT and the outage CSV" in
  the rackmains service plan is the master list, and the signature below lists every name the model uses.
- **Trials and by-hand cuts.** The rack's mains is cut by hand at a Tasmota plug upstream of the UPS; rackmains records the cut like a
  real outage. There is no tool for it.

## Design

**Tenets, 2026-10-31.** Each follows from a requirement of `model.md` section 2.
1. **Recorded once, at source** (R3, R9). Data is recorded in Rust where it is produced, and the same numbers appear in MQTT, the CSV and the
   log, so the lineage of every decision can be followed.
2. **Feature engineering ships with the model** (R3). It is part of the project, a WebAssembly module, and nothing the model needs is computed by
   code outside it.
3. **One artifact, built, tested and run** (R4). The model is fitted, evaluated and run through the same shipped module, `model.wasm`,
   embedded in the guard or served by MLServer.
4. **Non-numerics** (R3). A non-numeric value is converted to a number at source, in Rust, if the model needs it. Otherwise it sits beside
   the numbers, recorded but never sent to the model.
5. **Generic.** The model follows the specification like every other; whether a consumer embeds or serves it is decided per consumer.

**The design: a `wasm` step function.** The model is a pure function, `(row, state in) -> (outputs, state out)`, written as a WebAssembly module
(`model.md` 4). The row is numbers the service already records. The state is a small vector the model returns and the caller carries to
the next call, persisting it across restarts. Every feature (a running integral, a decay, a smoothing, a flag, the rounding) is computed
inside the graph. MLServer therefore stays stateless, a request is about a kilobyte and not a window of rows, and there are no windows
to size or empty windows to guard.

**How it meets the tenets**
- **1.** The service records what it sent (the numbers of each call, and the state at the start of an outage) and what came back (the
  outputs of every call, and the state at the end), so **a recorded outage is a complete fold, and replaying it through the model
  reproduces every output, checked row by row, and the final state exactly.**
- **2 and 3.** The graph is the only place the features exist. The notebook, the embedded runtime and the served runtime all run that one
  graph through `model.wasm`, with the parity gate (`model.md` 1.1) between hosts.
- **4.** The status text becomes the `rackmains_ups_on_battery` and `rackmains_battery_replace` flags and the timestamp becomes
  `rackmains_clock_epoch_seconds`, all at source. The status text, the status flags and the ISO timestamp stay beside them.

**State recording, decided 2026-10-31.** The model's outputs are recorded on every call, including the named metrics
`rackmains_model_energy_used_wh` and `rackmains_model_history_known`. The **state** is recorded as one JSON text column,
`rackmains_model_state`, only on the `start` and `end` rows and on any restart, reset or project change, and is not published on MQTT. The
state is a deterministic fold of the calls from the `start` row, so a replay regenerates it and is checked against the outputs row by
row. The guard's state file is written atomically on every call and is how state survives a crash. A debug switch records every state
when a divergence is being investigated.

## First pass: a default model, on day one

**Decided 2026-10-30.** The first release of rackmains ships with a **default model**, delivered through the same project path every later model
will use. rackmains therefore has a model, and a model version in every outage record, **from day one**, and the delivery path (the
spec, the signature, the validator, the golden cases, the embedded evaluator, the provenance) is exercised before any fitting exists. The
default model is conservative and **not fitted**: it supplies the guard's thresholds and nothing else.

**What it is.** A project of `flavour` `static`: a `project.json` manifest holding the rollout A constants, the `signature.json` and a
`golden.json`; no graph and no model file. For every valid request it returns the constants. The manifest, as in `model.md` 3.1:

```json
{
  "spec_version": 1,
  "name": "rackmains_ups_battery",
  "model_version": "static-1",
  "signature_version": 1,
  "flavour": "static",
  "provenance": { "source": "manual", "trained_on": "none, the rollout A starting values", "inputs": [], "notes": "a conservative default, not fitted" },
  "files": {
    "signature": { "path": "signature.json", "sha256": "..." },
    "golden": { "path": "golden.json", "sha256": "..." }
  },
  "constants": {
    "rackmains_guard_shed_max_seconds": 120,
    "rackmains_guard_halt_max_seconds": 450,
    "rackmains_guard_mains_stable_seconds": 300,
    "rackmains_guard_halt_delay_seconds": 120
  }
}
```

**What it does and does not do**
- **It validates.** A request that does not satisfy the signature is an error from day one, in every mode, so a malformed request is caught
  before a real model exists.
- **It answers with constants.** The thresholds above for every valid request, whatever the row contains.
- **It estimates nothing.** `rackmains_battery_remaining_pct` and `rackmains_battery_remaining_seconds` are absent, and so are the `lead`
  thresholds, so the guard acts on the time thresholds and the low-battery flag only, which is the rollout A behaviour.
- **It does not raise `rackmains_model_recalibrate`.** Nothing was fitted, so nothing is stale; that the model is a default is stated in its
  provenance and recorded in the CSV `start` row.

**The options for the default model**

| Option | What it is | Verdict |
|---|---|---|
| **D0, constants only** | the rollout A thresholds and nothing else | **Chosen.** Everything it returns is proven or deliberately conservative |
| D1, constants plus conservative estimates from the nameplate | adds remaining seconds and percent from the unit's rating | Rejected. The nameplate understates the draw (the plug reads about 81 to 100 W at 11 to 12 % utilisation, where 11 % of 480 W is about 53 W), so the estimate would overstate what is left, and unvalidated numbers in Home Assistant could mislead. The guard acts on estimates only through a lead threshold, which the default does not set, so it would add risk and no behaviour |
| D2, constants plus `rackmains_model_recalibrate` always 1 until fitted | flags the default as stale | Rejected. A permanent problem sensor from day one is noise; the provenance already says it |

**How it is produced: by hand, with `write_project` (`model.md` 3.3).** No fit and no MLflow are needed:
1. Write `signature.json` from the signature in this plan, and the manifest above.
2. Write the golden cases: a first call with no state, a row mid-drain, a row with the replace flag raised, and a request with a required
   input missing, which must give a signature error and not a response.
3. `write_project` computes the SHA-256 of each file into the manifest and `verify_project` checks the project; the Rust loader makes the same checks.
4. Copy it into `src/max/rackmains/src/build/resources/model/`, from where the build puts it in the image.

**Registered in MLflow as well (optional).** Register the same project directory with `register_project` under the registered name
`rackmains_ups_battery` with the alias `preview`, with `provenance.source` of `manual`, and `mlmodels` sets `release` at release. That
proves the registry path from the laptop through the tracking URI, gives `generate.sh` with the pull flag something to pull, and lets the
served path be tested with the same project later. The experiment MUST be created after the proxy is enabled (`model.md` 8).

**What ships in the first release**
- The project in the image under `/asystem/etc/model/default/`, loaded by `StaticModel` at start with a validation and a hash check.
- The model version and project hash in every outage CSV's `start` row and in each `decision` row.
- The default project **stays in the image as the last-resort floor even after a fitted project ships**: a later fitted project is added as
  `model/release/`, and the fallback order is the served answer, then the last valid answer, then the shipped release project, then the
  default project. A fitted project that fails validation at start therefore falls back to the default, never to nothing.

**Served on day one?** No: second pass. The serving runtime in `mlserver` is not built (`plans/mlmodels.md` 3), so the first release is embedded
only. The same default project is what MLServer will first serve, which lets the parity gate run on it before any fitted model.

**Acceptance for the first pass** (done, or not yet)
- Done: the default project is built, written to the consumer, and passes every project check of `model.md` section 10, with a golden
  case for each of a first call with no state, a row mid-drain, a row with the replace flag raised, and a missing required input.
- Not yet: rackmains starts with the default project, validates it and checks its hashes, and the Rust test reproduces every golden case
  exactly, including the signature error.
- Not yet: the guard refuses live mode if the project fails validation, and stays in dry-run saying so.
- Not yet: the CSV records the model version and project hash.
- Not yet: replacing the files with a different valid `static` project changes the thresholds with no code change.
- Not yet: the project is released. `fab release` in `mlmodels` moves `release`.

**What is implemented (2026-10-31).**
- The notebook `ups_battery` builds the default project in its Setup, Capture Data, Package and Register sections. The constants are the four
  thresholds above. The signature is built with `build_signature` from the five inputs, twelve outputs and six state slots of this plan.
  The golden samples are written once as the `golden` dataset `ups_battery_golden`, and the golden steps are built from it.
- The project is written to `src/max/rackmains/src/build/resources/model/default/` and verified by `write_project`, which applies PJ001 to
  PJ012 of `model.md` section 10. `generate.sh` verifies it again on every generate.
- The Register section registers it as `rackmains_ups_battery` with the alias `preview`. It has not been run against the server.
- **Not built:** the Rust loader and validator in rackmains, the image copy, and the guard's use of the project.

**Relationship to later stages.** A fitted `wasm` project replaces the `release` project through the same path, with the signature and rackmains
unchanged, and the default keeps guarding the floor.

## Measured results, 2026-10-28

Both cuts were made through the plug (below) with the recorder logging every 2 s and all four hosts up.

**60 s cut, 16:15:44.** `OB` within about 1 s, `OL` within 2 s of the restore. Battery 13.3 to 12.5 to 11.9 V; NUT's estimate
100 to 58 in a minute; input read 8.4 V when cut; output stayed regulated at 243 to 245 V; voltage rebounded to 12.7 V at once
on mains and 13.0 V a minute later. LCD showed "bat 19" (runtime in minutes).

**145 s cut, 18:13:58, ended by my own abort rule.** The unit's HID flags flipped at +1 s, NUT's `OB` at +5 s. Voltage 13.3 to
12.4 (+5 s) to 12.0 (+11 s), then 11.9 to 12.0 flat to +145 s with load 12 to 15%: **no knee yet**. The unit's capacity gauge
went 90 to 40 with the voltage flat and rebounded to 65 within 20 s of restore; its runtime fell 1195 to 1050 s (1 s/s). LCD
photos matched the recorder (1166 s shown as 19, 1134 s as 18). Over the next hour the runtime stopped falling near 870 s,
rose, and settled at 1010 to 1040 s at 90 to 91% and 10 to 11% load. No flag ever raised. The abort rule was the mistake: the
capacity gauge falls to the low 40s within minutes at this load, so it is not an abort signal.

**What is proven and what is not.** Proven: `OB` is a reliable trigger, and 145 s at service load costs nothing visible. Not
proven: the real runtime (the nameplate says 108 Wh, perhaps 65 to 75 usable, against about 81 to 100 W at the plug, so 45 to
60 minutes is an upper expectation, not a measurement), the knee, whether `LB` ever raises, whether the plug's own restore
timer works (every restore so far was explicit), and any restart path.

## Metrics collected, and what the model needs

| Name | Source | Where it lands | Use for the model |
|---|---|---|---|
| `rackmains_battery_volts` | NUT `battery.voltage`, 4 s refresh | MQTT and Home Assistant, and every 5 s on battery in the outage CSV | the knee, the plateau, the sag at transfer |
| `rackmains_output_utilisation_pct` | NUT `ups.load`, whole percent | the same | the live load input; the load axis of `watts_by_load` |
| `rackmains_ups_status` and the derived bools | NUT `ups.status` flags (`OB`, `OL`, `LB`) | the same, and MQTT at once on change | the trigger and the time on battery; whether `LB` raises |
| `rackmains_mains_input_volts`, `rackmains_mains_input_fault_volts`, `rackmains_output_volts`, `rackmains_output_hertz` | NUT | the same | none; input reads 8.4 V when cut |
| `rackmains_battery_charge_pct` | NUT's voltage-based estimate | the same | none; it is a voltage lookup |
| `rackmains_guard_*` | the guard | the same | the guard's own clocks; `mains_seconds` also supports the settled rule for trials |
| Plug watts and current | Tasmota `Status 8` on `rack_outlet_plug` | watts continuously in Home Assistant's history as `rack_outlet_plug_energy_power`; current read by hand around a cut (0 W while its relay is open) | `watts_by_load` and so `usable_wh` |
| Events: transfer, `LB`, shed and halt, restore | rackmains | the `event` rows of the outage CSV on `max`, backed up | the knee time, the failure record, the fit input |
| Follower shed times and `max`'s halt time | test 4 | this plan | `rackmains_guard_<step>_lead_seconds` |
| Recovery after a trial | voltage and `ups.load` on mains | Home Assistant's history | none; kept as evidence only, since nothing on mains shows the state of charge |

**Needed for the model and not collected yet**

| Need | Why | How it is got |
|---|---|---|
| `usable_wh` | the model's energy budget, from full to the knee | trial 5: watts (through `watts_by_load`) integrated over the discharge, at two loads (all servers up, then `max` alone) |
| `watts_by_load` | the unit reports no current or power | plug readings on mains before and after each trial, paired with `ups.load` |
| `rackmains_guard_<step>_lead_seconds` | when to shed and halt so the shutdown finishes before the knee | test 4, several runs per host |
| Starting state | the model assumes a full battery at the first `OB` | float voltage and `rackmains_guard_mains_seconds` before the cut |
| Whether `LB` raises at failure | decides if it is a usable backstop | trial 5 |

## The data the model is trained on

**The outage CSV, as the model sees it.** rackmains writes one file per outage, only while the UPS is on battery, so the files hold
drains and nothing else. Under the step-function design **each row on battery with no event, or a `start` or `status` event, is one model call**: the row's own
numbers are the model's input and the outputs are in the row. The state is recorded as `rackmains_model_state` only on the `start` row
(the state in), the `end` row (the state out) and on any restart, reset or project change; the model regenerates every state between
them, because it is a deterministic fold of the calls. The `decision`, `command`, `note` and `end` rows repeat the last values and a
replay skips them. A file is a complete, replayable record of what the model was asked and what it said.
- **Where, name, columns, rows and safe writes** are as in "Metrics, MQTT and the outage CSV" in the rackmains service plan. The text columns (`timestamp`, `rackmains_ups_status`, `rackmains_guard_state` and `rackmains_model_state`) sit beside the numbers and are never sent to the model. `rackmains_clock_epoch_seconds` is the numeric form of `timestamp` that the model does use. The model's inputs are `rackmains_clock_epoch_seconds`, `rackmains_output_utilisation_pct`, `rackmains_ups_on_battery` and `rackmains_battery_replace`, plus the state carried from the previous call. The `rackmains_model_state` column is blank except on the `start` and `end` rows and on a restart, reset or project change. The newest 100 files are kept on `max`; older ones survive only in the backups.

**Home Assistant's InfluxDB history** is described under "Same values as Home Assistant writes to InfluxDB" in the same section: a change-only subset of the CSV that covers the long periods on mains no CSV does, and has nothing while the broker is down, so it is forward-filled before it is compared or used.

**What the model is trained on.** It is fitted offline, by the `rackmains/ups/battery` notebook in the `mlflow` module, from:
- **The outage CSV files** (backed up under supervisor's policy), each outage a complete, replayable fold. They hold every metric at 1 s to 5 s through each drain, the model's outputs and its state at the start and end, the guard's decisions and the command timings, and are the only complete record when the broker and database were shed. Training **replays** them: the pipeline feeds the recorded rows through the Python reference step in order, from the `start` row's state, which regenerates the state the service saw, so no feature is ever recomputed by different code.
- **Home Assistant's InfluxDB history** of the rackmains entities, written from MQTT: measurement `<domain>__<device_class>`, tag
  `entity_id` equal to the canonical name, float `value` (a bool as `1.0` or `0.0`) and text in `state`. It covers the long periods on
  mains that no CSV does, such as the float voltage and the load distribution, but it is a change-only subset of the CSV and has no
  rows while the broker is down, so it is forward-filled before use.
- **The upstream plug, `rack_outlet_plug`.** A Tasmota 13 smart plug (WiFi, friendly name "Server Rack") that the UPS is plugged into,
  so it sits upstream of everything rackmains measures. It reports watts at 1 W resolution, and its reading includes the UPS's own
  losses and float charge as well as the rack's load (about 81 to 100 W at 11 to 12 % utilisation), so it overstates what the battery
  supplies. Home Assistant records it as `rack_outlet_plug_energy_power` (W, in the `sensor__power` measurement) and
  `rack_outlet_plug_energy_total` (kWh, in `sensor__energy`), and records the relay as the `rack_outlet_plug` switch; no current or
  voltage sensor for it is recorded, though Tasmota's `Status 8` returns current when read by hand. Its limits: while its relay is
  open for a by-hand cut it reads 0 W, so it never gives watts on battery; in a real outage it loses power with the mains and
  contributes nothing; and it is on WiFi. It is used only to build the load-to-watts map, as pairs of
  (`rackmains_output_utilisation_pct`, plug watts) taken on mains before and after each cut and joined by time, and the relay's
  history marks when a by-hand cut began and ended, which is how a trial is told from a real outage in the training data. The live
  request never contains plug data.
- **By-hand measurements** that none of these hold: the plug's current around a cut, and the per-host `asleep` times (test 4) that set
  `rackmains_guard_<step>_lead_seconds` and `rackmains_guard_halt_delay_seconds`.

The project's `provenance.inputs` lists the data files that fed each fit. This section
records what each source is and why it is used, so a later reader can tell whether a collection run was complete.

The targets are constructed, not observed: the knee time and `usable_wh` come from trial 5, and the thresholds follow from them as
"Setting the thresholds" below describes. The fit may write the project itself until the model is served.

## The model signature, inputs, outputs and thresholds

**Decided 2026-10-30, revised 2026-10-31 for the step-function design.** The model owns every parameter. rackmains collects raw numbers,
sends them to the model with the state from the previous call, and acts on what comes back; it holds no threshold of its own. Every
threshold, the shed and halt times, the lead times, the UPS shutdown delay and the durations, is a model **output**, so offline fitting
can change any of them without touching the guard.

**The interface is the MLServer V2 inference protocol** (`POST /v2/models/rackmains_ups_battery/infer`). A request is one row: each input is a named
one-value tensor, plus the state tensor. A response is named tensors, the new state among them. Every name is a metric name, so a
threshold is `rackmains_guard_<field>`, an estimate is `rackmains_battery_remaining_<unit>`, and the model's own outputs are
`rackmains_model_<name>`. Three documents:

| Document | What it is |
|---|---|
| `signature.json` | the model's metadata: every input and output, its type, unit and whether it is required, and the state slots (the shape MLServer serves at `/v2/models/rackmains_ups_battery`) |
| `request.json` | an example request |
| `response.json` | an example response: what the default model returns for every request, and the format of every real response; the model itself ships as a project ("First pass: a default model on day one") |

These JSON blocks explain the signature. It is built in the notebook with `build_signature` and committed as `signature.json` in the
consumer's `default` slot, `src/max/rackmains/src/build/resources/model/default/`, so the notebook is the source and the committed
file is its output. When the two differ, the file is regenerated, never edited.

**`signature.json`** (`required` outputs must always be present; `required` inputs must be present in every request):

```json
{
  "name": "rackmains_ups_battery",
  "platform": "mlserver",
  "versions": ["static-1"],
  "parameters": {
    "signature_version": 1,
    "state": [
      { "slot": 0, "name": "unrecovered_pct_seconds", "unit": "percent seconds", "description": "Utilisation integrated over the time on battery in earlier outages and not yet recovered." },
      { "slot": 1, "name": "outage_pct_seconds", "unit": "percent seconds", "description": "Utilisation integrated over the time on battery in the current outage." },
      { "slot": 2, "name": "mains_seconds", "unit": "seconds", "description": "Seconds on mains since the last outage ended." },
      { "slot": 3, "name": "was_on_battery", "unit": "flag", "description": "1 if the previous call was on battery, 0 otherwise." },
      { "slot": 4, "name": "history_known", "unit": "flag", "description": "1 once the battery is known to have recovered, 0 until then." },
      { "slot": 5, "name": "last_epoch_seconds", "unit": "seconds", "description": "The time of the previous call, 0 before the first." }
    ]
  },
  "inputs": [
    { "name": "rackmains_clock_epoch_seconds", "datatype": "FP64", "shape": [1], "parameters": { "unit": "seconds", "required": true, "description": "Time of the poll as seconds since the Unix epoch. The ISO text timestamp stays beside it in the record and is not sent." } },
    { "name": "rackmains_output_utilisation_pct", "datatype": "INT64", "shape": [1], "parameters": { "unit": "percent", "required": true, "description": "Load on the UPS output as a whole percent of its rated capacity. Not watts: whether the rating is volt-amperes or watts is not known." } },
    { "name": "rackmains_ups_on_battery", "datatype": "INT64", "shape": [1], "parameters": { "unit": "flag", "required": true, "description": "1 while the UPS is running from its battery because the mains has failed, 0 on mains. Held at 0 during a deliberate battery calibration. The status text it is derived from stays beside it and is not sent." } },
    { "name": "rackmains_battery_replace", "datatype": "INT64", "shape": [1], "parameters": { "unit": "flag", "required": true, "description": "1 while the UPS reports the battery needs replacing." } },
    { "name": "rackmains_model_state_in", "datatype": "FP64", "shape": [-1], "parameters": { "unit": "state", "required": false, "description": "The state the model returned on the previous call, carried unchanged by the caller. Absent on the first call, when the model starts from its initial state with the history unknown." } }
  ],
  "outputs": [
    { "name": "rackmains_guard_shed_max_seconds", "datatype": "INT64", "shape": [1], "parameters": { "unit": "seconds", "required": true, "description": "Seconds on battery after which the guard puts the follower servers to sleep, whatever else is estimated." } },
    { "name": "rackmains_guard_halt_max_seconds", "datatype": "INT64", "shape": [1], "parameters": { "unit": "seconds", "required": true, "description": "Seconds on battery after which the guard halts max and has the UPS cut and restore its output. Later than the shed time." } },
    { "name": "rackmains_guard_mains_stable_seconds", "datatype": "INT64", "shape": [1], "parameters": { "unit": "seconds", "required": true, "description": "Seconds of unbroken mains after which the on-battery clock resets and any server put to sleep is woken." } },
    { "name": "rackmains_guard_halt_delay_seconds", "datatype": "INT64", "shape": [1], "parameters": { "unit": "seconds", "required": true, "description": "Seconds the UPS waits before cutting its output after the guard asks it to shut down. Long enough for max to finish going to sleep." } },
    { "name": "rackmains_guard_shed_lead_seconds", "datatype": "INT64", "shape": [1], "parameters": { "unit": "seconds", "required": false, "description": "Optional. Put the follower servers to sleep when the estimated run time left falls to this: the measured time the shed takes plus a margin." } },
    { "name": "rackmains_guard_halt_lead_seconds", "datatype": "INT64", "shape": [1], "parameters": { "unit": "seconds", "required": false, "description": "Optional. Halt max when the estimated run time left falls to this: the measured time the halt takes plus a margin." } },
    { "name": "rackmains_battery_remaining_pct", "datatype": "INT64", "shape": [1], "parameters": { "unit": "percent", "required": false, "description": "Optional. Estimated usable battery left as a whole percent, 100 when full, rounded down. Informational: the guard does not act on it." } },
    { "name": "rackmains_battery_remaining_seconds", "datatype": "INT64", "shape": [1], "parameters": { "unit": "seconds", "required": false, "description": "Optional. Estimated run time left at the current load, rounded down, so it never overstates." } },
    { "name": "rackmains_model_energy_used_wh", "datatype": "FP64", "shape": [1], "parameters": { "unit": "watt hours", "required": false, "description": "Optional. Energy the model counts as used since the battery was last full, in the current outage and the unrecovered part of earlier ones." } },
    { "name": "rackmains_model_history_known", "datatype": "INT64", "shape": [1], "parameters": { "unit": "flag", "required": false, "description": "Optional. 1 once the model knows the battery had recovered before this outage, 0 while it is assuming a partly drained battery." } },
    { "name": "rackmains_model_recalibrate", "datatype": "INT64", "shape": [1], "parameters": { "unit": "flag", "required": false, "description": "Optional. 1 when the fit should be redone because it is old, the battery has been replaced or observed drains no longer match its predictions. The reason is in the response parameters." } },
    { "name": "rackmains_model_state_out", "datatype": "FP64", "shape": [-1], "parameters": { "unit": "state", "required": false, "description": "Optional. The state to carry to the next call, in the order the signature lists. Absent for a model with no state." } }
  ]
}
```

**`request.json`**, one row and the state, here 96 seconds into an outage at 13 percent utilisation:

```json
{
  "id": "2026-10-30T18:15:30+08:00",
  "inputs": [
    { "name": "rackmains_clock_epoch_seconds", "datatype": "FP64", "shape": [1], "data": [1793355330.0] },
    { "name": "rackmains_output_utilisation_pct", "datatype": "INT64", "shape": [1], "data": [13] },
    { "name": "rackmains_ups_on_battery", "datatype": "INT64", "shape": [1], "data": [1] },
    { "name": "rackmains_battery_replace", "datatype": "INT64", "shape": [1], "data": [0] },
    { "name": "rackmains_model_state_in", "datatype": "FP64", "shape": [6], "data": [0.0, 1235.0, 0.0, 1.0, 1.0, 1793355329.0] }
  ]
}
```

**The default model's response, the static stand-in.** Only the required outputs, with the rollout A starting values (the 120 s halt
delay is a placeholder until test 4 measures `max`'s `asleep --deep`). It has no state, so there is no state tensor. An optional output
that is absent is not applied, so the guard has no branch that waits for the model:

```json
{
  "model_name": "rackmains_ups_battery",
  "model_version": "static-1",
  "id": "static",
  "parameters": { "source": "static", "fitted_at": "2026-10-30", "trained_on": "none, the rollout A starting values" },
  "outputs": [
    { "name": "rackmains_guard_shed_max_seconds", "datatype": "INT64", "shape": [1], "data": [120] },
    { "name": "rackmains_guard_halt_max_seconds", "datatype": "INT64", "shape": [1], "data": [450] },
    { "name": "rackmains_guard_mains_stable_seconds", "datatype": "INT64", "shape": [1], "data": [300] },
    { "name": "rackmains_guard_halt_delay_seconds", "datatype": "INT64", "shape": [1], "data": [120] }
  ]
}
```

**A response from a fitted model, later** (illustrative values). Every output present, the new state included; the guard reads only
what is there:

```json
{
  "model_name": "rackmains_ups_battery",
  "model_version": "1",
  "id": "2026-10-30T18:15:30+08:00",
  "parameters": { "source": "mlflow", "fitted_at": "2026-12-01", "trained_on": "outage CSV files and InfluxDB history, illustrative", "recalibrate_reason": "" },
  "outputs": [
    { "name": "rackmains_guard_shed_max_seconds", "datatype": "INT64", "shape": [1], "data": [120] },
    { "name": "rackmains_guard_halt_max_seconds", "datatype": "INT64", "shape": [1], "data": [450] },
    { "name": "rackmains_guard_mains_stable_seconds", "datatype": "INT64", "shape": [1], "data": [300] },
    { "name": "rackmains_guard_halt_delay_seconds", "datatype": "INT64", "shape": [1], "data": [120] },
    { "name": "rackmains_guard_shed_lead_seconds", "datatype": "INT64", "shape": [1], "data": [300] },
    { "name": "rackmains_guard_halt_lead_seconds", "datatype": "INT64", "shape": [1], "data": [240] },
    { "name": "rackmains_battery_remaining_pct", "datatype": "INT64", "shape": [1], "data": [93] },
    { "name": "rackmains_battery_remaining_seconds", "datatype": "INT64", "shape": [1], "data": [1346] },
    { "name": "rackmains_model_energy_used_wh", "datatype": "FP64", "shape": [1], "data": [1.664] },
    { "name": "rackmains_model_history_known", "datatype": "INT64", "shape": [1], "data": [1] },
    { "name": "rackmains_model_recalibrate", "datatype": "INT64", "shape": [1], "data": [0] },
    { "name": "rackmains_model_state_out", "datatype": "FP64", "shape": [6], "data": [0.0, 1248.0, 0.0, 1.0, 1.0, 1793355330.0] }
  ]
}
```

**What a request contains.** Four numbers and the state, and nothing else: the poll time as seconds since the epoch, the utilisation, the
on-battery flag and the replace flag. No text, no ISO timestamp, no history and no window; the status text and the timestamp stay beside
these numbers in the record. Every number sent is recorded in the same row as the call, and the state at the start of an outage on its `start` row, so the request can
be rebuilt from the recording. The state is absent on the first call and after a reset, and the model then starts from its initial state with the history
unknown, which it treats as a partly drained battery. The caller persists the returned state together with the `project_sha256` it came
from, and discards a state that came from a different project.

**What the step does.** From the clock and the state it derives `dt`, the time since the previous call (0 on the first). The v1
calibration step, an example of what can be inside the graph:
- while on battery it adds `utilisation * dt` to the current outage's integral and holds the mains time at 0;
- when an outage begins it scales the unrecovered integral of earlier outages by the recovery that the mains time since the last outage
  allows (linear over six hours); when it ends it folds the outage's integral into the unrecovered part;
- on mains it adds `dt` to the mains time, and marks the history known once the mains time reaches the recovery period;
- from the integrals it computes the energy used through the fitted load-to-watts map, then the remaining seconds and percent, each
  `floor(x + 1e-6)` so a value that is mathematically an integer rounds to it in every engine;
- it raises the recalibrate flag when the fit is older than its limit, or the replace flag is 1.

**When it is called.** Every 5 s while on battery (the cadence of a CSV row), at each transition between mains and battery, and every 5
minutes on mains. The cadence is the same embedded and served, and `dt` means a missed call only makes the integral coarser. For identical numbers in both
modes the call sequence must be identical, which the parity gate arranges by replaying a recorded sequence.

**How a response is used.** rackmains' guard implements these rules.
- A step fires on whichever comes first: its time (`rackmains_guard_battery_seconds` reaches `rackmains_guard_<step>_max_seconds`), the
  low-battery flag, or the remaining seconds falling to `rackmains_guard_<step>_lead_seconds`, which applies only when the response
  provides it.
- At the halt, `shutdown.return` is sent with `ups.delay.shutdown` set to `rackmains_guard_halt_delay_seconds`.
- `rackmains_guard_mains_stable_seconds` of unbroken mains resets the guard's on-battery clock and wakes what was shed.
- The low-battery flag stays the guard's own override, honoured in dry-run too; it is a safety rail and not model-owned.
- `rackmains_model_recalibrate` of 1 logs a WARN with the reason from the response `parameters` and reaches Home Assistant as a problem
  sensor. It never changes what the guard does.
- **Validation, one function.** Every output named in `signature.json`, every required one present, every set number finite and
  non-negative, `rackmains_model_recalibrate` 0 or 1, the state out the length the signature lists, and
  `rackmains_guard_shed_max_seconds` below `rackmains_guard_halt_max_seconds`. An output the signature does not name is an error, so a
  misspelt name never reads as absent. A response that fails validation is not used, and the guard **refuses live mode** while the
  response it holds fails it.
- **Which response applies.** The latest valid model answer while it is younger than three calls, else the last valid one held for the
  rest of the outage, else the shipped release project, else the shipped default project. The default model is always the floor, so the
  guard always holds a full set of required thresholds, including when mlserver on `may` has been shed first and every call fails.
- **State handling.** The state returned by the answer in use is the state carried to the next call. When the answer in use changes
  project, the state is reset to the new model's initial state.
- The model version and project hash of the answer in use are written to the CSV `start` row and to every `decision` row.

## Delivery

Packaging, testing, registering and running a model, served or embedded, is specified in `model.md`. This section is what is specific to
this model.

**Projects**

| Project | Flavour | Registered Name and Version | Where It Runs |
|---|---|---|---|
| The default model of day one | `static` | `rackmains_ups_battery`, `static-1` | Embedded in the guard, always present as the floor |
| The fitted model | `wasm` | `rackmains_ups_battery`, the fitted `model_version` | Embedded in the guard through `wasmi`; served in `mlserver` as an option |

The fitted model MUST be a `wasm` project. The interim `parameters` flavour MUST NOT be used, because the guard cannot depend on a
hand-written evaluator per language (`model.md` 3.3).

**Data splits** (`model.md` 6.3)

| Split | Content |
|---|---|
| `training` | Trial 5 and any other discharge to the floor, as outage CSV files |
| `validation` | A repeat discharge at a different load |
| `backtest` | The outage CSV files from `max`, replayed row by row, and the by-hand trial cuts |
| `golden` | Sequences generated from the shipped runtime, which become the project's `golden.json` and the Rust loader's tests |

The notebook is `src/rue/mlmodels/src/main/notebook/rackmains/ups/battery/notebook.ipynb` with its data beside it under
`src/rue/mlmodels/src/main/notebook/rackmains/ups/battery/data`.

**Hooks in this module's fab lifecycle** (`model.md` 7.2)
- `src/max/rackmains/generate.sh` follows the consumer `generate.sh` in `model.md` 8.1: with the pull flag (only `fab pull`) it pulls the
  `rackmains_ups_battery` `release` project into `src/build/resources/model/` and checks its signature against the committed one; every build
  only verifies it.
- `fab unittest` runs the loader, the validator, the golden sequences and the replay test, on both architectures; `fab package` puts the
  project in the image at `/asystem/etc/model/`; the guard refuses live mode if the project fails validation.
- A signature change is a new `signature_version` and a release of rackmains.

**To finish for rackmains.** Register the default project as `rackmains_ups_battery`, add the name to `MLSERVER_MODELS` if it is served, run
`fab generate` in `rackmains`, and build the Rust loader around `wasmi` once the `wasm` flavour is implemented (`plans/mlmodels.md` 3), using this
notebook as the stateful worked example (`plans/mlmodels.md` 4).

## Route to the first fitted model

The project is the interface (`model.md` 3), so rackmains does not change as the producer of the project changes.

| Step | Project | What Has to Exist First |
|---|---|---|
| 1 | A hand-written `static` project, the rollout A constants | Nothing: it is the first release |
| 2 | A fitted `wasm` project from the `rackmains/ups/battery` notebook, parameters from trial 5, the plug pairs and the outage CSV files | The `wasm` flavour (`plans/mlmodels.md` 3), a drain to the knee, and the backtest below |
| 3 | The same registered version served by `mlserver` | The serving runtime (`plans/mlmodels.md` 3) |

Until a drain to the knee exists (trial 5), no fitted project ships and the `static` project stays.

**The fit procedure for step 2**, in the notebook (`model.md` 6.6)
1. From trial 5's CSV, find the time to the knee (or to the low-battery flag) and the load through the drain.
2. From the plug pairs build `load_to_watts` ("How the map is built").
3. Integrate watts over the drain through the map: that is `usable_wh` ("How `usable_wh` is fitted"), shaded to the safe side.
4. Set the thresholds from the knee and the measured per-host times ("Setting the thresholds"). Set `unknown_history_charge_fraction`
   conservatively and `recharge_credit_seconds` to the manual's six hours.
5. Build the graph with the project's builder, write the project with `provenance.source` of `mlflow`, list the data files in
   `provenance.inputs`, and raise `model_version`.
6. Write the `golden` rows from at least three sequences worked by hand from the parameters (a first call with no state, a drain at one
   load, a second dip), so the runtime is checked against an independent calculation and not only against itself.
7. Run the backtest and keep its report with the project.

**The backtest, the gate for any project.** Replay every `backtest` outage CSV through the shipped runtime, row by row, and compare
`rackmains_battery_remaining_seconds` with the time that was actually left (to the low-battery flag, or to the end of the file). The
estimate must **never exceed** the real remaining time by more than a stated margin, since the model must not overstate, and its
underestimate must be bounded, so it does not waste battery. The margins are set when the first drain data exists and recorded in
`provenance.notes`.

**What does not change.** rackmains, the signature, the golden test, the loader and the release flow are the same at every step. The only
difference in the project is `provenance.source`, which MUST be `static`, `manual` or `mlflow`, and the `model_version` written into every
outage's CSV says which one acted.

## The model: inputs, outputs and fit

The model owns every parameter the guard acts on, and estimates how much usable battery is left. rackmains collects raw numbers, sends one
row and the carried state to the model at each step, and acts on what comes back; it holds no threshold of its own. The exact JSON is in
"The model signature" above. The model is fitted offline and will be embedded or served; until then a shipped default model stands in,
and nothing downstream can tell the difference.

**Inputs, live, all available during an outage.** One row per step plus the state. Every number is a recorded metric under its canonical
name, and no text is sent. Only what rackmains holds on `max` can be an input, because the plug and anything upstream lose power in a
real outage.

| Input | Source | Reliable? | Notes |
|---|---|---|---|
| `rackmains_output_utilisation_pct` | NUT `ups.load`, 1 s poll on battery, whole percent | **yes as a reading, unproven as a power measure** | 10 to 18% over 4.5 hours on mains (mean 10.9), 12 to 15% on battery; each step is about 4.8 W (30% relative at the rack's load). It moved 10 to 12 to 13% at transfer and 12 to 15% during the 145 s cut, and whether that is the rack's load or a change in how the unit measures on battery is not known. It has not been checked against watts (the paired sampling is paused) and whether it is VA or W is unknown |
| `rackmains_ups_on_battery` | NUT `ups.status`, converted to a flag at source | `OB`/`OL` yes | the model starts and ends an outage from it |
| `rackmains_battery_replace` | NUT `ups.status`, converted to a flag at source | not yet seen | raises the recalibrate flag |
| `rackmains_clock_epoch_seconds` | the poll clock, converted from the timestamp at source | yes | the model derives every duration from it, with the previous call's time in its state |
| `rackmains_model_state_in` | the previous call's state out | yes | carried and persisted by the caller; lost state resets the model to history unknown, which it treats as a partly drained battery |

Not sent to the first fit, by decision or because not usable: `rackmains_battery_volts` (13.3 to 12.0 V in 11 s then flat; context for
the fit and added by a new signature version if trial 5 shows it earns a place), the status text, the ISO timestamp, temperature,
battery age, the unit's own capacity and runtime, `rackmains_battery_charge_pct` (NUT's voltage lookup), the input voltage and every HID
field.

**Outputs, per step.**

| Output | Meaning |
|---|---|
| `rackmains_battery_remaining_seconds` | `(usable_wh - Wh used) / watts at the current load`, rounded down: what a step compares with its `rackmains_guard_<step>_lead_seconds` |
| `rackmains_battery_remaining_pct` | `100 * (1 - Wh used / usable_wh)`, rounded down, informational |
| `rackmains_model_energy_used_wh` | the energy the model counts as used, from the integrals and the fitted load-to-watts map |
| `rackmains_model_history_known` | 1 once the model knows the battery had recovered before this outage |
| `rackmains_model_recalibrate` | 1 when the fit should be redone: it is old, the battery was replaced, or observed drains no longer match what it predicted |
| `rackmains_model_state_out` | the state to carry to the next call |
| `rackmains_guard_shed_max_seconds`, `rackmains_guard_halt_max_seconds`, `rackmains_guard_mains_stable_seconds`, `rackmains_guard_halt_delay_seconds` | the guard's required thresholds, fitted offline and returned with every answer |
| `rackmains_guard_<step>_lead_seconds` | the optional estimate-based threshold: a step fires when the remaining seconds fall to this, which the fit sets to that step's measured time plus a margin |

**Fitted parameters (kept inside the graph).** `usable_wh` and the load-to-watts map. **One assumption, not fitted:** energy used is
credited back linearly over 6 hours of mains (the manual's about 6 hours to 90%), a constant in the graph, so a second dip soon after
the first starts with less than a full battery. It is not an output and not a parameter anyone tunes.

**Can the outputs be modelled and fitted offline with enough data? Mostly as a calibration, not as a statistical fit.**
- **`usable_wh` (the energy to the knee) is one number per battery.** There is no ground-truth percentage anywhere: the percentage
  is defined as the fraction of that energy used, so the split is constructed from the time to the knee in trial 5, not
  observed. Deliberate cuts can be repeated at will, but a deep run costs battery life and about 6 hours of recharge, so the
  knee is likely to come from a handful of deep discharges (two loads, a repeat to see the spread), not hundreds. With that few
  deep points the spread is only roughly known; the figure is a calibration and should be shaded to the safe side.
- **The knee may not be reached.** Trial 5 stops at the voltage floor or `LB`, not at the UPS cutting out, so if the knee lies
  below the floor `usable_wh` is only a lower bound. That errs safe and wastes some battery. Finding the true knee needs the deeper
  run the plan chose not to make.
- **The load-to-watts map rests on an unverified link.** The plug's watts exist only on mains (its relay is open during a cut),
  so the map is built from mains readings and applied to the `ups.load` seen on battery. If the unit reports load differently on
  battery (the 10 to 12 to 13% step at transfer suggests it might), the map mis-scales the energy. The paired sampling of
  `ups.load` against the plug's watts, and a look at the load through a cut, check this before the map is trusted.
- **The recharge credit cannot be fitted, so it is a constant.** On mains the voltage sits at the float level whatever the charge, and the
  unit's capacity gauge is not a measure, so there is no signal for the state of charge between a trial and the next. The figure
  is the manual's about 6 hours to 90%, an assumption, and the safe default if a second outage soon follows is to treat the
  battery as not recovered. The guard's own clock resets after `rackmains_guard_mains_stable_seconds` and so already treats the battery as
  recovered much sooner; the model's slower credit is what covers the second-dip case.
- **What more data buys.** Deliberate cuts made by hand at the plug are repeatable at a chosen load and starting state, so the data is
  limited by battery wear and recharge time, not by how often outages happen. Shallow cuts of a few minutes are cheap and can be
  run many times: they give the plateau at each load, the sag at transfer, the `ups.load` behaviour and the load-to-watts map.
  They do not reach the knee. Second-dip runs (a cut, then another after 10 minutes, an hour and 6 hours) test the recharge
  assumption. Deep runs to the voltage floor are the expensive ones and are made once per battery, with a repeat if the spread
  matters. Real outages add the sag, the plateau at the actual load and a check of the shed and halt timings, but rarely the knee,
  because the guard is built to be finished before it. The percentage stays a refinement of the times, not a replacement for
  them, which is why the time thresholds remain the guard's primary trigger and the targets are optional.
- **Serving is optional.** A calibration this small runs in the guard without any server. Serving it in mlserver is an option that costs
  the runtime dependency the fallback order under "How a response is used" covers.

**Future: fitting the load-to-watts map and `usable_wh` (not built, not run).** Nothing here is done; it describes what the offline
fit will do when the trials have supplied the data.

**Features and outputs of the fit.**

| | Feature or output | Source | Role |
|---|---|---|---|
| Fit input | the recorded rows of each outage, replayed through the reference step | the outage CSV and InfluxDB history | regenerates the state the service saw, from the `start` row's state; the integral of utilisation is converted to watts by the map and to Wh |
| Fit input | plug watts, before and after each cut | `rack_outlet_plug_energy_power` in Home Assistant's history (0 W while the relay is open) | builds the map |
| Fit input | seconds from transfer to the voltage floor or `LB` | the outage CSV | the time to the knee, so the Wh to the knee |
| Fit input | `rackmains_battery_volts` series | the outage CSV and InfluxDB history | locates the knee and the plateau, and the sag at transfer; checks the map; not a live input |
| Fit input | `rackmains_ups_on_battery` and the other flags | the outage CSV and InfluxDB history | marks transfer, `LB` and recovery |
| Fit input | follower shed times and `max`'s halt time | test 4 | sets `rackmains_guard_<step>_lead_seconds` and `rackmains_guard_halt_delay_seconds` |
| Fit output | `usable_wh` | trial 5 | the energy budget, a constant inside the graph |
| Fit output | the load-to-watts map | mains pairs around each trial | converts a live utilisation to watts, a constant inside the graph |
| Fit output | every `rackmains_guard_*` threshold and the recalibrate limit | the fit | returned with each answer |
| Fixed assumption | the 6 hour recharge credit | the manual | not fitted |
| Live input | the row and the carried state | rackmains | the call |
| Live output | the estimates, thresholds, recalibrate flag and new state | the model | a step fires when its time is reached, `LB`, or when the remaining seconds fall to its lead |

Not used, by decision or because unusable: temperature, battery age, the unit's capacity and runtime, NUT's `battery.charge`,
input voltage and every HID field.

- **Why the map exists.** The unit reports no current or power, only `ups.load` as a whole percent of its 480 W rating. Taken as a
  plain percent of watts, 11% would be about 53 W, but the plug reads 81 to 100 W on mains at about 11 to 12%. The gap is the UPS's
  own losses and float charge, plus the open question whether the percent is of VA or of W. The map replaces the nameplate figure
  with a measured one.
- **How the map is built.** Pairs of (`ups.load`, plug watts) taken on mains before and after each trial give a short table, for
  example 10% to 48 W and 15% to 72 W, interpolated between points. The rack's load only moves between about 10% and 15%, so
  spanning a range needs extra load added by hand (a stress test on the hosts). The plug reads 0 W during a cut, so the map is
  never checked on battery, and the link from the wall draw to the battery draw is an assumption. The wall figure includes losses
  the battery does not supply, so the map overstates the battery draw a little, which errs safe.
- **How `usable_wh` is fitted.** In trial 5 record `ups.load` from the transfer until the voltage floor or `LB`, convert each
  reading to watts through the map, and integrate over time. A knee at 1500 s at about 60 W would give 25 Wh (illustrative only;
  the nameplate is 12 V x 9 Ah = 108 Wh, perhaps 65 to 75 Wh usable). It is an effective figure on the wall-watt scale, not the
  battery's own capacity: it folds in inverter losses and where the knee sits, and is tied to the map that produced it. If the
  knee is not reached it is a lower bound.
- **Why a wrong scale mostly cancels.** The fit and the live estimate use the same map, so a map that reads every wattage 20%
  high gives a `usable_wh` that is 20% high too, and the percentage is unchanged. It does not cancel for a map that is wrong in
  shape: `ups.load` meaning something different on battery than on mains, or lead-acid giving less energy at higher power. That
  is why trial 5 runs at two loads and why the percentage is trusted only near the loads the trials used.
- **Checks before the numbers are trusted.** The paired `ups.load` against plug-watts sampling on mains, the behaviour of
  `ups.load` through a short cut, and agreement between the two loads' `usable_wh` once converted.

**Inputs that should be evaluated for collection before the model is built.**
- **`ups.load` against the plug's watts**, on mains and through a short cut, to judge the load as a power measure (the paused
  paired sampling, and the existing recorder history).
- **Transfer behaviour of `ups.load`**: whether the step at transfer is real, by comparing the load a minute before, during and
  after cuts at the same rack load.
- **A finer load.** Nothing finer than whole percent is reported, so the rack's draw is quantised to about 4.8 W; the plug's watts
  taken before the cut and held are the only finer figure, and are lost in a real outage.
- **Voltage under each load at the plateau**, from trial 5 at two loads, to decide whether voltage ever becomes a useful input.

## Thresholds, fitted offline

**No voltage thresholds until modelling is done (decided 2026-10-28).** Voltage was weighed as a trigger and dropped. It is the
only signal that follows the battery's ageing, but it is flat on the plateau for minutes (the 145 s run sat at 11.9 to 12.0 V),
the knee is probably steep because an inverter draws roughly constant power, so the current (inferred, the unit reports none)
rises as the voltage falls and the fall accelerates, and the gap between the plateau and the knee is perhaps 0.4 V, inside the
noise of load steps and the 4 s refresh. A threshold that fires less than `max`'s halt duration plus a margin before the cutoff
is useless, and one on the plateau fires falsely. So the times, set for a worn battery, plus `LB` carry the job, and the voltage
is still published and recorded so the curve accrues. Voltage thresholds, or the sag in the first seconds of an outage (13.3 to
12.4 V, growing as the battery ages), could be added later as new optional outputs, if trial 5 shows the knee leaves at least the
halt duration plus a margin above the cutoff. A by-hand trial has no abort voltage now that the tool that held one is gone: the cut is stopped at the plug by hand, and
each cut is bounded by its own `Delay`.

What the model needs, and where it comes from, is in "Metrics collected, and what the model needs" above: `usable_wh` and
the load-to-watts map from trial 5 and the plug's readings around it, and the lead times and halt delay from test 4. The recharge
rate is a documented assumption, not a measurement.

**Staleness is not enforced by the model.** A battery that ages makes the static times optimistic, and nothing in a static response
follows the battery by itself. So a battery replacement, a change of load of more than about 30%, or a time to the abort voltage measured
20% below the last fit each means a new trial, a new fit and a release. Tracking that is a reminder, not a field (an open
decision).

**Starting values (rollout A)** are the default model's constants, in "First pass: a default model, on day one"; `rackmains_guard_halt_max_seconds` is then reset from the shed time plus the slowest measured follower shed plus a margin, once test 4 gives the shed times (Docker allows 90 s to stop per host and each runs four to six containers). They shed early on short outages and so waste battery, but never outrun what is proven.

**Later, fitted from trials and real outages.** An offline notebook, kept beside the weather-station one in the `mlflow` module, reads
Home Assistant's history and the outage CSV files, finds the knee at service load, the transfer sag (internal resistance)
and the time to the abort voltage, and writes the model's outputs, as a project until the model is served: `rackmains_guard_shed_max_seconds` is the knee time less
`rackmains_guard_shed_lead_seconds` (measured slowest shed, `max`'s halt, a margin), never below a minimum, and
`rackmains_guard_halt_max_seconds` follows from it. If the lead time does not fit inside the knee, the notebook says the battery cannot
support the shutdown and writes no file.

**Watts for the fit** come from the plug, paired with `ups.load` on mains and applied to the `ups.load` recorded through the discharge, as "How the map is built" and "How `usable_wh` is fitted" describe. The plug is a fit input only; the live guard sees only `ups.load`, since the plug is upstream and loses power in a real outage.

## Setting the thresholds, in rollout steps

The thresholds start very conservative, ship in a release, are tested against real data, then are reset in a second release.
Nothing is lengthened on a guess; each step is allowed only by the evidence named beside it.

| Step | Thresholds | Mode | Allowed by | Evidence it produces |
|---|---|---|---|---|
| A, floor | `rackmains_guard_shed_max_seconds` inside the proven span (145 s at service load held with no knee), `rackmains_guard_halt_max_seconds` from the measured shed times | dry-run | per-host `asleep` times (test 4); the forced-command test (3) | the guard's decisions on real mains events, logged but not acted on |
| B, live and cautious | the same | live | trial 1 held for the whole sequence length at worst-case load with no knee and no `LB`; trials 2 to 4 pass; the restart path chosen | real outages and by-hand cuts exercise the whole chain; each is a data point |
| C, measured | `rackmains_guard_shed_max_seconds` set to the knee time less `rackmains_guard_shed_lead_seconds` | live | trial 5 run to the floor once on this battery, plus any real outage, fitted offline | the knee at service load, the cutoff, whether `LB` raises |
| reset | recomputed | live | a battery replacement, a load change over about 30%, or a time to the floor 20% below the last fit | a new trial and a release |

**What each number needs.**
- **`rackmains_guard_shed_max_seconds`.** The knee time at service load (trial 5) less `rackmains_guard_shed_lead_seconds`. Until then only a span already survived is
  allowed: trial 1 proves it, and rollout A stays inside it. Check: the voltage at the end of trial 1 is still above the floor
  and has not begun to fall.
- **`rackmains_guard_<step>_lead_seconds` and `rackmains_guard_halt_delay_seconds`.** The slowest follower's `asleep`, start to `RESULT` and including the slowest container stop, and `max`'s
  `asleep --deep`, each measured several times on each host (test 4). The lead is that measurement plus a margin, which is a fraction of the spread seen, not a guess; the halt delay covers `max`'s `asleep --deep` plus a margin.
- **`rackmains_guard_mains_stable_seconds`.** The shortest run of `OL` that a flapping grid has not been seen to break, from the history, and
  long enough that a battery drained by the outage has begun to recover (about 6 hours to 90% per the manual, so a longer
  value is safer; there is no measure of the recovery, so it is a judgement).

**Why the floor and the knee need a run to failure.** Only a deliberate run shows the knee: the steps exist to avoid
reaching it in a real outage, so a real outage rarely supplies it. A single run to the voltage floor with the servers down (trial 5) costs some battery life, so it is made
once per battery, and its shape sets the `rackmains_guard_<step>_lead_seconds` every later outage is judged against. Without it the thresholds stay at rollout
B and waste battery but never risk the servers.

**Reset.** A reset is a refit from the outage CSV files and history, a new project or model version, a release, and a dry-run
period before live. The previous project stays in git, so a bad fit is undone by a release.

## The plug lever

The UPS is downstream of `rack_outlet_plug`, a Tasmota 13 plug at `http://10.0.4.102` (WiFi, `DeviceName` `rack_outlet_plug`,
`FriendlyName` "Server Rack", reading about 81 to 100 W), so switching its relay is a mains outage for the UPS, exactly timed
and independent of Home Assistant (which runs on `meg`, inside the rack). The API is open without a password on the LAN
(`cm?cmnd=…`), so anything on that network can cut the rack; `max` and a bridge container both reach it. `Delay` is in tenths of
a second and honours only 2 to 3600, so a longer cut chains delays. Read-only checks: `Status 0`, `Status 10`.
## Cutting the mains by hand

The `outage` tool (`tools/outage`) was deleted on 2026-10-30. A test cut is made by hand at the plug, and rackmains records it in its own outage CSV like a real outage, so there is no separate events file, run marker or abort logic to maintain.

- **The cut.** At the plug's console, `Backlog Power Off; Delay N; Power On`, so the restore is on the device. `Delay` is in tenths of
  a second and honours only 2 to 3600 (`Delay 4200` was ignored), so a cut above 360 s chains delays; the chain beyond one `Delay`
  is untested.
- **Before.** Check by hand what the tool used to: `rackmains_ups_on_battery` is off, all four hosts answer, `rackmains_guard_live` is the mode
  you intend, and `rackmains_guard_mains_seconds` shows the battery has settled. A live guard that sees the cut sheds the hosts, which
  trials 2 to 4 want and trial 1 does not.
- **Stopping early.** `Power On` at the plug console, which a by-hand run has instead of an abort rule. Stop on `LB`, on a host going
  down, or when the battery voltage in the log nears the floor.
- **Data.** The outage CSV on `max` holds the metrics every 5 s, plus event rows for statuses, decisions and command timings. Plug watts (`Status 8`) are
  read by hand on mains before and after, paired with `ups.load`, for the load-to-watts map; the plug reads 0 W while its relay is
  open. Note the cut length and start time beside each file.
- **Voltage refresh.** `pollfreq 4` is applied on `max` (it was 30, giving 32 s steps); the publisher sees 4 s.
- **Limits.** The plug's WiFi may not survive a long drain, so a long trial needs its device-side timer proven first (test 8).

## Trials

Every trial runs only after the battery has settled: on mains at least 12 hours since the last transfer, float steady within
0.1 V for 30 minutes, load steady within 3 points for 10 minutes, all four servers answering, outside the 01:00 backup window.
Abort on voltage, `LB`, a host down, stale readings or a cap, **never on the unit's capacity or runtime**.

| # | Trial | What it does | Needs first | Decides |
|---|---|---|---|---|
| 1 | Hold at service load | cut at the plug by hand for the whole rollout A sequence length (about 10 minutes), servers up, guard in dry-run | power-on-after-cut test not needed | the conservative timers fit; the knee if it appears |
| 2 | Recover before the shed | live guard, mains back before `rackmains_guard_shed_max_seconds` | guard built and trial 1 | nothing is shed, the reset works |
| 3 | Recover after the shed | followers shed (`asleep`) then `awake`, one follower first | power-on-after-cut test (5), forced-command test (3), `asleep` timing (4) | the restart path |
| 4 | Halt and UPS cut/restore | maintenance window, someone home; `shutdown.return` tried on a lamp first; if the UPS does not restart, press its On button | trial 3, lamp test | who brings the rack back |
| 5 | Run to failure, once per battery | servers down except `max`, **to the 11.5 V floor or `LB`, once, not to the UPS cutting out**; the outage CSV on `max` records it; network gear drains; a second point at service load because the low load runs long | device-side dead-man proven (chained `Delay`, or a Tasmota Rule/RuleTimer), trial 1 | the real knee and cutoff, whether `LB` raises, the offline fit |

## Tests still needed

Ordered from no risk to most; each result decides a branch.
1. **Baseline** a day on mains with the recorder: which flags appear unprompted (`BOOST`, `TRIM`).
2. **Quick battery test** (`test.battery.start.quick`): the test flag's name and the seconds spent in `OB`, in a quiet hour.
3. **Forced command** on `may`: a dedicated key with `command="echo ok",restrict` (no shell, no other command, no forwarding),
   then `command="/usr/local/bin/asleep --deep --dry-run",restrict`, run from a container on `max`. A forced command takes no
   arguments from the client, so decide here between a key per action (`asleep --deep`, `asleep --shallow …`, `awake`) and one
   wrapper that dispatches on `SSH_ORIGINAL_COMMAND`.
4. **Per-host `asleep` time**, from the start of the command to its `RESULT` line (the log's `took`), several runs per host and
   the slowest container stop; order `may`, `mad`, `meg`. Measured so far: `max`, shallow, three containers, about 3 s; no deep
   run yet.
5. **Power on after a cut** (still to do), per host. A clean `poweroff` is not the test, the board stays off after one; a cut
   while running, with no `asleep`, is optional and risks the filesystem. Decides whether the halt and UPS cycle brings the rack
   back, and how long each host takes to answer ssh.
   - **`max`, `may`, `meg`.** `AFTERG3_EN` is already cleared (`1c08`). Run `asleep --deep` (on `max`, `--shallow`), pull the
     cord from the UPS for 10 s, replace it, and time the boot to ssh.
   - **`mad` (Mac mini M2 Pro), a macOS step first, by hand.** Linux has no knob for it on kernel 6.14, so:
     (a) boot macOS from the boot picker (hold the power button at startup, choose macOS);
     (b) turn on "Start up automatically after a power failure" in System Settings, Energy Saver;
     (c) check in Terminal that `pmset -g | grep autorestart` prints `autorestart 1`;
     (d) boot back into Linux and run the same cut test as above.
     The only report that the setting carries through into Linux is on a base M1 Mac mini
     ([AsahiLinux/docs#156](https://github.com/AsahiLinux/docs/issues/156)), so the M2 Pro result is part of this test. The
     `ac_power_mode` sysfs attribute suggested there is missing on this kernel; `install_prep.sh` writes `restore` to it
     if a newer kernel offers it.
6. **`shutdown.return` on a lamp**, and `shutdown.stop` cancelling it: whether the UPS restarts by itself.
7. **Standby**, only with the outlets empty: `ups.status` for `OFF`.
8. **Plug dead-man**: the device-side restore of a chained `Delay`, proven by hand with the plug unreachable.
9. **Reachability**: that the plug console and all four hosts are reachable from where you cut, and that place is not on the UPS
   (`jen` was outside the rack).

The guard's build can begin after 3 and 4, with the restart left behind an interface until 5 is in.

**Acceptance.** A flag is a trigger only once it has been seen on this unit: `OB` (seen), the test flag (test 2), `OFF` (test 7).
`LB` and the alarm flags are overrides until observed; if `LB` never appears before the unit cuts, it is dropped from the design
and the time cap carries that job.

## Gaps and risks for the fit

Found in review on 2026-10-28 and still open.

| # | Gap | Closed by |
|---|---|---|
| 1 | trials ran at average load; the 01:00 backup and service starts raise it | take the worst-case `ups.load` over a week of history; run trial 1 at it, or add the extra load by hand; `LB` is the backstop |
| 2 | a second dip soon after the first finds a partly drained battery (about 6 h to 90%) | the guard's clock resets after `rackmains_guard_mains_stable_seconds` of mains; the model credits the used energy back slowly over a fixed 6 hours, which covers the second dip |
| 3 | the current battery's age and condition are unknown | not a model input (decided); the fit is of this battery, and a replacement means a new fit |
| 4 | what else is on the UPS (switch, router, access point, the Mac) is not inventoried | **yours:** list the loads on the UPS; the plug's WiFi and the followers' ssh path both depend on them |
| 5 | the 11.5 V abort floor is arbitrary | set the trial 5 floor from trial 1's voltage slope, then raise it stepwise |
| 6 | the offline fit's data path is unchecked | Home Assistant's history of the rackmains entities plus the outage CSV files; the by-hand pairs of plug watts and `ups.load` go wherever you keep them for the notebook; confirm Home Assistant records the entities at battery cadence |
## Open decisions

- **Delivery decisions** (the project flavour, the served mode, the `wasm` hosts) are in `model.md` section 2 (Requirements) and `plans/mlmodels.md`.
- **State persistence.** The carried state is persisted by the caller with the project hash it came from. Where, and in what format, is the
  guard's state file, which is not yet defined (see the open decision on it).
- **The route to the first fitted model** is "Route to the first fitted model": the `static` default first, then a fitted `wasm` project once
  trial 5 exists and the `wasm` flavour is implemented.
- **Model signature numbers.** The call cadence (5 s on battery, 5 minutes on mains), the "younger than three calls" freshness, the
  rounding epsilon of 1e-6 and the 120 s placeholder halt delay (until test 4 measures `max`'s `asleep --deep`) are my proposals.
- **A ceiling the model cannot exceed.** With the model owning `rackmains_guard_halt_max_seconds`, a bad fit could set a value longer than
  the battery lasts. Recommended: the guard compiles in an absolute ceiling on that one output (the nameplate-derived upper
  expectation, about 3,600 s) and treats a response above it as invalid. This is the only parameter the guard would then own.
- **A staleness reminder.** The default model carries no expiry, and the recalibrate flag exists only once a fitted model does, so a
  battery replacement or a six-monthly look at the trial 1 result is tracked outside it (a Home Assistant reminder, or by hand).

## Designs considered and left out

- **A feature layer outside the model artifact,** a declarative vocabulary per language or a shared Rust core with Python bindings, fed by
  windows of rows. Set aside for the `wasm` flavour: the features would not ship with the model, and it needs a second implementation
  in every runtime.
- **The service computes the features and records them (design R).** Set aside: the features are not part of the artifact, so the
  pipeline cannot add one without a service release.
- **A battery model on the unit's capacity or runtime, or on NUT's estimate.** Both are smoothed model outputs that lag.
- **A fraction-used accumulator with a Peukert load model.** More machinery than the conservative timers justify until a
  trial shows the timers waste battery.
- **A runtime `calibrate` tool with `calibration.json`.** Reloaded by the guard, with a `calibrating` flag, a health entity and
  an accumulator. Dropped for offline fitting and baked-in thresholds: nothing in the running service learns, and a threshold
  change is a reviewed release.
- **Reading the HID interface natively, or a second NUT driver (`usbhid-ups`).** Dropped; see the HID verdict in "The unit" in the rackmains service plan.
