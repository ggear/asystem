{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      stat.new(
        title='Services Running',
        datasource='InfluxDB2',
        unit='s',
        decimals=1,
        reducerFunction='last',
        colorMode='value',
        graphMode='none',
        justifyMode='auto',
        thresholdsMode='absolute',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 43200 }
      ).addThreshold(
        { color: 'green', value: 86400 }
      ).addTarget(influxdb.target(query='// Start
// End')) { gridPos: { x: 0, y: 0, w: 5, h: 3 } },

      stat.new(
        title='Services Stopped',
        datasource='InfluxDB2',
        unit='s',
        decimals=1,
        reducerFunction='last',
        colorMode='value',
        graphMode='none',
        justifyMode='auto',
        thresholdsMode='absolute',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 600 }
      ).addThreshold(
        { color: 'green', value: 12000 }
      ).addTarget(influxdb.target(query='// Start
// End')) { gridPos: { x: 5, y: 0, w: 5, h: 3 } },

      stat.new(
        title='Services Images',
        datasource='InfluxDB2',
        unit='s',
        decimals=1,
        reducerFunction='last',
        colorMode='value',
        graphMode='none',
        justifyMode='auto',
        thresholdsMode='absolute',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 432000 }
      ).addThreshold(
        { color: 'green', value: 864000 }
      ).addTarget(influxdb.target(query='// Start
// End')) { gridPos: { x: 10, y: 0, w: 5, h: 3 } },

    ],
}
