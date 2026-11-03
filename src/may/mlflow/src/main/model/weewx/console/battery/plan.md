# weewx / console / battery

The plan for the weewx weather station console battery model. It follows `spec.md`, the specification for MLflow model projects, and
holds only what is specific to this model.

| Term | In This Plan |
|---|---|
| **Module** | `weewx` |
| **Model** | `console` |
| **Notebook** | `src/may/mlflow/src/main/model/weewx/console/battery/notebook.ipynb` |
| **Registered Model** | `weewx_console_battery` (`spec.md` 6.1) |
| **Project Flavor** | `pyfunc`, with a `static` floor to follow; `wasm` only if an embedded consumer appears (`spec.md` 3.2) |
| **Consumer** | Home Assistant, calling `mlserver` when the voltage changes; embedding in Home Assistant later |
| **Worked Example** | The Python-only model flow (`plans/mlflow.md` 4) |

**Status, 2026-11-03.** The notebook fits and writes `model.py` with the fitted attributes built in, then stops at Evaluate because the acceptance criteria
have no labelled `backtest` run to measure. Package and Register are wired to run once it passes: golden steps from the shipped `model.py`, the `pyfunc` project and its registration. Nothing consumes the project yet, and the weewx module still carries the old hand-copied snippet in
Home Assistant.

**Why `pyfunc`.** The consumers are Home Assistant calling `mlserver` and Python, and none needs to run offline or embedded. `pyfunc` keeps the exact
arctan, where a `wasm` module could not, because `atan` has no exact cross-platform result (`spec.md` 4.2) and would need a piecewise-linear lookup. It
also needs no builder. The project MUST carry a `static` floor for when the network is gone (`spec.md` 3.3). A `wasm` version is the move only if
an embedded consumer appears.

## Intent

Turn the console battery's voltage into a remaining capacity percentage in steps of 5, so the battery can be tracked without a gauge. The
fitted curve replaces the arctan snippet that was copied into Home Assistant by hand.

## Signature

| Direction | Name | Type | Unit | Notes |
|---|---|---|---|---|
| Input | `weatherstation_console_battery_voltage` | FP64 | Volts | The name the weewx service publishes, used unchanged (`spec.md` 6.1) |
| Output | `weewx_console_battery_capacity_pct` | INT64 | Percent | Steps of 5, 0 to 100 |

The model is stateless: the signature has no state slots.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `console_battery_voltage_2024-06-06_2024-10-25` | The 2024 run, 1,137 samples, UTC, 3 hour steps |
| `validation` | `console_battery_voltage_2026-08-13_2026-10-30` | The 2026 run, 813 on-change readings from InfluxDB |
| `backtest` | None | |
| `golden` | `console_battery_voltage_golden` | The fixed voltages and expected percentages that become `golden.json` |

**The 2024 run** runs from 3.965 V on 2024-06-06 through a plateau (3.80 to 3.55 V) and a knee from about 12 October to the 3.000 V
cutoff on 2024-10-25. The raw readings are not recoverable from InfluxDB or its backups, whose store starts 2026-08-13. The data was
reverse engineered from the plot cached in git (the `Raw` line, revision 7ab8c7c7d) by mapping pixels to time and voltage through the axis
ticks, with a resolution of about 0.003 V and 3 hours and the steep end interpolated inside each pixel column. Its provenance is a plot,
not the sensor, so it is a shape for fitting and not a measurement. The Home Assistant statistics database, if it kept 2024, is the
better source.

**The 2026 run** is one discharge from 4.17 V (full) falling to 3.82 V by about 10 September and then flat at 3.76 to 3.80 V for six
weeks, in 0.01 V steps, with no charge event and no knee. It covers the top of the curve and the plateau only.

Neither run is a full cycle alone. The two together cover 4.17 V down to 3.0 V, assuming the same cell and sensor calibration.

## Fit

A bounded arctan from voltage to capacity, fitted on `training` only. On the 2024 data it comes out at `k` 39.9, `w` 10.9, `x0` 3.767 V and
`y0` 59.8, close to the deployed curve, with an in-sample error of 2.8 percent (4.1 percent after rounding to steps of 5, worst case 11.7).

On the `validation` run the predictions stay inside 0 to 100, but the stepped output rises 242 times in 812 steps on what is a one-way
discharge. The sensor's 0.01 V resolution moves the answer about 4.4 percent per tick near the centre, so noise flips the 5 percent
steps.

## Open decisions

- **Fit data.** Whether to stitch the 2026 top into the 2024 run to fit one full curve, or recover 2024 from Home Assistant statistics.
- **Flicker.** The stepped output needs smoothing or hysteresis. A state slot can hold it once the flavor is available.
- **Home Assistant embedding.** Served by `mlserver` first is decided (2026-10-31). Embedding in Home Assistant is possible later with
  a `wasm` version, which needs a builder and a piecewise-linear lookup in place of the arctan.

## To do

0. The notebook now fails at Evaluate on purpose. `acceptance.json` holds one provisional `backtest` row, `rmse <= 5`, which is one 5 point step and is yours to confirm, and no `backtest` data exists so it measures nothing. Capture a run with a known capacity, from a reference gauge or a full discharge, as `backtest`, then write `acceptance.json` (`spec.md` 6.8) and evaluate it in the Evaluate section. The `validation` run cannot serve, since it only falls to 55 % and then rises, so its time-normalised capacity is not true.
1. Add the `static` floor, a constant capacity the consumer can act on without the network (`spec.md` R8).
2. Check that MLServer's MLflow runtime loads the registered model (`plans/mlflow.md` 3); `register_project` already logs it with `mlflow.pyfunc.log_model`.
3. Add smoothing or hysteresis in the carried state.
4. Wire Home Assistant to the served model, and remove the hand-copied snippet.
