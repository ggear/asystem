# rackmains

**Status, 2026-10-31.** Built and tested locally, not released. The publisher is done: it reads the NUT driver socket,
publishes `rackmains/{data,status}` to the broker, and ships with a mock driver and a mock-backed system test. The host setup
(`install_prep.sh`, `install_pre.sh`) is written and unit tested. The tool that cut the rack's mains through its smart plug
(`tools/outage`) was deleted on 2026-10-30; a test cut is made by hand at the plug. The host side of the shutdown is built and tested
on `max`, in the `system` module (`asleep`, `awake` and the restart-after-power-loss setting). Waiting on you: the 25 metric rows
and the service switch row ("Workbook rows to add"), the release, and the power-on-after-cut tests. The shutdown guard is designed and not built.
The battery model is designed and not built, apart from the default model of day one, which is built (the model plan, `src/may/mlflow/src/main/model/rackmains/ups/battery/plan.md`):
the `static` project `rackmains_ups_battery` `static-1` is written by the `ups_battery` notebook from the guard thresholds into
`src/build/resources/model/default/` (`project.json`, `signature.json`, `golden.json`), with four golden steps, and `generate.sh` verifies it
on every generate. The Rust loader that reads it, its place in the image and the guard's validation at start are not built.

**Decided 2026-10-30, not built.** Every metric is published on MQTT for Home Assistant and, during a battery drain, also written to a
CSV in the home dir; there is no InfluxDB writer. Polling speeds up on battery and publishing is rare on mains, and health no longer
depends on MQTT (see "Metrics, MQTT and the outage CSV"). The module `CLAUDE.md`'s payload and health descriptions change when that
is built.

This file holds the status, what the code cannot say, the review and phases, and the open decisions for the service; the code and
the module `CLAUDE.md` say how the publisher works. Fitting and serving the battery model, tuning the guard's thresholds, and the
trials and tests that supply the data are in the model plan, which refers back here for the unit, the metrics and the guard.

---

## Goal and shape

1. **Publish** the rack UPS's mains and battery state to Home Assistant over MQTT, so an outage or a failing battery is
   visible and automatable there. Built.
2. **Guard** the rack: on a power cut, shut the other servers down early, `max` last, and bring the others back if mains
   returns in time. Designed; a thread inside this container.

**Simple and consistent.** rackmains only ever produces data. Nothing in the running service measures, fits or learns the
battery. Thresholds are outputs of a model that is fitted offline (see "The model signature, inputs, outputs and thresholds" in the model plan); until a fitted model exists a default model project (flavor `static`) ships in the image from the first release, and changing it is a release.

**Out of scope, deliberately**

- **No InfluxDB writer** (decided 2026-10-30, after a brief reversal the same day). Home Assistant records every published entity,
  and during an outage the CSV files hold the complete record.
- **No supervisor integration.** The guard lives here, so supervisor needs no UPS plugin. Two passive links: supervisor's
  generated config for `macmini-max` picks up the `rackmains` container on its next generate (which also gives Home Assistant its
  `Service Rackmains` switch, from the container's health check), and a host the guard powers off has its supervisor publish
  `offline`. A cut during the 01:00 nightly backup interrupts it; the guard does not coordinate.
- **No `upsmon` or `upssched`.** They stay disabled; see the designs left out.
- **No in-process calibration.** No runtime `calibrate` tool, no reloaded `calibration.json`, no battery-model `calibrating` flag (unrelated to the NUT `CAL` status, which is `rackmains_ups_calibrating`), no
  battery-health entity, no accumulator or Peukert model. Those were designed and dropped for the offline fit.

## The host, `max`

Set up by the module's own `install_prep.sh`, which runs on `install` and is idempotent. It installs `nut` and `nut-client`
with `dnf` when `rpm` says they are missing and writes `nut.conf` (`MODE=standalone`), `ups.conf` (`driver = nutdrv_qx`,
`port = auto`, `vendorid = 0665`, `productid = 5161`, `protocol = voltronic-qs`, `pollfreq = 4`) and `upsd.conf` (`LISTEN`
127.0.0.1 only), each only when its content differs. It then enables `nut-driver@<ups>` and `nut-server` and restarts both
once, only when a file changed. The UPS name comes from `RACKMAINS_DEVICE`, a `nutdrv_qx-<ups>` socket, so there is one
source. It creates no `upsd` users, never touches `upsmon`, and exits 0 whatever happens. `install_pre.sh` publishes the
discovery topics only when the version changed and a generated `broker.sh` exists. Only this module's own hooks are used.

The USB chip `0665:5161` has two HID interfaces. `nutdrv_qx` drives interface 0 over Voltronic-QS (auto-detect settled on
0.10, hence `protocol` is pinned). Interface 1 is a standard HID Power Device (`/dev/hidraw`, 769 byte descriptor).

The driver socket is `/run/nut/nutdrv_qx-powershield`, `0660` `nut:nut` in a `nut:dialout` `0770` directory; the container
runs as root and a `:ro` bind mount still connects. The socket accepts every command `upscmd -l` lists, among them `load.off`,
`shutdown.*` and `driver.killpower`, and `:ro` does not stop them, so the publisher only ever writes `DUMPALL`.

A transient unit `ups-recorder` on `max` runs `src/build/resources/validation/ups_recorder.py`: one JSON line every 2 s to
`/var/tmp/ups_status.jsonl` with the NUT variables, about 8 MB a day. It is a validation
aid independent of rackmains; `systemctl stop ups-recorder` ends it. **It is dropped after trial 1** ("Trials" in the model plan), once the new publisher has
agreed with it through a long cut and real data is being captured: stop the unit, delete `ups_recorder.py` and the `validation/` directory, and rely on the published entities in
Home Assistant's history and the outage CSV files on `max`. The HID fields it also logged are dropped from the design (see the HID verdict below).

## The unit, PowerShield Defender RackMount 800 (PSDR800)

From the manual kept at `src/build/resources/doc/powershield_psdr800_user_manual.pdf` (official V2, 22/04/2024).

| | |
|---|---|
| Rating | 800VA / 480W, 240 VAC, line interactive, simulated sine wave on battery |
| Battery | one 12V 9Ah, user replaceable, about 6 hours to recover to 90% |
| Input window | 177 to 290 VAC, output regulated to 240 VAC +/-10% |
| Transfer | 2 to 6 ms typical |
| Not in the manual | backup times, any self-test schedule, the status bits over USB |

| LCD status | Meaning | Beeper |
|---|---|---|
| On line | Utility stable | none |
| AVR operation | Boosting or bucking input | none |
| On battery | Running from battery; display alternates battery level and remaining time every 5 s | two beeps every 30 s |
| Low battery | "The unit is about to shut down" | rapid beep, 1 s intervals |
| Overload / Fault | output over rating / call for assistance | constant |
| Standby | button not pressed, outlets **not supplied** | none |

**Expected NUT status per state** (from memory of the Megatec status byte; only `OL` and `OB DISCHRG` have been seen).
`OL` normal; `OL` with `BOOST` or `TRIM` is information; `OB` is the trigger; `OB LB` is a last-resort override; `OFF` is a
silent failure (the outlets are unprotected) and alerts at once; a test flag is ignored because the shed waits `rackmains_guard_shed_max_seconds`. The beeper is audible only,
so the guard reads `ups.status`, never the alarm.

**What can be trusted today**

| Signal | Trust | Notes |
|---|---|---|
| `OB` / `OL` in `ups.status` | **yes** | follows the cut within 1 to 5 s, `OL` back within 2 s of restore |
| Elapsed time on battery | **yes** | the guard's own clock |
| Battery voltage and load | partly | falls 13.3 to 12.0 V in 11 s then sits flat; uninformative on the plateau until the knee; refreshes every 4 s at `pollfreq 4` (32 s before); sags under load and rebounds |
| `input.voltage` | no | reads 8.4 V when cut, the LCD says 0; `OB` is the signal. `input.voltage.fault` tracks the input and holds no memory |
| Battery current, output current, watts | **not reported** | neither NUT (only a fixed `output.current.nominal` of 3.0) nor the HID interface (none of its 153 fields) has a current or power reading; any amperage in this plan is inferred from `ups.load` of 480 W and about 12 V (roughly 4.5 to 6 A at 11 to 15% load, before inverter losses). The only measured wattage is the plug's 81 to 100 W, which includes the UPS's own losses and charging |
| NUT `battery.charge` | no | NUT's own estimate from voltage against 10.4 and 13.0 V; 100 to 58 in a minute |
| Unit capacity, unit runtime, LCD "bat" figure | no | smoothed model outputs; capacity fell 90 to 40 in 145 s with the voltage flat and rebounded 40 to 65 in 20 s; runtime falls at most 1 s/s, rises about a third of that, wanders 870 to 1766 s on mains |
| `LB` | untested | never raised in 145 s; only a run to failure will show if and how long before the cutoff |

**HID metrics and `usbhid-ups`: dropped (decided 2026-10-28).** Nothing from the HID interface is collected, published or used.
The unit's own capacity and runtime are model outputs that lag; its `Discharging` and `ACPresent` flags lead NUT's `OB` by about
4 s on a long cut, which the first action at 120 s does not need, duplicate `OB`, and missed the 1 s blip that NUT caught; its
alarm flags (`NeedReplacement`, `BelowRemainingCapacityLimit`, `ShutdownImminent`, `InternalFailure`, `Overload`) never raised
and stay unknown; and reading any of it needs a second reader of the chip. `usbhid-ups` has no subdriver for the ID and leaves
interface 1 detached when it exits (fix: `echo 1-7:1.1 > /sys/bus/usb/drivers/usbhid/bind`). The per-subdriver results, every
dynamic HID field, the raw descriptor and a field snapshot stay as reference only in `src/build/resources/doc/usbhid_ups_reference.md`,
`hid_report_descriptor.hex` and `hid_fields_snapshot.txt`; nothing in the code or the workbook refers to them. The recorder's
`hid.*` fields are not carried into any later logger.

## Metrics, MQTT and the outage CSV

**Decided 2026-10-30, not built.** This replaces a same-day design that wrote every metric to InfluxDB and kept MQTT small. There is
**no InfluxDB writer**. Every metric is published on MQTT for Home Assistant, which records its own history, and during a battery
drain every metric is also written to a CSV in the home dir, so the data survives the broker and the other servers going away.
`SAMPLES` in `nut.rs` stays the one mapping from NUT variable to metric, extended with the canonical name below, so one table drives
the payload, the CSV header and the entity rows. `ups.status` is resolved to bools by one pure function (below).

**One name per metric: `rackmains_<group>_<metric>`**, with a unit suffix on numeric metrics (`_volts`, `_hertz`, `_pct`, `_seconds`).
The same string is the MQTT payload key, the CSV column header and the Home Assistant `unique_id`, and the `rackmains_` prefix says
where it came from. The group says what is measured, and this table is the master list: the payload keys, the CSV columns and every table
below follow its order, and a name that is not in it is not a metric.

| Group | What it is | Metric names, in payload and CSV order |
|---|---|---|
| `clock` | the poll time as a number | `rackmains_clock_epoch_seconds` |
| `mains` | the supply at the UPS input | `rackmains_mains_input_volts`, `rackmains_mains_input_fault_volts` |
| `output` | what the UPS delivers to the rack | `rackmains_output_volts`, `rackmains_output_hertz`, `rackmains_output_utilisation_pct` |
| `battery` | the battery | `rackmains_battery_volts`, `rackmains_battery_charge_pct`, `rackmains_battery_charging`, `rackmains_battery_low`, `rackmains_battery_replace`, `rackmains_battery_remaining_pct`, `rackmains_battery_remaining_seconds` |
| `ups` | the unit's own state | `rackmains_ups_status`, `rackmains_ups_on_battery`, `rackmains_ups_problem`, `rackmains_ups_calibrating`, `rackmains_ups_boost`, `rackmains_ups_trim` |
| `guard` | the shutdown guard | `rackmains_guard_state`, `rackmains_guard_live`, `rackmains_guard_mains_seconds`, `rackmains_guard_battery_seconds` |
| `model` | the fitted model's own outputs and state | `rackmains_model_energy_used_wh`, `rackmains_model_history_known`, `rackmains_model_recalibrate`, `rackmains_model_state` |

Bools are the integers `1` and `0`, never JSON `true` and `false`, in the payload and the CSV alike. `_pct` and `_seconds` values are
integers too (NUT reports `ups.load` and `battery.charge` as whole numbers), and `_volts`, `_hertz` and `rackmains_clock_epoch_seconds` are floats, and `rackmains_model_state` is text holding a JSON object of the model's
state slots by name, recorded in the CSV and the log only. The envelope is not a metric and has no prefix: MQTT `timestamp` and `period_ms`;
CSV `timestamp`, `elapsed_seconds`, `event` and `detail`. A key is absent from the payload when its variable is unreported, and its
CSV cell is blank. `ups.load` is published as *utilisation* so it is never mistaken for the watts of Powercalc's `Home Load`.

```json
{
  "timestamp": "2026-10-30T12:00:00+08:00",
  "period_ms": 2000,
  "rackmains_clock_epoch_seconds": 1793332800.0,
  "rackmains_mains_input_volts": 241.4,
  "rackmains_mains_input_fault_volts": 241.4,
  "rackmains_output_volts": 241.4,
  "rackmains_output_hertz": 50.1,
  "rackmains_output_utilisation_pct": 13,
  "rackmains_battery_volts": 13.4,
  "rackmains_battery_charge_pct": 100,
  "rackmains_battery_charging": 0,
  "rackmains_battery_low": 0,
  "rackmains_battery_replace": 0,
  "rackmains_ups_status": "OL",
  "rackmains_ups_on_battery": 0,
  "rackmains_ups_problem": 0,
  "rackmains_ups_calibrating": 0,
  "rackmains_ups_boost": 0,
  "rackmains_ups_trim": 0
}
```

The `rackmains_guard_*` keys join it, in the same position, when the guard exists, and the model's keys (`rackmains_battery_remaining_*`
and the `rackmains_model_*` ones) when a fitted model returns them; the default model returns none of them. The payload no longer has a `samples` object or the old `rack_*_<unit>` keys. The code, `schema.rs`, `system_test.py`, the health check
and the workbook templates all move to these names when built.

**Cadence (proposed).**
- **On mains.** Poll the NUT socket every 2 s, so a status flip is seen. Publish every 5 minutes (retained) and at once on any change
  of `rackmains_ups_status` or a derived flag, so the start and end of a dip reach Home Assistant within about 2 s. Nothing is written to a file.
- **On battery**, from the first `rackmains_ups_on_battery` until `rackmains_guard_mains_stable_seconds` of unbroken `OL`. Poll every 1 s, publish every poll, and
  write one CSV row every 5 s and on every event. The driver itself refreshes values only every `pollfreq` (4 s on `max`), so a
  faster poll repeats values and the gain is bounded; lowering `pollfreq` is a host-config change left until trial data shows it is
  needed.
- **The model.** One call every 5 s on battery (the cadence of a CSV row), at each transition between mains and battery, and every 5
  minutes on mains; embedded and served alike. The row sent is the poll time, the utilisation and the on-battery and replace flags, with
  the state the model returned last time. The numbers are recorded with the call, so a recording replays exactly.

**All metrics: MQTT, CSV and log**

| Name | Source | MQTT | CSV | Log |
|---|---|---|---|---|
| `rackmains_clock_epoch_seconds` | the poll time as seconds since the epoch, converted at source from `timestamp` | yes | yes | DEBUG per poll |
| `rackmains_mains_input_volts` | `input.voltage` | yes | yes | DEBUG per poll |
| `rackmains_mains_input_fault_volts` | `input.voltage.fault` | yes | yes | DEBUG per poll |
| `rackmains_output_volts` | `output.voltage` | yes | yes | DEBUG per poll |
| `rackmains_output_hertz` | `output.frequency` | yes | yes | DEBUG per poll |
| `rackmains_output_utilisation_pct` | `ups.load` | yes | yes | DEBUG per poll; derived in `end`: peak and mean while on battery |
| `rackmains_battery_volts` | `battery.voltage` | yes | yes | DEBUG per poll; derived in the CSV `end` row: minimum and when, the sag at transfer, the last value |
| `rackmains_battery_charge_pct` | `battery.charge` | yes | yes | DEBUG per poll; derived in `end`: charge at start and end |
| `rackmains_battery_charging` | `CHRG` | yes | yes | DEBUG on change |
| `rackmains_battery_low` | `LB` | yes | yes | INFO on change, with the seconds since `OB` and the voltage |
| `rackmains_battery_replace` | `RB` | yes | yes | INFO on change |
| `rackmains_battery_remaining_pct` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call, beside what actually happened |
| `rackmains_battery_remaining_seconds` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call; INFO when it falls to a lead threshold |
| `rackmains_ups_status` | `ups.status` flags, text | yes | yes | INFO on every change: the flags before and after, with the derived bools |
| `rackmains_ups_on_battery` | `OB` and not `CAL` | yes | yes | INFO on change; starts and ends the outage CSV; derived: time on battery |
| `rackmains_ups_problem` | `OFF` `OVER` `BYPASS` `FSD` `ALARM` | yes | yes | INFO on change |
| `rackmains_ups_calibrating` | `CAL` | yes | yes | INFO on change |
| `rackmains_ups_boost` | `BOOST` | yes | yes | DEBUG on change |
| `rackmains_ups_trim` | `TRIM` | yes | yes | DEBUG on change |
| `rackmains_guard_state` | the guard, text | yes | yes | INFO on every transition, with the inputs and the threshold compared (a `decision` row); derived: seconds to each step |
| `rackmains_guard_live` | the guard | yes | yes | in the `start` row's detail; in dry-run every command is logged as would-run |
| `rackmains_guard_mains_seconds` | the guard | yes | yes | `note` rows counting down to `rackmains_guard_mains_stable_seconds` |
| `rackmains_guard_battery_seconds` | the guard | yes | yes | on every `decision` row |
| `rackmains_model_energy_used_wh` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call |
| `rackmains_model_history_known` | the model, an optional output | yes, once a fitted model returns it | yes | INFO on change |
| `rackmains_model_recalibrate` | the model, an optional output | yes, once the model returns it | yes | WARN on a change to 1, with the reason from the response `parameters` |
| `rackmains_model_state` | the model's state as one JSON text of the named state slots | no, not published | yes, on the `start` and `end` rows and on a restart, reset or project change, blank otherwise | INFO on those rows; DEBUG on every call when the debug switch is on |
| `timestamp`, `period_ms` | the poll | yes | `timestamp`, `elapsed_seconds` | DEBUG per poll |
| events: transitions, decisions, commands, notes, summary | rackmains, the guard | **never** | yes, the `event` and `detail` columns | INFO. Command timings and host results (`asleep`, `awake`, `shutdown.return`: start, `RESULT` status, `took`) live only here and in the CSV. The `end` row holds the summary: duration on battery, minimum voltage and when, peak utilisation, whether `LB` raised, steps reached, hosts shed |
| service health, the `Service Rackmains` switch | the container's health check, from a heartbeat file and independent of MQTT | none from rackmains, supervisor publishes it | no | none here, supervisor logs it |
| outage count | dropped | no | no | the `end` row's duration for that outage; a count is a query over `rackmains_ups_on_battery` |
| `ups.temperature` | not reported by the unit | no | no | no |
| plug watts | not collected | no | no | no |
| read failures | the poll | no | a `note` row during an outage | WARN per failed read, INFO on a reinit |
| transfer reason, test result, charger status, beeper, identity | mostly not reported by this unit | no | a `note` row during an outage | INFO on change, identity once at start |

**The service status switch** is Home Assistant's `Service Rackmains` switch under `Supervisor`, like `service_tempstat`: `Service Status`
domain, `Diagnostics` group, state topic `supervisor/macmini-max/data/service/rackmains/health_status`, `ON` when the container's
health check passes. Supervisor publishes it, so rackmains publishes nothing for it.

**Health does not depend on MQTT (decided 2026-10-30).** A drain sheds the broker's host with the other servers, so a health check
that read `rackmains/data` from the broker would fail exactly when rackmains is doing its job, and the switch would read OFF during
every outage.
- **Heartbeat file.** After every poll that read the UPS successfully, rackmains replaces a tiny file in the container's `/tmp`
  (written to a `.tmp` and renamed, no fsync, since a lost heartbeat is harmless) and the file's age is the health signal. A failed or
  stale read (`DATASTALE`, an unplugged UPS) does not touch it, so the container turns unhealthy by the same path as before.
- **`checkhealthy.sh`** tests that the heartbeat is younger than about 30 s (a few polls, unrelated to the 5 minute mains publish)
  and, once the guard exists, that the guard's own heartbeat in the state file is too. It no longer runs `mosquitto_sub` or `jq`,
  and needs neither the broker nor a payload.
- **MQTT trouble is reported, not fatal.** A broker that is down at start does not stop the process or the poll loop, and a lost
  connection never counts toward `MAX_CONSECUTIVE_FAILURES` or a reinit. Publishing is best effort through a bounded queue that
  drops while disconnected, and rackmains reconnects with backoff. The loss and the return are each one log line, WARN on mains and
  INFO during an outage when it is expected, with a `note` row in the outage CSV. On reconnect it publishes `online` and the full
  current payload so Home Assistant catches up. The broker's own last will still says `offline`, which is how Home Assistant sees it.

**`ups.status` to bools.** One pure function in `nut.rs`, with a table test over `OL`, `OB DISCHRG`, `OB LB`, `OL BOOST`, `OB CAL`,
`OFF`, an unknown token and empty. All derived bools are absent when `ups.status` is unreported, so Home Assistant keeps its last
state and a failed read never reads as an outage or a problem.

| NUT token | Resolves to | Logged |
|---|---|---|
| `OL` | `rackmains_ups_on_battery` 0 | no |
| `OB` | `rackmains_ups_on_battery` 1, unless `CAL` is present | INFO on change |
| `LB` | `rackmains_battery_low` | INFO on change |
| `RB` | `rackmains_battery_replace` | INFO on change |
| `OFF`, `OVER`, `BYPASS`, `FSD`, `ALARM` | `rackmains_ups_problem` | INFO on change |
| `CAL` | `rackmains_ups_calibrating`, and suppresses `rackmains_ups_on_battery` so a deliberate calibration is not an outage | INFO on change |
| `CHRG` | `rackmains_battery_charging` | DEBUG on change |
| `BOOST`, `TRIM` | `rackmains_ups_boost`, `rackmains_ups_trim` | DEBUG on change |
| `DISCHRG`, `HB` | nothing | DEBUG |
| any other token | nothing | WARN once per new token |

Decisions behind it (2026-10-30). `rackmains_ups_on_battery` and `rackmains_ups_problem` are separate so each entity means one thing and `BYPASS` never
reads as a power cut. `CAL` suppresses `rackmains_ups_on_battery` so a calibration does not add an outage or start the guard's time-on-battery
clock, at the cost of masking a real cut during one, which `LB` and the input voltage would still show. The `OB` test moves out of
the Home Assistant template and into the service, which gives it one owner and a test; this reverses the module `CLAUDE.md` line
"Home Assistant tests for the `OB` token", to be updated when built.

**Standard logging** goes to stdout, which Docker keeps (the compose file already rotates 5 files of 100 MB). INFO is one line per
event a human watching wants: start, every change of `rackmains_ups_status` or a derived flag, every command the guard runs and its result,
every CSV written or failed. DEBUG is everything per poll: each reading with its derived bools and each MQTT publish. During an
outage the logging is heavy: every guard decision with its inputs and the threshold it compared, and in dry-run the exact command it
would have run. Every log line and every CSV `detail` that mentions a metric uses its canonical name with the value in square
brackets, for example `change rackmains_ups_status [OL] to [OB DISCHRG]`, so a log line, a CSV row and the payload can all be found by
one string.

**The outage CSV**, on the data dir the compose file already mounts (`${SERVICE_DATA_DIR}` on the host, `/asystem/mnt/outage/` in
the container), so it is on the host's disk and survives Docker stopping.
- **Name and span.** `rackmains_outage_<portable timestamp of the first OB>.csv`. An outage starts at the first `rackmains_ups_on_battery` and
  ends after `rackmains_guard_mains_stable_seconds` of unbroken `OL`, the guard's own clock, so dips closer together than that are one file.
- **Columns.** `timestamp`, `elapsed_seconds`, `event`, `detail`, then every metric above in table order, headed by its canonical
  name. Every row repeats the last known value of every metric, so a row stands alone and a blank cell means never reported. `event`
  is empty on a plain sample and otherwise one of `start`, `status`, `decision`, `command`, `note`, `end`; `detail` is free text,
  quoted as RFC 4180, on one line. `start` carries the version, the model version and whether the guard is dry-run or
  live. A row is written every 5 s on battery, on every change of status or flag, and for each guard decision, command and note. A row with no
  event, or a `start` or `status` event, is also **one model call**: its numbers are the request and the outputs are in the row. The state
  is recorded as `rackmains_model_state` only on the `start` row (the state in), the `end` row (the state out) and on a restart, reset or
  project change, and is blank elsewhere, an exception to the rule that a row repeats the last values. The state between is a deterministic
  fold of the calls, so a replay regenerates it. The `decision`, `command`, `note` and `end` rows repeat the last values, and a
  replay skips them.
- **Same values as Home Assistant writes to InfluxDB.** Home Assistant records each entity through its InfluxDB integration, so the CSV
  is shaped to match what lands there (confirmed against the reflected `meg` schema and the integration source, 2026-10-30):
  - **Names.** The InfluxDB tag `entity_id` is the entity's object id, so the CSV column, the payload key and that tag are one
    string only if each row's `default_entity_id` is pinned to the canonical name. Pin it (see "Workbook rows to add").
  - **Bools.** Home Assistant stores a binary sensor as a float `value` of `1.0` or `0.0` plus a text `state` of `on` or `off`. The CSV
    writes `1` or `0`, the same number as `value`; the `state` text adds nothing and is not in the CSV.
  - **Numbers.** A numeric sensor is a single float `value`. The CSV writes the same number the payload carries, through the one
    formatter the payload uses (Rust's shortest round-trip form), so the CSV and the published value never differ by rounding. `*_pct`
    stay whole numbers.
  - **Text.** `rackmains_ups_status` and `rackmains_guard_state` are not numeric, so Home Assistant stores them as a text `state` only.
    The CSV writes the same string, on one line, quoted.
  - **Gaps.** An absent key leaves Home Assistant on its last state, so each CSV row repeats the last known value and a blank cell
    means never reported. Home Assistant drops `unavailable` and `unknown` states and writes only on change, while the CSV writes a
    row every 5 s on battery whatever the broker is doing, so the CSV is the complete series and the InfluxDB data is a subset of it;
    forward-fill the InfluxDB side to compare. Timestamps differ by the publish and receive delay: the CSV time is the poll, the
    InfluxDB time is when Home Assistant fired the event.
- **Safe write.** The whole file is rebuilt from the in-memory rows, written to `<name>.tmp` in the same directory, fsynced, renamed
  over the final name, and the directory fsynced, so the file on disk is always the whole previous version or the whole new one,
  never torn. A write happens at most every 5 s, except that an event row writes at once, and the `decision` to halt and the
  `shutdown.return` command are written, fsynced and waited for (bounded, 5 s) *before* the command is sent, so they are on disk
  before `max` quiesces. A run to failure therefore loses at most the rows since the last rename.
- **Small.** About 300 bytes a row, so 1 MB holds about 3,300 rows, or 4.6 hours at one row every 5 s. Past 1 MB the file continues
  in `..._2.csv`, so no rewrite is ever larger than that.
- **Works with everything else asleep.** It needs only this container and a writable data dir. `asleep --shallow` on `max` leaves
  `/home` writable and unmounts only what no running container holds; confirm `${SERVICE_DATA_DIR}` is under `/home`. The broker on
  `meg` is shed with the other servers, so MQTT publishing is best effort (a bounded client queue that drops when disconnected) and
  the CSV is the only complete record of a real outage.
- **Independent of everything else.** A dedicated writer thread behind a bounded channel does the writing, so a slow or failed write (a
  disk detaching) logs a WARN to stdout and never blocks the poll, the publisher or the guard. The in-memory rows keep growing, so
  the next write carries everything and a failure costs time, not rows.
- **Recovery.** On start, a stray `.tmp` is deleted, and a file whose last row is not `end` belongs to a process that was killed or
  lost power mid-outage: it is rewritten atomically with an `end` row whose detail is `interrupted`, timed at its last row. If the UPS
  is still on battery a new file starts, and its `start` row names the interrupted one; the guard's state file says who was shed.
- **Bounded.** The newest 100 files are kept (`OUTAGE_LOG_KEEP`), pruned only after a new file has been renamed into place and never
  the current or newest one; pruning is safe because the backup below is additive. The `outage/` directory is created at start, since
  the backup's include list fails on an absent directory.
- **Backed up, as the other modules are.** rackmains enrols with `write_container_backup()` and a `src/build/resources/backup.sh`
  whose include list is `outage` and whose excludes are `*.tmp` and the guard state file. Supervisor's policy then applies:
  primary under `/home/asystem/rackmains/backup/<run>/`, secondary GFS, tertiary mirror, and each release backs rackmains up first
  and abandons the install if that fails. Add `RACKMAINS_BACKUP_KEEP_{DAILY,WEEKLY,MONTHLY}` to `.env_all`; the files are small,
  so keep monthly points for a long time.
- **Following it.** The file is replaced, not appended, so `tail -F` on its path re-reads the whole file at every replace. Live
  follow is `docker logs -f rackmains`, which carries the same events at INFO; the file is what is left afterwards, read with `cat`,
  a spreadsheet or pandas. It is the failure record for real outages and for by-hand test cuts alike.
- **Tests.** A failed rename leaves the previous file intact; a failed write does not block the poll thread and the next write holds
  every row; recovery marks an unfinished file `interrupted` and deletes a stray `.tmp`; the prune keeps the newest and never the
  current file; the pre-halt row is on disk before its command is sent; the header equals the canonical names the payload
  declares, checked both ways; a table test deriving the `end` summary from a sequence of statuses and samples; and the process polls, writes the CSV and stays
  healthy with the broker unreachable, including at start.

**Short outages (decided 2026-10-28, revised 2026-10-30).** A one-second cut at 18:05:25 showed as `OB DISCHRG` in one 2 s recorder
sample and was gone by the next, so a slow poll would usually miss it. The poll is therefore 2 s even on mains, and any status
change publishes at once, so Home Assistant's history records the start and end of every dip the driver saw. A dip that falls
between two driver polls is still unseen. Outages are counted from Home Assistant's history of `rackmains_ups_on_battery`, not in the
service.

`rackmains_battery_charge_pct` is NUT's coarse estimate, from the battery voltage against `battery.voltage.low` and `.high`; the guard
never uses it.

**Guard metrics.** The guard's metrics join the payload when the guard exists, and each gets its own workbook row, `Enabled` for the
dry-run release, so nothing is added later by surprise. `rackmains_guard_state` is one of `idle`, `waiting`, `shedding`, `holding`,
`halting`, `restoring`; `rackmains_guard_live` is off while in dry-run; `rackmains_guard_mains_seconds` is the seconds on line since
the previous outage ended, absent when unknown; `rackmains_guard_battery_seconds` is the guard's accumulated time on battery.

## Workbook rows to add to `entity_metadata.xlsx`

Every payload metric except `rackmains_clock_epoch_seconds` (in the payload, the CSV and the log only) and `rackmains_model_state` (in the
CSV and the log only) gets a row, `Enabled`, all `device_via_device` **`RackMains`**, in
`src/all/_/src/build/resources/metadata/entity_metadata.xlsx`, with `unique_id` the canonical name and the payload key the same string.
Tell me when they are in and I run `fab generate`; I do not edit the workbook. Fill each new row **down from a `TempStat` row** so the
four topic columns and `name`, `device_name` and `device_identifiers` stay calculated (`rackmains/data`, `rackmains/command`,
`rackmains/status`, `homeassistant/<namespace>/rackmains/<unique_id>/config`). Never type those in. The device classes are
suggestions; mirror the nearest sibling row. A device class also sets the InfluxDB measurement (`<domain>__<device_class>`, or
the domain alone when there is none), so choose it knowing that. Pin each row's `default_entity_id` to the canonical name, for
example `sensor.rackmains_battery_volts`, so the InfluxDB `entity_id` tag equals the CSV column and the payload key.

| `unique_id` | Namespace | Unit | `device_class` |
|---|---|---|---|
| `rackmains_mains_input_volts` | `sensor` | V | `voltage` |
| `rackmains_mains_input_fault_volts` | `sensor` | V | `voltage` |
| `rackmains_output_volts` | `sensor` | V | `voltage` |
| `rackmains_output_hertz` | `sensor` | Hz | `frequency` |
| `rackmains_output_utilisation_pct` | `sensor` | % | |
| `rackmains_battery_volts` | `sensor` | V | `voltage` |
| `rackmains_battery_charge_pct` | `sensor` | % | `battery` |
| `rackmains_battery_charging` | `binary_sensor` | | `battery_charging` |
| `rackmains_battery_low` | `binary_sensor` | | `battery`, on means low |
| `rackmains_battery_replace` | `binary_sensor` | | `problem` |
| `rackmains_battery_remaining_pct` | `sensor`, with the model | % | |
| `rackmains_battery_remaining_seconds` | `sensor`, with the model | s | `duration` |
| `rackmains_ups_status` | `sensor`, text | | |
| `rackmains_ups_on_battery` | `binary_sensor` | | |
| `rackmains_ups_problem` | `binary_sensor` | | `problem` |
| `rackmains_ups_calibrating` | `binary_sensor` | | `running` |
| `rackmains_ups_boost` | `binary_sensor` | | |
| `rackmains_ups_trim` | `binary_sensor` | | |
| `rackmains_guard_state` | `sensor`, text, with the guard | | |
| `rackmains_guard_live` | `binary_sensor`, with the guard | | |
| `rackmains_guard_mains_seconds` | `sensor`, with the guard | s | `duration` |
| `rackmains_guard_battery_seconds` | `sensor`, with the guard | s | `duration` |
| `rackmains_model_energy_used_wh` | `sensor`, with the model | Wh | `energy` |
| `rackmains_model_history_known` | `binary_sensor`, with the model | | |
| `rackmains_model_recalibrate` | `binary_sensor`, with the model | | `problem` |

Shared by every row, mirroring `TempStat`: `entity_status` `Enabled`, `unique_id_device` `macmini-max`, `entity_domain`
`Device Conditions Rack`, `entity_group` `Diagnostics`, `device_suggested_area` `Rack`, `_device_name_suffix` `Mains`,
`device_manufacturer` and `device_model` the UPS's own, `device_sw_version` `ASYSTEM_VERSION`, `qos` `1`, `force_update`
`false`, `powercalc_enable` and every `powercalc_group_*` blank. `state_class` is `measurement` for every numeric sensor. Check what
`sample_period` drives: it was `60` for a 60 s publish, and the mains publish is now every 5 minutes, so it must match that or the
entity may read as stale between publishes.

A numeric sensor keeps its last state when its key is absent, so a failed read never reads as a value of zero:

```
{{ (value_json['rackmains_battery_volts'] | float(None)) if value_json['rackmains_battery_volts'] is defined else (states('sensor.rackmains_battery_volts') | float(None)) }}
```

A binary sensor row sets `payload_on` to `1` and `payload_off` to `0`, so its template returns the integer itself and, when the key
is absent, re-emits its own current state as an integer. No existing MQTT `binary_sensor` row sets those two columns (the 31 enabled
binary sensors in the workbook are template, UniFi, Sonoff and SenseMe entities), so there is no sibling to copy them from:

```
{{ value_json['rackmains_ups_on_battery'] if value_json['rackmains_ups_on_battery'] is defined else (1 if is_state('binary_sensor.rackmains_ups_on_battery', 'on') else 0) }}
```

The key each template reads must match the canonical name the service declares.

**One more row, for the service status switch.** There is no `service_rackmains` row in the workbook today (`service_tempstat` is
the model). Add it under `device_via_device` **`Supervisor`**, filled down from `service_tempstat` so the topics stay
calculated, with `unique_id` `service_rackmains`, `name` `Service Rackmains`, `unique_id_device` `macmini-max`, `Enabled`; it
resolves to `supervisor/macmini-max/data/service/rackmains/health_status`, command topic
`supervisor/macmini-max/command/service/rackmains`. Whether supervisor already publishes that topic for rackmains once its
config is regenerated for `macmini-max` has not been checked, and is confirmed after release.

After the rows: `fab generate` and read the diff, then add a check that every key a generated `value_template` reads is a
declared payload key. The system test's declared-topics check cannot pass until the rows exist.

## The shutdown guard (designed, not built)

**Why here and not `upsmon`.** The wanted behaviour is staged and reversible: shed the others, then `max`, or bring the
others back if mains returns. `upsmon` knows on-battery, low-battery and forced shutdown, so it cannot restore. A state
machine with hysteresis and a restart mid-sequence is easy to test in Rust against a mock driver and a mock ssh.

**Shape (decided).** A thread inside the one rackmains container, started by `run` before the publisher loop: one binary, one
image, one health check, and no change elsewhere.
- Its loop never touches MQTT, has its own clock and shares no blocking state with the publisher. `run` today connects to the
  broker before it polls; that order changes, so the guard is already running when the broker is unreachable (`meg` down).
- It reads the socket and, if it sends the final UPS command itself, writes to it (the mount then stops being `:ro`); otherwise
  the host sends it. The publisher's path writes only `DUMPALL`, held by discipline and a test of that path.
- It needs the ssh keys (a dedicated key, mounted read-only from a root-only directory on `max`, `known_hosts` pinned,
  `openssh-client` pinned in the image), the generated host list, the model's policy, and a state file under `/asystem/mnt` so a
  restart mid-sequence knows who it already shut down. It reconciles with that file on every start.
- A panic ends the process (release profile aborts) and Docker restarts it. The health check reads the guard's heartbeat from
  the state file. The guard writes its state to that file and the publisher reads and publishes it, one way.
- Every action is idempotent. A sequence starts only on a fresh reading that says on battery and a restore only on a fresh
  reading that says mains; once started, failed or stale reads do not stop it, because a USB glitch mid-outage must not leave
  the servers up until the battery is flat.
- The host list is generated by `fab generate`: workbook `Server` rows that are `Enabled`, area `Rack`, model starting
  `MacMini` (`mad`, `max`, `may`, `meg`; `jen` is a Pi in `Wardrobe`), ordered by `.hosts`, joined as `macmini-<label>`, MACs
  from the same rows. Nothing is typed twice.
- **Calling `asleep` and `awake`.** The guard shuts servers down and wakes them with these two scripts and nothing else, and a host
  is never powered off. Both are **synchronous**: the call blocks until the script has finished and verified its own work, and its
  exit status says how it went, so the guard never polls a host to learn whether it is done. Over ssh the exit status is the
  script's (`0` ok, `1` error, `2` usage, `3` not root, `4` timeout, `5` unclean, `6` unhealthy), the last output line
  `RESULT <command> status=… reason=…` gives the reason, and an ssh status of `255` is a host that could not be reached.
- **Parallel when asked.** The guard's runner takes a list of hosts, a command and whether to run them in parallel. A parallel request
  starts one worker per host, each making its own blocking call, and joins them as they return; a sequential one runs them in order.
  Workers report over a channel, so the guard's own loop keeps polling and deciding while a shed or a wake is running, and a halt
  that falls due before every follower has returned does not wait for them. Each result is a `command` row in the outage CSV (host,
  command, exit status, reason, how long it took) and an entry in the state file. A non-zero result is logged and alerted and never
  retried in a loop.
- **One call per host at a time.** The state file records which host has a call in flight, and the guard never starts `awake` on a
  host whose `asleep` has not returned, so the two cannot race.
- **Every call has a 30 s timeout (decided 2026-10-30)**, as for anything that can reach failing hardware. It is applied to the ssh
  connection and to silence: `ConnectTimeout` of 30 s, and a keepalive window of 30 s (`ServerAliveInterval` times
  `ServerAliveCountMax`), so a dead or hung host frees its worker within 30 s and is recorded as unreachable. It is **not a cap on the
  whole call**: a deep `asleep` can legitimately run for minutes, since each container gets its own stop grace (120 s by default), and
  the script bounds itself and exits `4` on its own timeout. Capping the whole call at 30 s would cut a deep shed short while the host
  carried on, leaving the guard not knowing whether `asleep` had finished.

**Steps (first version, timers and flags only).** The host actions are `asleep` and `awake` from the `system` module (the
next section). A host is never powered off.
1. **Watch.** Polls at the module's rate, 2 s on mains and 1 s on battery. Time on battery accumulates from the first `OB`, so a short blip simply never reaches
   `rackmains_guard_shed_max_seconds`, and resets to zero only after `rackmains_guard_mains_stable_seconds` of continuous `OL`, so a grid that flaps with dips under that apart cannot keep the
   servers up.
2. **Shed.** At `rackmains_guard_shed_max_seconds` on battery, or `LB`: run `asleep --deep` on the followers in parallel, `meg` last so Home
   Assistant and the broker outlast the rest, each over ssh with a key whose `authorized_keys` forces the command (`restrict`,
   no shell; see the forced-command test), each call synchronous, so it is done when the call returns, and `0` means it completed cleanly. Any other code (1 error, 4 timeout,
   5 unclean) is logged and alerted and the guard moves on; it never retries in a loop. On `max`, run `asleep --shallow`
   stopping every container but rackmains (supervisor first, it binds `/`). A shed is not undone by the voltage rebound when
   the load drops, only by `rackmains_guard_mains_stable_seconds` of mains.
3. **Halt.** At `rackmains_guard_halt_max_seconds` on battery, or on `LB`, whether or not every follower has finished (a halt implies a shed,
   so an `LB` runs both at once, with no staging): send `shutdown.return` first, with `ups.delay.shutdown` set to
   `rackmains_guard_halt_delay_seconds` (30 s by default), which the fit sets to cover `max`'s `asleep --deep` plus a margin, then start `asleep --deep` on `max` detached. It stops rackmains and the guard
   with it, so its result is only in `/run/asleep.log` on `max`, and `shutdown.stop` cannot be sent afterwards. The UPS then
   cuts and restores, and every host boots on AC restore (power-on-after-cut test, below).
4. **Mains returns first.** After `rackmains_guard_mains_stable_seconds` of continuous `OL`, run `awake` on `max` to restart what was
   stopped, and on each follower the state file lists once its `asleep` has returned, in the reverse of the shed order: `max`
   first, then `meg`, then the remaining followers in parallel (decided 2026-10-30). Each call is synchronous and its exit status says whether the host came back
   healthy (`6` is a container not running or healthy). `asleep` is undone by `awake`, so unlike
   a `poweroff` there is nothing to wait on being down. If the halt has started there is nothing to cancel.

**Safety rails.** It ships in dry-run, logging the exact commands it would run, and goes live only after the trials ("Trials" in the model plan) show the
conservative timers fit. It honours its hard override (`LB`) in dry-run too. The keys can
power off and nothing else. Any status flag that is not `OL` is surfaced; an alarm or fault flag raises an alert in Home
Assistant.

**Later.** The decision (reading and history in, action out) stays a pure function apart from the state machine and the
runners, so the timer policy is replaceable; if a better policy is ever wanted it is fitted offline like the thresholds ("Thresholds, fitted offline" in the model plan).

**Residual risk.** One USB link is one source of truth. A power cut with a failure of `max`, of Docker or of the guard leaves
the others running until the UPS is flat. A read-only `upsd` on the LAN with a dead-man timer on each follower would cover it
and is left out for now. Root login with a password is enabled on the followers, so the guard's keys are only as safe as that.

**Restart.** Decided: no wake packets and no Wake on LAN. If mains returns before the UPS is flat the guard runs `awake`; if the
UPS cuts, every host boots on AC restore from the state `asleep` left it in. That second path is the one still to prove (the
power-on-after-cut test).

## The host side, the `system` module (built)

`src/all/system` puts `asleep` and `awake` on the four servers; its `CLAUDE.md` is the reference and this is what the guard
needs from it. Hosts are never powered off: a Mac mini restarts after a power cut only from a running state and stays off
after a clean `poweroff`, so the guard quiesces a host and leaves it running.

- **`asleep --deep`** (followers). Stops timers, automounts, containers (each given its own grace period, its exit code
  checked), docker and the services, then unmounts every fstab mount, makes root read only, and flushes and detaches the SATA
  and USB SSDs. Leaves ssh, the network, NUT and the fan control. Never powers off.
- **`asleep --shallow --stop <container>`** (`max`). Leaves docker, root, `/var` and `/home` writable so rackmains keeps
  running and writing to its home dir; stops only the named containers; unmounts what no running container holds.
- **`awake`.** Undoes either from `/run/asleep.state`, then waits up to 60 s for containers that are starting or unhealthy to
  turn healthy. It replaces the wake packet.
- **What the guard reads.** The exit code and the last line, `RESULT <asleep|awake> status=… reason=…`: 0 ok, 1 error, 2 usage,
  3 not root, 4 timeout, 5 unclean (a container was killed), 6 unhealthy (`awake` only). Log lines go to stdout and to
  `/run/asleep.log` or `/run/awake.log`. A non-zero `asleep` leaves the host in whatever state it reached. Both scripts block until done, so
  the call returning is the completion signal and the guard needs no polling or callback.
- **Power on after a cut.** The module's `install_prep.sh` clears `AFTERG3_EN` (bit 0 of the register at `00:1f.0`, offset
  `0xa4`, [the method](https://gist.github.com/coldie/072d8e97dfad89d424ba91641641511d)) on every install; `max`, `may` and
  `meg` (Macmini7,1) read `1c08`. `mad` is a Mac mini M2 Pro under Asahi with no Linux knob on kernel 6.14: the setting lives
  in the SMC and is set once from macOS ([AsahiLinux/docs#156](https://github.com/AsahiLinux/docs/issues/156)), which is
  **yours to do by hand** (test 5 in "Tests still needed" in the model plan). Whether any host boots after a cut is **not yet tested**.
- **Tested on `max`, 2026-10-29.** Argument and precondition codes; dry runs that leave the host unchanged; a real shallow
  cycle with supervisor left running, returning 0 and restoring the host exactly; an unclean cycle (a container that ignores
  SIGTERM) returning 5 with exit code 137 reported; `awake` error paths returning 1 and 6; and a read-only remount round trip
  on every filesystem type in the estate, on all four hosts. **Not yet:** a real deep run, the timeout code end to end, any
  other host, the power-on-after-cut test.

## The model seam, in rackmains

The model, its JSON signature, its training and the plan for fitting it are in the sections from "Design tenets, and the chosen design" in the model plan. What rackmains
must build is the seam: how it builds a request from numbers it already records, carries and persists the model's state, validates and
applies a response, and the default model it ships from day one. Implement the rules in "The model signature, inputs, outputs and thresholds" in the model plan under "How a response is used", and
take the JSON from "The model signature, inputs, outputs and thresholds" in the model plan. The signature is built by the notebook with `build_signature` and is committed as
`src/build/resources/model/default/signature.json`; the default project is there, and the pulled `release` project goes in
`src/build/resources/model/release/`.

**Nothing computed here is a feature.** rackmains sends the poll time, the utilisation, the on-battery flag and the replace flag, exactly
the numbers it records, plus the state the model returned last time. Every feature is inside the model's graph. The row and the outputs
are recorded identically in MQTT, the CSV and the log, and the state is recorded in the CSV and the log at the start and end of an
outage (`rackmains_model_state`, JSON text), so a recorded outage is a complete fold and can be replayed through any project. Text and the timestamp are never sent: the
status becomes the flags and the time becomes `rackmains_clock_epoch_seconds` at source, here, in Rust.

**The Rust seam.** A `model.rs` in the library holds the V2 request and response types and a `Model` trait with one method,
`infer(request) -> response`. `StaticModel` loads the default project (`project.json` of flavor `static`) from the image at start, checks its
hashes and returns its constants for every valid request. A later `EmbeddedModel` loads `model.onnx` with `ort` (pinned exactly, one thread,
loading the shared library taken from the pinned wheel MLServer uses), builds the tensors from the row and the state, runs the step,
merges the constants and returns a V2 response; a later `MlServerModel` posts to the endpoint named in the module's `.env_*` files, a run-dependency connection
setting like the broker's. A fallback wrapper tries the chosen model, then the last valid answer, then the shipped release project, then
the default project. One validator turns a response into a typed `Policy` and the estimates, and the guard sees only those, never JSON, so
replacing the default model with a fitted one changes one constructor and nothing downstream.

**State.** The state in the answer in use is carried to the next call and persisted, with the project hash and model version, in the guard's
state file, **written atomically on every call**, which is how state survives a crash (its format and location are an open decision below). A state from a different project is discarded, and a lost state
restarts the model from its initial state, with the history unknown, which it treats as a partly drained battery. The guard does not read
the state; it is the model's.

**Engine and memory.** Day one embeds only the default (static) project, which needs no engine. The first ONNX project brings `ort`, the
ONNX Runtime shared library for each architecture, taken from the pinned wheel and hash-pinned into the image, and a higher compose
memory limit (measured at 34 MB for the engine on the laptop; about 96 MB suggested in place of 32 MB, to re-measure on Linux).

**Calls.** One every 5 s on battery, at each transition and every 5 minutes on mains. A call never blocks the poll or the guard; a failed
call falls back to the next answer in the order above and is a `note` row.

**Tests.** The validator against a table of good and bad responses; the shipped project loads, validates and matches its hashes; the names
in `signature.json` equal the validator's, checked both ways; the golden sequences replayed through `StaticModel` (and later
`EmbeddedModel`), carrying the state, give exact responses; a **replay test** feeds a recorded outage CSV through the model and requires
every recorded output to be reproduced from the `start` row's state and the final state to equal the `end` row's; a state from another
project is discarded; and a failed call falls back.

**The shipped default model** lives in the image as a project (`project.json` of flavor `static`, with its `signature.json` and `golden.json`), so
changing it is a release and the model the guard falls back to is the one that was reviewed. It is the **default model of day one**
("First pass: a default model, on day one" in the model plan), and it stays in the image as the last-resort floor even after a fitted project
ships. The guard validates it at start, checks its hashes, and **refuses live mode** if it fails; it stays in dry-run and says so.
Dry-run versus live is deployment config in `.env_prod`, never in a model document.

**What is implemented (2026-10-31).** The default project exists and passes every project check of `spec.md` section 10. It is
`src/build/resources/model/default/`: `project.json` (flavor `static`, provenance `manual`, the four constants, the golden data file in
`provenance.inputs`), `signature.json` (the five inputs, twelve outputs and six state slots of the model plan) and `golden.json` (a first
call with no state, a row mid-drain with state, a row with the replace flag raised, and a request with the utilisation missing that
must give a signature error). `src/build/resources/model/release/` is empty until a fitted project is pulled, and `generate.sh` verifies
both slots, pulling the `release` project only on `fab pull` and comparing its signature with the default's. **Not built:** `model.rs`
with `StaticModel`, the validator, the fallback wrapper, copying the slots into the image at `/asystem/etc/model/`, and the guard's
refusal of live mode on a failed validation.

**Starting values, the default model.** Constants only: `rackmains_guard_shed_max_seconds` 120, inside the 145 s already held at service
load with no knee; `rackmains_guard_halt_max_seconds` 450; `rackmains_guard_mains_stable_seconds` 300; and
`rackmains_guard_halt_delay_seconds` 120, a placeholder until `max`'s `asleep --deep` is timed. They shed early on short outages and so
waste battery, but never outrun what is proven. The exact manifest is in "First pass: a default model, on day one" in the model plan. A refit replaces the project, which is a release.

## Deploy and the vernemq release lifecycle

**No `deploy.sh`.** The module has none, and needs none now. It only ever existed in the old design to run that tool opt-in from the Mac.
`fab deploy` runs a module's `deploy.sh` only when the module has one, so it skips rackmains, and a release is the ordinary `fab release`.
That matches `tempstat`, which this module was cloned from and which has none; the root `CLAUDE.md` calls the file an optional operator hook,
not the deployer. Eleven other modules ship one for their own reasons (`media`, `homeassistant`, `tasmota`, `nginx`, `grafana`,
`benchmark`, `appdaemon`, `udmutilities`, `photos`, `kasa`, `storage`); none of them is affected by this module dropping the tool.

**MQTT artefacts do not use `deploy.sh` either.** In the other modules a `deploy.sh` pushes content to a running host without a release:
`grafana` syncs its dashboards, `homeassistant` copies its custom components and packages, `tasmota` runs its config script. MQTT
discovery and schema artefacts follow a different, established pattern, the one `tempstat` and `network` use and rackmains already has:
`fab generate` writes `image/broker.sh` from the workbook rows, the module's `install_pre.sh` runs it when the version changed, and
`install.sh schema broker` republishes without a release (it runs `image/broker.sh publish`). So after the workbook rows are added, a
release publishes them, and a republish between releases is that one command. A `deploy.sh` would only duplicate it.

**The vernemq release lifecycle works for rackmains automatically, with two conditions.** A vernemq release flushes the broker's retained
store in its `install_pre.sh`, then its `install_post.sh` visits every host in its `hosts` file and, on each, runs `install.sh schema
broker` for every installed module that has an executable `image/broker.sh`. There is no list to join: having that file is the
enlistment, and rackmains' `run_deps.txt` already names vernemq. `schema broker` restarts the module's service and then runs
`image/broker.sh publish`, which republishes the discovery topics.
- **Condition 1: the file must exist.** `image/broker.sh` is generated only once the workbook rows exist. Until then the republish
  silently skips rackmains (`[ -x broker.sh ] || continue`), so adding the rows is also what enlists it.
- **Condition 2: rackmains republishes its own retained state.** The flush also drops `rackmains/data` and `rackmains/status`, and the
  mains publish is only every 5 minutes, so the restart that `schema broker` causes must publish `online` and the full current payload
  at once, as the reconnect rule above already says. That is a test to write: a restart, and a plain reconnect, each leave both
  topics retained within one poll.
- **The restart is safe mid-outage by design.** It closes an unfinished outage CSV as `interrupted` and reconciles the guard with its
  state file. A vernemq release during an outage is unlikely anyway, since the broker's host is shed first.

## Code standards and the completion review

Every Rust crate in this module (`rackmains`, `mockdriver`, `tools/schema`, and anything the guard adds) follows
`tempstat` strictly, then Rust best practice, then the global and project guidelines that apply. Where `tempstat` and a
guideline disagree, the guideline wins and the difference is noted here.

**While writing**
- **Match `tempstat`.** Same layout (thin `main.rs` shim, logic in the library), same `Cli` flags and short letters
  (`-P -D -T -B -L`, `--broker-*`), same duration parsing, log format, `log_line` labels, reinit backoff, error enums and
  `Display`, test module shape and naming. A new tool reuses the library's helpers rather than copying them.
- **Rust best practice.** No `unwrap`/`expect` outside tests, errors as typed values carried with `?`, no needless clones or
  allocations, iterators over index loops, `Duration`/`Instant` over raw integers, no shared mutable state a channel or a
  single owner would replace, `clippy` clean with no `allow`, `cargo fmt` using the repo `rustfmt.toml`.
- **No comments** except a clear exception: documenting an interface, or a complicated process whose why is not evident.
  Maintenance notes telling a maintainer what to update by hand stay.
- **Logging and errors.** Interpolated values in square brackets, no `:` or dash separators in a message, INFO for events a
  human watching wants, everything per poll at DEBUG.
- **Ordering.** Exported functions and types first, private helpers, types and constants last.
- **Single-use functions.** A function with one call site is inlined; one used from several places in one function becomes a
  local closure beside its use; a second genuine call site earns a shared function. A pure function with a real input space
  (a parser, an encoder, a comparator) keeps its own definition and table test.
- **Vocabularies.** Words shared across a boundary (NUT status flags, the payload keys, `online`/`offline`) have one owner and
  a mirrored copy with a test that the sets agree; no literal repeated where a named constant exists.
- **Shell and Python** follow the global rules: `shellcheck` clean with bare directives, `ruff format` and `ruff check --fix`,
  pyright only.

**On completion of each piece (a crate, a hook, a tool, the guard) a review pass, written up here**
1. **Correct.** Check all the logic against the design, every branch and every error path, including what happens when a
   dependency (broker, plug, driver socket, a host) is down, slow or answers garbage, and that a host is never left half asleep without the state file and the CSV saying so.
2. **Simplify.** Can it be simpler? Remove dead code and unused constants, fields and parameters; inline single-use
   functions; collapse duplicated branches; drop anything added "for later".
3. **Tests complete.** Every edge case and error path has a test; gaps listed and closed. Tests assert behaviour and
   boundaries (codes, counters, state, parsed values), not log lines or message wording; remove tests that are not valuable
   or that only restate the implementation.
4. **Style in sync with `tempstat`.** Diff the structure, flags, naming, log lines and test shape against `tempstat` and
   reconcile every difference or record why it stays.
5. **Guidelines.** Walk the global and project guidelines (comments, logging format, ordering, single-use functions,
   vocabularies, shell and Python rules, no writes to git, generated files untouched) and fix each deviation.
6. **Reorganise.** Order types, constants and functions as the guidelines say.
7. **Gates.** `cargo fmt --check`, `clippy` with warnings denied, the targeted tests, `shellcheck`, `ruff`, pyright, and a
   `fab generate` whose diff is read.

The first review (step 1 of the remaining phases) is owed now on what exists: `rackmains`, `mockdriver` and `tools/schema` (no
end-to-end test yet, a few long lines and an inline `json!` shape to tidy), and the two install hooks with their unit tests.

**Final review stage (the whole module, before the first release)**

Run it once the publisher, the outage CSV, the model seam and the guard are all built, so the module is reviewed as a whole and not
piece by piece, and **repeat it for anything that changes afterwards**. The aim beyond correctness is a **reference project**: the
module a reader copies to learn how a Rust service here is laid out, tested and logged. It is the last gate before the release in
step 6, and it supersedes the per-piece passes above where they disagree.

**Scope.** Everything the module owns:
- the Rust workspace (`rackmains` library with its `broker`, `nut`, `schema`, `mock` modules and everything added since: the outage
  CSV writer, the model seam, the heartbeat, the guard and its ssh runners), `mockdriver`, and `tools/schema`;
- the hooks (`install_prep.sh`, `install_pre.sh`), the image scripts (`checkhealthy.sh` and the generated ones it uses), `backup.sh`,
  `generate.py`, the Dockerfile, the compose file and the `.env_*` files;
- the tests (the Rust unit tests, `src/test/python/unit`, the system test) and the module `CLAUDE.md`.

**The review, in this order**
1. **Read the whole module once, in dependency order, before changing anything**, and write each finding in the table below as it is
   found. Fix them after the read, not during, so the findings are judged against the whole.
2. **Correctness: check all the logic.** Every branch and every error path, against the design in this plan, asking of each what
   the code does when its own assumption is false. In particular:
   - each dependency failing: the broker down at start and mid-run, the driver socket missing, stale or answering garbage, the data
     dir full or detaching, a host unreachable or hung, mlserver absent, a malformed response;
   - concurrency: every thread and channel, bounded queues, no blocking of the poll loop, shutdown and signal handling, no shared
     mutable state that ownership or a channel would replace;
   - time: monotonic clocks for durations, the wall clock only for stamps, and a stepped or wrong clock;
   - numbers: parsing, overflow, the whole-number rounding, and the one formatter shared by the payload and the CSV;
   - files: write, fsync, rename, directory fsync in that order, recovery of an unfinished file, the bound on file count, and that
     the prune never removes the current file;
   - restart: mid-outage and mid-sequence, every guard action idempotent, and the shipped default project always valid.
3. **Failure injection: exercise the failures, do not only read them.** Against the built image with the mock driver: `kill -9` the
   process in the middle of a CSV write; stop the container in the middle of an outage and check the stop path (the final CSV row is
   written and fsynced, `offline` is published, all inside Docker's stop grace); start with the broker down, and lose it mid-drain;
   make the data dir read-only or full; present a stale, a garbage and a vanished driver socket; flap the mains with dips shorter and
   longer than the stable period; run a long drain to the low-battery flag; return a model response that is invalid, absent or slow;
   hang a host. Each scenario has the outcome this plan states, an automated test where one is practical, and otherwise a recorded
   manual run.
4. **Security and safety.** Only `DUMPALL` is ever written to the driver socket; the ssh keys are forced-command and restricted with
   the host key pinned, and a host name is never interpolated into a shell string; untrusted input is parsed defensively (driver
   lines, the MQTT command payload, a model response, ssh output) and CSV text is quoted so a value cannot forge a row; no panic is
   reachable from outside input; secrets never reach a log or the repo (variables named with `TOKEN`, `KEY`, `PASSWORD` or `SECRET` so
   a release masks them, and the generated `.env` ignored by git, checked with `git check-ignore`); the container runs with the least
   it needs (`/run/nut` read-only, only the data dir writable) and the CSV and state files have deliberate modes.
5. **Resources.** The module stays inside its compose memory limit (32 MB today, raised when the ONNX Runtime library is embedded) through the longest outage the CSV bound allows, measured as
   resident memory over a long mock drain. Nothing grows without bound: queues, in-memory rows, threads, file descriptors. CPU at the
   1 s battery poll is negligible. Disk writes are measured, the CSV rewrite of up to 1 MB every 5 s and the per-poll heartbeat, and
   either judged acceptable for the SSD or reduced. DEBUG log volume fits the 5 x 100 MB rotation.
6. **Can it be simpler?** Fewer types, flags, environment variables and dependencies; single-use functions inlined; duplicated
   branches collapsed; nothing added "for later". Find **dead code** by removing a suspect and building (cargo does not flag unused
   public items in a library). `mockdriver` ships in the image, so it either earns its place or is trimmed.
7. **Style matches `tempstat`, and Rust best practice is observed.** Diff the layout, `Cli` flags, naming, error enums and `Display`,
   log format and labels, reinit backoff and test module shape against `tempstat`; reconcile every difference or record here why it
   stays, and whether `tempstat` should adopt rackmains' improvement (not done in this module). Rust: no `unwrap` or `expect` outside
   tests, no swallowed errors (`let _ =` on a `Result`), typed errors carried with `?`, no needless clones or allocations, iterators
   over index loops, `Duration` and `Instant` over raw integers, borrowing over owning, a small public surface with `pub(crate)`
   where it is enough, `clippy` clean as the build runs it (pedantic, warnings denied, the short `-A` list in `fabfile.py`, never an
   `#[allow]` in source) and `cargo fmt` with the repo `rustfmt.toml`. **Dependencies:** each is justified, its features minimal as
   in `tempstat`, none duplicated, versions and toolchain pinned, and `Cargo.lock` unchanged by the review except deliberately.
8. **Project guidelines, rule by rule.** Logging and errors (values in square brackets, no `:` or dash separators in a message,
   short static tags); single-use functions; shared vocabularies with one owner and a mirrored copy with a test that the sets agree;
   no message-text tests; no test names in documents; no padded numbers in brackets; private items last; shellcheck with bare
   directives; Python through `ruff` and pyright only, with no IDE directives; generated files untouched; the workbook never edited
   by code; nothing written to git.
9. **Names and vocabularies, mechanically.** Every metric name and every UPS status token has one owning place and agrees across
   the code, the payload, the CSV header, the workbook rows, the model signature and the log lines, checked by a test where one exists
   and otherwise by a search for every name. Plant one deliberate mismatch to prove the check bites, then remove it.
10. **No comments**, except documenting an interface or a complicated process whose why is not evident, and the maintenance notes
    that tell a maintainer what to update by hand. No commented-out code, no `TODO` or `FIXME`, no section-divider comments,
    nothing that restates the code. Doc comments only on the library's public interface, and only where the name cannot say it.
11. **Tests, and whether they bite.** List the gaps (an untested branch, error path or boundary) and close them. **Remove tests that
    are not valuable**: any that assert a log line or message wording, restate the implementation, exercise only a mock the test
    itself wrote, or duplicate another. A helper extracted only so a test could reach it is inlined and tested at its caller's
    boundary, unless it is a pure function with a real input space. Then **plant a deliberate fault** in each rule that matters (a
    flag mapping, the write-rename order, the prune bound, a threshold comparison, the response validator) and confirm a test fails;
    a test that stays green is not protecting anything. Measure coverage where tooling exists, otherwise map every branch to a test
    by hand. The system test covers the MQTT signature end to end.
12. **Reorganise** structs, constants, variables and functions as the guidelines say: public and primary first, private helpers,
    types and constants last, in the same order in every file, related items together, the `impl` after its type, and the module
    list in `lib.rs` in the same order as the files are read.
13. **Operability and documentation.** Each log line says what happened, at the right level, and where it matters what to do; start
    and stop are logged; the health check means one thing; an operator can find, read and back up the CSV from what is written. Every
    claim in the module `CLAUDE.md`, in the model sections of this plan (names, columns, the signature) and in its descriptions of
    behaviour is true of the code. Each hook is idempotent: run twice it leaves the host unchanged, and it never fails an install it
    should not.
14. **Build and package.** `fab build`, then `fab package`, then run the image with the mock driver and the system test. The generated
    files (`broker.sh`, the schema, `.env`, `docker_deps.sh`) regenerate **byte-identical** after a pure refactor, and any other diff
    is explained.
15. **Gates.** `cargo fmt --check`, `clippy` as the build runs it, the module's tests (`fab unittest`, then `fab systest`), `shellcheck`
    on every script, `ruff format`, `ruff check` and pyright on every Python file, and a `fab generate` whose diff is read. The build
    rewrites source when it lints, so the diff is read after every run.
16. **Write up the findings** in the table below with a severity, fix or accept each with a reason, review the fixes by their diff,
    and re-run the gates.

**Process rules.** Judge the module against this checklist, not against taste: each finding cites the rule it breaks. Classify each
as a **blocker** (wrong or unsafe), a **should-fix** (against a guideline, or a clear simplification) or a **nit**. Nothing classed
blocker or should-fix is deferred without a reason recorded. A second reader reviews what the first changed, so nobody signs off
their own fixes: a human, or an automated high-effort review (the `code-review` and `simplify` skills may be used for it). Record the
version reviewed (`SERVICE_VERSION_ABSOLUTE`) beside the table, so a later change is known to come after it.

**Exit criteria.** No blocker or should-fix is open; every other finding is fixed or accepted with a reason; the gates are green; a
fresh diff of the module against `tempstat` shows only intended differences; the module `CLAUDE.md` matches the code; and nobody
reading the module would need this plan to understand it.

Version reviewed: none yet, the final review has not run.

| # | Finding | Where | Rule broken | Kind | Severity | Outcome |
|---|---|---|---|---|---|---|
| | none yet | | | correctness, safety, resources, simplification, style, guideline, name, comment, test, order or docs | blocker, should-fix or nit | fixed, or accepted with the reason |

## Gaps found in review, 2026-10-28

| # | Gap | Closed by |
|---|---|---|
| 1 | `awake` must not race a running `asleep` | the restore runs `awake` only once each host's `asleep` has returned (exit code and `RESULT` line), and a non-zero `asleep` is surfaced |
| 2 | the recorder's 2 s data and independent check go | kept until after trial 1 (decided); superseded 2026-10-30: poll 2 s on mains and 1 s on battery, publish every poll on battery and every 5 minutes on mains, and the outage CSV records every 5 s on battery |
| 3 | the dry-run release is invisible in Home Assistant | every candidate metric gets a workbook row (decided) |
| 4 | ssh key provisioning is unplanned | a step: forced-command key on all four hosts including `max`, private key mounted read-only from a root-only directory on `max`, `known_hosts` pinned; yours to install, the forced-command test (3) proves it |
| 5 | rollout A protects nothing | stated: the rack is exactly as exposed as it is today until rollout B ("Setting the thresholds, in rollout steps" in the model plan) is live |

## Remaining phases

Decided 2026-10-28: rollout A starts inside the proven 145 s (`rackmains_guard_shed_max_seconds` 120, `rackmains_guard_halt_max_seconds` from the measured shed
times); trial 5 goes to the voltage floor once; the trials are cut at the plug by hand; and there is **one
first release carrying the publisher and the guard in dry-run**, not a publisher alone.

1. **Run the review above** on `rackmains`, `mockdriver`, `tools/schema` and the
   hooks.
2. **Metrics and the outage CSV** (decided 2026-10-30): the `nut.rs` flag function and `SAMPLES` with the canonical names, the flat
   MQTT payload and the poll and publish cadence, the outage CSV writer and its backup enrolment (`backup.sh`,
   `write_container_backup()`, the `.env_all` keep values), the workbook rows (yours), the heartbeat file and an MQTT-independent
   `checkhealthy.sh`, the model seam with the default model project ("First pass: a default model, on day one" in the model plan, whose project is built; the Rust loader is not), the module
   `CLAUDE.md` update; then the review above.
3. **Run the forced-command test and the `asleep` timing** (yours, on the hosts, tests 3 and 4 in "Tests still needed" in the model plan), recording each result there; they
   fix `rackmains_guard_halt_max_seconds`.
4. **Build the guard, dry-run only**: restructure `run` so the poll, the CSV writer and the guard start before, and never wait on, the broker connect, generate the host file
   and the default model project, the model seam, config and state, the ssh runners for `asleep` and `awake`, the state machine with mock sequences, the heartbeat in the
   health check; then review it as above.
5. **Final review of the whole module** (see "Final review stage" above): the full pass (correctness, failure injection, safety,
   resources, simplification, `tempstat` style, guidelines, names, comments, tests, ordering, operability and packaging) over everything built, with the findings table filled in and the gates green. The release in step 6
   waits for it.
6. **Add the workbook rows (yours), release publisher and guard in dry-run** and confirm `rackmains/status` is `online`, the
   entities appear, and a short cut at the plug turns `rackmains_ups_on_battery` on within one poll and back off when mains returns.
7. **Trial 1, then drop the recorder** (the publisher must have agreed with it through the long cut), **then the restart tests
   (5 and 6), then trials 2 to 4 live** (see "Trials" in the model plan), recording each result there.
8. **Trial 5 once per battery** ("Trials" in the model plan), fit the model's outputs offline (a new project, later the model), release the measured thresholds.

## Open decisions

- **Poll and publish cadence.** Proposed: poll 2 s on mains and 1 s on battery; publish every 5 minutes on mains and at once on a
  change, and every poll on battery; one CSV row every 5 s on battery. Health no longer depends on the publish interval, so the 5 minutes only sets how stale a Home Assistant value can look. The model is called every 5 s on battery, at transitions and every
  5 minutes on mains.
- **Outage CSV numbers.** 5 s between rows, the 100 file bound and the 1 MB cap are my proposals. The file is a whole-document
  rewrite for each write, as asked, which is cheap at these sizes; an append-only file with an fsync per line would be tail-friendly,
  but it is not what was asked for, and it can leave a torn last line after a power cut.
- **The guard's state file.** It is referenced throughout and not yet defined. It must hold the heartbeat, the guard's clocks, which hosts are
  shed and which calls are in flight, and the model's state with the project hash and version it came from. Written like the CSV (a
  temporary file, fsync, rename), on every call, not backed up. The format, location and versioning remain to be decided.
- **Call timeout.** Decided as 30 s and recorded as an ssh connect and silence timeout, not a cap on the whole call (see "Calling
  `asleep` and `awake`"). Confirm that reading: if a 30 s cap on the whole call was meant, a deep shed would be cut short. No deep
  run has been timed yet, so the whole-call length is still unmeasured (test 4 in "Tests still needed" in the model plan).
- **Switch or binary sensor.** `rackmains_ups_on_battery` is a read-only `binary_sensor`; revisit if a command is ever wired.
- **Who sends the final UPS command**, the guard (read-write socket) or the host.
- **Restart shape.** Decided: `awake` when mains returns early, `AFTERG3_EN` after a cut; the power-on-after-cut test (5)
  confirms it per host.

## Designs considered and left out

- **Reading the HID interface natively, or a second NUT driver (`usbhid-ups`).** Dropped; see the HID verdict in the unit section.
- **A direct InfluxDB writer in `network`'s pattern.** Designed and dropped 2026-10-30: Home Assistant already records every
  published entity, and the outage CSV is the complete record when the broker and database are shed. A writer would add a client, a
  token, a run dependency and a schema half for data Home Assistant already holds.
- **Publishing from `upsmon`'s `NOTIFYCMD`.** Needs `upsmon` and a host hook, and only reports changes.
- **Reading `upsd` over the network** (host network, a bridge listener, or the LAN). The socket needs no host change and no
  listener; the cost accepted is that it also accepts UPS commands, hence the `DUMPALL`-only rule.
- **Running NUT inside the container with the USB device mapped in.** Ties the shutdown path to Docker being up.
- **A Go client with `go.nut` or a Rust one with `rups`.** They speak `upsd`'s protocol, which this module does not use.
- **Shutdown led by supervisor.** It has ssh, host lists and a plug, but a guard there needs a plugin, its own leader election
  independent of the broker (an unreachable broker at start makes it exit and restart), safety-critical code in a binary
  that releases often on every host, and two owners of the UPS.
- **A second service or a separate module for the guard.** Needs a health check and restart handling the tooling does not
  generate, or a copied crate. A thread in the one container was chosen; the guard code is the same in each placement, so a
  later move is a repackaging.
- **Shutdown by host `upsmon` and `upssched`.** The fewest parts and it survives Docker being down, but it cannot stage or
  restore. It is the fallback if staging proves unnecessary.
- **A guard sharing the publisher's broker loop.** A broker outage would stop it.
- **Followers deciding for themselves from a LAN-readable `upsd`.** Resilient to `max` failing, but it spreads UPS logic across
  hosts, exposes `upsd`, and cannot keep `max` last.

- **Powering hosts off (`systemctl poweroff`).** A Mac mini that is shut down stays off when power returns; it restarts after a
  cut only from a running state. Replaced by `asleep`, which quiesces a host and leaves it running.
- **Wake on LAN.** Needed only to restart hosts that `poweroff` had left off, and it wants the container on the host network. Dropped
  without testing (`mad` also reports `Wake-on: d`).
- **A smart plug per host** (new hardware) to restart hosts.

sed: 1: "1i\\
": extra characters after \ at the end of i command

## Deleting this plan

This plan can be deleted once the publisher, the outage CSV, the health check and the guard are implemented and released. Before
deleting, check:
1. **The module `CLAUDE.md` matches the code.** Today it is accurate for the built publisher. When the metrics work lands, update its
   payload, health check and "Home Assistant tests for the `OB` token" lines, and replace "MQTT only" with MQTT plus the outage CSV
   (there is still no database and no InfluxDB writer). Point future modelling work at the model plan.
2. **Nothing open is lost.** Every open decision here is either settled in the code or `CLAUDE.md`, or copied into the model plan.
3. **The final review has run.** Its findings table is empty or every row is fixed or accepted with a reason, and the gates are green.
4. **the model plan has what it needs.** It outlives this plan, so its references back to the unit, the metric names and the outage CSV
   are replaced by that content, or by `CLAUDE.md`, before this file goes.
