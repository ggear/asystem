local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graph_network = import 'graph_network.jsonnet';
local graph_electricity = import 'graph_electricity.jsonnet';
local graph_servers = import 'graph_servers.jsonnet';
local graph_water = import 'graph_water.jsonnet';
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';
local graph_internet = import 'graph_internet.jsonnet';
local graph_conditions = import 'graph_conditions.jsonnet';
local graph_containers = import 'graph_containers.jsonnet';

{
  grafanaDashboards:: {

    network_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Network (Mobile)',
        uid='network-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-2d', refresh=''
      )
      .addPanels(graph_network.graphs()),


    electricity_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Electricity (Mobile)',
        uid='electricity-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-7d', refresh=''
      )
      .addPanels(graph_electricity.graphs()),


    servers_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Servers (Mobile)',
        uid='servers-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-2d', refresh=''
      )
      .addPanels(graph_servers.graphs()),


    water_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Water (Mobile)',
        uid='water-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-7d', refresh=''
      )
      .addPanels(graph_water.graphs()),


    currency_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Currency (Mobile)',
        uid='currency-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-5y', refresh=''
      )
      .addPanels(graph_currency.graphs()),


    interest_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Interest (Mobile)',
        uid='interest-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-5y', refresh=''
      )
      .addPanels(graph_interest.graphs()),


    internet_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Internet (Mobile)',
        uid='internet-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-2d', refresh=''
      )
      .addPanels(graph_internet.graphs()),


    conditions_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Conditions (Mobile)',
        uid='conditions-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-7d', refresh=''
      )
      .addPanels(graph_conditions.graphs()),


    containers_dashboard:
      dashboard.new(
        schemaVersion=26,
        title='Containers (Mobile)',
        uid='containers-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
        tags=['published', 'mobile'],
        time_from='now-1h', refresh=''
      )
      .addPanels(graph_containers.graphs()),

  },
}
