# rackmains

**Built and tested locally 2026-10-28, not released.** Phases 1 and 2 are done: the crate reads the driver socket,
publishes to the broker, and ships with a mock driver and a mock-backed system test. `fab test-sys` passes the publish
test through the real image and broker; the declared-topics check fails until the rows exist. What remains is the
spreadsheet rows (phase 3, yours), the release, a pull-the-plug test and data collection (phase 4), a first shutdown
guard driven by the UPS's alarm flags and timers (phase 5), and a battery model with percentage stages once enough
discharge curves exist (phase 6). The guard is designed below and not built. The code and the module `CLAUDE.md` say how the publisher works; this file holds
the status, what the code cannot say, and the decisions still open.

---

## Goal

1. **Publish** the rack UPS's mains and battery state to Home Assistant over MQTT, so an outage or a failing battery is
   visible and automatable there. Built.
2. **Guard** the rack: on a power cut, shut the other servers down early, `max` last, and bring the others back if mains
   returns in time. Designed, not built.

**Out of scope, deliberately**

- **No InfluxDB writer.** Home Assistant records the entities itself and that history is the database. The module declares
  no `database` schema.
- **No supervisor integration.** The guard lives here, so supervisor needs no UPS plugin and no change.
- **No `upsmon` or `upssched`.** They stay disabled; see the designs left out.

## The host, `max`

Set up by hand 2026-10-28, not yet in any module script: `nut` and `nut-client` installed; `ups.conf` with
`driver = nutdrv_qx`, `port = auto`, `vendorid = 0665`, `productid = 5161`, `protocol = voltronic-qs`; `nut.conf`
`MODE=standalone`; `upsd` on 127.0.0.1 only with a `monitor` user; `nut-driver@powershield` and `nut-server` enabled.
**`upsmon` is not enabled** and no shutdown behaviour is configured. rackmains needs nothing more from the host.

The USB chip is `0665:5161`, a Voltronic serial bridge posing as a HID device. `usbhid-ups` does not work on it, and `q1`
returned short replies; auto-detect settled on Voltronic-QS 0.10, which is why `protocol` is pinned.

The driver socket is `/run/nut/nutdrv_qx-powershield`, `0660` `nut:nut` in a `nut:dialout` `0770` directory, and the
container runs as root. A `:ro` bind mount still connects (checked on `max`). The same socket accepts every command
`upscmd -l` lists, among them `load.off`, `shutdown.*` and `driver.killpower`, and `:ro` does not stop them.

## Metrics, as Home Assistant sees them

The NUT variable to payload key mapping is `SAMPLES` in `nut.rs`. What the workbook rows need:

| Payload key (`samples.`) | HA `unique_id` | Namespace | Unit | `device_class` |
|---|---|---|---|---|
| `mains_status` (top level) | `rack_mains_status` | `binary_sensor` | | `power` |
| `rack_mains_input_voltage_volts` | `rack_mains_input_voltage` | `sensor` | V | `voltage` |
| `rack_mains_input_voltage_fault_volts` | `rack_mains_input_voltage_fault` | `sensor` | V | `voltage` |
| `rack_mains_output_voltage_volts` | `rack_mains_output_voltage` | `sensor` | V | `voltage` |
| `rack_mains_output_frequency_hertz` | `rack_mains_output_frequency` | `sensor` | Hz | `frequency` |
| `rack_mains_utilisation_percent` | `rack_mains_utilisation` | `sensor` | % | |
| `rack_battery_charge_percent` | `rack_battery_charge` | `sensor` | % | `battery` |
| `rack_battery_voltage_volts` | `rack_battery_voltage` | `sensor` | V | `voltage` |

`input.voltage.fault` is the last input voltage the UPS saw drop out, so it normally tracks `input.voltage` until an
event.

`battery.charge` is NUT's own estimate from voltage against `battery.voltage.low` (10.4) and `battery.voltage.high` (13.0),
constants it fills in itself, so it reads 100 whenever the battery sits above 13.0 V and is a poor clock. The published
entity is therefore coarse, and the guard does not use it; see the battery model below.

## Phase 3, entity rows to add to `entity_metadata.xlsx`

Seven `sensor` rows and one `binary_sensor` row, `device_via_device` **`RackMains`**. Tell me when they are in and I run
`fab generate`; I do not edit the workbook. Fill each new row **down from a `TempStat` row** so the four topic columns
and `name`, `device_name` and `device_identifiers` stay calculated, giving `rackmains/data`, `rackmains/command`,
`rackmains/status` and `homeassistant/<namespace>/rackmains/<unique_id>/config`. Never type those in.

Shared by all eight rows, mirroring `TempStat`: `entity_status` `Enabled`, `unique_id_device` `macmini-max`,
`entity_domain` `Device Conditions Rack`, `entity_group` `Diagnostics`, `device_suggested_area` `Rack`,
`_device_name_suffix` `Mains` (so the device is "Rack Mains"), `device_manufacturer` and `device_model` the UPS's own,
`device_sw_version` `ASYSTEM_VERSION`, `qos` `1`, `force_update` `false`, `sample_period` `10`, `powercalc_enable` and
every `powercalc_group_*` blank.

Per row, `state_class` is `measurement` for every sensor, and the `value_template` literal is the one the matching key
needs, shown for the battery and repeated with its own key for the rest:

```
{{ (value_json['samples']['rack_battery_charge_percent'] | float(None)) if (value_json['samples'] is defined and value_json['samples']['rack_battery_charge_percent'] is defined) else (states('sensor.rack_battery_charge') | float(None)) }}
```

`rack_mains_status`, namespace `binary_sensor`, `device_class` `power`, ON while mains is present, keeping the last
state when the status is unreported so a failed read never reads as an outage:

```
{{ ('OFF' if 'OB' in value_json['mains_status'].split() else 'ON') if value_json['mains_status'] is defined else states('binary_sensor.rack_mains_status') }}
```

`rack_battery_low` from the `LB` token is a natural ninth row and is left out because it was not asked for.

After the rows: `fab generate` and read the diff, then add a check that every key a generated `value_template` reads is a
declared payload key, since the workbook is the mirrored copy of `SAMPLES`. The system test's declared-topics check
cannot pass until the rows exist, because the topics come from them.

## Phases 5 and 6, the shutdown guard (designed, not built)

**Why here, and why not a script.** The wanted behaviour is staged and reversible: shut everything down except `max`
first, then `max` if mains has not returned, or bring the others back if it does. Later the stages move to battery level,
50% used and 10% left. `upsmon` only knows on-battery, low-battery and forced shutdown, with timers through `upssched`,
so it cannot express percent stages or a restore. A shell script can, but a state machine with hysteresis, partial
failures and a restart in the middle of a sequence is the part that is hard to test in shell and easy to test in Rust
against a mock driver and a mock ssh.

**Shape.** The same binary and image, a second compose service running `rackmains guard` on the host network (only the wake packet needs
the LAN, ssh works from a bridge, and it listens on nothing), so the publisher and the guard fail separately. Eleven modules run a second
compose service, but each is a one-shot `<name>_bootstrap`, so a second long-running service is new here; see the
pressure test.

- It never touches MQTT. Today the publisher will not poll while the broker is unreachable, so a guard inside that
  process would be dead exactly when `meg` (the broker) is down or already shut.
- The publisher keeps its read-only `DUMPALL`-only socket. The guard mounts the socket read-write only if it sends the
  final UPS command itself; otherwise the host does that.
- It needs the ssh keys, a config file (thresholds, with the hosts, MACs and order generated from the workbook and
  `.hosts`, see the pressure test) and a state file under
  `/asystem/mnt`, so a restart mid-sequence knows who it already shut down.
- Every action is idempotent. A sequence starts only on a fresh reading that says on battery, and a restore starts only on
  a fresh reading that says mains. Once a sequence has started, failed or stale reads do not stop it: it carries on from
  its timers, because a USB glitch mid-outage must not leave the servers up until the battery is flat.
- It writes its state to a file the publisher reads and publishes, one way, so Home Assistant shows what the guard is
  doing. A guard nobody can see is untrusted. The publisher stays read-only and the guard stays off MQTT.
- The private key is a dedicated one, mounted read-only from a root-only directory on `max`, never in the repo or the
  image, with `known_hosts` pinned. `openssh-client` joins the image with a pinned version.

**First version, alarm based (phase 5).** The triggers are the UPS's own status flags and timers, nothing estimated.

1. **On battery (`OB`).** Poll every 2s. Nothing happens before a short `grace` has passed, so a blip does nothing.
   Time on battery accumulates and decays while on mains (a leaky bucket, say one second off for every ten on mains),
   not a timer that resets on every `OL`, so a flapping grid cannot keep the servers up through repeated dips.
2. **Stage 1, shed the followers.** When the accumulated time reaches `shed_after`, or `LB` appears, shut the followers
   down in parallel, `meg` last so Home Assistant and the broker outlast the rest. The CIFS client `jen` is an edge
   Raspberry Pi outside the rack and takes no part, so no ordering is needed unless one server turns out to mount
   another's share. Each goes over ssh with a key whose
   `authorized_keys` forces `command="/usr/sbin/poweroff",restrict`, then is confirmed down by its ssh port refusing or
   timing out (a TCP connect, so no ping binary) within a per-host deadline. `max` stays up.
3. **Stage 2, `max`.** Once every follower is confirmed down and `OB` still holds after a further `max_hold`, or on `LB`
   at any time, or when a hard time cap since `OB` began is reached, shut `max` down by ssh to the host, since the
   container cannot power it off. The UPS cut and restore goes **first**: send `shutdown.return`, with
   `ups.delay.shutdown` raised from 30s to cover `max`'s measured halt plus a margin (it goes to 540s), then ssh the
   poweroff. If the poweroff fails, send `shutdown.stop` to cancel the pending cut. Sending it afterwards cannot work,
   because powering `max` off kills the guard first. Everything restarts when mains is back.
4. **Mains returns first.** Wait `restore_hold` of continuous `OL` so a flapping grid does not power-cycle the estate,
   cancel stage 2, and wake the followers the state file lists as shut down by the guard. The leaky bucket is not reset
   to empty on wake: it starts partly full, since the battery is partly drained, so hosts that boot into a second dip are
   shed sooner. If stage 2 has already started there is nothing to cancel: `max` halts and the UPS cycle brings everything
   back. On every start the guard reconciles with its state file, waking any listed host that is still down once mains has
   held, so a guard restarted by the cycle finishes the job.

**Later, percentage based (phase 6).** Only the triggers change: `shed_after` and `max_hold` give way to thresholds on the
battery model's fraction used, 50% used for stage 1 and 10% left for stage 2. So the code keeps the decision (reading and
history in, stage out) a pure function apart from the state machine and the runners, and the first version is a
replaceable policy, not a throwaway.

**Timing budget.** The whole sequence has to fit in the battery: `shed_after`, plus the slowest follower's measured
shutdown, plus `max_hold`, plus `max`'s measured halt, plus a margin, all against the runtime at the rack's load. Docker
alone allows 1min30s to stop on each host and each runs four to six containers, with databases among them, so the
shutdown times are measured per host, not assumed.

**Choosing the first timers without data.** None of the numbers are measured yet, and whether this unit ever sets `LB`
is unknown, so until it is seen the time cap is the only safety net. A rough runtime comes from the battery label (volts
times amp-hours, about 70% usable) divided by the rack's watts, which Home Assistant already holds for `rack_outlet_plug`.
Set `shed_after` to a modest fraction of that and the hard cap to about half, keep the guard in dry-run, and revise
after the first recorded outage.

**The restart is a known unknown, and yours to test.** Two facts decide how followers come back, and neither is known.

- **Wake from off.** `max`, `may` and `meg` are Macmini7,1 (2014); their NICs report `Wake-on: g` already. `mad` is an
  Asahi M-series box that supports `g` but has it `d` (disabled). Whether the firmware honours a magic packet from a full
  poweroff is not known.
- **Power on when power is applied.** Whether each host boots by itself when AC returns after a clean poweroff. This is
  not the same as after a hard power loss while running, which many firmwares treat separately ("last state" stays off
  after a clean halt). The end of stage 2 relies on the clean-halt case.

The restart then takes one of four shapes, chosen from the tests:

- **A. Wake on LAN.** The guard sends a magic packet to each shed follower while `max` and everything on it stays up.
  Needs the wake test to pass, and the guard on the host network.
- **B. Cycle on return.** If hosts boot when power is applied, there is no need to wake anything: when mains returns and
  followers are down, the guard waits `restore_hold` and then runs stage 2 on purpose (cut and restore the UPS, halt
  `max`), and every host boots on AC restore. No wake packets, no host network, no extra key command, and one restart path
  for both cases. The cost is that `max` and what it runs (`cloudflare`, `grafana`, `letsencrypt`, `openra`) go down for
  roughly the halt, the UPS restart delay (`ups.delay.start`, 180s today) and a boot, and the battery is partly drained
  when the output cycles.
- **C. Smart plug per host.** A Tasmota plug on each host's outlet, cycled to start it. New hardware.
- **D. By hand, or stop containers instead of powering hosts off.** Stage 1 would stop the services and leave the hosts up,
  which needs no restart at all and saves little power.

If B works it is likely the simplest, and A, C and the host network can be dropped; if neither A nor B works, C or D.

**Safety rails.** It ships in dry-run (logging the exact commands it would run) and goes live only after the
pull-the-plug test has shown the real thresholds. Only the rack's Mac mini servers take part, as generated. The keys can
power off and nothing else.

**Alarm flags beyond `OB`.** Any flag that is not `OL` or a charging state is surfaced, and a replace-battery or alarm
flag (`RB`, `ALARM`) raises an alert in Home Assistant, since a failing battery makes every timer here unsafe.

**Open numbers.** `grace`, `shed_after`, `max_hold`, the hard cap, `restore_hold`, the per-host deadlines, and whether
the guard or the host sends the final UPS command.

**Testing.** Unit tests drive the state machine with an injected clock, reading source, ssh runner and wake runner.
`mockdriver` grows scripted sequences (mains lost, voltage falling, mains back), and a system test runs the whole sequence
in dry-run.

**Residual risk.** One USB link is one source of truth. A power cut together with a failure of `max` or of the guard
leaves the others running until the UPS is flat. A read-only `upsd` on the LAN and a dead-man timer on each follower would
cover it and is left out for now.

## The battery model

**What the UPS gives.** Checked on `max`: `battery.voltage`, `ups.load` (a percentage of capacity) and the status flags
(`OL`, `OB`, and `LB` if the firmware sets it). Nothing else: no runtime, no temperature, no real power, and the only
test command is `test.battery.start.quick`. `battery.charge` and the voltage limits are NUT's constants, not UPS data.
Whether the raw reply carries a temperature the driver drops is worth a look with the driver's debug output.

**Why voltage alone is weak.** On mains the battery sits at the charger's float voltage, which says nothing about charge.
On battery a lead-acid voltage is nearly flat through the middle of the discharge and only drops sharply near the end,
so it resolves "10% left" but not "50% used", which is the stage that fires first. It also sags under load and rebounds
when the load drops.

**Reusing the weather-station notebook.** `weatherstation_console_battery.ipynb` takes months of one battery's voltage
from InfluxDB, treats the sample index as capacity used (valid for a slow, constant discharge), fits a bounded polynomial
and arctan to voltage against capacity, and prints a small function for the pipeline. What carries over: the data comes
from the history Home Assistant already keeps, the arctan suits a flat-then-knee curve, and the output is a small
generated artefact. What does not: a UPS discharge is short, its load varies, and there is no months-long history, so
one voltage to percentage curve is not enough.

**Proposed model, fitted by a notebook and run by the guard.** Track *fraction of battery used*, not a voltage lookup.

- On battery, add `dt / T(load)` each poll, where `T(load)` is the runtime to the low-battery point at that load, fitted
  as a power law (a Peukert-style `T = a * load^-b`) from two or more measured discharges. A changing load is handled by
  the integration.
- On mains, let the fraction recover at a measured recharge rate, so a second outage soon after the first starts below
  full. Persist it with the guard's state so a restart does not forget.
- Use voltage and flags as hard overrides and as learning anchors, not as the percentage: `LB` or a voltage floor forces
  the last stage whatever the accumulator says, and a knee that arrives earlier than predicted shrinks the learned
  capacity. The voltage step at the moment of transfer to battery also gives an internal-resistance estimate, which
  corrects the sag and shows the battery ageing.
- "50% used" and "10% left" are then thresholds on the accumulator, in time-at-load terms that stay meaningful as the
  battery ages.

**Collect first.** Phases 3 and 4 start recording `battery.voltage` and the load into Home Assistant's history (confirm
the entities reach InfluxDB at the 10s poll). Real outages may be rare and short, so a few minutes of deliberate pull-the-plug
with everything up and the guard in dry-run gives an early curve, the sag at transfer and the recovery at the current
load without going near `LB`. The model is built once several curves exist.

**Calibration data.** Controlled discharges are the only complete source: the history will hold few real outages. At least two
runs to the low-battery point at different loads, with `rackmains/data` recorded throughout. Each costs some battery
life, and a discharge with all the servers up risks the very shutdown being designed, so they run with the guard in
dry-run and mains ready to restore. How deep and at which loads is still to decide.

**Replacing the battery.** The model is a small parameter block (reference runtime, exponent, recharge rate, knee
voltage, install date) in a file the guard loads, like `tempstat`'s `sensors.json`. A new battery means: reset to nominal
parameters, rerun the controlled discharges, regenerate the block from the notebook, and release. Each real outage
afterwards compares predicted with observed time to the low-battery point and nudges the capacity within bounds, which
also yields a "battery health" figure Home Assistant could show and alert on before the next replacement is due. Whether
the parameter file is baked into the image or mounted from `/asystem/mnt` so recalibration needs no release is open.

**Where the notebook lives.** Beside the weather-station one in `mlserver`, reading `rack_battery_voltage`,
`rack_mains_utilisation` and the status through `query_influxdb3` once the entities exist, and printing the parameter
block under the same "generated, do not edit" banner.

## Pressure test, 2026-10-28

Checked against the estate where it could be. Fixed in the text above unless marked open.

1. **A started sequence stalled on a failed read.** The first draft refused to advance on any failed or stale read, so a
   USB glitch mid-outage would have left every server up. Fixed: reads can start a sequence or a restore, never stop one.
2. **The final UPS command could not be sent.** Powering `max` off kills the guard before it sends it. Fixed: send first,
   with a delay long enough to cover the halt, and cancel with `shutdown.stop` if the poweroff fails.
3. **Wake packets probably cannot leave a bridge network.** A magic packet is a link-layer broadcast and a bridge does not
   forward one onto the LAN; ssh is unaffected. Settled for now: the guard runs on the host network, as `plex` and
   `homeassistant` do; if restart option B is chosen it needs no wake packet and goes back to bridge. Alternatives, open: stay on bridge and wake through a dispatcher on the host (the forced command
   allows only `poweroff` or `wake <mac>`, using `ether-wake`, present on `mad` and `max` only), a directed broadcast
   from the bridge (doubtful), or macvlan. A cheap test settles the directed broadcast: send a UDP datagram to the LAN
   broadcast address from a bridge container on `max` and watch for it with `tcpdump` on `may`; if it arrives, bridge is
   enough.
4. **The shed time was unbounded.** Docker allows 90s to stop per host and each runs four to six containers. Fixed in the
   plan as a budget to measure; open until it is.
5. **A flapping grid could defeat a plain timer**, and hosts woken into a second dip started with a full budget. Fixed with
   the leaky bucket and a partly full start.
6. **The guard was invisible.** Fixed: its state reaches Home Assistant through the publisher. This adds a row to phase 3,
   a guard-state sensor, once the states are named.
7. **A restarted guard could forget hosts.** Fixed: reconcile with the state file on every start.
8. **The poweroff path differs.** `command -v poweroff` gives `/usr/bin/poweroff` on `mad` and `max` (Fedora) and
   `/usr/sbin/poweroff` on `may` and `meg` (Debian), so a forced command written as `/usr/sbin/poweroff` is unproven on
   the Fedora hosts. Open: use `systemctl poweroff` by its full path, or a per-host path, and test each.
9. **`shutdown.return` is unproven on this unit.** If the UPS cuts but does not restart, the rack stays dead until someone
   presses its button. Open: test it with a lamp as the only load before it is relied on.
10. **Version 1 is what `upssched` does natively** (start a timer on on-battery, cancel it on mains, run a script). It is
    built in Rust anyway for the percentage stages, the restore logic, the state and the tests. If the percentage stages
    are never built, `upssched` plus two scripts would have been simpler, and that is the exit.
11. **The guard depends on Docker.** `SERVICE_RESTART` is `always` on a release, so it returns after a Docker restart, but
    Docker being down means no protection. Residual, listed with the USB link.
12. **`sshd` allows root login with a password on `mad`** (`PasswordAuthentication yes`, `PermitRootLogin yes` everywhere).
    Not this module's to fix, but the guard's keys are only as safe as root on the followers.
13. **Which hosts are on this UPS.** Settled by the workbook, not hand-kept: the guard's host list is generated by
    `fab generate`. The workbook already holds a device-only row per host (`device_via_device` `Server`, no `unique_id`)
    with `device_suggested_area`, `connection_mac` and `connection_ip`. The filter is `Server` rows that are `Enabled`, have
    `device_suggested_area` `Rack` and a `device_model` starting `MacMini`; that is `mad`, `max`, `may` and `meg`, and
    leaves out the Raspberry Pis (`jen` is in `Wardrobe`). `.hosts` agrees (`macmini` model, `server` role) and supplies the
    order. The join key is `macmini-<label>`: `.hosts` gives model plus label, and the sheet's `device_name` lowercased
    with a hyphen for the space gives the same, since `ssh` already uses it. The MACs for the wake packets come from the
    same rows, so nothing is typed twice. If a server ever sits in the rack off the UPS, a dedicated column would replace
    the area. Still to verify physically: the pull-the-plug test notes which hosts stayed up.

14. **A second long-running service is unprecedented.** The generated health checks, `container_name` and the
    supervisor's per-service entities assume one service per module. Open, four placements for the guard:
    - **A second service in this module.** Needs a health check and restart handling the tooling does not generate.
    - **Its own module and image** (say `rackguard`). Own version, deploy and health, at the cost of a copied crate.
    - **A thread in the one container.** One health check, but it couples the guard to the publisher's loops again.
    - **A supervisor plugin.** No new container: supervisor already runs on every host, is root-equivalent
      (`docker.sock`, `SYS_ADMIN`), has an action engine with side effects (the nightly backup), dispatches over ssh from a
      host list, drives a plug that powers the backup disk (so restart option C already has code), and publishes per-host
      entities (so the guard's state is visible with no extra work). What it would need and what it costs:
      - The guard must not use supervisor's leader election, which runs over MQTT and so depends on the broker; `max` leads
        by configuration.
      - Checked in `engine_impl_server.go` and `engine_util_broker.go`. After the first connect nothing waits on the
        broker: publishes are fire-and-forget, the database connects on its own goroutine, and the poll callback never
        blocks, so a broker outage mid-run stops no probe. But an unreachable broker **at start** makes `brokerConnect`
        fail and `RunAllProbesPublishLoop` return before any probe runs, so `serve` exits and Docker restarts it until the
        broker answers, which includes the minutes after a UPS cycle while `meg` boots. A guard would have to start before
        the broker connect, in its own goroutine under `recover`, or be its own subcommand like `backup`.
      - Nothing in supervisor acts on an MQTT command today (`onCommand` is a TODO). Its actions are the `backup`
        subcommand, which runs bash scripts and dispatches over ssh, and the reaper's plug.
      - A read-only socket mount on `max` only, so a per-host value for it (`SUPERVISOR_*_SOURCE` style), and a second
        small `DUMPALL` reader in Go.
      - Safety-critical logic ships in a binary that releases often and runs on every host, including the client
        builds, dormant everywhere but `max`. Dry-run by default and a static leader setting are the guards.
      - Wake from the bridge is still the problem it was; option B or the plug avoids it.
    The guard code is the same in each, so this can be settled when it is built. Rackmains stays a publisher in all four.

## To test (yours)

- **Wake from off.** Shut `may` down by hand and send a magic packet from `max` (`Wake-on: g` is already on for `max`,
  `may` and `meg`; `mad` shows `d` and needs enabling, and whether the setting survives a reboot is unchecked). Repeat
  per host, since the answer may differ.
- **Power on when power is applied**, per host, two cases: (a) a clean `poweroff`, then remove and restore its power,
  and see whether it boots; (b) power removed while it is running, then restored. (a) is the case stage 2 and option B
  depend on. If a host stays off, note how its firmware setting for this is changed, and whether it survives a reboot
  and a power cut. Do (a) first, and with the rack's other hosts up so only that one outlet is cycled.
- **What an unplugged UPS looks like** on the socket, and whether `LB` ever appears.
- **A controlled discharge**, for the battery model.
- **`shutdown.return` and the restart**, with a lamp as the only load, and `shutdown.stop` cancelling it.
- **Each host's shutdown time** from `poweroff` to its ssh port closing, and the forced command on each OS.
- **ssh from the guard's container** to each follower, and **a wake packet** from a host-network container, plus the
  directed-broadcast capture above.
- **The plug map**: which hosts and network gear are on this UPS.

## Remaining phases

4. **Release the publisher to `max` and start collecting.** Deploy, confirm `rackmains/status` is `online` and the entities
   appear in Home Assistant, then the pull-the-plug test: `rack_mains_status` goes OFF within one poll and back, and
   `mains_status` shows `OB`. Record the unplugged-UPS behaviour and the first partial discharge, and leave the voltage
   recording running.
5. **Build the first guard, alarm based**, in the order above: config and state, the ssh and wake runners, the state
   machine with mock sequences, a dry-run deploy, then a live pull-the-plug test. It can be built while data accumulates.
6. **Battery model and percentage stages.** Fit the model from the collected curves and controlled discharges, swap the
   guard's triggers for the thresholds, and rerun the pull-the-plug test.
7. **Housekeeping.** Move the host NUT setup into a module script so a rebuilt `max` reproduces it, and add the module
   to Home Assistant's diagnostics view if wanted.

Found on the way, outside this module: pytest 9.2.0 rejected the relative `cache_dir` argument every module's
`system_test.py` passed. It is now an absolute path in all of them. `tempstat`'s Dockerfile apt pins are also stale
(`jq` is now `deb12u3` and `ca-certificates` `20250419~deb12u2`), so its image will not build until they are refreshed.

## Open decisions

- **Poll period.** 10s in prod so an outage reaches Home Assistant quickly, at about 6 retained publishes a minute.
  Health tolerates 120s of staleness.
- **Switch or binary sensor.** `rack_mains_status` is a read-only `binary_sensor`; the `Network` and `Supervisor` modules
  use switches because they take commands. Revisit if a command is ever wired (battery test, beeper).
- **Battery model details**: discharge depth and loads for calibration, and baked-in or mounted parameter file.
- **The first guard's timers and the restart mechanism**, above.

## Designs considered and left out

- **A database writer, as `network` has.** Duplicates what Home Assistant already records, and adds a second place to
  keep schemas in step.
- **Publishing from `upsmon`'s `NOTIFYCMD`.** Event-driven and faster, but it needs `upsmon` and a hook script on the
  host and only reports changes. Polling the driver socket gives the full state and one failure model, and the 10s poll
  is fast enough for Home Assistant.
- **Reading `upsd` over the network.** `network_mode: host`, `upsd` also listening on the Docker bridge gateway
  (`172.16.0.1` here, with a `docker.service` ordering drop-in), and `upsd` on the LAN were all weighed and dropped for
  the socket: no host change, no listener to filter. The cost accepted is that the container's socket also accepts UPS
  commands, which is why the publisher only ever writes `DUMPALL`.
- **Running NUT inside the container with the USB device mapped in.** It would tie the shutdown path to Docker being up.
- **A Go client with `go.nut` or a Rust one with `rups`.** They speak `upsd`'s protocol, which this module does not use.
- **Shutdown led by supervisor.** It already has ssh and the host lists, but it would need a new plugin for a job whose
  state machine is unrelated to its own, and the UPS would then have two owners.
- **Shutdown by host `upsmon` and `upssched`.** The fewest parts, with NUT's own detection and final UPS cut, and it
  survives Docker or the broker being down. It cannot stage by percent or restore the others, so it is the fallback if
  staging proves unnecessary.
- **The guard inside the publisher's process.** It shares the broker reconnect loop, so a broker outage would stop it.
- **Followers deciding for themselves from a LAN-readable `upsd`.** Resilient to `max`'s guard failing, but it spreads
  UPS logic across hosts, exposes `upsd` to the LAN, and cannot keep `max` last.

## Renames

The module name, topics and entity ids are fixed before the first deploy because a rename strands retained topics:
clear `rackmains/#` and `homeassistant/+/rackmains/+/config` with `mosquitto_pub -r -n` and restart Home Assistant.
