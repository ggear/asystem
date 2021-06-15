{
      graphs()::
      
            local grafana = import 'grafonnet/grafana.libsonnet';
            local dashboard = grafana.dashboard;
            local graph = grafana.graphPanel;
            local influxdb = grafana.influxdb;
            
            [

                  graph.new(
                        title='Power Consumption',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "office_power_consumption" or r["entity_id"] == "servers_power_consumption" or r["entity_id"] == "towelrails_power_consumption")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

            ],
}
