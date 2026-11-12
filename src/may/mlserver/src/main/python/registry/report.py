import time
from contextlib import contextmanager

STAGE_WIDTH = 12


class Stage:
    def __init__(self, name=""):
        self.name = name
        self.detail: str | None = None
        self.broken = False

    def note(self, text):
        if not self.broken:
            print(flush=True)
            self.broken = True
        print(f"        {text}", flush=True)

    def resume(self):
        return f"    {self.name:<{STAGE_WIDTH}} ..." if self.broken else ""


@contextmanager
def subject(name):
    started = time.monotonic()
    print(f"=== RUN   {name}", flush=True)
    try:
        yield
    except BaseException:
        print(f"--- FAIL: {name} ({time.monotonic() - started:.2f}s)", flush=True)
        raise
    print(f"--- PASS: {name} ({time.monotonic() - started:.2f}s)", flush=True)


@contextmanager
def stage(name):
    entry = Stage(name)
    started = time.monotonic()
    print(f"    {name:<{STAGE_WIDTH}} ...", end="", flush=True)
    try:
        yield entry
    except BaseException:
        print(f"{entry.resume()} FAILED ({time.monotonic() - started:.2f}s)", flush=True)
        raise
    print(f"{entry.resume()} done{f' [{entry.detail}]' if entry.detail else ''} ({time.monotonic() - started:.2f}s)", flush=True)
