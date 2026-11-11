# rackmains

**Status, 2026-11-11.**

| Part | State |
|---|---|
| Publisher (`rackmains/{data,status}`, mock driver, mock-backed system test) | built and tested locally, not released |
| Host setup (`install_prep.sh`, `install_pre.sh`) | built, unit tested |
| Host side of the shed (`asleep`, `awake`, power-on-after-cut setting, in the `system` module) | built, tested on `max`; a deep run and the power-on-after-cut test are not done |
| Battery model (`ups/battery` notebook, `static` project `rackmains_ups_battery`) | built, released, embedded, `policy.rs` built; the halt thresholds were removed before release; the guard's validation at start is not built |
| Metrics, outage CSV, heartbeat health that does not need MQTT | designed, not built |
| Guard (shed, restore, state machine, `guard_state.json`) | designed, not built |
| `guard_auto`, `rackmains guard drill`, the root CLI and `check` | designed, not built |
| Workbook rows | yours: 27 metric rows and `service_rackmains` |
| Release | not done; the first release is the publisher and the guard in dry-run |

**Decided 2026-11-11, not built: no final UPS command, run to failure.** The guard sheds the followers and then does nothing more. `max` stays up in
`asleep --shallow` with rackmains and the guard recording until the UPS cuts its own output at its low-battery cutoff, and every host boots on AC restore. There is no
`shutdown.return`, no `ups.delay.shutdown`, no halt step, no `asleep --deep` on `max`, and no host helper or socket write: nothing in this module ever writes anything but
`DUMPALL`. This removes a state, two thresholds and an open decision. The cost, accepted: the battery runs to its cutoff on every outage long enough to shed, and
`max` is cut while running. The one fact it rests on, that the PSDR800 restores its output by itself after a depletion cutoff, is not in the manual and is observed in trial 5
("Residual risk").

**Decided 2026-10-30, not built.** Every metric is published on MQTT for Home Assistant and, during a battery drain, also written to a
CSV in the home dir; there is no InfluxDB writer. Polling speeds up on battery and publishing is rare on mains, and health no longer
depends on MQTT (see "Metrics, MQTT and the outage CSV"). The module `CLAUDE.md`'s payload and health descriptions change when that
is built.

This file holds the status, what the code cannot say, the review and phases, and the open decisions for the service; the code and
the module `CLAUDE.md` say how the publisher works. Fitting the battery model and tuning the guard's thresholds are the Intent and Future of the `ups/battery` notebook title cell in `mlmodels`, which refers back here for the unit, the metrics and the guard.
The trials and tests that supply the data are in "Trials, tests and rollout".

---

## Goal and shape

1. **Publish** the rack UPS's mains and battery state to Home Assistant over MQTT, so an outage or a failing battery is
   visible and automatable there. Built.
2. **Guard** the rack: on a power cut, shed the other servers early, and bring them back if mains returns. `max` keeps
   running to the end and the UPS runs to failure. Designed; a thread inside this container.

**Simple and consistent.** rackmains only ever produces data. Nothing in the running service measures, fits or learns the
battery. Thresholds are outputs of a model that is fitted offline (the Intent of the `ups/battery` notebook title cell); until a fitted model exists the constants project (flavour `static`) is the released model, and changing it is a release.

**Out of scope, deliberately**

- **No InfluxDB writer** (decided 2026-10-30, after a brief reversal the same day). Home Assistant records every published entity,
  and during an outage the CSV files hold the complete record.
- **No supervisor integration.** The guard lives here, so supervisor needs no UPS plugin. Two passive links: supervisor's
  generated config for `macmini-max` picks up the `rackmains` container on its next generate (which also gives Home Assistant its
  `Service Rackmains` switch, from the container's health check), and a host the guard sheds has its supervisor publish
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
`shutdown.*` and `driver.killpower`, and `:ro` does not stop them, so nothing in the module ever writes anything but `DUMPALL`.

The 2 s `ups-recorder` validation unit was stopped and its script deleted on 2026-11-11, before trial 1. The raw recording it made from 2026-10-28, `/var/tmp/ups_status.jsonl` on `max`, is the only record of the outages behind the numbers in this plan; the published entities in Home Assistant's history and the outage CSV files replace it from now on.

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
silent failure (the outlets are unprotected) and alerts at once; a test flag is ignored because the shed waits `guard_shed_max_seconds`. The beeper is audible only,
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
| `LB` | untested | never raised in 145 s; only a run to failure will show if and how long before the cutoff, and whether output restores on its own when mains returns (trial 5) |

**HID metrics and `usbhid-ups`: dropped (decided 2026-10-28).** Nothing from the HID interface is collected, published or used.
The unit's own capacity and runtime are model outputs that lag; its `Discharging` and `ACPresent` flags lead NUT's `OB` by about
4 s on a long cut, which the first action at 120 s does not need, duplicate `OB`, and missed the 1 s blip that NUT caught; its
alarm flags (`NeedReplacement`, `BelowRemainingCapacityLimit`, `ShutdownImminent`, `InternalFailure`, `Overload`) never raised
and stay unknown; and reading any of it needs a second reader of the chip. `usbhid-ups` has no subdriver for the ID and leaves
interface 1 detached when it exits (fix: `echo 1-7:1.1 > /sys/bus/usb/drivers/usbhid/bind`). The per-subdriver results, every
dynamic HID field, the raw descriptor and a field snapshot stay as reference only in `src/build/resources/doc/usbhid_ups_reference.md`,
`hid_report_descriptor.hex` and `hid_fields_snapshot.txt`; nothing in the code or the workbook refers to them. The `hid.*` fields the
earlier recorder logged are not carried into any later logger.

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
| `clock` | the poll time as a number | `clock_epoch_seconds` |
| `mains` | the supply at the UPS input | `rackmains_mains_input_volts`, `rackmains_mains_input_fault_volts` |
| `output` | what the UPS delivers to the rack | `rackmains_output_volts`, `rackmains_output_hertz`, `output_utilisation_pct` |
| `battery` | the battery | `rackmains_battery_volts`, `rackmains_battery_charge_pct`, `rackmains_battery_charging`, `rackmains_battery_low`, `battery_replace`, `battery_remaining_pct`, `battery_remaining_seconds` |
| `ups` | the unit's own state | `rackmains_ups_status`, `ups_on_battery`, `rackmains_ups_problem`, `rackmains_ups_calibrating`, `rackmains_ups_boost`, `rackmains_ups_trim` |
| `guard` | the shutdown guard | `guard_state`, `guard_live`, `guard_auto`, `guard_auto_expires`, `guard_mains_seconds`, `guard_battery_seconds` |
| `model` | the fitted model's own outputs and state | `model_energy_used_wh`, `model_history_known`, `model_recalibrate`, `model_state` |

Bools are the integers `1` and `0`, never JSON `true` and `false`, in the payload and the CSV alike. `_pct` and `_seconds` values are
integers too (NUT reports `ups.load` and `battery.charge` as whole numbers), and `_volts`, `_hertz` and `clock_epoch_seconds` are floats, and `model_state` is text holding a JSON object of the model's
state slots by name, recorded in the CSV and the log only. The envelope is not a metric and has no prefix: MQTT `timestamp` and `period_ms`;
CSV `timestamp`, `elapsed_seconds`, `event` and `detail`. A key is absent from the payload when its variable is unreported, and its
CSV cell is blank. `ups.load` is published as *utilisation* so it is never mistaken for the watts of Powercalc's `Home Load`.

```json
{
  "timestamp": "2026-10-30T12:00:00+08:00",
  "period_ms": 2000,
  "clock_epoch_seconds": 1793332800.0,
  "rackmains_mains_input_volts": 241.4,
  "rackmains_mains_input_fault_volts": 241.4,
  "rackmains_output_volts": 241.4,
  "rackmains_output_hertz": 50.1,
  "output_utilisation_pct": 13,
  "rackmains_battery_volts": 13.4,
  "rackmains_battery_charge_pct": 100,
  "rackmains_battery_charging": 0,
  "rackmains_battery_low": 0,
  "battery_replace": 0,
  "rackmains_ups_status": "OL",
  "ups_on_battery": 0,
  "rackmains_ups_problem": 0,
  "rackmains_ups_calibrating": 0,
  "rackmains_ups_boost": 0,
  "rackmains_ups_trim": 0
}
```

The `guard_*` keys join it, in the same position, when the guard exists, and the model's keys (`battery_remaining_*`
and the `model_*` ones) when a fitted model returns them; the default model returns none of them. The payload no longer has a `samples` object or the old `rack_*_<unit>` keys. The code, `schema.rs`, `system_test.py`, the health check
and the workbook templates all move to these names when built.

**Cadence (proposed).**
- **On mains.** Poll the NUT socket every 2 s, so a status flip is seen. Publish every 5 minutes (retained) and at once on any change
  of `rackmains_ups_status` or a derived flag, so the start and end of a dip reach Home Assistant within about 2 s. Nothing is written to a file.
- **On battery**, from the first `ups_on_battery` until `guard_mains_stable_seconds` of unbroken `OL`. Poll every 1 s, publish every poll, and
  write one CSV row every 5 s and on every event. The driver itself refreshes values only every `pollfreq` (4 s on `max`), so a
  faster poll repeats values and the gain is bounded; lowering `pollfreq` is a host-config change left until trial data shows it is
  needed.
- **The model.** One call every 5 s on battery (the cadence of a CSV row), at each transition between mains and battery, and every 5
  minutes on mains; embedded and served alike. The row sent is the poll time, the utilisation and the on-battery and replace flags, with
  the state the model returned last time. The numbers are recorded with the call, so a recording replays exactly.

**All metrics: MQTT, CSV and log**

| Name | Source | MQTT | CSV | Log |
|---|---|---|---|---|
| `clock_epoch_seconds` | the poll time as seconds since the epoch, converted at source from `timestamp` | yes | yes | DEBUG per poll |
| `rackmains_mains_input_volts` | `input.voltage` | yes | yes | DEBUG per poll |
| `rackmains_mains_input_fault_volts` | `input.voltage.fault` | yes | yes | DEBUG per poll |
| `rackmains_output_volts` | `output.voltage` | yes | yes | DEBUG per poll |
| `rackmains_output_hertz` | `output.frequency` | yes | yes | DEBUG per poll |
| `output_utilisation_pct` | `ups.load` | yes | yes | DEBUG per poll; derived in `end`: peak and mean while on battery |
| `rackmains_battery_volts` | `battery.voltage` | yes | yes | DEBUG per poll; derived in the CSV `end` row: minimum and when, the sag at transfer, the last value |
| `rackmains_battery_charge_pct` | `battery.charge` | yes | yes | DEBUG per poll; derived in `end`: charge at start and end |
| `rackmains_battery_charging` | `CHRG` | yes | yes | DEBUG on change |
| `rackmains_battery_low` | `LB` | yes | yes | INFO on change, with the seconds since `OB` and the voltage |
| `battery_replace` | `RB` | yes | yes | INFO on change |
| `battery_remaining_pct` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call, beside what actually happened |
| `battery_remaining_seconds` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call; INFO when it falls to a lead threshold |
| `rackmains_ups_status` | `ups.status` flags, text | yes | yes | INFO on every change: the flags before and after, with the derived bools |
| `ups_on_battery` | `OB` and not `CAL` | yes | yes | INFO on change; starts and ends the outage CSV; derived: time on battery |
| `rackmains_ups_problem` | `OFF` `OVER` `BYPASS` `FSD` `ALARM` | yes | yes | INFO on change |
| `rackmains_ups_calibrating` | `CAL` | yes | yes | INFO on change |
| `rackmains_ups_boost` | `BOOST` | yes | yes | DEBUG on change |
| `rackmains_ups_trim` | `TRIM` | yes | yes | DEBUG on change |
| `guard_state` | the guard, text | yes | yes | INFO on every transition, with the inputs and the threshold compared (a `decision` row); derived: seconds to each step |
| `guard_live` | the guard | yes | yes | in the `start` row's detail; in dry-run every command is logged as would-run |
| `guard_mains_seconds` | the guard | yes | yes | `note` rows counting down to `guard_mains_stable_seconds` |
| `guard_battery_seconds` | the guard | yes | yes | on every `decision` row |
| `guard_auto` | `auto.json`, read by the guard and mirrored by the publisher | yes, `1` armed and `0` paused | yes | INFO on change, with `set_by` and the deadline |
| `guard_auto_expires` | `auto.json` | yes, ISO text, absent when armed | yes | in the same line |
| `model_energy_used_wh` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call |
| `model_history_known` | the model, an optional output | yes, once a fitted model returns it | yes | INFO on change |
| `model_recalibrate` | the model, an optional output | yes, once the model returns it | yes | WARN on a change to 1, with the reason from the response `parameters` |
| `model_state` | the model's state as one JSON text of the named state slots | no, not published | yes, on the `start` and `end` rows and on a restart, reset or project change, blank otherwise | INFO on those rows; DEBUG on every call when the debug switch is on |
| `timestamp`, `period_ms` | the poll | yes | `timestamp`, `elapsed_seconds` | DEBUG per poll |
| events: transitions, decisions, commands, notes, summary | rackmains, the guard | **never** | yes, the `event` and `detail` columns | INFO. Command timings and host results (`asleep`, `awake`: start, `RESULT` status, `took`) live only here and in the CSV. The `end` row holds the summary: duration on battery, minimum voltage and when, peak utilisation, whether `LB` raised, steps reached, hosts shed |
| service health, the `Service Rackmains` switch | the container's health check, from a heartbeat file and independent of MQTT | none from rackmains, supervisor publishes it | no | none here, supervisor logs it |
| outage count | dropped | no | no | the `end` row's duration for that outage; a count is a query over `ups_on_battery` |
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
  and, once the guard exists, that the guard's own `guard_heartbeat` is too. It no longer runs `mosquitto_sub` or `jq`,
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
| `OL` | `ups_on_battery` 0 | no |
| `OB` | `ups_on_battery` 1, unless `CAL` is present | INFO on change |
| `LB` | `rackmains_battery_low` | INFO on change |
| `RB` | `battery_replace` | INFO on change |
| `OFF`, `OVER`, `BYPASS`, `FSD`, `ALARM` | `rackmains_ups_problem` | INFO on change |
| `CAL` | `rackmains_ups_calibrating`, and suppresses `ups_on_battery` so a deliberate calibration is not an outage | INFO on change |
| `CHRG` | `rackmains_battery_charging` | DEBUG on change |
| `BOOST`, `TRIM` | `rackmains_ups_boost`, `rackmains_ups_trim` | DEBUG on change |
| `DISCHRG`, `HB` | nothing | DEBUG |
| any other token | nothing | WARN once per new token |

Decisions behind it (2026-10-30). `ups_on_battery` and `rackmains_ups_problem` are separate so each entity means one thing and `BYPASS` never
reads as a power cut. `CAL` suppresses `ups_on_battery` so a calibration does not add an outage or start the guard's time-on-battery
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
- **Name and span.** `rackmains_outage_<portable timestamp of the first OB>.csv`. An outage starts at the first `ups_on_battery` and
  ends after `guard_mains_stable_seconds` of unbroken `OL`, the guard's own clock, so dips closer together than that are one file.
- **Columns.** `timestamp`, `elapsed_seconds`, `event`, `detail`, then every metric above in table order, headed by its canonical
  name. Every row repeats the last known value of every metric, so a row stands alone and a blank cell means never reported. `event`
  is empty on a plain sample and otherwise one of `start`, `status`, `decision`, `command`, `note`, `end`; `detail` is free text,
  quoted as RFC 4180, on one line. `start` carries the version, the model version and whether the guard is dry-run or
  live. A row is written every 5 s on battery, on every change of status or flag, and for each guard decision, command and note. A row with no
  event, or a `start` or `status` event, is also **one model call**: its numbers are the request and the outputs are in the row. The state
  is recorded as `model_state` only on the `start` row (the state in), the `end` row (the state out) and on a restart, reset or
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
  - **Text.** `rackmains_ups_status` and `guard_state` are not numeric, so Home Assistant stores them as a text `state` only.
    The CSV writes the same string, on one line, quoted.
  - **Gaps.** An absent key leaves Home Assistant on its last state, so each CSV row repeats the last known value and a blank cell
    means never reported. Home Assistant drops `unavailable` and `unknown` states and writes only on change, while the CSV writes a
    row every 5 s on battery whatever the broker is doing, so the CSV is the complete series and the InfluxDB data is a subset of it;
    forward-fill the InfluxDB side to compare. Timestamps differ by the publish and receive delay: the CSV time is the poll, the
    InfluxDB time is when Home Assistant fired the event.
- **Safe write.** The whole file is rebuilt from the in-memory rows, written to `<name>.tmp` in the same directory, fsynced, renamed
  over the final name, and the directory fsynced, so the file on disk is always the whole previous version or the whole new one,
  never torn. A write happens at most every 5 s, except that an event row writes at once. A run to failure therefore loses at most the rows since the last rename.
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
- **Bounded.** The newest 100 files are kept (`RACKMAINS_OUTAGE_LOG_KEEP`, a module setting so it carries the module prefix), a sidecar `.plug.csv` going with its CSV, pruned only after a new file has been renamed into place and never
  the current or newest one; pruning is safe because the backup below is additive. The `outage/` directory is created at start, since
  the backup's include list fails on an absent directory.
- **Backed up, as the other modules are.** rackmains enrols with `write_container_backup()` and a `src/build/resources/backup.sh`
  whose include list is `outage` and whose excludes are `*.tmp`, the guard state file, `auto.json` and `drill.json` (a restore must never bring back a stale pause). Supervisor's policy then applies:
  primary under `/home/asystem/rackmains/backup/<run>/`, secondary GFS, tertiary mirror, and each release backs rackmains up first
  and abandons the install if that fails. Add `RACKMAINS_BACKUP_KEEP_{DAILY,WEEKLY,MONTHLY}` to `.env_all`; the files are small,
  so keep monthly points for a long time.
- **Following it.** The file is replaced, not appended, so `tail -F` on its path re-reads the whole file at every replace. Live
  follow is `docker logs -f rackmains`, which carries the same events at INFO; the file is what is left afterwards, read with `cat`,
  a spreadsheet or pandas. It is the failure record for real outages and for by-hand test cuts alike.
- **Tests.** A failed rename leaves the previous file intact; a failed write does not block the poll thread and the next write holds
  every row; recovery marks an unfinished file `interrupted` and deletes a stray `.tmp`; the prune keeps the newest and never the
  current file; the header equals the canonical names the payload
  declares, checked both ways; a table test deriving the `end` summary from a sequence of statuses and samples; and the process polls, writes the CSV and stays
  healthy with the broker unreachable, including at start.

**Short outages (decided 2026-10-28, revised 2026-10-30).** A one-second cut at 18:05:25 showed as `OB DISCHRG` in one 2 s recorder
sample and was gone by the next, so a slow poll would usually miss it. The poll is therefore 2 s even on mains, and any status
change publishes at once, so Home Assistant's history records the start and end of every dip the driver saw. A dip that falls
between two driver polls is still unseen. Outages are counted from Home Assistant's history of `ups_on_battery`, not in the
service.

`rackmains_battery_charge_pct` is NUT's coarse estimate, from the battery voltage against `battery.voltage.low` and `.high`; the guard
never uses it.

**Guard metrics.** The guard's metrics join the payload when the guard exists, and each gets its own workbook row, `Enabled` for the
dry-run release, so nothing is added later by surprise. `guard_state` is one of `idle`, `waiting`, `shedding`, `holding`,
`restoring`; `guard_live` is off while in dry-run; `guard_mains_seconds` is the seconds on line since
the previous outage ended, absent when unknown; `guard_battery_seconds` is the guard's accumulated time on battery.

## Workbook rows to add to `entity_metadata.xlsx`

Every payload metric except `clock_epoch_seconds` (in the payload, the CSV and the log only) and `model_state` (in the
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
| `output_utilisation_pct` | `sensor` | % | |
| `rackmains_battery_volts` | `sensor` | V | `voltage` |
| `rackmains_battery_charge_pct` | `sensor` | % | `battery` |
| `rackmains_battery_charging` | `binary_sensor` | | `battery_charging` |
| `rackmains_battery_low` | `binary_sensor` | | `battery`, on means low |
| `battery_replace` | `binary_sensor` | | `problem` |
| `battery_remaining_pct` | `sensor`, with the model | % | |
| `battery_remaining_seconds` | `sensor`, with the model | s | `duration` |
| `rackmains_ups_status` | `sensor`, text | | |
| `ups_on_battery` | `binary_sensor` | | |
| `rackmains_ups_problem` | `binary_sensor` | | `problem` |
| `rackmains_ups_calibrating` | `binary_sensor` | | `running` |
| `rackmains_ups_boost` | `binary_sensor` | | |
| `rackmains_ups_trim` | `binary_sensor` | | |
| `guard_state` | `sensor`, text, with the guard | | |
| `guard_live` | `binary_sensor`, with the guard | | |
| `guard_mains_seconds` | `sensor`, with the guard | s | `duration` |
| `guard_battery_seconds` | `sensor`, with the guard | s | `duration` |
| `guard_auto` | `switch`, with the guard; `state_on` `1`, `state_off` `0`, `payload_on` `ON`, `payload_off` `OFF`, command topic `rackmains/command` (the one row that uses it) | | |
| `guard_auto_expires` | `sensor`, with the guard | | `timestamp` |
| `model_energy_used_wh` | `sensor`, with the model | Wh | `energy` |
| `model_history_known` | `binary_sensor`, with the model | | |
| `model_recalibrate` | `binary_sensor`, with the model | | `problem` |

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
{{ value_json['ups_on_battery'] if value_json['ups_on_battery'] is defined else (1 if is_state('binary_sensor.ups_on_battery', 'on') else 0) }}
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
- It reads the socket and writes only `DUMPALL`, so the mount stays `:ro`; no UPS command is ever sent, by the guard or by a host helper.
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
- **`awake` is safe after a reboot.** `/run/asleep.state` is tmpfs and a reboot clears it; with no record `awake` restores from fstab alone and waits for the containers to be healthy. So after a hard cut
  the guard runs it for every host the state file lists as shed, and its health wait is the confirmation that the host came back.
- **Calling `asleep` and `awake`.** The guard shuts servers down and wakes them with these two scripts and nothing else, and a host
  is never powered off. Both are **synchronous**: the call blocks until the script has finished and verified its own work, and its
  exit status says how it went, so the guard never polls a host to learn whether it is done. Over ssh the exit status is the
  script's (`0` ok, `1` error, `2` usage, `3` not root, `4` timeout, `5` unclean, `6` unhealthy), the last output line
  `RESULT <command> status=… reason=…` gives the reason, and an ssh status of `255` is a host that could not be reached.
- **Parallel when asked.** The guard's runner takes a list of hosts, a command and whether to run them in parallel. A parallel request
  starts one worker per host, each making its own blocking call, and joins them as they return; a sequential one runs them in order.
  Workers report over a channel, so the guard's own loop keeps polling and deciding while a shed or a wake is running. Each result is a `command` row in the outage CSV (host,
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
   `guard_shed_max_seconds`, and resets to zero only after `guard_mains_stable_seconds` of continuous `OL`, so a grid that flaps with dips under that apart cannot keep the
   servers up.
2. **Shed.** At `guard_shed_max_seconds` on battery, or `LB`: run `asleep --deep` on the followers in parallel, `meg` last so Home
   Assistant and the broker outlast the rest, each over ssh with a key whose `authorized_keys` forces the command (`restrict`,
   no shell; see the forced-command test), each call synchronous, so it is done when the call returns, and `0` means it completed cleanly. Any other code (1 error, 4 timeout,
   5 unclean) is logged and alerted and the guard moves on; it never retries in a loop. On `max`, run `asleep --shallow`
   stopping every container but rackmains (supervisor first, it binds `/`). A shed is not undone by the voltage rebound when
   the load drops, only by `guard_mains_stable_seconds` of mains. While `guard_auto` is paused the timer shed is withheld (next section).
3. **Run to failure.** Nothing more is done after the shed. rackmains and the guard stay up on `max` (shallow) and keep polling and
   recording until the UPS cuts its own output at its low-battery cutoff, and every host then boots on AC restore (power-on-after-cut
   test, below). If mains returns at any point before the cut, step 4 runs as normal, because nothing was ever past the point of return.
4. **Mains returns first.** After `guard_mains_stable_seconds` of continuous `OL`, run `awake` on `max` to restart what was
   stopped, and on each follower the state file lists once its `asleep` has returned, in the reverse of the shed order: `max`
   first, then `meg`, then the remaining followers in parallel (decided 2026-10-30). Each call is synchronous and its exit status says whether the host came back
   healthy (`6` is a container not running or healthy). `asleep` is undone by `awake`, so unlike
   a `poweroff` there is nothing to wait on being down.
**Safety rails.** It ships in dry-run, logging the exact commands it would run, and goes live only after the trials (see "Trials, tests and rollout") show the
conservative timers fit. It honours its hard override (`LB`) in dry-run too. The keys can
run `asleep` and `awake` and nothing else. Any status flag that is not `OL` is surfaced; an alarm or fault flag raises an alert in Home
Assistant.

**Later.** The decision (reading and history in, action out) stays a pure function apart from the state machine and the
runners, so the timer policy is replaceable; if a better policy is ever wanted it is fitted offline like the thresholds (the Future of the `ups/battery` notebook title cell).

**Residual risk of running to failure (decided 2026-11-11).**
- **Output may not restore after a depletion cutoff.** The manual says only that the unit starts by itself when plugged in, that "Standby" is
  connected to utility with outlets **not supplied**, and, under troubleshooting, to recharge for at least 6 hours and start again after a low battery. If the PSDR800 comes
  back from a depletion in Standby, no host boots and the rack stays dark until someone presses the button. Trial 5 observes this: after the
  cutoff restore mains and record whether the outlets are supplied without a button press, and how long it takes. If they are not, revisit by
  adding a host-side helper that sends `shutdown.return` over a forced-command ssh key, since that is the only command that guarantees a power cycle.
- **Battery wear.** A 9Ah sealed lead-acid battery runs to the unit's own cutoff on every outage past the shed point. The shed point is the only limit on how often.
- **`max` is cut while running.** Only rackmains runs there and the CSV is written by write, fsync and rename, so the cut is survivable, but `/home` is writable
  and root is not unmounted.

**Residual risk.** One USB link is one source of truth. A power cut with a failure of `max`, of Docker or of the guard leaves
the others running until the UPS is flat. A read-only `upsd` on the LAN with a dead-man timer on each follower would cover it
and is left out for now. Root login with a password is enabled on the followers, so the guard's keys are only as safe as that.

**Restart.** Decided: no wake packets and no Wake on LAN. If mains returns before the UPS is flat the guard runs `awake`; if the
UPS cuts, every host boots on AC restore from the state `asleep` left it in. The cut is now only the UPS's own depletion cutoff, so that second path
needs two things proved: the hosts boot after a cut (the power-on-after-cut test) and the UPS supplies its outlets again when mains returns (trial 5).

## Control plane, what talks over what (decided 2026-11-11)

**The rule.** MQTT is used only when the cluster is in normal operation: it mirrors state to Home Assistant and carries one convenience command. Everything a guard action or a trial needs works with
`meg`, the broker and Home Assistant shed: files in the data dir, the Tasmota plug's local HTTP, ssh to the hosts, and the driver socket. Health is the heartbeat file. The data dir is on `max`'s `/home`, which
stays writable under `asleep --shallow`, and the tool runs in the same container (`docker exec`), so no network is involved between the tool and the main program.

| Channel | Direction | Carries | Needs the broker |
|---|---|---|---|
| `auto.json` | CLI, Home Assistant (via the publisher) or `guard drill` to the guard | the pause | no, except the Home Assistant route |
| `drill.json` | the drill to the guard | the marker and its `id` | no |
| `guard_state.json` | guard to tool and publisher | the effective configuration, hosts, clocks, the ack, the model state | no |
| `guard_heartbeat` | guard to `checkhealthy.sh`, tool and publisher | liveness | no |
| the outage CSV | guard to tool, read-only | the live record | no |
| the Tasmota plug HTTP | tool to plug | cut, restore, readings, deadman | no |
| `rackmains/command`, `rackmains/data` | Home Assistant and publisher | the pause convenience command, the mirror | yes, normal operation only |

**What is reachable during a drain.** Once the shed has run (about 2 minutes on battery):
- yes: ssh to `max`, `docker logs -f rackmains`, `rackmains guard tail|list|stop` on `max`, the plug's HTTP from `max`, and ssh to a shed follower (`asleep --deep` leaves ssh and the network up);
- no: the broker, Home Assistant and InfluxDB on `meg`, the followers' services, supervisor's publishing, and the `guard_auto` switch in Home Assistant;
- everything goes dark at the UPS's cutoff until mains returns. Whether the network gear stays up on the UPS is unknown (gap 4 above), and ssh to `max` from outside depends on it.

With `meg` down the Home Assistant switch cannot pause the guard; `docker exec rackmains rackmains guard auto off` over ssh to `max` is the route.

**Request and reply over files, without a listener.** A file has no reply, so the reply is an echo the tool checks.
- The marker carries an `id`. The guard reads it on its next poll (at most 2 s on mains) and writes `ack = {id, accepted, reason, acked_ts}` into `guard_state.json`. The tool waits at most 10 s and **will not cut
  unless the ack carries its own `id` and `accepted`**; a rejection (an outage in progress, the guard not ready) prints its reason. No ack in 10 s means no cut.
- `rackmains guard drill` without `--force` prints the `effective` section of `guard_state.json`, so what the operator reads is what the process that will act has loaded, not a recomputation by the tool.
- Liveness is `guard_heartbeat` (a `seq` and a timestamp, replaced every guard iteration, no fsync, as the publisher's is). The tool refuses to cut if `seq` has not moved for a few polls, which is the proof a socket
  would give.

**Marker staleness.** The guard honours a marker only if it acked that `id` **before** the first `OB` of the outage and the marker is unexpired; a marker that appears after `OB`, was never acked, or has expired marks nothing.
Its expiry is the planned cut plus the hold plus the after-restore cap plus a margin. The tool deletes the marker on exit, the guard never deletes it (one writer per document), and a leftover marker is therefore harmless.

**Restart mid-trial.** The marker, `auto.json` and `guard_state.json` survive on disk. On start the guard rereads an unexpired marker and re-issues the same ack, the new CSV `start` row records `drill` and the mode
as for any outage, and the interrupted file is closed `interrupted` as usual.

**`guard_state.json`** (the guard thread is its only writer; the publisher and the tool only read it). Written to a temporary file, fsynced and renamed on every change, and at the CSV cadence while on battery, so a reader
sees a whole previous or whole new version and needs no lock; a reader that fails to parse simply reads again. Not backed up.

```
{
  "version": 1,
  "written_ts": "...",
  "effective": { "guard_live", "model": {"name", "version", "hash"}, "guard_shed_max_seconds", "guard_mains_stable_seconds",
                 "poll_mains_s", "poll_battery_s", "csv_row_s", "ssh_timeout_s", "shed_order": [...], "auto": {"state", "expires_ts", "run_to_failure", "set_by"} },
  "clocks": { "battery_seconds", "mains_seconds" },
  "hosts": { "<host>": { "shed", "call": null | {"command", "started_ts"}, "last": {"command", "status", "reason", "took_s"} } },
  "ack": null | { "id", "accepted", "reason", "acked_ts" },
  "model": { "project_hash", "version", "state": {...} }
}
```

A version it does not know is discarded and logged. On start the guard probes each host instead of trusting `hosts`, because after a hard cut the hosts boot fresh while the file still lists them as shed.
`guard_heartbeat` is separate so that liveness costs no fsync per poll.

**Why not a socket or an API.** A unix socket (or HTTP over one) would give a synchronous reply, but the pause and the marker still need files to survive a restart, so it would be an addition, not a replacement, and
it adds an always-on server to a module whose surface is deliberately small. A TCP REST API adds a LAN listener and authentication, which the plan already rejected for `upsd`, and nothing off-host needs it. Health
stays on the heartbeat, because a server thread can answer while the poll loop is hung, whereas the heartbeat is written by the loop itself. If a live request and reply is wanted later, add a unix socket for it.

## The pause switch, `guard_auto` (designed 2026-11-11, not built)

Modelled on supervisor's `backup auto` (the reaper switch), with the same polarity: **`ON` is armed, `OFF` is paused until a deadline.** It is the one way to stop the
guard shedding for a deliberate cut (maintenance, a plug change, a `drill` that must not shed), replacing a release that flips dry-run.

- **The truth is a file, not the broker.** `auto.json` in the data dir: `state` (`ON`/`OFF`), `expires_ts` (RFC 3339), `run_to_failure` (bool), `set_by` (`ha`, `cli` or `drill`),
  `set_ts`. The guard reads it every poll and never touches MQTT, so a pause survives the broker or `meg` going away. The publisher mirrors it to Home Assistant from the
  file, so a vernemq flush can neither lose nor invent a pause. It is a separate file from the guard's state file so the guard never read-modify-writes operator input, and it is
  excluded from the backup.
- **Fail-safe armed.** Only an explicit `OFF` with an unexpired `expires_ts` pauses. A missing, corrupt, expired or `ON` file, an `OFF` with no deadline, or a deadline beyond
  `RACKMAINS_GUARD_AUTO_PAUSE_MAX` (6 h, a guard against a stepped clock) is armed.
- **Setting it.** Three callers, one atomic write function (temporary file, fsync, rename), last writer wins and `set_by` says who:
  - the Home Assistant switch publishes `ON`/`OFF` to `rackmains/command`; the **publisher**, not the guard, subscribes, and `OFF` pauses for `RACKMAINS_GUARD_AUTO_PAUSE`
    (30 min); **retained commands are ignored**, so a stale `OFF` cannot re-pause the guard after a restart
  - `docker exec rackmains rackmains guard auto [on|off [<dur>] [--run-to-failure]]` (default 30 min, cap 6 h); with no argument it prints the state
  - `rackmains guard drill ... --no-shed`
- **Guard behaviour when paused.** It still polls, accumulates time on battery, records the CSV and publishes. Only the timer shed is withheld: at `guard_shed_max_seconds` it
  writes a `decision` row naming the deadline and `guard_state` stays `waiting`; there is no new state. When the pause expires mid-outage the guard resumes with the
  accumulated battery time and sheds at once. A pause set after the shed has started stops further shed steps but never the restore, which is always safe.
- **Low battery.** `LB` sheds even when paused, since waiting protects nothing. `--run-to-failure` (stored as `run_to_failure`) withholds that too, for a deliberate run to the cutoff
  with the whole rack on.
- **Home Assistant.** `guard_auto` and `guard_auto_expires` are in `rackmains/data` and count as derived flags, so a change, including the flip back to armed at expiry, publishes at
  once. No new topic and no formula change. Alert on `guard_auto` off for longer than a threshold. `RACKMAINS_GUARD_AUTO_PAUSE` (30 min) is shorter than the battery's run
  so a forgotten pause cannot outlast it; the duration argument extends it for longer maintenance.
- **Tests.** Table over the file contents (missing, corrupt, expired, over the cap, `ON` with a deadline, `OFF` without one, valid) giving armed or paused; a pause withholds the
  timer shed, expiry mid-outage sheds at once, `LB` sheds while paused and not with `run_to_failure`; a retained command is ignored; the pause survives a restart and a broker
  outage; restore runs while paused. Each rule is deleted once to prove its test fails.

## The guard CLI and the test command, `rackmains guard drill` (designed 2026-11-11, not built)

The `rackmains` binary becomes a multi-command CLI as supervisor's is (`backup start|stop|auto`, noun then verb, safe by default). `drill` cuts the rack's mains through its plug, collects data, and restores before
exhaustion or runs to the cutoff. It replaces the deleted `tools/outage`. It is a subcommand of the one binary, run as `docker exec -it rackmains rackmains guard drill`, not a second binary, so it uses the same typed
readers of the outage CSV, `auto.json` and the model policy as the service and there is one CLI to build, parse and test. `mockdriver` stays a separate crate, being a test double. `main.rs` stays a thin shim over the library's `Cli`, which becomes a root with subcommands as
supervisor's is: `serve` runs the service with the flags it has today (moved under it), `guard` holds the operator commands, `check` validates, and a bare `rackmains` prints help, so a stray `docker exec rackmains rackmains` cannot
start a second reader. The container entrypoint and compose command become `rackmains serve`. That is a deliberate deviation from `tempstat`, to be recorded in the final review.

**The plug.** `rack_outlet_plug` ("Server Rack") is a Tasmota at `10.0.4.102` (not `rack_backup_plug`, which is supervisor's backup-disk plug). The tool uses its local HTTP
(`/cm?cmnd=...`, as `tasmota_config.sh` does), never MQTT or Home Assistant, because `meg` is shed during a drain. It reads `Power` back and `Status 8` for watts; the plug's clock reads
1970, so the tool stamps readings with its own clock. A plug-side **deadman** is armed before the cut and disarmed after a clean finish, a one-shot rule that restores mains by itself
if the tool, ssh or `max` dies:

```
Rule1 ON Power1#State=0 DO RuleTimer1 <max_seconds> ENDON ON Rules#Timer=1 DO Backlog Power1 1; Rule1 0 ENDON
```

It is unproven until tried on the spare plug (Remaining phases, step 3). `PowerOnState 1` only covers the plug itself losing power. In drain mode the deadman is what restores mains after
the cutoff, so the report on that run comes from the outage CSV afterwards, not from the tool, which dies with `max`.

**Interaction with the main program, by files in the data dir and never MQTT.**
- The drill writes `drill.json` (mode, hold, planned cut, expiry) atomically before the cut. The main program reads it at the first `ob`, notes `drill` and the mode in the `start` row
  and otherwise behaves as for any outage. An expired or absent marker marks nothing. The tool deletes it on exit.
- The guard answers in `guard_state.json` with an `ack` that echoes the marker's `id` (see "Control plane"); the tool will not cut until it sees its own `id` accepted, which also proves the guard is alive.
- The tool reads the guard state file and tails the outage CSV, and never writes the CSV. The main program names, writes and rotates it (timestamped name, temporary file and rename), so a run cannot
  overwrite an earlier one. Plug readings go to a sidecar `<same stem>.plug.csv` beside it, created exclusively and written the same safe way, with its own clock.
- A maintenance pause and a `drill` that must not shed share one mechanism, `auto.json`; the marker only marks the run.

**CLI.** Follows supervisor's pattern (`cmd.go`, `cmd_serve.go`, `cmd_backup.go`): a root with subcommands, noun then verb, verbs held in one table, help lines lowercase and verb first, optional positionals in brackets,
durations with unit suffixes, kebab-case long flags with a short form for the common ones, choices listed as `[a, b]`, and a command that acts on the real system shows its plan without `--force` (as
`backup module restore`). `auto` with no argument queries, `tail` follows, `list` shows recent runs, and `stop` is the pair of the command that starts a run.

```
rackmains [-V|--version] [--data-dir <dir>]     root flags, inherited by every command; --data-dir is /asystem/mnt, env RACKMAINS_DATA_DIR

rackmains serve [options]                       run the reader, publisher and guard
rackmains check                                 validate the model, host file, ssh keys, data dir and driver socket, then exit
rackmains guard auto [on|off [<dur>]]           query or set the guard's automatic shedding; off pauses it, default 30m, cap 6h
                     [--run-to-failure]         with off, also skip the low-battery shed
rackmains guard drill [<dur>|drain]             rehearse a power cut: print the plan without --force; default hold is the shed point plus 120s
                      [--no-shed] [--force]     --no-shed pauses the guard for the run; --force cuts mains
rackmains guard stop [--force]                  abort the active drill: mains on, deadman disarmed, guard re-armed if the drill paused it
rackmains guard tail [<file>]                   follow the newest outage CSV, or the given file, as rows arrive
rackmains guard list                            show the recent outages and how each ended
```

- **Conventions taken from supervisor.**
  - `-V/--version` (clap's, as `tempstat`'s; supervisor's is `-v`) prints `SERVICE_VERSION_ABSOLUTE` and exits.
  - `-L/--log-level [debug, info, warn, error]` on `serve`, default `info`, its default overridable by `RACKMAINS_LOG_LEVEL` as supervisor's is by its environment variable. Supervisor's source, subject and action log filters
    are not copied, since rackmains has no such vocabulary.
  - A short list of common flags is shown and the rest are advanced, hidden behind `--help-all`. Shown on `serve`: `-P`, `-B`, `--heartbeat-period`, `--live`, `-L`. Advanced: `-D`, `-M`, `-T`, `--broker-port`,
    `--broker-token`, `--battery-poll-period`, `--csv-period`, `--outage-keep`.
  - Errors go to stderr and exit `1`; a command that has already reported its failure returns a reported error so it is not printed twice; a command that must exit with its own code (a `drill` aborted with mains restored)
    returns an exit error carrying it. The codes themselves are still open decision Q5 (recommended: mirror `asleep`).
  - The `guard` verbs are one table (name, usage, help, argument count), as `backupVerbs`, not separate handlers.
- **Crate: `clap` 4 with `derive` and `env`, already a dependency (4.6.7 locked), and nothing new is added.** The root is a `Parser` with a `Subcommand` enum, `guard` a nested `Subcommand` enum, and the root flags `global = true`.
  Advanced flags use `hide_short_help = true`, so `-h` omits them and `--help` shows them, which replaces supervisor's `--help-all` without custom code. Choices use the existing `PossibleValuesParser`. Durations (`<dur>`, the
  period flags) use `humantime`, also already a dependency. Version stays clap's `-V/--version`, as `tempstat`'s, not supervisor's `-v`. The typed `drain` confirmation reads one line from stdin, with no prompt crate. Exit
  codes come from a typed error matched in `main`. No completion crate.
- **`serve` options.** The existing flags move across unchanged (`-P/--poll-period`, `-D/--device`, `-M/--model-dir`, `-T/--timeout`, `-B/--broker-host`, `--broker-port`, `--broker-token`, `-L/--log-level`). Added:

  | Option | Default | Meaning |
  |---|---|---|
  | `--battery-poll-period` | `1s` | poll period on battery; `-P` is the mains period (`2s`); uses unit suffixes [s, m, h] |
  | `--heartbeat-period` | `5m` | publish on mains even if unchanged, supervisor's name for it; no short form, `-B` is the broker |
  | `--csv-period` | `5s` | one outage CSV row on battery |
  | `--outage-keep` | `100`, env `RACKMAINS_OUTAGE_LOG_KEEP` | newest outage files kept |
  | `--live` | off, env `RACKMAINS_GUARD_LIVE`, set in `.env_prod` | the guard sheds for real; without it the guard is in dry-run; refused if `check` fails |

  No flag sets `guard_shed_max_seconds` or `guard_mains_stable_seconds`: thresholds come from the released model, never from flags or constants.
- **`check`** loads the model and verifies its hashes and signature, reads the generated host file and checks the ssh keys exist with the right modes, the data dir is writable and the driver socket reachable, then exits `0`
  or non-zero. `fab systest`, the install hook and an operator can run it, and `--live` uses the same checks, so the guard's "refuses live mode if the model fails" has one implementation.
- **`guard tail`** and **`guard list`** are read-only and share the one typed outage CSV reader. `tail` is what follows an outage after the drill has gone (a `drain` ends with `max` dying, and the record is read afterwards);
  `list` prints each recent outage with its start, duration, minimum battery voltage, hosts shed and whether it was a real outage or a `drill`, taken from the `start` and `end` rows.
- **`<dur>` or `drain`** is one positional on `drill`. `drain` keeps mains off until the UPS cuts its own output.
- **`--no-shed`** writes the pause to `auto.json` and re-arms on every exit path. `drain --no-shed` hard-cuts every host with writable disks, so it sets `run_to_failure` itself and still needs a typed `drain` even with
  `--force`. There is no separate run-to-failure option on `drill`.
- **No `plan` or `run` command, no `--yes`, no `--label`:** a bare `drill` is the plan and `--force` acts. `drill` follows its own run and keeps following after Ctrl-C; `docker logs -f rackmains` carries the same events at INFO.
- **From the environment, not flags:** `RACKMAINS_PLUG_HOST` (`10.0.4.102`), set in `.env_all`.
- **Fixed, not options:** recording continues after restore until the outage CSV's `end` row, capped at 30 min; the plug deadman is hold plus 5 min, or 3 h for `drain` until the first measured run (Decided). Changing
  either is a release.
- **Container-free fallback.** If Docker or the rackmains container is down, `guard stop` cannot run; the plug deadman is the backstop and the operator command is
  `curl 'http://10.0.4.102/cm?cmnd=Power%20On'` followed by `curl 'http://10.0.4.102/cm?cmnd=Rule1%200'` to disarm the rule.
- **Detached sessions.** `docker exec -it` is not detached; if the ssh session drops, the plug is left to the deadman. That is accepted, because the deadman exists for exactly this case.

**What it prints before cutting**, in three blocks so the drain is clearly understood:
1. the tool's settings (mode, hold, after, deadman, guard posture, plug);
2. what the main program will observe, read live from the state file and policy (dry-run or live, version, model project and mode, `guard_shed_max_seconds`, `guard_mains_stable_seconds`,
   the poll and CSV row intervals, the ssh timeout, the shed order, and the `guard_auto` state with its deadline and `set_by`);
3. the derived timeline (T+0 plug off, about T+2 `OB`, T+120 shed, T+hold plug on, T+hold+300 `awake`, `end`), with a loud warning if hold is under the shed point (the guard will not shed)
   or the guard is in dry-run (the test proves nothing about the shed), and the preflight results.

**While running.** It tails the CSV by row count (the file is replaced every 5 s and continues in `_2.csv`, so `tail -F` is no use) and prints one line per new row: elapsed, status, volts,
utilisation, `guard_state`, host results and plug watts. The hold is counted from the first `OB` row, not from the command. It also stops early in hold mode if `LB` is raised.

**Arming is read back.** Before the cut the tool arms the deadman, then reads `Rule1` and its timer back from the plug and refuses to cut if either is wrong; after the cut it requires `Power` to read `OFF`.

**Exit paths.** On Ctrl-C, SIGTERM or SIGHUP the plug goes on first, a second Ctrl-C is ignored until the plug reads back `ON`, then `auto.json` is re-armed if the tool paused it, the marker becomes
`aborted`, and the tool says the main program will run `awake` after `guard_mains_stable_seconds` of mains and keeps following until `end`. After a normal restore it verifies `OL` within a bound and
retries, alarming loudly with `rackmains guard stop` and the container-free fallback otherwise. After the plug reports off it requires `ups_on_battery` in the CSV within 10 s, else it restores and fails. The tool runs
detached from the ssh session.

**Preflight** refuses on: an outage in progress, an existing marker, a stale guard heartbeat, an unreachable host, the 01:00 backup window, and a paused guard without `--no-shed` (the run would test
nothing). It **warns only** when the last outage ended under 6 hours ago (the manual's recharge time) or the battery is not at 100%. `--no-shed` writes a pause ending 60 s after the deadman,
capped at the maximum, and re-arms on every exit path; the plug deadman and the pause expiry are independent, so neither depends on the tool. If `auto.json` changes during a run the tool warns and never overrides it.
`drain --no-shed` would hard-cut every host with writable disks, so it needs the typed `drain`.

**Interaction tests** (the system test with the mock driver and a mock plug):
| # | Scenario | Expected |
|---|---|---|
| 1 | hold 240 s, guard armed | shed at 120 s, plug on at 240 s, `awake` after 300 s of mains, `end` |
| 2 | run while the guard is paused | preflight refuses |
| 3 | `--no-shed`, hold 240 s | no shed commands, a withheld `decision` row, tool re-arms at restore |
| 4 | Ctrl-C during `--no-shed` | plug on first, then re-armed, marker `aborted` |
| 5 | `kill -9` the tool during `--no-shed` | the deadman restores mains and the pause expires |
| 6 | pause set from Home Assistant during a default (armed) run | guard pauses, tool warns and does not override |
| 7 | pause expires mid-outage | immediate shed |
| 8 | pause set after the shed started | no more steps, restore still runs |
| 9 | low battery while paused | shed, unless `run_to_failure` |
| 10 | broker or `meg` down, a vernemq flush, a container restart while paused | pause survives |
| 11 | missing, corrupt, expired or over-cap `auto.json` | armed |
| 12 | retained `OFF` command on the broker | ignored |
| 13 | dry-run guard | pause has no effect but is shown |
| 14 | `drain --no-shed` without the typed confirmation | refused |
| 15 | an ack with another `id`, a rejected ack, no ack within 10 s, or a `guard_heartbeat` whose `seq` has stopped | the tool does not cut |
| 16 | a marker that was never acked, appears after `OB`, or has expired | marks no outage |
| 17 | the guard restarts mid-trial | the marker is honoured, the same ack is re-issued, the new `start` row records `drill` |
| 18 | `guard_state.json` is read while being replaced | the reader sees a whole old or new version |

Risks accepted: a forgotten pause costs protection until its deadline (30 min default, plus the alert); two callers can overwrite `auto.json` (`set_by` makes it visible); the wall-clock deadline depends on
`max`'s clock (the cap bounds it).

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
  **yours to do by hand** (test 5, see "Trials, tests and rollout"). Whether any host boots after a cut is **not yet tested**.
- **Tested on `max`, 2026-10-29.** Argument and precondition codes; dry runs that leave the host unchanged; a real shallow
  cycle with supervisor left running, returning 0 and restoring the host exactly; an unclean cycle (a container that ignores
  SIGTERM) returning 5 with exit code 137 reported; `awake` error paths returning 1 and 6; and a read-only remount round trip
  on every filesystem type in the estate, on all four hosts. **Not yet:** a real deep run, the timeout code end to end, any
  other host, the power-on-after-cut test.

## The model seam, in rackmains

The model, its signature, its training and the plan for fitting it are the `ups/battery` notebook in `mlmodels`: its title cell holds the intent, status and future, and the `signature.json` beside it the signature. What rackmains
must build is the seam: how it builds a request from numbers it already records, carries and persists the model's state, validates and
applies a response, and the constants model it ships from day one. The signature is declared once, in that `signature.json` (the notebook reads it through `ws.inputs` and `ws.outputs`), and the embedded released project is `src/build/resources/model/battery/`.

**Nothing computed here is a feature.** rackmains sends the poll time, the utilisation, the on-battery flag and the replace flag, exactly
the numbers it records, plus the state the model returned last time. Every feature is inside the model's graph. The row and the outputs
are recorded identically in MQTT, the CSV and the log, and the state is recorded in the CSV and the log at the start and end of an
outage (`model_state`, JSON text), so a recorded outage is a complete fold and can be replayed through any project. Text and the timestamp are never sent: the
status becomes the flags and the time becomes `clock_epoch_seconds` at source, here, in Rust.

**The Rust seam.** The model is the bundled loader (`mlmodels` `model.md` 10.9), written by `python -m mlmodels embed` into `src/model/` as `loader.rs`, `battery.rs` (the name constants, `Request`, `Response` and their conversions, and a `load` that checks the signature against them) and `mod.rs`. `model::battery::load` checks every hash and returns a `Model` whose `predict` gives the constants for every valid request; `policy.rs` turns the `Response` into the guard's `Policy`. A later ONNX project needs no new type: the same loader builds its driver with `ort` (pinned exactly, one thread, loading the shared library taken from the pinned wheel MLServer uses) and `predict` takes the row and the state and returns the response. There is no served model and no fallback project: a project that fails to load makes rackmains broken (`mlmodels` `model.md` R8), and its build and tests catch that. A failed call keeps the last valid answer. One validator turns a response into a typed `Policy` and the estimates, and the guard sees only those, never JSON, so
replacing the constants project with a fitted one changes one constructor and nothing downstream.

**State.** The state in the answer in use is carried to the next call and persisted, with the project hash and model version, in the guard's
state file, **written atomically on every call**, which is how state survives a crash (its format is in "Control plane"). A state from a different project is discarded, and a lost state
restarts the model from its initial state, with the history unknown, which it treats as a partly drained battery. The guard does not read
the state; it is the model's.

**Engine and memory.** Day one embeds only the default (static) project, which needs no engine. The first ONNX project brings `ort`, the
ONNX Runtime shared library for each architecture, taken from the pinned wheel and hash-pinned into the image, and a higher compose
memory limit (measured at 34 MB for the engine on the laptop; about 96 MB suggested in place of 32 MB, to re-measure on Linux).

**Calls.** One every 5 s on battery, at each transition and every 5 minutes on mains. A call never blocks the poll or the guard; a failed
call keeps the last valid answer and is a `note` row.

**Tests.** The validator against a table of good and bad responses; the shipped project loads, validates and matches its hashes; the names
in `signature.json` equal the validator's, checked both ways; the golden sequences replayed through `model::battery::load` (and later every fitted project), carrying the state, give exact responses; a **replay test** feeds a recorded outage CSV through the model and requires
every recorded output to be reproduced from the `start` row's state and the final state to equal the `end` row's; a state from another
project is discarded; and a failed call keeps the last valid answer.

**The shipped model** lives in the image as the embedded project (`project.json`, `signature.json` and `golden.json`), so
changing it is a release. The first release is the `static` day-one project and a fitted
project later replaces it; there is no floor beside it. The guard validates it at start, checks its hashes, and **refuses live mode** if it fails; it stays in dry-run and says so.
Dry-run versus live is deployment config in `.env_prod`, never in a model document.

**What is implemented (2026-11-05).** The project is written by the notebook and passes every project check of `model.md` section 9 (the five inputs, nine outputs (twelve before the halt thresholds were removed) and six state slots of `signature.json`, and a golden file with a first
call with no state, a row mid-drain with state, a row with the replace flag raised, and a request with the utilisation missing that
must give a signature error). It is embedded into `src/build/resources/model/battery/` by `generate.sh` once released, and not before. **Implemented (2026-11-11):** the first release is embedded, with the loader and model file in `src/model/`, `policy.rs` and its tests, and the project copied into the image at `/asystem/etc/model/`. **Not built:** the guard's
refusal of live mode on a failed validation.

**Starting values, the default model.** Constants only: `guard_shed_max_seconds` 120, inside the 145 s already held at service
load with no knee; and `guard_mains_stable_seconds` 300. They shed early on short outages and so
waste battery, but never outrun what is proven. The values are the constants of the notebook's `define_model` call. A refit replaces the project, which is a release.
The halt thresholds (`guard_halt_max_seconds`, `guard_halt_delay_seconds`, `guard_halt_lead_seconds`) were removed from the signature in place, before it was released, so the project, its golden file, the generated
`battery.rs` and `policy.rs` no longer carry them; the signature now has the five inputs and nine outputs, two of them required (`guard_shed_max_seconds`, `guard_mains_stable_seconds`).

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

## Build standards and the review phases

Judged in this order when they disagree: the global and project `CLAUDE.md`, then `tempstat`, then Rust idiom. The aim is a **reference project**: the module a reader copies to learn how a Rust service here is laid out, tested and
logged, in the smallest code that does the job.

**Building (every crate: `rackmains`, `mockdriver`, `tools/schema`, and anything the guard adds)**
- **Layout as `tempstat`.** A thin `main.rs` (version from `SERVICE_VERSION_ABSOLUTE`, `ExitCode`, `eprintln!("rackmains: {err}")`) and a library holding all logic; modules by concept (`broker`, `nut`, `schema`, `policy`, `model`, plus the
  guard); public items first, then private helpers, then types and constants; `#[cfg(test)] mod tests` last in each file, shared stand-ins in `#[cfg(test)] mod mock`; `mockdriver` stays a shim because its emulators are production code shipped in the image.
- **Errors.** A typed enum per module with `Display` and a `Result<T>` alias, values in `[brackets]`, no `:` or dash separators in a message; `?` to propagate; no `unwrap` or `expect` outside tests; no `let _ =` on a `Result`.
- **Ownership and iterators.** Borrow before clone (`&str`, `&[T]`), iterators over index loops, `Option` and `Result` combinators, exhaustive `match` with no wildcard on our own enums, `Duration` and `Instant` for time, never raw integers.
- **Traits only at a real seam** (the broker `Publisher`, the driver, the plug, the ssh runner, the clock), so the state machine is tested against a mock; no trait with one implementation and no double.
- **State as data.** The guard is one pure function from (state, input) to (state, actions); the runners and the clock sit outside it, so every sequence is a table test.
- **Concurrency.** Threads and bounded `mpsc` channels with one owner per piece of state; no `Arc<Mutex<_>>` where a channel does; every blocking call has a timeout; one shutdown path; monotonic `Instant` for durations and the wall clock only for stamps and persisted deadlines.
- **Files.** One function writes a file atomically (temporary file, fsync, rename, directory fsync), and one typed reader exists per persisted document (the outage CSV, `auto.json`, `guard_state.json`, `drill.json`, the heartbeat).
- **Logging.** The `log` macros and `log_line` as `tempstat`: INFO is one line per event a human watching wants, everything per poll is DEBUG, values in `[brackets]`, the canonical metric name beside the value.
- **CLI** as set out in "The guard CLI": `clap` derive, the nested enums, a parsing test per flag as `tempstat`'s `cli_parses_*`.
- **Dependencies** are justified and minimal-featured; a new crate needs a stated reason here. No comments except a documented interface or a genuinely complicated process, and maintenance notes. No `TODO`.
- **Simplicity.** A function with one caller is inlined (a closure beside its use when the step wants a name); a pure function with a real input space keeps its definition and a table test; nothing is added "for later"; one owner per closed vocabulary
  (NUT tokens and the payload keys in `nut.rs`, the guard states, the `ON`/`OFF` words) with a mirrored copy tested for equality.
- **Gates** on every change: `cargo fmt` with the root `rustfmt.toml` (width 120), `clippy` as `fabfile.py` runs it (pedantic, `-D warnings`, its short `-A` list, never an `#[allow]` in source), `shellcheck` with bare directives, `ruff`
  and pyright for Python, the targeted tests.

**The review, run at R1 to R4 and repeated for anything that changes afterwards.** A review finds defects first and simplifies second, then fixes what it finds and reports what it did not. Read the module's `CLAUDE.md` and the
neighbouring files first, and keep the style in step with them. Passes, in this order, because the early ones change what the later ones see:
1. **Correctness.** Read the logic itself, not the tests. Hardest at state that crosses a boundary (processes, threads, retries, restarts), ordering, what an interrupt or half-finished run leaves behind, idempotency, and error paths that report
   success. A value set in one process is not visible in the next. Specific to this module:
   - each dependency failing: the broker down at start and mid-run, the driver socket missing, stale or garbage, the data dir full or detaching, a host unreachable or hung, the plug unreachable, a malformed model response;
   - time: monotonic for durations, the wall clock only for stamps and the persisted deadlines in `auto.json` and `drill.json`, a stepped clock, and the 6 h cap that bounds it;
   - numbers and files: parsing, overflow, the one formatter shared by the payload and the CSV, write-fsync-rename order, recovery of an unfinished file, the file count bound and that the prune never removes the current file or leaves an orphaned sidecar;
   - the guard: every action idempotent, a restart mid-outage and mid-sequence, a flapping grid with dips shorter and longer than the stable period, a pause set or expiring mid-outage, a lost ack, a reader meeting a file mid-replace;
   - the drill: the deadman armed and read back before the cut, every exit path restoring the plug first and re-arming after, a second Ctrl-C, a dropped session, a stale or never-acked marker.
2. **Dead code.** Count the references to every function, type, constant, flag and parameter; one used only by tests is dead in production, so delete it or move it into the test. Find it by removing a suspect and building, since cargo does not flag unused public items in a library.
3. **Duplication.** One reader per persisted document and one owner per constant; search for every place that parses the same file and make them share one typed reader.
4. **Single-use helpers.** Count the call sites outside tests and apply the rules above: inline, closure, a shared function only from a second real caller.
5. **Naming.** One prefix per domain, the same concept spelled the same in every file and language, verbs first for functions and nouns for types and constants, names that say what a thing is now; rename mechanically with whole-word patterns, check for collisions, then build, and rename the tests with the code.
6. **Layout.** Public and primary first, then helpers, types and constants last, in the same order in every file, the `impl` after its type, the `lib.rs` module list in reading order; merge a tiny file into the file that owns its concept and split a file holding two.
7. **Comments.** None, except an interface contract, a genuinely complicated process, and a note telling a maintainer what to update by hand. Suppression directives stand bare. No commented-out code.
8. **Tests.** Table-driven where the input space is real, one test file's worth per source file, names that read as the behaviour (as `tempstat`'s). Assert behaviour (codes, counters, states, data, files), never log, error or reason wording and never the implementation's shape; remove tests whose
   subject was inlined; add one where a handler or a decision rule has none; cover the failure path as well as the success. **Prove each new decision rule bites** by deleting the rule and watching its test fail.
9. **Standards.** Run the formatters, linters and type checkers and the project's own convention tests; the build rewrites source when it lints, so read the diff after every run. Check the dependency list (each justified, features minimal, none duplicated, pinned), `Cargo.lock` unchanged except deliberately, and the
   security points: only `DUMPALL` written to the driver socket, forced-command keys with the host key pinned and no host name interpolated into a shell string, untrusted input parsed defensively (driver lines, the MQTT command, a model response, ssh output, CSV quoting), no panic reachable from outside input, no secret in a log or the repo.
10. **Prove it still works.** Run the targeted tests first, then the full suite once. Run the real built artefact: `fab build`, `fab package`, then the image with the mock driver and the system test, with failure injection (`kill -9` mid CSV write, stop the container mid outage, start with the broker down and lose it mid drain,
    a read-only or full data dir, a stale, garbage and vanished driver socket, an invalid, absent or slow model response, a hung host, a plug that does not answer). Measure resources: the compose memory limit through the longest outage the CSV bound allows, with no queue, in-memory row set, thread or descriptor growing without
    bound, the CSV rewrite of up to 1 MB every 5 s and the per-poll heartbeat judged for SSD wear, and DEBUG volume against the 5 x 100 MB log rotation. For generated output (`broker.sh`, the schema, `.env`, `docker_deps.sh`) a pure refactor regenerates byte-identical, and any other diff is explained.

**Operability and documentation (part of the final review).** Each log line says what happened at the right level; start and stop are logged; the health check means one thing; an operator can find, read and back up the CSV from what is written; every claim in the module `CLAUDE.md` and this plan is true of the
code; each hook is idempotent and never fails an install it should not.

**Review is not permission to ship.** Do not run a release, deploy or install as part of a review, and read what a release command does to git and to remote hosts first. Report in this order: the defects found and fixed, then the simplifications, then what was left alone and why, then what was not checked; keep a real bug
distinct from tidying, and say plainly when a pass found nothing.

**Process rules.** Judge against this list, not taste, and cite the rule each finding breaks. Classify each as a **blocker** (wrong or unsafe), a **should-fix** (against a guideline, or a clear simplification) or a **nit**. Nothing classed blocker or should-fix is deferred without a reason recorded. A second reader reviews what
the first changed, a human or an automated high-effort review (`code-review`, `simplify`). Record the version reviewed (`SERVICE_VERSION_ABSOLUTE`) beside the table.

**Exit criteria.** No blocker or should-fix is open; every other finding is fixed or accepted with a reason; the gates are green; a fresh diff against `tempstat` shows only intended differences, each recorded with whether `tempstat` should adopt it (the root CLI is one); the module `CLAUDE.md` matches the code; and nobody
reading the module would need this plan to understand it.

Version reviewed: none yet, no review has run.

| # | Finding | Where | Rule broken | Kind | Severity | Outcome |
|---|---|---|---|---|---|---|
| | none yet | | | correctness, safety, resources, simplification, style, guideline, name, comment, test, order or docs | blocker, should-fix or nit | fixed, or accepted with the reason |

## Trials, tests and rollout (restated 2026-11-11)

Recovered from the model plan deleted in commit `ca0c83150` (`git show ca0c83150^:src/rue/mlmodels/src/main/notebook/rackmains/ups/battery/plan.md`), adapted to the decisions since: no halt, no `shutdown.return`, run to failure, and
`rackmains guard drill` replacing the by-hand cut. Results are recorded here as they come in.

**Before every trial.** The battery has settled: on mains at least 12 hours since the last transfer, float steady within 0.1 V for 30 minutes, load steady within 3 points for 10 minutes, all four servers answering, and outside the
01:00 backup window. Abort on voltage, `LB`, a host down, stale readings or a cap, **never on the unit's capacity or runtime**, which are smoothed model outputs that lag.

| # | Trial | Command | Needs first | Decides |
|---|---|---|---|---|
| 1 | Hold at service load | `guard drill 10m --force`, guard in dry-run | the guard and the drill built | the conservative timers fit; the knee if it appears |
| 2 | Recover before the shed | `guard drill 90s --force`, guard live | trial 1 | nothing is shed, the reset works |
| 3 | Recover after the shed | `guard drill 4m --force`, guard live, followers shed then woken | tests 3, 4 and 5 | the restart path |
| 4 | (dropped) Halt and UPS cut/restore | | | there is no halt and no `shutdown.return`; test 6 stays only as the fallback if outlets do not restore |
| 5 | Run to failure, once per battery | `guard drill drain --force`, guard armed | the plug deadman proven (test 8), trial 1 | the real knee and cutoff, whether `LB` raises, whether outlets restore, the offline fit |

Trial 5 was written as "to the 11.5 V floor or `LB`, not to the UPS cutting out", a second point at service load because the low load runs long. The run-to-failure decision supersedes the stopping point; see Q4.

**Tests still needed**, from no risk to most; each result decides a branch.
1. **Baseline**, a day on mains with the recorder: which flags appear unprompted (`BOOST`, `TRIM`). The recorder has since been stopped, so the published entities and the outage CSVs are the record.
2. **Quick battery test** (`test.battery.start.quick`): the test flag's name and the seconds spent in `OB`, in a quiet hour.
3. **Forced command** on `may`: a dedicated key with `command="echo ok",restrict`, then `command="/usr/local/bin/asleep --deep --dry-run",restrict`, run from a container on `max`. A forced command takes no arguments, so decide between a
   key per action (`asleep --deep`, `asleep --shallow ...`, `awake`) and one wrapper that dispatches on `SSH_ORIGINAL_COMMAND`.
4. **Per-host `asleep` time**, start of the command to its `RESULT` line (`took`), several runs per host and the slowest container stop; order `may`, `mad`, `meg`. Measured so far: `max`, shallow, three containers, about 3 s; no deep run yet.
5. **Power on after a cut**, per host, yours. A clean `poweroff` is not the test, the board stays off after one. `max`, `may`, `meg`: `AFTERG3_EN` is already cleared (`1c08`); run `asleep --deep` (on `max`, `--shallow`), pull the cord from the UPS for
   10 s, replace it, and time the boot to ssh. `mad` (Mac mini M2 Pro) needs a macOS step first: boot macOS from the boot picker, turn on "Start up automatically after a power failure" in Energy Saver, check `pmset -g | grep autorestart`
   prints `autorestart 1`, boot back into Linux and run the same cut. The only report that this carries into Linux is on a base M1 ([AsahiLinux/docs#156](https://github.com/AsahiLinux/docs/issues/156)), so the M2 Pro result is part of the test.
6. **`shutdown.return` on a lamp**, and `shutdown.stop` cancelling it, only if trial 5 shows the outlets do not restore by themselves.
7. **Standby**, only with the outlets empty: `ups.status` for `OFF`.
8. **Plug deadman**: the on-device restore proven by hand with the plug unreachable. The Tasmota `Delay` honours only 2 to 3600 tenths of a second (`Delay 4200` was ignored), so a cut above 360 s cannot use a single `Delay`; the rule timer in
   "The guard CLI and the test command" is the design, and it is proven on the spare plug first.
9. **Reachability**: the plug console and all four hosts are reachable from where the cut is made, and that place is not on the UPS. The plug's API is open without a password on the LAN, so anything on that network can cut the rack; `max` and a
   bridge container both reach it (a bridge container on `max` was confirmed on 2026-11-11).

The guard's build can begin after tests 3 and 4, with the restart left behind an interface until test 5 is in.

**Acceptance.** A flag is a trigger only once seen on this unit: `OB` (seen), the test flag (test 2), `OFF` (test 7). `LB` and the alarm flags are overrides until observed; if `LB` never appears before the unit cuts, it is dropped from the design
and the time cap carries that job.

**Rollout, in steps.** Thresholds start very conservative, ship in a release, are tested against real data, then are reset in a second release. Nothing is lengthened on a guess.

| Step | Thresholds | Mode | Allowed by | Evidence it produces |
|---|---|---|---|---|
| A, floor | `guard_shed_max_seconds` 120, inside the proven 145 s at service load with no knee | dry-run | the per-host `asleep` times (test 4) and the forced-command test (3) | the guard's decisions on real mains events, logged but not acted on |
| B, live and cautious | the same | live | trial 1 at worst-case load with no knee and no `LB`; trials 2 and 3 pass; the restart path chosen | real outages and drills exercise the whole chain |
| C, measured | `guard_shed_max_seconds` set to the knee time less `guard_shed_lead_seconds` | live | trial 5 once on this battery, plus any real outage, fitted offline | the knee at service load, the cutoff, whether `LB` raises |
| reset | recomputed | live | a battery replacement, a load change over about 30%, or a time to the floor 20% below the last fit | a new trial and a release |

- `guard_mains_stable_seconds` is the shortest run of `OL` that a flapping grid has not been seen to break, and long enough that a drained battery has begun to recover (about 6 hours to 90% per the manual, so longer is safer; there is no measure, it is a judgement).
- A single run to the cutoff costs some battery life, so trial 5 is made once per battery. Without it the thresholds stay at step B and waste battery but never risk the servers.
- A reset is a refit from the outage CSVs and history, a new project, a release, and a dry-run period before live; the previous project stays in git.

**Gaps carried from that plan, still open**

| # | Gap | Closed by |
|---|---|---|
| 1 | trials run at average load; the 01:00 backup and service starts raise it | take the worst-case `ups.load` over a week of history and run trial 1 at it, or add the load by hand; `LB` is the backstop |
| 2 | a second dip soon after the first finds a partly drained battery (about 6 hours to 90%) | the guard's clock resets after `guard_mains_stable_seconds` of mains |
| 3 | the battery's age and condition are unknown | not a model input; the fit is of this battery, and a replacement means a new fit |
| 4 | what else is on the UPS (switch, router, access point, the Mac) is not inventoried | **yours:** list the loads on the UPS; the plug's WiFi and the followers' ssh path both depend on them |
| 5 | the offline fit's data path is unchecked | Home Assistant's history of the rackmains entities plus the outage CSVs; confirm Home Assistant records the entities at battery cadence |

## Yours to do

Hands-on steps the code cannot do, in the order they unblock work. Results of the tests and trials are recorded in "Trials, tests and rollout".

1. **Workbook rows** in `entity_metadata.xlsx` (never edited by code): the 27 metric rows under `RackMains` and `service_rackmains` under `Supervisor`, then run `fab generate` and read the diff.
2. **ssh keys:** a forced-command key on all four hosts including `max`, the private key mounted read-only from a root-only directory on `max`, `known_hosts` pinned. The forced-command test (3) proves it.
3. **Tests 3 and 4** (forced command, per-host `asleep` time), then the **spare-plug deadman proof** (test 8) and the **retained `cmnd/POWER` check**.
4. **`mad`'s macOS step** for power-on after a cut, then test 5 on all four hosts.
5. **List what else is on the UPS** (switch, router, access point, the Mac): the plug's WiFi and the followers' ssh path depend on them.
6. **Releases and trials:** the dry-run release, trial 1, trials 2 and 3, and trial 5 once per battery.
7. **Until the guard goes live** the rack is exactly as exposed as it is today, so the dry-run release protects nothing.

## Remaining phases

Decided: step A starts inside the proven 145 s (`guard_shed_max_seconds` 120); trial 5 goes to the cutoff once; trials are cut with `rackmains guard drill`; and there is **one first release carrying the publisher and the guard in
dry-run**, not a publisher alone. Each build step ends in a review (R1 to R4, defined in the next section), and the release waits for R4.

1. **R1, now:** review `rackmains`, `mockdriver`, `tools/schema`, the install hooks and `policy.rs`.
2. **Build metrics and the outage CSV:** the `nut.rs` flag function and `SAMPLES` with the canonical names, the flat MQTT payload and the poll and publish cadence, the outage CSV writer and its backup enrolment (`backup.sh`,
   `write_container_backup()`, the `.env_all` keep values), the heartbeat file and an MQTT-independent `checkhealthy.sh`, the model seam, the module `CLAUDE.md`. Then **R2**.
3. **Yours:** tests 3 and 4, the spare-plug deadman proof and the retained-command check ("Yours to do").
4. **Build the guard, dry-run only:** the root CLI (`serve`, `check`, `guard`) with the image entrypoint and compose command changed to `rackmains serve`; `run` restructured so the poll, the CSV writer and the guard start
   before, and never wait on, the broker connect; the generated host file; `guard_state.json` and `guard_heartbeat`; the ssh runners for `asleep` and `awake`; the state machine with mock sequences; `guard_auto` (`auto.json`, the
   publisher's command subscription, `rackmains guard auto`); `rackmains guard drill|stop|tail|list`. Then **R3**.
5. **R4, final review of the whole module,** then **yours:** the workbook rows and the dry-run release; confirm `rackmains/status` is `online`, the entities appear, and a short `drill` turns `ups_on_battery` on within one poll and off when mains returns.
6. **Trial 1, then test 5 and the restart tests, then trials 2 and 3 live,** recording each result.
7. **Trial 5 once per battery** (`rackmains guard drill drain --force`), fit the model's outputs offline (a new project), release the measured thresholds.

## Open decisions

Consolidated 2026-11-11 and renumbered Q1 to Q21. Each has the question, why it matters, and a recommendation to accept or change. Settled ones are under "Decided" and in the sections above.

**A. Decisions that change behaviour**
- **Q1. Alerting.** Non-zero host results and alarm flags are said to be alerted, with no mechanism. Recommended: no new publisher; Home Assistant automations on `guard_state`, `guard_auto` off for more than 30 min, `rackmains_battery_low`, `rackmains_ups_problem`,
  `battery_replace`, `model_recalibrate` and `Service Rackmains`, plus a new `guard_failed_hosts` count, since events never go to MQTT.
- **Q2. Health from the UPS.** Today only a stale read or heartbeat is unhealthy. Recommended: `rackmains_ups_problem`, `battery_replace` and `model_recalibrate` also make the container unhealthy; `OB` never does.
- **Q3. Monthly calibration.** A deliberate monthly drain is a run to failure on one 9Ah battery, and the manual lists no self-test. Recommended: keep calibration out of rackmains; only `model_recalibrate` feeds health (Q2). A drain is one command
  (`rackmains guard drill drain --force`), which makes a monthly one easy to run and does not change its cost.
- **Q4. Trial 5's stopping point.** The recovered trial 5 stopped at the 11.5 V floor or `LB`, not at the UPS cutting out, to spare the battery; the run-to-failure decision and Q18 both need the cutoff. Recommended: `drill drain` runs to the cutoff, with the deadman as the only stop, once per battery.
- **Q5. Exit codes.** Recommended: mirror `asleep` (`0` ok, `1` error, `2` usage, `4` timeout) plus one code for "aborted, mains restored", returned as an exit error as supervisor does.
- **Q6. A drill against a dry-run guard.** Allow `drill --force` with a loud warning (trial 1 runs in dry-run), or refuse. Recommended: allow.
- **Q7. The plug has no password.** Its API is open on the LAN, so any host can cut the rack or rewrite the deadman rule. Recommended: set a Tasmota web password in `tasmota_config.sh` (outside this module, so your call) and give the drill a
  `RACKMAINS_PLUG_PASSWORD` (a name a release masks).
- **Q8. `guard stop` with no drill running.** Turning the plug on regardless would override a plug that is off for a legitimate reason. Recommended: without a drill it reports the state and changes nothing; `guard stop --force` is the unconditional emergency form.
- **Q9. A ceiling on the model's output.** A bad fit could set `guard_shed_max_seconds` longer than the battery lasts. Recommended: the guard compiles in one absolute ceiling (nameplate-derived, about 3,600 s) and treats a larger response as invalid.
- **Q10. A staleness reminder.** The constants project carries no expiry. Recommended: a Home Assistant reminder after a battery replacement and every six months to look at the trial 1 result, outside rackmains.
- **Q11. Words I cannot map,** need yours: "Turn off patriot auto" and "calibrate fan by MPTT home assistance" (neither word is in the repo and the plan has no fans), and "Make unhealthy driven from Estates from UPS" (recommended: read as UPS status, which is Q2). Left out until explained.

**B. Confirm-only: accept the recommendation or change it**
- **Q12. Call timeout.** 30 s as an ssh connect and silence timeout, not a cap on the whole call, so a deep shed is not cut short; no deep run has been timed (test 4).
- **Q13. Poll and publish cadence.** Poll 2 s on mains and 1 s on battery; publish every 5 minutes on mains and at once on a change, and every poll on battery; one CSV row every 5 s on battery; the model is called every 5 s on battery, at transitions and every 5 minutes on mains.
- **Q14. Outage CSV numbers.** 5 s between rows, 100 files kept (a sidecar going with its CSV), 1 MB per file, whole-document rewrite rather than an fsynced append.
- **Q15. Model state in its own file.** It is rewritten every 5 s on battery. Recommended: its own file, so the configuration and the ack in `guard_state.json` are not rewritten at that rate. The exact `effective` fields wait for the final policy type.
- **Q16. Drill constants.** The ack timeout is 10 s and a stalled heartbeat is 3 polls without a `seq` change. The marker expiry is the planned cut plus hold plus the after-restore cap plus 5 min. `RACKMAINS_GUARD_AUTO_PAUSE_MAX` is 6 h.
- **Q17. Plug sampling and the backup window.** `Status 8` every 5 s (whole watts only); sidecar columns `timestamp`, `elapsed_seconds`, `plug_power_state`, `plug_watts`, `plug_volts`, `plug_amps`, `plug_energy_today_wh`, rewritten whole like the CSV. The 01:00 backup refusal is a fixed window
  (00:45 to 01:45), with no coupling to supervisor. A last outage under 6 h ago, or a battery under 100%, warns and never refuses.

**C. To observe or check, not to decide**
- **Q18. Does the PSDR800 supply its outlets again by itself after a depletion cutoff?** Not in the manual; trial 5 observes it. If not, the fallback is a host-side `shutdown.return` helper (see "Residual risk of running to failure").
- **Q19. Two checks before `guard drill` is trusted:** the rule-timer deadman on the spare plug (test 8), and no retained `cmnd/POWER` for `rack_outlet_plug` on the broker (`mosquitto_sub` from the Mac failed to connect on 2026-11-11, so it needs the broker's credentials or a run from `max`).
- **Q20. The CLI's tests.** Recommended: a parsing test per flag and subcommand as `tempstat`'s `cli_parses_*`, written in the CLI build step.
- **Q21. The `effective` fields and `guard_failed_hosts`.** Fixed when the guard's policy type and the host results are final, in the guard build step.

**Decided, kept for reference**
- **Run to failure, no final UPS command** (2026-11-11), at the top of this file.
- **Model promotion** (2026-11-11). The first release ships the constants project, so a model is always present, and later releases replace it with a fitted one as part of the codebase once data is collected. There are no `static`, `shadow` or `live` modes and no `guard_mode`; `guard_live`
  (dry-run or live) stays deployment config in `.env_prod`. A refit is a release.
- **Guard state file** (2026-11-11). `guard_state.json` with a separate `guard_heartbeat`, as written in "Control plane".
- **`drain` deadman** (2026-11-11). 3 h for the first run with the guard armed, printed in the plan, then set from the measured time to cutoff plus a margin.
- **Trials, tests and rollout restated** from the model plan deleted in commit `ca0c83150`, and **reachability during a drain**, in the sections of those names.
- **The guard CLI** (2026-11-11): `rackmains serve|check|guard auto|drill|stop|tail|list`, plan-only without `--force`, one binary, `guard_auto` with a 30 min default pause, low battery sheds while paused unless `--run-to-failure` (implied by `drill drain --no-shed`), a plug sidecar CSV, recording after restore
  until the CSV `end` row capped at 30 min.
- **Restart shape.** `awake` when mains returns early, `AFTERG3_EN` after a cut; the power-on-after-cut test (5) confirms it per host.
- **`ups_on_battery` stays a read-only `binary_sensor`;** `guard_auto` is the one `switch` row.

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

- **A final UPS command and a deep `asleep` on `max` (`shutdown.return`, `ups.delay.shutdown`, a halt step).** Dropped 2026-11-11. It guaranteed a power cycle
  and a clean unmount of `max` before the cut, but needed either a read-write socket or a host helper, two more thresholds and a state, and left the rack asleep
  with nothing to wake it if mains returned after the halt. Running to failure needs none of them, at the cost of battery wear and a hard cut of `max`.
- **Powering hosts off (`systemctl poweroff`).** A Mac mini that is shut down stays off when power returns; it restarts after a
  cut only from a running state. Replaced by `asleep`, which quiesces a host and leaves it running.
- **Wake on LAN.** Needed only to restart hosts that `poweroff` had left off, and it wants the container on the host network. Dropped
  without testing (`mad` also reports `Wake-on: d`).
- **A smart plug per host** (new hardware) to restart hosts.
- **MQTT between the tool and the guard.** The broker is on `meg`, which is shed first, so it is unusable exactly when the tool needs it.
- **A unix socket or REST API for the tool and for health.** See "Control plane": files carry the state that must survive a restart, and the heartbeat is the honest health signal.
- **The pause held as a retained MQTT topic** (supervisor's reaper keeps its state there). Dropped 2026-11-11 for `guard_auto`: the guard must work with the broker and `meg` shed, so the file is the truth and MQTT is a mirror.
- **A test tool as a host script or in Python.** A second reader of the outage CSV, `auto.json` and the policy, which can drift from the guard's own; replaced by a Rust binary sharing the library.
- **Commanding the plug through Home Assistant or MQTT.** `meg` is shed during a drain, so `drill` uses the Tasmota's local HTTP and an on-device deadman.
- **Pausing the guard by releasing with dry-run flipped.** Too slow and too coarse for maintenance and for trials.

## Deleting this plan

This plan can be deleted once the publisher, the outage CSV, the health check and the guard are implemented and released. Before
deleting, check:
1. **The module `CLAUDE.md` matches the code.** Today it is accurate for the built publisher. When the metrics work lands, update its
   payload, health check and "Home Assistant tests for the `OB` token" lines, and replace "MQTT only" with MQTT plus the outage CSV
   (there is still no database and no InfluxDB writer). Point future modelling work at the `ups/battery` notebook title cell.
2. **Nothing open is lost.** Every open decision here is either settled in the code or `CLAUDE.md`, or copied into the Future of the `ups/battery` notebook title cell.
3. **The final review has run.** Its findings table is empty or every row is fixed or accepted with a reason, and the gates are green.
4. **The module `CLAUDE.md` describes the pause and the drill.** the `serve`, `check` and `guard` commands and the `rackmains serve` entrypoint, `guard_auto` and `auto.json`, the publisher's `rackmains/command` subscription (it currently says nothing subscribes), `rackmains guard drill`, the plug sidecar CSV and the `drill.json` marker.
5. **The notebook title cell has what it needs.** It outlives this plan, so its references back to the unit, the metric names and the outage CSV
   are replaced by that content, or by `CLAUDE.md`, before this file goes.
