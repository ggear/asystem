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

if __name__ == "__main__":
    sensors = load()
    for group in sensors:
        with open(DIR_MODULE_ROOT + "/../../main/resources/config/graphs_{}.libsonnet".format(group.lower()), "w") as file:
            file.write("""
{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [
            """.strip() + "\n\n")
            snip_path = file.name.replace(".libsonnet", ".snipsonnet")
            if os.path.isfile(snip_path):
                with open(snip_path, 'r') as snip_file:
                    file.write(snip_file.read())
            for domain in sensors[group]:
                filter = " or ".join([sub + '"'
                                      for sub in ['r["entity_id"] == "' + sub for sub in [sensor[2] for sensor in sensors[group][domain]]]])
                flux = """
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => {})
  |> rename(columns: {{friendly_name: "name"}})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
                """.format(filter).strip()
                file.write("      " + """
      graph.new(
        title='{}',
        datasource='InfluxDB2',
        fill=0,
        format='{}'
      ).addTarget(influxdb.target(query='
{}
        ')) {{ gridPos: {{ x: 0, y: 0, w: 24, h: 10 }} }},
                """.format(domain, "short", flux).strip() + "\n\n")
            file.write("    " + """
    ],
}
            """.strip() + "\n")
    print("Metadata script [grafana] graphs saved")
    with open(DIR_MODULE_ROOT + "/../../main/resources/config/dashboards_all.jsonnet", "w") as file:
        file.write("""
local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
        """.strip() + "\n")
        for group in sensors:
            file.write("""
local graphs_{} = import 'graphs_{}.libsonnet';
            """.format(group.lower(), group.lower()).strip() + "\n")
        file.write("\n" + """

{
  grafanaDashboards:: {
        """.strip() + "\n")
        for group in sensors:
            file.write("\n    " + """
    {}_dashboard:
      dashboard.new(
        title='{}',
        uid='{}',
        editable=true,
        schemaVersion=26,
        time_from='now-2d',
        graphTooltip='shared_tooltip',
      )
      .addPanels(graphs_{}.graphs()),
            """.format(group.lower(), group, group, group.lower()).strip() + "\n\n")
        file.write("  " + """
  },
}
        """.strip() + "\n")
    print("Metadata script [grafana] dashboards saved")
