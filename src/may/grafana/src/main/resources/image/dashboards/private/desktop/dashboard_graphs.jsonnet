// WARNING: This file is written by the build process, any manual edits will be lost!

local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local timepicker = grafana.timepicker;
local graph_internet = import 'graph_internet.jsonnet';
local graph_servers = import 'graph_servers.jsonnet';
local graph_containers = import 'graph_containers.jsonnet';
local graph_equity = import 'graph_equity.jsonnet';
local graph_health = import 'graph_health.jsonnet';
local graph_network = import 'graph_network.jsonnet';
local graph_rain = import 'graph_rain.jsonnet';
local graph_diagnostics = import 'graph_diagnostics.jsonnet';
local graph_conditions = import 'graph_conditions.jsonnet';
local graph_control = import 'graph_control.jsonnet';
local graph_electricity = import 'graph_electricity.jsonnet';
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
            
      grafanaDashboardFolder:: 'Private_Desktop',
            
      grafanaDashboards:: {

            internet_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Internet',
                        uid='internet-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['20s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_internet.graphs()),


            servers_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Servers',
                        uid='servers-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-2d', refresh='', timepicker=timepicker.new(refresh_intervals=['10s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_servers.graphs()),


            containers_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Containers',
                        uid='containers-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-1h', refresh='', timepicker=timepicker.new(refresh_intervals=['10s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_containers.graphs()),


            equity_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Equity',
                        uid='equity-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-12M', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_equity.graphs()),


            health_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Health',
                        uid='health-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['20s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_health.graphs()),


            network_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Network',
                        uid='network-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['30s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_network.graphs()),


            rain_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Rain',
                        uid='rain-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_rain.graphs()),


            diagnostics_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Diagnostics',
                        uid='diagnostics-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_diagnostics.graphs()),


            conditions_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Conditions',
                        uid='conditions-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_conditions.graphs()),


            control_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Control',
                        uid='control-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_control.graphs()),


            electricity_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Electricity',
                        uid='electricity-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_electricity.graphs()),


            currency_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Currency',
                        uid='currency-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-1y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Interest',
                        uid='interest-desktop',
                        editable=true,
                        hideControls=false,
                        graphTooltip='shared_tooltip',
                        tags=['private', 'desktop'],
                        time_from='now-25y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
