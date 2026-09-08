# Bypassing the kernel serial driver

Why `may`'s kernel log fills with `pl2303_get_line_request - failed: -32`, what it actually costs,
and what it would take for tempstat to drive the probe over raw USB instead of a serial device.
Status is marked per section: **built** is in the repo today, **planned** is not, **measured** is a
number taken off `may` rather than reasoned about.

Read *Root cause* and *Cheaper answers* first. The implementation below is the **third-choice**
option and this plan says so throughout — it exists so the decision is made against a real design
rather than a guess at one.

---

## Root cause, measured

The message is not a fault in the probe, the driver, or the wiring. It is the Linux `pl2303`
driver asking the adapter a question the adapter refuses to answer:

```
3,92299,5121083047322,-;pl2303 ttyUSB0: pl2303_get_line_request - failed: -32
```

`-32` is `-EPIPE` — the USB control endpoint **stalled**. `pl2303_set_termios()` calls
`pl2303_get_line_request()` purely to read back the port's current line coding before applying a
new one; on failure it logs `dev_err` and carries on, then issues `SET_LINE_REQUEST`, which the
chip does honour. So the *set* direction works, which is why readings are correct and nothing is
broken. The device is `067b:2303` and is almost certainly a counterfeit — genuine HXD/TA/TB parts
answer the request.

**The rate is entirely ours, and it is arithmetic, not luck.** The kernel emits one line per
*hardware* termios change. `Ds9097::reset` (`src/main/rust/tempstat/src/driver/ds9097.rs:78-90`)
changes baud twice per bus reset — `BAUD_RESET` 9600 for the `0xF0` reset pulse, `BAUD_SLOTS`
115200 for the time slots — and `read_sensor` (`src/main/rust/tempstat/src/lib.rs:273-286`) costs
three resets per sensor per poll:

| Step | Resets |
|---|---|
| `Ds18b20::attach` → `read_scratchpad`, to learn the resolution | 1 |
| `convert_t` → `select` | 1 |
| `read_temperature` → `read_scratchpad` | 1 |

3 sensors x 3 resets x 2 baud changes x 96 polls/day at `TEMPSTAT_POLL_PERIOD=15m` = **1728/day**,
against a measured **1728** pl2303 lines in 24 h out of 1807 kernel lines total (96%).

**Caching the baud in `SerialUart` would save exactly zero lines.** `pl2303_set_termios()` opens
with `if (old_termios && !tty_termios_hw_change(...)) return;`, so a redundant set is already free,
and `reset()` always alternates — every call is a genuine change.

## What it actually costs, measured

Not disk. `/var` on `may` is 50% used and the lines are ~260 KB/day.

The cost is **supervisor's `host/failed_log_messages`**, which counts kernel errors in a 24 h trend
window against `FailedLogsBudget = 10` (`internal/metric/metric_build.go:29`). `may` reports
**1710 errors across 1 distinct message** — 17100% of budget, so the metric is pegged red
permanently, and supervisor shouts a WARN per error, which is what bloats the watch logs under
`/var/log/supervisor`.

## Cheaper answers, ranked above this plan

1. **`logIgnore` in supervisor** (`internal/probe/probe_lib_logs.go:389`, currently an empty
   `[]*regexp.Regexp`). The mechanism exists for exactly this and supervisor prints the line to
   paste beside every counted error:

   ```go
   regexp.MustCompile(`^pl2303 ttyUSB0: pl2303_get_line_request - failed: -\d+`),
   ```

   One line, no risk, fixes the actual pain. Cost: genuine pl2303 faults on `may` go unreported.
2. **A genuine PL2303, or a CH340/FT232.** The chip is what stalls; a real one answers and the
   message never appears. ~$5, no code.
3. **A DS2480B adapter.** The bridge chip does the 1-Wire timing itself, so `Ds2480b` never calls
   `set_baud` after open — one message per process start at most. tempstat already implements and
   auto-detects this path (`lib.rs:191-205`), so it is zero code.
4. **Fewer resets per poll.** Cache `attach` across polls and use one SKIP ROM broadcast
   conversion: 18 lines/poll to ~8, and faster polls. Worth doing on its own merits; does not move
   the metric, which needs a ~170x reduction.
5. **Raise `TEMPSTAT_POLL_PERIOD`.** Divides the count linearly, costs resolution, env-only.

Nothing at the OS level helps: Debian 12 on `may` runs journald only, and **journald cannot drop
messages by content** — there is no filter rule to write. `dmesg -n 3` quietens the console while
the lines still land in the journal. `pl2303` has no module parameter, and dynamic debug controls
`pr_debug`, not `dev_err`.

## Why the two in-code alternatives lose

**Break-based reset** — hold the line low with `TIOCSBRK` (an ioctl, not a termios change) instead
of dropping to 9600 — is ~20 lines and fails three ways. It may silence nothing: `pl2303_break_ctl`
is *also* a vendor request the clone may stall, and that failure is `dev_err` too, so the same rate
of a different message. It blinds the bus: `OneWire::select` maps `Presence::Absent`/`Shorted` to
`Error::NoDevice`/`Error::Shorted` (`driver/onewire.rs:53-55`) on every sensor operation, and a
break returns no echo to classify, so an unplugged probe would surface as garbled data rather than
a clean fault. And it breaks the mock irreparably — `driver/mock.rs` is built on `feed(byte)` with
`RESET_PULSE = 0xF0` *as* the reset, and a break is an electrical condition that cannot cross
socat's pty at all, taking `fab st`, `fab exe` and the `driver::mock` end-to-end tests with it.

**Doing nothing in code** is the recommendation. What follows is the design if that is overruled.

---

## Design, planned

### The seam already exists

`driver::uart::Uart` (`driver/uart.rs:15-21`) is five methods — `write_all`, `read_exact`,
`send_break`, `clear`, `set_baud` — and `SerialUart` is its only production implementation. A
second implementation talking USB directly is a drop-in: `Ds9097`, `Ds2480b`, `Ds18b20`, the poll
loop and every unit test above the trait are untouched. This is the whole reason the option is
tractable.

`UsbUart::set_baud` issues the PL2303 `SET_LINE_REQUEST` control transfer itself and **never issues
the GET**. No kernel driver is in the path, so there is nothing to log. Elimination is total, not
partial — that is the one thing this option has over every other.

### Use `nusb`, not `rusb`/libusb

`nusb` is pure Rust and talks to usbfs directly, so nothing new enters `docker_deps_base.txt` or
`docker_deps_build.txt`, there is no C library to pin, and the builder stage is unchanged. `rusb`
would drag in `libusb-1.0` and its headers for no benefit.

### Device identity

The path-based identity goes away. `/dev/ttyUSBTempProbe` is a udev symlink to `ttyUSB0`; the usbfs
node is `/dev/bus/usb/001/037` (char 189:36) and **the device number climbs on every replug** — 037
already, so no fixed node can be mapped. Selection is by USB id `067b:2303`, which is unique on
`may` (measured, one match in `lsusb`). `-D`/`--device` grows a `usb:VVVV:PPPP` form alongside the
existing path form, so mock mode keeps a path and production takes an id.

### Releasing the kernel driver

`pl2303` is bound at `1-2.1:1.0` and `/sys/bus/usb/drivers/pl2303/unbind` exists (measured). Two
placements, and the first is preferred:

- **Host, at deploy time.** One line in `install_prep.sh` beside the `chmod 666` already there,
  plus a udev rule so it survives a replug or reboot. Keeps the privileged act on the host.
- **Container, at startup.** `USBDEVFS_DISCONNECT` works as root with write access to the node, but
  it mutates *host* kernel state from inside a container.

### Compose

`docker-compose.yml:16-17` hands the container exactly one device via `${TEMPSTAT_DEVICE_MAP}`.
USB needs the tree instead:

```yaml
volumes:
  - /dev/bus/usb:/dev/bus/usb
device_cgroup_rules:
  - 'c 189:* rmw'
```

The container already runs as `root` and is **not** privileged (measured), and would not need to
be. `TEMPSTAT_DEVICE_MAP` stays for mock mode (`/dev/null:/dev/null` in `.env_test`/`.env_exec`)
and is dropped from `.env_prod`.

**This is the cost that is not obvious: `/dev/bus/usb` exposes every USB device on `may`, not the
probe.** The cgroup rule grants the whole 189 major. Today the container can touch one device and
nothing else. There is no way to narrow it, because the device number moves.

### The mock keeps the serial path

Nothing can present itself as a USB device inside a container — socat can fake a serial port, not a
bus. `SerialUart` stays, mock mode selects it, production selects `UsbUart`. The `Uart` trait keeps
both honest and every unit test in `driver::mock` still runs.

**Accept plainly what this costs:** `fab st` would then exercise a path production does not use.
The system test stops being end-to-end proof of the shipped configuration.

---

## What could refuse

In rough order of likelihood. The first is the one that decides the plan.

1. **No local test loop.** Neither `cargo test` on the dev Mac nor `fab st` can reach a USB device.
   Development becomes edit-blind, deploy to `may`, read logs — against the one adapter in the
   house, which is also the live one. Every risk below is worse for it.
2. **Chip quirks.** `pl2303.c` is fifteen years of variant handling — a dozen chip types, two baud
   encodings, per-variant init sequences. This adapter is by definition an odd one; it refuses a
   standard request. A from-scratch implementation may hit an undocumented quirk findable only on
   the host.
3. **Buffering and timing bugs present as flaky readings, not failures.** The DS9097 reads bits by
   echo, and today the kernel keeps the bulk endpoint drained and buffered; `UART_FIFO_SIZE = 160`
   exists to match the chip. All of that becomes ours: draining the IN endpoint, flushing stale
   bytes before a reset (`clear()` is currently `tcflush`), timeouts. Wrong by one byte
   occasionally is an odd temperature or a CRC retry — weeks to notice, days to find.
4. **Hotplug and recovery.** USB resets, suspend/resume and replugs are the kernel driver's job
   today; re-claiming and re-detaching become ours. `may` has ~60 days uptime, so this path would
   be rarely exercised and therefore rarely correct.
5. **Portability, which is a certainty rather than a risk.** This ties tempstat to PL2303
   permanently. Buying the $5 genuine adapter — the cheapest real fix — would then *break*
   tempstat instead of fixing it.

---

## Phases

### Phase 0 — the spike, and the gate

**Nothing else starts until this passes.** On `may`, outside the container, outside the repo: a
throwaway Rust binary that unbinds `pl2303`, opens `067b:2303` with `nusb`, sets the line coding to
9600 and then 115200, sends `0xF0`, and reads the echo back. Assert the echo is not `0xF0` (a
presence pulse pulled it low) and that `dmesg` gains no new lines.

This settles risks 2 and 3 and most of the plumbing in about an hour. If the chip's quirks defeat
it, the answer is `logIgnore` and a new adapter, and the cost was an hour.

Rebind `pl2303` afterwards and confirm tempstat recovers.

### Phase 1 — `UsbUart`, on the dev machine

`driver/usb.rs` implementing `Uart` against `nusb`, with the PL2303 line-coding and bulk transfers.
`-D usb:VVVV:PPPP` parsing in `lib.rs`, selecting `UsbUart` or `SerialUart`. Unit tests via the
existing `MockUart` — the trait is the seam, so coverage above it is unchanged. `cargo clippy
--workspace --all-targets` clean, files comment-free per the module convention.

Nothing is deployed in this phase and nothing is proven by it beyond compilation and the shape.

### Phase 2 — host plumbing

`install_prep.sh` gains the unbind; a udev rule makes it survive replug and reboot.
`docker-compose.yml` gains the `/dev/bus/usb` mount and the cgroup rule. `.env_prod` drops
`TEMPSTAT_DEVICE_MAP` and names the USB id; `.env_test`/`.env_exec` are untouched, so `fab st` and
`fab exe` keep the socat mock and the serial path.

Verify on `may` that the container can enumerate the device without `privileged`.

### Phase 3 — deploy and observe

Release, then confirm over a full 24 h window: `dmesg` gains no `pl2303` lines,
`host/failed_log_messages` returns green, `tempstat/data` carries three samples on cadence with no
new CRC retries, and a deliberate replug of the probe recovers without a container restart. That
last one is risk 4 and is the only way to test it.

If any of those fail, revert. The serial path is still in the binary, so revert is an env change.

## Not doing

- **Break-based reset.** See above — may silence nothing, blinds fault detection, breaks the mock.
- **Removing `SerialUart`.** It is the mock path and the revert path; it stays.
- **A `logIgnore` entry as well.** If this works there is nothing left to ignore, and an entry would
  then be masking a message that ought to be impossible.
- **Narrowing the USB exposure.** There is no mechanism; the device number moves. Either accept the
  widening or do not do this.
