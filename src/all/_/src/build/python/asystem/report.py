import time
from contextlib import contextmanager

STAGE_WIDTH = 12


class Stage:
    def __init__(self):
        self.detail: str | None = None


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
    entry = Stage()
    started = time.monotonic()
    print(f"    {name:<{STAGE_WIDTH}} ...", end="", flush=True)
    try:
        yield entry
    except BaseException:
        print(f" FAILED ({time.monotonic() - started:.2f}s)", flush=True)
        raise
    print(f" done{f' [{entry.detail}]' if entry.detail else ''} ({time.monotonic() - started:.2f}s)", flush=True)


def skipped(name, reason):
    print(f"--- SKIP: {name} ({reason})", flush=True)


class PytestPlugin:
    def __init__(self, suite):
        self.suite = suite
        self.started = time.monotonic()
        self.durations = {}
        self.failed = set()
        self.skipped = set()

    def pytest_collectreport(self, report):
        if report.failed:
            print(f"--- FAIL: {report.nodeid} (collect)\n{report.longreprtext}", flush=True)
            self.failed.add(report.nodeid)

    def pytest_runtest_logstart(self, nodeid, location):
        print(f"=== RUN   {self._name(nodeid)}", flush=True)

    def pytest_runtest_logreport(self, report):
        self.durations[report.nodeid] = self.durations.get(report.nodeid, 0.0) + report.duration
        if report.failed:
            self.failed.add(report.nodeid)
            print("\n".join(f"    {line}" for line in report.longreprtext.splitlines()), flush=True)
        if report.skipped:
            self.skipped.add(report.nodeid)
        if report.when == "teardown":
            outcome = "FAIL" if report.nodeid in self.failed else "SKIP" if report.nodeid in self.skipped else "PASS"
            print(f"--- {outcome}: {self._name(report.nodeid)} ({self.durations[report.nodeid]:.2f}s)", flush=True)

    def pytest_sessionfinish(self, session, exitstatus):
        elapsed = time.monotonic() - self.started
        print("FAIL" if self.failed else "PASS", flush=True)
        print(f"{'FAIL' if self.failed else 'ok  '}\t{self.suite}\t{elapsed:.3f}s", flush=True)

    def _name(self, nodeid):
        return nodeid.split("::", 1)[-1].replace("::", "/")


def run_pytest(suite, arguments):
    import pytest

    return pytest.main(["-p", "no:terminal", *arguments], plugins=[PytestPlugin(suite)])
