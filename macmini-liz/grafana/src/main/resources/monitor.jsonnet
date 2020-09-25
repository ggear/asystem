local grafana = import 'grafonnet/grafana.libsonnet';
local graphs = import 'graphs.libsonnet';
local dashboard = grafana.dashboard;

{
  grafanaDashboards:: {
    asystem_dashboard:
      dashboard.new(
        title='ASystem',
        uid='ASystem',
        editable=true,
        schemaVersion=26
      )
      .addPanels(graphs.graphs()),
  },
}
