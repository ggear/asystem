local grafana = import 'grafonnet/grafana.libsonnet';

{
  grafanaDashboards:: {
    asystem_dashboard: grafana.dashboard.new('ASystem', uid='ASystem'),
  },
}