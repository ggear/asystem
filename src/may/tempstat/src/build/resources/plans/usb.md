# The pl2303 kernel log noise

Why `may`'s kernel log fills with `pl2303_get_line_request - failed: -32`, what it costs now that
supervisor ignores it, and why every software answer inside this driver has been ruled out.
Status is marked per section: **built** is in the repo today, **ruled out** was tried or reasoned
to a mechanism and rejected, **measured** is a number taken off a host rather than argued.

The verdict: the messages are harmless, the metric they used to break is fixed, and nothing this
driver can do will stop them. What is left is a hardware swap, and it is cheap.

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

## Two baud rates are compulsory, so the messages are compulsory

This is the finding that closes off every in-driver fix. With bit time `T = 1/baud`:

- **Reset.** The longest continuous low a UART frame can produce is the start bit plus 8 zero data
  bits, `9T`; the stop bit is always high. 1-Wire needs `tRSTL >= 480us`, so `9T >= 480us`,
  `T >= 53.3us`, **baud <= 18750**. At 9600, `0xF0` holds low for `5T = 521us`.
- **Time slot.** One byte per bit. A write-1 or read slot must pull low for 1-15us and release,
  and that low is the start bit, `1T`. So `T <= 15us`, **baud >= 66667**. At 115200, `T = 8.68us`.

The two ranges are disjoint. **No single baud rate can drive a passive 1-Wire bus from a UART**,
so any `Ds9097` implementation must switch baud, and on Linux each switch is a `tcsetattr` →
`pl2303_set_termios` → `pl2303_get_line_request` → one `-EPIPE` line. Not an implementation
choice.

## What it costs now

**Not the supervisor metric — that is fixed and deployed.** `logIgnore` in
`src/all/supervisor/src/main/go/supervisor/internal/probe/probe_util_logs.go` carries the
pattern ``^pl2303 ttyUSB\d+: .*``, shipped in `supervisor:10.200.1735` and confirmed in
the running binary. Measured: `supervisor/macmini-may/data/host/failed_log_messages` reads
`pulse 0 / trend 0 / ok true`, and `/var/log/supervisor` is 12K holding one backup log with zero
pl2303 lines. (The earlier claim that supervisor shouts a WARN per error was also wrong —
`logShoutsMax` caps it at 5 per scan.)

Not disk either. ~1.3 MB/week against a 2.9 GB journal, and `/var` on `may` is 52% used.

**The entire remaining cost is that `dmesg` on `may` is unreadable** — 88% of kernel lines are this
one message, which buries anything else while debugging that host. That is a real cost and it is
the only one.

## Ruled out

**Bypassing the kernel driver with raw USB (`nusb`) — ruled out.** The original subject of this
plan. It is the one option that eliminates the messages totally, and it loses on risk. There is no
local test loop: neither `cargo test` on the dev Mac nor `fab st` can reach a USB device, so
development is edit-blind-deploy-read-logs against the only adapter in the house, which is also
the live one. `pl2303.c` is fifteen years of variant handling and this chip is by definition an odd
one. Buffering and timing bugs would present as occasional wrong bytes — an odd temperature or a
CRC retry, weeks to notice. Hotplug re-claim becomes ours. And it ties tempstat to PL2303
permanently, so buying the genuine adapter that is the cheapest real fix would then *break* it.
Against a service measured at **864 consecutive polls over 9 days with zero warnings, zero errors
and zero CRC retries at a rock-steady 2473 ms**, that is not a trade worth making.

Four things learned while costing it, kept because they are what the next attempt would have to
rediscover:

- The spike as originally scoped would have failed for the wrong reason. It omitted
  `pl2303_startup()`'s vendor magic (`vendor_read(0x8484)`, `write(0x0404,0)` … `write(0x0002,0x0044)`
  for HX-family) and `pl2303_open()`'s pipe reset. Without those the chip may not transmit at all,
  and the gate would have read as "chip quirks defeat it".
- `vendor_write(8,0)` / `vendor_write(9,0)` reset the upstream and downstream data pipes, which is
  the hardware equivalent of the `tcflush` behind `Uart::clear()`. A raw implementation has a real
  `clear()`, not a best-effort drain.
- 9600 and 115200 are both in `pl2303_standard_rates`, so the direct 4-byte encoding applies and
  the divisor-encoding path is never reached.
- The interrupt endpoint `0x81` is polled continuously by the kernel for modem status. A raw
  implementation would have to decide whether the chip tolerates nobody draining it.

Its host plumbing had three gaps worth recording. `docker-compose.yml` is
`devices: - ${TEMPSTAT_DEVICE_MAP}`, and an unset variable renders `devices: - ""`, which compose
rejects — prod would have to keep a placeholder, and `/dev/bus/usb` plus `device_cgroup_rules`
would then apply in mock mode too. `install_prep.sh` is `chmod 666 /dev/ttyUSBTempProbe`, which
fails once the driver is unbound and there is no tty. And `/dev/bus/usb` on `may` exposes an Apple
Bluetooth HID keyboard and mouse, the Bluetooth host controller, an IR receiver and the Ugreen
storage bridge — `c 189:* rmw` grants a thermometer reader raw usbfs access to all of them, with no
way to narrow it because the device number moves.

**Break-based reset — ruled out, but not for the reason first written.** Holding the line low with
`TIOCSBRK` instead of dropping to 9600 removes the baud change entirely, and the earlier objection
that a break "cannot cross socat's pty at all, taking `fab st` with it" is **wrong**: `Uart` already
declares `send_break`, `Ds2480b::try_detect` already calls it on every detect, and the mock's
`FsmUart::send_break` is a no-op that both `fab st` and the native tests already tolerate.

It loses on presence detection instead, and irrecoverably. `Ds9097::reset` classifies the bus
purely from the echo byte — `0x00` Shorted, `0xF0` Absent, anything else Present — and
`OneWire::select` maps those to `Error::NoDevice` / `Error::Shorted`, which is what drives the
whole recovery ladder. A break returns no echo. Sampling the presence pulse afterwards cannot
recover it: the pulse begins 15-60us after release and lasts 60-240us, while USB frame scheduling
puts the earliest possible read slot ~1ms later. So an unplugged probe or a shorted bus would
surface as garbled data rather than a clean fault. Separately, a break-based reset makes the break
load-bearing rather than a resync nudge, so `MockDs9097` would need an out-of-band reset signal
that no real wire carries. And `pl2303_break_ctl` is itself a vendor request this clone may stall,
which would log at the same rate under a different message.

**A multi-byte reset at 115200 — ruled out on mechanism.** `0x00` gives `9T = 78us` of low, so six
frames would reach 480us, but each frame ends with a stop bit that releases the line for 8.68us.
The bus is open-drain with a pull-up and rises in well under a microsecond, and the DS18B20's reset
detector restarts on a rising edge, so the 480us is never accumulated.

**OS-level suppression — ruled out, no mechanism exists.** `dev_err` reaches the kmsg ring buffer
unconditionally and the kernel has no content filter. Debian 12 on `may` runs journald only, and
journald cannot drop messages by content. `kernel.printk` and `dmesg -n` set the *console*
loglevel and leave the ring buffer untouched, so `dmesg` still shows them. Dynamic debug controls
`pr_debug`/`dev_dbg`, not `dev_err`. `modinfo pl2303` reports no module parameters, and no
`usbcore.quirks` flag suppresses control-transfer error logging. Binding the device to the generic
`usbserial` driver does silence it, because that driver implements no `set_termios` at all — which
is exactly why it cannot work, as baud changes become silent no-ops and the bus needs both rates.
Rebuilding `pl2303.ko` without the `dev_err` works and breaks on every Debian kernel update.

## What is left

Ranked. Only the first two remove the messages.

1. **A DS2480B adapter (DS9097U), and this driver already supports it.** `Ds2480b` configures the
   bridge chip's own baud with a command byte and **never calls `set_baud`**, so the port stays at
   9600 for the life of the process — one message at open and silence after. `open_bus` already
   auto-selects it, `driver::mock`'s `MockDs2480b` already covers it end to end, and it is better
   hardware besides: strong pullup means real parasite detection and completion polling instead of
   blind `t_conv` waits. **Zero new code.** The one risk is that the path has never run against a
   real DS2480B, only the emulator.
2. **A different UART chip in front of the existing passive adapter.** The chip is what stalls.
   Measured: `jen` runs **two** CP210x bridges (`10c4:ea60`) and has zero serial-driver noise in
   its kernel log — its top repeated lines are all docker bridge churn. CP2102 is already proven
   twice on this estate for the VantagePro2 and the Zigbee dongle, `cp210x_set_termios` is silent
   on success, and the only change is the VID:PID in the udev rule. Whether this is a ~$5 cable
   swap depends on the physical form — a DB9 DS9097 dongle behind a USB-serial cable can take a new
   cable, an integrated USB unit cannot.
3. **Fewer resets per poll, worth doing on its own merits.** Caching `attach` across polls and
   using one SKIP ROM broadcast conversion takes 9 resets to 4, so **18 lines per poll to 8** — a
   55% cut — and collapses three 750 ms `t_conv` waits into one, which should take the measured
   2473 ms poll to roughly 1000 ms. All in-repo, covered by `cargo test` and `fab st`, no host
   state. It reduces rather than removes, which is why it sat below the metric fix before the
   metric was fixed; now that the only cost is legibility, halving it is worth having.
4. **Filter at the reading end.** `dmesg -T | grep -v pl2303` makes the log readable today at zero
   risk and composes with all of the above.
5. **Raise `TEMPSTAT_POLL_PERIOD`.** Divides the count linearly, costs resolution, env-only.

## Not doing

- **Removing `SerialUart`.** It is the mock path and the production path; it stays.
- **Removing the `logIgnore` entry.** It is what keeps the metric honest, and none of the options
  above are certain to land.
- **Narrowing the USB exposure.** There was no mechanism; the device number moves.
