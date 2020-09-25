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
    with open(DIR_MODULE_ROOT + "/../../main/resources/graphs.libsonnet", "w") as file:
        file.write("""
{
  graphs()::
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    [
        """.strip() + "\n")
        for domain in sensors:
            filter = " or ".join([sub + '"' for sub in ['r["entity_id"] == "' + sub for sub in [sensor[2] for sensor in sensors[domain]]]])
            file.write("      " + """
      graph.new(title='{}', datasource='InfluxDB', fill=0).addTarget(influxdb.target(query='
        from(bucket: "asystem")
           |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
           |> filter(fn: (r) => {})
           |> group(columns: ["friendly_name"])
           |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
           |> yield(name: "mean")
      ')) {{ gridPos: {{ x: 0, y: 0, w: 24, h: 15 }} }},
            """.format(domain, filter).strip() + "\n")
        file.write("""
    ],
}
        """.strip() + "\n")
    print("Metadata script [grafana] dashboard saved")
