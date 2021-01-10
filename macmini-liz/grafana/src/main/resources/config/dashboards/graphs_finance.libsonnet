{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local stat = grafana.statPanel;
    local graph = grafana.graphPanel;
    local table = grafana.tablePanel;
    local gauge = grafana.gaugePanel;
    local bar = grafana.barGaugePanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='FX Rates',
        datasource='InfluxDB2',
        fill=0,
        format='Bps',
        bars=false,
        lines=true,
        staircase=false,
        points=true,
        pointradius=1,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

    ],
}
