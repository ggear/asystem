# The pl2303 kernel log noise

**Built and released 2026-09-27** in `10.200.1748`. The durable rules — why the probe is driven
over raw USB, the two-baud arithmetic, the five `pl2303.rs`/`usb.rs` invariants and the
hardware gate procedure — live in the module `CLAUDE.md`. What is kept here is what does not
belong there: the measurements the decision rests on, and the designs that were rejected, with
the mechanism that rejected each. The rejected design is the one that will be proposed again.

---

## What it cost, measured before the change

`may`'s kernel log carried **1728 `pl2303_get_line_request - failed: -32` lines a day** — exactly
18 per poll in every 15-minute bucket, 96 polls, no variance; 12060 of 13717 kernel lines over
seven days, **88% of `dmesg`**. Plus 21 `error sending break = -32` from the `Ds2480b` detect,
which matters below.

Only two things ever suffered. Supervisor's `host/failed_log_messages` was pegged red, and that
was **fixed independently** by a `logIgnore` entry in `probe_util_logs.go` (2026-09-14) — the
metric read `pulse 0 / trend 0 / ok` long before this work landed, and `/var/log/supervisor` was
12K with zero pl2303 lines. Disk was never a factor: ~1.3 MB/week against a 2.9 GB journal.

**So by the time this was built the only remaining cost was that `dmesg` on `may` was unreadable.**
That is a real cost for anyone debugging that host, and it is the whole justification. Keep the
`logIgnore` entry: it is cheap, and it is what holds the metric honest if the USB path is ever
reverted.

After release: **zero kernel lines of any kind**, `pl2303` unbound, no `/dev/ttyUSB0` at all. The
messages are not suppressed, they can no longer be generated.

## Ruled out

**Break-based reset** — hold the line low with `TIOCSBRK` instead of dropping to 9600, removing
the baud change entirely. It survives the mock (`Ds2480b::try_detect` already sends a break and
`FsmUart::send_break` is a no-op both `fab st` and the native tests tolerate), so the early
objection that it "cannot cross socat's pty" was wrong. It loses two other ways, both decisive.
*Presence detection is irrecoverable*: `Ds9097::reset` classifies the bus purely from the echo
byte and `OneWire::select` maps that to `NoDevice`/`Shorted`, which is what drives the recovery
ladder; a break returns no echo, and the presence pulse (15-60us after release, 60-240us long) is
long gone by the time USB frame scheduling could deliver a read slot ~1ms later. *And the clone
stalls the break too* — **measured**, not assumed: the host log carries 21
`pl2303 ttyUSB0: error sending break = -32` lines from the serial path's adapter detect. A
break-based reset would have logged at the same rate under a different message.

**A multi-byte reset at 115200** — `0x00` gives `9T = 78us` of low, so six frames would reach
480us. Each frame ends with a stop bit that releases the line for 8.68us; the bus is open-drain
with a pull-up and rises in well under a microsecond, and the DS18B20's reset detector restarts on
a rising edge, so the 480us never accumulates.

**OS-level suppression** — no mechanism exists. `dev_err` reaches the kmsg ring buffer
unconditionally and the kernel has no content filter. Debian 12 runs journald only, which cannot
drop by content. `kernel.printk` and `dmesg -n` set the *console* loglevel and leave the ring
buffer untouched. Dynamic debug controls `pr_debug`/`dev_dbg`, not `dev_err`. `modinfo pl2303`
reports no module parameters and no `usbcore.quirks` flag suppresses control-transfer errors.
Rebuilding `pl2303.ko` without the `dev_err` works and breaks on every Debian kernel update.

**The generic `usbserial` driver** — `modprobe usbserial vendor=0x067b product=0x2303` does
silence it, because that driver implements no `set_termios` at all, which is exactly why it cannot
work: baud changes become silent no-ops and the bus needs both rates.

**A hybrid** — keeping the tty for data and issuing only the baud change over usbfs is impossible.
usbfs control transfers require `USBDEVFS_CLAIMINTERFACE`, which requires the kernel driver gone.

**Dropping `SerialUart`** — it is the mock path and the revert path. Reverting is two lines in
`.env_prod` (`TEMPSTAT_DEVICE_MAP` and `TEMPSTAT_DEVICE`) plus a redeploy, with no broker or Home
Assistant migration since the MQTT topics are byte-identical either way.

## Cheaper alternatives, still valid if this is ever reverted

1. **A DS2480B adapter (DS9097U).** `Ds2480b` configures the bridge chip's own baud with a command
   byte and never calls `set_baud`, so the port stays at 9600 for the life of the process — one
   message at open, silence after. `open_bus` already auto-selects it and `MockDs2480b` covers it,
   so this is **zero code**. It is also better hardware: strong pullup means real parasite
   detection and completion polling instead of blind `t_conv` waits. Never run against real
   DS2480B silicon.
2. **A different UART chip.** The chip is what stalls. Measured: `jen` runs **two** CP210x bridges
   (`10c4:ea60`) with zero serial-driver noise — its top repeated kernel lines are all docker
   bridge churn. `cp210x_set_termios` is silent on success; only the udev rule's VID:PID changes.
   Whether it is a cable swap depends on the physical form.
3. **Fewer resets per poll.** Caching `attach` and using one SKIP ROM broadcast conversion takes 9
   resets to 4 — 18 lines per poll to 8 — and collapses three 750 ms `t_conv` waits into one.
   Reduces rather than removes, but worth doing on its own merits whatever else is true.
4. **`dmesg -T | grep -v pl2303`.** Free, and composes with everything.

## Measurements worth keeping

- The chip is a counterfeit reporting as **TYPE_HXD**: `067B:2303`, `bcdUSB 1.10`,
  `bcdDevice 4.00`, `bMaxPacketSize0 64`, empty `iSerial`. Endpoints bulk OUT `0x02`, bulk IN
  `0x83`, interrupt IN `0x81` (10 bytes, `bInterval` 1). **Nothing drains `0x81` and the chip does
  not care** — 48 s of continuous traffic, no ill effect.
- 9600 and 115200 are both in `pl2303_standard_rates`, so the direct 4-byte encoding applies and
  the divisor-encoding path is never reached.
- Gate result from a physically cold plug: **600 scratchpad transactions, 0 failures, 0 CRC
  retries**, temperatures within 0.125 °C of the tty path. Across 2467 `clear()` calls, **two**
  discarded anything — 72 bytes and 12 bytes, both the `Ds2480b` detect's unconsumed echo. With
  the detect running at its intended 9600 it leaves none, so the drain is a backstop rather than
  the thing holding the stream together.
- Post-release: poll 2887 ms against 2474 ms on the tty path; memory 1.9 MB against a cap that had
  been 16M — `nusb` cost essentially nothing.
- Service reliability on the serial path beforehand, for comparison: 864 consecutive polls over 9
  days, zero warnings, zero errors, rock-steady 2473 ms.

## What the process taught, which is the reusable part

Four bugs, and **only two were reachable by the gate**. `clear()` not flushing and the bulk-IN
packet-multiple rule were found by soaking real hardware; the missing initial line coding and the
unasserted DTR/RTS were found by a reviewer reading `SerialUart` beside `Pl2303Uart` and asking
what the tty path does that the USB path does not. The DTR/RTS one would have failed the first
cold boot in production.

The first gate was also a **false pass**: it set 9600 then 115200 before adapter selection, so the
DS2480B probe ran at the wrong rate and fell through to `Ds9097` — the right answer for the wrong
reason. Re-gating had to be done from a *physically* cold plug, because the chip retains DTR/RTS
from the kernel driver's last tty open and masks the defect otherwise. **When a test can pass
because of state the system happened to be left in, it is not a test of the thing you think.**

Finally, a pre-existing bug surfaced on the way: `system_test.py` used the paho-mqtt **1.x**
`Client(client_id, clean_session)` signature against a `paho-mqtt==2.1.0` pin, so the client id was
being passed as `callback_api_version`. tempstat's systest had been failing since that upgrade. The
root `CLAUDE.md` had reasoned the 1→2 migration through for weewx and concluded the default made
it safe — true for weewx's *keyword* call, not for a positional one. **A migration note verified
against one call site is not verified.**
