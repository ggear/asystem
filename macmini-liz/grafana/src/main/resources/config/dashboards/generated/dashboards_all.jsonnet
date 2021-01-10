local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graphs_finance = import '../graphs_finance.libsonnet';
local graphs_servers = import '../graphs_servers.libsonnet';
local graphs_containers = import '../graphs_containers.libsonnet';
local graphs_network = import '../graphs_network.libsonnet';
local graphs_internet = import '../graphs_internet.libsonnet';
local graphs_conditions = import 'graphs_conditions.libsonnet';
local graphs_water = import 'graphs_water.libsonnet';
local graphs_electricity = import 'graphs_electricity.libsonnet';

{
  grafanaDashboards:: {

    finance_dashboard:
      dashboard.new(
        title='Finance',
        uid='finance',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-1h',
        refresh='5m',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_finance.graphs()),

    servers_dashboard:
      dashboard.new(
        title='Servers',
        uid='servers',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-1h',
        refresh='5m',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_servers.graphs()),

    containers_dashboard:
      dashboard.new(
        title='Containers',
        uid='containers',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-1h',
        refresh='5m',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_containers.graphs()),

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
        time_from='now-3h',
        refresh='30s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_internet.graphs()),

    conditions_dashboard:
      dashboard.new(
        title='Conditions',
        uid='conditions',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-7d',
        refresh='90s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_conditions.graphs()),


    water_dashboard:
      dashboard.new(
        title='Water',
        uid='water',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-7d',
        refresh='90s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_water.graphs()),


    electricity_dashboard:
      dashboard.new(
        title='Electricity',
        uid='electricity',
        editable=true,
        tags=['published'],
        schemaVersion=26,
        time_from='now-7d',
        refresh='90s',
        graphTooltip='shared_crosshair',
      )
      .addPanels(graphs_electricity.graphs()),

  },
}
