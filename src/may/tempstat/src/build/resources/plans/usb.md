# Driving the probe over raw USB

Why `may`'s kernel log fills with `pl2303_get_line_request - failed: -32`, why no change inside
this driver can stop it, and what it takes to bypass the kernel serial driver instead.
Status is marked per section: **built** is in the repo today, **planned** is not, **ruled out**
was reasoned to a mechanism and rejected, **measured** is a number taken off a host rather than
argued.

The verdict: replacing `SerialUart` with a userspace PL2303 implementation over usbfs is the
**preferred** answer and the only software one that works. Everything else either reduces the rate
or needs different hardware.

---

## Root cause, measured

The message is not a fault in the probe, the driver, or the wiring. It is the Linux `pl2303`
driver asking the adapter a question the adapter refuses to answer:

```
pl2303 ttyUSB0: pl2303_get_line_request - failed: -32
```

`-32` is `-EPIPE` — the USB control endpoint **stalled**. `pl2303_set_termios()` calls
`pl2303_get_line_request()` purely to read back the port's current line coding before applying a
new one; on failure it logs `dev_err` and carries on, then issues `SET_LINE_REQUEST`, which the
chip does honour. The *set* direction works, which is why readings are correct and nothing is
broken.

The chip is a counterfeit. Measured off `/sys/bus/usb/devices/1-2.1`: `067b:2303`, `bcdUSB 1.10`,
`bcdDevice 4.00`, `bMaxPacketSize0 64`, empty `iSerial`. That combination makes
`pl2303_detect_type()` classify it **TYPE_HXD**, and a genuine HXD answers the request. Endpoints
are bulk OUT `0x02`, bulk IN `0x83` and interrupt IN `0x81` (10 bytes, `bInterval` 1).

**The rate is ours, and it is arithmetic.** The kernel emits one line per *hardware* termios
change. `Ds9097::reset` changes baud twice per bus reset — `BAUD_RESET` 9600 for the `0xF0` reset
pulse, `BAUD_SLOTS` 115200 for the time slots — and `read_sensor` costs three resets per sensor
per poll:

| Step | Resets |
|---|---|
| `Ds18b20::attach` → `read_scratchpad`, to learn the resolution | 1 |
| `convert_t` → `select` | 1 |
| `read_temperature` → `read_scratchpad` | 1 |

3 sensors x 3 resets x 2 baud changes = **18 per poll**, x 96 polls/day at
`TEMPSTAT_POLL_PERIOD=15m` = **1728/day**. Measured on `may`: `dmesg` shows literally 18 lines in
every 15-minute bucket with no variance, and the journal holds 12060 pl2303 lines in 7 days
(1723/day) out of 13717 kernel lines total.

**Caching the baud in `SerialUart` would save exactly zero lines.** `pl2303_set_termios()` opens
with `if (old_termios && !tty_termios_hw_change(...)) return;`, so a redundant set is already free,
and `reset()` always alternates — every call is a genuine change.

## Two baud rates are compulsory, so a kernel tty cannot be quiet

This is what closes off every in-driver fix and leaves only the bypass. With bit time `T = 1/baud`:

- **Reset.** The longest continuous low a UART frame can produce is the start bit plus 8 zero data
  bits, `9T`; the stop bit is always high. 1-Wire needs `tRSTL >= 480us`, so `9T >= 480us`,
  `T >= 53.3us`, **baud <= 18750**. At 9600, `0xF0` holds low for `5T = 521us`.
- **Time slot.** One byte per bit. A write-1 or read slot must pull low for 1-15us and release,
  and that low is the start bit, `1T`. So `T <= 15us`, **baud >= 66667**. At 115200, `T = 8.68us`.

The two ranges are disjoint. **No single baud rate can drive a passive 1-Wire bus from a UART**,
so any `Ds9097` implementation must switch baud, and through a kernel tty each switch is a
`tcsetattr` → `pl2303_set_termios` → `pl2303_get_line_request` → one `-EPIPE` line. Not an
implementation choice. The only way out is for no kernel driver to be in the path.

## What it costs, measured

**Not the supervisor metric.** `logIgnore` in
`src/all/supervisor/src/main/go/supervisor/internal/probe/probe_util_logs.go` carries the pattern
``^pl2303 ttyUSB\d+: .*``, shipped in `supervisor:10.200.1735` and confirmed in the running binary.
`supervisor/macmini-may/data/host/failed_log_messages` reads `pulse 0 / trend 0 / ok true`, and
`/var/log/supervisor` is 12K holding one backup log with zero pl2303 lines.

Not disk. ~1.3 MB/week against a 2.9 GB journal, and `/var` on `may` is 52% used.

**The entire cost is that `dmesg` on `may` is unreadable** — 88% of kernel lines are this one
message, which buries anything else while debugging that host.

---

## Preferred: a userspace PL2303 over usbfs, planned

`UsbUart` issues `SET_LINE_REQUEST` itself and **never issues the GET**. No kernel driver is in
the path, so there is nothing to log. Elimination is total, not partial — that is the one thing
this has over every other option.

### The chip risk is low, and this is the argument for doing it

The plan this replaces ranked "chip quirks" as its second-biggest risk, on the grounds that
`pl2303.c` is fifteen years of variant handling and this adapter is by definition an odd one. That
reasoning is backwards. **Every request the kernel makes to this device works except the GET.**
The port opens, the vendor init completes, baud changes take effect, bulk data flows, and the
service has run **864 consecutive polls over 9 days with zero warnings, zero errors and zero CRC
retries at a rock-steady 2473 ms**. This is not writing a driver for an unknown chip — it is
reimplementing a request sequence demonstrably working on this exact device, and omitting the one
request that is not.

Two further de-risking facts, both measured: 9600 and 115200 are in `pl2303_standard_rates`, so
the direct 4-byte encoding applies and the divisor-encoding path is never reached; and
`vendor_write(8,0)` / `vendor_write(9,0)` reset the upstream and downstream data pipes, which is a
real hardware equivalent of the `tcflush` behind `Uart::clear()` rather than a best-effort drain.

### The seam already exists

`driver::uart::Uart` is five methods and `SerialUart` is its only production implementation. A
second implementation talking usbfs is a drop-in: `Ds9097`, `Ds2480b`, `Ds18b20`, the poll loop and
every unit test above the trait are untouched. The wire protocol, taken from `pl2303.c`:

| Method | Transfers |
|---|---|
| open | claim interface 0 after unbind, then `pl2303_startup`: `vendor_read(0x8484)`, `vendor_write(0x0404,0)`, `read(0x8484)`, `read(0x8383)`, `read(0x8484)`, `vendor_write(0x0404,1)`, `read(0x8484)`, `read(0x8383)`, `vendor_write(0,1)`, `vendor_write(1,0)`, `vendor_write(2,0x44)` — `0x44` for HXD, `0x24` is the legacy variant |
| `set_baud` | control OUT type `0x21` request `0x20`, 7-byte payload: baud LE32, stop bits, parity, data bits |
| `write_all` | bulk OUT `0x02`, 64-byte packets |
| `read_exact` | bulk IN `0x83`, accumulated to length against a timeout |
| `clear` | `vendor_write(8,0)`, `vendor_write(9,0)`, then drain bulk IN |
| `send_break` | control OUT type `0x21` request `0x23`, value `0xffff` then `0x0000` |

Vendor requests are type `0x40` write / `0xc0` read, request `0x01`. Roughly 250-350 lines.

**There is no hybrid.** Keeping the tty for data and issuing only the baud change over usbfs is
impossible: usbfs control transfers require `USBDEVFS_CLAIMINTERFACE`, which requires the kernel
driver gone. It is all or nothing.

### Use `nusb`, not `rusb`/libusb

`nusb` 0.2.7 is pure Rust and talks to usbfs directly, so nothing new enters
`docker_deps_base.txt` or `docker_deps_build.txt`, there is no C library to pin, and the builder
stage is unchanged. MSRV is 1.85 against the 1.98 pin. `tokio` and `blocking` are optional
features, so no executor is forced, but the transfer API is submit-and-wait shaped and needs a
blocking bridge to satisfy a synchronous `fn read_exact`. `rusb` would drag in `libusb-1.0` and its
headers for no benefit.

### Device identity

The path-based identity goes away. `/dev/ttyUSBTempProbe` is a udev symlink to `ttyUSB0`; the
usbfs node is `/dev/bus/usb/001/037` and **the device number climbs on every replug**, so no fixed
node can be mapped. Selection is by USB id `067b:2303`, measured as the only match in `lsusb` on
`may`. `-D`/`--device` grows a `usb:VVVV:PPPP` form alongside the existing path form, so mock mode
keeps a path and production takes an id.

Note this is a thinner identity than the udev rule it replaces, which also matches
`ATTRS{product}=="USB-Serial Controller"` — and the CP2102 lines beside it show why, since
`10c4:ea60` matches both the VantagePro2 and the Zigbee dongle. This device's `iSerial` is empty,
so a second PL2303 anywhere on `may` would make selection arbitrary. Accept it or add a product
string match.

### Releasing the kernel driver

`pl2303` is bound at `1-2.1:1.0` and binds **exactly one device** on `may` (measured:
`ls /sys/bus/usb/drivers/pl2303/`), so removing it entirely is safe.

**Prefer `blacklist pl2303` in `/etc/modprobe.d/` over a udev unbind.** It is race-free and
survives replug and reboot by construction, where a udev `RUN+=` unbind races the driver's own
probe so the device is briefly claimed on every replug. It is also already the idiom on this host,
which carries `blacklist-btusb.conf`, `blacklist-bluetooth.conf`, `blacklist-wifi.conf` and
others.

**No `fab` task writes host udev or modprobe files.** The rule that creates
`/dev/ttyUSBTempProbe` lives in `src/zzz/_debian_macmini/install.sh`, a hand-run provisioning
script in the graveyard (`.group` is `-1`, host form-factor `ignore`) that provisions all four
macminis and also configures digitemp against the symlink. So this half is a manual host edit
outside the release, and must be recorded as one rather than written as a phase deliverable.

**`install_prep.sh` must change.** It is `chmod 666 /dev/ttyUSBTempProbe`, which fails on every
release once there is no tty. The usbfs node is `crw-rw-r-- root root` and the container runs as
root, so it can write today — but that is an inherited accident, and a udev `MODE="0666"` on the
usbfs node is the explicit form.

### Compose

`docker-compose.yml` hands the container one device via `${TEMPSTAT_DEVICE_MAP}`. USB needs the
tree instead:

```yaml
volumes:
  - /dev/bus/usb:/dev/bus/usb
device_cgroup_rules:
  - 'c 189:* rmw'
```

**`TEMPSTAT_DEVICE_MAP` cannot simply be dropped from `.env_prod`.** The key is
`devices: - ${TEMPSTAT_DEVICE_MAP}`, and an unset variable renders `devices: - ""`, which compose
rejects; prod must keep a placeholder such as `/dev/null:/dev/null`. Conversely the mount and the
cgroup rule then apply in mock mode too, so `fab st` and `fab exe` on the dev Mac get both against
a path neither has been tested with.

`may` is `cgroup2fs` with Docker 28.3.3, so `device_cgroup_rules` goes through eBPF rather than
the v1 devices controller. This should work and is **not** yet measured — the one plumbing claim
here that is not.

The container already runs as root and is **not** privileged (measured), and would not need to be.
It is capped at `memory: 16M`; nusb adds `rustix`, `linux-raw-sys`, `futures-core`, `slab` and
`once_cell` plus an event thread and URB buffers, so the cap needs re-measuring rather than
assuming.

### Costs to accept plainly

- **`fab st` stops testing the shipped path.** Nothing can present as a USB device in a container —
  socat fakes a serial port, not a bus. `SerialUart` stays, mock mode selects it, production
  selects `UsbUart`. The `Uart` trait keeps both honest and every `driver::mock` test still runs,
  but the system test is no longer end-to-end proof of the shipped configuration.
- **`/dev/bus/usb` exposes every USB device on `may`**, not the probe: an Apple Bluetooth HID
  keyboard and mouse, the Bluetooth host controller, an IR receiver and the Ugreen storage bridge.
  The cgroup rule grants the whole 189 major. There is no way to narrow it, because the device
  number moves. Either accept the widening or do not do this.
- **Hotplug and recovery become ours.** USB resets, suspend/resume and replugs are the kernel
  driver's job today. `may` has 80 days uptime, so this path would be rarely exercised and
  therefore rarely correct.
- **Portability.** This ties tempstat to PL2303. Buying a different adapter would then break it
  rather than fix it.

### Phases

**Phase 0 — the spike, and the gate.** Nothing else starts until this passes. On `may`, outside
the container: a throwaway binary that unbinds `pl2303`, opens `067b:2303` with `nusb`, **runs the
full `pl2303_startup` sequence above**, sets the line coding to 9600 then 115200, sends `0xF0` and
reads the echo. Assert the echo is not `0xF0` (a presence pulse pulled it low) and that `dmesg`
gains no new lines. The init sequence is the part the previous version of this plan omitted, and
without it the chip may not transmit at all — a failure would then read as "chip quirks defeat it"
when it was a missing setup step. Rebind `pl2303` afterwards and confirm tempstat recovers.

**Phase 1 — `UsbUart` on the dev machine.** `driver/usb.rs` implementing `Uart` against `nusb`,
`usb:VVVV:PPPP` parsing in `lib.rs` selecting `UsbUart` or `SerialUart`. Unit tests via the
existing `MockUart` — the trait is the seam, so coverage above it is unchanged.
`cargo clippy --workspace --all-targets` clean, files comment-free per the module convention.
Nothing is proven by this phase beyond compilation and shape.

**Phase 2 — host plumbing.** `blacklist pl2303`; `install_prep.sh` loses the `chmod`;
`docker-compose.yml` gains the mount and the cgroup rule; `.env_prod` keeps a placeholder
`TEMPSTAT_DEVICE_MAP` and names the USB id. `.env_test`/`.env_exec` keep the socat mock. Verify the
container enumerates the device without `privileged`, and re-measure the 16M cap.

**Phase 3 — deploy and observe.** Over a full 24 h window: `dmesg` gains no pl2303 lines,
`tempstat/data` carries three samples on cadence with no new CRC retries, and a deliberate replug
recovers without a container restart. That last is the hotplug risk and is the only way to test
it. If any fail, revert — the serial path is still in the binary, though reverting also needs the
blacklist removed and udev re-triggered on the host.

**There is a test loop, and it is on `may`.** The image already builds `linux/amd64`, so a test
binary runs on the host against the real device. Slower than `cargo test`, not blind.

---

## Alternatives, kept because they are cheaper

1. **A DS2480B adapter (DS9097U).** `Ds2480b` configures the bridge chip's own baud with a command
   byte and **never calls `set_baud`**, so the port stays at 9600 for the life of the process — one
   message at open and silence after. `open_bus` already auto-selects it and `MockDs2480b` already
   covers it end to end, so this is **zero new code**, and the strong pullup means real parasite
   detection and completion polling instead of blind `t_conv` waits. The one risk is that the path
   has never run against real DS2480B silicon.
2. **A different UART chip in front of the passive adapter.** The chip is what stalls. Measured:
   `jen` runs **two** CP210x bridges (`10c4:ea60`) with zero serial-driver noise in its kernel log.
   CP2102 is proven twice on this estate and `cp210x_set_termios` is silent on success; only the
   udev rule's VID:PID changes. Whether this is a cable swap depends on the physical form — a DB9
   dongle behind a USB-serial cable can take a new cable, an integrated unit cannot.
3. **Fewer resets per poll.** Caching `attach` across polls and using one SKIP ROM broadcast
   conversion takes 9 resets to 4, so **18 lines per poll to 8**, and collapses three 750 ms
   `t_conv` waits into one — the measured 2473 ms poll should fall to roughly 1000 ms. All in-repo,
   covered by `cargo test` and `fab st`. It reduces rather than removes, and is worth doing on its
   own merits whatever else lands.
4. **Filter at the reading end.** `dmesg -T | grep -v pl2303` costs nothing and composes with
   everything above.
5. **Raise `TEMPSTAT_POLL_PERIOD`.** Divides the count linearly, costs resolution, env-only.

## Ruled out

**Break-based reset.** Holding the line low with `TIOCSBRK` instead of dropping to 9600 removes
the baud change entirely, and it does survive the mock — `Uart` already declares `send_break`,
`Ds2480b::try_detect` already calls it on every detect, and `FsmUart::send_break` is a no-op both
`fab st` and the native tests tolerate. It loses on presence detection, irrecoverably.
`Ds9097::reset` classifies the bus purely from the echo byte (`0x00` Shorted, `0xF0` Absent,
anything else Present) and `OneWire::select` maps those to `Error::NoDevice`/`Error::Shorted`,
which is what drives the whole recovery ladder. A break returns no echo, and sampling the presence
pulse afterwards cannot recover it: the pulse begins 15-60us after release and lasts 60-240us,
while USB frame scheduling puts the earliest possible read slot ~1ms later. An unplugged probe
would surface as garbled data rather than a clean fault. Making the break load-bearing would also
need `MockDs9097` to carry an out-of-band reset signal that no real wire carries, and
`pl2303_break_ctl` is itself a vendor request this clone may stall.

**A multi-byte reset at 115200.** `0x00` gives `9T = 78us` of low, so six frames would reach 480us,
but each frame ends with a stop bit that releases the line for 8.68us. The bus is open-drain with a
pull-up and rises in well under a microsecond, and the DS18B20's reset detector restarts on a
rising edge, so the 480us is never accumulated.

**OS-level suppression.** No mechanism exists. `dev_err` reaches the kmsg ring buffer
unconditionally and the kernel has no content filter. Debian 12 on `may` runs journald only, which
cannot drop messages by content. `kernel.printk` and `dmesg -n` set the *console* loglevel and
leave the ring buffer untouched, so `dmesg` still shows them. Dynamic debug controls
`pr_debug`/`dev_dbg`, not `dev_err`. `modinfo pl2303` reports no module parameters, and no
`usbcore.quirks` flag suppresses control-transfer error logging. Rebuilding `pl2303.ko` without
the `dev_err` works and breaks on every Debian kernel update.

**The generic `usbserial` driver.** Binding with `modprobe usbserial vendor=0x067b product=0x2303`
does silence it, because that driver implements no `set_termios` at all — which is exactly why it
cannot work, since baud changes become silent no-ops and the bus needs both rates.

## Not doing

- **Removing `SerialUart`.** It is the mock path and the revert path; it stays.
- **A `logIgnore` entry as well.** If this lands there is nothing left to ignore, and the entry
  would then mask a message that ought to be impossible. It stays until Phase 3 passes.
- **Narrowing the USB exposure.** There is no mechanism; the device number moves.
