# Plan — Redevelop `network` as a Go service

Redevelop `src/max/network` from its current skeleton into a real Go service that
mirrors `src/all/supervisor`'s module shape (directory layout, Docker build, fab
lifecycle, unit + system tests) but implements a **plugin-based network-health
monitor**. It polls a set of plugins (internet, wireless, zigbee), rolls their
samples into an aggregate window, decides a health status, and publishes the
result to MQTT (with Home Assistant discovery) and InfluxDB v3.

Runs on the `max` host (`macmini-max`, x86_64, server, deployment group 31).

---

## Design decisions (locked)

| Topic | Decision |
|---|---|
| Architecture | **Clean-room, borrow patterns only.** Fresh package structure. Supervisor is a *style/idiom* reference (cobra cmd, `slog`+`lumberjack` scribe, JSON `config.Load`, `context`-driven tick loop, table-driven tests, no code comments) — no stats/metric/cache code is lifted. |
| Status vocabulary | **Generic triad + detail.** Top-level `status ∈ {HEALTHY, DEGRADED, FLATLINE}`. Plugin-specific sub-states (e.g. `LAN_DOWN`, `ISP_DOWN`, `ELEVATED_LOSS`) go in `data.detail`, with an optional human `data.reason`. |
| Wireless source | **Local UniFi Network controller API** (unpoller-style, on-LAN). Controller URL + credentials from config. No cloud dependency. |
| Publishing | **Vitals only, for now.** `vitals` (aggregate) → MQTT retained (+ HA discovery) + InfluxDB line protocol. `pulse` (per-poll) stays in-memory in the aggregation window and is emitted to the debug log only — not published, not stored. |
| Poll cadence | **internet** runs the fast poll loop (default `--poll-period` = 5 min) and aggregates (default `--aggregate-period` = 15 min). **wireless** and **zigbee** run **only at the aggregate cadence** (every 15 min); they produce one sample per aggregate window and emit vitals directly, with no fast pulse phase. |
| Dashboard/API | Bundled HTTP server (Go `net/http` + `embed.FS` + `html/template`) — same *mechanism* as wrangle (server renders HTML with data injected as JSON + a `/api/v1/...` REST API + a trigger endpoint) but **minimal styling**, not wrangle's LCARS/ApexCharts theme. Renders the latest `pulse` and `vitals` `Message`s as pretty JSON with plain status badges and a "CHECK NOW" trigger. This is also where `pulse` (never published to MQTT/DB) becomes observable. |
| Commands | A single **command queue** (buffered channel) drained by the engine. Both the dashboard's `POST /api/v1/check` and an **MQTT command topic** enqueue onto it — one code path for on-demand actions (supervisor's `commandTopic` idiom + wrangle's `/run` trigger, unified). |

### Resolved
- **Short-flag clash** (brief listed `-p` twice): `--poll-period` keeps `-p`;
  `--filter-plugins` takes `-f`. **Confirmed.**
- **Binary delivery**: switch from the old "delivered at runtime via `/asystem/mnt`"
  model to supervisor's in-image build — Go builder stage compiles
  `/asystem/bin/network`, runtime stage `COPY --from`s it. `network/CLAUDE.md`
  updated accordingly. **Confirmed.**
- **Temp-probe device**: drop the `/dev/ttyUSBTempProbe` mapping from
  `docker-compose.yml` (temperature-probe leftover, unrelated to network health).
  **Confirmed.**

---

## Target module layout

Mirrors supervisor. New/changed paths under `src/max/network/`:

```
src/main/go/network/
  go.mod                     module network; go 1.25.0
  main.go                    func main(){ cmd.Execute() }
  CLAUDE.md                  module go-code guide (env, commands, arch, style)
  cmd/
    cmd.go                   root cobra cmd + Execute() + global flags + version
    cmd_serve.go             `serve` — run the poll/aggregate/publish daemon
    cmd_check.go             `check` — run one aggregate cycle, print vitals, exit (on-demand "check now")
  internal/
    config/
      config.go              Load() JSON config + env resolve (broker, database, unifi, targets)
      config_test.go
    scribe/
      scribe.go              slog + lumberjack file rotation (/tmp/network | /var/log/network)
      scribe_test.go
    engine/
      engine.go              poll+aggregate scheduler; drives plugins; fans results to publishers
      engine_broker.go       MQTT connect/publish (paho), retained vitals, HA status topic, LWT
      engine_database.go     InfluxDB v3 line-protocol writer
      engine_command.go      MQTT command-topic subscribe + command queue drain (on-demand check)
      store.go               thread-safe latest-Message store (per plugin: last pulse + last vitals)
      engine_test.go
    server/
      server.go              net/http server: HTML dashboard + /api/v1 REST + POST /api/v1/check
      server_test.go
      web/                   //go:embed assets
        dashboard.html       html/template; latest pulse/vitals as pretty JSON, minimal style
        dashboard.css        minimal stylesheet (status colors only)
    plugin/
      plugin.go              Plugin interface + registry + Message/Point/Field/Tag types + Status enum
      serialise.go           Message.MarshalJSON + Message.AppendLineProtocol (pooled buffers)
      serialise_test.go      round-trip JSON + line-protocol golden tests
      window.go              rolling aggregate window (ring of Message per plugin)
      window_test.go
      plugin_test.go
    plugins/
      internet/
        internet.go          ICMP burst probe (gateway + 1.1.1.1/8.8.8.8/9.9.9.9)
        decide.go            pure/stateless decision fn: []Pulse -> Vitals
        internet_test.go
        decide_test.go
      wireless/
        wireless.go          UniFi Network local API client; aggregate-only
        decide.go
        wireless_test.go
      zigbee/
        zigbee.go            zigbee2mqtt MQTT diagnostics; aggregate-only
        decide.go
        zigbee_test.go
    testutil/
      container.go           testcontainers helpers (MQTT broker, mock HTTP/ICMP targets)
      types.go
src/test/python/
  unit/unit_test.py          module-level unit harness (fab ut entry)
  system/system_test.py      docker-compose up, assert vitals on MQTT, tear down (fab st)
src/test/resources/
  config/*.json              happy/sad config fixtures
  mosquitto.conf             broker for system test
src/main/resources/image/
  config.json                generated by generate.py (broker/database/unifi/targets)
  bootstrap.sh checkalive.sh checkexecuting.sh checkhealthy.sh mqtt/...  (generated)
src/build/resources/
  bootstrap.sh check{alive,executing,healthy}.sh   (fragments — edit these)
Dockerfile docker-compose.yml deploy.sh install*.sh docker_deps_base.txt run_deps.txt
```

---

## CLI

Root command `network` with a `serve` daemon and a `check` one-shot. Global
persistent flags (match supervisor's cobra idiom, `SortFlags=false`):

| Flag | Short | Default | Meaning |
|---|---|---|---|
| `--filter-plugins` | `-f` | `""` (empty = all) | comma list restricting which plugins run (e.g. `internet,zigbee`) |
| `--poll-period` | `-p` | `5m` (`60s*5`) | fast poll cadence; drives pulse for poll-phase plugins (internet) |
| `--aggregate-period` | `-a` | `15m` (`60s*15`) | window rolled up before a status decision → vitals |
| `--publish-data` | `-d` | `false` | when true, publish vitals to MQTT + InfluxDB; when false, log only (dry run) |
| `--log-level` | `-l` | `info` | `debug`/`info`/`warn`/`error` |
| `--config` | `-c` | `/var/lib/asystem/install/network/latest/image/config.json` | config path |
| `--version` | `-v` | — | print version and exit |

`serve`-only flag: `--http-port` / `-w`, default `8090` — port for the dashboard +
REST API (`0` disables the server). `check` shares the engine's single-cycle
primitive with the dashboard button and the MQTT command, so all three are one path.

Period parsing follows supervisor's `makePeriods` style: parse via
`time.ParseDuration`, require `poll > 0`, `aggregate` a whole multiple of `poll`
(so internet's window holds an integer number of polls). Validation errors abort
`serve` with a clear message.

`check` = run each selected plugin through exactly one aggregate cycle
(internet: one burst folded into an otherwise-empty window; wireless/zigbee: one
sample), evaluate the decision function, print the vitals JSON, exit. No separate
code path — reuses the engine's single-cycle primitive.

---

## Data model (`internal/plugin`)

**One generic envelope serves both wire formats.** `pulse` and `vitals` share an
identical shape, so they collapse into a single `Message` type discriminated by a
`Message` field. The plugin-specific payload is **not** an opaque blob — it is a
list of `Point`s, each a set of string **Tags** (dimensions) plus typed **Fields**
(measurements). Tags map to InfluxDB tag sets, Fields to InfluxDB field sets, and
the whole `Message` marshals to the MQTT/JSON payload. This makes the same struct
efficiently serialisable to both line protocol and JSON with no reflection and no
`map[string]any` boxing.

```go
type Status string
const ( StatusHealthy Status = "HEALTHY"; StatusDegraded Status = "DEGRADED"; StatusFlatline Status = "FLATLINE" )

type Kind uint8
const ( KindNull Kind = iota; KindFloat; KindInt; KindBool; KindStr )

type Field struct {                 // typed value union: no interface{} boxing
    Key   string
    Kind  Kind
    Float float64
    Int   int64
    Bool  bool
    Str   string
}

type Tag struct{ Key, Value string }

type Point struct {                 // one InfluxDB series + one JSON object
    Tags   []Tag                    // ordered, low-cardinality dims: scope, target, ap, device
    Fields []Field                  // ordered; KindNull skipped on line-protocol write
}

type Message struct {               // single envelope for pulse AND vitals
    Message       string            // "pulse" | "vitals"
    Plugin        string            // "internet" | "wireless" | "zigbee"
    Host          string
    Timestamp     time.Time
    Status        Status            // generic triad
    Detail        string            // coarse sub-state: LAN_DOWN, ISP_DOWN, RF_CONGESTION...
    Reason        string            // optional human string
    SamplePeriodS int
    SampleCount   int
    Points        []Point           // the data as tagged, typed field-sets
}

type Plugin interface {
    Name() string                   // "internet" | "wireless" | "zigbee"
    PollPhase() bool                // true=fast poll loop (internet); false=aggregate-only (wireless,zigbee)
    Poll(ctx context.Context) (Message, error)        // one sample; Message=="pulse"
    Aggregate(window []Message) (Message, error)      // pure/stateless rollup+decision; Message=="vitals"
}
```

Ergonomic constructors keep plugin code terse and allocation-light:
`plugin.Float("avg_rtt_ms", 34.2)`, `plugin.Int`, `plugin.Bool`, `plugin.Str`,
`plugin.Null("min_rtt_ms")` build `Field`s; `plugin.NewPoint(tags, fields...)`.

**Two serialisers on `Message`, both streaming into a reused/pooled buffer:**

- `MarshalJSON() ([]byte,error)` — envelope + `points[]`, each point rendered
  `{"tags":{…}, "fields":{…}}` with typed values (`KindNull`→JSON `null`). Ordered
  slices give a byte-stable payload (good for retained MQTT + test assertions).
- `AppendLineProtocol(buf *bytes.Buffer, measurement string, ts int64)` — for each
  point writes `measurement,host=…,plugin=…,status=…,detail=…,<point tags> <fields> ts\n`
  using `strconv.Append*` directly (no reflection). `KindNull` fields are omitted;
  `status`/`detail` are added as tags on every point so InfluxDB can filter/group.
  Output is `[]byte` fed straight into supervisor-style `databaseClient.write`.

Design notes:
- **Slices, not maps** → deterministic field/tag order (line-protocol series
  stability + reproducible retained payloads) and no map-iteration overhead.
- **Typed `Field` union** → the hot line-protocol path avoids `any`/reflection.
- Numeric-only fields flow to InfluxDB; `KindStr`/`KindBool` are allowed as fields
  too (bools and quoted strings are valid line protocol) but string free-text like
  `Reason` stays JSON-only.
- **Registry**: each plugin self-registers in `init()` (supervisor's `registerProbes`
  pattern); engine filters by `--filter-plugins`.
- Decision functions (`decide.go`) are **pure and stateless** given the window
  slice `[]Message` → produce a `vitals` `Message`; trivially unit-testable,
  independent of scheduling.

### Status semantics
- `HEALTHY` — everything within normal range.
- `DEGRADED` — reachable but impaired (elevated loss/RTT/jitter; some targets/APs/devices down but not all).
- `FLATLINE` — no usable signal for the whole window (internet: all internet targets down, or gateway down → `data.detail=LAN_DOWN`; wireless: controller unreachable/no APs; zigbee: coordinator offline/no device reports).

---

## Engine (`internal/engine`)

Single `context`-cancellable scheduler (supervisor `probe.Run` tick-loop idiom):

1. `time.Ticker` at `poll-period`. On each tick, run `Poll()` for every
   **poll-phase** plugin (internet), concurrently; append each `pulse` `Message` to
   that plugin's rolling window (`internal/plugin/window.go`, a ring sized to
   `aggregate/poll` samples). Log the pulse at debug. Nothing published.
2. A second ticker at `aggregate-period`. On each aggregate tick:
   - For poll-phase plugins: call `Aggregate(window)` over the accumulated pulses.
   - For **aggregate-only** plugins (wireless, zigbee): call `Poll()` once *now* to
     get a single fresh sample, then `Aggregate([]Message{that})`.
   - Publish each resulting `vitals` `Message` (if `--publish-data`).
3. Graceful shutdown on `SIGINT`: publish `offline` status, flush, disconnect, stop
   the HTTP server.

The engine also owns a **latest-Message store** (`store.go`): a thread-safe map
keyed by plugin holding the most recent `pulse` and `vitals` `Message`. Each poll
updates last-pulse; each aggregate updates last-vitals. The HTTP server reads from
it (network's analogue of wrangle's `history.snapshot()`).

---

## HTTP dashboard & API (`internal/server`)

Same *mechanism* as wrangle's `server.py` (a `net/http` server rendering an HTML
page with data injected as JSON, a versioned REST API, and a trigger endpoint) but
**minimal styling**. Started by `serve` on `--http-port` unless `0`; a plain
`http.ServeMux`, handlers read the engine's latest-store and enqueue commands.

Routes (wrangle-shaped, network payloads):

| Method | Path | Returns |
|---|---|---|
| GET | `/` | HTML dashboard (`html/template` from `//go:embed web/`) |
| GET | `/online` | `online\n` (liveness) |
| GET | `/health` | `{ "status": <overall triad>, "plugins": { "<name>": <triad> } }` |
| GET | `/api/v1` | resource index |
| GET | `/api/v1/plugins` | `{ "plugins": [ {"name","poll_phase"} ] }` |
| GET | `/api/v1/pulse` `?plugin=` | latest `pulse` `Message`(s), full JSON |
| GET | `/api/v1/vitals` `?plugin=` | latest `vitals` `Message`(s), full JSON |
| POST | `/api/v1/check` | body `{"plugin":"internet"}` (or all) → enqueue an on-demand check; chunked keep-alive like wrangle's `/run`; responds with the fresh `vitals` |

**Dashboard content (minimal):** one section per plugin showing a status badge
(HEALTHY green / DEGRADED amber / FLATLINE red, from a tiny `dashboard.css`), the
`Detail`/`Reason`, and the latest `pulse` and `vitals` `Message`s pretty-printed in
`<pre>` blocks (the raw JSON, as requested). A "CHECK NOW" button per plugin does
`fetch('/api/v1/check',{method:'POST',body:{plugin}})` then refreshes. A small
`setInterval` auto-refresh (fetches `/api/v1/vitals` + `/api/v1/pulse` and re-renders
the `<pre>` blocks). No charts, no external CDN, no fonts/sounds — a single embedded
CSS file. Data injected on first paint as `window.NETWORK_DATA = {{ json }}`.

JSON responses reuse `Message.MarshalJSON`, so the API and the MQTT payloads are
byte-identical. `no-store`, `X-API-Version: v1` headers as in wrangle.

---

## Command queue (HTTP + MQTT) — `engine_command.go`

One buffered `chan command` decouples request receipt from the engine loop; a
single drain runs commands so there is no separate "check now" code path.

```go
type command struct {
    Action string   // "check"
    Plugin string   // "" = all selected plugins
    Result chan Message   // optional; HTTP waits on it, MQTT ignores
    Source string   // "http" | "mqtt"
}
```

- **MQTT source** (`engine_command.go`): on connect, subscribe
  `network/${SUPERVISOR_HOST}/command/#` (supervisor's `commandTopic` idiom).
  Payload `{"command":"check","plugin":"internet"}` → build a `command`, enqueue,
  and publish an ack/result to `network/${SUPERVISOR_HOST}/command/result` (the
  resulting `vitals` JSON). Unknown/malformed payloads logged and dropped.
- **HTTP source**: `POST /api/v1/check` enqueues a `command` with a `Result`
  channel and streams keep-alive bytes until it resolves (wrangle `/run` pattern),
  then writes the `vitals` JSON.
- **Drain**: a goroutine (or the aggregate tick) pops a `command`, runs exactly one
  aggregate cycle for the target plugin(s) — `Poll()` once, fold into the current
  window, re-evaluate `Aggregate` — publishes the fresh `vitals` (if
  `--publish-data`), updates the latest-store, and signals `Result`. Identical to
  the `check` subcommand's primitive.

Bounded queue (drop-oldest or reject-when-full with a logged warning) prevents a
command storm from stalling the poll loop.

Publishing (`--publish-data` true):
- **MQTT** (`engine_broker.go`, paho like supervisor): vitals → retained topic
  `network/${SUPERVISOR_HOST}/data/<plugin>/vitals`; a retained
  `network/${SUPERVISOR_HOST}/status` = `online`/`offline` with an `offline` LWT.
  Reuse supervisor's broker connect/reconnect/`SetWill` structure.
- **InfluxDB v3** (`engine_database.go`): call `Message.AppendLineProtocol` for each
  vitals into a single reused `bytes.Buffer` (one line per `Point`), then hand the
  `[]byte` to a supervisor-style `databaseClient.write`. Connection from config
  (`DATABASE_*`), same InfluxCommunity client + reconnect-on-error logic supervisor uses.

---

## Plugin: internet

Poll-phase. Plugin constants (from config, sane defaults): `Targets` = default
route gateway + `1.1.1.1` (Cloudflare) + `8.8.8.8` (Google) + `9.9.9.9` (Quad9);
`BurstSize` 8–10; `BurstGap` ~100–150 ms; `BurstTimeout` ~2–3 s.

**Poll** — send a concurrent burst of `BurstSize` **unprivileged ICMP (UDP-based,
no root)** pings to every target. Per target compute: loss %, avg/min/max RTT,
jitter (stddev of burst RTTs). Emit a `pulse` `Message` — one `Point` per target
(gateway carries `scope=gateway`, publics `scope=target`):

```json
{ "message":"pulse","plugin":"internet","host":"macmini-max","timestamp":"...",
  "status":"DEGRADED","detail":"ELEVATED_LOSS","reason":"elevated loss on 8.8.8.8/9.9.9.9",
  "sample_period_s":300,"sample_count":1,
  "points":[
    { "tags":{"scope":"gateway","target":"192.168.1.1"},
      "fields":{"sent":8,"recv":8,"loss_pct":0.0,"avg_rtt_ms":1.2,"min_rtt_ms":0.9,"max_rtt_ms":1.6,"jitter_ms":0.2} },
    { "tags":{"scope":"target","target":"1.1.1.1"},
      "fields":{"sent":8,"recv":8,"loss_pct":0.0,"avg_rtt_ms":12.4,"min_rtt_ms":11.1,"max_rtt_ms":14.0,"jitter_ms":1.1} },
    { "tags":{"scope":"target","target":"8.8.8.8"},
      "fields":{"sent":8,"recv":6,"loss_pct":25.0,"avg_rtt_ms":41.7,"min_rtt_ms":33.2,"max_rtt_ms":58.9,"jitter_ms":9.4} },
    { "tags":{"scope":"target","target":"9.9.9.9"},
      "fields":{"sent":8,"recv":0,"loss_pct":100.0,"avg_rtt_ms":null,"min_rtt_ms":null,"max_rtt_ms":null,"jitter_ms":null} } ] }
```

**Aggregate/decide** (`decide.go`, pure over `[]Message`) — roll up the last N
polls: avg loss %, avg RTT, avg jitter; per-target reachability count across the
window; gateway reachability. Emit a `vitals` `Message` — a `scope=summary` point
plus one `scope=target` point each:

```json
{ "message":"vitals","plugin":"internet","host":"macmini-max","timestamp":"...",
  "status":"DEGRADED","detail":"ELEVATED_LOSS","reason":"elevated loss",
  "sample_period_s":900,"sample_count":3,
  "points":[
    { "tags":{"scope":"summary"},
      "fields":{"avg_loss_pct":12.5,"avg_rtt_ms":34.2,"avg_jitter_ms":8.1,"gateway_ok":true} },
    { "tags":{"scope":"target","target":"1.1.1.1"}, "fields":{"ok":true,"loss_pct":0.0,"avg_rtt_ms":12.4} },
    { "tags":{"scope":"target","target":"8.8.8.8"}, "fields":{"ok":true,"loss_pct":25.0,"avg_rtt_ms":41.7} },
    { "tags":{"scope":"target","target":"9.9.9.9"}, "fields":{"ok":false,"loss_pct":100.0,"avg_rtt_ms":null} } ] }
```

Line protocol emitted for that vitals (nulls dropped, `status`/`detail` as tags):

```
network,host=macmini-max,plugin=internet,status=DEGRADED,detail=ELEVATED_LOSS,scope=summary avg_loss_pct=12.5,avg_rtt_ms=34.2,avg_jitter_ms=8.1,gateway_ok=true <ts>
network,host=macmini-max,plugin=internet,status=DEGRADED,detail=ELEVATED_LOSS,scope=target,target=8.8.8.8 ok=true,loss_pct=25,avg_rtt_ms=41.7 <ts>
network,host=macmini-max,plugin=internet,status=DEGRADED,detail=ELEVATED_LOSS,scope=target,target=9.9.9.9 ok=false,loss_pct=100 <ts>
```

Decision (generic status + `data.detail`):

| status | data.detail | condition |
|---|---|---|
| HEALTHY | `UP` | gateway reachable; ≥2/3 internet targets consistently reachable; avg loss low; RTT/jitter normal |
| DEGRADED | `ELEVATED_LOSS` / `HIGH_LATENCY` | gateway reachable; targets reachable but avg loss elevated (~2–20%) or RTT/jitter abnormally high |
| FLATLINE | `ISP_DOWN` | gateway reachable but all (per policy, most) internet targets unreachable across the whole window |
| FLATLINE | `LAN_DOWN` | gateway itself unreachable across the window (local router/LAN problem, distinct from ISP outage) |

Rationale: requiring agreement across multiple public targets before declaring an
outage avoids false alarms from a single provider blip — one target failing while
others succeed is at most `DEGRADED`. Bursts run **concurrently** to keep each poll
sub-3 s so a poll doubles as an on-demand "check now".

---

## Plugin: wireless (aggregate-only, every 15 min)

Talk to the **local UniFi Network controller** (unpoller-style). Config supplies
controller URL + credentials/API key. One sample per aggregate window:

- `GET .../proxy/network/api/s/<site>/stat/device` → APs: state, uptime, load,
  channel utilization / interference, TX retries, per-radio client counts.
- `GET .../proxy/network/api/s/<site>/stat/sta` → clients: RSSI/signal, tx/rx
  rate, satisfaction/experience, per-AP distribution.

Assess wireless health broadly: APs up vs configured, poor-signal client count,
channel-utilization/retry hotspots, mean client experience. Emit a `vitals`
`Message` — a `scope=summary` point plus per-AP (`scope=ap`, tag `ap=<name>`) and
optionally per-band points — with `status` triad and `Detail` (e.g. `AP_DOWN`,
`RF_CONGESTION`, `POOR_CLIENTS`). `decide.go` pure over the single-sample window.

---

## Plugin: zigbee (aggregate-only, every 15 min)

Follow the methodology in
`src/meg/homeassistant/src/main/resources/data/custom_packages/diagnostics.yaml`,
sourced via **zigbee2mqtt over MQTT**. Subscribe/query z2m topics
(`zigbee2mqtt/bridge/state`, `.../bridge/info`, `.../bridge/devices`, per-device
`availability` and `linkquality`). Assess zigbee health as many ways as possible:

- coordinator/bridge online; permit-join state sane;
- device count online vs total; devices `offline`/unavailable;
- LQI distribution (min/mean/weak-link count); recent last-seen staleness;
- router vs end-device topology health.

Emit a `vitals` `Message` — a `scope=summary` point (device counts, online ratio,
min/mean LQI, weak-link count) plus optional per-device points (`scope=device`,
tag `device=<friendly_name>`, fields `lqi`, `available`, last-seen age) — with the
`status` triad and `Detail` (e.g. `COORDINATOR_DOWN`, `DEVICES_OFFLINE`,
`WEAK_LINKS`). Pure `decide.go` over the sample.

---

## Docker / build / deploy

- **Dockerfile** — adopt supervisor's multi-stage shape. Add a Go builder stage
  (goenv toolchain, `go build` → `/asystem/bin/network`) that the runtime stage
  `COPY --from`s, so the binary ships **inside the image** (drop the current
  "binary delivered via `/asystem/mnt`" model and update `network/CLAUDE.md`,
  which currently documents the mnt entrypoint). Runtime `FROM debian:slim` with
  the pinned base packages. `CMD ["/asystem/bin/network","serve","-c","/asystem/etc/config.json"]`.
  Build-only toolchain packages (`ca-certificates`, `gcc`, `libc6-dev` if cgo)
  go in `docker_deps_build.txt`, pinned; keep `docker_deps_base.txt` slim
  (`bash coreutils less curl vim jq mosquitto-clients`).
- **docker-compose.yml** — keep `network` + `network_bootstrap`, `256M` limit,
  `TZ=Australia/Perth`, `BROKER_*`/`DATABASE_*` env, `${SERVICE_DATA_DIR}:/asystem/mnt`.
  Add a `ports:` mapping for the dashboard (`--http-port`, default `8090`) and a
  `NETWORK_HTTP_PORT`/`UNIFI_*` env passthrough. HA/nginx can proxy the dashboard
  like other service UIs.
  The internet plugin needs egress ICMP — verify default bridge networking permits
  unprivileged ICMP; if kernel `ping_group_range` blocks it in-container, document
  the `net.ipv4.ping_group_range` sysctl or `cap_add: NET_RAW` fallback. Drop the
  temp-probe `/dev/ttyUSBTempProbe` device mapping (belongs to the old skeleton,
  unrelated to network health) unless still wanted.
- **run_deps.txt** — `vernemq`, `postgres` stay; add nothing unless wireless needs
  a dep host up first.
- **config.json / generate.py** — extend `write_...` generation to emit
  broker + database + a `unifi` block (controller URL/site/creds) + internet
  `targets`/burst tuning. Keep HA discovery generation: `write_entity_metadata`
  filtered to `device_via_device == "Zeroth"` on `network_${SUPERVISOR_HOST}`
  topics (already wired in `generate.py`).
- **Health-check fragments** (`src/build/resources/`, then `fab generate`):
  - `checkalive.sh` — `pgrep -f "/asystem/bin/network" >/dev/null`
  - `checkexecuting.sh` — checkalive && MQTT `network/$SUPERVISOR_HOST/status` == `online`
  - `checkhealthy.sh` — checkexecuting && latest `.../data/internet/vitals` parses and `status != FLATLINE` (via `mosquitto_sub -C 1 -W 2` + `jq -e`)
  - `bootstrap.sh` — (re)publish HA discovery via generated `mqtt.sh`.
  No `#` comments in fragments (they get line-joined).
- **install_pre.sh** already runs `mqtt.sh`; keep. `deploy.sh` mirrors supervisor's
  SSH-triggered install.

---

## Tests

- **Go unit** (`go test ./...` via `fab ut`): decision functions (`decide_test.go`)
  are the priority — table-driven, `expectedError bool` last, every case fills it.
  Cover internet (healthy / elevated-loss DEGRADED / ISP_DOWN / LAN_DOWN /
  2-of-3 thresholds), plus config parse (happy/sad fixtures), window ring behavior,
  period validation. Mock ICMP/HTTP/MQTT via injected function fields (supervisor's
  `cpuTimes func(...)` seam pattern) so no network in unit tests.
- **testutil** (`testcontainers-go`): spin an MQTT broker; stub UniFi HTTP and a
  z2m publisher for integration coverage.
- **server** (`server_test.go`, `httptest`): route/status-code coverage, `/health`
  triad mapping, `/api/v1/vitals` JSON shape, `POST /api/v1/check` enqueues one
  command and returns fresh vitals. **command** drain: HTTP and MQTT commands both
  land on the queue and run exactly one aggregate cycle; bounded-queue overflow.
- **System** (`fab st`, `system_test.py`): `docker-compose up`, wait for
  `network/<host>/data/internet/vitals` retained message, assert schema + `status`
  in the triad; `GET /health` returns `200` and `GET /online` returns `online`;
  `POST /api/v1/check` returns vitals; tear down.

---

## Suggested build order

1. Scaffold Go module: `go.mod`, `main.go`, `cmd/` (flags, version, `serve`/`check` stubs), `config`, `scribe`. Build green, `--version` works.
2. `plugin` package: interface, registry, `Message`/`Point`/`Field`/`Tag`/`Status`, the two serialisers (JSON + line protocol), window ring + tests.
3. `engine` scheduler (poll + aggregate tickers, filter, dry-run logging) — no publish yet.
4. **internet** plugin: ICMP burst `Poll`, pure `decide.go`, full decision tests. `network check` prints vitals.
5. `engine_broker.go` + `engine_database.go`; wire `--publish-data`; HA status/LWT; retained vitals; line protocol.
6. Latest-store + command queue (`store.go`, `engine_command.go`) + MQTT command topic; wire the `check` subcommand through the queue.
7. `internal/server`: `net/http` + embedded minimal dashboard + `/api/v1` + `POST /api/v1/check`; `--http-port`; tests via `httptest`.
8. **wireless** (UniFi local API) + **zigbee** (z2m MQTT), aggregate-only, with decide tests.
9. Dockerfile Go build stage, `docker_deps_build.txt`, compose ICMP capability + port mapping, health-check fragments, `generate.py` config extension. `fab generate`.
10. System test; `fab t`; then `fab pkg`; update `network/CLAUDE.md`.

---

## Cross-cutting conventions

- Go: build/test with `GOROOT=~/.goenv/versions/1.25.8 ~/.goenv/versions/1.25.8/bin/go`.
- **No comments** in `.go` source; no blank lines inside funcs/structs (repo + supervisor style).
- Never edit generated artifacts (`.env`, `src/main/resources/image/*.sh`, `config.json`, `docker_deps.sh`, `target/`); edit sources and `fab generate`.
- Never `git add` unless a commit is explicitly requested.
