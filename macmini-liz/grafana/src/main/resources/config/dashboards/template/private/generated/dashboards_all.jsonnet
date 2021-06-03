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
// GRAPH_DESKTOP:         title='Network (Desktop)',
// GRAPH_MOBILE:         title='Network (Mobile)',
// GRAPH_DESKTOP:         uid='network-dekstop',
// GRAPH_MOBILE:         uid='network-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-2d', refresh=''
      )
      .addPanels(graph_network.graphs()),


    electricity_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Electricity (Desktop)',
// GRAPH_MOBILE:         title='Electricity (Mobile)',
// GRAPH_DESKTOP:         uid='electricity-dekstop',
// GRAPH_MOBILE:         uid='electricity-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-7d', refresh=''
      )
      .addPanels(graph_electricity.graphs()),


    servers_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Servers (Desktop)',
// GRAPH_MOBILE:         title='Servers (Mobile)',
// GRAPH_DESKTOP:         uid='servers-dekstop',
// GRAPH_MOBILE:         uid='servers-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-2d', refresh=''
      )
      .addPanels(graph_servers.graphs()),


    water_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Water (Desktop)',
// GRAPH_MOBILE:         title='Water (Mobile)',
// GRAPH_DESKTOP:         uid='water-dekstop',
// GRAPH_MOBILE:         uid='water-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-7d', refresh=''
      )
      .addPanels(graph_water.graphs()),


    currency_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Currency (Desktop)',
// GRAPH_MOBILE:         title='Currency (Mobile)',
// GRAPH_DESKTOP:         uid='currency-dekstop',
// GRAPH_MOBILE:         uid='currency-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-5y', refresh=''
      )
      .addPanels(graph_currency.graphs()),


    interest_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Interest (Desktop)',
// GRAPH_MOBILE:         title='Interest (Mobile)',
// GRAPH_DESKTOP:         uid='interest-dekstop',
// GRAPH_MOBILE:         uid='interest-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-5y', refresh=''
      )
      .addPanels(graph_interest.graphs()),


    internet_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Internet (Desktop)',
// GRAPH_MOBILE:         title='Internet (Mobile)',
// GRAPH_DESKTOP:         uid='internet-dekstop',
// GRAPH_MOBILE:         uid='internet-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-2d', refresh=''
      )
      .addPanels(graph_internet.graphs()),


    conditions_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Conditions (Desktop)',
// GRAPH_MOBILE:         title='Conditions (Mobile)',
// GRAPH_DESKTOP:         uid='conditions-dekstop',
// GRAPH_MOBILE:         uid='conditions-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-7d', refresh=''
      )
      .addPanels(graph_conditions.graphs()),


    containers_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Containers (Desktop)',
// GRAPH_MOBILE:         title='Containers (Mobile)',
// GRAPH_DESKTOP:         uid='containers-dekstop',
// GRAPH_MOBILE:         uid='containers-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-1h', refresh=''
      )
      .addPanels(graph_containers.graphs()),

  },
}
