# rackmains

**Status, 2026-11-12.** All code phases are built, reviewed twice and tested (unit tests, clippy and `fab test-sys` in the real container), the 29 workbook rows are in and the battery model is released and embedded. What remains is yours: the R4 sign-off, the dry-run release, ssh keys, hardware tests and trials.

| Part | State |
|---|---|
| Publisher (`rackmains/{data,status}`, mock driver, mock-backed system test) | built on the flat canonical payload; unit tests and the container system test pass |
| Host setup (`install_prep.sh`, `install_pre.sh`) | built, unit tested |
| Host side of the shed (`asleep`, `awake`, power-on-after-cut setting, in the `system` module) | built, tested on `max`; a deep run and the power-on-after-cut test are not done |
| Battery model (`ups/battery` notebook, `static` project `rackmains_ups_battery`) | built, released, embedded; signature prefixed `rackmains_`, optional inputs (calibrating, battery low, volts, replace due, age, read failures, state) and outputs (runtime and energy remaining, energy used, refit due and reason, state) wired through `serve.rs` and `policy.rs`; the model is called through failed reads; the guard validates the policy at start |
| Metrics, outage CSV, liveness-file health that does not need MQTT, watchdog, backup enrolment | built, unit tested and run in the container against the mock driver |
| Guard (shed, restore, state machine), dry-run by default | built as a pure state machine with table tests, called from the poll loop; ssh runner built, calling `asleep` and `awake` by absolute path over an unrestricted root key (`asleep --except` in the `system` module), not run against a host; dry-run by default |
| The root CLI, `check`, `guard tail` and `guard list` | built |
| `rackmains guard drill` and `guard stop` | built and exercised end to end against a simulated plug and a real poller; the deadman rule and the `Status 0` parse are unproven on the real plug |
| Workbook rows | done: 29 metric rows (indexes 2450 to 2478) and `service_rackmains`; the topic and schema checks pass |
| Release | not done, waits for R4; the first release is the publisher and the guard in dry-run, `.env_prod` sets `RACKMAINS_GUARD_LIVE=0` |

**Decided 2026-11-11, not built: no final UPS command, run to failure.** The guard sheds the followers and then does nothing more. `max` stays up in
`asleep --shallow` with rackmains and the guard recording until the UPS cuts its own output at its low-battery cutoff, and every host boots on AC restore. There is no
`shutdown.return`, no `ups.delay.shutdown`, no halt step, no `asleep --deep` on `max`, and no host helper or socket write: nothing in this module ever writes anything but
`DUMPALL`. This removes a state, two thresholds and an open decision. The cost, accepted: the battery runs to its cutoff on every outage long enough to shed, and
`max` is cut while running. The one fact it rests on, that the PSDR800 restores its output by itself after a depletion cutoff, is not in the manual and is observed in trial 5
("Residual risk").

**Decided 2026-10-30, not built.** Every metric is published on MQTT for Home Assistant and, during a battery drain, also written to a
CSV in the home dir; there is no InfluxDB writer. Polling is 1 s in both modes, publishing is coarse on mains (a change at once, otherwise every 5 s) and detailed on battery, and health no longer
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
  battery-health entity, no accumulator or Peukert model. Those were designed and dropped for the offline fit. No calibration is scheduled; a drain is run by hand only, with `rackmains guard drill drain --force` (decided 2026-11-12).

## The host, `max`

Set up by the module's own `install_prep.sh`, which runs on `install` and is idempotent. It installs `nut` and `nut-client`
with `dnf` when `rpm` says they are missing and writes `nut.conf` (`MODE=standalone`), `ups.conf` (`driver = nutdrv_qx`,
`port = auto`, `vendorid = 0665`, `productid = 5161`, `protocol = voltronic-qs`, `pollfreq = 4`, to become `1` after trial 1) and `upsd.conf` (`LISTEN`
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
silent failure (the outlets are unprotected) and alerts at once; a test flag is ignored because the shed waits `rackmains_guard_shed_battery_seconds`. The beeper is audible only,
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
| `read` | the poll's own health | `rackmains_read_failures`, `rackmains_read_last_epoch_seconds` |
| `mains` | the supply at the UPS input | `rackmains_mains_input_volts`, `rackmains_mains_input_fault_volts` |
| `output` | what the UPS delivers to the rack | `rackmains_output_volts`, `rackmains_output_hertz`, `rackmains_output_load_pct` |
| `battery` | the battery | `rackmains_battery_volts`, `rackmains_battery_charge_pct`, `rackmains_battery_charging`, `rackmains_battery_low`, `rackmains_battery_replace_due`, `rackmains_battery_age_days`, `rackmains_battery_age_due`, `rackmains_battery_energy_remaining_pct`, `rackmains_battery_runtime_remaining_seconds` |
| `ups` | the unit's own state | `rackmains_ups_status`, `rackmains_mains_failed`, `rackmains_ups_problem`, `rackmains_ups_calibrating`, `rackmains_ups_boost`, `rackmains_ups_trim` |
| `outage` | the last outage, from the CSV `end` row, absent until the first | `rackmains_outage_last_duration_seconds`, `rackmains_outage_last_battery_min_volts`, `rackmains_outage_last_end_epoch_seconds` |
| `guard` | the shutdown guard | `rackmains_guard_state`, `rackmains_guard_live`, `rackmains_guard_mains_seconds`, `rackmains_guard_battery_seconds`, `rackmains_guard_failed_hosts`, `rackmains_guard_last_action_result` |
| `model` | the fitted model's own outputs and state | `rackmains_battery_energy_used_wh`, `model_history_known`, `rackmains_model_refit_due`, `rackmains_battery_state` |
| `plug` | the rack plug's meter, CSV only, filled during a drill | `rackmains_plug_power_state`, `rackmains_plug_watts`, `rackmains_plug_volts`, `rackmains_plug_amps`, `rackmains_plug_energy_today_wh` |

Bools are the integers `1` and `0`, never JSON `true` and `false`, in the payload and the CSV alike. `_pct` and `_seconds` values are
integers too (NUT reports `ups.load` and `battery.charge` as whole numbers), and `_volts`, `_hertz` and `clock_epoch_seconds` are floats, and `rackmains_battery_state` is text holding a JSON object of the model's
state slots by name, recorded in the CSV and the log only. The envelope is not a metric and has no prefix: MQTT `timestamp` and `period_ms`;
CSV `timestamp`, `elapsed_seconds`, `event` and `detail`. A key is absent from the payload when its variable is unreported, and its
CSV cell is blank. `ups.load` is published as *utilisation* so it is never mistaken for the watts of Powercalc's `Home Load`.

```json
{
  "timestamp": "2026-10-30T12:00:00+08:00",
  "period_ms": 1000,
  "clock_epoch_seconds": 1793332800.0,
  "rackmains_read_failures": 0,
  "rackmains_read_last_epoch_seconds": 1793332800.0,
  "rackmains_mains_input_volts": 241.4,
  "rackmains_mains_input_fault_volts": 241.4,
  "rackmains_output_volts": 241.4,
  "rackmains_output_hertz": 50.1,
  "rackmains_output_load_pct": 13,
  "rackmains_battery_volts": 13.4,
  "rackmains_battery_charge_pct": 100,
  "rackmains_battery_charging": 0,
  "rackmains_battery_low": 0,
  "rackmains_battery_replace_due": 0,
  "rackmains_battery_age_days": 730,
  "rackmains_battery_age_due": 0,
  "rackmains_ups_status": "OL",
  "rackmains_mains_failed": 0,
  "rackmains_ups_problem": 0,
  "rackmains_ups_calibrating": 0,
  "rackmains_ups_boost": 0,
  "rackmains_ups_trim": 0
}
```

`period_ms` is the poll period. The `last_outage_*` keys join it after the first outage, in the same position, and the `guard_*` keys when the guard exists, and the model's keys (`battery_remaining_*`
and the `model_*` ones) when a fitted model returns them; the default model returns none of them. The payload no longer has a `samples` object or the old `rack_*_<unit>` keys. The code, `schema.rs`, `system_test.py`, the health check
and the workbook templates all move to these names when built.

**Cadence (decided 2026-11-12).** Poll fast, report coarse: one loop, polled every second in both modes, one decision per poll. Detection is cheap (a local unix socket), so a cut or a return is acted on within one poll; only what is published and written differs by mode. Mains reporting matches Home Assistant's Kasa plug polling (5 s, `custom_components/tplink`).
- **Mode.** On battery from the first `rackmains_mains_failed` until `rackmains_guard_restore_mains_seconds` of unbroken `OL`, which is the guard's own `rackmains_guard_mains_seconds` counter, so there is no second timer. Otherwise on mains. The raw NUT `OB` token starts the mode even when `CAL` suppresses `rackmains_mains_failed`, so a calibration is recorded in full; during `CAL` the timer shed is withheld, and `LB` still sheds.
- **Poll.** Every 1 s in both modes (`-P`). The guard, the status flags and the derived bools are evaluated on every poll, so a status flip is seen and acted on at once. There is no per-mode poll period. The tick is fixed-rate on monotonic `Instant` deadlines: an overrunning poll (a slow socket read, bounded by `-T`) logs a WARN and the next tick starts at once, with missed ticks skipped and never queued. Consecutive failed reads are counted as a duration, 10 s, not as a number of polls, so the 1 s poll does not shorten the time to a reinit.
- **Publish and model call.** One rule: on a poll, publish and call the model if on battery, or if `rackmains_ups_status` or a derived flag changed, or if `--mains-publish-period` (5 s) has passed since the last publish. On mains that is a change at once and otherwise every 5 s (retained); on battery it is every poll. A dip therefore reaches Home Assistant within one poll.
- **File writes.** None on mains. On battery, each poll writes once: the CSV row and every event row since the last poll (command results, notes, decisions), and, on a restart, nothing else is read back: the state is rebuilt from the open file (see "Restart"). During an acked drill the plug columns are filled by a separate bounded sampler thread (see the lead-in below). Nothing writes between polls, so there is no write on an event.
- **The model.** Called whenever a publish happens (every poll on battery, every 5 s on mains); embedded and served alike. The row sent is the poll time, the utilisation and the on-battery and replace flags, with the state the model returned last time. The numbers are recorded with the call, so a recording replays exactly.
- **Reaction latency is the driver's.** The driver refreshes values every `pollfreq` (4 s on `max`), so a cut or a return can take up to `pollfreq` plus one poll to appear, and 1 s rows repeat each value up to four times. Setting `pollfreq = 1` in `ups.conf` (written by `install_prep.sh`, both modes) brings reaction to 1 to 2 s and makes the battery data genuinely 1 s. It adds USB traffic to the unit, which is untested above 4 s, so it stays at 4 until trial 1 shows the unit tolerates 1.

**All metrics: MQTT, CSV and log**

| Name | Source | MQTT | CSV | Log |
|---|---|---|---|---|
| `clock_epoch_seconds` | the poll time as seconds since the epoch, converted at source from `timestamp` | yes | yes | DEBUG per poll |
| `rackmains_mains_input_volts` | `input.voltage` | yes | yes | DEBUG per poll |
| `rackmains_mains_input_fault_volts` | `input.voltage.fault` | yes | yes | DEBUG per poll |
| `rackmains_output_volts` | `output.voltage` | yes | yes | DEBUG per poll |
| `rackmains_output_hertz` | `output.frequency` | yes | yes | DEBUG per poll |
| `rackmains_output_load_pct` | `ups.load` | yes | yes | DEBUG per poll; derived in `end`: peak and mean while on battery |
| `rackmains_battery_volts` | `battery.voltage` | yes | yes | DEBUG per poll; derived in the CSV `end` row: minimum and when, the sag at transfer, the last value |
| `rackmains_battery_charge_pct` | `battery.charge` | yes | yes | DEBUG per poll; derived in `end`: charge at start and end |
| `rackmains_battery_charging` | `CHRG` | yes | yes | DEBUG on change |
| `rackmains_battery_low` | `LB` | yes | yes | INFO on change, with the seconds since `OB` and the voltage |
| `rackmains_battery_replace_due` | `RB` | yes | yes | INFO on change |
| `rackmains_battery_age_days` | whole days since `RACKMAINS_BATTERY_INSTALLED`, from the wall clock at each publish | yes | yes | DEBUG per publish |
| `rackmains_battery_age_due` | `rackmains_battery_age_days` at or over 1095 (3 years, the start of the manual's 3 to 5 year service life at 25 °C) | yes | yes | INFO on change |
| `rackmains_battery_energy_remaining_pct` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call, beside what actually happened |
| `rackmains_battery_runtime_remaining_seconds` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call; INFO when it falls to a lead threshold |
| `rackmains_ups_status` | `ups.status` flags, text | yes | yes | INFO on every change: the flags before and after, with the derived bools |
| `rackmains_mains_failed` | `OB` and not `CAL` | yes | yes | INFO on change; starts and ends the outage CSV; derived: time on battery |
| `rackmains_ups_problem` | `OFF` `OVER` `BYPASS` `FSD` `ALARM` | yes | yes | INFO on change |
| `rackmains_ups_calibrating` | `CAL` | yes | yes | INFO on change |
| `rackmains_ups_boost` | `BOOST` | yes | yes | DEBUG on change |
| `rackmains_ups_trim` | `TRIM` | yes | yes | DEBUG on change |
| `rackmains_guard_state` | the guard, text | yes | yes | INFO on every transition, with the inputs and the threshold compared (a `decision` row); derived: seconds to each step |
| `rackmains_guard_live` | the guard | yes | yes | in the `start` row's detail; in dry-run every command is logged as would-run |
| `rackmains_guard_mains_seconds` | the guard | yes | yes | `note` rows counting down to `rackmains_guard_restore_mains_seconds` |
| `rackmains_guard_battery_seconds` | the guard | yes | yes | on every `decision` row |
| `rackmains_guard_failed_hosts` | the guard, hosts whose last `asleep` or `awake` returned non-zero | yes, same | yes | WARN on a change to non-zero, naming the hosts |
| `rackmains_guard_last_action_result` | the guard, text: the last command's host and `RESULT` status | yes, same | yes | INFO on every command |
| `rackmains_battery_energy_used_wh` | the model, an optional output | yes, once a fitted model returns it | yes | DEBUG per call |
| `model_history_known` | the model, an optional output | yes, once a fitted model returns it | yes | INFO on change |
| `rackmains_model_refit_due` | the model, an optional output | yes, once the model returns it | yes | WARN on a change to 1, with the reason from the response `parameters` |
| `rackmains_battery_state` | the model's state as one JSON text of the named state slots | no, not published | yes, on the `start` and `end` rows and on a restart, reset or project change, blank otherwise | INFO on those rows; DEBUG on every call when the debug switch is on |
| `rackmains_plug_power_state`, `rackmains_plug_watts`, `rackmains_plug_volts`, `rackmains_plug_amps`, `rackmains_plug_energy_today_wh` | the plug sampler thread, only while an acked drill marker exists | no | yes, blank outside a drill and when the plug is unreachable | DEBUG per sample |
| `timestamp`, `period_ms` | the poll | yes | `timestamp`, `elapsed_seconds` | DEBUG per poll |
| events: transitions, decisions, commands, notes, summary | rackmains, the guard | **never** | yes, the `event` and `detail` columns | INFO. Command timings and host results (`asleep`, `awake`: start, `RESULT` status, `took`) live only here and in the CSV. The `end` row holds the summary: duration on battery, minimum voltage and when, peak utilisation, whether `LB` raised, steps reached, hosts shed |
| service health, the `Service Rackmains` switch | the container's health check, from the liveness file and independent of MQTT | none from rackmains, supervisor publishes it | no | none here, supervisor logs it |
| outage count | dropped | no | no | the `end` row's duration for that outage; a count is a query over `rackmains_mains_failed` |
| `ups.temperature` | not reported by the unit | no | no | no |
| plug watts | not collected | no | no | no |
| `rackmains_read_failures` | the poll, consecutive failed reads, `0` after a good read | yes, on every change, so a dead UPS link shows while the rest of the payload is stale; in memory only, a restart resets it | a `note` row during an outage | WARN per failed read, INFO on a reinit |
| `rackmains_read_last_epoch_seconds` | the poll time of the last good read | yes, with the same publishes | yes | DEBUG per poll |
| `rackmains_outage_last_duration_seconds` | the CSV `end` row, duration on battery | yes, retained; published when the outage ends and replayed on every broker reconnect and on start from the newest CSV `end` row | the `end` row | INFO in the `end` row |
| `rackmains_outage_last_battery_min_volts` | the `end` row, minimum battery voltage | yes, same | the `end` row | same |
| `rackmains_outage_last_end_epoch_seconds` | the `end` row, when mains returned | yes, same | the `end` row | same |
| transfer reason, test result, charger status, beeper, identity | mostly not reported by this unit | no | a `note` row during an outage | INFO on change, identity once at start |

**The service status switch** is Home Assistant's `Service Rackmains` switch under `Supervisor`, like `service_tempstat`: `Service Status`
domain, `Diagnostics` group, state topic `supervisor/macmini-max/data/service/rackmains/health_status`, `ON` when the container's
health check passes. Supervisor publishes it, so rackmains publishes nothing for it.

**Health does not depend on MQTT (decided 2026-10-30).** A drain sheds the broker's host with the other servers, so a health check
that read `rackmains/data` from the broker would fail exactly when rackmains is doing its job, and the switch would read OFF during
every outage.
- **Liveness file (decided 2026-11-12).** The compose file mounts a tmpfs at `/run/rackmains`, so liveness costs no disk write. Each poll the poller replaces `/run/rackmains/liveness.json` (a `.tmp` and a rename, no fsync, since a lost one is harmless) with `boot_ms` (when it was written), `last_read_boot_ms` (the last good read), `guard_boot_ms` (the guard's last iteration) and `ups_problem`. All stamps are the boot clock (`CLOCK_BOOTTIME`), never the wall clock, so a clock step on `max` cannot make a healthy loop look stale or a dead one fresh. A failed or stale read (`DATASTALE`, an unplugged UPS) does not move `last_read_boot_ms`, so the container turns unhealthy by the same path as before.
- **`checkhealthy.sh`** compares each stamp with `/proc/uptime` and fails when `boot_ms`, `last_read_boot_ms` or, once the guard exists, `guard_boot_ms` is older than about 30 s (a few polls, unrelated to the 5 s mains publish), or when `ups_problem` is set. It no longer runs `mosquitto_sub` or `jq`, and needs neither the broker nor a payload. `rackmains_battery_replace_due`, `rackmains_model_refit_due` and `rackmains_battery_age_due` are alerts only and never drive health, since they can stay set for months; `OB` never makes the container unhealthy (decided 2026-11-12). Its test is a liveness file with `ups_problem` set giving unhealthy, and `OB`, `rackmains_battery_replace_due`, `rackmains_model_refit_due` and `rackmains_battery_age_due` each leaving it healthy. The compose health check runs every 10 s with 3 retries, since it only reads a file.
- **Watchdog (decided 2026-11-12).** Docker never restarts an unhealthy container, only an exited one, so detection alone leaves a hung guard hung. A small thread in the process aborts it, and Docker restarts it, when the poller's or the guard's in-memory progress counter has not moved for 10 s, well above the `-T` socket timeout. A restart mid-outage is safe by design (the open CSV is closed `interrupted` and the guard is rebuilt from it). The CSV writer and the publisher are not watched this way: a stalled writer logs a WARN, since a detaching disk is already handled by the writer's own isolation, and a stalled publisher is the broker's concern.
- **MQTT trouble is reported, not fatal.** A broker that is down at start does not stop the process or the poll loop, and a lost
  connection never counts toward `MAX_CONSECUTIVE_FAILURES` or a reinit. Publishing is best effort through a bounded queue that
  drops while disconnected, and rackmains reconnects with backoff. The loss and the return are each one log line, WARN on mains and
  INFO during an outage when it is expected, with a `note` row in the outage CSV. On reconnect it publishes `online` and the full
  current payload so Home Assistant catches up. The broker's own last will still says `offline`, which is how Home Assistant sees it.
- **Alerting (decided 2026-11-12).** No new publisher. Home Assistant automations, built outside this module, on `rackmains_guard_state`, `rackmains_battery_low`, `rackmains_ups_problem`,
  `rackmains_battery_replace_due`, `rackmains_battery_age_due`, `rackmains_model_refit_due`, `Service Rackmains`, `rackmains_read_failures`, `rackmains_guard_failed_hosts`, `rackmains_guard_last_action_result` and the `last_outage_*` entities. These are state, not events: each is computed without the broker, written to the CSV, and replayed once the broker returns, so an alert reads them in normal running and never relies on MQTT during a drain. No reminder to review the constants after a battery change or on a schedule is set up (decided 2026-11-12). Alerts need Home Assistant, so a power cut alerts within the first poll or two while `meg` is up, about 2 minutes before the shed; after that the state is read once the broker returns.

**Battery age (decided 2026-11-12).** `RACKMAINS_BATTERY_INSTALLED` in `.env_all` is the battery's install date as `YYYY-MM-DD`, assumed `2024-11-12` until you give the real one. `rackmains_battery_age_days` is computed from it and the wall clock at each publish, so there is no counter to store or restore, and a replacement is one edit and a release. `rackmains_battery_age_due` turns on at 3 years, the start of the manual's service life of 3 to 5 years at 25 °C. The UPS reports no temperature, so the ambient assumption is unchecked and a warm rack shortens life; read 3 years as the point to start checking, not the replacement date. A 5 year hard threshold is a Home Assistant automation on the age. Both are separate from `rackmains_battery_replace_due`, which stays the unit's own `RB`. A run to failure ages the battery beyond its calendar age, and counting those is left out. Neither drives health.

**`ups.status` to bools.** One pure function in `nut.rs`, with a table test over `OL`, `OB DISCHRG`, `OB LB`, `OL BOOST`, `OB CAL`,
`OFF`, an unknown token and empty. All derived bools are absent when `ups.status` is unreported, so Home Assistant keeps its last
state and a failed read never reads as an outage or a problem.

| NUT token | Resolves to | Logged |
|---|---|---|
| `OL` | `rackmains_mains_failed` 0 | no |
| `OB` | `rackmains_mains_failed` 1, unless `CAL` is present | INFO on change |
| `LB` | `rackmains_battery_low` | INFO on change |
| `RB` | `rackmains_battery_replace_due` | INFO on change |
| `OFF`, `OVER`, `BYPASS`, `FSD`, `ALARM` | `rackmains_ups_problem` | INFO on change |
| `CAL` | `rackmains_ups_calibrating`, and suppresses `rackmains_mains_failed` so a deliberate calibration is not an outage | INFO on change |
| `CHRG` | `rackmains_battery_charging` | DEBUG on change |
| `BOOST`, `TRIM` | `rackmains_ups_boost`, `rackmains_ups_trim` | DEBUG on change |
| `DISCHRG`, `HB` | nothing | DEBUG |
| any other token | nothing | WARN once per new token |

Decisions behind it (2026-10-30). `rackmains_mains_failed` and `rackmains_ups_problem` are separate so each entity means one thing and `BYPASS` never
reads as a power cut. `CAL` suppresses `rackmains_mains_failed` so a calibration does not add an outage in Home Assistant's history, but the mode, the CSV and the time-on-battery clock key on the raw `OB` token, so a calibration or a real cut during one is recorded in full; the timer shed is withheld during `CAL` and `LB` still sheds. The `OB` test moves out of
the Home Assistant template and into the service, which gives it one owner and a test; this reverses the module `CLAUDE.md` line
"Home Assistant tests for the `OB` token", to be updated when built.

**Standard logging** goes to stdout, which Docker keeps (the compose file already rotates 5 files of 100 MB). INFO is one line per
event a human watching wants: start, every change of `rackmains_ups_status` or a derived flag, every command the guard runs and its result,
every CSV written or failed. DEBUG is everything per poll: each reading with its derived bools and each MQTT publish. During an
outage the logging is heavy: every guard decision with its inputs and the threshold it compared, and in dry-run the exact command it
would have run. Every log line and every CSV `detail` that mentions a metric uses its canonical name with the value in square
brackets, for example `change rackmains_ups_status [OL] to [OB DISCHRG]`, so a log line, a CSV row and the payload can all be found by
one string.

**Data dir layout (decided 2026-11-12).** Everything rackmains writes to disk is under one directory, `/asystem/mnt` in the container and `/home/asystem/rackmains/latest` on the host (`${SERVICE_DATA_DIR}`, mounted by the compose file; `RACKMAINS_DATA_DIR`, `--data-dir`). It has two subdirectories, records and operator input, so a person finds each by its name:

```
/asystem/mnt/                                        host: /home/asystem/rackmains/latest/
  outage/                                            the records, backed up
    rackmains_outage_2026-11-12_14-03-27_1.csv       main program, the only writer, one file per 1 MB of an outage
    rackmains_outage_2026-11-12_14-03-27_2.csv       the continuation, same stem, next number
  state/                                             operator input, never backed up
    drill.json                                       drill tool

/run/rackmains/                                      tmpfs in the container, not on the host, gone on a container restart
  liveness.json                                      poller and guard, read by checkhealthy.sh and, once built, the drill tool
```

- **Timestamps (decided 2026-11-12).** Every timestamp rackmains writes to disk, in a file name, a CSV column or a JSON field, is Perth time as `YYYY-MM-DD_HH-MM-SS`. Perth has no daylight saving, so it is unambiguous and sorts as text. The exception is the MQTT payload's `timestamp`, which stays ISO 8601 because Home Assistant's `timestamp` device class requires it.
- **Naming.** `rackmains_outage_<timestamp of the first row>_<n>.csv`, `n` from 1 and the same stem for the whole outage; the first row is the first `OB`, or the start of an acked drill's lead-in. There is no sidecar: the five `plug_*` columns are in the CSV, blank outside a drill. `guard list` and `guard tail` order by stem, then by `n` as a number.
- **Why two directories.** `outage/` holds only records and is the whole backup include list; `state/` holds a file that must never be restored (a stale marker) and so needs no exclude list. The guard's own status is not on the host disk at all.

**The outage CSV**, on the data dir the compose file already mounts (`${SERVICE_DATA_DIR}` on the host, `/asystem/mnt/outage/` in
the container), so it is on the host's disk and survives Docker stopping.
- **Name and span.** `rackmains_outage_<timestamp of the first row>_<n>.csv` (see the layout above). An outage starts at the first `OB`, or at the lead-in of an acked drill, and
  ends after `rackmains_guard_restore_mains_seconds` of unbroken `OL`, the guard's own clock, so dips closer together than that are one file. A drill's file that never sees an `OB` ends with an `end` row whose detail is `aborted` when its marker is deleted or expires, or after `rackmains_guard_restore_mains_seconds` of `OL` counted from its first row.
- **Columns.** `timestamp`, `elapsed_seconds`, `event`, `detail`, then every metric above in table order, headed by its canonical
  name. Every row repeats the last known value of every metric, so a row stands alone and a blank cell means never reported. `event`
  is empty on a plain sample and otherwise one of `start`, `status`, `decision`, `command`, `note`, `end`; `detail` is free text,
  quoted as RFC 4180, on one line. `start` carries the version, the model version and whether the guard is dry-run or
  live. A row is written every poll (1 s) on battery, on every change of status or flag, and for each guard decision, command and note. A row with no
  event, or a `start` or `status` event, is also **one model call**: its numbers are the request and the outputs are in the row. The state
  is recorded as `rackmains_battery_state` only on the `start` row (the state in), the `end` row (the state out) and on a restart, reset or
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
    row every 1 s on battery whatever the broker is doing, so the CSV is the complete series and the InfluxDB data is a subset of it;
    forward-fill the InfluxDB side to compare. Timestamps differ by the publish and receive delay: the CSV time is the poll, the
    InfluxDB time is when Home Assistant fired the event.
- **Call logs (2026-11-13).** Each live `asleep` or `awake` call writes `outage/rackmains_call_<timestamp>_<host>_<verb>.log` from its own call thread when it returns: the host, command, status and time, then the whole stdout and stderr. The host's `/run/asleep.log` and `/run/awake.log` hold the same detail but are tmpfs, truncated by the next run and lost with the reboot a power cut brings, so these are the durable copy. They are backed up with `outage/`, the newest 400 are kept (about 100 outages of four hosts), the outage prune and recovery ignore them, and a failed write is a WARN that never changes the call's result. Dry-run writes none.
- **Safe write.** The whole file is rebuilt from the in-memory rows, written to `<name>.tmp` in the same directory, fsynced, renamed
  over the final name, and the directory fsynced, so the file on disk is always the whole previous version or the whole new one,
  never torn. A write happens once per tick (1 s on battery), carrying every row since the last one. A run to failure therefore loses at most the rows since the last rename.
- **Write budget.** On battery each tick costs one CSV rewrite and fsync (up to 1 MB); `liveness.json` is a rename on tmpfs, and `drill.json` is written rarely. The combined load is measured in the resource check (review pass 10); if the SSD wear is judged too high the CSV becomes an fsynced append of whole lines, the one reader tolerating a partial last line.
- **Small.** About 300 bytes a row, so 1 MB holds about 3,300 rows, or about 55 minutes at one row every second. Past 1 MB the file continues
  in the next numbered file, so no rewrite is ever larger than that.
- **Works with everything else asleep.** It needs only this container and a writable data dir. `asleep --shallow` on `max` leaves
  `/home` writable and unmounts only what no running container holds; confirm `${SERVICE_DATA_DIR}` is under `/home`. The broker on
  `meg` is shed with the other servers, so MQTT publishing is best effort (a bounded client queue that drops when disconnected) and
  the CSV is the only complete record of a real outage.
- **Independent of everything else.** A dedicated writer thread behind a bounded channel does the writing, so a slow or failed write (a
  disk detaching) logs a WARN to stdout and never blocks the poll, the publisher or the guard. The in-memory rows keep growing, so
  the next write carries everything and a failure costs time, not rows.
- **Recovery.** On start, a stray `.tmp` is deleted, and a file whose last row is not `end` belongs to a process that was killed or
  lost power mid-outage: it is rewritten atomically with an `end` row whose detail is `interrupted`, timed at its last row. If the UPS
  is still on battery a new file starts, and its `start` row names the interrupted one; the hosts are not tracked, since `awake` is run on every host at restore.
- **Bounded.** The newest 100 files are kept (`RACKMAINS_OUTAGE_LOG_KEEP`, a module setting so it carries the module prefix), pruned only after a new file has been renamed into place and never
  the current or newest one; pruning is safe because the backup below is additive. The `outage/` and `state/` directories are created at start, since
  the backup's include list fails on an absent directory.
- **Backed up, as the other modules are.** rackmains enrols with `write_container_backup()` and a `src/build/resources/backup.sh`
  whose include list is `outage` and whose only exclude is `*.tmp`; `state/` is not in it, so a restore never brings back a stale marker. Supervisor's policy then applies:
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

**Reading the CSV as data (decided 2026-11-12).** Three rules for anything that fits a model from the outage files.
- **Timestamps.** `timestamp` in the CSV is Perth time as `YYYY-MM-DD_HH-MM-SS`, as in the layout above.
- **Repeated values.** The driver refreshes every `pollfreq` (4 s on `max`) and a row carries no value age, so consecutive rows repeat each reading. The `start` row's detail records the `pollfreq`, and a consumer takes the first row of each run of identical battery readings as the reading.
- **The label.** The time of the cutoff is the `timestamp` of the last row of a file closed `interrupted` whose last row has `rackmains_mains_failed` `1`, which is a run to failure, within one tick of the real cutoff. A file ended by a normal restore has no cutoff and gives no label. The model's own `rackmains_battery_runtime_remaining_seconds` column is its estimate, never the label.

**Short outages (decided 2026-10-28, revised 2026-10-30).** A one-second cut at 18:05:25 showed as `OB DISCHRG` in one 2 s recorder
sample and was gone by the next, so a slow poll would usually miss it. The poll is therefore 1 s even on mains, and any status
change publishes at once, so Home Assistant's history records the start and end of every dip the driver saw. A dip that falls
between two driver refreshes is still unseen. Outages are counted from Home Assistant's history of `rackmains_mains_failed`, not in the
service.

`rackmains_battery_charge_pct` is NUT's coarse estimate, from the battery voltage against `battery.voltage.low` and `.high`; the guard
never uses it.

**Guard metrics.** The guard's metrics join the payload when the guard exists, and each gets its own workbook row, `Enabled` for the
dry-run release, so nothing is added later by surprise. `rackmains_guard_state` is one of `idle`, `waiting`, `shedding`, `holding`,
`restoring`; `rackmains_guard_live` is off while in dry-run; `rackmains_guard_mains_seconds` is the seconds on line since
the previous outage ended, absent when unknown; `rackmains_guard_battery_seconds` is the guard's accumulated time on battery.

## Workbook rows to add to `entity_metadata.xlsx`

Every payload metric except `clock_epoch_seconds` (in the payload, the CSV and the log only), `rackmains_battery_state` (in the
CSV and the log only) and the model's five optional outputs (`rackmains_battery_energy_remaining_pct`, `rackmains_battery_runtime_remaining_seconds`, `rackmains_battery_energy_used_wh`, `model_history_known`, `rackmains_model_refit_due`, whose rows are added when a fitted model ships, as a sensor in `%`, a `duration` sensor in `s`, a `Wh` `energy` sensor, a `binary_sensor` and a `problem` `binary_sensor`) gets a row, `Enabled`, all `device_via_device` **`RackMains`**, in
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
| `rackmains_output_load_pct` | `sensor` | % | |
| `rackmains_battery_volts` | `sensor` | V | `voltage` |
| `rackmains_battery_charge_pct` | `sensor` | % | `battery` |
| `rackmains_battery_charging` | `binary_sensor` | | `battery_charging` |
| `rackmains_battery_low` | `binary_sensor` | | `battery`, on means low |
| `rackmains_battery_replace_due` | `binary_sensor` | | `problem` |
| `rackmains_battery_age_days` | `sensor` | d | `duration` |
| `rackmains_battery_age_due` | `binary_sensor` | | `problem` |
| `rackmains_ups_status` | `sensor`, text | | |
| `rackmains_mains_failed` | `binary_sensor` | | |
| `rackmains_ups_problem` | `binary_sensor` | | `problem` |
| `rackmains_ups_calibrating` | `binary_sensor` | | `running` |
| `rackmains_ups_boost` | `binary_sensor` | | |
| `rackmains_ups_trim` | `binary_sensor` | | |
| `rackmains_guard_state` | `sensor`, text, with the guard | | |
| `rackmains_guard_live` | `binary_sensor`, with the guard | | |
| `rackmains_guard_mains_seconds` | `sensor`, with the guard | s | `duration` |
| `rackmains_guard_battery_seconds` | `sensor`, with the guard | s | `duration` |
| `rackmains_guard_failed_hosts` | `sensor`, with the guard | | |
| `rackmains_guard_last_action_result` | `sensor`, text, with the guard | | |
| `rackmains_read_failures` | `sensor` | | |
| `rackmains_read_last_epoch_seconds` | `sensor` | | `timestamp` |
| `rackmains_outage_last_duration_seconds` | `sensor` | s | `duration` |
| `rackmains_outage_last_battery_min_volts` | `sensor` | V | `voltage` |
| `rackmains_outage_last_end_epoch_seconds` | `sensor` | | `timestamp` |

Shared by every row, mirroring `TempStat`: `entity_status` `Enabled`, `unique_id_device` `macmini-max`, `entity_domain`
`Device Conditions Rack`, `entity_group` `Diagnostics`, `device_suggested_area` `Rack`, `_device_name_suffix` `Mains`,
`device_manufacturer` and `device_model` the UPS's own, `device_sw_version` `ASYSTEM_VERSION`, `qos` `1`, `force_update`
`false`, `powercalc_enable` and every `powercalc_group_*` blank. `state_class` is `measurement` for every numeric sensor. Check what
`sample_period` drives: it was `60` for a 60 s publish, and the mains publish is now every 5 s, so it must match that or the
entity may read as stale between publishes.

A numeric sensor keeps its last state when its key is absent, so a failed read never reads as a value of zero:

```
{{ (value_json['rackmains_battery_volts'] | float(None)) if value_json['rackmains_battery_volts'] is defined else (states('sensor.rackmains_battery_volts') | float(None)) }}
```

A binary sensor row sets `payload_on` to `1` and `payload_off` to `0`, so its template returns the integer itself and, when the key
is absent, re-emits its own current state as an integer. No existing MQTT `binary_sensor` row sets those two columns (the 31 enabled
binary sensors in the workbook are template, UniFi, Sonoff and SenseMe entities), so there is no sibling to copy them from:

```
{{ value_json['rackmains_mains_failed'] if value_json['rackmains_mains_failed'] is defined else (1 if is_state('binary_sensor.rackmains_mains_failed', 'on') else 0) }}
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

## The shutdown guard (built)

**Why here and not `upsmon`.** The wanted behaviour is staged and reversible: shed the others, then `max`, or bring the
others back if mains returns. `upsmon` knows on-battery, low-battery and forced shutdown, so it cannot restore. A state
machine with hysteresis and a restart mid-sequence is easy to test in Rust against a mock driver and a mock ssh.

**Shape (decided).** A thread inside the one rackmains container, started by `run` before the publisher loop: one binary, one
image, one health check, and no change elsewhere.
- **One poller (decided 2026-11-12).** A single thread reads the socket, once per poll, and hands each reading to the guard, the CSV writer and the publisher over bounded channels, so they never disagree on a reading and the unit sees one `DUMPALL` per poll. It never touches MQTT, so the guard is already running when the broker is unreachable (`meg` down); `run` today connects to the broker before it polls, and that order changes.
- **Backpressure (decided 2026-11-12).** Only the guard's channel is allowed to apply backpressure, and the poller never blocks on any channel. The publisher's queue is bounded and drops when full. The CSV writer owns its row buffer, which grows at about 300 B a second if the disk stalls, and warns. A stalled writer or publisher therefore never delays a poll or the guard.
- It reads the socket and writes only `DUMPALL`, so the mount stays `:ro`; no UPS command is ever sent, by the guard or by a host helper.
- It needs the ssh keys (a dedicated key, mounted read-only from a root-only directory on `max`, `known_hosts` pinned,
  `openssh-client` pinned in the image), the generated host list, and the model's policy. It keeps no record of who it shed: each host's own `/run/asleep.state` is that record, and the open outage CSV is the guard's journal.
- A panic ends the process (release profile aborts) and Docker restarts it (which needs `restart:` to be `unless-stopped` or `always` in every environment, so the compose `SERVICE_RESTART` value is checked, test 12), and the watchdog (see "Metrics") aborts it when the poller or guard stops making progress. The health check reads the guard's stamp from `/run/rackmains/liveness.json`. The guard hands its metrics to the publisher over a channel.
- Every action is idempotent. A sequence starts only on a fresh reading that says on battery and a restore only on a fresh
  reading that says mains; once started, failed or stale reads do not stop it, because a USB glitch mid-outage must not leave
  the servers up until the battery is flat.
- The host list is generated by `fab generate`: workbook `Server` rows that are `Enabled`, area `Rack`, model starting
  `MacMini` (`mad`, `max`, `may`, `meg`; `jen` is a Pi in `Wardrobe`), ordered by `.hosts`, joined as `macmini-<label>`, MACs
  from the same rows. Nothing is typed twice.
- **`awake` is safe after a reboot.** `/run/asleep.state` is tmpfs and a reboot clears it; with no record `awake` restores from fstab alone and waits for the containers to be healthy. So the guard runs it on every host in the host list at restore, after a hard cut or not, and its health wait is the confirmation that the host came back. This needs `awake` to be harmless on a host that is already awake, which is untested (test 11).
- **Calling `asleep` and `awake`.** The guard shuts servers down and wakes them with these two scripts and nothing else, and a host
  is never powered off. Both are **synchronous**: the call blocks until the script has finished and verified its own work, and its
  exit status says how it went, so the guard never polls a host to learn whether it is done. Over ssh the exit status is the
  script's (`0` ok, `1` error, `2` usage, `3` not root, `4` timeout, `5` unclean, `6` unhealthy), the last output line
  `RESULT <command> status=… reason=…` gives the reason, and an ssh status of `255` is a host that could not be reached.
- **Parallel when asked.** The guard's runner takes a list of hosts, a command and whether to run them in parallel. A parallel request
  starts one worker per host, each making its own blocking call, and joins them as they return; a sequential one runs them in order.
  Workers report over a channel, so the guard's own loop keeps polling and deciding while a shed or a wake is running. Each result is a `command` row in the outage CSV (host,
  command, exit status, reason, how long it took). A non-zero result is logged and alerted and never
  retried in a loop.
- **One call per host at a time.** The guard keeps which host has a call in flight in memory, and the guard never starts `awake` on a
  host whose `asleep` has not returned, so the two cannot race.
- **Every call has a 30 s timeout (decided 2026-10-30)**, as for anything that can reach failing hardware. It is applied to the ssh
  connection and to silence: `ConnectTimeout` of 30 s, and a keepalive window of 30 s (`ServerAliveInterval` times
  `ServerAliveCountMax`), so a dead or hung host frees its worker within 30 s and is recorded as unreachable. It is **not a cap on the
  whole call**: a deep `asleep` can legitimately run for minutes, since each container gets its own stop grace (120 s by default), and
  the script bounds itself and exits `4` on its own timeout. Capping the whole call at 30 s would cut a deep shed short while the host
  carried on, leaving the guard not knowing whether `asleep` had finished.

**Steps (first version, timers and flags only).** The host actions are `asleep` and `awake` from the `system` module (the
next section). A host is never powered off.
1. **Watch.** Polls every 1 s in both modes. Time on battery accumulates from the first `OB`, so a short blip simply never reaches
   `rackmains_guard_shed_battery_seconds`, and resets to zero only after `rackmains_guard_restore_mains_seconds` of continuous `OL`, so a grid that flaps with dips under that apart cannot keep the
   servers up.
2. **Shed.** At `rackmains_guard_shed_battery_seconds` on battery, or `LB`: run `asleep --deep` on the followers in parallel, `meg` last so Home
   Assistant and the broker outlast the rest, each over ssh with a key whose `authorized_keys` forces the command (`restrict`,
   no shell; see the ssh test), each call synchronous, so it is done when the call returns, and `0` means it completed cleanly. Any other code (1 error, 4 timeout,
   5 unclean) is logged and alerted and the guard moves on; it never retries in a loop. On `max`, run `asleep --shallow`
   stopping every container but rackmains (supervisor first, it binds `/`). A shed is not undone by the voltage rebound when
   the load drops, only by `rackmains_guard_restore_mains_seconds` of mains.
3. **Run to failure.** Nothing more is done after the shed. rackmains and the guard stay up on `max` (shallow) and keep polling and
   recording until the UPS cuts its own output at its low-battery cutoff, and every host then boots on AC restore (power-on-after-cut
   test, below). If mains returns at any point before the cut, step 4 runs as normal, because nothing was ever past the point of return.
4. **Mains returns first.** After `rackmains_guard_restore_mains_seconds` of continuous `OL`, run `awake` on `max` to restart what was
   stopped, and on every follower, whether or not its `asleep` ran, in the reverse of the shed order: `max`
   first, then `meg`, then the remaining followers in parallel (decided 2026-10-30). Each call is synchronous and its exit status says whether the host came back
   healthy (`6` is a container not running or healthy). `asleep` is undone by `awake`, so unlike
   a `poweroff` there is nothing to wait on being down.
5. **Blind restore (decided 2026-11-12).** If reads fail continuously for 2 x `rackmains_guard_restore_mains_seconds` (10 min) after a shed, the guard runs step 4 without having seen `OL`. The broker and Home Assistant are on `meg`, which is shed, so no alert can reach you, and without this rule the hosts stay asleep after mains returns if the UPS link is lost. The cost is waking hosts on a guess when the outage is still going; a host woken that way is cut by the UPS cutoff exactly as it would have been, so the downside is bounded. It is a `decision` row and a WARN. You can raise the wait or turn it into a stay-asleep rule by changing this one step.
**Safety rails.** It ships in dry-run, logging the exact commands it would run, and goes live only after the trials (see "Trials, tests and rollout") show the
conservative timers fit. In dry-run the `LB` override is logged as the command it would run and nothing is shed. It compiles in one absolute ceiling on `rackmains_guard_shed_battery_seconds` (nameplate-derived, about 3,600 s) and treats a larger model response as invalid, so a bad fit cannot set a shed time longer than the battery lasts (decided 2026-11-12). The keys can
run `asleep` and `awake` and nothing else. Any status flag that is not `OL` is surfaced; an alarm or fault flag raises an alert in Home
Assistant.

**Guard tests.** Table-driven over mock readings and a mock ssh runner: a flapping grid (40 s dips 100 s apart shed at the accumulated 120 s, and 300 s of `OL` resets the clock), `LB` in dry-run and live, failed reads mid-outage not stopping a sequence, the blind restore, a restart mid-sequence, and a stalled writer or publisher not delaying a poll. Each decision rule is deleted once to prove its test fails.

**Later.** The decision (reading and history in, action out) stays a pure function apart from the state machine and the
runners, so the timer policy is replaceable; if a better policy is ever wanted it is fitted offline like the thresholds (the Future of the `ups/battery` notebook title cell).

**Residual risk of running to failure (decided 2026-11-11).**
- **Output may not restore after a depletion cutoff.** The manual says only that the unit starts by itself when plugged in, that "Standby" is
  connected to utility with outlets **not supplied**, and, under troubleshooting, to recharge for at least 6 hours and start again after a low battery. If the PSDR800 comes
  back from a depletion in Standby, no host boots and the rack stays dark until someone presses the button. Trial 5 observes this: after the
  cutoff restore mains and record whether the outlets are supplied without a button press, and how long it takes. If they are not, revisit by
  adding a host-side helper that sends `shutdown.return` over the guard's ssh key, since that is the only command that guarantees a power cycle.
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

**The rule.** MQTT is used only when the cluster is in normal operation: it mirrors state to Home Assistant. Everything a guard action or a trial needs works with
`meg`, the broker and Home Assistant shed: files in the data dir, the Tasmota plug's local HTTP, ssh to the hosts, and the driver socket. Health is the liveness file. The data dir is on `max`'s `/home`, which
stays writable under `asleep --shallow`, and the tool runs in the same container (`docker exec`), so no network is involved between the tool and the main program.

| Channel | Direction | Carries | Needs the broker |
|---|---|---|---|
| `drill.json` | the drill to the guard | the marker and its `id` | no |
| `/run/rackmains/liveness.json` | poller and guard to `checkhealthy.sh` and the drill tool, tmpfs | boot-clock stamps, `ups_problem` and a static `effective` block | no |
| the outage CSV | guard to tool, read-only | the live record | no |
| the Tasmota plug HTTP | tool to plug | cut, restore, readings, deadman | no |
| `rackmains/data` | publisher to Home Assistant | the mirror | yes, normal operation only |

`drill.json` is in `/asystem/mnt/state/`, the CSV is in `/asystem/mnt/outage/`, and the tmpfs file is in `/run/rackmains/`, which is gone when the container restarts.

**What is reachable during a drain.** Once the shed has run (about 2 minutes on battery):
- yes: ssh to `max`, `docker logs -f rackmains`, `rackmains guard tail|list|stop` on `max`, the plug's HTTP from `max`, and ssh to a shed follower (`asleep --deep` leaves ssh and the network up);
- no: the broker, Home Assistant and InfluxDB on `meg`, the followers' services, supervisor's publishing;
- everything goes dark at the UPS's cutoff until mains returns. Whether the network gear stays up on the UPS is unknown (gap 4 above), and ssh to `max` from outside depends on it.


**Request and reply over files, without a listener.** A file has no reply, so the reply is an echo the tool checks.
- The marker carries an `id`. The guard reads it on its next poll (at most 1 s) and, when it accepts, opens the run's CSV, whose `start` row carries the marker's `id`: that row is the ack. The tool waits at most 10 s for a file whose `start` row carries its own `id` and **will not arm or cut without one**. A rejection (an outage in progress, the guard not ready) is a `note` row in the open file naming the `id` and the reason, or, with no file to write it in, no ack within 10 s, which means no cut.
- `rackmains guard drill` without `--force` prints the `effective` block of `liveness.json`, which the guard writes once at start (`rackmains_guard_live`, the model name, version and hash, `rackmains_guard_shed_battery_seconds`, `rackmains_guard_restore_mains_seconds`, `poll_s`, `ssh_timeout_s`, the shed order), so what the operator reads is what the process that will act has loaded, not a recomputation by the tool.
- Liveness is the `guard_boot_ms` stamp in `liveness.json`, replaced every poll with no fsync. The tool refuses to arm or cut if it is more than 3 s old, which is the proof a socket would give.

**Marker staleness.** The guard honours a marker only if it acked that `id` **before** the first `OB` of the outage and the marker is unexpired; a marker that appears after `OB`, was never acked, or has expired marks nothing.
Its expiry is the planned cut plus the hold plus the after-restore cap plus a margin. The tool deletes the marker on exit, the guard never deletes it (one writer per document), and a leftover marker is therefore harmless.

**Restart mid-trial.** The marker survives on disk. On start the guard rereads an unexpired marker, and the new CSV `start` row carries the same `id` (the re-issued ack) and records `drill` and the mode
as for any outage, and the interrupted file is closed `interrupted` as usual.

**Restart (decided 2026-11-12).** Nothing but the outage CSV and `drill.json` is persisted, and the guard rebuilds the rest on start:
- **Clocks.** `rackmains_guard_battery_seconds` is the time since the open file's first row, and `rackmains_guard_mains_seconds` the time since its last `OB` row. Both use the wall-clock timestamps in the file against now, so a clock step during an outage skews them, bounded by the 300 s stable window.
- **Model state.** A static model has no state to rebuild. When a stateful model ships, the open file is replayed through it from its `start` row's state, which the replay test already proves exact; that replay is built with that model, not before.
- **Hosts.** There is no shed list. At restore the guard runs `awake` on every host, and each host's own `/run/asleep.state` decides what it undoes. A kill loses at most one tick of event rows, which is harmless for the same reason.
- **Calls in flight** die with the process; a half-finished `asleep` is undone by the same `awake`.

**Why not a socket or an API.** A unix socket (or HTTP over one) would give a synchronous reply, but the marker still needs a file to survive a restart, so it would be an addition, not a replacement, and
it adds an always-on server to a module whose surface is deliberately small. A TCP REST API adds a LAN listener and authentication, which the plan already rejected for `upsd`, and nothing off-host needs it. Health
stays on the liveness file, because a server thread can answer while the poll loop is hung, whereas the file is written by the loop itself. If a live request and reply is wanted later, add a unix socket for it.

## The guard CLI and the test command, `rackmains guard drill` (built)

**Staging (decided 2026-11-12).** The first release carries `serve`, `check` and the read-only `guard tail` and `guard list`. `guard drill` and `guard stop`, with the marker, ack, lead-in, plug sampler and deadman handling below, are built after the first release and before trial 5, since only trial 5 and the deadman proof need them. Trials 1 to 3 are cut by hand (see "Trials, tests and rollout"). Everything below describes the drill as it will be built.

The `rackmains` binary becomes a multi-command CLI as supervisor's is (`backup start|stop|auto`, noun then verb, safe by default). `drill` cuts the rack's mains through its plug, collects data, and restores before
exhaustion or runs to the cutoff. It replaces the deleted `tools/outage`. It is a subcommand of the one binary, run as `docker exec -it rackmains rackmains guard drill`, not a second binary, so it uses the same typed
readers of the outage CSV and the model policy as the service and there is one CLI to build, parse and test. `mockdriver` stays a separate crate, being a test double. `main.rs` stays a thin shim over the library's `Cli`, which becomes a root with subcommands as
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
- The drill writes `drill.json` (mode, hold, planned cut, expiry) atomically before anything else. The guard reads it on its next poll, acks it, and from the ack opens the run's CSV and records `drill` and the mode in the `start` row; it otherwise behaves as for any outage. An expired or absent marker marks nothing. The tool deletes it on exit.
- The guard acks in the CSV's `start` row, which carries the marker's `id` (see "Control plane"); the tool will not arm or cut until it sees its own `id`, which also proves the guard is alive.
- The tool reads `liveness.json` and tails the outage CSV, and never writes it or any data file. The main program names, writes and rotates the CSV (timestamped name, temporary file and rename), so a run cannot overwrite an earlier one.
- **Plug columns.** While an acked, unexpired marker exists the main program runs a plug sampler thread, which calls `Status 8` on the plug each poll with a 500 ms timeout and hands the latest result to the CSV writer over a channel. A row takes the result if it is under 2 s old, else the `plug_*` columns are blank. A plug that is unreachable, or off the UPS, simply gives blanks, and outside a drill the sampler does not run, so a real outage makes no plug calls. The guard never reads these columns and the sampler can never block the poll. The deadman stays entirely in the tool.

**CLI.** Follows supervisor's pattern (`cmd.go`, `cmd_serve.go`, `cmd_backup.go`): a root with subcommands, noun then verb, verbs held in one table, help lines lowercase and verb first, optional positionals in brackets,
durations with unit suffixes, kebab-case long flags with a short form for the common ones, choices listed as `[a, b]`, and a command that acts on the real system shows its plan without `--force` (as
`backup module restore`). `auto` with no argument queries, `tail` follows, `list` shows recent runs, and `stop` is the pair of the command that starts a run.

```
rackmains [-V|--version] [--data-dir <dir>]     root flags, inherited by every command; --data-dir is /asystem/mnt, env RACKMAINS_DATA_DIR

rackmains serve [options]                       run the reader, publisher and guard
rackmains check                                 validate the model, host file, ssh keys, data dir and driver socket, then exit
rackmains guard drill [<dur>|drain]             rehearse a power cut: print the plan without --force; default hold is the shed point plus 120s
                      [--force]                 --force cuts mains
rackmains guard stop [--force]                  abort the active drill: mains on, deadman disarmed
rackmains guard tail [<file>]                   follow the newest outage CSV, or the given file, as rows arrive
rackmains guard list                            show the recent outages and how each ended
```

- **Drill and stop behaviour (decided 2026-11-12).**
  - `drill drain` runs to the UPS cutoff with the deadman as the only stop; at least one such trial is run, once per battery, to collect the data.
  - `drill --force` is allowed against a dry-run guard (trial 1 runs that way) with a loud warning.
  - `guard stop` with no drill running reports the state and changes nothing, so it cannot override a plug that is off for a legitimate reason; `guard stop --force` is the unconditional emergency form.
- **Drill constants (decided 2026-11-12).**
  - The ack timeout is 10 s and a stalled guard is a `guard_boot_ms` more than 3 s old.
  - The marker expiry is the planned cut plus hold plus the after-restore cap plus 5 min.
  - The plug is sampled with `Status 8` every poll (1 s, in step with the CSV; whole watts only). The CSV columns are `rackmains_plug_power_state`, `rackmains_plug_watts`, `rackmains_plug_volts`, `rackmains_plug_amps` and `rackmains_plug_energy_today_wh`, all CSV only, never in the payload.
  - The 01:00 backup refusal is a fixed window (00:45 to 01:45), with no coupling to supervisor. A last outage under 6 h ago, or a battery under 100%, warns and never refuses.
- **Conventions taken from supervisor.**
  - `-V/--version` (clap's, as `tempstat`'s; supervisor's is `-v`) prints `SERVICE_VERSION_ABSOLUTE` and exits.
  - `-L/--log-level [debug, info, warn, error]` on `serve`, default `info`, its default overridable by `RACKMAINS_LOG_LEVEL` as supervisor's is by its environment variable. Supervisor's source, subject and action log filters
    are not copied, since rackmains has no such vocabulary.
  - A short list of common flags is shown and the rest are advanced, hidden behind `--help-all`. Shown on `serve`: `-P`, `-B`, `--mains-publish-period`, `--live`, `-L`. Advanced: `-D`, `-M`, `-T`, `--broker-port`,
    `--broker-token`, `--outage-keep`.
  - Errors go to stderr and exit `1`; a command that has already reported its failure returns a reported error so it is not printed twice; a command that must exit with its own code (a `drill` aborted with mains restored)
    returns an exit error carrying it. The codes mirror `asleep` (`0` ok, `1` error, `2` usage, `4` timeout) plus one code for "aborted, mains restored" (decided 2026-11-12).
  - The `guard` verbs are one table (name, usage, help, argument count), as `backupVerbs`, not separate handlers.
- **Crate: `clap` 4 with `derive` and `env`, already a dependency (4.6.7 locked), and nothing new is added.** The root is a `Parser` with a `Subcommand` enum, `guard` a nested `Subcommand` enum, and the root flags `global = true`.
  Advanced flags use `hide_short_help = true`, so `-h` omits them and `--help` shows them, which replaces supervisor's `--help-all` without custom code. Choices use the existing `PossibleValuesParser`. Durations (`<dur>`, the
  period flags) use `humantime`, also already a dependency. Version stays clap's `-V/--version`, as `tempstat`'s, not supervisor's `-v`. The typed `drain` confirmation reads one line from stdin, with no prompt crate. Exit
  codes come from a typed error matched in `main`. No completion crate.
- **`serve` options.** The existing flags move across unchanged (`-P/--poll-period`, `-D/--device`, `-M/--model-dir`, `-T/--timeout`, `-B/--broker-host`, `--broker-port`, `--broker-token`, `-L/--log-level`). Added:

  | Option | Default | Meaning |
  |---|---|---|
  | `--mains-publish-period` | `5s` | publish on mains even if unchanged; no short form, `-B` is the broker |
  | `--outage-keep` | `100`, env `RACKMAINS_OUTAGE_LOG_KEEP` | newest outage files kept |
  | `--live` | off, env `RACKMAINS_GUARD_LIVE`, set in `.env_prod` | the guard sheds for real; without it the guard is in dry-run; refused if `check` fails |

  No flag sets `rackmains_guard_shed_battery_seconds` or `rackmains_guard_restore_mains_seconds`: thresholds come from the released model, never from flags or constants.
- **`check`** loads the model and verifies its hashes and signature, reads the generated host file and checks the ssh keys exist with the right modes, the data dir is writable and the driver socket reachable, then exits `0`
  or non-zero. `fab systest`, the install hook and an operator can run it, and `--live` uses the same checks, so the guard's "refuses live mode if the model fails" has one implementation.
- **`guard tail`** and **`guard list`** are read-only and share the one typed outage CSV reader. `tail` is what follows an outage after the drill has gone (a `drain` ends with `max` dying, and the record is read afterwards);
  `list` prints each recent outage with its start, duration, minimum battery voltage, hosts shed and whether it was a real outage or a `drill`, taken from the `start` and `end` rows.
- **`<dur>` or `drain`** is one positional on `drill`. `drain` keeps mains off until the UPS cuts its own output.
- **`drain`** keeps mains off until the UPS cuts its own output, so the guard sheds as for any outage and `max` is then cut while running. It needs a typed `drain` even with `--force`.
- **No `plan` or `run` command, no `--yes`, no `--label`:** a bare `drill` is the plan and `--force` acts. `drill` follows its own run and keeps following after Ctrl-C; `docker logs -f rackmains` carries the same events at INFO.
- **From the environment, not flags:** `RACKMAINS_PLUG_HOST` (`10.0.4.102`), set in `.env_all`.
- **Fixed, not options:** recording continues after restore until the outage CSV's `end` row, capped at 30 min; the 60 s lead-in; the plug deadman is hold plus 5 min, or 3 h for `drain` until the first measured run (Decided). Changing
  either is a release.
- **Container-free fallback.** If Docker or the rackmains container is down, `guard stop` cannot run; the plug deadman is the backstop and the operator command is
  `curl 'http://10.0.4.102/cm?cmnd=Power%20On'` followed by `curl 'http://10.0.4.102/cm?cmnd=Rule1%200'` to disarm the rule.
- **Detached sessions.** `docker exec -it` is not detached; if the ssh session drops, the plug is left to the deadman. That is accepted, because the deadman exists for exactly this case.

**What it prints before cutting**, in three blocks so the drain is clearly understood:
1. the tool's settings (mode, hold, after, deadman, guard posture, plug);
2. what the main program will observe, read live from the `effective` block of `liveness.json` (dry-run or live, version, model project and mode, `rackmains_guard_shed_battery_seconds`, `rackmains_guard_restore_mains_seconds`,
   the poll and CSV row intervals, the ssh timeout, and the shed order);
3. the derived timeline (T-60 lead-in starts, T+0 plug off, about T+2 `OB`, T+120 shed, T+hold plug on, T+hold+300 `awake`, `end`), with a loud warning if hold is under the shed point (the guard will not shed)
   or the guard is in dry-run (the test proves nothing about the shed), and the preflight results.

**While running.** It tails the CSV by row count (the file is replaced every 1 s and continues in the next numbered file, so `tail -F` is no use) and prints one line per new row: elapsed, status, volts,
utilisation, `rackmains_guard_state`, host results and plug watts. The hold is counted from the first `OB` row, not from the command. It also stops early in hold mode if `LB` is raised.

**Arming is read back.** After the lead-in, immediately before the cut, the tool arms the deadman, then reads `Rule1` and its timer back from the plug and refuses to cut if either is wrong; after the cut it requires `Power` to read `OFF`.

**Lead-in (decided 2026-11-12).** Once the guard acks the marker its CSV is open and recording mains rows with the plug columns. The tool waits for 60 s of lead-in rows showing `ups.status` `OL` throughout and plug watts within 3 W, read from the CSV it tails, and only then arms the deadman, reads it back and cuts, within seconds, so nothing is left armed on the plug if the run dies during the lead-in. Preflight and the ack come first, as above. This makes the settled-load condition of "Trials, tests and rollout" a check, and the lead-in is the steady-state baseline of plug watts against `ups.load`. `elapsed_seconds` counts from the first row of the file.

**A drill that dies during the lead-in (traced 2026-11-12).** The file opened at the ack has mains rows and no `OB`, and the deadman is not yet armed.
- **The tool dies, cleanly (Ctrl-C, SIGTERM):** it deletes the marker, the guard sees it gone and closes the file with `end` `aborted`, and the plug sampler stops with the file. Nothing was cut or armed.
- **The tool dies with `kill -9`:** the marker stays. The guard closes the file with `end` `aborted` after `rackmains_guard_restore_mains_seconds` of `OL` from its first row at the latest, or at the marker's expiry, whichever is first, and the sampler stops with the file. The next preflight does not refuse on that marker, because its run is closed; it replaces the marker. `guard stop` with no tool running clears a leftover marker.
- **rackmains or the container restarts:** the open file's last row is not `end`, so recovery rewrites it with `end` `interrupted` at its last row. The unexpired marker is re-acked, which opens a new file whose `start` row names the interrupted one and records `drill`. The UPS is on mains, so no other file starts. The tool tails the newest file, notices the change, and restarts its 60 s lead-in count in the new one; if the guard `seq` stalls for 3 polls it aborts before arming.
- **No cut and no label:** a file with no `OB` is not a run to failure, so it gives no cutoff label.

**What a run records (decided 2026-11-12).**
- **Before:** the 60 s lead-in, in the CSV's first rows.
- **After a normal restore:** sampling continues until the CSV's `end` row, about 5 minutes of `OL` after the plug comes on (`rackmains_guard_restore_mains_seconds`), capped at 30 min. That is the start of the recharge, not its tail (about 6 hours to 90%), and a longer tail is not recorded.
- **A drain:** the tool dies with `max` at the cutoff, so the CSV ends there. The only later record is the CSV closed `interrupted`, timed at its last row, written when the container restarts.

**Exit paths.** On Ctrl-C, SIGTERM or SIGHUP the plug goes on first, a second Ctrl-C is ignored until the plug reads back `ON`, then the marker becomes
`aborted`, and the tool says the main program will run `awake` after `rackmains_guard_restore_mains_seconds` of mains and keeps following until `end`. After a normal restore it verifies `OL` within a bound and
retries, alarming loudly with `rackmains guard stop` and the container-free fallback otherwise. After the plug reports off it requires `rackmains_mains_failed` in the CSV within 10 s, else it restores and fails. The tool runs
detached from the ssh session.

**Preflight** refuses on: an outage in progress, an existing marker whose run is still open, a stale guard stamp, an unreachable host and the 01:00 backup window. It **warns only** when the last outage ended under 6 hours ago (the manual's recharge time), the battery is not at 100%, or the guard is in dry-run (the run proves nothing about the shed). The plug deadman does not depend on the tool.

**Interaction tests** (the system test with the mock driver and a mock plug):
| # | Scenario | Expected |
|---|---|---|
| 1 | hold 240 s, guard armed | shed at 120 s, plug on at 240 s, `awake` after 300 s of mains, `end` |
| 4 | Ctrl-C during the hold | plug on first, marker `aborted` |
| 5 | `kill -9` the tool during the hold | the deadman restores mains |
| 13 | dry-run guard | preflight warns that the shed is not tested |
| 15 | an ack with another `id`, a rejected ack, no ack within 10 s, or a `guard_boot_ms` more than 3 s old | the tool does not cut |
| 16 | a marker that was never acked, appears after `OB`, or has expired | marks no outage |
| 17 | the guard restarts mid-trial | the marker is honoured, the same ack is re-issued, the new `start` row records `drill` |
| 18 | `liveness.json` is read while being replaced | the reader sees a whole old or new version |
| 19 | the lead-in shows a status other than `OL`, or plug watts moving more than 3 W | the tool refuses to cut |
| 20 | a normal run | one CSV holds 60 s of mains lead-in rows with plug columns, then the run, then rows to the `end` row |
| 21 | the plug unreachable during a drill, and a real outage | the `plug_*` columns are blank and no plug call is made outside a drill |
| 22 | the tool dies in the lead-in, by Ctrl-C and by `kill -9` | the file closes `aborted`, the sampler stops, no deadman is armed, the next preflight proceeds |
| 23 | rackmains restarts in the lead-in | the old file is `interrupted`, a new file names it and records `drill`, the tool restarts its 60 s count |
| 24 | a lead-in file closed `interrupted` or `aborted` with the last row on mains | no cutoff label |

The numbers are stable ids. Tests 2, 3, 6 to 12 and 14 went with `guard_auto`.

## The host side, the `system` module (built)

`src/all/system` puts `asleep` and `awake` on the four servers; its `CLAUDE.md` is the reference and this is what the guard
needs from it. Hosts are never powered off: a Mac mini restarts after a power cut only from a running state and stays off
after a clean `poweroff`, so the guard quiesces a host and leaves it running.

- **`asleep --deep`** (followers). Stops timers, automounts, containers (each given its own grace period, its exit code
  checked), docker and the services, then unmounts every fstab mount, makes root read only, and flushes and detaches the SATA
  and USB SSDs. Leaves ssh, the network, NUT and the fan control. Never powers off.
- **`asleep --shallow --except rackmains`** (`max`; `--except` added 2026-11-13, replacing the wrapper's container list, and `--stop <container>` still works). Leaves docker, root, `/var` and `/home` writable so rackmains keeps
  running and writing to its home dir; stops every container but `rackmains`; unmounts what no running container holds.
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
outage (`rackmains_battery_state`, JSON text), so a recorded outage is a complete fold and can be replayed through any project. Text and the timestamp are never sent: the
status becomes the flags and the time becomes `clock_epoch_seconds` at source, here, in Rust.

**The Rust seam.** The model is the bundled loader (`mlmodels` `model.md` 10.9), written by `python -m mlmodels embed` into `src/model/` as `loader.rs`, `battery.rs` (the name constants, `Request`, `Response` and their conversions, and a `load` that checks the signature against them) and `mod.rs`. `model::battery::load` checks every hash and returns a `Model` whose `predict` gives the constants for every valid request; `policy.rs` turns the `Response` into the guard's `Policy`. A later ONNX project needs no new type: the same loader builds its driver with `ort` (pinned exactly, one thread, loading the shared library taken from the pinned wheel MLServer uses) and `predict` takes the row and the state and returns the response. There is no served model and no fallback project: a project that fails to load makes rackmains broken (`mlmodels` `model.md` R8), and its build and tests catch that. A failed call keeps the last valid answer. One validator turns a response into a typed `Policy` and the estimates, and the guard sees only those, never JSON, so
replacing the constants project with a fitted one changes one constructor and nothing downstream.

**State.** The state in the answer in use is carried to the next call and persisted, with the project hash and model version, in
The state is not persisted: on a restart the open outage CSV is replayed through the model from its `start` row (see "Control plane"), and the project hash and version sit in the `effective` block of `liveness.json`. A state from a different project is discarded, and a lost state
restarts the model from its initial state, with the history unknown, which it treats as a partly drained battery. The guard does not read
the state; it is the model's.

**Engine and memory.** Day one embeds only the default (static) project, which needs no engine. The first ONNX project brings `ort`, the
ONNX Runtime shared library for each architecture, taken from the pinned wheel and hash-pinned into the image, and a higher compose
memory limit (measured at 34 MB for the engine on the laptop; about 96 MB suggested in place of 32 MB, to re-measure on Linux). The compose limit also rises from 32 MB to 64 MB for the first release, since the guard runs up to four `ssh` children in parallel beside the CSV rows, and review pass 10 measures it.

**Calls.** One whenever a publish happens: every poll (1 s) on battery, every 5 s on mains. A call never blocks the poll or the guard; a failed
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

**Starting values, the default model.** Constants only: `rackmains_guard_shed_battery_seconds` 120, inside the 145 s already held at service
load with no knee; and `rackmains_guard_restore_mains_seconds` 300. They shed early on short outages and so
waste battery, but never outrun what is proven. The values are the constants of the notebook's `define_model` call. A refit replaces the project, which is a release.
The halt thresholds (`guard_halt_max_seconds`, `guard_halt_delay_seconds`, `guard_halt_lead_seconds`) were removed from the signature in place, before it was released, so the project, its golden file, the generated
`battery.rs` and `policy.rs` no longer carry them; the signature now has the five inputs and nine outputs, two of them required (`rackmains_guard_shed_battery_seconds`, `rackmains_guard_restore_mains_seconds`).

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
  mains publish is only every 5 s, so the restart that `schema broker` causes must publish `online` and the full current payload
  at once, as the reconnect rule above already says. That is a test to write: a restart, and a plain reconnect, each leave both
  topics retained within one poll.
- **The restart is safe mid-outage by design.** It closes an unfinished outage CSV as `interrupted` and rebuilds the guard from that file. A vernemq release during an outage is unlikely anyway, since the broker's host is shed first.

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
- **Files.** One function writes a file atomically (temporary file, fsync, rename, directory fsync), and one typed reader exists per persisted document (the outage CSV, `drill.json` and `liveness.json`).
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
   - time: monotonic for durations, the wall clock only for stamps and the persisted marker expiry in `drill.json`, and a stepped clock;
   - numbers and files: parsing, overflow, the one formatter shared by the payload and the CSV, write-fsync-rename order, recovery of an unfinished file, the file count bound and that the prune never removes the current file;
   - the guard: every action idempotent, a restart mid-outage and mid-sequence, a flapping grid with dips shorter and longer than the stable period, a lost ack, a reader meeting a file mid-replace;
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
   security points: only `DUMPALL` written to the driver socket, the ssh key with the host key pinned and no host name interpolated into a shell string, untrusted input parsed defensively (driver lines, the MQTT command, a model response, ssh output, CSV quoting), no panic reachable from outside input, no secret in a log or the repo.
10. **Prove it still works.** Run the targeted tests first, then the full suite once. Run the real built artefact: `fab build`, `fab package`, then the image with the mock driver and the system test, with failure injection (`kill -9` mid CSV write, stop the container mid outage, start with the broker down and lose it mid drain,
    a read-only or full data dir, a stale, garbage and vanished driver socket, an invalid, absent or slow model response, a hung host, a plug that does not answer). Measure resources: the compose memory limit through the longest outage the CSV bound allows, with no queue, in-memory row set, thread or descriptor growing without
    bound, the combined writes per second on battery (the CSV rewrite of up to 1 MB; the tmpfs files cost no disk) judged for SSD wear, and DEBUG volume against the 5 x 100 MB log rotation. For generated output (`broker.sh`, the schema, `.env`, `docker_deps.sh`) a pure refactor regenerates byte-identical, and any other diff is explained.

**Operability and documentation (part of the final review).** Each log line says what happened at the right level; start and stop are logged; the health check means one thing; an operator can find, read and back up the CSV from what is written; every claim in the module `CLAUDE.md` and this plan is true of the
code; each hook is idempotent and never fails an install it should not.

**Review is not permission to ship.** Do not run a release, deploy or install as part of a review, and read what a release command does to git and to remote hosts first. Report in this order: the defects found and fixed, then the simplifications, then what was left alone and why, then what was not checked; keep a real bug
distinct from tidying, and say plainly when a pass found nothing.

**Process rules.** Judge against this list, not taste, and cite the rule each finding breaks. Classify each as a **blocker** (wrong or unsafe), a **should-fix** (against a guideline, or a clear simplification) or a **nit**. Nothing classed blocker or should-fix is deferred without a reason recorded. A second reader reviews what
the first changed, a human or an automated high-effort review (`code-review`, `simplify`). Record the version reviewed (`SERVICE_VERSION_ABSOLUTE`) beside the table.

**Exit criteria.** No blocker or should-fix is open; every other finding is fixed or accepted with a reason; the gates are green; a fresh diff against `tempstat` shows only intended differences, each recorded with whether `tempstat` should adopt it (the root CLI is one); the module `CLAUDE.md` matches the code; and nobody
reading the module would need this plan to understand it.

Version reviewed: none stamped; the author's passes and a high-effort `code-review` second reader both ran over the new code on 2026-11-12 and their findings are below. Passes 5, 6 and 10 (naming, layout, resources) and a human read are still open.

| # | Finding | Where | Rule broken | Kind | Severity | Outcome |
|---|---|---|---|---|---|---|
| 1 | Restarting with an unfinished drill lead-in file resumed the guard as if on battery, so the surviving marker was rejected | `outage::clocks` | correctness, restart | correctness | blocker | fixed: no resume without a battery row; test added |
| 2 | Prune counted the current stem inside the kept set, so it could delete the newest file | `outage::prune` | correctness | correctness | should-fix | fixed: the newest `keep` are kept, the current stem never deleted |
| 3 | A broker down at start blocked the publisher for 30 s and failed the process | `broker::MqttPublisher::new` | each dependency failing | resources | blocker | fixed: connect is in the background, the one-shot mode waits explicitly |
| 4 | A down broker logged a WARN every poll and every reconnect | `serve::publish`, `broker` | operability | style | should-fix | fixed: one line on loss, one on return |
| 5 | `Guard::mains` and `Guard::battery` were used only by tests | `guard.rs` | dead code | simplification | nit | fixed: deleted |
| 6 | The guard is stepped inside the poll loop, not in its own thread | `serve::Poller::tick` | plan deviation | guideline | accepted | one decision per poll is the specified behaviour and a pure step cannot hang; only ssh calls, the writer, the plug sampler, the broker and the watchdog are threads |
| 7 | The plug sampler reads `Status 0`, not `Status 8`, so the power state and the sensor come in one call | `drill::Plug::status` | plan deviation | guideline | accepted | `rackmains_plug_power_state` needs the `StatusSTS` block; to be confirmed on the spare plug |
| 8 | No reinit loop | `serve::run` | plan deviation | guideline | accepted | a fresh socket per poll leaves nothing to reinitialise; `tempstat` could adopt the removal |
| 9 | `rackmains_battery_state` is recorded as a JSON array, not an object of named slots | `serve::sample_state` | plan deviation | guideline | accepted | the response carries no slot names; revisit with the stateful model |
| 10 | `struct_excessive_bools` added to the shared clippy `-A` list | `fabfile.py` | style | guideline | accepted | `Flags` mirrors NUT's status tokens; a per-crate allow is forbidden and the list is the one policy home |
| 11 | The `system` module gained `asleep --except` (2026-11-13; the `rackmains-shed` forced-command wrapper was dropped) | `src/all/system` | scope | guideline | accepted | the guard's ssh key is unrestricted by choice; keys and deployment are yours |
| 13 | A restart after a shed rebuilt the guard with no shed on record, so mains returning never woke the hosts | `guard::resume`, `outage::clocks` | correctness, restart | correctness | blocker | fixed: a shed decision row in the open file restores `shed_started`; tests for both directions |
| 14 | A restore wanted but not started was never cancelled if the battery returned, waking hosts mid-outage | `guard::step` | correctness, flapping grid | correctness | blocker | fixed: cancelled, the shed starts afresh; test added |
| 15 | Failed reads freeze the battery timer, so a dead driver mid-outage never sheds | `guard::step` | correctness | correctness | accepted | specified: a sequence starts only on a fresh reading; the 120 s floor and the UPS cutoff are the backstop, and the stale liveness turns the container unhealthy |
| 16 | The drill lead-in could wait forever if the plug never sampled | `drill::drive` | each dependency failing | correctness | should-fix | fixed: bounded, and a closed file ends it with the timeout code |
| 17 | The publisher was never closed on the one-shot or error path | `serve::Poller::stop` | correctness | dead code | should-fix | fixed: `Publisher::close`, called on stop |
| 18 | `seconds_on_battery` counted ticks, not elapsed time | `outage::Stats` | numbers | correctness | should-fix | fixed: adds the poll's `dt`; test with a 10 s period |
| 19 | `guard tail <file>` failed for a bare or relative name | `report::tail` | correctness | correctness | should-fix | fixed: matched by file name; test added |
| 20 | The CSV is rewritten whole with two fsyncs each tick | `outage::Spool::flush` | resources | resources | accepted | decided in the plan with the append fallback; the combined write load is still to be measured (pass 10) |
| 21 | A SAFETY comment in a no-comment crate | `drill::install_signal_handlers` | comments | comment | nit | fixed: removed |
| 22 | Metric names repeated as literals outside the column table | `serve`, `outage`, `drill`, `metrics` | duplication | duplication | should-fix | fixed: named constants in `metrics.rs` for the ones used elsewhere |
| 23 | `drill` and `stop` rebuilt every default by hand | `cli::CommonArgs::defaults` | duplication | duplication | should-fix | fixed: the common flags are flattened into both commands |
| 24 | Cancelling a pending restore cleared the shed record, so a later calm would end the outage with the hosts still asleep | `guard::step` | correctness | correctness | blocker | fixed: the shed record stays and every host is shed afresh; test |
| 25 | Going back on battery during a running restore was ignored, and the finish then reset the battery clock | `guard::settle` | correctness, flapping grid | correctness | blocker | fixed: the restore finishes, the shed record clears, the clock keeps running, the next tick sheds; test |
| 26 | A restart rebuilt the battery clock as wall time since the first row, not time on battery | `outage::clocks` | correctness, restart | correctness | should-fix | fixed: sums the intervals that began on battery, counts downtime as battery only if the last row was on battery; tests |
| 27 | The deadman was never enabled with `Rule1 1`, and `Rule1 0` after a drill left it off | `drill::drive` | correctness | correctness | blocker | fixed: explicit enable before the read-back; unproven on the real plug |
| 28 | The lead-in refused `OL CHRG`, which preflight treats as a warning | `drill::lead_in_verdict` | correctness | correctness | should-fix | fixed: refuses a missing `OL`, `OB` or a problem flag only |
| 29 | The drill followed forever after the restore if no end row appeared | `drill::drive` | each dependency failing | correctness | should-fix | fixed: bounded by the after-restore cap, exit 4 |
| 30 | The plug status check matched `200` anywhere in the headers | `drill::Tasmota` | untrusted input | correctness | should-fix | fixed: the status line's second token |
| 31 | A decision on first sight wrote its row before the `start` row | `serve::tick` | correctness | correctness | should-fix | fixed: `start` first; test |
| 32 | Guard rows are dropped when no session is open after a mid-outage restart | `serve::tick` | correctness | correctness | accepted | logged at INFO; a restart on mains with an outage clock needs no record |
| 33 | Failed reads freeze the battery timer (raised again) | `guard::step` | correctness | correctness | accepted | as row 15, awaiting your decision |
| 34 | The CSV rewrite is quadratic in writes (raised again) | `outage::Spool` | resources | resources | accepted | as row 20 |
| 12 | The container system test was written but not run | `system_test.py` | prove it works | test | open | needs `fab systest` with docker and the broker |

## Trials, tests and rollout (restated 2026-11-11)

Recovered from the model plan deleted in commit `ca0c83150` (`git show ca0c83150^:src/rue/mlmodels/src/main/notebook/rackmains/ups/battery/plan.md`), adapted to the decisions since: no halt, no `shutdown.return`, run to failure, and
`rackmains guard drill` replacing the by-hand cut. Results are recorded here as they come in.

**Before every trial.** The battery has settled: on mains at least 12 hours since the last transfer, float steady within 0.1 V for 30 minutes, load steady within 3 points for 10 minutes, all four servers answering, and outside the
01:00 backup window. Abort on voltage, `LB`, a host down, stale readings or a cap, **never on the unit's capacity or runtime**, which are smoothed model outputs that lag.

| # | Trial | Command | Needs first | Decides |
|---|---|---|---|---|
| 1 | Hold at service load | by hand, plug off for 10 min, guard in dry-run | the guard built, the plug deadman proven by hand (test 8) | the conservative timers fit; the knee if it appears |
| 2 | Recover before the shed | by hand, plug off for 90 s, guard live | trial 1 | nothing is shed, the reset works |
| 3 | Recover after the shed | by hand, plug off for 4 min, guard live, followers shed then woken | tests 3, 4 and 5 | the restart path |
| 4 | (dropped) Halt and UPS cut/restore | | | there is no halt and no `shutdown.return`; test 6 stays only as the fallback if outlets do not restore |
| 5 | Run to failure, once per battery | `guard drill drain --force`, guard armed | the drill built, trial 1 | the real knee and cutoff, whether `LB` raises, whether outlets restore, the offline fit |

**Trials 1 to 3 by hand (decided 2026-11-12).** The commands the drill would issue, typed on `max`: arm the plug's deadman rule (the `Rule1` line in "The guard CLI", with the hold plus 5 min) and read `Rule1` back, `Power Off`, watch `docker logs -f rackmains`, `Power On` at the end of the hold, `Rule1 0`, and wait for the CSV's `end` row. These runs have no lead-in, no plug columns and no marker, so the CSV is not tagged `drill` and has no plug watts baseline; note the run's label by hand. The container-free fallback in "The guard CLI" is the way out if anything goes wrong.

Trial 5 was written as "to the 11.5 V floor or `LB`, not to the UPS cutting out", a second point at service load because the low load runs long. The run-to-failure decision supersedes the stopping point: trial 5 runs to the UPS cutoff, at least once, to collect the data (decided 2026-11-12).

**Tests still needed**, from no risk to most; each result decides a branch.
1. **Baseline**, a day on mains with the recorder: which flags appear unprompted (`BOOST`, `TRIM`). The recorder has since been stopped, so the published entities and the outage CSVs are the record.
2. **Quick battery test** (`test.battery.start.quick`): the test flag's name and the seconds spent in `OB`, in a quiet hour.
3. **ssh key** on `may`: a dedicated unrestricted root key (decided 2026-11-13, simplicity over restriction; the forced-command wrapper was dropped), then `/usr/local/bin/asleep --deep --dry-run` run from a container on `max` with `StrictHostKeyChecking=yes` against the pinned `known_hosts`.
4. **Per-host `asleep` time**, start of the command to its `RESULT` line (`took`), several runs per host and the slowest container stop; order `may`, `mad`, `meg`. Measured so far: `max`, shallow, three containers, about 3 s; no deep run yet.
5. **Power on after a cut**, per host, yours. A clean `poweroff` is not the test, the board stays off after one. `max`, `may`, `meg`: `AFTERG3_EN` is already cleared (`1c08`); run `asleep --deep` (on `max`, `--shallow`), pull the cord from the UPS for
   10 s, replace it, and time the boot to ssh. `mad` (Mac mini M2 Pro) needs a macOS step first: boot macOS from the boot picker, turn on "Start up automatically after a power failure" in Energy Saver, check `pmset -g | grep autorestart`
   prints `autorestart 1`, boot back into Linux and run the same cut. The only report that this carries into Linux is on a base M1 ([AsahiLinux/docs#156](https://github.com/AsahiLinux/docs/issues/156)), so the M2 Pro result is part of the test.
6. **`shutdown.return` on a lamp**, and `shutdown.stop` cancelling it, only if trial 5 shows the outlets do not restore by themselves.
7. **Standby**, only with the outlets empty: `ups.status` for `OFF`.
8. **Plug deadman**: the on-device restore proven by hand with the plug unreachable. The Tasmota `Delay` honours only 2 to 3600 tenths of a second (`Delay 4200` was ignored), so a cut above 360 s cannot use a single `Delay`; the rule timer in
   "The guard CLI and the test command" is the design, and it is proven on the spare plug first.
9. **Reachability**: the plug console and all four hosts are reachable from where the cut is made, and that place is not on the UPS. The plug's API is open without a password on the LAN, so anything on that network can cut the rack, and no password is set or planned, the risk being accepted (decided 2026-11-12); `max` and a
   bridge container both reach it (a bridge container on `max` was confirmed on 2026-11-11).
10. **Reaction latency and `pollfreq`**: set `pollfreq = 1` in `ups.conf`, check the unit and the driver tolerate it, and time the cut to `OB` and the restore to `OL` in the published entities and the CSV. This decides whether `pollfreq` stays at 1.
11. **`awake` on an awake host**: run `awake` on each of the four hosts when it was never put asleep and when it was asleep, and confirm it changes nothing in the first case and returns 0. The guard's restore, which runs `awake` on every host, rests on this.
12. **Restart policy**: `docker inspect` the restart policy of the running container in every environment, and `kill -9` the process once to confirm Docker restarts it. The watchdog's abort relies on this.

The guard's build can begin after tests 3 and 4, with the restart left behind an interface until test 5 is in.

**Acceptance.** A flag is a trigger only once seen on this unit: `OB` (seen), the test flag (test 2), `OFF` (test 7). `LB` and the alarm flags are overrides until observed; if `LB` never appears before the unit cuts, it is dropped from the design
and the time cap carries that job.

**Rollout, in steps.** Thresholds start very conservative, ship in a release, are tested against real data, then are reset in a second release. Nothing is lengthened on a guess.

| Step | Thresholds | Mode | Allowed by | Evidence it produces |
|---|---|---|---|---|
| A, floor | `rackmains_guard_shed_battery_seconds` 120, inside the proven 145 s at service load with no knee | dry-run | the per-host `asleep` times (test 4) and the forced-command test (3) | the guard's decisions on real mains events, logged but not acted on |
| B, live and cautious | the same | live | trial 1 at worst-case load with no knee and no `LB`; trials 2 and 3 pass; the restart path chosen | real outages and drills exercise the whole chain |
| C, measured | `rackmains_guard_shed_battery_seconds` set to the knee time less `rackmains_guard_shed_runtime_seconds` | live | trial 5 once on this battery, plus any real outage, fitted offline | the knee at service load, the cutoff, whether `LB` raises |
| reset | recomputed | live | a battery replacement, a load change over about 30%, or a time to the floor 20% below the last fit | a new trial and a release |

- `rackmains_guard_restore_mains_seconds` is the shortest run of `OL` that a flapping grid has not been seen to break, and long enough that a drained battery has begun to recover (about 6 hours to 90% per the manual, so longer is safer; there is no measure, it is a judgement).
- A single run to the cutoff costs some battery life, so trial 5 is made once per battery. Without it the thresholds stay at step B and waste battery but never risk the servers.
- A reset is a refit from the outage CSVs and history, a new project, a release, and a dry-run period before live; the previous project stays in git.

**Gaps carried from that plan, still open**

| # | Gap | Closed by |
|---|---|---|
| 1 | trials run at average load; the 01:00 backup and service starts raise it | take the worst-case `ups.load` over a week of history and run trial 1 at it, or add the load by hand; `LB` is the backstop |
| 2 | a second dip soon after the first finds a partly drained battery (about 6 hours to 90%) | the guard's clock resets after `rackmains_guard_restore_mains_seconds` of mains |
| 3 | the battery's condition is unknown; its age is assumed, installed 2024-11-12 | `RACKMAINS_BATTERY_INSTALLED` and the `battery_age_*` metrics give the age; condition is not a model input, the fit is of this battery, and a replacement means a new fit |
| 4 | what else is on the UPS (switch, router, access point, the Mac) is not inventoried | **yours:** list the loads on the UPS; the plug's WiFi and the followers' ssh path both depend on them |
| 5 | the offline fit's data path is unchecked | Home Assistant's history of the rackmains entities plus the outage CSVs; confirm Home Assistant records the entities at battery cadence |

## Yours to do

Hands-on steps the code cannot do, in the order they unblock work. Results of the tests and trials are recorded in "Trials, tests and rollout".

1. ~~Workbook rows~~ done 2026-11-12.
2. **ssh keys** (decided 2026-11-13: a dedicated, unrestricted root key, simplicity over restriction; the forced-command wrapper `rackmains-shed` was dropped). Open until every step is done:
   1. ~~Release the `system` module~~ done 2026-11-13: all four hosts have `asleep --except` and none has `/usr/local/bin/rackmains-shed`.
   2. ~~Run `asleep --shallow --except rackmains --dry-run` on `max`~~ done 2026-11-13: `rackmains` left running, `supervisor`, `grafana`, `letsencrypt` and `cloudflare` stopped, `/home` and `/var` kept held, exit 0. Its closing ERROR (still writable) is a dry run's own, nothing was unmounted. A real run followed the same day: status 0, `rackmains` stayed healthy, the four others stopped cleanly in about 1.4 s, `sda` detached, one avahi stop job cancelled and retried by the verify pass, and one failed unit afterwards. `awake` then returned status 0 in 16 s: all five containers healthy (`rackmains` untouched), 30 services, 11 timers and 10 automounts back, and the failed unit cleared, so it was transient. That closes the shallow round trip on `max`; a deep run is still not done. The host mounts the key directory at `/etc/asystem/rackmains/ssh`.
   3. ~~Generate a keypair, distribute it, pin `known_hosts`~~ dropped 2026-11-13: the guard uses the existing shared `id_rsa` (`_homes`) and root's `known_hosts`, both already on `max` and authorized on all four hosts (checked: `known_hosts` has `macmini-max`, `-may`, `-mad` and `-meg`, the `hosts.json` addresses). `.env_all` sets `RACKMAINS_SSH_SOURCE=/root/.ssh` and `RACKMAINS_SSH_KEY=/asystem/ssh/id_rsa`; the compose mount is unchanged.
   4. Release `rackmains`, then prove it with test 3 and `rackmains check` in the container.
   Not restricted by the key, and not dedicated: it is the personal key that opens every host, so the guard cannot be revoked without rotating it (accepted, simplicity over security). Kept: strict host key checking and the mode check in `check`.
3. **Tests 3 and 4** (ssh key, per-host `asleep` time), then the **spare-plug deadman proof** (test 8) and the **retained `cmnd/POWER` check**.
4. **`mad`'s macOS step** for power-on after a cut, then test 5 on all four hosts.
5. **List what else is on the UPS** (switch, router, access point, the Mac): the plug's WiFi and the followers' ssh path depend on them.
6. **Releases and trials:** the dry-run release, trial 1, trials 2 and 3, and trial 5 once per battery.
7. **Until the guard goes live** the rack is exactly as exposed as it is today, so the dry-run release protects nothing.

## Remaining phases

Decided: step A starts inside the proven 145 s (`rackmains_guard_shed_battery_seconds` 120); trial 5 goes to the cutoff once; trials 1 to 3 are cut by hand and trial 5 with `rackmains guard drill`; and there is **one first release carrying the publisher and the guard in
dry-run**, not a publisher alone. Each build step ends in a review (R1 to R4, defined in the next section), and the release waits for R4.

1. **R1, done in the build pass (2026-11-12):** review `rackmains`, `mockdriver`, `tools/schema`, the install hooks and `policy.rs`.
2. **Build metrics and the outage CSV:** the `nut.rs` flag function and `SAMPLES` with the canonical names, the flat MQTT payload and the poll and publish cadence, the outage CSV writer and its backup enrolment (`backup.sh`,
   `write_container_backup()`, the `.env_all` keep values), the liveness file, the watchdog and an MQTT-independent `checkhealthy.sh`, the model seam, the module `CLAUDE.md`. Then **R2**.
3. **Yours (not done, no longer blocks the build):** tests 3 and 4, the spare-plug deadman proof and the retained-command check ("Yours to do").
4. **Build the guard, dry-run only:** the root CLI (`serve`, `check`, `guard`) with the image entrypoint and compose command changed to `rackmains serve`; `run` restructured so the poll, the CSV writer and the guard start
   before, and never wait on, the broker connect; the generated host file; `liveness.json` on tmpfs; the ssh runners for `asleep` and `awake`; the state machine with mock sequences; `rackmains guard tail|list`. Then **R3**.
5. **R4, final review of the whole module,** then **yours:** the workbook rows and the dry-run release; confirm `rackmains/status` is `online`, the entities appear, and a short by-hand plug cut turns `rackmains_mains_failed` on within one poll and off when mains returns.
6. **Trial 1 by hand, then test 5 and the restart tests, then trials 2 and 3 live by hand,** recording each result.
7. **Build `rackmains guard drill` and `guard stop`,** then **R5**, a review of what they added.
8. **Trial 5 once per battery** (`rackmains guard drill drain --force`), fit the model's outputs offline (a new project), release the measured thresholds.

## Open decisions

Consolidated 2026-11-11 and renumbered Q1 to Q21. Each has the question, why it matters, and a recommendation to accept or change. Settled ones are under "Decided" and in the sections above.

**To observe or check, not to decide**
- **Q18. Does the PSDR800 supply its outlets again by itself after a depletion cutoff?** Not in the manual; trial 5 observes it. If not, the fallback is a host-side `shutdown.return` helper (see "Residual risk of running to failure").
- **Q19. Two checks before `guard drill` is trusted:** the rule-timer deadman on the spare plug (test 8), and no retained `cmnd/POWER` for `rack_outlet_plug` on the broker (`mosquitto_sub` from the Mac failed to connect on 2026-11-11, so it needs the broker's credentials or a run from `max`).
- **Q21. Closed 2026-11-12.** The `effective` fields and `rackmains_guard_failed_hosts` are final with the guard's policy type.
- **Q22. Power off and on behaviour per model of host.** Observe, on `mad` (Mac mini M2 Pro, Asahi) and on `max`, `may` and `meg` (the 2014 Mac minis, Macmini7,1), what each does when its power is lost and when it returns: after `asleep --deep` (on `max`, `--shallow`), and with the cord pulled from a running host. Record per host whether it boots by itself, the time to ssh, and whether the containers come back healthy. The three 2014 minis are expected to behave the same (`AFTERG3_EN` is cleared on each); `mad` is the one at risk, since the macOS "Start up automatically after a power failure" setting is not known to carry into Linux on an M2 Pro. This is test 5 in "Trials, tests and rollout", run on all four hosts, and its result decides the restart shape.

**Decided, kept for reference**
- **Q1 to Q17 and Q20 (2026-11-12)** are settled and folded into the sections above: alerting, health from the UPS and the staleness reminder (rejected) under "Metrics, MQTT and the outage CSV"; calibration under "Goal and shape"; the exit codes, the drill and stop behaviour in "The guard CLI"; the model ceiling in "The shutdown guard"; the plug password in "Trials, tests and rollout"; trial 5 in the same section. Q11 closed with no action. Q12 to Q15 are accepted: every shed and wake call runs in its own worker thread with a 30 s connect and silence timeout that frees the worker on error and never caps or interrupts other calls ("The shutdown guard"); the poll, the CSV row and the model call are both 1 s on battery, in step with the poll ("Metrics, MQTT and the outage CSV", "The model seam"); 100 files kept, 1 MB per file, whole-document rewrite. Q16 and Q17 (drill constants, plug sampling and the backup window) are in "The guard CLI". Q18, Q19, Q21 and Q22 keep their numbers. The CLI's tests (Q20) are a parsing test per flag and subcommand, as `tempstat`'s `cli_parses_*`, written in the CLI build step.
- **Run to failure, no final UPS command** (2026-11-11), at the top of this file.
- **Model promotion** (2026-11-11). The first release ships the constants project, so a model is always present, and later releases replace it with a fitted one as part of the codebase once data is collected. There are no `static`, `shadow` or `live` modes and no `guard_mode`; `rackmains_guard_live`
  (dry-run or live) stays deployment config in `.env_prod`. A refit is a release.
- **Guard status** (2026-11-12). One `liveness.json` on tmpfs, replacing `rackmains_guard_state.json`, `guard_heartbeat`, `rackmains_battery_state.json` and `status.json`, as written in "Control plane". The ack is a CSV row, host results are CSV rows, and the publisher is fed over a channel.
- **`drain` deadman** (2026-11-11). 3 h for the first run with the guard armed, printed in the plan, then set from the measured time to cutoff plus a margin.
- **Trials, tests and rollout restated** from the model plan deleted in commit `ca0c83150`, and **reachability during a drain**, in the sections of those names.
- **The guard CLI** (2026-11-11): `rackmains serve|check|guard drill|stop|tail|list`, plan-only without `--force`, one binary, plug columns in the outage CSV, recording after restore
  until the CSV `end` row capped at 30 min.
- **Restart shape.** `awake` when mains returns early, `AFTERG3_EN` after a cut; the power-on-after-cut test (5) confirms it per host.
- **`rackmains_mains_failed` stays a read-only `binary_sensor`;** there is no switch row, since `guard_auto` was dropped on 2026-11-12.

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
- **A unix socket or REST API for the tool and for health.** See "Control plane": files carry the state that must survive a restart, and the liveness file is the honest health signal.
- **The guard pause, `guard_auto`.** Designed 2026-11-11 and dropped 2026-11-12, with `auto.json`, the `guard_auto` and `guard_auto_expires` entities, the Home Assistant switch and `rackmains/command` subscription, `guard auto` and `drill --no-shed`. A deliberate cut with the guard live now sheds the hosts gracefully, and maintenance without that is a dry-run release.
- **A test tool as a host script or in Python.** A second reader of the outage CSV and the policy, which can drift from the guard's own; replaced by a Rust binary sharing the library.
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
4. **The module `CLAUDE.md` describes the drill.** the `serve`, `check` and `guard` commands and the `rackmains serve` entrypoint, `rackmains guard drill`, the plug columns in the outage CSV and the `drill.json` marker.
5. **The notebook title cell has what it needs.** It outlives this plan, so its references back to the unit, the metric names and the outage CSV
   are replaced by that content, or by `CLAUDE.md`, before this file goes.
