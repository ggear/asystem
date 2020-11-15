# coding=utf-8

import glob
import os
import sys

DIR_MODULE_ROOT = os.path.abspath("{}/../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/*/*/".format("{}/../../../../../../..".format(os.path.dirname(os.path.realpath(__file__))))):
    if dir_module.split("/")[-2] == "anode":
        sys.path.insert(0, "{}/src/main/python".format(dir_module))
sys.path.insert(0, DIR_MODULE_ROOT)

from anode.metadata.build import load

DIR_DASHBOARD_ROOT = DIR_MODULE_ROOT + "/../../main/resources/config/dashboards"

if __name__ == "__main__":
    sensors = load()
    for group in sensors:
        with open(DIR_DASHBOARD_ROOT + "/generated/graphs_{}.libsonnet".format(group.lower()), "w") as file:
            file.write("""
{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [
            """.strip() + "\n\n")
            snip_path = DIR_DASHBOARD_ROOT + "/" + os.path.basename(file.name).replace(".libsonnet", ".snipsonnet")
            if os.path.isfile(snip_path):
                with open(snip_path, 'r') as snip_file:
                    file.write(snip_file.read())
            for domain in sensors[group]:
                filter = " or ".join([sub + '"'
                                      for sub in ['r["entity_id"] == "' + sub for sub in [sensor[2] for sensor in sensors[group][domain]]]])
                flux = """from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => {})
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                """.format(filter).strip()
                file.write("      " + """
      graph.new(
        title='{}',
        datasource='InfluxDB2',
        fill=0,
        format='{}',
        bars=false,
        lines=true,
        staircase=false,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=350
      ).addTarget(influxdb.target(query='// Start
{}
// End'))
      {{ gridPos: {{ x: 0, y: 0, w: 24, h: 12 }} }},
                """.format(domain, "short", flux).strip() + "\n\n")
            file.write("    " + """
    ],
}
            """.strip() + "\n")
    print("Metadata script [grafana] graphs saved")
    with open(DIR_DASHBOARD_ROOT + "/generated/dashboards_all.jsonnet", "w") as file:
        file.write("""
local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graphs_servers = import '../graphs_servers.libsonnet';
local graphs_services = import '../graphs_services.libsonnet';
local graphs_network = import '../graphs_network.libsonnet';
local graphs_internet = import '../graphs_internet.libsonnet';
        """.strip() + "\n")
        for group in sensors:
            file.write("""
local graphs_{} = import 'graphs_{}.libsonnet';
            """.format(group.lower(), group.lower()).strip() + "\n")
        file.write("\n" + """

{
  grafanaDashboards:: {

    servers_dashboard:
      dashboard.new(
        title='Servers',
        uid='servers',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-7d',
        refresh='30s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_servers.graphs()),

    services_dashboard:
      dashboard.new(
        title='Services',
        uid='services',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-15m',
        refresh='1m',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_services.graphs()),

    network_dashboard:
      dashboard.new(
        title='Network',
        uid='network',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-1h',
        refresh='30s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_network.graphs()),

    internet_dashboard:
      dashboard.new(
        title='Internet',
        uid='internet',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-1d',
        refresh='30s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_internet.graphs()),
        """.strip() + "\n")
        for group in sensors:
            file.write("\n    " + """
    {}_dashboard:
      dashboard.new(
        title='{}',
        uid='{}',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-7d',
        refresh='90s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_{}.graphs()),
            """.format(group.lower(), group, group.lower(), group.lower()).strip() + "\n\n")
        file.write("  " + """
  },
}
        """.strip() + "\n")
    print("Metadata script [grafana] dashboards saved")
