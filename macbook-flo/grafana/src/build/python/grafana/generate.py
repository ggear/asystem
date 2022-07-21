# coding=utf-8

import glob
import os
import shutil
import sys

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_entity_metadata

DIR_DASHBOARDS_ROOT = os.path.join(DIR_ROOT, "src/main/resources/config/dashboards")

PREFIX = "//AS"
PREFIX_MOBILE = PREFIX + "M"
PREFIX_TABLET = PREFIX + "T"
PREFIX_DESKTOP = PREFIX + "D"
PREFIX_DASHBOARD_DEFAULTS = PREFIX + "DASHBOARD_DEFAULTS "

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    metadata_dashboard_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"].str.len() > 0) &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["grafana_display_type"].str.len() > 0) &
        (metadata_df["entity_group"].str.len() > 0)
        ]
    metadata_dashboard_dicts = {}
    for metadata_dashboard_dict in [row.dropna().to_dict() for index, row in metadata_dashboard_df.iterrows()]:
        group = metadata_dashboard_dict["entity_group"].lower()
        if group not in metadata_dashboard_dicts:
            metadata_dashboard_dicts[group] = {}
        domain = metadata_dashboard_dict["entity_domain"]
        if domain not in metadata_dashboard_dicts[group]:
            metadata_dashboard_dicts[group][domain] = [[]]
        if metadata_dashboard_dict["device_via_device"] == "_":
            if metadata_dashboard_dict["unique_id"] == "graph_break":
                metadata_dashboard_dicts[group][domain].append([])
        else:
            metadata_dashboard_dicts[group][domain][-1].append(metadata_dashboard_dict)
    for group in metadata_dashboard_dicts:
        with open(DIR_DASHBOARDS_ROOT + "/template/private/generated/graph_{}.jsonnet".format(group.lower()), "w") as file:
            file.write((PREFIX_DASHBOARD_DEFAULTS + "time_from='now-7d', refresh='', "
                                                    "timepicker=timepicker.new(refresh_intervals=['1m'], time_options="
                                                    "['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])" + """
{
      graphs()::

            local grafana = import 'grafonnet/grafana.libsonnet';
            local asystem = import 'default/generated/asystem-library.jsonnet';
            local dashboard = grafana.dashboard;
            local stat = grafana.statPanel;
            local graph = grafana.graphPanel;
            local table = grafana.tablePanel;
            local gauge = grafana.gaugePanel;
            local bar = grafana.barGaugePanel;
            local influxdb = grafana.influxdb;
            local header = asystem.header;

            header.new(
//ASM           style='minimal',
//AST           style='medial',
//ASD           style='maximal',
//ASM           formFactor='Mobile',
//AST           formFactor='Tablet',
//ASD           formFactor='Desktop',
                datasource='InfluxDB_V2',

// TODO: Update this to include metadata rows when re-implemented in Go
                measurement='__FIXME__',

                maxMilliSecSinceUpdate='259200000',
            ) +

            [
            """).strip() + "\n\n")
            snip_path = DIR_DASHBOARDS_ROOT + "/template/private/" + os.path.basename(file.name).replace("graph_", "snippet_")
            if os.path.isfile(snip_path):
                with open(snip_path, 'r') as snip_file:
                    file.write(snip_file.read())
            for domain in metadata_dashboard_dicts[group]:
                for domain_index, _ in enumerate(metadata_dashboard_dicts[group][domain]):
                    if metadata_dashboard_dicts[group][domain][domain_index]:
                        type = metadata_dashboard_dicts[group][domain][domain_index][0]["grafana_display_type"]
                        filter = " or ".join([('r["entity_id"] == "' + _dict["unique_id"] + '"') \
                                              for _dict in metadata_dashboard_dicts[group][domain][domain_index]])
                        flux = """from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => {})
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: {})
                        """.format(
                            filter,
                            "true" if type == "Discrete" else "false"
                        ).strip()
                        file.write("                  " + """
              graph.new(
                        title='{}',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='{}',
                        bars=false,
                        lines=true,
                        staircase=false,
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
{}
                  '))
                  {{ gridPos: {{ x: 0, y: 2, w: 24, h: 12 }} }},
                        """.format(domain, "short", flux).strip() + "\n\n")
            file.write("            " + """
        ],
}
            """.strip() + "\n")
    print("Metadata script [grafana] graphs saved")

    graphs = {"public": {}, "private": {}}
    for scope in ["public", "private"]:
        for graph in glob.glob("{}/template/{}/graph_*.jsonnet".format(DIR_DASHBOARDS_ROOT, scope)):
            graphs[scope][os.path.basename(graph).replace(".jsonnet", "").replace("graph_", "")] = \
                "../../config/dashboards/template/{}/".format(scope)
        for graph in glob.glob("{}/template/{}/generated/graph_*.jsonnet".format(DIR_DASHBOARDS_ROOT, scope)):
            graphs[scope][os.path.basename(graph).replace(".jsonnet", "").replace("graph_", "")] = \
                "../../config/dashboards/template/{}/generated/".format(scope)
    graphs["private"].update(graphs["public"])
    for scope in ["public", "private"]:
        with open(DIR_DASHBOARDS_ROOT + "/template/{}/generated/dashboard_graphs.jsonnet".format(scope), "w") as file:
            file.write("""
local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local timepicker = grafana.timepicker;
            """.strip() + "\n")
            for graph in graphs[scope]:
                file.write("""
local graph_{} = import 'graph_{}.jsonnet';
                """.format(graph, graph).strip() + "\n")
            file.write("\n" + ("""

{
            """ + """
//ASM grafanaDashboardFolder:: '{}_Mobile',
//AST grafanaDashboardFolder:: '{}_Tablet',
//ASD grafanaDashboardFolder:: '{}_Desktop',
            """.format(
                scope.title(),
                scope.title(),
                scope.title()
            ) + """
      grafanaDashboards:: {

            """).strip() + "\n")
            for graph in graphs[scope]:
                defaults = open(os.path.join(DIR_DASHBOARDS_ROOT, graphs[scope][graph], "graph_{}.jsonnet".format(graph))) \
                    .readline().rstrip()
                if defaults.startswith(PREFIX_DASHBOARD_DEFAULTS):
                    defaults = defaults.replace(PREFIX_DASHBOARD_DEFAULTS, "")
                else:
                    defaults = "time_from='now-7d', refresh=''"
                file.write("\n            " + """
            {}_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='{}',
//ASM                   uid='{}-mobile',
//AST                   uid='{}-tablet',
//ASD                   uid='{}-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['{}', 'mobile'],
//AST                   tags=['{}', 'tablet'],
//ASD                   tags=['{}', 'desktop'],
                        {}
                  )
                  .addPanels(graph_{}.graphs()),
                """.format(
                    graph,
                    graph.title(),
                    graph,
                    graph,
                    graph,
                    scope,
                    scope,
                    scope,
                    defaults,
                    graph).strip() + "\n\n")
            file.write("  " + """
      },
}
            """.strip() + "\n")
    print("Metadata script [grafana] dashboard templates saved")

    shutil.rmtree(os.path.join(DIR_DASHBOARDS_ROOT, "instance"), ignore_errors=True)
    for scope in ["default", "public", "private"]:
        for form in ["desktop", "tablet", "mobile"]:
            for files in os.walk("{}/template/{}".format(DIR_DASHBOARDS_ROOT, scope)):
                for file_name in files[2]:
                    if not file_name.startswith("snippet_"):
                        with open("{}/{}".format(files[0], file_name), "r") as file_source:
                            file_destination_path = "{}/{}/{}{}".format(files[0].replace("template", "instance")
                                                                        .replace("generated", ""), "generated",
                                                                        "" if scope == "default" else (form + "/"),
                                                                        file_name)
                            private_copy = scope == "public" and file_name.startswith("graph_")
                            if private_copy:
                                destination_path_copy = file_destination_path.replace("public", "private")
                                if not os.path.exists(os.path.dirname(destination_path_copy)):
                                    os.makedirs(os.path.dirname(destination_path_copy))
                                destination_file_copy = open(destination_path_copy, "w")
                            if not os.path.exists(os.path.dirname(file_destination_path)):
                                os.makedirs(os.path.dirname(file_destination_path))
                            with open(file_destination_path, "w") as destination_file:
                                for line in file_source:
                                    if not line.startswith(PREFIX) or \
                                            line.startswith(PREFIX_MOBILE) and form == "mobile" or \
                                            line.startswith(PREFIX_TABLET) and form == "tablet" or \
                                            line.startswith(PREFIX_DESKTOP) and form == "desktop":
                                        if not line.startswith(PREFIX_DASHBOARD_DEFAULTS):
                                            line = line \
                                                .replace(PREFIX_MOBILE, "     ") \
                                                .replace(PREFIX_TABLET, "     ") \
                                                .replace(PREFIX_DESKTOP, "     ")
                                            destination_file.write(line)
                                            if private_copy:
                                                destination_file_copy.write(line)
                                print("{} -> {}".format(
                                    os.path.abspath(file_source.name),
                                    os.path.abspath(file_destination_path)
                                ))
                            if private_copy:
                                print("{} -> {}".format(
                                    os.path.abspath(file_source.name),
                                    os.path.abspath(destination_path_copy)
                                ))
                                destination_file_copy.close()
    print("Metadata script [grafana] dashboard specialisations saved")
