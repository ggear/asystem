local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graphs_conditions = import 'graphs_conditions.libsonnet';
local graphs_water = import 'graphs_water.libsonnet';
local graphs_electricity = import 'graphs_electricity.libsonnet';

{
  grafanaDashboards:: {

    conditions_dashboard:
      dashboard.new(
        title='Conditions',
        uid='Conditions',
        editable=true,
        schemaVersion=26,
        time_from='now-2d',
        graphTooltip='shared_tooltip',
      )
      .addPanels(graphs_conditions.graphs()),


    water_dashboard:
      dashboard.new(
        title='Water',
        uid='Water',
        editable=true,
        schemaVersion=26,
        time_from='now-2d',
        graphTooltip='shared_tooltip',
      )
      .addPanels(graphs_water.graphs()),


    electricity_dashboard:
      dashboard.new(
        title='Electricity',
        uid='Electricity',
        editable=true,
        schemaVersion=26,
        time_from='now-2d',
        graphTooltip='shared_tooltip',
      )
      .addPanels(graphs_electricity.graphs()),

  },
}
