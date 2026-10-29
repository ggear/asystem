import fcntl
import glob
import json
import os
import socket
import time

SOCKET = "/run/nut/nutdrv_qx-powershield"
USB_ID = "0665:5161"
PERIOD = 2
HID_REPORTS = {
    0x20: {(0x84, 0x30): "battery_decivolts"},
    0x1E: {(0x84, 0x35): "load_percent"},
    0x32: {
        (0x85, 0xD0): "ac_present",
        (0x85, 0x44): "charging",
        (0x85, 0x45): "discharging",
        (0x85, 0x46): "fully_charged",
        (0x85, 0x47): "fully_discharged",
        (0x85, 0x4B): "need_replacement",
        (0x85, 0x42): "below_capacity_limit",
        (0x84, 0x69): "shutdown_imminent",
        (0x84, 0x62): "internal_failure",
    },
    0x34: {(0x85, 0x66): "capacity_percent"},
    0x35: {(0x85, 0x68): "runtime_seconds"},
}


def parse_fields(desc):
    fields, stack, usages = [], [], []
    page = size = count = rid = 0
    umin = umax = None
    i = 0
    while i < len(desc):
        prefix = desc[i]
        nbytes = {0: 0, 1: 1, 2: 2, 3: 4}[prefix & 3]
        kind, tag = (prefix >> 2) & 3, prefix >> 4
        raw = int.from_bytes(desc[i + 1 : i + 1 + nbytes], "little") if nbytes else 0
        i += 1 + nbytes
        if kind == 1:
            if tag == 0:
                page = raw
            elif tag == 7:
                size = raw
            elif tag == 8:
                rid = raw
            elif tag == 9:
                count = raw
            elif tag == 10:
                stack.append((page, size, count, rid))
            elif tag == 11:
                page, size, count, rid = stack.pop()
        elif kind == 2:
            if tag == 0:
                usages.append((raw >> 16 or page, raw & 0xFFFF) if nbytes == 4 else (page, raw))
            elif tag == 1:
                umin = raw
            elif tag == 2:
                umax = raw
        elif tag in (8, 9, 11):
            expanded = [(page, u) for u in range(umin, umax + 1)] if umin is not None and umax is not None else list(usages)
            for n in range(count):
                fields.append((tag, rid, expanded[min(n, len(expanded) - 1)] if expanded else (page, 0), size, bool(raw & 1)))
        if kind == 0:
            usages, umin, umax = [], None, None
    return fields


def hid_layout():
    node = next((f"/dev/{os.path.basename(p)}" for p in sorted(glob.glob("/sys/class/hidraw/hidraw*")) if USB_ID in os.path.realpath(p + "/device")), None)
    if node is None:
        raise OSError("no hidraw node for " + USB_ID)
    with open(f"/sys/class/hidraw/{os.path.basename(node)}/device/report_descriptor", "rb") as handle:
        fields = parse_fields(handle.read())
    offsets, wanted = {}, {}
    for tag, rid, usage, size, constant in fields:
        offset = offsets.get((tag, rid), 0)
        offsets[(tag, rid)] = offset + size
        if tag == 11 and not constant and rid in HID_REPORTS and usage in HID_REPORTS[rid]:
            wanted.setdefault(rid, []).append((HID_REPORTS[rid][usage], offset, size))
    lengths = {rid: 1 + (offsets[(11, rid)] + 7) // 8 for rid in wanted}
    return node, wanted, lengths


def bits(body, offset, size):
    return sum(((body[(offset + b) // 8] >> ((offset + b) % 8)) & 1) << b for b in range(size))


def read_hid(layout):
    node, wanted, lengths = layout
    row = {}
    fd = os.open(node, os.O_RDWR)
    try:
        for rid, fields in wanted.items():
            buf = bytearray(lengths[rid])
            buf[0] = rid
            fcntl.ioctl(fd, (3 << 30) | (lengths[rid] << 16) | (ord("H") << 8) | 0x07, buf, True)
            for name, offset, size in fields:
                row["hid." + name] = bits(bytes(buf[1:]), offset, size)
    finally:
        os.close(fd)
    return row


def read_nut():
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(3)
    sock.connect(SOCKET)
    sock.sendall(b"DUMPALL\n")
    buf = b""
    while b"DUMPDONE" not in buf:
        buf += sock.recv(65536)
    sock.close()
    text = buf.decode()
    row = {line.split()[1]: line.split('"')[1] for line in text.splitlines() if line.startswith("SETINFO")}
    row["fresh"] = "DATAOK" in text
    return row


layout = None
while True:
    started = time.monotonic()
    row = {"t": time.strftime("%FT%T%z")}
    try:
        row.update(read_nut())
    except Exception as err:
        row["error"] = str(err)
    try:
        layout = layout or hid_layout()
        row.update(read_hid(layout))
    except Exception as err:
        row["hid.error"] = str(err)
        layout = None
    print(json.dumps(row), flush=True)
    time.sleep(max(0.0, PERIOD - (time.monotonic() - started)))
