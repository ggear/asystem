# Dashboards

How the `grafana` module builds, configures and deploys its dashboards, and the migration from the legacy
jsonnet/grizzly/Flux stack to the Foundation SDK, the Grafana CLI (`gcx`) and SQL. Status is marked per section:
**built** is in the repo today, **planned** is not. Nothing here is built yet.

**The outcome.** The default org and nothing else — no public, private or default split, no anonymous access.
One set of dashboards in one tree, `data/dashboards/`, all native `dashboard.grafana.app/v2` YAML, grouped by
provenance: `generated/` (rendered from Python on the Grafana Foundation SDK), `snippets/` and `custom/`
(hand-authored in the Grafana UI). All are pushed by `gcx` through **one script that both `bootstrap.sh` and
`deploy.sh` run**. Panel queries are SQL: InfluxDB 3 SQL over Flight SQL for `home`, Postgres
SQL for `wrangle`. Panels are derived from the `_` schema documents and `entity_metadata.xlsx` wherever the data
has a declared shape, and hand-written only where it does not. `grafana.ini` stops being a vendored copy. Every
jsonnet, grafonnet, grizzly and Flux line is deleted.

**How to read it.** *Current state* is the inventory and why most of it cannot simply be ported. *Target* is the
shape. *Catalogue* is the part you will live with — what is generated, what is hand-written, and where common
elements are owned. *Schema contract* and *Queries* feed it. *Dependencies*, *Image*, *Config*, *Push path* are
the runtime. *Gaps and decisions* is the assessment.

## Current state

The module is the oldest still running and predates every convention `supervisor`, `network` and `wrangle` follow.

| Concern | Today |
|---|---|
| Authoring | jsonnet on a forked `grafonnet-lib` (`ggear-grafonnet`), 6.2k lines across 19 templates |
| Variants | `//ASM` `//AST` `//ASD` line prefixes, specialised by `generate.py` into `mobile`/`tablet`/`desktop` copies — 48 generated files |
| Orgs | org 1 *Public Portal* (anonymous, holds no dashboards — `public/generated/dashboard_graphs.jsonnet` is empty), org 2 *Private Portal* with its own admin user, four `Private_*` folders |
| Deploy | `grr apply` per `dashboard_*.jsonnet` in `bootstrap.sh`; `deploy.sh` builds grizzly from source with Go 1.16 from Homebrew paths, and does not work |
| Deps | `GRIZZLY_VERSION` in `.env_fab`, `grr-linux-amd64` curled into the image (amd64 only), grizzly and grafonnet cloned into `.deps` by `generate.sh` |
| Datasource | one, `InfluxDB_V3` (SQL mode) created by `curl`, while every panel names `InfluxDB_V2` and queries Flux |
| Queries | Flux, against buckets `data_public`, `data_private`, `host_private`, `home_private` — none exist in InfluxDB 3 |
| Config | `grafana.ini` vendored from an older release, 1946 lines against 13.2.2's 2338 |
| Panels | legacy Angular `graph` panel (removed upstream), `schemaVersion=30` |

**Why the data is broken, per source.** Most dashboards read measurements nothing writes any more.

| Dashboard | Panels | Reads today | Producer then | Producer now |
|---|---:|---|---|---|
| Currency | 11 | `data_public/currency` fields `aud/gbp` … | old wrangle → InfluxDB 2 | `wrangle` → Postgres `currency` |
| Interest | 10 | `data_public/interest` | old wrangle | `wrangle` → Postgres `interest` |
| Equity | 11 | `data_private/equity` incl. `holdings` | old wrangle | `wrangle` → Postgres `equity` (no holdings) |
| Servers | 14 | `host_private/{cpu,mem,disk,diskio,net,sensors,swap,system}` | telegraf (archived) | `supervisor/host` → InfluxDB 3 |
| Containers | 12 | `host_private/docker_*` | telegraf docker input (archived) | `supervisor/service` → InfluxDB 3 |
| Network | 12 | `host_private/{usg,usw,uap,uap_vaps,clients}` | unpoller (archived) | `network` wireless/ethernet/zigbee/weewx → InfluxDB 3 |
| Internet | 12 | `host_private/{internet,clientdpi,usg_wan_ports}` | old internet probe, unpoller | `network` internet/domain/certificate/diagnosis → InfluxDB 3 |
| Health | 0 | every panel commented out | — | — |
| Conditions, Control, Diagnostics, Electricity, Rain | 16 | `home_private` by `entity_id`, field `value` | Home Assistant → InfluxDB 2 | Home Assistant → InfluxDB 3 `<domain>__<device_class>` |
| Home ×3, Homes | 4 | dashboard lists, org-switch links | — | — |

Only the xlsx five keep their identity (`entity_id`), and even they moved measurement: HA now writes one measurement
per `domain__device_class` (`sensor__temperature`, `sensor__power`, …) with tag `module='homeassistant'`, field
`value`.

The shared header (`header_metadata.jsonnet`, 547 lines — freshness, poll age, point counts and four error stats on
every dashboard) reads wrangle `type == "metadata"` rows that current wrangle neither declares nor writes.

## Target — planned

### Module layout

```
src/max/grafana/
  CLAUDE.md                                       new, module rules
  Dockerfile                                      grafana + gcx, both pinned in .env_fab
  docker-compose.yml                              GF_* overrides, provisioning path, no grizzly
  generate.sh                                     pulls gcx at GCX_VERSION, like sonarr pulls sonarr
  deploy.sh                                       copies data/ to the host, runs push.sh in the container
  src/build/python/grafana/
    generate.py                                   the only build Python, like every other module: common elements, one
                                                  section per generated dashboard, the snippet merge and the YAML writer
  src/build/resources/
    bootstrap.sh                                  fragment: runs push.sh
    push.sh                                       fragment: the one push path
    check{alive,executing,healthy}.sh             rewritten counts
    plans/dashboards.md                           this file
  src/main/resources/data/                        → SERVICE_DATA_DIR → /asystem/mnt
    dashboards/
      generated/<uid>.yaml                        native v2, banner, written by fab generate — never edit
      snippets/<uid>.yaml                         native v2, hand-authored — panels merged into generated/<uid>.yaml
      custom/<uid>.yaml                           native v2, hand-authored — a whole dashboard, pushed as-is
      folders/<uid>.yaml                          folder.grafana.app/v1, banner
      preferences/namespace.yaml                  preferences.grafana.app/v1, banner
    provisioning/datasources/asystem.yaml         banner
```

**Every dashboard is in one tree, in one format.** `src/main/resources/data/dashboards/` holds every dashboard
Grafana will show, as native `dashboard.grafana.app/v2` YAML. The directory says where it came from:

- `generated/` is build output, with the banner.
- `snippets/` and `custom/` are hand-authored, with no banner.

A generated dashboard and a hand-authored one can be diffed directly. Copying one from `generated/` into `custom/`
forks it into a hand-authored dashboard.

**One build file, like every module.** All ~35 modules keep their build Python in a single
`src/build/python/<module>/generate.py`, and shared build code lives only in `_`. Grafana follows suit. Each
generated dashboard is a section of `generate.py`, headed `# Build dashboard [<uid>]` in the style of
supervisor's `# Build broker schema`, and homeassistant generates its Lovelace dashboards the same way in one
1,589-line file. The one-file-per-dashboard view lives on the output side, `data/dashboards/generated/<uid>.yaml`,
which is where a dashboard is read anyway. `grep "dashboard \[<uid>\]" generate.py` finds its source.

**Why under `data/`.** `data/` is installed to `SERVICE_DATA_DIR` and mounted at `/asystem/mnt`, so:

- `deploy.sh` can replace dashboards on the host without a new image, and the running container sees them
  immediately;
- hand-authored files are pushed from where they live, with no copy step, which is what keeps the banner meaning
  only one thing.

Mixing hand-maintained and generated, bannered YAML in `data/` is an existing repo pattern: homeassistant's
`data/` does the same. The never-edit list gains `data/dashboards/{generated,folders,preferences}/` and
`data/provisioning/`. `data/dashboards/{snippets,custom}/` are sources.

### Generated files carry the build banner

Every file `generate.py` writes starts with the same banner as every other module's generated output:

```
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################
```

The text comes from the shared `banner()` in `asystem/schema/query.py`, its single owner, which the influxdb3,
postgres and vernemq emitters already use. `banner` is added to the explicit `from asystem.schema import (...)`
list in `asystem/__init__.py`, so `generate.py` reaches it through `from asystem import *` instead of copying the
string. JSON has no comments, so every generated file is YAML. gcx reads YAML resources natively, and Grafana's
provisioning format is YAML anyway.

| File | Banner | Written from |
|---|---|---|
| `data/dashboards/generated/<uid>.yaml` | yes | its section of `generate.py`, plus `snippets/<uid>.yaml` when present |
| `data/dashboards/folders/<uid>.yaml` | yes | `generate.py`, common elements |
| `data/dashboards/preferences/namespace.yaml` | yes | `generate.py`, common elements |
| `data/provisioning/datasources/asystem.yaml` | yes | `generate.py`, common elements |
| `image/{bootstrap,push,checkalive,checkexecuting,checkhealthy}.sh` | yes, already, via `write_container_*` | `src/build/resources/*.sh` fragments |
| `_`: `schema/<dialect>/document.yaml` in each module (*C1*) | yes | the module's schema reflection |
| `data/dashboards/{snippets,custom}/<uid>.yaml` | **never** | hand-authored. The build rejects one that contains the banner, so a generated file pasted back as a source is caught |

### One writer, so every dashboard reads alike

The SDK's output and a Grafana UI export are both v2, but they differ in noise. The export carries server metadata
(`resourceVersion`, `generation`, `creationTimestamp`, `uid`, `managedFields`), and the two use different key
order. `fab generate` passes **every** YAML file under `data/dashboards/` through one writer, about 20 lines of
`yaml.SafeDumper` configuration in `generate.py`:

- **sorted keys**, the only order both the SDK and the UI can share;
- **multi-line strings as `|` blocks**, so SQL reads and diffs as SQL;
- **server metadata stripped**, and `metadata.name` set from the file name.

Generated files are written that way. Hand-authored files are **rewritten in place** that way, with no banner,
the same as the build already rewrites source with `ruff --fix`, `cargo fmt` and `gofmt -w`. After a build,
generated and hand-authored dashboards differ only in directory and banner, never in layout. The writer is
deterministic, so regeneration stays byte-stable (*D9*).

Empty defaults (`description: ''`, `links: []`) are **kept**. The SDK emits them itself, as required or defaulted
fields, so stripping them would mean code that fights the SDK, for files that are only ever read in diffs.

### One org, one set

- **Default org only.** Org 1 as Grafana creates it. Org 2, `admin_private`, every `*_PRIVATE` var and the
  `Public`/`Private`/`Default` naming are gone. Anonymous auth is off. Bootstrap does not touch orgs or users.
- **No form-factor copies.** One dashboard per subject, uid = the subject (`currency`, not `currency-desktop`),
  laid out from today's **desktop** sizes so the shape is preserved. Grafana collapses a grid to one column below
  its mobile breakpoint, which covers what the `mobile` copies did by hand. *D1.*
- **Folders by subject**, not by audience or device: `Finance`, `Infrastructure`, `Home`, plus `Snippets`
  (*Catalogue*).
- **Navigation** by v2 dashboard `links` (by tag, as dropdown) on every dashboard, replacing the HTML text panels
  with `onClick` links — which also retires `disable_sanitize_html`. The home dashboard is one `dashboardlist`.

## Catalogue — planned

**Native formats only, and only the code the data forces.** Grafana sees one format, the native v2 dashboard
YAML. Python exists only where panels must be computed from data: the xlsx, the schema relations, and the shared
header. Nothing is invented: no DSL, no parser, no templating language.

### The three categories

| Category | Lives in | Source format | Authored by | Edit it to |
|---|---|---|---|---|
| **generated** | output `data/dashboards/generated/<uid>.yaml`, source the `# Build dashboard [<uid>]` section of `generate.py` | Python + Foundation SDK | code, from data | add or restyle a panel over declared data, or (xlsx) add entities **in the xlsx** |
| **snippets** | `data/dashboards/snippets/<uid>.yaml` | native v2 Dashboard | the Grafana UI | change the hand-written panels of generated dashboard `<uid>` |
| **custom** | `data/dashboards/custom/<uid>.yaml` | native v2 Dashboard | the Grafana UI | change a dashboard that has no generated partner |

Snippets and custom are the same kind of file. The difference is the rule: **a snippet is named after the
generated dashboard it extends, and a custom dashboard has no generated partner.** The build fails if a snippet
has no `generated/<uid>`, or if a custom file's uid collides with one.

Shared elements live only at the top of `generate.py`, because only generated dashboards share them. A hand-authored
dashboard that wants a common element takes it from a generated example (*Forking*).

### Every dashboard

| Dashboard | Category | Source | Folder | Panels from |
|---|---|---|---|---|
| Control | generated | `generate.py` [control] | home | xlsx |
| Diagnostics | generated | `generate.py` [diagnostics] | home | xlsx |
| Electricity | generated | `generate.py` [electricity] | home | xlsx |
| Rain | generated | `generate.py` [rain] | home | xlsx |
| Conditions | generated + snippets | `generate.py` [conditions], `snippets/conditions.yaml` | home | xlsx; snippets *Temperature Forecast* (pivots `bom_darlington_temp_{max,min}_<n>` into days ahead) and *Lounge* (a composite across measurements), from today's `snippet_conditions.jsonnet` |
| Containers | generated | `generate.py` [containers] | infrastructure | supervisor/service |
| Servers | generated | `generate.py` [servers] | infrastructure | supervisor/host, HA `rack_temperature` |
| Network | generated | `generate.py` [network] | infrastructure | network wireless/ethernet/zigbee/weewx, supervisor/host, HA |
| Internet | generated | `generate.py` [internet] | infrastructure | network internet/domain/certificate/diagnosis |
| Interest | generated | `generate.py` [interest] | finance | wrangle interest/rate |
| Currency | generated | `generate.py` [currency] | finance | wrangle currency/rate (`invert`, `baseline`) |
| Equity | generated + snippets | `generate.py` [equity], `snippets/equity.yaml` | finance | wrangle equity/ticker; snippets *Portfolio Performance* and *Portfolio Range Performance* (an equal-weight mean across tickers). Holdings dropped (*D2*) |
| Home | custom | `custom/home.yaml` | — | a dashboard list |
| Health | deleted | | | every panel was commented out |
| Homes | deleted | | | it only switched orgs |

That is 12 generated dashboards, 2 snippet files (4 panels) and 1 custom dashboard. The snippets' `rawSql` is the
only hand-written SQL in the estate, against ~120 hand-written Flux queries today.

### Generated sources

The currency section of `generate.py`, illustrative. Each section builds one value into `DASHBOARDS`, never a
function, so the single-use-function rule never applies:

```python
    # Build dashboard [currency]
    PAIRS = [("GBP/AUD", "AUD/GBP", 1.58, 2.07), ("USD/AUD", "AUD/USD", 1.30, 1.60), ("SGD/AUD", "AUD/SGD", 1.00, 1.20)]
    RATE = relation("wrangle", "currency/rate")
    DASHBOARDS["currency"] = dashboard("currency", "Currency", FINANCE, YEARS, header(RATE, "wrangle"), [
    [*(stat(f"{pair} Last End of Day", RATE.query(["snapshot"], entities=[code], invert=True), 3, 3)
       .thresholds(higher_better(low, high)) for pair, code, low, high in PAIRS),
     bars("CCY/AUD Range End of Day Deltas", RATE.query(["snapshot"], invert=True, baseline=True), 9, 8)
       .thresholds(DELTA)],
    [series(f"{pair} End of Days", RATE.query(["snapshot"], entities=[code], invert=True), 24, 12)
     for pair, code, _, _ in PAIRS],
])
```

`stat`, `series`, `bars` and the rest return the **SDK's own builders** with house defaults applied, so any SDK
option can be chained on (`.thresholds(...)`, `.unit(...)`) without wrapping. The xlsx dashboards share one section:

```python
    # Build dashboard [conditions] [control] [diagnostics] [electricity] [rain]
    for uid, title in [("conditions", "Conditions"), ("control", "Control"), ("diagnostics", "Diagnostics"),
                       ("electricity", "Electricity"), ("rain", "Rain")]:
        DASHBOARDS[uid] = xlsx_dashboard(uid, title, HOME, WEEK)
```

`xlsx_dashboard` (a common element, used by all five) turns the group's xlsx rows into panels:
- `entity_domain` is the panel;
- `graph_break` splits it;
- `grafana_display_type` picks line or step;
- `unit_of_measurement` sets the unit.

**Where snippets go.** A row may be the marker `SNIPPETS`, which places `snippets/<uid>.yaml`'s panels at that
point, so Equity's portfolio panels keep their place mid-dashboard. Without a marker, snippets go directly under the
header, as `snippet_conditions.jsonnet` does today.

### Snippets and custom dashboards

Both are whole native v2 dashboards: elements, layout, everything Grafana stores, with the SQL as a `rawSql: |`
block. Because a snippet is a whole dashboard, it carries its own panel sizes and positions, and needs no field of
ours.

The edit loop is the Grafana UI:

1. **Custom:** open the dashboard. **Snippet:** open it in the **Snippets** folder, since `push.sh` pushes every
   snippet file as its own dashboard, uid `snippets-<uid>`, so its panels can be edited and previewed live.
2. Edit and save in the UI. Dashboards stay editable (*D7*).
3. `gcx resources pull dashboards.v2.dashboard.grafana.app/<name> -o yaml` into `custom/<uid>.yaml` or
   `snippets/<uid>.yaml`.
4. `fab generate` normalises the file, re-merges the snippet into `generated/<uid>.yaml`, and validates. Read the
   diff, then `fab deploy`.

Nothing is copy-pasted, and the SQL is never retyped. Each snippet panel's `description` says why it is
hand-written. A panel without one fails the build, which keeps bespoke SQL rare and explained.

### Forking and examples

Because every dashboard is the same normalised format in one tree, the generated ones are the reference examples
for hand authoring:

- **To see how something is expressed natively** (a palette, the header, a legend style), open the
  `generated/<uid>.yaml` that uses it.
- **To fork a generated dashboard into a hand-authored one**:
  1. `cp generated/<uid>.yaml custom/<uid>.yaml`;
  2. delete the banner;
  3. delete its `# Build dashboard [<uid>]` section from `generate.py`;
  4. `fab generate`.

  The uid, folder and URL are unchanged.
- **To hand-author a panel next to generated ones:** start `snippets/<uid>.yaml` from a copy of the generated
  dashboard, keep only the panels you are writing, and edit them in the UI.

### Common elements — top of `generate.py`

| Element | Defines | Replaces |
|---|---|---|
| `INFLUXDB3`, `POSTGRES` | the two datasource uids, also used to render the provisioning file | `'InfluxDB_V2'` in ~120 panels, and the `curl` datasource block |
| `FINANCE`, `INFRASTRUCTURE`, `HOME`, `SNIPPETS_FOLDER` | folders | `Private_*` folders |
| `LIVE`, `HOURS`, `DAYS`, `WEEK`, `YEAR`, `YEARS` | range, refresh and picker options | 14 `//ASDASHBOARD_DEFAULTS` lines |
| `dashboard(uid, title, folder, time, header, rows)` | `editable: true` (*D7*), shared crosshair, `timezone: browser`, folder tag, nav links; packs rows left to right by width into a `GridLayout` (about 15 lines, kept over v2 `AutoGrid` because today's dashboards mix widths) | `dashboard.new(...)` per file, absolute `gridPos` |
| `xlsx_dashboard(uid, title, folder, time)` | the xlsx group's rows as panels | the Flux-emitting loop in today's `generate.py` |
| `stat`, `series`, `steps`, `bars`, `gauge`, `state`, `table` | the SDK panel builder plus house options: right-side legend table with min/max/mean, no fill, decimals | `graph.new(...)`/`stat.new(...)` blocks |
| `higher_better(lo, hi)`, `lower_better(lo, hi)`, `DELTA`, `BINARY`, `PERCENT_USED` | threshold ladders by meaning | ~200 `.addThreshold(...)` chains |
| `UNITS` | the unit table (*C3*), covering both schema units and the xlsx `unit_of_measurement` values (`W`, `kWh`, `mm`, `mm/h`, `ppm`, `dB`, `µg/m³`, `kg`, `°C`, `%`) | `unit=`/`formatY1=` literals |
| `relation(module, path)` | loads the `document.yaml` relation; `.query(measures, entities, invert, baseline)` calls the dialect `panel()` (*C2*) | Flux per target |
| `header(relation, service)` | the twelve-slot header row (*Header row*) | the 547-line header |

**What is native rather than ours.** A stat's reduction is the stat panel's own reducer, and series are split
by a `metric` column, which Grafana splits by itself. Only `invert` and `baseline` stay in SQL, because Grafana has
no native "percent change from the first point".

### How changes are made

| To | Edit |
|---|---|
| add an HA entity to a home dashboard | the xlsx row, then `fab generate` |
| add a panel over existing declared data | its section of `generate.py`, one line |
| add a bespoke panel to a generated dashboard | `snippets/<uid>.yaml` in the UI, then pull |
| add a dashboard | a new `# Build dashboard [<uid>]` section in `generate.py` (or a row in the xlsx loop), or a UI-built `custom/<uid>.yaml` |
| restyle every stat, or change every legend | the helper at the top of `generate.py` |
| change what "stale" means everywhere | `header` at the top of `generate.py` |
| try something out | edit it in the Grafana UI. It is lost on the next push unless pulled |

### Code we write, in total

| Where | What | Size |
|---|---|---|
| `_` `dialects/{influxdb3,postgres}.py` | `panel()` with `invert`/`baseline`, and a `Dataquery` subclass each (*C2*) | ~60 lines each |
| `_` `emit.py` + `document.py` | `document.yaml` write and `load_schema_artifact` (*C1*) | ~40 lines |
| `generate.py` | common elements (~240), the xlsx section (~5), seven schema sections (~30–80 each), snippet merge, normalising writer, folders, preferences, provisioning (~140) | ~800 lines |
| `snippets/`, `custom/` | none — authored in Grafana | 0 |

That is roughly 900 lines of Python (about 800 in `generate.py`, the rest in `_`), replacing 6,200 lines of jsonnet and the 547-line header library.

Rejected:

- **Our own YAML format.** It is not native, and would need a parser, validator, templating and a schema of its
  own.
- **Native YAML for every dashboard.** That means ~120 hand-maintained panels disconnected from the xlsx and the
  schema, and 12 copies of the header.
- **Library panels for the header.** It differs per dashboard by relation and service, which would mean dashboard
  variables interpolated into table names.
- **Single-panel snippets.** A v2 panel has no size or position, so they would need an invented field, and a
  copy-paste out of an export.
- **Pruning empty defaults.** That is code that fights the SDK, for files only read in diffs.
- **A Python module per dashboard** (`common.py` plus `generated/{xlsx,schema}/<uid>.py`). No other module splits
  its build Python. Shared build code belongs in `_`, the only place `fab` lints and type-checks, and grafana-only
  helpers do not qualify. The output tree already gives one file per dashboard.

### Validation

The SDK's typed builders reject malformed panels, so what remains is checking against the data, and the build
fails loudly when:

- a `relation(...)`, or a measure or entity passed to `.query(...)`, is absent from the module's `document.yaml`;
- an xlsx `unique_id` is not an entity of any HA relation, an xlsx panel mixes units, or a `grafana_display_type`
  is outside the vocabulary;
- a snippet has no generated partner, a custom uid collides with a generated one, or a snippet panel lacks a
  `description`;
- a hand-authored file contains the banner, or a generated file is missing it;
- an xlsx entity has no measurement in homeassistant's committed `document.yaml`. The error names the entity and
  the fix, `fab generate` in `src/meg/homeassistant` (*D19*);
- a unit has no mapping, a row is wider than 24, or a uid is used twice.

### Header row

Today's header is a strip of twelve `w=2` slots across the top of every dashboard. Five of its sources no longer
exist: the four error stats came from wrangle metadata rows, and the poll age came from the same rows. **The strip
keeps its twelve slots, its order and its thresholds style. Each slot that lost its source is redrawn from data
that exists**, so every dashboard looks the same as today and the same as every other dashboard. Two sources feed
it:

- the dashboard's **primary relation** (`relation`), for example `wrangle` `currency/rate`, `supervisor/host`, or
  the HA measurements of an xlsx group;
- the **producing service's** `supervisor/service` row (`service`), for example `wrangle`, `homeassistant`,
  `supervisor`, `network`. Every producer is a supervised service, so this source exists for every dashboard.

| Slot | Today | Now | Source |
|---|---|---|---|
| 1 | Dashboards (HTML nav) | **Last Updated**: `max(time)` | relation |
| 2 | Time Since Poll | **Time Since Poll**: age of the service's newest supervisor row. Green under 2× the 6s cadence | service |
| 3 | Time Since Update | **Time Since Update**: `now() - max(time)`. Green under 2× the relation `cadence`, yellow under 4×, red above. HA's `<on-change>` relations take an explicit ceiling in the catalogue | relation |
| 4 | Last Updated | **Update Entities**: distinct entities in the newest row set | relation |
| 5 | Update Metrics | **Update Metrics**: declared measures carrying a value in the newest row set | relation |
| 6 | Update Points | **Update Points**: rows in the newest row set | relation |
| 7 | Total Metrics | **Total Entities**: distinct entities in range | relation |
| 8 | Total Points | **Total Points**: `count(*)` in range | relation |
| 9 | Source Errors | **Service Status**: last `status` | service |
| 10 | File Errors | **Service Health**: last `health_status` | service |
| 11 | Data Errors | **Service Restarts**: increase in `restart_count` over the range | service |
| 12 | Egress Errors | **Service Backup**: last `backup_status` (`BINARY` palette) | service |

Nav moves to dashboard links, which frees slot 1. Slots 9–12 are the closest available equivalent of "is the
producer erroring": `status` drops when the service stops reporting, `health_status` when its healthcheck fails,
and a restart is how a crashing producer usually shows itself. The header is one helper, `header` in `generate.py`, so a better
source for any slot later is a single edit.

### Substitutions

Every panel whose source is archived keeps its slot, size and panel kind. It is redrawn from the nearest declared
measure, and its title changes to name what it now shows, so a reader is never misled (*D8*). Panels whose
data still exists map directly and are not listed.

| Dashboard | Was | Now | Source |
|---|---|---|---|
| Containers | Container Images Currently Installed | **Services Configured**: count of `configured_status = 1` | supervisor/service |
| Containers | Container Image Usage | **Service Restarts**: `restart_count` increase per service | supervisor/service |
| Servers | Servers Min Uptime | **Servers Min Availability**: min over hosts of `avg(status) * 100` (*D5*) | supervisor/host |
| Network | Gateway Uptime | **Gateway Reachability**: `avg(reachable) * 100` for the gateway target | network internet/target |
| Network | Network Unique Clients | **Wireless Clients Total**: sum of `clients` across access points | network wireless/accesspoint |
| Network | Wireless Performance | **Wireless Experience**: `experience_pct` per access point | network wireless/accesspoint |
| Network | Wireless Quality Score (5GHz) / (2.4GHz) | **Wireless Experience Min** / **Zigbee Link Quality Min**: no per-band data, so the pair becomes Wi-Fi and Zigbee | network wireless/accesspoint, zigbee/device `lqi` |
| Network | Network Throughput | **Network Utilisation**: `used_network` per host | supervisor/host |
| Network | Network Clients | **Access Point Clients**: `clients` per access point | network wireless/accesspoint |
| Network | Network Device CPU Usage | **Network Diagnosis**: `score` per plugin | network diagnosis/plugin |
| Network | Network Device RAM Usage | **Switch Port Health**: `up`, `degraded` per port | network ethernet/port |
| Network | Network Device Temperature | **Network Device Temperature**: HA `utility_temperature` and `rack_temperature` (the first was already on the panel) | homeassistant sensor__temperature |
| Network | Wireless Clients | **Zigbee Devices Available**: `available` per device | network zigbee/device |
| Network | Wired Clients | **Switch Ports Up**: count of `up = 1` | network ethernet/port |
| Internet | Internet Uptime | **Internet Reachability**: `avg(reachable) * 100`, public targets | network internet/target |
| Internet | Domain Uptime | **Domain Resolution Agreement**: `avg(ok) * 100` across resolvers | network domain/resolver |
| Internet | Service Availability | **Certificate Verified**: `verified` | network certificate/endpoint |
| Internet | Internet Max Upload | **Internet Max Latency**: `max(rtt_ms)`, public targets | network internet/target |
| Internet | Internet Max Download | **Internet Max Loss**: `max(loss_pct)`, public targets | network internet/target |
| Internet | Internet Total Throughput | **Internet Jitter**: `jitter_ms` per target | network internet/target |
| Internet | Internet Max Throughput | **Internet Max Jitter**: `max(jitter_ms)` | network internet/target |
| Internet | Internet Categorised Throughput | **Network Diagnosis**: `score` per plugin | network diagnosis/plugin |
| Internet | Domain Resolution | **Domain Resolution**: `latency_ms` per resolver (direct) | network domain/resolver |

Each substitution is an ordinary `.query(...)` panel in its dashboard's section of `generate.py`, so none of them adds hand-written SQL.
Where a richer source appears later, for example if the network module grows gateway or speed-test relations,
moving a panel back is a one-line change to its `schema:` key.

## Schema contract — planned

The catalogue reads the *declared* shape of the data — relation, dimensions, entities, measures, units, cadence.
Today that shape exists only while a module's own `generate.py` reflects it (`go run ./tools/schema`, a Python
import, or for Home Assistant a live database discovery). `grafana` cannot re-run another module's reflector: it
would need that module's toolchain state and, for HA, a live InfluxDB.

**C1. Emit the schema document as an artifact.** `write_schema_database` additionally writes
`src/build/resources/schema/<dialect>/document.yaml` — the `SchemaDocument` after `merge_schema_entities`, with
the entities `generate.py` filled in, in exactly the shape `load_schema_document`'s docstring specifies. It is
YAML rather than JSON only so it can carry the build `banner()` like every other file under `schema/`.
`parse_schema_document` is split so its dict-level half is shared: the reflectors keep `json.loads` on stdout, and
the artifact reader uses `yaml.safe_load`. The validation path is the same, and there is no new parser. `_` owns the writer (`emit.py`) and the reader, a new
`load_schema_artifact(module, dialect)`. HA's discovered document is written the same way, so `grafana` gets the
`entity_id → measurement` map from a committed file. Tested as a round trip: every committed `document.yaml`
parses, and equals a fresh reflection for the module under test.

**C2. Grafana SQL lives with the dialect.** `dialects/influxdb3.py` and `dialects/postgres.py` already own every
predicate their backend needs (`where`, `_binned`, `_aggregate`, the `module = '<m>'` and `IS [NOT] NULL` sibling
predicates that keep relations sharing a measurement apart). Each gains one public `panel(relation, document,
measures, entities=None, transforms=())` returning Grafana SQL, with Grafana macros in place of the fixed
`now() - INTERVAL` windows, and the `Dataquery` subclass the Foundation SDK lacks for that backend. `_localised`
is not applied: Grafana renders in the browser's zone, panel SQL stays UTC.

**C3. No presentation in the contract.** Titles, colours, thresholds and layout stay in `grafana`. The contract
already carries what is derivable: `description` → panel description, `unit` → panel unit, `period` → series
filter, `cadence` → interval floor and freshness thresholds, `entities` → series. A measure `range` for gauges is
left out until a second consumer wants it.

Units cross a boundary, so the unit table `UNITS` in `generate.py` is tested against every unit in every committed
`document.yaml` — a producer adding a unit fails `grafana`'s build rather than rendering as `short`:

| Schema | Grafana |
|---|---|
| `%` | `percent` |
| `$` | `currencyUSD` (as today, *D6*) |
| `°C`, `Celsius` | `celsius` |
| `ms` | `ms` |
| `s` | `s` |
| `d` | `d` |
| `MiB` | `mbytes` |
| `Mbps` | `Mbits` |
| `-`, empty | `none` |

## Queries — planned

### Datasources

Provisioned by file, not `curl`: `generate.py` writes `provisioning/datasources/asystem.yaml`, using Grafana's
own `$VAR` expansion so the file holds no secrets, and Grafana reads it from `/asystem/mnt/provisioning`
(`GF_PATHS_PROVISIONING`). The uids are `INFLUXDB3`/`POSTGRES` in `generate.py`, which also renders this file.

| uid | type | target |
|---|---|---|
| `influxdb3-home` | `influxdb`, `version: SQL` | `${INFLUXDB3_SERVICE}:${INFLUXDB3_API_PORT}`, db `${INFLUXDB3_DATABASE_HOME}`, Flight SQL, `insecureGrpc: true` |
| `postgres-wrangle` | `grafana-postgresql-datasource` | `${POSTGRES_SERVICE}:${POSTGRES_API_PORT}`, db `${POSTGRES_DATABASE_WRANGLE}`, `timescaledb: true`, `sslmode: disable` (*D23*), as `${POSTGRES_USER_WRANGLE}`/`${POSTGRES_KEY_WRANGLE}` (*D3*) |

`run_deps.txt` gains `postgres` and drops `vernemq` (Grafana never used the broker).

### Flux idioms and their SQL

| Flux pattern | SQL |
|---|---|
| `range(v.timeRangeStart, v.timeRangeStop)` | `WHERE $__timeFilter(time)` |
| `aggregateWindow(every: v.windowPeriod, fn: mean)` | InfluxDB `$__dateBin(time)` + `avg()`; Postgres `$__timeGroupAlias(time, $__interval)` |
| `… \|> last() \|> keep(["_value"])` for a stat | the series query; the stat reduces `lastNotNull` — one query feeds value and sparkline |
| one target per entity + `rename(…)` | one query `time, entity AS metric, value`; series split by `metric` |
| `findRecord(idx: 0)` baseline, `(baseline - v) / baseline * 100` | `baseline`: `(value / first_value(value) OVER (PARTITION BY entity ORDER BY time) - 1) * 100` |
| `map(… 1.0 / r._value)` | `invert`: `1.0 / value`, series named by the inverted pair |
| `r["entity_id"] == "a" or …` | `entity_id IN (…)` via `query.literals()` |
| `createEmpty: true` for discrete | `Steps` kind (`stepAfter`), no gap filling in SQL |
| `range(start: -100y)` totals | header totals are over the dashboard range, not all time; all-time counts over a `-100y` range were the slowest query on every dashboard |

## Dependencies — planned

Per the repo convention: tool versions pinned in `.env_fab` with a `# NOTES:` release-list line and passed into
the Dockerfile as `ASYSTEM_<NAME>` build args by `fab`; build-library Python pinned in `py_deps_prod.txt`; an
upstream whose release is pinned is cloned into `.deps` by the module's `generate.sh`.

| Change | Where |
|---|---|
| **remove** `GRIZZLY_VERSION` and its NOTES line | `.env_fab` |
| **add** `GRAFANA_VERSION=13.2.3` (2026-09-29, the latest release; bumps today's 13.2.2) — `# NOTES: https://github.com/grafana/grafana/releases` (moves out of the Dockerfile `FROM`, so the SDK bump gate in *D9* can name it) | `.env_fab` |
| **add** `GCX_VERSION=1.4.0` — `# NOTES: https://github.com/grafana/gcx/releases` | `.env_fab` |
| **add** `grafana-foundation-sdk==0.0.20` (PyPI moved from `<epoch>!<grafana>` to `0.0.x`; 0.0.20 is 2026-09-09) | `py_deps_prod.txt`, beside `pandas`/`openpyxl` |
| **remove** grizzly and grafonnet `pull_repo`s and the grafonnet copy into `image/libraries` (the directory goes too) | `generate.sh` |
| **add** `pull_repo … "grafana" "gcx" "grafana/gcx" "v${GCX_VERSION}"` | `generate.sh` |
| **delete** `.deps/grafana/{grizzly,grafonnet-lib}` | by hand |

`gcx` (`v1.4.0`, 2026-10-02) is the Grafana CLI's successor to `grafanactl`, whose repo was archived 2026-06-01.

## Image — planned

```dockerfile
# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_GRAFANA_VERSION="latest"
FROM grafana/grafana:${ASYSTEM_GRAFANA_VERSION} AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=… && \
    apk add --upgrade --no-cache coreutils=… && \
    apk add --upgrade --no-cache less=… && \
    apk add --upgrade --no-cache curl=… && \
    apk add --upgrade --no-cache vim=… && \
    apk add --upgrade --no-cache jq=… && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_GCX_VERSION
ARG TARGETARCH
RUN cd /tmp && \
    curl -sfSLO "https://github.com/grafana/gcx/releases/download/v${ASYSTEM_GCX_VERSION}/gcx_${ASYSTEM_GCX_VERSION}_linux_${TARGETARCH}.tar.gz" && \
    curl -sfSLO "https://github.com/grafana/gcx/releases/download/v${ASYSTEM_GCX_VERSION}/gcx_${ASYSTEM_GCX_VERSION}_checksums.txt" && \
    grep "gcx_${ASYSTEM_GCX_VERSION}_linux_${TARGETARCH}.tar.gz" "gcx_${ASYSTEM_GCX_VERSION}_checksums.txt" | sha256sum -c - && \
    tar -xzf "gcx_${ASYSTEM_GCX_VERSION}_linux_${TARGETARCH}.tar.gz" -C /usr/local/bin gcx && \
    rm -f gcx_* && \
    gcx --version

FROM image_base AS image_build
COPY target/package/main/resources/image/. /asystem/etc

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT [ "/run.sh" ]
```

- `apk` pins are refreshed by running the generated `docker_deps.sh` against the new base, as for every module.
- `TARGETARCH` replaces the hard-coded `grr-linux-amd64`; `max` is x86_64 but a local `SERVICE_LOCAL_RUNTIME=native`
  build on arm64 now works.
- The `cp config/grafana.ini /etc/grafana` line goes (*Config*); the image's own `/etc/grafana/grafana.ini` is
  the base.

## Config — planned

**Rebaseline on the shipped file, customise over the top.** Our `grafana.ini` is a whole-file copy of an old
`sample.ini` with eleven live settings; the rest is upstream's commented defaults, now stale — 13.2.2 (and so 13.2.3) adds
`[dashboard_cleanup]`, `[rbac.iam_client]`, `[unified_alerting.notification_history]`,
`[unified_alerting.prometheus_conversion]`, `[annotations.app_platform]`, `[marketplace]`, `[time_picker]`,
`[secrets_manager]`, `[provisioning]`, `[tracing.opentelemetry.file]`, drops `[feature_management]`, and ours has
a duplicate `[unified_alerting.reserved_labels]`.

The image ships the current file for its own version at `/etc/grafana/grafana.ini`. Delete our copy and apply each
customisation as `GF_<SECTION>_<KEY>` in `docker-compose.yml`, beside the `GF_SECURITY_ADMIN_*` already there. The
base then always matches the pinned image and cannot go stale on a bump; the overrides are a short reviewed list.

| Today | Decision | Override |
|---|---|---|
| `server.http_port = ${GRAFANA_HTTP_PORT}` | keep | `GF_SERVER_HTTP_PORT` |
| `server.domain = ${GRAFANA_DOMAIN}` | keep | `GF_SERVER_DOMAIN` |
| `server.root_url = ${GRAFANA_DOMAIN_URL}` | keep | `GF_SERVER_ROOT_URL` |
| `users.allow_sign_up = false` | keep, explicit though it is the default | `GF_USERS_ALLOW_SIGN_UP=false` |
| `users.allow_org_create = false` | keep | `GF_USERS_ALLOW_ORG_CREATE=false` |
| `auth.anonymous.enabled = true` | **drop** — all private | default `false` |
| `auth.anonymous.org_name = Public Portal` | **drop** | — |
| `auth.anonymous.hide_version = true` | **drop** with anonymous | — |
| `log.level = warn` | keep | `GF_LOG_LEVEL=warn` |
| `recording_rules.enabled = false` (+ stale `url`/`basic_auth_*`/`timeout`) | keep `false` — upstream now defaults `true`, nothing uses it | `GF_RECORDING_RULES_ENABLED=false` |
| `panels.disable_sanitize_html = true` | **drop** — no HTML panels remain | — |
| — | **new**: provisioning from the data mount | `GF_PATHS_PROVISIONING=/asystem/mnt/provisioning` |
| — | **new**: no phoning home | `GF_ANALYTICS_REPORTING_ENABLED=false`, `GF_ANALYTICS_CHECK_FOR_UPDATES=false` |
| — | **new**: browser timezone default | `GF_USERS_DEFAULT_TIMEZONE=browser` |
| — | **new**: long sessions for wall displays (*D16*) | `GF_AUTH_LOGIN_MAXIMUM_INACTIVE_LIFETIME_DURATION=90d`, `GF_AUTH_LOGIN_MAXIMUM_LIFETIME_DURATION=365d` |

Fallback if a setting ever cannot be an env var (none today): vendor the pinned `conf/sample.ini` into `.deps` from
`generate.sh` and patch keys in `generate.py`. Rejected as the default because it reintroduces the copy that went
stale.

**Persistence.** `GF_PATHS_DATA` stays the image default `/var/lib/grafana`, unmounted: the SQLite database is
rebuilt on every container recreation. With everything generated that is correct — code is the source of truth, no
backup needed, and a dashboard deleted from the catalogue is gone on the next release without a prune. *D7.*

## APIs — planned

**Rule: the newest *stable* version of each API that the pinned Grafana serves.** Experimental (`v0alpha1`) and
`v*beta*` versions are not used where a stable one exists. Older versions are not used just because a tool still
defaults to them. All three tools target the same version of each resource: the SDK builds it, gcx pushes it,
and the server stores it. Checked against `v13.2.3`, `grafana-foundation-sdk==0.0.20` and gcx `v1.4.0`:

| Concern | API used | Built by | Applied by | Not used, and why |
|---|---|---|---|---|
| Dashboards | `dashboard.grafana.app/v2` (stable; `dashboardNewLayouts` is GA in 13.2, so v2 layouts are on by default) | SDK `builders.dashboardv2` | `gcx resources push dashboards` | `v2beta1`, `v2alpha1`, `v1`, `v1beta1`, the legacy `/api/dashboards/db` |
| Folders | `folder.grafana.app/v1` | SDK `builders.folderv1` | `gcx resources push folders` | `v1beta1`, the legacy `/api/folders` |
| Org home dashboard, timezone | `preferences.grafana.app/v1`, the org-level object (owner name `namespace`; confirm with `gcx resources get preferences` in phase 2) | SDK `models.preferencesv1alpha1` spec, emitted under `apiVersion: preferences.grafana.app/v1`. The spec is identical between versions in `apps/preferences/kinds/preferences.cue`, and the SDK has no `v1` builder yet | `gcx resources push preferences` | the legacy `PATCH /api/org/preferences`, which 13.2 now reroutes to this API anyway (`preferences.rerouteLegacyAPIs` is GA) |
| Datasources | file provisioning (`apiVersion: 1` YAML), reloaded with `POST /api/admin/provisioning/datasources/reload` | `generate.py` | Grafana at start; `push.sh` on reload | `datasource.grafana.app` exists only as `v0alpha1` (experimental). Move to it once it is stable — the change is confined to `push.sh` and the provisioning writer |
| Removing a dashboard | `dashboard.grafana.app/v2` delete | — | `gcx resources delete dashboards/<uid>` for each uid on the server and not on disk | `push` has no prune flag in v1.4.0 |
| Liveness, counts | `/api/health`, `/api/admin/stats` | — | health checks | no app-platform equivalent; these are the current endpoints |
| Panel queries | the datasource query path that dashboards use | — | Grafana | `query.grafana.app`: `queryService` is still experimental |

Not adopted: Grafana's `provisioning.grafana.app` (Git Sync, with a `local` repository type) could have Grafana
pull the resources directory itself instead of having gcx push it. It is a reasonable successor to evaluate once
its toggles are all GA. Today `provisioningExport` and `provisioning.performance` are still experimental, and the
request was for the CLI.

The emitted resources therefore carry three `apiVersion`s, all the latest stable:
`dashboard.grafana.app/v2`, `folder.grafana.app/v1` and `preferences.grafana.app/v1`. A test in `generate.py`
asserts that set, so an SDK bump that silently moves a resource to a different version fails the build.

## Push path — planned

**One script, two callers.** `push.sh` (a `src/build/resources` fragment, wrapped into `image/` by the build like
the others) is the only code that talks to Grafana's API. `bootstrap.sh` runs it at container start; `deploy.sh`
runs the very same script in the running container after copying fresh resources. There is no second
implementation to drift.

### push.sh

1. `POST /api/admin/provisioning/datasources/reload`. This is harmless at start and picks up a changed
   datasource after a `deploy.sh`.
2. `gcx resources push folders dashboards preferences -p /asystem/mnt/dashboards/folders -p /asystem/mnt/dashboards/preferences
   -p /asystem/mnt/dashboards/generated -p /asystem/mnt/dashboards/snippets -p /asystem/mnt/dashboards/custom --omit-manager-fields --on-error abort`.
   Folders, every dashboard (snippets as `snippets-<uid>` in the Snippets folder), and the org home dashboard all
   go out in one call, and nothing is set by `curl`. Naming each directory avoids relying on gcx recursing.
   `--omit-manager-fields` keeps dashboards saveable in the UI (*D7*).
3. `gcx resources delete dashboards/<uid>` for every uid that `gcx resources get dashboards` returns but that
   no file under `/asystem/mnt/dashboards/{generated,snippets,custom}` declares. It does nothing after a fresh start, and removes a
   dashboard after a `deploy.sh` that dropped one.
4. Print `/api/admin/stats`.

Every step is idempotent, so running it twice, or after a partial failure, converges.

**Credentials collision.** `gcx` reads `GRAFANA_TOKEN` as a *service account token*; this module's
`GRAFANA_TOKEN` is the admin *password*. `push.sh` invokes gcx as
`env -u GRAFANA_TOKEN GRAFANA_SERVER="http://${GRAFANA_SERVICE}:${GRAFANA_HTTP_PORT}" GRAFANA_ORG_ID=1
GRAFANA_USER="${GRAFANA_USER}" GRAFANA_PASSWORD="${GRAFANA_TOKEN}" gcx …` — in one place. Renaming the module var
would touch every consumer of `GRAFANA_TOKEN`; a service account would need creating on every ephemeral start.

### bootstrap.sh

The fragment becomes the single line `"${ASYSTEM_HOME}/push.sh"`. The wrapper `write_container_bootstrap`
generates already waits for `checkalive.sh` before and `checkexecuting.sh` after. The org, user, datasource and
four-folder `curl` blocks are deleted.

### deploy.sh

Follows the shape of `homeassistant`'s and `nginx`'s: resolve the host from `.hosts`, then

```bash
#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"

rsync -av --delete "${ROOT_DIR}/src/main/resources/data/provisioning/" "root@${HOST}:${HOME}/provisioning/"
rsync -av --delete "${ROOT_DIR}/src/main/resources/data/dashboards/" "root@${HOST}:${HOME}/dashboards/"
ssh "root@${HOST}" "docker exec $(basename "${ROOT_DIR}") /asystem/etc/push.sh"
```

`fab deploy` runs it after `fab generate`. It needs no local Go, Homebrew, gcx or credentials: the binary, the
script and the env are the running container's. `--delete` keeps the host copy an exact mirror, which is what
makes step 3 of `push.sh` correct. A change to `push.sh` itself, the Dockerfile or the compose file still needs
`fab release`; `deploy.sh` is for catalogue changes, which are almost all of them. Shellchecked.

### install_pre.sh

A release copies the previous version's home into the new one and then copies `data/` on top **without deleting**
(`install.sh`, the `cp -rfpa` of the old home followed by `cp -rfpv data/*`). Without a fix, a dashboard removed
from the repo would survive every release and `push.sh` would push it back. `install.sh` already runs a module's
`./install_pre.sh` after that copy and before the service starts. Grafana's `install_pre.sh`:

- mirrors the packaged `data/dashboards/` and `data/provisioning/` into `${SERVICE_HOME}` with delete, so the host
  copy is exact, as `deploy.sh`'s `rsync --delete` makes it;
- removes the dead `config/` directory left by grizzly (*Deleted*).

It is listed in `src/resources.txt` if it needs substitution, and shellchecked (*D15*).

### Health checks

- `checkalive` unchanged.
- `checkexecuting`: `orgs == 1`, and `dashboards >= $(ls /asystem/mnt/dashboards/{generated,snippets,custom}/*.yaml | wc -l)`.
- `checkhealthy` unchanged (the `.proxy` URL).

### Compose and env

Remove `GRAFANA_URL_PRIVATE`, `GRAFANA_USER_PRIVATE`, `GRAFANA_TOKEN_PRIVATE` (`.env_all`, `.env_all_key`,
compose), and the `${SERVICE_DATA_DIR}/config/settings.yaml` volume line (*Deleted*); keep the
`${SERVICE_DATA_DIR}:/asystem/mnt` volume, which now carries `provisioning/` and `resources/`; add the `GF_*`
overrides and the Postgres connection vars.

## Deleted — planned

The dead set after the refactor, found by listing every tracked file in the module and searching the repo for
`grizzly`, `grr`, `grafonnet`, `jsonnet`, `GRAFANA_*_PRIVATE`, `admin_private`, `InfluxDB_V2`, `Private_*`,
`private-home-default`, `Public Portal`/`Private Portal` and `orgId=2`. Deletions use plain `rm`, and changes stay
unstaged.

### Whole files and directories — 102 tracked files

| Path | Files | Why it is dead |
|---|---:|---|
| `src/build/resources/dashboards/default/` | 2 | `asystem-library.jsonnet` and the 547-line `header_metadata.jsonnet`, replaced by the header in `generate.py` |
| `src/build/resources/dashboards/private/` | 17 | every jsonnet template (11 `graph_*`, `dashboard_home`, `dashboard_homes`, `snippet_conditions`), plus `generated/` holding 6 generated `graph_*` and `dashboard_graphs.jsonnet` |
| `src/build/resources/dashboards/public/` | 1 | the empty public `dashboard_graphs.jsonnet` |
| `src/main/resources/image/dashboards/` | 50 | build output: 48 form-factor specialisations under `private/{desktop,tablet,mobile}/`, plus 2 copies under `default/` |
| `src/main/resources/image/libraries/` | 30 | the whole directory, not just `grafonnet-lib/` under it. Grafonnet was its only content, and `deploy.sh`'s `LIBRARIES_HOME` its only other reader |
| `src/main/resources/image/config/` | 1 | the vendored `grafana.ini`, its only content (*Config*) |
| `src/main/resources/data/config/` | 1 | the whole directory. Its only content is `settings.yaml`, a 2-byte placeholder that existed only as the bind-mount target for grizzly's `/root/.config/grizzly/settings.yaml`. gcx is configured by env vars in `push.sh`, so nothing replaces it |
| `generate.sh` | — | **kept but emptied of its old body.** The grizzly and grafonnet `pull_repo`s and the grafonnet copy into `image/libraries` go, and the gcx `pull_repo` replaces them (*Dependencies*) |

`src/build/resources/dashboards/` is then empty and removed. Nothing in the new design lives there: hand-authored
dashboards are in `data/dashboards/` (*Catalogue*).

### Dead code inside kept files

| File | Dead | Kept |
|---|---|---|
| `src/build/python/grafana/generate.py` | everything after the two `write_container_*` calls: `DIR_DASHBOARD_ROOT`, `DIR_DASHBOARD_TEMPLATE_ROOT`, the `PREFIX*` constants, the Flux-in-jsonnet graph writer, the `dashboard_graphs.jsonnet` writer, and the `//AS*` form-factor specialiser loop | `load_bootstrap_entities()` and the xlsx filter (the filter feeds the new xlsx section), `write_container_healthchecks()`, `write_container_bootstrap()` |
| `src/build/resources/bootstrap.sh` | all of it: the `grr config` contexts, the org-2 create, the `admin_private` user, the `curl` datasource, the four `Private_*` folders, `grr apply`, and the preferences `PATCH` | replaced by the one-line call to `push.sh` |
| `src/build/resources/checkexecuting.sh` | `orgs -eq 2`, and the dashboard count over `public`/`private` `graph_*.jsonnet` | rewritten (*Health checks*) |
| `deploy.sh` | all of it: the Go 1.16 Homebrew `GOROOT`s, `GOPATH`, the `GRAFANA_URL_PRIVATE` export, `LIBRARIES_HOME`/`DASHBOARDS_HOME`, `make dev` in grizzly, and the image `bootstrap.sh` run from the laptop | rewritten (*deploy.sh*) |
| `Dockerfile` | the `image_base` stage's `ASYSTEM_GRIZZLY_VERSION` and `grr` download, the `mkdir /root/.config/grizzly`, and `cp config/grafana.ini /etc/grafana` | rewritten (*Image*) |
| `docker-compose.yml` | `GRAFANA_URL_PRIVATE`, `GRAFANA_USER_PRIVATE`, `GRAFANA_TOKEN_PRIVATE`, and the `config/settings.yaml:/root/.config/grizzly/settings.yaml` volume | `GRAFANA_URL`, `GRAFANA_USER`, `GRAFANA_TOKEN` (checks and `push.sh`), and the `${SERVICE_DATA_DIR}:/asystem/mnt` volume |
| `.env_all` | `GRAFANA_USER_PRIVATE`, `GRAFANA_URL_PRIVATE` | the rest |
| `.env_all_key` | `GRAFANA_TOKEN_PRIVATE` | `GRAFANA_TOKEN` |
| `run_deps.txt` | `vernemq` | `influxdb3`, plus `postgres` added |
| `.env_fab` (repo root) | `GRIZZLY_VERSION` and its `# NOTES:` line | — |

### Regenerated, not hand-deleted

`src/main/resources/image/{bootstrap,checkalive,checkexecuting,checkhealthy}.sh`, `.env`, and `docker_deps.sh`
are build output. They lose their dead content on the next `fab generate` / `docker_deps.sh` run. Read the diff
rather than editing them.

### Outside the repo

| Where | Dead | How |
|---|---|---|
| `.deps/grafana/{grizzly,grafonnet-lib}` | the two cloned repos | `rm -rf` by hand. They are untracked, and `pull_repo` never removes a repo it no longer pulls |
| `macmini-max:/home/asystem/grafana/latest/config/settings.yaml` | the grizzly placeholder, present today | check whether `install.sh` mirrors `data/` with delete. If not, `rm -rf` the `config/` directory on the host after the first release |
| Grafana's database | org 2, `admin_private`, the `Private_*` folders, the form-factor dashboards | nothing to do: the database is not persisted, so the first container on the new image never creates them |
| the `grafana` image on `macmini-max` | old images with `grr` baked in | removed by the normal image pruning |
| `ggear/grafonnet-lib` on GitHub | the fork | no longer referenced. Archiving it is the user's call |

### Stale documentation elsewhere

| File | Stale | Change |
|---|---|---|
| `src/all/supervisor/src/build/resources/plans/backup.md` line 1817, and line 1849 | lists `grafana` on host `may` as needing a backup of `grafana.db`, because "dashboards come from jsonnet" | grafana is on `max`, the database is ephemeral by design, and dashboards come from `data/dashboards/`, which is in the repo. Grafana drops out of the backup candidates |

**Not dead, despite matching the search:**

- nginx's `grafana.proxy.janeandgraham.com` proxy and `GRAFANA_IP` (`src/meg/nginx/src/main/resources/data/nginx.conf`);
- homeassistant's `switch.service_grafana` (supervisor's service entity, in `customise.yaml` and `ui-lovelace/diagnostics.yaml`);
- supervisor's `service_grafana` broker and schema artifacts;
- udmutilities' DHCP alias;
- `docker_deps_base.txt` (`bash`, `curl`, `jq` are still used by `push.sh` and the checks);
- `src/build/python/grafana/__init__.py`;
- `.env_{exec,prod,test}`, whose `GRAFANA_DOMAIN`/`GRAFANA_DOMAIN_URL` now feed the `GF_SERVER_*` overrides;
- `src/resources.txt`.

## Module CLAUDE.md — planned

Only what the code cannot say:

- Every dashboard is native v2 YAML in `data/dashboards/`, and the directory is its provenance: `generated/`
  (banner, from the `# Build dashboard [<uid>]` section of `generate.py`), `snippets/<uid>.yaml`
  (hand-authored panels for generated `<uid>`), `custom/` (hand-authored, no generated partner).
- Hand-authored files are edited in the Grafana UI and pulled back with gcx; `fab generate` rewrites them in
  place through the same writer as generated files, so the two always read alike.
- Promote to a common element at the top of `generate.py` on the second use. Every snippet carries a `description` saying why it is hand-written.
- UI edits are throwaway: the database is ephemeral and the next push overwrites them.
- Never edit `data/dashboards/{generated,folders,preferences}/` or `data/provisioning/`; they carry the banner and
  are rewritten by `fab generate` (*D24*).
- Datasource uids are the contract between provisioning and panels, owned by `generate.py`.
- `push.sh` is the only API client, and both bootstrap and deploy use it.
- The `GRAFANA_TOKEN`/gcx credential collision.
- The xlsx vocabulary (`Continuous`/`Discrete`, `graph_break`).
- A new unit from a producer needs a row in `UNITS` in `generate.py`.

## Phases

**Build everything, release once (*D21*).** Phases 1–6 are done in the working tree and verified locally. The live
instance goes from the legacy dashboards to the complete new set in a single `fab release`, so there is never a
window with dashboards missing.

1. **Contract** (`_`): *C1* `document.yaml` + `load_schema_artifact`; *C2* `panel()` and `Dataquery` per dialect;
   unit-table test. Regenerate every module with a database schema. Only the new `document.yaml` files may differ;
   every other artifact must be byte-identical. This touches other modules' generated artifacts only, so it can
   ship with any later release of those modules.
2. **Runtime** (`grafana`): deps, Dockerfile, compose overrides, provisioning, `install_pre.sh`, `push.sh`,
   `bootstrap.sh`, `deploy.sh`, checks, default org only. Prove locally with `fab execute`:
   - both push callers work;
   - the YAML writer round-trips: push the normalised output, pull it back with gcx, normalise again, and the
     result is byte-identical;
   - gcx pushes from all five `-p` directories;
   - a push over a UI-edited dashboard behaves as *D22* expects.
3. **Generated, xlsx**: `generate.py` common elements and the xlsx section, with the xlsx five and
   `snippets/conditions.yaml`.
4. **Finance**: Currency, Interest, Equity on Postgres.
5. **Infrastructure**: Servers, Containers, Network, Internet on supervisor/network.
6. **Delete** everything in *Deleted*, write the module `CLAUDE.md`, and the systest (*D18*).
7. **Release once**: `fab release`, the production query probe (*D18*), a visual check of every dashboard at
   `https://grafana.proxy.janeandgraham.com`, then a `deploy.sh` round trip (add a panel, deploy, remove it, deploy).
   Then collapse this file to a record.

**Seeing real data before release.** The local run deps (`influxdb3`, `postgres`) start empty, so phases 3–5 would
otherwise only be checked for shape. During development, `.env_exec` points the two datasources at the production
`INFLUXDB3_SERVICE_PROD` and `POSTGRES_SERVICE_PROD`, which are only read, so every panel can be checked against
real data under `fab execute`. Confirm in phase 2 that `_write_env` lets a module's `.env_exec` override run-dep
connection vars. If it does not, the provisioning file takes a `GRAFANA_DATASOURCE_TARGET` switch instead.
`.env_test` stays on the empty local run deps, so the systest is hermetic.

## Gaps and decisions

**D1. One layout, not three — decided: desktop shape.** One dashboard per subject at the desktop sizes, relying
on the v2 grid's mobile collapse. Bookmarks to `-desktop`/`-tablet`/`-mobile` uids and `orgId=2` URLs (including
the one in the request) will 404, so check kiosk devices.

**D2. Equity holdings have no source — decided: drop.** The eight `holdings` panels are removed. Holdings
return only if wrangle later declares a holdings relation, which is a wrangle feature and out of scope here.

**D3. Database credentials — decided: reuse the owners.** Postgres is read as `${POSTGRES_USER_WRANGLE}` and
InfluxDB 3 with `${INFLUXDB3_TOKEN_HOME}`, so no cross-module change is needed. Accepted consequence: Grafana
holds write-capable credentials to both stores. Panel SQL is generated and read-only, and only admins can edit,
but a hand-written snippet could in principle modify data. Every snippet's `rawSql` is reviewed in the generate diff
for that reason.

**D4. The header's error stats have no source — decided: substitute.** The four slots are redrawn from the
producing service's `supervisor/service` row (status, health, restarts, backup), and Time Since Poll from the
same row. See *Header row*.

**D5. Up-time is not persisted — decided: substitute.** `supervisor/host` declares `up_time` with
`persist: false`, so "Servers Min Uptime" becomes **Servers Min Availability**: the minimum across hosts of
`avg(status) * 100` over the range, in the same slot with a `HIGHER_BETTER` palette. Supervisor needs no change.

**D6. Currency unit — decided: keep `currencyUSD`.** It renders exactly as today. The unit table maps `$` to
`currencyUSD`, and the pair in each title carries the currency.

**D7. UI edits — decided: editable, throwaway.** Dashboards are pushed `editable: true`, so they can be tweaked in
the UI to try things out. Those edits are lost on the next release, or on the next `deploy.sh` that touches that
dashboard. A change worth keeping is copied into the dashboard's YAML by hand. Two consequences:

- `push.sh` pushes with `--omit-manager-fields`. Without it, gcx stamps each resource as managed by gcx, and Grafana
  then shows the dashboard as externally managed and blocks saving it in the UI.
- A UI save creates a new resource version that the next push overwrites without warning. That is the agreed
  behaviour, and the module `CLAUDE.md` says so.

**D8. Infrastructure panels whose producers are archived — decided: substitute.** The rule is the same as for the
header: every slot stays, and each panel that lost its source is redrawn from the nearest measure that exists, with
its title changed to say what it now shows. The full map is under *Substitutions*.

**D9. Foundation SDK maturity.** The Python SDK is `0.0.x` and tracks Grafana `main`; a bump can change builder
signatures and emitted output. Pin exactly, and gate any bump of `grafana-foundation-sdk` or `GRAFANA_VERSION` on a
byte-identical regeneration of every dashboard, or a reviewed diff.

**D10. SDK lacks InfluxDB and Postgres query builders.** 0.0.20 ships Prometheus, Loki, Tempo, Elasticsearch,
CloudWatch and others, not these two. Covered by *C2*'s two small `Dataquery` subclasses; if the SDK adds them,
switch and expect a byte-identical regeneration.

**D11. Flight SQL macro coverage.** The InfluxDB datasource in SQL mode is expected to support `$__timeFilter`,
`$__dateBin`, `$__dateBinAlias`, `$__interval`; confirm against 13.2.3 in phase 3 before generating the rest. If
`$__dateBin` is missing, `date_bin(INTERVAL '$__interval', time)` is the fallback, inside InfluxDB's `panel()`
only.

**D12. `gcx` against OSS with basic auth.** gcx's core resource commands are documented for any Grafana 12+, with
basic auth supported for self-hosted. Prove `resources push` of `dashboard.grafana.app/v2`, `folder.grafana.app/v1` and
`preferences.grafana.app/v1` against 13.2.3 in phase 2 before building on it. If it falls short, only `push.sh`
changes, to the same resources sent with `curl` to `/apis/<group>/<version>/namespaces/default/<resource>`. The
catalogue, the resources and both callers stay as they are.

**D13. Datasources — decided: file provisioning.** The app-platform datasource API is only `v0alpha1` in
13.2.3, so datasources stay stable YAML provisioning rendered by `generate.py`, and `push.sh`
reloads them. Move to `datasource.grafana.app` once it reaches a stable version. That change touches only
`push.sh` and the provisioning writer.

**D14. Dashboard sources — decided: one native tree, grouped by provenance.** Every dashboard is native v2 YAML
in `data/dashboards/{generated,snippets,custom}/`, normalised by one writer so generated and hand-authored files
are directly comparable, and generated ones serve as examples and fork points. Python exists only as the single `generate.py`,
with one section per `generated/` dashboard. No invented format. See *Catalogue*.

**D15. Stale files on release — decided: `install_pre.sh` mirror.** See *install_pre.sh*. The release path and
`deploy.sh` both leave the host's `dashboards/` and `provisioning/` as an exact copy of the repo, so `push.sh`'s
delete step is always correct.

**D16. Wall displays — decided: longer sessions.** Anonymous access is off, so displays log in once. Session
lifetimes rise to 90 days inactive and 365 days maximum via `GF_AUTH_LOGIN_*` overrides (*Config*).

**D17. Snippets in the UI — decided: a visible `Snippets` folder.** Snippet dashboards (`snippets-<uid>`) live
in a plainly named folder that is left out of the Home dashboard list and the nav links. No permissions code.

**D18. Tests — decided: systest plus a query probe.**
- `fab systest` brings up grafana with its `influxdb3` and `postgres` run deps and asserts that `push.sh` lands
  every dashboard, both folders and the preferences. A `src/test/python/system/system_test.py`, as in other
  modules.
- A production probe, run by hand like `fab schema`, executes every panel query through `/api/ds/query` and
  reports panels returning empty frames. This replaces the per-phase manual query check.

**D19. Home Assistant schema freshness — decided: fail with the fix.** Grafana's generate fails on an xlsx entity
missing from homeassistant's committed `document.yaml`, naming the entity and `fab generate` in
`src/meg/homeassistant`. The order between the two modules is explicit, and nothing renders silently empty.

**D20. Alerting — decided: out of scope.** Dashboards only. Supervisor and Home Assistant already own health
alerting.

**D21. Cutover — decided: build everything, release once.** See *Phases*. Phases 1–6 land in the working tree and
are verified locally against production data. Production switches from legacy to complete in one release.

**D22. Push over UI edits — decided: verify, then overwrite.** A UI save bumps the server's resource version, and a
gcx push of a file without it may be rejected as a conflict. Phase 2 proves gcx's behaviour on a UI-edited
dashboard. If it conflicts, `push.sh` deletes that dashboard and re-pushes it, so the repo always wins, consistent
with *D7*.

**D23. Postgres TLS — decided: `sslmode: disable`.** This matches wrangle's in-LAN connection. It is set explicitly
in the provisioning file, because Grafana's Postgres datasource otherwise defaults to `require`.

**D24. Never-edit rules — decided: module `CLAUDE.md` only.** The banner marks every generated file, and the module
`CLAUDE.md` names `data/dashboards/{generated,folders,preferences}/` and `data/provisioning/`. The root
`CLAUDE.md` stays generic.
