# rackmains

**Status, 2026-10-29.** Built and tested locally, not released. The publisher is done: it reads the NUT driver socket,
publishes `rackmains/{data,status}` to the broker, and ships with a mock driver and a mock-backed system test. The host setup
(`install_prep.sh`, `install_pre.sh`) and `tools/outage`, the tool that cuts the rack's mains through its smart plug, are
written and unit tested. The host side of the shutdown is built and tested on `max`, in the `system` module (`asleep`, `awake`
and the restart-after-power-loss setting). Waiting on you: the nine workbook rows (phase 3), the release, and the
power-on-after-cut tests. The shutdown guard is designed and not built. This file holds the status, what the code cannot say, and the open decisions; the code and the
module `CLAUDE.md` say how the publisher works.

---

## Goal and shape

1. **Publish** the rack UPS's mains and battery state to Home Assistant over MQTT, so an outage or a failing battery is
   visible and automatable there. Built.
2. **Guard** the rack: on a power cut, shut the other servers down early, `max` last, and bring the others back if mains
   returns in time. Designed; a thread inside this container.

**Simple and consistent.** rackmains only ever produces data. Nothing in the running service measures, fits or learns the
battery. Thresholds are conservative timers, fitted **offline** from recorded trials and real outages, in the way the Davis
console battery is (`src/may/mlserver/src/main/notebook/weatherstation_console_battery.ipynb`: query the history, fit, emit a
small generated artefact), and baked into the image as `thresholds.json`. Changing them is a release.

**Out of scope, deliberately**

- **No InfluxDB writer.** Home Assistant records the entities itself and that history is the database.
- **No supervisor integration.** The guard lives here, so supervisor needs no UPS plugin. Two passive links: supervisor's
  generated config for `macmini-max` picks up the `rackmains` container on its next generate, and a host the guard powers off
  has its supervisor publish `offline`. A cut during the 01:00 nightly backup interrupts it; the guard does not coordinate.
- **No `upsmon` or `upssched`.** They stay disabled; see the designs left out.
- **No in-process calibration.** No runtime `calibrate` tool, no reloaded `calibration.json`, no `calibrating` flag, no
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
aid independent of rackmains; `systemctl stop ups-recorder` ends it. **It is dropped after trial 1**, once the new publisher has
agreed with it through a long cut and real data is being captured: stop the unit, delete `ups_recorder.py` and the `validation/` directory, and rely on the published entities in
Home Assistant's history and the `outage` events log. The HID fields it also logged are dropped from the design (see the HID verdict below).

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
silent failure (the outlets are unprotected) and alerts at once; a test flag is ignored because the shed waits `shed.max_seconds`. The beeper is audible only,
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

## Metrics, as Home Assistant sees them

The NUT variable to payload key mapping is `SAMPLES` in `nut.rs`; the payload is `timestamp`, `period_ms`, `mains_status`
(NUT's flags verbatim), `mains_outages` and `samples`.

| Payload key | HA `unique_id` | Namespace | Unit | `device_class` |
|---|---|---|---|---|
| `mains_status` (top level) | `rack_mains_status` | `binary_sensor` | | `power` |
| `rack_mains_input_voltage_volts` | `rack_mains_input_voltage` | `sensor` | V | `voltage` |
| `rack_mains_input_voltage_fault_volts` | `rack_mains_input_voltage_fault` | `sensor` | V | `voltage` |
| `rack_mains_output_voltage_volts` | `rack_mains_output_voltage` | `sensor` | V | `voltage` |
| `rack_mains_output_frequency_hertz` | `rack_mains_output_frequency` | `sensor` | Hz | `frequency` |
| `rack_mains_utilisation_percent` | `rack_mains_utilisation` | `sensor` | % | |
| `rack_battery_charge_percent` | `rack_battery_charge` | `sensor` | % | `battery` |
| `rack_battery_voltage_volts` | `rack_battery_voltage` | `sensor` | V | `voltage` |
| `mains_outages` (top level) | `rack_mains_outages` | `sensor` | | | 

**Short outages (decided 2026-10-28).** A one-second cut at 18:05:25 showed as `OB DISCHRG` in one 2 s recorder sample and was
gone by the next, so a 10 s publisher would usually miss it. The publisher therefore polls the socket every 2 s but publishes
every 60 s, and **also publishes at once whenever `mains_status` changes**, so the start and end of any dip the driver saw reach
Home Assistant within about 2 s and its history records both. `mains_outages` counts the `OB` onsets seen since the service
started (a `total_increasing` sensor, so a restart's reset is handled by Home Assistant). While on battery it publishes every
poll, so a trial sees the voltage at 2 s steps. A dip that falls between two driver polls is still unseen; the counter cannot
recover what the driver missed.

`rack_battery_charge` is NUT's coarse estimate and is published because it was asked for; the guard never uses it.

**Candidate new metrics, all to get workbook rows (decided 2026-10-28).** The guard's state joins the payload as a `guard` object and needs a schema declaration. Every row below
is added to the workbook and `Enabled` for the dry-run release, so nothing is added later by surprise.

| Name | Payload path | Source | Verdict |
|---|---|---|---|
| `rack_guard_state` | `guard.state`: `idle`, `waiting`, `shedding`, `holding`, `halting`, `restoring` | the guard | publish |
| `rack_guard_live` | `guard.live`, off while in dry-run | the guard | publish |
| `rack_guard_mains_seconds` | `guard.mains_seconds`, seconds on line since the last `OB` | the guard | publish, lets `outage` enforce the settled rule |
| `rack_guard_battery_seconds` | `guard.battery_seconds` | the guard's accumulated time | publish |

## Metrics collected, and what the model needs

| Name | Source | Where it lands | Use for the model |
|---|---|---|---|
| `rack_battery_voltage` | NUT `battery.voltage`, 4 s refresh | Home Assistant, and every poll on battery | the knee, the plateau, the sag at transfer, the trial abort |
| `rack_mains_utilisation` | NUT `ups.load`, whole percent | Home Assistant | the live load input; the load axis of `watts_by_load` |
| `rack_mains_status` | NUT `ups.status` flags (`OB`, `OL`, `LB`) | Home Assistant, and at once on change | the trigger and the time on battery; whether `LB` raises |
| `rack_mains_outages` | rackmains counter of `OB` onsets | Home Assistant | context only |
| `rack_mains_input_voltage`, `_fault`, `rack_mains_output_voltage`, `rack_mains_output_frequency` | NUT | Home Assistant | none; input reads 8.4 V when cut |
| `rack_battery_charge` | NUT's voltage-based estimate | Home Assistant | none; it is a voltage lookup |
| `rack_guard_state`, `_live`, `_mains_seconds`, `_battery_seconds` | the guard | Home Assistant | the guard's own clocks; `mains_seconds` also enforces the settled rule for trials |
| Plug watts and current | Tasmota `Status 8` on `rack_outlet_plug` | the `outage` events file, around the cut only (0 W while its relay is open) | `watts_by_load` and so `usable_wh` |
| Events: cut, abort, restore, hosts down, each poll's reading | the `outage` tool on the Mac | JSONL, fsync per line | the knee time, the failure record, the fit input |
| Follower shed times and `max`'s halt time | test 4 | this plan | `takes_seconds` |
| Recovery after a trial | voltage and `ups.load` on mains | Home Assistant history and the events file | none; kept as evidence only, since nothing on mains shows the state of charge |

**Needed for the model and not collected yet**

| Need | Why | How it is got |
|---|---|---|
| `usable_wh` | the model's energy budget, from full to the knee | trial 5: watts (through `watts_by_load`) integrated over the discharge, at two loads (all servers up, then `max` alone) |
| `watts_by_load` | the unit reports no current or power | plug readings on mains before and after each trial, paired with `ups.load` |
| `takes_seconds` | when to shed and halt so the shutdown finishes before the knee | test 4, several runs per host |
| Starting state | the model assumes a full battery at the first `OB` | float voltage and `guard.mains_seconds` before the cut |
| Whether `LB` raises at failure | decides if it is a usable backstop | trial 5 |

## Phase 3, entity rows to add to `entity_metadata.xlsx`

Eight `sensor` rows and one `binary_sensor` row (the nine above, `Enabled`; the new `rack_mains_outages` takes `state_class` `total_increasing`), then the four guard rows above (`Enabled`), all `device_via_device` **`RackMains`**, in
`src/all/_/src/build/resources/metadata/entity_metadata.xlsx`. Tell me when they are in and I run `fab generate`; I do not
edit the workbook. Fill each new row **down from a `TempStat` row** so the four topic columns and `name`, `device_name` and
`device_identifiers` stay calculated (`rackmains/data`, `rackmains/command`, `rackmains/status`,
`homeassistant/<namespace>/rackmains/<unique_id>/config`). Never type those in.

Shared by all nine rows, mirroring `TempStat`: `entity_status` `Enabled`, `unique_id_device` `macmini-max`, `entity_domain`
`Device Conditions Rack`, `entity_group` `Diagnostics`, `device_suggested_area` `Rack`, `_device_name_suffix` `Mains`,
`device_manufacturer` and `device_model` the UPS's own, `device_sw_version` `ASYSTEM_VERSION`, `qos` `1`, `force_update`
`false`, `sample_period` `60`, `powercalc_enable` and every `powercalc_group_*` blank. `state_class` is `measurement` for every
sensor except `rack_mains_outages`, which is `total_increasing`. The `value_template` is, with each row's own key (the outages
counter reads the top-level `mains_outages` instead of `samples`):

```
{{ (value_json['samples']['rack_battery_charge_percent'] | float(None)) if (value_json['samples'] is defined and value_json['samples']['rack_battery_charge_percent'] is defined) else (states('sensor.rack_battery_charge') | float(None)) }}
```

`rack_mains_status` keeps its last state when the status is unreported, so a failed read never reads as an outage:

```
{{ ('OFF' if 'OB' in value_json['mains_status'].split() else 'ON') if value_json['mains_status'] is defined else states('binary_sensor.rack_mains_status') }}
```

After the rows: `fab generate` and read the diff, then add a check that every key a generated `value_template` reads is a
declared payload key. The system test's declared-topics check cannot pass until the rows exist.

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
  `openssh-client` pinned in the image), the generated host list and thresholds, and a state file under `/asystem/mnt` so a
  restart mid-sequence knows who it already shut down. It reconciles with that file on every start.
- A panic ends the process (release profile aborts) and Docker restarts it. The health check reads the guard's heartbeat from
  the state file. The guard writes its state to that file and the publisher reads and publishes it, one way.
- Every action is idempotent. A sequence starts only on a fresh reading that says on battery and a restore only on a fresh
  reading that says mains; once started, failed or stale reads do not stop it, because a USB glitch mid-outage must not leave
  the servers up until the battery is flat.
- The host list is generated by `fab generate`: workbook `Server` rows that are `Enabled`, area `Rack`, model starting
  `MacMini` (`mad`, `max`, `may`, `meg`; `jen` is a Pi in `Wardrobe`), ordered by `.hosts`, joined as `macmini-<label>`, MACs
  from the same rows. Nothing is typed twice.

**Steps (first version, timers and flags only).** The host actions are `asleep` and `awake` from the `system` module (the
next section). A host is never powered off.
1. **Watch.** Polls every 2 s. Time on battery accumulates from the first `OB`, so a short blip simply never reaches
   `shed.max_seconds`, and resets to zero only after `mains_stable_seconds` of continuous `OL`, so a grid that flaps with dips under that apart cannot keep the
   servers up.
2. **Shed.** At `shed.max_seconds` on battery, or `LB`: run `asleep --deep` on the followers in parallel, `meg` last so Home
   Assistant and the broker outlast the rest, each over ssh with a key whose `authorized_keys` forces the command (`restrict`,
   no shell; see the forced-command test), done when its `RESULT asleep status=0` arrives. Any other code (1 error, 4 timeout,
   5 unclean) is logged and alerted and the guard moves on; it never retries in a loop. On `max`, run `asleep --shallow`
   stopping every container but rackmains (supervisor first, it binds `/`). A shed is not undone by the voltage rebound when
   the load drops, only by `mains_stable_seconds` of mains.
3. **Halt.** At `halt.max_seconds` on battery, or on `LB`, whether or not every follower has finished (a halt implies a shed,
   so an `LB` runs both at once, with no staging): send `shutdown.return` first, with `ups.delay.shutdown` raised from 30 s to
   cover `max`'s `asleep --deep` plus a margin, then start `asleep --deep` on `max` detached. It stops rackmains and the guard
   with it, so its result is only in `/run/asleep.log` on `max`, and `shutdown.stop` cannot be sent afterwards. The UPS then
   cuts and restores, and every host boots on AC restore (power-on-after-cut test, below).
4. **Mains returns first.** After `mains_stable_seconds` of continuous `OL`, run `awake` on each follower the state file
   lists once its `asleep` has returned, and on `max` to restart what was stopped. `asleep` is undone by `awake`, so unlike
   a `poweroff` there is nothing to wait on being down. If the halt has started there is nothing to cancel.

**Safety rails.** It ships in dry-run, logging the exact commands it would run, and goes live only after the trials show the
conservative timers fit. It honours its hard override (`LB`) in dry-run too. The keys can
power off and nothing else. Any status flag that is not `OL` is surfaced; an alarm or fault flag raises an alert in Home
Assistant.

**Later.** The decision (reading and history in, action out) stays a pure function apart from the state machine and the
runners, so the timer policy is replaceable; if a better policy is ever wanted it is fitted offline like the thresholds.

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
  `/run/asleep.log` or `/run/awake.log`. A non-zero `asleep` leaves the host in whatever state it reached.
- **Power on after a cut.** The module's `install_prep.sh` clears `AFTERG3_EN` (bit 0 of the register at `00:1f.0`, offset
  `0xa4`, [the method](https://gist.github.com/coldie/072d8e97dfad89d424ba91641641511d)) on every install; `max`, `may` and
  `meg` (Macmini7,1) read `1c08`. `mad` is a Mac mini M2 Pro under Asahi with no Linux knob on kernel 6.14: the setting lives
  in the SMC and is set once from macOS ([AsahiLinux/docs#156](https://github.com/AsahiLinux/docs/issues/156)), which is
  **yours to do by hand** (test 5). Whether any host boots after a cut is **not yet tested**.
- **Tested on `max`, 2026-10-29.** Argument and precondition codes; dry runs that leave the host unchanged; a real shallow
  cycle with supervisor left running, returning 0 and restoring the host exactly; an unclean cycle (a container that ignores
  SIGTERM) returning 5 with exit code 137 reported; `awake` error paths returning 1 and 6; and a read-only remount round trip
  on every filesystem type in the estate, on all four hosts. **Not yet:** a real deep run, the timeout code end to end, any
  other host, the power-on-after-cut test.

## The model (mlserver): inputs, outputs and fit

The model estimates how much usable battery is left, so a step can fire sooner than its `max_seconds` when the battery is worse
than the times assume. It never fires one later (the times are the guard). It is fitted offline and served by mlserver; the guard
asks it once per poll, and nothing depends on the answer.

**Inputs, live, all available during an outage.** Only what the guard already holds on `max` can be an input, because the plug and
anything upstream lose power in a real outage, and mlserver is asked rather than consulted for data.

| Input | Source | Reliable? | Notes |
|---|---|---|---|
| `ups.load` over time | NUT, 2 s poll, whole percent | **yes as a reading, unproven as a power measure** | 10 to 18% over 4.5 hours on mains (mean 10.9), 12 to 15% on battery; each step is about 4.8 W (30% relative at the rack's load). It moved 10 to 12 to 13% at transfer and 12 to 15% during the 145 s cut, and whether that is the rack's load or a change in how the unit measures on battery is not known. It has not been checked against watts (the paired sampling is paused) and whether it is VA or W is unknown |
| Seconds on battery | the guard's clock | yes | resets only after `mains_stable_seconds` of `OL` |
| Seconds on mains since the last `OB`, and the energy already used | the guard's state file | yes | the credit-back basis; lost if the state file is lost, in which case a full battery is assumed |
| `battery.voltage` | NUT, 4 s refresh | reading yes, information weak | 13.3 to 12.0 V in 11 s then flat; sags under load and rebounds when followers go. Context for the fit, not a live input to the estimate until trial 5 shows the knee |
| `ups.status` (`OB`, `OL`, `LB`) | NUT | `OB`/`OL` yes, `LB` untested | gates when the model runs |

Not inputs, by decision or because they are not usable: temperature, battery age, the unit's own capacity and runtime, NUT's
`battery.charge`, input voltage and every HID field.

**Outputs, per lookup.**

| Output | Meaning |
|---|---|
| `percent_remaining` | `100 * (1 - Wh used / usable_wh)`, where watts come from `ups.load` through the fitted load-to-watts map and the energy is integrated over the time on battery |
| `seconds_remaining` | `(usable_wh - Wh used) / watts at the current load`: what a step compares with its `takes_seconds` plus `margin_seconds` |
| `version` | the fit that answered; the guard refuses an answer whose version differs from `thresholds.json` |

**Fitted parameters (kept on the mlserver side).** `usable_wh` and the load-to-watts map. **One assumption, not fitted:** energy used is
credited back linearly over 6 hours of mains (the manual's about 6 hours to 90%), a constant on the mlserver side, so a second dip
soon after the first starts with less than a full battery. It is not in `thresholds.json` and not a parameter anyone tunes.

**Can the outputs be modelled and fitted offline with enough data? Mostly as a calibration, not as a statistical fit.**
- **`usable_wh` (the energy to the knee) is one number per battery.** There is no ground-truth percentage anywhere: the percentage
  is defined as the fraction of that energy used, so the label is constructed from the time to the knee in trial 5, not
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
  battery as not recovered. The guard's own clock resets after `mains_stable_seconds` and so already treats the battery as
  recovered much sooner; the model's slower credit is what covers the second-dip case.
- **What more data buys.** Deliberate cuts with `outage` are repeatable at a chosen load and starting state, so the data is
  limited by battery wear and recharge time, not by how often outages happen. Shallow cuts of a few minutes are cheap and can be
  run many times: they give the plateau at each load, the sag at transfer, the `ups.load` behaviour and the load-to-watts map.
  They do not reach the knee. Second-dip runs (a cut, then another after 10 minutes, an hour and 6 hours) test the recharge
  assumption. Deep runs to the voltage floor are the expensive ones and are made once per battery, with a repeat if the spread
  matters. Real outages add the sag, the plateau at the actual load and a check of the shed and halt timings, but rarely the knee,
  because the guard is built to be finished before it. The percentage stays a refinement of the times, not a replacement for
  them, which is why `max_seconds` stay the guard.
- **mlserver is a host, not a necessity.** A calibration this small could be a single formula; the guard could even evaluate it
  locally. mlserver is chosen to keep the fit and the notebook beside the Davis console battery model, and costs the runtime
  dependency the failure handling below covers.

**Future: fitting the load-to-watts map and `usable_wh` (not built, not run).** Nothing here is done; it describes what the offline
fit will do when the trials have supplied the data.

**Features and outputs of the fit.**

| | Feature or output | Source | Role |
|---|---|---|---|
| Fit input | `ups.load` series through each trial | NUT, logged by `outage` events and the recorder | converted to watts by the map, then integrated to Wh |
| Fit input | plug watts and current, before and after each cut | Tasmota `Status 8` (0 W while the relay is open) | builds the map |
| Fit input | seconds from transfer to the voltage floor or `LB` | the `outage` events file | the time to the knee, so the Wh to the knee |
| Fit input | `battery.voltage` series | NUT, 4 s refresh | locates the knee and the plateau, and the sag at transfer; checks the map; not a live input |
| Fit input | `ups.status` flags | NUT | marks transfer, `LB` and recovery |
| Fit input | follower shed times and `max`'s halt time | test 4 | `takes_seconds`, `margin_seconds` (policy, not the model) |
| Fit output | `usable_wh` | trial 5 | the energy budget |
| Fit output | the load-to-watts map | mains pairs around each trial | converts a live `ups.load` to watts |
| Fixed assumption | the 6 hour recharge credit | the manual | not fitted |
| Live input | `ups.load`, seconds on battery, seconds on mains since the last `OB`, energy already used, `ups.status` | the guard and NUT | the lookup request |
| Live output | `percent_remaining`, `seconds_remaining`, `version` | the model on mlserver | a step fires sooner than `max_seconds` when the percent falls to `target_percent` or the seconds fall to `takes_seconds` plus `margin_seconds` |

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

## Thresholds, fitted offline and baked in

`thresholds.json` is **policy only**: what to do and when. The model that turns a reading into a percentage of battery remaining
is **not in the guard and not in this file**; it is fitted and served by mlserver (`may`), as the Davis console battery model is,
and the guard asks it. Each step carries a time ceiling and an optional percentage target. **Optional fields may be absent or
`null`, and the two mean the same**, so the first release can be written without them and the model release adds them without a
schema change. Unknown keys are still rejected, so a misspelt optional key (`target_percnt`) is an error rather than a silently
absent field. JSON has no comments and nothing else in this repo puts them in a data file; the repo documents a JSON shape in the
typed definition that reads it (the dataclasses in `asystem/schema/document.py`, the serde structs in `schema.rs`), so the schema
is documented by the Rust definition below, whose `///` doc comments are the interface documentation the code standards allow.

```rust
/// The guard's thresholds, baked into the image as `thresholds.json`. Optional fields may be absent or `null`; any other missing
/// key, or any unknown key, is an error. Until the model lookup is built the validator rejects a `target_percent`, a `takes_seconds` or a `margin_seconds`.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Thresholds {
    /// Identifies the fit these thresholds belong to, bumped on every rewrite so the file can be matched to the model that
    /// mlserver is serving. Required, and sent with every lookup so a mismatch is refused.
    pub version: u32,
    /// When to shut the followers down. Required.
    pub shed: Step,
    /// When to halt `max` and cut the UPS. Required, and later than `shed`.
    pub halt: Step,
    /// Seconds of unbroken mains before the time-on-battery clock resets to zero and the shed followers are woken. Required.
    pub mains_stable_seconds: u64,
    /// Seconds of safety added to a step's `takes_seconds` when checking the time remaining. Optional; required if any
    /// `takes_seconds` is set.
    #[serde(default)]
    pub margin_seconds: Option<u64>,
}

/// A step fires on whichever comes first: its time, its percentage target, or `LB`. The time is the guard: the model can only make
/// a step fire earlier than `max_seconds`, never later.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Step {
    /// Accumulated seconds on battery at which the step fires whatever the model says, or whether the model answers. Required.
    /// Fitted offline from the trials and changed only by a release.
    pub max_seconds: u64,
    /// Percentage of battery remaining at or below which the step fires. Optional; needs the model lookup. `shed` is above `halt`.
    #[serde(default)]
    pub target_percent: Option<u8>,
    /// Measured seconds the step takes to finish: for `shed` the slowest follower from the start of `asleep` to its `RESULT`, for
    /// `halt` `max` from `asleep --deep` to the UPS cut. Optional; with the model the guard also fires the step when the model's
    /// seconds remaining fall to `takes_seconds` plus `margin_seconds`, so a percentage cannot leave too little time at a high load.
    #[serde(default)]
    pub takes_seconds: Option<u64>,
}
```

**The first release, minimal** (optional fields left out):

```json
{
  "version": 10,
  "shed": { "max_seconds": 120 },
  "halt": { "max_seconds": 450 },
  "mains_stable_seconds": 300
}
```

**The same, with the optional fields written as `null`** (identical meaning, accepted too):

```json
{
  "version": 10,
  "shed": { "max_seconds": 120, "target_percent": null, "takes_seconds": null },
  "halt": { "max_seconds": 450, "target_percent": null, "takes_seconds": null },
  "mains_stable_seconds": 300,
  "margin_seconds": null
}
```

**With the model lookup** (illustrative numbers, not built). The times are unchanged, because they are the guard; the percentage
targets add an earlier trigger when the battery is worse than the times assume (a second dip soon after the first, or a high
load):

```json
{
  "version": 11,
  "shed": { "max_seconds": 120, "target_percent": 40, "takes_seconds": 240 },
  "halt": { "max_seconds": 450, "target_percent": 20, "takes_seconds": 180 },
  "mains_stable_seconds": 300,
  "margin_seconds": 60
}
```

The model cannot lengthen the runtime. If trial 5 shows the knee is later than the times assume, the fit raises `max_seconds` in a
new release, as before; the model only adds triggers that fire sooner.

**The mlserver lookup (not built).** The guard asks mlserver for the battery remaining; the fit stays on the mlserver side
(`usable_wh`, the load-to-watts map and the 6 hour recharge assumption), which is why none of it is here. The model uses no temperature and no
  battery age.
- **Request.** What the guard knows locally and nothing else: the `version` it holds, `ups.load` and `battery.voltage` over the
  time since the last full battery, the accumulated seconds on battery, and the seconds on mains since the last `OB`. mlserver
  stays stateless, so the guard keeps the series in its state file and sends it, and the model credits the recharge from it at its fixed rate.
- **Response.** `percent_remaining` and `seconds_remaining` at the current load, plus the model version it used.
- **Failure handling.** One lookup per poll with a short timeout, off the decision path. An answer older than a few polls, a
  timeout, an error or a version mismatch counts as no answer, and the guard does nothing extra: `max_seconds` and `LB` apply
  in every case. mlserver sits on `may`, which the guard sheds first, and the network or broker may be gone in an outage, so the
  lookup is expected to fail exactly when it matters; it costs nothing because the times already cover it.
- **Where the address lives.** The mlserver endpoint is a run-dependency connection setting in the module's `.env_*` files, not
  in this file, as the broker's is.
- **Dry-run.** The lookup runs in dry-run too, so a month of real answers can be compared with the times before it acts.

The file has no dates and no battery fields. It is baked into the image with the code, so `version` is a label that matches it
to the mlserver model; a lookup whose `version` differs from the model's is refused.

**Until the model lookup exists the guard reads only the `max_seconds` and `mains_stable_seconds`.** The validator rejects a file
with a `target_percent`, a `takes_seconds` or a `margin_seconds`, so a filled-in file cannot be mistaken for a working model. That
one check is the only code the optional fields cost; the guard has no dead branch for them. When the lookup is built the
validator changes to: `shed.target_percent` is above `halt.target_percent`; `halt.max_seconds` is above `shed.max_seconds`; and a step with a `target_percent` also has a `takes_seconds`, and `margin_seconds` is set.

**No voltage thresholds until modelling is done (decided 2026-10-28).** Voltage was weighed as a trigger and dropped. It is the
only signal that follows the battery's ageing, but it is flat on the plateau for minutes (the 145 s run sat at 11.9 to 12.0 V),
the knee is probably steep because an inverter draws roughly constant power, so the current (inferred, the unit reports none)
rises as the voltage falls and the fall accelerates, and the gap between the plateau and the knee is perhaps 0.4 V, inside the
noise of load steps and the 4 s refresh. A threshold that fires less than `max`'s halt duration plus a margin before the cutoff
is useless, and one on the plateau fires falsely. So the times, set for a worn battery, plus `LB` carry the job, and the voltage
is still published and recorded so the curve accrues. Voltage thresholds, or the sag in the first seconds of an outage (13.3 to
12.4 V, growing as the battery ages), could be added later as new optional fields, if trial 5 shows the knee leaves at least the
halt duration plus a margin above the cutoff. The `outage` tool keeps its own abort voltage (`-F/--floor-volts`), which protects
a trial and is not a guard threshold.

What mlserver's model needs, and where it comes from, is in "Metrics collected, and what the model needs" above: `usable_wh` and
the load-to-watts map from trial 5 and the plug's readings around it, and `takes_seconds` from test 4. The recharge rate is a documented
assumption, not a measurement.

**Baked into the image** under `src/main/resources/image/`, so changing it is a release and the file the guard runs on is the
file that was reviewed. The guard validates it at start (every set number finite, `shed.max_seconds` below
`halt.max_seconds`, the model rules above) and **refuses live mode** if it fails; it stays in dry-run and says so.
Dry-run versus live is deployment config in `.env_prod`, never in this file.

**Staleness is not enforced by the file.** A battery that ages makes these times optimistic, and nothing in the file follows the
battery by itself. So a battery replacement, a change of load of more than about 30%, or a time to the abort voltage measured
20% below the last fit each means a new trial, a new fit and a release. Tracking that is a reminder, not a field (an open
decision).

**Starting values (rollout A).** `shed.max_seconds` 120, inside the 145 s already held at service load
with no knee. `halt.max_seconds` is `shed.max_seconds` plus the slowest measured follower shed plus a margin, set once test 4
gives the shed times (Docker allows 90 s to stop per host and each runs four to six containers). They shed early on short
outages and so waste battery, but never outrun what is proven.

**Later, fitted from trials and real outages.** An offline notebook, kept beside the weather-station one in `mlserver`, reads
the Home Assistant history and the `outage` events logs, finds the knee at service load, the transfer sag (internal resistance)
and the time to the abort voltage, and writes `thresholds.json`: `shed.max_seconds` is the knee time less `takes_seconds`
(measured slowest shed, `max`'s halt, a margin), never below a minimum, and `halt.max_seconds` follows from it. If `takes_seconds` does not fit inside the knee, the notebook says the battery cannot
support the shutdown and writes no file.

**Watts for the fit, from the plug.** The unit reports no current or power, so the fit takes real watts from the plug's own energy
reading (`Status 8`), which has 1 W resolution against the whole-percent `ups.load` (about 4.8 W a step). The plug's relay is open
during a cut, so it reads 0 W while the battery discharges: the watts come from before the cut and after the restore. The
notebook pairs them with the `ups.load` logged at the same moments to build a load-to-watts map, applies that map to the
`ups.load` recorded through the discharge, and integrates to the usable energy to the knee in Wh. The plug's figure includes the
UPS's own losses and float charge, so the map overstates the battery draw a little, which errs on the safe side. It is a fit
input only; the live guard sees only `ups.load`, since the plug is upstream and loses power in a real outage.

## Setting the thresholds, in rollout steps

The thresholds start very conservative, ship in a release, are tested against real data, then are reset in a second release.
Nothing is lengthened on a guess; each step is allowed only by the evidence named beside it.

| Step | Thresholds | Mode | Allowed by | Evidence it produces |
|---|---|---|---|---|
| A, floor | `shed.max_seconds` inside the proven span (145 s at service load held with no knee), `halt.max_seconds` from the measured shed times | dry-run | per-host `asleep` times (test 4); the forced-command test (3) | the guard's decisions on real mains events, logged but not acted on |
| B, live and cautious | the same | live | trial 1 held for the whole sequence length at worst-case load with no knee and no `LB`; trials 2 to 4 pass; the restart path chosen | real outages and `outage` cuts exercise the whole chain; each is a data point |
| C, measured | `shed.max_seconds` set to the knee time less `takes_seconds` | live | trial 5 run to the floor once on this battery, plus any real outage, fitted offline | the knee at service load, the cutoff, whether `LB` raises |
| reset | recomputed | live | a battery replacement, a load change over about 30%, or a time to the floor 20% below the last fit | a new trial and a release |

**What each number needs.**
- **`shed.max_seconds`.** The knee time at service load (trial 5) less `takes_seconds`. Until then only a span already survived is
  allowed: trial 1 proves it, and rollout A stays inside it. Check: the voltage at the end of trial 1 is still above the floor
  and has not begun to fall.
- **`takes_seconds` and `margin_seconds`.** The slowest follower's `asleep`, start to `RESULT` and including the slowest container stop, and `max`'s
  `asleep --deep`, each measured several times on each host (test 4), plus a margin. The margin is a fraction of the spread seen, not a guess.
- **`mains_stable_seconds`.** The shortest run of `OL` that a flapping grid has not been seen to break, from the history, and
  long enough that a battery drained by the outage has begun to recover (about 6 hours to 90% per the manual, so a longer
  value is safer; there is no measure of the recovery, so it is a judgement).

**Why the floor and the knee need a run to failure.** Only a deliberate run shows the knee: the steps exist to avoid
reaching it in a real outage, so a real outage rarely supplies it. A single run to the voltage floor with the servers down (trial 5) costs some battery life, so it is made
once per battery, and its shape sets the `takes_seconds` every later outage is judged against. Without it the thresholds stay at rollout
B and waste battery but never risk the servers.

**Reset.** A reset is a recompute of `thresholds.json` from the events logs and history, a release, and a dry-run period before
live. The previous file stays in git, so a bad fit is undone by a release.

## The `outage` tool, `tools/outage`

A workspace crate beside `tools/schema`, depending on the `rackmains` library for the flags, duration parsing and log format,
and **run from the Mac through the module's `deploy.sh`** (the operator hook `fab deploy` runs), never in the container and
never from a host on the UPS. It reads `rackmains/data`
from the broker, so it needs no NUT socket and no ssh key.

Flags are the main program's (`-P`, `-T`, `-B`, `--broker-*`, `-L`) plus `-C/--cut`, `-F/--floor-volts` (11.5),
`-U/--plug-host`, `-H/--hosts`, `-E/--events` and `-n/--dry-run`. A run:
1. **Pre-flight.** A fresh reading, `OL` and not `OB`, no abort condition true, the plug reading `ON`, every host answering on
   TCP 22. Otherwise it refuses.
2. **Cut.** `Backlog Power Off; Delay …; Power On`, chaining delays above 360 s because one `Delay` honours only 2 to 3600
   tenths of a second (`Delay 4200` was ignored). The chain beyond one `Delay` is untested.
3. **Hold.** Polls the feed; aborts on `LB`, battery voltage below the floor, three stale polls, or a host down (checked every
   15 s). It does not use the unit's capacity or runtime.
4. **Restore.** On an abort, `Power On` at once. On a full cut, it waits for the plug's own timer and, if the plug is not `ON` 15 s
   after the cut ends, restores explicitly and reports that the device timer did not fire. That is the first independent test of
   the device-side restore.
5. **Recover.** Waits up to 120 s for `OL`, re-checks the hosts, writes a `finish` event, exits non-zero on any failure.

**Safety additions (from the 2026-10-28 review).** `outage` reads `guard.live` from the payload and takes `--expect-guard
<dry|live>`, refusing to start on a mismatch; its pre-flight also enforces the settled rule (needs a published seconds-on-line
value, see the guard metrics); `Power On` on abort is retried while the plug stays unreachable; and it gets a SIGINT/SIGTERM
handler that restores before exiting. Through `deploy.sh` it is **opt-in**: it runs only when `RACKMAINS_OUTAGE=<cut>` is set,
always as a dry run first, so a plain `fab deploy` never cuts the mains.

`-E` appends every step as a JSONL event with an fsync per line. Limits: no Ctrl-C handler, so killing it mid-cut leaves the
restore to the plug's own timer; the plug's WiFi may not survive a long drain, so a long trial needs its device-side timer
proven first.

**Data-capture gaps to close before the long trials.**
- **Run markers.** The events file needs a `run` event first, carrying a run id, the version, the cut, the floor, the hosts,
  the plug's energy reading (`Status 8`), so a recording is attributable and a drain is a data point.
- **Plug watts around the cut.** `outage` samples `Status 8` every poll through the pre-cut baseline and the recovery, since the
  plug reads 0 W while its relay is open, and logs each with the `ups.load` of the same moment, for the fit's load-to-watts map.
- **Failure record.** The `outage` events file, written on the Mac with an fsync per line, is the failure record, so the recorder
  is dropped rather than made durable.
- **Voltage refresh.** `pollfreq 4` is applied on `max` (it was 30, giving 32 s steps); the publisher sees 4 s.

## Trials

Every trial runs only after the battery has settled: on mains at least 12 hours since the last transfer, float steady within
0.1 V for 30 minutes, load steady within 3 points for 10 minutes, all four servers answering, outside the 01:00 backup window.
Abort on voltage, `LB`, a host down, stale readings or a cap, **never on the unit's capacity or runtime**.

| # | Trial | What it does | Needs first | Decides |
|---|---|---|---|---|
| 1 | Hold at service load | `outage` held for the whole rollout A sequence length (about 10 minutes), servers up, guard in dry-run, driven from the Mac | power-on-after-cut test not needed | the conservative timers fit; the knee if it appears |
| 2 | Recover before the shed | live guard, mains back before `shed.max_seconds` | guard built and trial 1 | nothing is shed, the reset works |
| 3 | Recover after the shed | followers shed (`asleep`) then `awake`, one follower first | power-on-after-cut test (5), forced-command test (3), `asleep` timing (4) | the restart path |
| 4 | Halt and UPS cut/restore | maintenance window, someone home; `shutdown.return` tried on a lamp first; if the UPS does not restart, press its On button | trial 3, lamp test | who brings the rack back |
| 5 | Run to failure, once per battery | servers down except `max`, **to the 11.5 V floor or `LB`, once, not to the UPS cutting out**; the events file records on the Mac with an fsync per line; network gear drains; a second point at service load because the low load runs long | device-side dead-man proven (chained `Delay`, or a Tasmota Rule/RuleTimer), trial 1 | the real knee and cutoff, whether `LB` raises, the offline fit |

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
8. **Plug dead-man**: the device-side restore of a chained `Delay`, proven by `outage` with the plug unreachable.
9. **Mac reachability**: that it reaches the broker, the plug and all four hosts from where the trials run, stays awake for
   trials up to 15 minutes or more, and that `deploy.sh` can pass the cut and floor through (it is not on the UPS, as `jen` was
   outside the rack), so it can drive the trials.

The guard's build can begin after 3 and 4, with the restart left behind an interface until 5 is in.

**Acceptance.** A flag is a trigger only once it has been seen on this unit: `OB` (seen), the test flag (test 2), `OFF` (test 7).
`LB` and the alarm flags are overrides until observed; if `LB` never appears before the unit cuts, it is dropped from the design
and the time cap carries that job.

## The plug lever

The UPS is downstream of `rack_outlet_plug`, a Tasmota 13 plug at `http://10.0.4.102` (WiFi, `DeviceName` `rack_outlet_plug`,
`FriendlyName` "Server Rack", reading about 81 to 100 W), so switching its relay is a mains outage for the UPS, exactly timed
and independent of Home Assistant (which runs on `meg`, inside the rack). The API is open without a password on the LAN
(`cm?cmnd=…`), so anything on that network can cut the rack; `max` and a bridge container both reach it. `Delay` is in tenths of
a second and honours only 2 to 3600, so a longer cut chains delays. Read-only checks: `Status 0`, `Status 10`.

## Code standards and the completion review

Every Rust crate in this module (`rackmains`, `mockdriver`, `tools/schema`, `tools/outage`, and anything the guard adds) follows
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
   dependency (broker, plug, driver socket, a host) is down, slow or answers garbage, and that the plug is never left off.
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

The first review is owed now on what exists: `rackmains`, `mockdriver`, `tools/schema` and `tools/outage` (no end-to-end test
yet, a few long lines and an inline `json!` shape to tidy), and the two install hooks with their unit tests.

## Gaps found in review, 2026-10-28

| # | Gap | Closed by |
|---|---|---|
| 1 | `deploy.sh` could cut the mains on an ordinary `fab deploy` | opt-in `RACKMAINS_OUTAGE=<cut>`, dry run first (decided) |
| 2 | `outage` ignored the guard's mode | `--expect-guard`, reads `guard.live` |
| 3 | trials ran at average load; the 01:00 backup and service starts raise it | take the worst-case `ups.load` over a week of history; run trial 1 at it, or add the extra load by hand; `LB` is the backstop |
| 4 | a second dip soon after the first finds a partly drained battery (about 6 h to 90%) | the guard's clock resets after `mains_stable_seconds` of mains; the model credits the used energy back slowly over a fixed 6 hours, which covers the second dip |
| 5 | `awake` must not race a running `asleep` | the restore runs `awake` only once each host's `asleep` has returned (exit code and `RESULT` line), and a non-zero `asleep` is surfaced |
| 6 | the current battery's age and condition are unknown | not a model input (decided); the fit is of this battery, and a replacement means a new fit |
| 7 | what else is on the UPS (switch, router, access point, the Mac) is not inventoried | **yours:** list the loads on the UPS; the plug's WiFi and the followers' ssh path both depend on them |
| 8 | the recorder's 2 s data and independent check go | kept until after trial 1 (decided); the 10 s poll no longer applies: the publisher publishes every 2 s while on battery (decided) |
| 9 | the 11.5 V abort floor is arbitrary | set the trial 5 floor from trial 1's voltage slope, then raise it stepwise |
| 10 | the dry-run release is invisible in Home Assistant | every candidate metric gets a workbook row (decided) |
| 11 | ssh key provisioning is unplanned | a step: forced-command key on all four hosts including `max`, private key mounted read-only from a root-only directory on `max`, `known_hosts` pinned; yours to install, the forced-command test (3) proves it |
| 12 | the offline fit's data path is unchecked | confirm the rackmains entities reach InfluxDB at a useful cadence; decide where the Mac-written events logs land for the notebook |
| 13 | `outage` robustness | signal handler and `Power On` retries (above) |
| 14 | rollout A protects nothing | stated: the rack is exactly as exposed as it is today until rollout B is live |

## Remaining phases

Decided 2026-10-28: rollout A starts inside the proven 145 s (`shed.max_seconds` 120, `halt.max_seconds` from the measured shed
times); trial 5 goes to the voltage floor once; the trials are driven from the Mac through `deploy.sh`; and there is **one
first release carrying the publisher and the guard in dry-run**, not a publisher alone.

4. **Close the data-capture gaps** and run the review above on `rackmains`, `mockdriver`, `tools/schema`, `tools/outage` and the
   hooks.
5. **Run the forced-command test and the `asleep` timing** (yours, on the hosts, tests 3 and 4), recording each result here; they
   fix `halt.max_seconds`.
6. **Build the guard, dry-run only**: restructure `run` so the guard starts before the broker connect, generate the host file
   and `thresholds.json`, config and state, the ssh runners for `asleep` and `awake`, the state machine with mock sequences, the heartbeat in the
   health check; then review it as above.
7. **Add the workbook rows (yours), release publisher and guard in dry-run** and confirm `rackmains/status` is `online`, the
   entities appear, and a short `outage` cut turns `rack_mains_status` OFF within one poll and back with `mains_status` `OB`.
8. **Trial 1, then drop the recorder** (the publisher must have agreed with it through the long cut), **then the restart tests
   (5 and 6), then trials 2 to 4 live**, recording each result here.
9. **Trial 5 once per battery**, fit `thresholds.json` offline, release the measured thresholds.

## Open decisions

- **Poll and publish periods.** Poll 2 s, publish 60 s plus on every status change and every poll while on battery. The health
  check tolerates 120 s of staleness today, which a 60 s publish leaves only one missed publish of margin; raise it to 180 s.
- **Switch or binary sensor.** `rack_mains_status` is a read-only `binary_sensor`; revisit if a command is ever wired.
- **Who sends the final UPS command**, the guard (read-write socket) or the host.
- **Restart shape.** Decided: `awake` when mains returns early, `AFTERG3_EN` after a cut; the power-on-after-cut test (5)
  confirms it per host.
- **A staleness reminder.** The file carries no expiry, so a battery replacement or a six-monthly look at the trial 1 result is
  tracked outside it (a Home Assistant reminder, or by hand).

## Designs considered and left out

- **A runtime `calibrate` tool with `calibration.json`.** Reloaded by the guard, with a `calibrating` flag, a health entity and
  an accumulator. Dropped for offline fitting and baked-in thresholds: nothing in the running service learns, and a threshold
  change is a reviewed release.
- **A battery model on the unit's capacity or runtime, or on NUT's estimate.** Both are smoothed model outputs that lag.
- **A fraction-used accumulator with a Peukert load model.** More machinery than the conservative timers justify until a
  trial shows the timers waste battery.
- **Reading the HID interface natively, or a second NUT driver (`usbhid-ups`).** Dropped; see the HID verdict in the unit section.
- **A database writer, as `network` has.** Duplicates what Home Assistant records.
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

## Renames

The module name, topics and entity ids are fixed before the first deploy because a rename strands retained topics: clear
`rackmains/#` and `homeassistant/+/rackmains/+/config` with `mosquitto_pub -r -n` and restart Home Assistant.
