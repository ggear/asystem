import collections
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

_CHART_ROWS = [
    [
        ("Sources", "Downloaded", "Sources Downloaded"),
        ("Sources", "Uploaded", "Sources Uploaded"),
        ("Sources", "Errored", "Sources Errored")
    ],
    [
        ("Data", "Current Columns", "Data Current Columns"),
        ("Data", "Delta Rows", "Data Delta Rows"),
        ("Data", "Current Rows", "Data Current Rows")
    ],
    [
        ("Egress", "Queue Rows", "Egress Queue Rows"),
        ("Egress", "Sheet Rows", "Egress Sheet Rows"),
        ("Egress", "Database Rows", "Egress Database Rows")
    ],
]

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wrangle</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/apexcharts@3"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #eff4f7; color: #546e7a; font-family: 'Titillium Web', Arial, sans-serif; min-height: 100vh; }
    #topnav {
      background: #37474f; height: 60px; display: flex; align-items: center;
      padding: 0 30px; gap: 14px; position: sticky; top: 0; z-index: 100;
      box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    .nav-logo {
      width: 32px; height: 32px; border: 2px solid #26c6da; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      color: #26c6da; font-weight: 700; font-size: 13px; flex-shrink: 0;
    }
    .nav-title { color: #fff; font-size: 18px; font-weight: 700; letter-spacing: 0.5px; flex: 1; }
    .nav-title span { color: #26c6da; }
    .nav-meta { color: #90a4ae; font-size: 12px; white-space: nowrap; }
    .health-badge {
      padding: 4px 14px; border-radius: 20px; font-size: 11px;
      font-weight: 700; text-transform: uppercase; letter-spacing: 1px; white-space: nowrap;
    }
    .health-badge.healthy   { background: rgba(0,216,182,0.12); color: #00d8b6; border: 1px solid #00d8b6; }
    .health-badge.unhealthy { background: rgba(255,69,96,0.12);  color: #ff4560; border: 1px solid #ff4560; }
    .health-badge.unknown   { background: rgba(120,144,156,0.12); color: #78909c; border: 1px solid #78909c; }
    .content-area { max-width: 1200px; margin: 0 auto; padding: 32px 24px 56px; }
    .plugin-section { margin-bottom: 48px; }
    .plugin-header {
      display: flex; align-items: center; gap: 10px;
      margin-bottom: 20px; padding-bottom: 14px;
      border-bottom: 2px solid #dde4ea;
    }
    .plugin-name { font-size: 20px; font-weight: 700; color: #37474f; text-transform: capitalize; }
    .plugin-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
    .plugin-dot.ok    { background: #00d8b6; box-shadow: 0 0 0 3px rgba(0,216,182,0.2); }
    .plugin-dot.error { background: #ff4560; box-shadow: 0 0 0 3px rgba(255,69,96,0.2); }
    .chart-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-bottom: 18px; }
    .chart-card { background: #fff; border-radius: 6px; padding: 18px 16px 6px; box-shadow: 0 1px 22px -12px #607d8b; }
    .no-data { text-align: center; padding: 120px 20px; color: #90a4ae; }
    .no-data strong { display: block; font-size: 28px; font-weight: 600; margin-bottom: 10px; color: #b0bec5; }
    @media (max-width: 960px) { .chart-row { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 600px) { .chart-row { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div id="topnav">
    <div class="nav-logo">W</div>
    <div class="nav-title">Wran<span>gle</span></div>
    <div class="nav-meta"><<<NAV_META>>></div>
    <div class="health-badge <<<HEALTH_CLASS>>>"><<<HEALTH_TEXT>>></div>
  </div>
  <div class="content-area"><<<CONTENT>>></div>
  <script>
    var D = <<<RUN_DATA>>>;
    var RC = ['#00D8B6', '#008FFB', '#775DD0'];
    var CR = <<<CHART_ROWS>>>;
    var runs = D.runs;
    var labels = runs.map(function(r) { return r.ts; });
    D.plugins.forEach(function(pl) {
      CR.forEach(function(row, ri) {
        row.forEach(function(c, ci) {
          var isErr = c.a === 'Errored';
          var vals = runs.map(function(r) {
            var p = r.plugins[pl];
            return (p && p[c.s] && p[c.s][c.a] != null) ? p[c.s][c.a] : 0;
          });
          var colors = vals.map(function(v) {
            return isErr ? (v > 0 ? '#FF4560' : '#e8ecef') : RC[ri];
          });
          new ApexCharts(document.getElementById('c-' + pl + '-' + ri + '-' + ci), {
            chart: {
              type: 'bar', height: 190,
              toolbar: {show: false},
              animations: {enabled: true, speed: 500},
              fontFamily: "'Titillium Web', Arial, sans-serif",
            },
            plotOptions: {bar: {columnWidth: '72%', distributed: true, borderRadius: 2}},
            colors: colors,
            legend: {show: false},
            dataLabels: {enabled: false},
            series: [{name: c.l, data: vals}],
            xaxis: {
              categories: labels,
              labels: {show: false},
              axisBorder: {show: false},
              axisTicks: {show: false},
              tooltip: {enabled: false},
            },
            yaxis: {
              min: 0,
              tickAmount: 3,
              labels: {
                style: {colors: '#90a4ae', fontSize: '11px'},
                formatter: function(v) { return Number.isInteger(v) ? v.toLocaleString() : ''; },
              },
              axisBorder: {show: false},
              axisTicks: {show: false},
            },
            grid: {borderColor: '#f0f4f7', strokeDashArray: 4, xaxis: {lines: {show: false}}},
            title: {
              text: c.l, align: 'left', offsetY: 4,
              style: {fontSize: '13px', fontWeight: '600', color: '#546e7a'},
            },
            tooltip: {
              theme: 'light',
              x: {formatter: function(_, o) { return labels[o.dataPointIndex] || ''; }},
              y: {formatter: function(v) { return v.toLocaleString(); }},
            },
          }).render();
        });
      });
    });
  </script>
</body>
</html>"""


class RunHistory:
    def __init__(self, max_runs=25):
        self._runs = collections.deque(maxlen=max_runs)
        self._plugins = []
        self._lock = threading.Lock()

    def add_run(self, timestamp, plugins, errored):
        with self._lock:
            self._runs.append({"ts": timestamp, "plugins": plugins, "errored": errored})
            for name in plugins:
                if name not in self._plugins:
                    self._plugins.append(name)

    def is_healthy(self):
        with self._lock:
            if not self._runs:
                return None
            return not self._runs[-1]["errored"]

    def get_state(self):
        with self._lock:
            return list(self._runs), list(self._plugins)


def _generate_html(runs, plugins):
    if not runs:
        health_class, health_text, nav_meta = "unknown", "No Data", "No runs yet"
        content = '<div class="no-data"><strong>No Data</strong>Waiting for first run…</div>'
    else:
        last = runs[-1]
        health_class = "unhealthy" if last["errored"] else "healthy"
        health_text = "Unhealthy" if last["errored"] else "Healthy"
        nav_meta = f"{len(runs)} run{'s' if len(runs) != 1 else ''} · Last: {last['ts'].strftime('%d %b %H:%M')}"
        parts = []
        for plugin_name in plugins:
            last_plugin = last["plugins"].get(plugin_name, {})
            plugin_errored = any(
                last_plugin.get(src, {}).get("Errored", 0) > 0
                for src in ("Sources", "Files", "Data", "Egress")
            )
            dot_class = "error" if plugin_errored else "ok"
            rows_html = []
            for ri, row in enumerate(_CHART_ROWS):
                cards = "".join(
                    f'<div class="chart-card"><div id="c-{plugin_name}-{ri}-{ci}"></div></div>'
                    for ci in range(len(row))
                )
                rows_html.append(f'<div class="chart-row">{cards}</div>')
            parts.append(
                f'<div class="plugin-section">'
                f'<div class="plugin-header">'
                f'<div class="plugin-name">{plugin_name}</div>'
                f'<div class="plugin-dot {dot_class}"></div>'
                f'</div>'
                + "".join(rows_html)
                + '</div>'
            )
        content = "".join(parts)

    run_data = {
        "runs": [
            {
                "ts": r["ts"].strftime("%d %b %H:%M"),
                "errored": r["errored"],
                "plugins": r["plugins"],
            }
            for r in runs
        ],
        "plugins": plugins,
    }
    chart_rows = [
        [{"s": src, "a": act, "l": label} for src, act, label in row]
        for row in _CHART_ROWS
    ]
    return (
        _HTML
        .replace("<<<HEALTH_CLASS>>>", health_class)
        .replace("<<<HEALTH_TEXT>>>", health_text)
        .replace("<<<NAV_META>>>", nav_meta)
        .replace("<<<CONTENT>>>", content)
        .replace("<<<RUN_DATA>>>", json.dumps(run_data))
        .replace("<<<CHART_ROWS>>>", json.dumps(chart_rows))
    )


class _Handler(BaseHTTPRequestHandler):
    def __init__(self, history, *args, **kwargs):
        self._history = history
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path in ("/health", "/health/"):
            self._serve_health()
        elif self.path in ("/", "/history", "/history/"):
            self._serve_history()
        else:
            self.send_error(404)

    def _serve_health(self):
        healthy = self._history.is_healthy()
        if healthy is None:
            body, code = b"no data\n", 200
        elif healthy:
            body, code = b"healthy\n", 200
        else:
            body, code = b"unhealthy\n", 503
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_history(self):
        runs, plugins = self._history.get_state()
        body = _generate_html(runs, plugins).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_server(port, history):
    def handler_factory(*args, **kwargs):
        return _Handler(history, *args, **kwargs)

    server = HTTPServer(("", port), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
