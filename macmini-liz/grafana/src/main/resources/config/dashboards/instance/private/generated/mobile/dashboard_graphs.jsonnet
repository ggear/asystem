local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local timepicker = grafana.timepicker;
local graph_network = import 'graph_network.jsonnet';
local graph_electricity = import 'graph_electricity.jsonnet';
local graph_internet = import 'graph_internet.jsonnet';
local graph_servers = import 'graph_servers.jsonnet';
local graph_water = import 'graph_water.jsonnet';
local graph_currency = import 'graph_currency.jsonnet';
local graph_health = import 'graph_health.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';
local graph_equity = import 'graph_equity.jsonnet';
local graph_conditions = import 'graph_conditions.jsonnet';
local graph_containers = import 'graph_containers.jsonnet';

{
            
      grafanaDashboardFolder:: 'Private_Mobile',
            
      grafanaDashboards:: {

            network_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Network',
                        uid='network-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['30s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_network.graphs()),


            electricity_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Electricity',
                        uid='electricity-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_electricity.graphs()),


            internet_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Internet',
                        uid='internet-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['20s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_internet.graphs()),


            servers_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Servers',
                        uid='servers-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['10s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_servers.graphs()),


            water_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Water',
                        uid='water-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_water.graphs()),


            currency_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Currency',
                        uid='currency-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-1y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_currency.graphs()),


            health_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Health',
                        uid='health-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['20s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_health.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Interest',
                        uid='interest-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-25y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_interest.graphs()),


            equity_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Equity',
                        uid='equity-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-9M', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_equity.graphs()),


            conditions_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Conditions',
                        uid='conditions-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_conditions.graphs()),


            containers_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Containers',
                        uid='containers-mobile',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'mobile'],
                        time_from='now-1h', refresh='', timepicker=timepicker.new(refresh_intervals=['10s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_containers.graphs()),

  },
}
