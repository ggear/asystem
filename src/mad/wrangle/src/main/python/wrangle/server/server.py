import dataclasses
import json
import mimetypes
import os
import threading
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from wrangle.plugin.config import TIMEOUT_RUN_SECONDS
from wrangle.plugin.counters import COUNTERS, aggregate_summary

WEB_ROOT_DIR: str = os.path.dirname(os.path.realpath(__file__))

THEMES = ["creme", "butter", "gold", "orange", "pumpkin", "rich", "ember", "cinnabar"]

CHART_SPEC = [
    [
        {"source": "Data", "action": "Errored", "label": "Data/File Errored", "source2": "Files", "action2": "Errored", "color": "#ff5555", "col": "left"},
        {"source": "Data", "action": "Delta Rows", "color": "#ffcc99", "col": "middle"},
        {"source": "Data", "action": "Current Rows", "color": "#ffcc99", "col": "right"},
    ],
    [
        {"source": "Sources", "action": "Errored", "color": "#ff5555", "col": "left"},
        {"source": "Sources", "action": "Downloaded", "color": "#8899ff", "col": "middle"},
        {"source": "Sources", "action": "Uploaded", "color": "#cc99ff", "col": "right"},
    ],
    [
        {"source": "Egress", "action": "Errored", "color": "#ff5555", "col": "left"},
        {"source": "Egress", "action": "Sheet Rows", "color": "#cc99ff", "col": "middle"},
        {"source": "Egress", "action": "Database Rows", "color": "#cc99ff", "col": "right"},
    ],
    [
        {"source": "Timings", "action": "Marshall Millis", "color": "#ff9900", "col": "left"},
        {"source": "Timings", "action": "Process Millis", "color": "#ff9900", "col": "middle"},
        {"source": "Timings", "action": "Egress Millis", "color": "#ff9900", "col": "right"},
    ],
]

assert all(
    (cell["source"], cell["action"]) in COUNTERS
    for row in CHART_SPEC for cell in row
), "CHART_SPEC references counters not in the registry"

_ENV = Environment(
    loader=FileSystemLoader(WEB_ROOT_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
TEMPLATE = _ENV.get_template("dashboard.html")


class _Handler(BaseHTTPRequestHandler):
    def __init__(self, history, run_callback, *args, **kwargs):
        self._history = history
        self._run_callback = run_callback
        self._head = False
        self._response_started = False
        super().__init__(*args, **kwargs)

    # noinspection PyPep8Naming
    def do_GET(self):  # noqa: N802
        self._dispatch("GET")

    # noinspection PyPep8Naming
    def do_HEAD(self):  # noqa: N802
        self._dispatch("HEAD")

    # noinspection PyPep8Naming
    def do_POST(self):  # noqa: N802
        self._dispatch("POST")

    def _dispatch(self, method: str):
        # noinspection PyBroadException
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            routes = self._routes_for(path, params)
            if routes is None:
                self._send_error_json(404, "not_found", f"unknown resource: {path}")
                return
            self._head = method == "HEAD"
            effective_method = "GET" if method == "HEAD" else method
            handler = routes.get(effective_method)
            if handler is None:
                allowed = set(routes.keys())
                if "GET" in allowed:
                    allowed.add("HEAD")
                self._send_error_json(405, "method_not_allowed", f"method {method} not allowed for {path}", allow=sorted(allowed))
                return
            handler()
        except Exception:
            if not self._response_started:
                self._send_error_json(500, "internal_error", "internal server error")

    def _routes_for(self, path: str, params):
        if path in ("/", "/history"):
            return {"GET": self._serve_history}
        if path == "/health":
            return {"GET": self._serve_health_json}
        if path == "/online":
            return {"GET": lambda: self._send_text(b"online\n")}
        if path == "/api/v1":
            return {"GET": self._serve_index}
        if path == "/api/v1/plugins":
            return {"GET": self._serve_plugins}
        if path == "/api/v1/counters":
            return {"GET": self._serve_counters}
        if path == "/api/v1/snapshot":
            return {"GET": lambda: self._serve_snapshot_filtered(params)}
        if path == "/api/v1/snapshot/views":
            return {"GET": lambda: self._serve_views_filtered(params)}
        if path.startswith("/api/v1/snapshot/views/"):
            view_name = path[len("/api/v1/snapshot/views/"):]
            return {"GET": lambda: self._serve_single_view(view_name, params)}
        if path == "/api/v1/run":
            return {"POST": self._serve_run}
        if path.startswith("/static/"):
            relative_path = path[len("/static/"):]
            return {"GET": lambda: self._serve_static(relative_path)}
        return None

    def _serve_index(self):
        self._send_json({
            "version": "v1",
            "resources": {
                "plugins": "/api/v1/plugins",
                "counters": "/api/v1/counters",
                "snapshot": "/api/v1/snapshot",
                "views": "/api/v1/snapshot/views",
                "view": "/api/v1/snapshot/views/{name}",
                "run": "/api/v1/run",
            },
        })

    def _serve_plugins(self):
        snapshot = self._history.snapshot()
        self._send_json({"plugins": snapshot.plugins})

    def _serve_counters(self):
        self._send_json({"counters": {f"{src}|{act}": dataclasses.asdict(counter) for (src, act), counter in COUNTERS.items()}})

    def _serve_run(self):
        if self._run_callback is None:
            self._send_error_json(405, "not_supported", "run trigger not available in polling mode")
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            params = json.loads(body)
        except json.JSONDecodeError:
            self._send_error_json(400, "invalid_body", "request body must be JSON")
            return
        run_result: list[dict | None] = [None]
        run_error: list[BaseException | None] = [None]
        completed = threading.Event()

        def _run() -> None:
            try:
                run_result[0] = self._run_callback(force_reprocessing=bool(params.get("force_reprocessing", False)))
            except BaseException as exc:
                run_error[0] = exc
            finally:
                completed.set()

        threading.Thread(target=_run, daemon=True).start()
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-API-Version", "v1")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        while not completed.wait(timeout=30):
            self.wfile.write(b"1\r\n \r\n")
        if run_error[0] is not None:
            self.wfile.write(b"0\r\n\r\n")
            return
        callback_result = run_result[0]
        plugin_counters = callback_result["counters"]  # type: ignore[index]
        response_body = json.dumps({"ts": callback_result["ts"], "counters": {"summary": aggregate_summary(plugin_counters), **plugin_counters}}).encode("utf-8")  # type: ignore[index]
        self.wfile.write(f"{len(response_body):x}\r\n".encode() + response_body + b"\r\n0\r\n\r\n")

    def _send_text(self, body: bytes, code: int = 200):
        self._response_started = True
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not self._head:
            self.wfile.write(body)

    def _send_json(self, data, code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self._response_started = True
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-API-Version", "v1")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not self._head:
            self.wfile.write(body)

    def _send_error_json(self, code: int, error_code: str, message: str, allow=None):
        body = json.dumps({"error": {"code": error_code, "message": message}}).encode("utf-8")
        try:
            self._response_started = True
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-API-Version", "v1")
            if allow is not None:
                self.send_header("Allow", ", ".join(allow))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not self._head:
                self.wfile.write(body)
        except OSError:
            pass

    def _serve_health_json(self):
        snapshot = self._history.snapshot()

        def status_for(plugin_name):
            result = self._history.is_errored(plugin_name)
            if result is None:
                return "unknown"
            return "unhealthy" if result else "healthy"

        overall = status_for("summary")
        plugins_status = {name: status_for(name) for name in snapshot.plugins}
        self._send_json({"status": overall, "plugins": plugins_status}, 200)

    def _serve_history(self):
        snapshot = self._history.snapshot()
        plugin_sections = [{"id": "summary", "title": "Summary", "theme": "ghost-gray"}] + [
            {"id": name, "title": name.capitalize(), "theme": THEMES[index % len(THEMES)]}
            for index, name in enumerate(p for p in snapshot.plugins if p != "summary")
        ]
        snapshot_json = json.dumps(dataclasses.asdict(snapshot))
        latest_run = self._history.latest_run_entry()
        latest_run_json = json.dumps(latest_run) if latest_run is not None else "null"
        body = TEMPLATE.render(
            snapshot_json=snapshot_json,
            latest_run_json=latest_run_json,
            run_timeout_ms=TIMEOUT_RUN_SECONDS * 1000,
            views=[{"name": v.name, "label": v.label} for v in snapshot.views],
            chart_spec=CHART_SPEC,
            plugin_sections=plugin_sections,
        ).encode("utf-8")
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not self._head:
            self.wfile.write(body)

    @staticmethod
    def _parse_last_param(params):
        last_str = params.get("last")
        if last_str is None:
            return None, None
        try:
            last_n = int(last_str)
            if last_n < 1:
                raise ValueError()
        except ValueError:
            return None, (400, "invalid_last", "last must be integer >= 1")
        return last_n, None

    @staticmethod
    def _parse_plugin_param(params, snapshot):
        plugin_name = params.get("plugin")
        if plugin_name is None:
            return None, None
        if plugin_name not in snapshot.plugins:
            return None, (404, "unknown_plugin", f"unknown plugin: {plugin_name}")
        return plugin_name, None

    def _apply_filters(self, snapshot, params):
        last_n, err = self._parse_last_param(params)
        if err:
            return None, err
        plugin_name, err = self._parse_plugin_param(params, snapshot)
        if err:
            return None, err
        result = dataclasses.asdict(snapshot)
        if plugin_name is not None:
            filtered_plugins = [p for p in result["plugins"] if p == "summary" or p == plugin_name]
            result["plugins"] = filtered_plugins
            for view in result["views"]:
                view["series"] = {p: v for p, v in view["series"].items() if p in filtered_plugins}
                view["errored"] = {p: v for p, v in view["errored"].items() if p in filtered_plugins}
        if last_n is not None:
            for view in result["views"]:
                timestamps = view["timestamps"]
                real_bins = len(timestamps)
                while real_bins > 0 and not timestamps[real_bins - 1]:
                    real_bins -= 1
                start = max(0, real_bins - last_n)
                end = real_bins
                in_progress = view["in_progress_bin"]
                view["timestamps"] = timestamps[start:end]
                view["series"] = {p: {src: {act: vals[start:end] for act, vals in actions.items()} for src, actions in srcs.items()} for p, srcs in view["series"].items()}
                view["errored"] = {p: vals[start:end] for p, vals in view["errored"].items()}
                view["bins"] = end - start
                view["in_progress_bin"] = in_progress - start if start <= in_progress < end else -1
        return result, None

    def _serve_snapshot_filtered(self, params):
        snapshot = self._history.snapshot()
        result, err = self._apply_filters(snapshot, params)
        if err:
            self._send_error_json(*err)
            return
        self._send_json(result)

    def _serve_views_filtered(self, params):
        snapshot = self._history.snapshot()
        result, err = self._apply_filters(snapshot, params)
        if err:
            self._send_error_json(*err)
            return
        assert result is not None
        self._send_json({"views": result["views"]})

    def _serve_single_view(self, view_name: str, params):
        snapshot = self._history.snapshot()
        result, err = self._apply_filters(snapshot, params)
        if err:
            self._send_error_json(*err)
            return
        assert result is not None
        matched = next((v for v in result["views"] if v["name"] == view_name), None)
        if matched is None:
            self._send_error_json(404, "unknown_view", f"unknown view: {view_name}")
            return
        self._send_json(matched)

    def _serve_static(self, relative_path: str):
        safe_path = os.path.normpath(os.path.join(WEB_ROOT_DIR, relative_path))
        if not safe_path.startswith(WEB_ROOT_DIR + os.sep) or not os.path.isfile(safe_path):
            self._send_error_json(404, "not_found", f"unknown static asset: {relative_path}")
            return
        stat_result = os.stat(safe_path)
        etag = f'"{stat_result.st_mtime_ns:x}-{stat_result.st_size:x}"'
        if self._static_not_modified(etag, stat_result.st_mtime):
            self._response_started = True
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            return
        content_type, _ = mimetypes.guess_type(safe_path)
        if content_type is None:
            content_type = "application/octet-stream"
        with open(safe_path, "rb") as handle:
            body = handle.read()
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", self.date_time_string(int(stat_result.st_mtime)))
        self.end_headers()
        if not self._head:
            self.wfile.write(body)

    def _static_not_modified(self, etag: str, mtime: float) -> bool:
        if_none_match = self.headers.get("If-None-Match")
        if if_none_match is not None:
            candidates = [tag.strip() for tag in if_none_match.split(",")]
            return etag in candidates or "*" in candidates
        if_modified_since = self.headers.get("If-Modified-Since")
        if if_modified_since is not None:
            try:
                return mtime <= parsedate_to_datetime(if_modified_since).timestamp()
            except (TypeError, ValueError):
                return False
        return False

    # noinspection PyShadowingBuiltins
    def log_message(self, format, *args):  # noqa: A002
        pass

    # noinspection PyShadowingBuiltins
    def log_error(self, format, *args):  # noqa: A002
        pass


def start_server(port, history, run_callback=None):
    def handler_factory(*args, **kwargs):
        return _Handler(history, run_callback, *args, **kwargs)

    server = ThreadingHTTPServer(("", port), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
