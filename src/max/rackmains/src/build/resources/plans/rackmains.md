# rackmains

**Built and tested locally 2026-10-28, not released.** Phases 1 and 2 are done: the crate reads the driver socket,
publishes to the broker, and ships with a mock driver and a mock-backed system test. What remains is the
spreadsheet rows (phase 3, yours), the release and the pull-the-plug test (phase 4), and housekeeping (phase 5). The
code and the module `CLAUDE.md` say how it works; this file holds the status, what the code cannot say, and the
decisions still open.

---

## Goal

Publish the rack UPS's mains and battery state to Home Assistant over MQTT, so an outage or a failing battery is visible
and automatable there. Nothing else depends on it.

**Out of scope, deliberately**

- **No InfluxDB writer.** Home Assistant records the entities itself and that history is the database. The module declares
  no `database` schema.
- **No supervisor integration.** Supervisor reads the same driver socket itself and shuts servers down, with `max` as
  leader (last section). That path must work with every intermediate service stopped, so the shutdown decision never
  routes through this module, the broker or `upsd`.

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

`battery.charge` is estimated from voltage against `battery.voltage.low` (10.4) and `battery.voltage.high` (13.0), the
NUT defaults, so it reads 100 whenever the battery sits above 13.0 V. Set both in `ups.conf` once the real float and
cut-off voltages are known, or treat the entity as coarse.

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

## Remaining phases

4. **Release to `max`.** Deploy, confirm `rackmains/status` is `online` and the entities appear in Home Assistant, then
   the pull-the-plug test: `rack_mains_status` goes OFF within one poll and back, and `mains_status` shows `OB`. Also
   check what an unplugged UPS looks like on the socket, since only the stale marker in a unit test covers it.
5. **Housekeeping.** Move the host NUT setup into a module script so a rebuilt `max` reproduces it, and add the module
   to Home Assistant's diagnostics view if wanted.

## Open decisions

- **Poll period.** 10s in prod so an outage reaches Home Assistant quickly, at about 6 retained publishes a minute.
  Health tolerates 120s of staleness.
- **Switch or binary sensor.** `rack_mains_status` is a read-only `binary_sensor`; the `Network` and `Supervisor` modules
  use switches because they take commands. Revisit if a command is ever wired (battery test, beeper).
- **Battery estimate thresholds**, above.

## Designs considered and left out

- **A database writer, as `network` has.** Duplicates what Home Assistant already records, and adds a second place to
  keep schemas in step.
- **Publishing from `upsmon`'s `NOTIFYCMD`.** Event-driven and faster, but it needs `upsmon` and a hook script on the
  host and only reports changes. Polling the driver socket gives the full state and one failure model, and the 10s poll
  is fast enough for Home Assistant.
- **Reading `upsd` over the network.** `network_mode: host`, `upsd` also listening on the Docker bridge gateway
  (`172.16.0.1` here, with a `docker.service` ordering drop-in), and `upsd` on the LAN were all weighed and dropped for
  the socket: no host change, no listener to filter, and `upsd` out of the shutdown path. The cost accepted is that the
  container's socket also accepts UPS commands, which is why only `DUMPALL` is ever written.
- **Running NUT inside the container with the USB device mapped in.** It would tie the shutdown path to Docker being up,
  which is exactly what the supervisor plugin must avoid.
- **A Go client with `go.nut` or a Rust one with `rups`.** They speak `upsd`'s protocol, which this module does not use.

## Shutdown and supervisor (max leads)

Decided 2026-10-28, to be built in `supervisor`, not here.

- **One leader.** The supervisor on `max` reads the UPS from the same driver socket and alone decides, then shuts the
  other servers down over ssh and itself last. Followers hold no UPS logic, and `upsd` is not exposed beyond 127.0.0.1.
- **Ordering by observation.** Shut a client before the server whose share it mounts (`jen` before `mad`, the CIFS
  mount in `jen`'s `fstab`), confirm each host has stopped answering, and only then stop `max`, with a deadline.
- **The ssh key can only power off.** A dedicated key per follower with a forced command, for example
  `command="/usr/sbin/poweroff",restrict` in `authorized_keys`. Not checked against how supervisor's ssh is set up today.
- **Unreachable is not on battery.** Act on the `OB` flag from the socket, never on a failed read or stale data. Cancel
  the sequence if `OL` returns before the commit point.
- **Last step.** Tell the UPS to cut and restore its load (`shutdown.return`, after `ups.delay.shutdown`, 30s today),
  so mains returning restarts the hosts instead of leaving them halted on a UPS that never dropped. Whether supervisor
  sends it down the socket or the host's NUT does it at shutdown is open.
- **Open numbers.** Seconds on battery or charge before starting, the per-host order, the ping deadline, and which
  hosts take part (the edge and client hosts probably do not).
- **Residual risk.** One USB link is one source of truth. A power cut together with a failure of `max` or its
  supervisor leaves the others running until the UPS is flat. A read-only `upsd` on the LAN and a dead-man timer on
  each follower would cover it and is left out for now.

## Renames

The module name, topics and entity ids are fixed before the first deploy because a rename strands retained topics:
clear `rackmains/#` and `homeassistant/+/rackmains/+/config` with `mosquitto_pub -r -n` and restart Home Assistant.
