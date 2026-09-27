# Driving the probe over raw USB

Why `may`'s kernel log fills with `pl2303_get_line_request - failed: -32`, why no change inside
this driver can stop it, and what it takes to bypass the kernel serial driver instead.
Status is marked per section: **built** is in the repo today, **planned** is not, **ruled out**
was reasoned to a mechanism and rejected, **measured** is a number taken off a host rather than
argued.

The verdict: replacing `SerialUart` with a userspace PL2303 implementation over usbfs is the
**preferred** answer and the only software one that works. Everything else either reduces the rate
or needs different hardware.

**Phase 0 is built and Phase 1 passed on `may` on 2026-09-27**, finally from a physically cold
plug — 600 scratchpad transactions, zero failures, zero CRC retries, temperatures matching the tty
path, and **not one new `pl2303_get_line_request` line**. It took four bugs to get there, all in
`UsbUart`: two found by the soak and two more by review afterwards, of which one would have failed
Phase 2 outright. Nothing is deployed, the host is back as it was, and production still runs
`SerialUart` through the kernel driver. **Phase 2 is the next step.**

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

One further de-risking fact, measured: 9600 and 115200 are in `pl2303_standard_rates`, so the
direct 4-byte encoding applies and the divisor-encoding path is never reached.

It was also assumed that `vendor_write(8,0)` / `vendor_write(9,0)` — the upstream and downstream
pipe reset `pl2303_open` issues — would serve as the hardware equivalent of the `tcflush` behind
`Uart::clear()`. **Phase 1 disproved that on the real device; see the gate result below.**

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

### How the code must read

`driver/usb.rs` sits beside `ds9097.rs` and `uart.rs` and must be indistinguishable from them. The
crate's existing conventions are the specification; none of this is new policy.

- **No inline comments.** The only prose is the `//!` module header carrying source links, the same
  exception every `driver/` file already takes. For `usb.rs` that is the PL2303 references — the
  kernel driver and the CDC line-coding shape — and nothing else.
- **No new error crate.** `driver::Error` is a hand-rolled enum with `Display`, `source()` and
  `From` impls, and there is no `thiserror` or `anyhow` anywhere in the crate. `UsbUart`'s failures
  become new `Error` variants plus a `From` impl for the nusb error type. Their `Display` text
  follows the repo convention — every interpolated value wrapped in `[...]`, no `:` or dash
  separators. The pre-existing `io error: {err}` forms predate that rule; leave them alone, they
  are not this change's business.
- **Dependencies stay lean.** `serialport`, `rumqttc` and `chrono` are all `default-features =
  false`; `nusb` takes neither `tokio` nor `blocking` unless the blocking bridge genuinely needs
  one, and if it does, say so rather than pulling an executor in quietly.
- **No `unsafe`.** Needing none is the whole reason `nusb` was chosen over `rusb`. A patch that
  wants `unsafe` is a signal that the wrong crate or the wrong abstraction is in play.
- **Layout mirrors the sibling file** — `//!` header, `use`, consts, struct, `impl` blocks, then a
  colocated `#[cfg(test)] mod tests` at the bottom, which every driver file has. Exported items
  come before unexported helpers.
- **A function called from exactly one place is a jump, not an abstraction.** The repo-wide rule
  applies here specifically: resist splitting the eleven-transfer `pl2303_startup` sequence into
  eleven named helpers. It is one sequence with one call site and it reads better spelled out.
- **Naming splits between code and text.** Types stay Rust-cased — `UsbUart`, matching `Ds2480b`
  and `Ds9097` — while log and error *text* spells the chipset upper-case, `PL2303`, as the
  existing log convention requires.
- **Logging matches `SerialUart`.** `log_line(label, value)` for the aligned INFO lines, INFO
  reserved for the one-line-per-event summary a human watching the service wants, and every
  byte-level transfer detail at DEBUG exactly as the existing `uart tx` / `uart rx` lines are.
- **Thin binaries.** If the `--probe` pre-gate needs an entrypoint it belongs in the library behind
  a thin shim, as `main.rs` and `mockdev.rs` are. Prefer a flag on the existing `Cli` over a third
  binary, since `mockdev` already ships in the image; if it must not ship, make it a workspace
  member the way `tools/schema` is.
- **`cargo fmt` and `cargo clippy --workspace --all-targets -- -D warnings` are gates, not
  suggestions.** `fab build` runs both, `rustfmt.toml` pins `max_width = 120`, and warnings are
  errors. Keeping files comment-free is what makes a build's formatting pass only ever reflow code.

### Phases

**The gate must exercise 115200 slot traffic, not just the reset.** The obvious spike — unbind,
init, set both bauds, send `0xF0`, read the echo — proves the plumbing and none of the risk. It
never sends a time slot, never reads a temperature, never calls `clear()` and runs once, so it
would pass while telling you nothing about the two things most likely to be wrong: the 160-byte
full-duplex echo at 115200, and intermittent byte-level desync. `touch_slots` does
`write_all(chunk)` then `read_exact(chunk)` for up to `UART_FIFO_SIZE` 160 bytes, and today the
kernel tty layer buffers the inbound echo while the write is in flight. With raw bulk that becomes
a bulk OUT followed by a bulk IN against a 64-byte endpoint and an unknown RX FIFO on a clone.
That is the question the gate exists to answer.

**So write `UsbUart` first and spike with the real driver stack.** Reversing the usual order is
right here because a throwaway that tests the reset only is not cheaper in any useful sense — it
fails cheap *and* proves nothing. The real stack brings its own correctness oracle: DS18B20
scratchpad reads are CRC-8 checked in `read_scratchpad`, so a CRC-valid scratchpad is strong
evidence the byte framing is right, and `read_temperature` already counts retries.

**Phase 0 — `UsbUart`, plus a cheap pre-gate. Built.** `driver/usb.rs` implements `Uart` against
`nusb` 0.2.7 — the eleven-step `pl2303_startup` table, `SET_LINE_REQUEST` line coding, bulk
`0x02`/`0x83` transfers via `transfer_blocking`, `clear()` as the `vendor_write(8,0)`/`(9,0)` pipe
reset, and break as the class request. `lib.rs` parses `usb:VVVV:PPPP` and selects `UsbUart` or
`SerialUart`; `open_device` hands back a `Ds2480b<Box<dyn Uart>>`, which is what a new
`impl Uart for Box<dyn Uart>` passthrough in `uart.rs` buys, so `select_adapter` and everything
above the trait is untouched.

`nusb` needed no blocking bridge in the end — `MaybeFuture::wait()` and
`Endpoint::transfer_blocking` are native, so neither `tokio` nor `blocking` is enabled. On Linux it
pulls only `futures-core`, `linux-raw-sys`, `log`, `once_cell`, `rustix` and `slab` (verified with
`cargo tree --target x86_64-unknown-linux-gnu`); the `tokio` in the lock file is rumqttc's and
predates this. Nothing entered `docker_deps_*`.

`--probe` is the 20-minute kill check: claim the interface, run the full startup sequence, set the
line coding to 9600 then 115200, touch the bus not at all. It reuses `ds9097::BAUD_RESET` and
`BAUD_SLOTS`, now `pub(crate)`, so the probe cannot drift from the driver. If the clone stalls a
vendor request the project is dead there and the cost was an afternoon. This is the part the
previous version of this plan omitted from its spike, and without it a failure reads as "chip
quirks defeat it" when it was a missing setup step.

Four tests cover what can be covered without hardware — `usb_target` accepting a path, parsing
upper and lower case ids, and rejecting five malformed forms, plus a `Box<dyn Uart>` driving the
real `Ds9097`/`Ds18b20` stack against `MockDs9097` end to end. 125 tests pass, `cargo clippy
--workspace --all-targets -- -D warnings` is clean and `fab build` is green. The three CLI error
paths were exercised by hand on the dev machine: a serial path is refused, `usb:zzz` reports
`invalid device [usb:zzz]`, and absent hardware reports `no usb device [067B:2303]`.

**Phase 1 — the gate, on `may`.** Build `linux/amd64`, stop the tempstat container (it holds the
tty, and unbinding under it gives it I/O errors it would take three failed polls to recover from),
capture `dmesg | wc -l`, and run against the real probe. Pass criteria, all of them:

| Check | Pass |
|---|---|
| Reset at 9600 | echo is not `0xF0` — a presence pulse pulled it low |
| One `match_rom` + `read_scratchpad` at 115200 | CRC-8 valid — this is the real gate |
| All three sensors read | within ±0.5 °C of the tty baseline below |
| Soak, a few hundred reads back to back | **zero** CRC retries and zero errors, against a production baseline of zero in 9 days |
| `clear()` between chunks | no desync across the soak |
| Per-sensor duration | recorded against the 825 ms tty baseline; poll total against 2473 ms |
| `dmesg` delta | exactly zero new lines |
| Interrupt endpoint `0x81` | nothing drains it across the soak and the chip keeps working |

The baseline oracle, measured 2026-09-27 16:56 AWST over the tty path — ROMs and readings:
`28FF641E870006AE` utility 16.3125 °C, `28FF641E87CB3CF9` rack_top 22.8125 °C,
`28FF641E870576A9` rack_bottom 16.75 °C. Compare against the live `tempstat/data` at the time of
the run rather than these numbers, which move with the weather; what matters is agreement with the
tty path, not the absolute value.

A single successful read is not a pass. The failure mode this gate exists to catch is "wrong by
one byte occasionally", which the plan costs at weeks to notice and days to find, so the soak and
its zero-retry threshold are the point of the phase.

Rebind `pl2303` afterwards, restart tempstat and confirm it recovers.

**Phase 1 result, measured on `may` 2026-09-27. Passed, on the third run.**

*The kill check passed outright, first time.* All eleven `pl2303_startup` transfers completed
`status=0` — the vendor reads returning `actual_length=1` on ep 80, the vendor writes
`actual_length=0` on ep 0 — and both line codings applied with `actual_length=7`. **Not one
control request stalled.** The counterfeit accepts every request the kernel makes except the GET,
exactly as argued.

*Two bugs, both caught by the soak and neither reachable any other way.*

The first was `clear()`. Reset echo reads came back desynchronised: a 1-byte echo read submitted
as a 64-byte bulk IN returned `actual_length=6` on one reset and `actual_length=62` on the next,
with a stale first byte, so `reset()` classified the bus `Shorted` then `Absent`. Both vendor
writes had completed `status=0` immediately before, so **`vendor_write(8,0)` /
`vendor_write(9,0)` do not purge the PL2303 receive FIFO** — the assumption this plan carried as a
de-risking fact was simply wrong. `clear()` now issues the two vendor writes and then drains the
IN endpoint until a short-timeout read returns nothing, which is what `tcflush(TCIOFLUSH)` does
for the tty path.

The instrumented run names the culprit precisely: across the whole soak **2465 clears discarded 0
bytes and exactly two discarded anything — one 72 bytes and one 12 bytes.** Those 84 bytes are
unconsumed echo left by the `Ds2480b` detect probe, which writes command bytes a passive adapter
echoes and never reads them all back. One un-flushed byte shifts every subsequent transaction by
one for the life of the process, which is why the symptom looked like random bus faults rather
than a startup bug.

The second was transfer sizing. **`nusb` rejects a bulk IN whose length is not a multiple of
`wMaxPacketSize`** — a 72-byte scratchpad read failed with `invalid or unsupported argument` under
a `Submitting transfer with length 72 which is not a multiple of max packet size 64` warning. The
original `.max(PACKET_SIZE)` hid this for short reads and exposed it for long ones; `read_exact`
now rounds the request up with `div_ceil(PACKET_SIZE) * PACKET_SIZE` and buffers the surplus.

*The passing run.* The adapter resolved to `DS9097`, the same path production takes — but see the
caveat below: that was a forced fallback, not a detection. Opening
reads 16.75 / 22.875 / 16.75 °C and closing reads 16.75 / 23 / 16.8125 °C, against a tty baseline
of 16.6875 / 22.9375 / 16.875 °C taken minutes earlier — every sensor inside 0.125 °C, well within
the ±0.5 °C criterion, and the drift is the real room. **300 soak iterations, 0 failures, and not
one `scratchpad crc failed` warning.** Each iteration is *two* CRC-checked scratchpad
transactions, not one — `Ds18b20::attach` reads the scratchpad itself to learn the resolution
before the explicit read — so the soak was **600 transactions at ~80 ms each**, not the 300 at
~160 ms the counter reports. The counter undercounts by half; the coverage is twice what was
claimed and the per-transaction cost is half. `dmesg` gained no `pl2303_get_line_request` line: the last
one on the host predates the run, and the only new kernel lines are the unbind and rebind notices.
Nothing drained interrupt endpoint `0x81` for 48 s of continuous traffic and the chip did not care.

*The cost, measured.* A full sensor read took ~970 ms against the tty path's ~825 ms, and the soak
ran 48 147 ms for 300 scratchpad reads, ~160 ms each. The overhead is the drain: nearly every
`clear()` finds nothing and pays the full `DRAIN_TIMEOUT` (10 ms), and a poll makes roughly thirty
of them. A poll would therefore land near 2.9 s against today's 2473 ms. The lever is obvious if
that matters — shorten the timeout, or skip the drain when the preceding transaction consumed
every byte it wrote — but neither is needed to pass.

*Two findings that simplify the plan.* `nusb`'s `detach_and_claim_interface` detaches the kernel
driver itself and **re-attaches it when the process exits** (observed: `Reattached kernel drivers
for interface 0`, with `ttyUSB0` and the udev symlink back immediately). So the manual unbind is
unnecessary, and **`blacklist pl2303` is optional** rather than required — a bound-but-unopened
`pl2303` logs nothing, since the message only comes from `set_termios`. That removes the manual
host edit this plan flagged as having no home in `fab`, and means a crashing container hands the
tty back rather than orphaning the device.

*Recovery was clean, twice.* Rebind, `chmod 666`, `docker start tempstat` — the service came back
on the serial path first try both times, at 2474 ms against 2473 ms, reading values matching the
baseline. Roughly fifteen minutes of downtime across the whole exercise.

*Two defects the first gate could not catch, found by review afterwards and since fixed and
re-gated from a cold plug.*

**`UsbUart::open` set no initial line coding, so DS2480B auto-detection could not work.**
`SerialUart::open` opens at 9600 and `Ds2480b` never calls `set_baud` — the detect sequence
depends on the UART already sitting there. `UsbUart::open` ran the startup table and returned,
leaving whatever coding the chip last held, so in the first gate the DS2480B probe ran at 115200,
could not succeed, and fell through to `Ds9097` — the right answer on `may`, reached for the wrong
reason. `UsbUart::open` now issues `set_baud`, and the value is a `pub(crate) const BAUD_OPEN` in
`uart.rs` read by both implementations so they cannot drift.

**DTR and RTS were never asserted.** `SerialUart::open` raises both; `UsbUart` issued only the
vendor request, `SET_LINE` and `BREAK`, never `SET_CONTROL` (`0x22`, class/interface,
`CONTROL_DTR|CONTROL_RTS`). The first gate passed only because the kernel driver had asserted the
lines at its last tty open and the chip retained them — a passive DS9097 adapter commonly draws
bus power from those lines, so a cold plug under a blacklisted `pl2303` would have found an
unpowered adapter with no diagnostic.

**Re-gated cold, 2026-09-27 20:40, and this is the run that matters.** The probe was physically
unplugged and replugged with tempstat stopped, so nothing opened the tty and the kernel never
asserted the control lines — verified before the run with `fuser -v /dev/ttyUSB0` returning no
holder. The adapter came back as **device 038 on hub port `1-2.2`, a different physical port from
the `1-2.1` it had occupied**. Result: **600 scratchpad transactions, 0 failures, no CRC-retry
warning, exit 0**, temperatures 16.75 / 22.5625 / 16.8125 °C opening and 16.75 / 22.5 / 16.8125 °C
closing against a tty baseline of 16.6875 / 23 / 16.8125 °C taken 25 minutes earlier. `dmesg` held
at 1457 pl2303 lines across the whole run, the last `get_line_request` timestamped before the
replug. So the USB path works from cold, which is the state Phase 2 creates.

The new diagnostics confirm the rest: `PL2303 packet size [64] flow control [0x0044]` — the packet
size now read from the endpoint rather than assumed, and the flow-control byte chosen at runtime
from `bMaxPacketSize0` rather than hardcoded to HX — followed by `PL2303 asserted DTR and RTS`.
**Across 2467 clears, every one discarded 0 bytes**, against the two poisoned clears (72 and 12
bytes) of the first gate: with the detect probe now running at its intended 9600 it no longer
leaves unconsumed echo, so the drain has become a backstop rather than the thing holding the
stream together. No drain hit the packet cap.

**The port change was an accident and a useful one.** It is the case a path-based identity would
have failed: `1-2.1` is now wrong, and anything keyed on the usbfs node or the bus path would have
needed re-provisioning. Selection by `067B:2303` survived untouched, and so did the udev symlink,
which matches on vendor, product and product string rather than on path. It also means the plan's
recorded binding of `1-2.1:1.0` is now `1-2.2:1.0` — the address is not stable and nothing should
be keyed to it.

*Also fixed from the same review, not individually re-gated beyond the passing run above.*
Enumeration now errors with `found [n] usb devices [...], expected one` instead of silently taking
an arbitrary match; the drain distinguishes `TransferError::Cancelled` from real errors, which now
propagate rather than being swallowed into an `Ok`, and warns when it hits `DRAIN_PACKETS` instead
of returning success over a still-desynchronised stream; a malformed `usb:` device string is
validated once at the top of `run()` so a config typo fails immediately rather than being retried
forever as a transient hardware fault; and the soak counter now reports both transactions per
iteration, since `Ds18b20::attach` reads the scratchpad itself — the first gate's "300 reads at
~160 ms" was really 600 at ~80 ms.

*Still untested, and this is the gap that stands between here and a release.* **No run has ever
exercised `UsbUart` together with the poll loop and the MQTT publish.** Every hardware run used
`--probe`, which reads sensors but never publishes; every publish test (`fab st`, `fab exe`) used
the mock serial path. The deployed shape of Phase 2 — the compose mount, the cgroup rule, the
`--device` flag and `TEMPSTAT_DEVICE=usb:067B:2303` — has likewise never been executed, only
written. Hotplug recovery under `UsbUart` is also untested, and the 16M memory cap is unmeasured
with nusb in the process. Close those before releasing, not after.

**The transport seam, built.** Three of the first four bugs lived in protocol logic that only real
hardware could reach, so `driver/transport.rs` now sits under `UsbUart`: a `UsbTransport` trait of
six methods (`control_in`, `control_out`, `bulk_out`, `bulk_in`, `packet_size`,
`max_packet_size_0`) over a `UsbSetup` that mirrors the USB setup packet, with `NusbTransport`
for production and `mock::MockTransport` for tests. It is the same shape the crate already uses
twice — `Uart`/`MockUart` and `Publisher`/`MockPublisher` — so `usb.rs` became pure PL2303
protocol and `transport.rs` owns every nusb call. `UsbUart` is generic over the trait;
`UsbUart::open` builds the nusb transport and `UsbUart::new` takes any transport, which is the
entry point tests drive.

One simplification fell out: `bulk_in` maps `TransferError::Cancelled` to `Ok(vec![])`, so a
timeout and an empty read are the same thing to the caller and real errors propagate. `clear()`
lost its error-swallowing match arm as a result and simply checks `is_empty()`.

**Thirteen tests, and each historical bug was replanted to prove they bite.** Every one fails
exactly one named test and the suite restores to 138 passing:

| Replanted bug | Test that caught it |
|---|---|
| no initial line coding | `open_sets_the_line_coding_then_asserts_dtr_and_rts` |
| DTR/RTS never asserted | `open_sets_the_line_coding_then_asserts_dtr_and_rts` |
| bulk IN not a packet multiple | `read_exact_rounds_the_request_up_to_a_packet_multiple` |
| `clear()` swallows transport errors | `clear_propagates_a_transport_error_rather_than_reporting_success` |
| hardcoded HX flow byte | `startup_picks_the_flow_control_byte_from_the_control_endpoint_size` |

So the three bugs that previously needed a production outage and a physical replug to find are now
caught in 1.5 s on the dev machine. The rest of the suite covers the startup table's order and
request types, little-endian baud encoding, surplus buffering across reads, the read timeout, the
pipe-reset pair, the drain's packet cap, and the break toggle. **Re-gated on `may` after the
refactor: 600 transactions, 0 failures, `dmesg` unchanged.**

**Phase 2 — host plumbing.** `blacklist pl2303`; `install_prep.sh` loses the `chmod`;
`docker-compose.yml` gains the mount and the cgroup rule; `.env_prod` keeps a placeholder
`TEMPSTAT_DEVICE_MAP` and names the USB id. `.env_test`/`.env_exec` keep the socat mock. Verify the
container enumerates the device without `privileged`, confirm the cgroup v2 eBPF path actually
grants it, and re-measure the 16M cap.

**Phase 3 — deploy and observe.** Over a full 24 h window: `dmesg` gains no pl2303 lines,
`tempstat/data` carries three samples on cadence with no new CRC retries, and a deliberate replug
recovers without a container restart. That last is the hotplug risk and is the only way to test
it. If any fail, revert — the serial path is still in the binary, though reverting also needs the
blacklist removed and udev re-triggered on the host.

**The test loop is on `may`, and that is workable.** The image already builds `linux/amd64`, so a
test binary runs on the host against the real device. Slower than `cargo test`, not blind.

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
