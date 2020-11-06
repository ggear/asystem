{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='Rain',
        datasource='InfluxDB2',
        fill=0,
        format='short',
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
      ).addTarget(influxdb.target(query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "last_30_min_rain")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "friendly_name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
      '))
      { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

    ],
}
