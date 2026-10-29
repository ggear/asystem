# usbhid-ups and the HID interface, for reference

Recorded 2026-10-28 on `max` (NUT 2.8.5, Fedora 42) for the PowerShield Defender RackMount 800 (USB `0665:5161`). Not used in
production: `nutdrv_qx` is, and nothing here is a dependable decision signal (see the verdicts). Raw captures beside this file:
`hid_report_descriptor.hex` (the 769 byte descriptor) and `hid_fields_snapshot.txt` (every battery and power field with a value).

## The two interfaces

| Interface | HID descriptor | Endpoint | Used by |
|---|---|---|---|
| 0 | 27 bytes, vendor specific | `0x81` IN, 8 bytes | `nutdrv_qx` (Voltronic-QS) |
| 1 | 769 bytes, Power Device (`0x84`) and Battery System (`0x85`) pages | `0x82` IN, 8 bytes | nothing in NUT by default; `/dev/hidraw*` |

`lsusb -v -d 0665:5161` shows both. `nutdrv_qx` claims interface 0 and the kernel leaves interface 1 bound to `usbhid`, which is
why a native reader can use `/dev/hidraw` alongside it.

## Running usbhid-ups against it

Auto-detection fails ("No matching HID UPS found"): this build has no subdriver for the ID. Forced onto interface 0 with any
subdriver it reports identification fields and an empty `ups.status`. What worked, with `nutdrv_qx` stopped for the test:

```
[test]
    driver = usbhid-ups
    port = auto
    vendorid = 0665
    productid = 5161
    subdriver = cyberpower
    usb_hid_rep_index = 1
```

Run as `NUT_CONFPATH=<dir> NUT_STATEPATH=<dir>/state usbhid-ups -a test -u root -d 2`. Acceptable subdriver names in this build:
APC, Arduino, Belkin/Liebert, CyberPower, Delta UPS, EXPLORE, EcoFlow, Ever, Legrand, MGE, Phoenixtec/Liebert, PowerCOM, Powervar,
Salicru, TrippLite, iDowell, openUPS. Results at `usb_hid_rep_index = 1`:

| Subdriver | Variables | Battery variables | Notes |
|---|---|---|---|
| `cyberpower` | 34 to 35 | 6 | the fullest set; adding `usb_hid_ep_in = 2` or `usb_hid_desc_index = 1` gave 35 variables against 34, with the same battery set |
| `mge` | 33 | 3 | adds `output.voltage`, `output.frequency`, `outlet.1.status`; loses `battery.charge.warning` and `battery.status` |
| `explore` | 27 | 0 | no battery data |
| `apc` | not run at index 1 | | at index 0 identical to the others: identification only |

**Side effect.** After `usbhid-ups` exits, interface 1 is left with no kernel driver and its `/dev/hidraw` node disappears. It
returns with `echo 1-7:1.1 > /sys/bus/usb/drivers/usbhid/bind` (the node number changes, `hidraw4` became `hidraw3`). It does run
alongside `nutdrv_qx`, and `nutdrv_qx` stayed fresh and healthy while it ran.

## The dynamic details, as reported

Static identification fields are left out: `device.*` and `ups.mfr/model/serial` all read `HID UPS`, `ups.vendorid` `0665`,
`ups.productid` `5161`, `battery.type` `PbAc`, `battery.charge.warning` `30`, `ups.beeper.status` `enabled`, and the `driver.*`
block.

| usbhid-ups variable | Source (HID field) | Seen | What it did |
|---|---|---|---|
| `battery.charge` | `RemainingCapacity` | 90 to 95 on mains; 90 down to 40 on battery | follows the loaded or float voltage, smoothed |
| `battery.runtime` | `RunTimeToEmpty`, seconds | 1013, 1016 (matching the LCD's whole minutes) | rate-limited, see below |
| `ups.status` | `Charging`, `Discharging`, `ACPresent`, the limit and replace flags | `OL CHRG` | only `OL CHRG` seen through `usbhid-ups`; `DISCHRG`, `LB`, `RB` never observed through it |
| `battery.status` | unclear | `100%` | meaning unknown |

Dynamic fields on the HID interface itself, read by `GET_REPORT` on `/dev/hidraw` (see `hid_fields_snapshot.txt`):

| Field | Report id | Behaviour observed |
|---|---|---|
| `RemainingCapacity` (two copies) | `0x21` range 0 to 100, `0x34` range 0 to 255 | 94 to 95 at 13.3 to 13.4 V float, 90 to 91 at 13.2 V float, fell 90 to 40 in 145 s of a cut with the voltage flat at 12.0 V, rebounded 40 to 65 in 20 s once mains returned |
| `RunTimeToEmpty` | `0x35`, 16 bits | rose while charging at about 0.2 to 0.4 s per second (1476 to 1766 s over 15 minutes), fell at most one second per second (1730 to about 870 s between 18:05 and 18:20, through the cut), then rose again and settled at 1010 to 1040 s at 90 to 91% and 10 to 11% load. The LCD shows it in whole minutes, rounded down |
| `Discharging`, `Charging`, `ACPresent` | `0x32` and `0x23` bits | flipped about one second after the plug was cut, four seconds before NUT's `OB`; reversed when mains returned |
| `BelowRemainingCapacityLimit`, `ShutdownImminent`, `NeedReplacement`, `InternalFailure`, `Overload`, `Boost`, `Buck`, `AwaitingPower`, `FullyCharged`, `FullyDischarged` | `0x32`, `0x23`, `0x22` | never raised, including at a capacity gauge of 40% |
| `Voltage` and `Frequency`, in tenths | `0x20` battery; `0x18` with `0x19` and `0x1b` with `0x1c` are input and output (order inferred) | agree with NUT's `battery.voltage`, `input.voltage` and `output.voltage` |
| `PercentLoad` | `0x1e` | agrees with `ups.load` |
| `WarningCapacityLimit` | `0x38` | 30, constant |
| `AudibleAlarmControl` | `0x11` | 2 (enabled) |
| `DelayBeforeShutdown`, `DelayBeforeStartup`, `DelayBeforeReboot` | `0x15`, `0x61`, `0x17` | 65535 (unset), 0, 0 |

## Verdicts

- The capacity and runtime are model outputs of the unit's firmware, derived from the voltage and the load and smoothed, as
  NUT's `nutdrv_qx` documentation expects of UPSes that report neither (it offers guessed values from the configured voltage
  limits). They are not measured charge, and they lag a discharge: capacity can fall far while the voltage is flat, and runtime can fall no
  faster than one second per second.
- The one thing the HID side offers sooner is the transfer: its `Discharging` and `ACPresent` flipped about four seconds before
  NUT's `OB`. That is irrelevant against a grace period of a minute.
- The flags that would matter, `NeedReplacement`, `BelowRemainingCapacityLimit` and `ShutdownImminent`, were never raised in the
  cuts so far. Only a run to failure will show whether they raise, and how long before the cutoff.
- `usbhid-ups` adds only the same two model outputs and an unseen flag mapping, at the cost of a second driver and the interface
  conflict above, so it is not run.
