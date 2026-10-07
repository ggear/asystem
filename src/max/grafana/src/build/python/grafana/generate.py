from collections import namedtuple
from dataclasses import dataclass, replace

import yaml
from grafana_foundation_sdk.builders import (
    common,
    dashboardv2,
    folderv1,
    preferencesv1alpha1,
    timeseries,
)
from grafana_foundation_sdk.builders import stat as stats
from grafana_foundation_sdk.builders import statetimeline as statetimelines
from grafana_foundation_sdk.builders import text as texts
from grafana_foundation_sdk.cog.encoder import JSONEncoder
from grafana_foundation_sdk.models import common as kinds
from grafana_foundation_sdk.models import dashboardv2 as models
from grafana_foundation_sdk.models import text as textkinds

from asystem import *
from asystem.schema.document import BETTER_HIGHER, BETTER_LOWER
from asystem.schema.panel import Query, aggregated, entitled, selected, subjected
from asystem.schema.query import duration, expanded


def main():
    write_container_bootstrap()
    write_container_healthchecks()

    # Build shared sources
    metadata_df = load_bootstrap_entities()
    graphed_metadata_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"].str.len() > 0) &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["grafana_display_type"].str.len() > 0) &
        (metadata_df["entity_group"].str.len() > 0)
        ]
    home_span = 7 * DAY
    server_hosts = Relation("supervisor", "supervisor/host")
    host_names = server_hosts.entities(("all",))
    internet_targets = Relation("network", "internet/target")
    hass_temperatures = Relation("homeassistant", "sensor__temperature")
    rack_group = "Rack"
    rack_ids = [unique_id for unique_id, grouped in zip(metadata_df["unique_id"], metadata_df["grafana_group"], strict=True)
                if rack_group in [group.strip() for group in str(grouped).split(",")]]
    if not rack_ids:
        raise failed(f"no entity has [grafana_group] [{rack_group}], tag the rack temperature sensors in the entity metadata")
    rack_temperatures = friendly_names(metadata_df, rack_ids)

    # Build Home dashboard [weather]
    perth_midnight = "TIMESTAMP '1969-12-31T16:00:00'"
    forecast_bounds = {
        "bom_darlington_temp_max_1": "Max",
        "bom_darlington_temp_min_1": "Min",
    }
    forecast_sql = """
WITH forecast AS (
    SELECT
        date_bin(INTERVAL '1 day', time, $midnight) + INTERVAL '1 day' AS day,
        $bound AS bound,
        last_value(value ORDER BY time) AS value
    FROM $table
    WHERE
        $forecast
    GROUP BY 1, 2
), observed AS (
    SELECT
        date_bin(INTERVAL '1 day', time, $midnight) AS day,
        max(value) AS high,
        min(value) AS low
    FROM $table
    WHERE
        $observed
        AND time < date_bin(INTERVAL '1 day', $__timeTo(), $midnight)
    GROUP BY 1
)
SELECT day AS time, 'Forecast ' || bound AS metric, value FROM forecast
UNION ALL
SELECT day AS time, 'Observed Max' AS metric, high AS value FROM observed
UNION ALL
SELECT day AS time, 'Observed Min' AS metric, low AS value FROM observed
UNION ALL
SELECT observed.day AS time, forecast.bound || ' Error' AS metric,
    CASE forecast.bound WHEN 'Max' THEN observed.high ELSE observed.low END - forecast.value AS value
FROM observed JOIN forecast ON observed.day = forecast.day
ORDER BY time
"""
    forecast_series = hass_temperatures.sql(
        forecast_sql, "°C", "BOM's next-day forecast against the observed roof temperature per Perth day, with the error as bars",
        midnight=perth_midnight,
        bound=entitled("NULL", hass_temperatures.subject, list(forecast_bounds), forecast_bounds),
        forecast=hass_temperatures.scope("value", list(forecast_bounds)),
        observed=hass_temperatures.scope("value", ["compensation_sensor_roof_temperature"]),
    )
    forecast_rows = [
        [
            steps("Forecast", forecast_series)
            .override("/Max/", {"color": {"mode": "fixed", "fixedColor": "orange"}})
            .override("/Min/", {"color": {"mode": "fixed", "fixedColor": "blue"}})
            .override("/Forecast/", {"custom.lineStyle": {"fill": "dash", "dash": [10, 10]}})
            .override("/Error/", {"custom.drawStyle": "bars", "custom.fillOpacity": 50, "custom.barWidthFactor": 0.15, "custom.axisPlacement": "right"})
            .override("/Max Error/", {"custom.barAlignment": -1})
            .override("/Min Error/", {"custom.barAlignment": 1}),
        ],
    ]
    calm_gust_kmh = 5
    gust_speed, gust_direction = "roof_wind_gust_speed", "roof_wind_gust_direction"
    hass_sensors = Relation("homeassistant", "sensor")
    gusts_sql = """
WITH events AS (
    SELECT
        time,
        CASE $entity WHEN $speed THEN value END AS speed,
        CASE $entity WHEN $direction THEN value END AS direction
    FROM $table
    WHERE
        $gusts
), runs AS (
    SELECT
        time,
        speed,
        direction,
        count(speed) OVER (ORDER BY time, speed NULLS LAST ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS run
    FROM events
), held AS (
    SELECT
        time,
        direction,
        first_value(speed) OVER (PARTITION BY run ORDER BY time, speed NULLS LAST) AS speed
    FROM runs
)
SELECT
    $__dateBin(time) AS time,
    'Gust Direction' AS metric,
    $bearing AS value
FROM held
WHERE
    direction IS NOT NULL
    AND speed > $calm
GROUP BY 1
ORDER BY time
"""
    gust_direction_panel = compass_scale(points("Wind", hass_sensors.sql(
        gusts_sql, "", f"Mean gust direction per bucket, from gusts above {calm_gust_kmh} km/h only, each paired with the latest gust speed at or before it, since calm reads as north",
        speed=f"'{gust_speed}'",
        direction=f"'{gust_direction}'",
        gusts=hass_sensors.scope("value", [gust_speed, gust_direction]),
        bearing=aggregated("direction", ("compass",)),
        calm=str(calm_gust_kmh),
    )))
    metadata_dashboard("weather", home_span, graphed_metadata_df, placed={
        # Orders interleave with metadata index, above roof temperature (1001) and below wind (1300 to 1306)
        "Forecast": (1000.5, forecast_rows),
        "Gust Direction": (1306.5, [[gust_direction_panel]]),
    })

    # Build Home dashboard [conditions]
    metadata_dashboard("conditions", home_span, graphed_metadata_df)

    # Build Home dashboard [electricity]
    metadata_dashboard("electricity", home_span, graphed_metadata_df)

    # Build Finance dashboard [currency]
    typical_rates = {
        "AUD/GBP": 1.9,
        "AUD/USD": 1.4,
        "AUD/SGD": 1.1,
    }
    typical_spread = 0.1
    display_names = {code: "/".join(reversed(code.split("/"))) for code in typical_rates}
    currency_rates = Relation("wrangle", "currency/rate")
    header_panels = header([(currency_rates, None)], "wrangle", TRADING_SPAN)
    dashboard("currency", YEAR_WINDOW, header_panels, [
        [
            *(stat(display_names[code], currency_rates.query(["snapshot"], [code], ("invert",), display_names))
              .thresholds(higher_better(round(typical * (1 - typical_spread), 3), round(typical * (1 + typical_spread), 3)))
              for code, typical in typical_rates.items()),
            *(stat(f"{display_names[code]} Day", currency_rates.query(["delta@1d"], [code], ("invert",), display_names)).thresholds(CHANGE_LADDER) for code in typical_rates),
        ],
        [series("CCY/AUD Range Deltas", currency_rates.query(["snapshot"], None, ("invert", "baseline"), display_names))],
        [series(f"{display_names[code]} End of Days", currency_rates.query(["snapshot"], [code], ("invert",), display_names)) for code in typical_rates],
    ])

    # Build Finance dashboard [interest]
    interest_window = TimeRange("now-25y", "15m", LONG_RANGES)
    interest_span = 45 * DAY
    interest_series = ["Net", "Bank", "Inflation"]
    interest_means = Relation("wrangle", "interest/rate")
    header_panels = header([(interest_means, None)], "wrangle", interest_span)
    dashboard("interest", interest_window, header_panels, [
        [
            *(stat(f"{entity} Month", interest_means.query(["mean@1mo"], [entity])) for entity in interest_series),
            *(stat(f"{entity} 10 Year", interest_means.query(["mean@10y"], [entity])) for entity in interest_series),
        ],
        [series("Interest Rates Monthly Means", interest_means.query(["mean@1mo"]))],
        [series("Interest Rates 10 Year Means", interest_means.query(["mean@10y"]))],
        [series("Net Rate N Year Means", interest_means.query(["mean"], ["Net"]))],
    ])

    # Build Finance dashboard [equity]
    portfolio_tickers = ["CLNE", "ERTH", "GOLD", "IAF", "MCK", "MUK", "MUS", "VAE", "VAS", "VDHG", "VHY"]
    fund_tickers = ["MCK", "MUK", "MUS"]
    equity_quotes = Relation("wrangle", "equity/ticker")
    change_sql = """
SELECT
    time,
    '$label' AS metric,
    avg(value) AS value
FROM (
    SELECT
        time,
        $entity,
        (value / first_value(value) OVER (PARTITION BY $entity ORDER BY time) - 1) * 100 AS value
    FROM (
        SELECT
            $__timeGroupAlias(time, $__interval),
            $entity,
            avg(value) AS value
        FROM $table
        WHERE
            $tickers
        GROUP BY 1, 2
    ) AS tickers
) AS changes
GROUP BY 1, 2
ORDER BY time
"""
    performance_series = {
        label: equity_quotes.sql(change_sql, "%", "Equal-weight mean of each ticker's change since the start of the window", label=label, tickers=equity_quotes.scope("price-close-spot", tickers))
        for label, tickers in (("Portfolio", portfolio_tickers), ("ASX 200", ["AXJO"]))
    }
    header_panels = header([(equity_quotes, None)], "wrangle", TRADING_SPAN)
    dashboard("equity", YEAR_WINDOW, header_panels, [
        [
            *(stat(label, change).thresholds(CHANGE_LADDER) for label, change in performance_series.items()),
            *(stat(ticker, equity_quotes.query(["price-close-spot"], [ticker], ("baseline",))).thresholds(CHANGE_LADDER) for ticker in fund_tickers + ["VAS"]),
        ],
        [series("Portfolio Performance", list(performance_series.values()))],
        [series("Equities Performance", equity_quotes.query(["price-close-spot"], portfolio_tickers, ("baseline",)))],
        [series("Fund Performance", equity_quotes.query(["price-close-spot", "price-close-base"], fund_tickers, ("baseline",)))],
    ])

    # Build Systems dashboard [containers]
    containers_window = TimeRange("now-1h", "10s", SHORT_RANGES)

    def state_mappings(below, at):
        return [
            models.RangeMap(options=models.Dashboardv2RangeMapOptions(from_val=None, to=0.999, result=models.ValueMappingResult(text=below, color=RED))),
            models.RangeMap(options=models.Dashboardv2RangeMapOptions(from_val=1, to=None, result=models.ValueMappingResult(text=at, color=GREEN))),
        ]

    up_mappings = state_mappings("Down", "Up")
    healthy_mappings = state_mappings("Unhealthy", "Healthy")
    service_names = SUPERVISOR_SERVICES.entities()
    header_panels = header([(SUPERVISOR_SERVICES, service_names)], "supervisor", SUPERVISOR_SPAN)
    dashboard("containers", containers_window, header_panels, [
        [
            stat("Running", SUPERVISOR_SERVICES.query(["status"], service_names, ("sum",))),
            stat("Not Running", SUPERVISOR_SERVICES.query(["status"], service_names, ("complement", "sum"))).thresholds(lower_better(1, 1)),
            stat("Configured", SUPERVISOR_SERVICES.query(["configured_status"], service_names, ("sum",))),
            stat("Running Rate", SUPERVISOR_SERVICES.query(["status"], service_names, ("percent", "avg")), "mean").thresholds(higher_better(90, 99)),
            stat("Healthy Rate", SUPERVISOR_SERVICES.query(["health_status"], service_names, ("percent", "avg")), "mean").thresholds(higher_better(90, 99)),
            stat("Restarts", SUPERVISOR_SERVICES.query(["restart_count"], service_names, ("counter", "sum")), "delta").thresholds(lower_better(1, 5)),
        ],
        [series("Container CPU Usage", SUPERVISOR_SERVICES.query(["used_processor"], service_names))],
        [series("Container RAM Usage", SUPERVISOR_SERVICES.query(["used_memory"], service_names))],
        [series("Container Disk Usage", SUPERVISOR_SERVICES.query(["used_disk_rate"], service_names))],
        [series("Container Network Usage", SUPERVISOR_SERVICES.query(["used_network"], service_names))],
        [state("Container Running", SUPERVISOR_SERVICES.query(["status"], service_names), 16).mappings(up_mappings)],
        [state("Container Healthy", SUPERVISOR_SERVICES.query(["health_status"], service_names), 16).mappings(healthy_mappings)],
        [state("Container Backed Up", SUPERVISOR_SERVICES.query(["backup_status"], service_names), 16)],
    ])

    # Build Systems dashboard [servers]
    servers_window = TimeRange("now-2d", "10s", SHORT_RANGES)
    used_ladder = lower_better(70, 90)
    header_panels = header([(server_hosts, host_names)], "supervisor", SUPERVISOR_SPAN)
    dashboard("servers", servers_window, header_panels, [
        [
            stat("Availability", server_hosts.query(["status"], host_names, ("percent", "min")), "mean").thresholds(higher_better(90, 99)),
            stat("CPU Mean", server_hosts.query(["used_processor"], host_names, ("avg",)), "mean").thresholds(used_ladder),
            stat("RAM Mean", server_hosts.query(["used_memory"], host_names, ("avg",)), "mean").thresholds(used_ladder),
            stat("Temperature Mean", server_hosts.query(["temperature"], host_names, ("avg",)), "mean").thresholds(lower_better(70, 85)),
            stat("Home Volume Max", server_hosts.query(["used_home_space"], host_names, ("max",))),
            stat("Share Volume Max", server_hosts.query(["used_share_space"], host_names, ("max",))),
        ],
        [series("Server CPU Usage", server_hosts.query(["used_processor"], host_names))],
        [series("Server RAM Usage", server_hosts.query(["used_memory"], host_names))],
        [series("Server Swap Usage", server_hosts.query(["used_swap_space"], host_names))],
        [series("Server Volume Usage", server_hosts.query(["used_home_space", "used_share_space", "used_backup_space"], host_names))],
        [series("Server Disk Usage", server_hosts.query(["used_disk_time"], host_names))],
        [series("Server Network Usage", server_hosts.query(["used_network"], host_names))],
        [series("Server Temperature", [
            server_hosts.query(["temperature"], host_names),
            hass_temperatures.query(["value"], list(rack_temperatures), (), {unique_id: name.lower().replace(" ", "-") for unique_id, name in rack_temperatures.items()}, "°C"),
        ])],
        [series("Server Temperature Warning", server_hosts.query(["warn_temperature"], host_names))],
        [series("Server Fan Speed", server_hosts.query(["spin_fan_speed"], host_names))],
        [series("Server Memory Allocated", server_hosts.query(["allocated_memory"], host_names))],
        [series("Server Drive Life Used", server_hosts.query(["used_drive_life"], host_names))],
        [series("Server Drive Failures", server_hosts.query(["failed_drives"], host_names))],
        [series("Server Share Failures", server_hosts.query(["failed_shares"], host_names))],
        [series("Server Log Errors", server_hosts.query(["failed_log_messages"], host_names))],
        [series("Server Backup Stage Failures", server_hosts.query(["failed_backup_stages"], host_names))],
        [series("Server Backup Stage Halts", server_hosts.query(["halted_backup_stages"], host_names))],
        [series("Cluster Health", server_hosts.query(["cluster"], None, ("percent",)))],
    ])

    # Build Systems dashboard [network]
    access_points = Relation("network", "wireless/accesspoint")
    zigbee_devices = Relation("network", "zigbee/device")
    zigbee_experience = Relation("network", "zigbee/experience")
    network_diagnosis = Relation("network", "diagnosis/plugin")
    wired_switches = Relation("network", "ethernet/switch")
    powered_devices = Relation("network", "ethernet/powered")
    header_panels = header([(access_points, None)], "network")
    dashboard("network", HOURS_WINDOW, header_panels, [
        [
            stat("Gateway", internet_targets.query(["reachable"], ["gateway"], ("percent",)), "mean").thresholds(higher_better(95, 99.9)),
            stat("Wireless Clients", access_points.query(["clients"], None, ("sum",))),
            stat("Wireless Experience", access_points.query(["experience_pct"], None, ("min",))),
            stat("Wired Experience", wired_switches.query(["experience_pct"], None, ("min",))),
            stat("Zigbee Experience", zigbee_experience.query(["experience_pct"], ["router"])),
            stat("PoE Budget", wired_switches.query(["poe_pct"], None, ("max",))).thresholds(lower_better(80, 95)),
        ],
        [series("Network Utilisation", server_hosts.query(["used_network"], host_names))],
        [series("Network Device Experience", [wired_switches.query(["experience_pct"]), access_points.query(["experience_pct"])])],
        [series("Network Device Throughput", [wired_switches.query(["throughput_mbps"]), access_points.query(["throughput_mbps"])])],
        [series("Network Device Link Utilisation", [wired_switches.query(["network_pct"]), access_points.query(["network_pct"])])],
        [series("Network Device Processor", [wired_switches.query(["cpu_pct"]), access_points.query(["cpu_pct"])])],
        [series("Network Device Memory", [wired_switches.query(["memory_pct"]), access_points.query(["memory_pct"])])],
        [series("Network Device Power", [wired_switches.query(["poe_w"]), powered_devices.query(["power_w"])])],
        [series("Access Point Clients", access_points.query(["clients"]))],
        [series("Network Diagnosis", network_diagnosis.query(["score"]))],
        [series("Zigbee Experience", zigbee_experience.query(["experience_pct"]))],
        [series("Network Device Temperature", [hass_temperatures.query(["value"], list(rack_temperatures), (), rack_temperatures, "°C"), wired_switches.query(["temperature"])])],
        [state("Network Devices Up", [wired_switches.query(["up"]), access_points.query(["up"])], 5)],
        [state("Network Devices Restarted", [wired_switches.query(["restarted"], None, ("complement",)), access_points.query(["restarted"], None, ("complement",))], 5)],
        [state("Zigbee Devices Available", zigbee_devices.query(["available"]), 16)],
    ])

    # Build Systems dashboard [internet]
    public_targets = internet_targets.entities(("gateway",))
    dns_resolvers = Relation("network", "domain/resolver")
    certificate_endpoints = Relation("network", "certificate/endpoint")
    header_panels = header([(internet_targets, None)], "network")
    dashboard("internet", HOURS_WINDOW, header_panels, [
        [
            stat("Reachability", internet_targets.query(["reachable"], public_targets, ("percent", "avg")), "mean").thresholds(higher_better(95, 99.9)),
            stat("Resolution", dns_resolvers.query(["ok"], None, ("percent", "avg")), "mean").thresholds(higher_better(95, 99.9)),
            stat("Certificate", certificate_endpoints.query(["expiry_days"], None, ("min",))),
            stat("Latency Mean", internet_targets.query(["rtt_ms"], public_targets, ("avg",)), "mean").thresholds(lower_better(50, 100)),
            stat("Latency Max", internet_targets.query(["rtt_ms"], public_targets, ("peak", "max")), "max"),
            stat("Loss Max", internet_targets.query(["loss_pct"], public_targets, ("peak", "max")), "max"),
        ],
        [series("Internet Latency", internet_targets.query(["rtt_ms"]))],
        [series("Internet Jitter", internet_targets.query(["jitter_ms"]))],
        [series("Internet Loss", internet_targets.query(["loss_pct"]))],
        [series("Domain Resolution", dns_resolvers.query(["latency_ms"]))],
        [state("Certificate Verified", certificate_endpoints.query(["verified"]), 4)],
    ])

    # Write generated dashboards
    for generated_path in glob.glob(join(DIR_GENERATED, "*.yaml")):
        with open(generated_path) as generated_file:
            if BANNER not in generated_file.read():
                raise failed(f"file [{generated_path}] lacks the build banner, a hand-authored dashboard belongs in [custom]")
    folder_of = {dashboard_uid: folder for folder, declared in FOLDERS.items() for dashboard_uid in declared.dashboards}
    ordered = [dashboard_uid for dashboard_uid in TITLES if dashboard_uid in DASHBOARDS]

    def navigation(current):
        sections = []
        for folder, declared in FOLDERS.items():
            label = f'<span style="color:{SECTION_COLOUR}">**{declared.title.upper()}**</span>'
            links = [f"**{TITLES[uid]}**" if uid == current else f"[{TITLES[uid]}](/d/{uid}?${{__url_time_range}})"
                     for uid in ordered if folder_of[uid] == folder]
            sections.append(" · ".join([label] + links))
        return " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(sections)

    shutil.rmtree(DIR_GENERATED, ignore_errors=True)
    for dashboard_uid in ordered:
        dashboard_resource = DASHBOARDS[dashboard_uid]
        dashboard_resource["metadata"]["annotations"] = {FOLDER: folder_of[dashboard_uid]}
        dashboard_resource["spec"]["tags"] = [folder_of[dashboard_uid], DASHBOARD_TAG]
        elements = dashboard_resource["spec"]["elements"]
        identifier = max(element["spec"]["id"] for element in elements.values()) + 1
        elements[NAVIGATION_ELEMENT] = encoded(dashboardv2.Panel().id(identifier).title("").transparent(True).data(dashboardv2.QueryGroup())
                                               .visualization(texts.VisualizationV2().mode(textkinds.TextMode.MARKDOWN).content(navigation(dashboard_uid))).build())
        items = dashboard_resource["spec"]["layout"]["spec"]["items"]
        for item in items:
            item["spec"]["y"] += NAVIGATION_HEIGHT
        items.insert(0, encoded(dashboardv2.grid_item(NAVIGATION_ELEMENT).x(0).y(0).width(GRID_WIDTH).height(NAVIGATION_HEIGHT).build()))
        write(join(DIR_GENERATED, dashboard_uid + ".yaml"), dashboard_resource)

    # Normalise custom dashboards
    collisions = sorted({basename(custom)[:-5] for custom in glob.glob(join(DIR_CUSTOM, "*.yaml"))} & set(DASHBOARDS))
    if collisions:
        raise failed(f"custom dashboards [{','.join(collisions)}] collide with generated dashboards")
    for custom_path in sorted(glob.glob(join(DIR_CUSTOM, "*.yaml"))):
        write(custom_path, normalised(sourced(custom_path), basename(custom_path)[:-5]), False)

    # Build folders
    shutil.rmtree(DIR_FOLDERS, ignore_errors=True)
    for folder_uid, declared in FOLDERS.items():
        write(join(DIR_FOLDERS, folder_uid + ".yaml"), encoded(folderv1.manifest(folder_uid, folderv1.Folder(declared.title)).build()))

    # Build preferences
    preferences = encoded(preferencesv1alpha1.manifest("namespace", preferencesv1alpha1.Preferences().home_dashboard_uid(HOME).timezone("browser")).build())
    preferences["apiVersion"] = "preferences.grafana.app/v1"
    shutil.rmtree(DIR_CONFIG, ignore_errors=True)
    write(join(DIR_CONFIG, "preferences.yaml"), preferences)

    # Build datasources
    # noinspection HttpUrlsUsage
    write(join(DIR_PROVISIONING, "datasources/datasources.yaml"), {
        "apiVersion": 1,
        "datasources": [
            {
                "name": "InfluxDB3 Home",
                "uid": INFLUXDB3,
                "type": dialects.influxdb3.GRAFANA,
                "access": "proxy",
                "url": "http://${INFLUXDB3_SERVICE}:${INFLUXDB3_API_PORT}",
                "isDefault": True,
                "editable": False,
                "jsonData": {
                    "version": "SQL",
                    "dbName": "${INFLUXDB3_DATABASE_HOME}",
                    "httpMode": "POST",
                    "insecureGrpc": True,
                    "timeout": 60,
                },
                "secureJsonData": {
                    "token": "${INFLUXDB3_TOKEN_HOME}",
                },
            },
            {
                "name": "Postgres Wrangle",
                "uid": POSTGRES,
                "type": dialects.postgres.GRAFANA,
                "access": "proxy",
                "url": "${POSTGRES_SERVICE}:${POSTGRES_API_PORT}",
                "user": "${POSTGRES_USER_WRANGLE}",
                "editable": False,
                "jsonData": {
                    "database": "${POSTGRES_DATABASE_WRANGLE}",
                    "sslmode": "disable",
                    "timescaledb": True,
                    "postgresVersion": 1600,
                },
                "secureJsonData": {
                    "password": "${POSTGRES_KEY_WRANGLE}",
                },
            },
        ],
    })


def artifact(module):
    if module not in SCHEMA_ARTIFACTS:
        dialect = [basename(dirname(path)) for path in glob.glob(join(DIR_ROOT, "../../*", module, "src/build/resources/schema/*/document.json"))]
        if len(dialect) != 1 or dialect[0] not in DATASOURCES:
            raise failed(f"module [{module}] has no single database schema artifact, run [fab generate] in the module")
        SCHEMA_ARTIFACTS[module] = (dialect[0], load_schema_artifact(module, dialect[0]))
    return SCHEMA_ARTIFACTS[module]


def unified(units, noun, owner, unit=None):
    if unit is not None:
        return unit
    if len(units) > 1:
        raise failed(f"{noun} [{owner}] mixes units [{','.join(sorted(units))}], pass one explicitly or split it")
    return units.pop() if units else ""


class Relation:

    def __init__(self, module, path):
        dialect, self.document = artifact(module)
        self.dialect, self.datasource = DATASOURCES[dialect]
        matched = [relation for relation in self.document.relations if relation.path == path]
        if not matched:
            raise failed(f"module [{module}] declares no relation [{path}]")
        self.relation = matched[0]
        self.subject = self.dialect.subject(self.relation)
        self.interval = self.relation.cadence if duration(self.relation.cadence) else ""

    def query(self, measures, entities=None, transforms=(), labels=None, unit=None, description=None):
        picked = [measure for measure, _ in selected(self.relation, self.document, measures, self.dialect.KINDS)]
        units = {"%"} if "percent" in transforms or "baseline" in transforms else {measure.unit for measure in picked}
        descriptions = sorted({measure.description for measure in picked if measure.description})
        levels = None
        if len(picked) == 1 and picked[0].levels is not None and set(transforms) <= WORST_TRANSFORMS[picked[0].levels.better]:
            judged = picked[0].levels
            bounds = {(judged.entities[entity].amber, judged.entities[entity].red) if entity in judged.entities else (judged.amber, judged.red)
                      for entity in (entities or self.relation.entities or [None])}
            if len(bounds) == 1 and bounds != {(None, None)}:
                levels = Levels(judged.better, *bounds.pop(), judged.inclusive)
        return Series(
            self.dialect,
            self.datasource,
            self.dialect.panel(self.relation, self.document, measures, entities, transforms, labels),
            unified(units, "relation", self.relation.path, unit),
            self.interval,
            "; ".join(descriptions) if description is None else description,
            "time_series",
            levels=levels,
        )

    def sql(self, statement, unit, description, **values):
        placeholders = set(re.findall(SQL_PLACEHOLDER, statement))
        unused = sorted(set(values) - placeholders)
        values = {"table": self.relation.plugin, "entity": self.subject, **values}
        unknown = sorted(placeholders - set(values))
        if unknown or unused:
            raise failed(f"relation [{self.relation.path}] sql placeholders [{','.join(unknown)}] have no value and values [{','.join(unused)}] have no placeholder")

        def indented(match):
            line = match.string[match.string.rfind("\n", 0, match.start()) + 1:]
            return str(values[match.group(1)]).replace("\n", "\n" + line[:len(line) - len(line.lstrip())])

        return Series(
            self.dialect,
            self.datasource,
            re.sub(SQL_PLACEHOLDER, indented, statement.strip()),
            unit,
            self.interval,
            description,
            "time_series",
            ORIGIN_WRITTEN,
        )

    def scope(self, measure, entities):
        picked = selected(self.relation, self.document, [measure], self.dialect.KINDS)
        if len(picked) != 1:
            raise failed(f"relation [{self.relation.path}] measure [{measure}] matches [{len(picked)}] periods, name one as [<measure>@<period>]")
        return "\nAND ".join(self.dialect.predicates(self.relation, self.document, picked[0][0], subjected(self.relation, self.document, entities)))

    def entities(self, excluded=()):
        return [entity for entity in self.relation.entities if entity not in excluded]


def summary(sources, statistic, span, unit, description):
    first = sources[0][0]
    return Series(
        first.dialect,
        first.datasource,
        first.dialect.summary([(source.relation, entities) for source, entities in sources], first.document, statistic, span),
        unit,
        first.interval,
        description,
        "table",
    )


def higher_better(low, high):
    return [(None, RED)] + ([(low, YELLOW)] if low != high else []) + [(high, GREEN)]


def lower_better(low, high):
    return [(None, GREEN)] + ([(low, YELLOW)] if low != high else []) + [(high, RED)]


def levelled(levels):
    rising_is_healthier = levels.better == BETTER_HIGHER

    def onset(bound):
        return bound if levels.inclusive == rising_is_healthier else bound + LEVEL_EPSILON

    if rising_is_healthier:
        ladder = [(None, RED if levels.red is not None else YELLOW)]
        if levels.red is not None and levels.amber is not None:
            ladder.append((onset(levels.red), YELLOW))
        ladder.append((onset(levels.amber if levels.amber is not None else levels.red), GREEN))
        return ladder
    ladder = [(None, GREEN)]
    if levels.amber is not None:
        ladder.append((onset(levels.amber), YELLOW))
    if levels.red is not None:
        ladder.append((onset(levels.red), RED))
    return ladder


class Panel:

    def __init__(self, title, queries, width, height, visualization, unit=None):
        self.queries = queries if isinstance(queries, list) else [queries]
        self.title, self.width, self.height = title, width, height
        self.visualization = visualization
        unit = unified({query.unit for query in self.queries}, "panel", title, unit)
        grafana_unit = GRAFANA_UNITS.get(unit, f"suffix: {unit}")
        self.visualization.unit(grafana_unit).decimals(UNIT_DECIMALS.get(grafana_unit, 2))
        displays = {query.dialect.DISPLAY for query in self.queries}
        if len(displays) == 1 and "" not in displays and all(query.form == "time_series" for query in self.queries):
            self.visualization.display_name(displays.pop())
        judged = {query.levels for query in self.queries}
        self.levels = next(iter(judged)) if len(judged) == 1 else None
        self.disagreeing = len(judged) > 1 and judged != {None}
        self.explicit = False

    def __getattr__(self, name):
        method = getattr(self.visualization, name)

        def chained(*arguments, **options):
            method(*arguments, **options)
            return self

        return chained

    def override(self, pattern, properties):
        self.visualization.override_by_regexp(pattern, [models.DynamicConfigValue(id_val=key, value=value) for key, value in properties.items()])
        return self

    def thresholds(self, ladder, override=False):
        if self.levels is not None and not override:
            raise failed(f"panel [{self.title}] takes its thresholds from its measure's levels, "
                         f"declare them in the owning schema or pass override=True to replace them deliberately")
        self.explicit = True
        return self._coloured(ladder)

    def _coloured(self, ladder):
        self.visualization.thresholds(dashboardv2.ThresholdsConfig().mode(models.ThresholdsMode.ABSOLUTE).steps([
            models.Threshold(value=value, color=color) for value, color in ladder
        ]))
        return self

    def build(self, identifier):
        if self.disagreeing and not self.explicit:
            raise failed(f"panel [{self.title}] combines queries whose measure levels disagree, give it explicit thresholds")
        group = dashboardv2.QueryGroup().targets([
            dashboardv2.Target().ref_id(chr(ord("A") + index)).query(Query(query.dialect.GRAFANA, query.datasource, query.sql, query.form))
            for index, query in enumerate(self.queries)
        ])
        intervals = sorted({query.interval for query in self.queries if query.interval}, key=lambda interval: duration(interval) or 0)
        if intervals:
            group.query_options(dashboardv2.QueryOptionsSpec().interval(intervals[-1]))
        origin = ORIGIN_WRITTEN if any(query.origin == ORIGIN_WRITTEN for query in self.queries) else ORIGIN_GENERATED
        described = "; ".join(sorted({query.description for query in self.queries if query.description}))
        return (dashboardv2.Panel()
                .id(identifier)
                .title(self.title)
                .description(f"{origin}: {described}" if described else origin)
                .data(group)
                .visualization(self.visualization))


def stat(title, queries, reducer="lastNotNull", unit=None, height=4):
    visualization = (stats.VisualizationV2()
                     .graph_mode(kinds.BigValueGraphMode.AREA)
                     .color_mode(kinds.BigValueColorMode.VALUE)
                     .text_mode(kinds.BigValueTextMode.VALUE)
                     .justify_mode(kinds.BigValueJustifyMode.CENTER)
                     .reduce_options(common.ReduceDataOptions().calcs([reducer])))
    panel = Panel(title, queries, 4, height, visualization, unit)
    if panel.levels is not None and reducer not in WORST_REDUCERS[panel.levels.better]:
        panel.levels, panel.disagreeing = None, False
    return panel._coloured(levelled(panel.levels) if panel.levels is not None else NEUTRAL_LADDER)


def series(title, queries, unit=None, interpolation=kinds.LineInterpolation.LINEAR):
    visualization = (timeseries.VisualizationV2()
                     .line_interpolation(interpolation)
                     .fill_opacity(0)
                     .line_width(1)
                     .show_points(kinds.VisibilityMode.NEVER)
                     .span_nulls(True)
                     .axis_width(AXIS_WIDTH)
                     .tooltip(common.VizTooltipOptions().mode(kinds.TooltipDisplayMode.MULTI).sort(kinds.SortOrder.DESCENDING))
                     .legend(common.VizLegendOptions()
                             .show_legend(True)
                             .display_mode(kinds.LegendDisplayMode.TABLE)
                             .placement(kinds.LegendPlacement.RIGHT)
                             .width(LEGEND_WIDTH)
                             .calcs(["min", "max", "mean"])))
    panel = Panel(title, queries, GRID_WIDTH, 10, visualization, unit)
    panel.levels, panel.disagreeing = None, False
    return panel


def steps(title, queries, unit=None):
    return series(title, queries, unit, kinds.LineInterpolation.STEP_AFTER)


def points(title, queries, unit=None):
    return series(title, queries, unit).draw_style(kinds.GraphDrawStyle.POINTS).show_points(kinds.VisibilityMode.ALWAYS).point_size(4)


def bars(title, queries, unit=None):
    return series(title, queries, unit).draw_style(kinds.GraphDrawStyle.BARS).fill_opacity(80)


def compass_scale(panel):
    return panel.min(0).max(len(COMPASS_POINTS)).mappings(COMPASS_MAPPINGS)


def state(title, queries, height=10):
    visualization = (statetimelines.VisualizationV2()
                     .show_value(kinds.VisibilityMode.NEVER)
                     .merge_values(True)
                     .row_height(0.8)
                     .fill_opacity(80)
                     .line_width(0)
                     .color_scheme(dashboardv2.FieldColor().mode(models.FieldColorModeId.THRESHOLDS))
                     .axis_width(AXIS_WIDTH)
                     .legend(common.VizLegendOptions()
                             .show_legend(True)
                             .display_mode(kinds.LegendDisplayMode.LIST)
                             .placement(kinds.LegendPlacement.RIGHT)
                             .width(LEGEND_WIDTH)))
    panel = Panel(title, queries, GRID_WIDTH, height, visualization)
    panel.levels, panel.disagreeing = None, False
    return panel._coloured(STATE_LADDER)


def header(sources, service, ceiling=None):
    relation = sources[0][0].relation
    span = int(ceiling or duration(relation.cadence) or 0)
    if not span:
        raise failed(f"header relation [{relation.path}] cadence [{relation.cadence}] needs an explicit ceiling")
    availability_series = Series(
        SUPERVISOR_SERVICES.dialect,
        SUPERVISOR_SERVICES.datasource,
        SUPERVISOR_SERVICES.dialect.held(SUPERVISOR_SERVICES.relation, SUPERVISOR_SERVICES.document, "status", [service]),
        "%",
        SUPERVISOR_SERVICES.interval,
        f"Share of the window the {service} service was up",
        "table",
    )
    slots = [
        ("Newest", summary(sources, "newest", span, "s", "Time from the most recent report by any entity to the end of the window"), lower_better(2 * span, 4 * span)),
        ("Oldest", summary(sources, "oldest", span, "s", "Time from the stalest entity's last report to the end of the window"), lower_better(2 * span, 4 * span)),
        ("Availability", availability_series, higher_better(99, 99.5)),
        ("Entities", summary(sources, "entities", span, "%", "Share of recently active entities reporting in the latest batch"), higher_better(80, 100)),
        ("Metrics", summary(sources, "metrics", span, "%", "Share of measures written in the window that reported in the latest batch"), higher_better(80, 100)),
        ("Volume", summary(sources, "volume", span, "%", "Rows in the last quarter of the window as a share of the average quarter"), VOLUME_LADDER),
    ]
    return [
        stat(title, query, height=3).color_mode(kinds.BigValueColorMode.BACKGROUND).graph_mode(kinds.BigValueGraphMode.NONE).decimals(0).thresholds(ladder)
        for title, query, ladder in slots
    ]


def dashboard(uid, window, header_panels, rows):
    if uid not in TITLES:
        raise failed(f"dashboard [{uid}] is in no folder, list it in FOLDERS")
    if uid in DASHBOARDS:
        raise failed(f"dashboard uid [{uid}] is used twice")
    elements, items, skyline = {}, [], [0] * GRID_WIDTH
    for row in [header_panels] + rows:
        top, cursor = max(skyline), 0
        for panel in row:
            if panel.width > GRID_WIDTH:
                raise failed(f"dashboard [{uid}] panel [{panel.title}] is wider than [{GRID_WIDTH}]")
            if cursor + panel.width > GRID_WIDTH:
                cursor = 0
            y = max([top] + skyline[cursor:cursor + panel.width])
            name = f"panel-{len(elements) + 1}"
            elements[name] = panel.build(len(elements) + 1)
            items.append(dashboardv2.grid_item(name).x(cursor).y(y).width(panel.width).height(panel.height))
            skyline[cursor:cursor + panel.width] = [y + panel.height] * panel.width
            cursor += panel.width
    ranges = [
        dashboardv2.TimeRangeOption().display(f"Last {option}").from_val(f"now-{option}").to("now")
        for option in window.options
    ]
    builder = (dashboardv2.Dashboard(TITLES[uid])
               .editable(True)
               .cursor_sync(models.DashboardCursorSync.CROSSHAIR)
               .elements(elements)
               .layout(dashboardv2.Grid().items(items))
               .time_settings(dashboardv2.TimeSettings()
                              .timezone("browser")
                              .from_val(window.start)
                              .to("now")
                              .auto_refresh("")
                              .auto_refresh_intervals([window.refresh])
                              .quick_ranges(ranges)))
    DASHBOARDS[uid] = encoded(dashboardv2.manifest(uid, builder).build())
    return DASHBOARDS[uid]


def metadata_dashboard(uid, ceiling, entities_df, group=None, placed=None):
    group = group or TITLES[uid]
    domain_parts, units = {}, {}
    for entity in [metadata_row.dropna().to_dict() for _, metadata_row in entities_df.iterrows()]:
        if group not in [grouped.strip() for grouped in str(entity.get("grafana_group") or entity["entity_group"]).split(",")]:
            continue
        if "grafana_index" in entity:
            try:
                entity["grafana_index"] = float(entity["grafana_index"])
            except ValueError:
                warned(f"entity [{entity['unique_id']}] grafana_index [{entity['grafana_index']}] is not a number so its panel is ordered by index")
                del entity["grafana_index"]
        if entity["device_via_device"] == "_":
            if entity["unique_id"] == "graph_break":
                domain_parts.setdefault(entity["entity_domain"], [[]]).append([])
            continue
        domain_parts.setdefault(entity["entity_domain"], [[]])
        declared = []
        if entity["unique_id"] in HASS_MEASUREMENTS:
            declared = [dimension.entities for dimension in HASS_MEASUREMENTS[entity["unique_id"]].dimensions if dimension.key == "unit_of_measurement"]
        elif entity["entity_namespace"] in HASS_PATHS:
            warned(f"entity [{entity['unique_id']}] has no homeassistant schema measurement so dashboard [{uid}] draws no data for it, "
                   f"run [fab generate] in [src/meg/homeassistant] once it has written")
        else:
            warned(f"entity [{entity['unique_id']}] has no homeassistant schema measurement and namespace [{entity['entity_namespace']}] is no homeassistant relation so is left off dashboard [{uid}]")
            continue
        unit = entity.get("unit_of_measurement") or (declared[0][0] if declared and len(declared[0]) == 1 else "")
        if unit or entity["unique_id"] in HASS_MEASUREMENTS:
            units[entity["unique_id"]] = unit
        domain_parts[entity["entity_domain"]][-1].append(entity)

    def queried(entities, transforms, description):
        relation = Relation("homeassistant", measurement_paths[entities[0]["unique_id"]])
        unmeasured = [member["unique_id"] for member in entities if member["unique_id"] not in expanded(relation.relation, relation.relation.subject)]
        if unmeasured:
            relation.relation = replace(relation.relation, entities=relation.relation.entities + unmeasured, dimensions=[
                replace(dimension, entities=dimension.entities + unmeasured) if dimension.subject and dimension.entities else dimension
                for dimension in relation.relation.dimensions
            ])
        return relation.query(
            ["value"],
            [member["unique_id"] for member in entities],
            transforms,
            {member["unique_id"]: member.get("friendly_name", member["unique_id"]) for member in entities},
            "",
            description,
        )

    splits = [(domain, part) for domain, domain_splits in domain_parts.items() for part in domain_splits if part]
    if not splits:
        warned(f"dashboard [{uid}] has no graphed entity so is not generated")
        return None
    measurement_paths, sources = {}, {}
    for _, members in splits:
        known = [HASS_MEASUREMENTS[member["unique_id"]].path for member in members if member["unique_id"] in HASS_MEASUREMENTS]
        for entity in members:
            path = HASS_MEASUREMENTS[entity["unique_id"]].path if entity["unique_id"] in HASS_MEASUREMENTS else (known[0] if known else entity["entity_namespace"])
            measurement_paths[entity["unique_id"]] = path
            sources.setdefault(path, []).append(entity["unique_id"])
    panel_runs = []
    for domain, members in splits:
        split_runs = []
        for entity in members:
            unit, kind = units.get(entity["unique_id"]), entity["grafana_display_type"]
            if split_runs and split_runs[-1].kind == kind and split_runs[-1].members[-1].get("grafana_index") == entity.get("grafana_index") \
                    and (unit is None or split_runs[-1].unit in (None, unit)):
                split_runs[-1].unit = split_runs[-1].unit or unit
                split_runs[-1].members.append(entity)
            else:
                split_runs.append(PanelRun(domain, unit, kind, [entity]))
        panel_runs.extend(split_runs)
    ordered_rows = list((placed or {}).values())
    for run in panel_runs:
        if run.kind not in DISPLAY_TYPES:
            warned(f"dashboard [{uid}] panel [{run.domain}] grafana_display_type [{run.kind}] expected one of [{','.join(DISPLAY_TYPES)}] so draws lines")
        unit = run.unit or ""
        by_measurement = {}
        for entity in run.members:
            by_measurement.setdefault(measurement_paths[entity["unique_id"]], []).append(entity)
        panel_transforms = ("compass",) if unit == ANGLE_UNIT else ("peak",) if run.kind == BARS_DISPLAY else ()
        queries = [queried(entities, panel_transforms, f"Home Assistant Group {run.domain}") for entities in by_measurement.values()]
        panel = DISPLAY_TYPES.get(run.kind, series)(run.domain, queries, "" if unit == ANGLE_UNIT else unit)
        overrides = [member["grafana_index"] for member in run.members if "grafana_index" in member]
        ordered_rows.append((min(overrides) if overrides else min(member["index"] for member in run.members), [[compass_scale(panel) if unit == ANGLE_UNIT else panel]]))
    panel_rows = [row for _, rows in sorted(ordered_rows, key=lambda ordered: ordered[0]) for row in rows]
    kpi_marked = [member for _, part in splits for member in part if member.get("grafana_kpi")]
    if len(kpi_marked) > KPI_SLOTS:
        warned(f"dashboard [{uid}] marks [{len(kpi_marked)}] entities with [grafana_kpi] so only the first [{KPI_SLOTS}] are shown")
    measurements_differ = len(set(measurement_paths.values())) > 1
    kpi_panels, kpi_entities = [], set()
    for entity in kpi_marked + [run.members[0] for run in panel_runs] + [member for _, part in splits for member in part]:
        if len(kpi_panels) == KPI_SLOTS or entity["unique_id"] in kpi_entities:
            continue
        kpi_entities.add(entity["unique_id"])
        reducer = entity.get("grafana_kpi", "last")
        if reducer not in REDUCERS:
            warned(f"entity [{entity['unique_id']}] grafana_kpi [{reducer}] expected one of [{','.join(REDUCERS)}] so shows its last value")
            reducer = "last"
        name = entity.get("friendly_name", entity["unique_id"])
        device_class = measurement_paths[entity["unique_id"]].partition("__")[2]
        noun = DEVICE_CLASS_NOUNS.get(device_class, device_class.replace("_", " ").title())
        if measurements_differ and device_class and noun.lower() not in name.lower():
            name = f"{name} {noun}"
        name = " ".join(word for word in (name, REDUCERS[reducer].suffix) if word)
        if name in [panel.title for panel in kpi_panels]:
            continue
        described = f"Home Assistant entity {entity['unique_id']}, {REDUCERS[reducer].phrase}"
        is_angle = units.get(entity["unique_id"]) == ANGLE_UNIT
        kpi_query = queried([entity], ("compass",) if is_angle else REDUCERS[reducer].transforms, described)
        kpi = stat(name, kpi_query, REDUCERS[reducer].calculation, "" if is_angle else units.get(entity["unique_id"], ""))
        kpi_panels.append(compass_scale(kpi) if is_angle else kpi)
    for panel in kpi_panels:
        panel.width = GRID_WIDTH // len(kpi_panels)
    sourced_relations = [(Relation("homeassistant", path), entities) for path, entities in sources.items()]
    return dashboard(uid, WEEK_WINDOW, header(sourced_relations, "homeassistant", ceiling), [kpi_panels] + panel_rows)


def friendly_names(entities_df, unique_ids):
    names = {unique_id: name for unique_id, name in zip(entities_df["unique_id"], entities_df["friendly_name"], strict=True) if isinstance(name, str) and name}
    for unique_id in unique_ids:
        if unique_id not in names:
            warned(f"entity [{unique_id}] has no [friendly_name] in the metadata so is labelled by its id")
            names[unique_id] = unique_id
    return {unique_id: names[unique_id] for unique_id in unique_ids}


def failed(message):
    return ValueError(f"Build generate script [grafana] {message}")


def warned(message):
    print(f"Build generate script [grafana] warning {message}", file=sys.stderr)
    sys.stderr.flush()


def encoded(built):
    return json.loads(json.dumps(built, cls=JSONEncoder))


class Dumper(yaml.SafeDumper):
    pass


Dumper.add_representer(str, lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None))
Dumper.add_representer(float, lambda dumper, value: dumper.represent_int(int(value)) if value.is_integer() else dumper.represent_float(value))


def dumped(resource):
    return yaml.dump(resource, Dumper=Dumper, sort_keys=True, allow_unicode=True, default_flow_style=False, width=4096)


def normalised(resource, name):
    folder = ((resource.get("metadata") or {}).get("annotations") or {}).get(FOLDER)
    resource = {key: value for key, value in resource.items() if key in ("apiVersion", "kind", "spec")}
    resource["metadata"] = {"name": name, **({"annotations": {FOLDER: folder}} if folder else {})}
    return resource


def write(path: str, resource, bannered=True):
    if "kind" in resource and resource["apiVersion"] not in API_VERSIONS:
        raise failed(f"resource [{path}] has apiVersion [{resource['apiVersion']}] expected one of [{','.join(sorted(API_VERSIONS))}]")
    os.makedirs(dirname(path), exist_ok=True)
    with open(path, "w") as file:
        file.write((BANNER + "\n" if bannered else "") + dumped(resource))
    print(f"Build generate script [grafana] resource persisted to [{path}]")


def sourced(path):
    with open(path) as file:
        text = file.read()
    if BANNER in text:
        raise failed(f"hand-authored file [{path}] carries the build banner, a generated file was copied back as a source, delete the banner or the file")
    return yaml.safe_load(text)


DIR_ROOT: str = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_DATA = join(DIR_ROOT, "src/main/resources/data")
DIR_DASHBOARDS = join(DIR_DATA, "dashboards")
DIR_GENERATED = join(DIR_DASHBOARDS, "generated")
DIR_CUSTOM = join(DIR_DASHBOARDS, "custom")
DIR_FOLDERS = join(DIR_DASHBOARDS, "folders")
DIR_CONFIG = join(DIR_DASHBOARDS, "config")
DIR_PROVISIONING = join(DIR_ROOT, "src/main/resources/image/provisioning")

BANNER = banner()
FOLDER = "grafana.app/folder"
API_VERSIONS = {
    "dashboard.grafana.app/v2",
    "folder.grafana.app/v1",
    "preferences.grafana.app/v1",
}

INFLUXDB3 = "influxdb3-home"
POSTGRES = "postgres-wrangle"
DATASOURCES = {
    "influxdb3": (dialects.influxdb3, INFLUXDB3),
    "postgres": (dialects.postgres, POSTGRES),
}

HOME = "home"
FINANCE = "finance"
SYSTEMS = "systems"
Folder = namedtuple("Folder", "title dashboards")
FOLDERS = {
    HOME: Folder("Home", {"weather": "Weather", "conditions": "Conditions", "electricity": "Electricity"}),
    FINANCE: Folder("Finance", {"currency": "Currency", "interest": "Interest", "equity": "Equity"}),
    SYSTEMS: Folder("Systems", {"containers": "Containers", "servers": "Servers", "network": "Network", "internet": "Internet"}),
}
TITLES = {uid: title for declared in FOLDERS.values() for uid, title in declared.dashboards.items()}
DASHBOARD_TAG = "asystem"

GRID_WIDTH = 24
AXIS_WIDTH = 200
LEGEND_WIDTH = 400
TimeRange = namedtuple("TimeRange", "start refresh options")
SHORT_RANGES = ["5m", "15m", "1h", "6h", "12h", "24h", "2d", "7d", "30d", "60d", "90d"]
LONG_RANGES = ["7d", "30d", "90d", "180d", "1y", "5y", "10y", "25y", "50y"]
HOURS_WINDOW = TimeRange("now-6h", "30s", SHORT_RANGES)
WEEK_WINDOW = TimeRange("now-7d", "1m", SHORT_RANGES)
YEAR_WINDOW = TimeRange("now-1y", "15m", LONG_RANGES)

GRAFANA_UNITS = {
    "": "none",
    "%": "percent",
    "$": "currencyUSD",
    "°C": "celsius",
    "°": "degree",
    "ms": "ms",
    "s": "s",
    "minutes": "m",
    "d": "d",
    "MiB": "mbytes",
    "Mbps": "Mbits",
    "W": "watt",
    "kWh": "kwatth",
    "wpm²": "Wm2",
    "V": "volt",
    "mV": "mvolt",
    "A": "amp",
    "m": "lengthm",
    "km": "lengthkm",
    "km/h": "velocitykmh",
    "kn": "velocityknot",
    "hPa": "pressurehpa",
    "ppm": "ppm",
    "dB": "dB",
    "µg/m³": "conμgm3",
    "μg/m³": "conμgm3",
}
UNIT_DECIMALS = {
    "percent": 1,
    "currencyUSD": 3,
    "celsius": 1,
    "degree": 0,
    "ms": 0,
    "s": 0,
    "m": 0,
    "d": 0,
    "watt": 0,
    "kwatth": 2,
    "Wm2": 0,
    "mvolt": 0,
    "suffix: mm": 1,
    "lengthm": 0,
    "lengthkm": 1,
    "velocitykmh": 1,
    "velocityknot": 1,
    "pressurehpa": 1,
    "suffix: mbar": 0,
    "ppm": 0,
    "dB": 0,
    "conμgm3": 0,
}
RED, YELLOW, GREEN, BLUE = "red", "yellow", "green", "blue"
CHANGE_LADDER = [(None, RED), (0, GREEN)]
VOLUME_LADDER = [(None, RED), (50, YELLOW), (80, GREEN), (120, YELLOW), (150, RED)]
STATE_LADDER = [(None, RED), (1, GREEN)]
NEUTRAL_LADDER = [(None, BLUE)]
SUPERVISOR_SPAN = 300
DAY = 86400
TRADING_SPAN = 3 * DAY
KPI_SLOTS = 6
DEVICE_CLASS_NOUNS = {
    "pm25": "PM2.5",
}
Reducer = namedtuple("Reducer", "calculation transforms suffix phrase")
REDUCERS = {
    "last": Reducer("lastNotNull", (), "", "latest in the window"),
    "mean": Reducer("mean", (), "Mean", "mean across the window"),
    "max": Reducer("max", ("peak",), "Max", "maximum across the window"),
    "min": Reducer("min", ("trough",), "Min", "minimum across the window"),
}

SQL_PLACEHOLDER = r"\$([a-z]\w*)"
ORIGIN_GENERATED = "Generated"
ORIGIN_WRITTEN = "Hand-written"
Series = namedtuple("Series", "dialect datasource sql unit interval description form origin levels", defaults=[ORIGIN_GENERATED, None])
Levels = namedtuple("Levels", "better amber red inclusive")
WORST_TRANSFORMS = {BETTER_HIGHER: {"trough", "min"}, BETTER_LOWER: {"peak", "max"}}
WORST_REDUCERS = {BETTER_HIGHER: {"lastNotNull", "min"}, BETTER_LOWER: {"lastNotNull", "max"}}
LEVEL_EPSILON = 1e-6
SCHEMA_ARTIFACTS = {}


@dataclass
class PanelRun:
    domain: str
    unit: str | None
    kind: str
    members: list


BARS_DISPLAY = "Bars"
DISPLAY_TYPES = {
    "Lines": series,
    "Steps": steps,
    "Points": points,
    BARS_DISPLAY: bars,
}
ANGLE_UNIT = "°"
NAVIGATION_ELEMENT = "panel-navigation"
NAVIGATION_HEIGHT = 2
SECTION_COLOUR = "#8e8e8e"
COMPASS_POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
COMPASS_MAPPINGS = [
    models.RangeMap(options=models.Dashboardv2RangeMapOptions(from_val=low, to=high, result=models.ValueMappingResult(text=point)))
    for low, high, point in [(max(0.0, index - 0.5), index + 0.5, point) for index, point in enumerate(COMPASS_POINTS)] + [(15.5, 16.0, "N")]
]
DASHBOARDS = {}
SUPERVISOR_SERVICES = Relation("supervisor", "supervisor/service")
HASS_RELATIONS = artifact("homeassistant")[1].relations
HASS_PATHS = {relation.path for relation in HASS_RELATIONS}
HASS_MEASUREMENTS = {}
for hass_relation in HASS_RELATIONS:
    for hass_dimension in hass_relation.dimensions:
        if hass_dimension.key == "entity_id":
            for hass_entity in hass_dimension.entities:
                HASS_MEASUREMENTS.setdefault(hass_entity, hass_relation)

if __name__ == "__main__":
    main()
