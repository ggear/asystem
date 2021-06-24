local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local timepicker = grafana.timepicker;
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
            
      grafanaDashboardFolder:: 'Private_Desktop',
            
      grafanaDashboards:: {

            network_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Network',
                        uid='network-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_network.graphs()),


            electricity_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Electricity',
                        uid='electricity-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_electricity.graphs()),


            servers_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Servers',
                        uid='servers-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_servers.graphs()),


            water_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Water',
                        uid='water-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_water.graphs()),


            currency_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Currency',
                        uid='currency-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-1y', refresh='', timepicker=timepicker.new(refresh_intervals=['30m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Interest',
                        uid='interest-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-25y', refresh='', timepicker=timepicker.new(refresh_intervals=['30m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_interest.graphs()),


            internet_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Internet',
                        uid='internet-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_internet.graphs()),


            conditions_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Conditions',
                        uid='conditions-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_conditions.graphs()),


            containers_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Containers',
                        uid='containers-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-1h', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_containers.graphs()),

  },
}
