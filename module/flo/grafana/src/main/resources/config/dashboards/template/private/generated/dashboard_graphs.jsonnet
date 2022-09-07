local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local timepicker = grafana.timepicker;
local graph_internet = import 'graph_internet.jsonnet';
local graph_servers = import 'graph_servers.jsonnet';
local graph_containers = import 'graph_containers.jsonnet';
local graph_equity = import 'graph_equity.jsonnet';
local graph_health = import 'graph_health.jsonnet';
local graph_network = import 'graph_network.jsonnet';
local graph_water = import 'graph_water.jsonnet';
local graph_conditions = import 'graph_conditions.jsonnet';
local graph_electricity = import 'graph_electricity.jsonnet';
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
            
//ASM grafanaDashboardFolder:: 'Private_Mobile',
//AST grafanaDashboardFolder:: 'Private_Tablet',
//ASD grafanaDashboardFolder:: 'Private_Desktop',
            
      grafanaDashboards:: {

            internet_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Internet',
//ASM                   uid='internet-mobile',
//AST                   uid='internet-tablet',
//ASD                   uid='internet-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['20s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_internet.graphs()),


            servers_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Servers',
//ASM                   uid='servers-mobile',
//AST                   uid='servers-tablet',
//ASD                   uid='servers-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-2d', refresh='', timepicker=timepicker.new(refresh_intervals=['10s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_servers.graphs()),


            containers_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Containers',
//ASM                   uid='containers-mobile',
//AST                   uid='containers-tablet',
//ASD                   uid='containers-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-1h', refresh='', timepicker=timepicker.new(refresh_intervals=['10s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_containers.graphs()),


            equity_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Equity',
//ASM                   uid='equity-mobile',
//AST                   uid='equity-tablet',
//ASD                   uid='equity-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-12M', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_equity.graphs()),


            health_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Health',
//ASM                   uid='health-mobile',
//AST                   uid='health-tablet',
//ASD                   uid='health-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['20s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_health.graphs()),


            network_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Network',
//ASM                   uid='network-mobile',
//AST                   uid='network-tablet',
//ASD                   uid='network-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['30s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_network.graphs()),


            water_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Water',
//ASM                   uid='water-mobile',
//AST                   uid='water-tablet',
//ASD                   uid='water-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_water.graphs()),


            conditions_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Conditions',
//ASM                   uid='conditions-mobile',
//AST                   uid='conditions-tablet',
//ASD                   uid='conditions-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_conditions.graphs()),


            electricity_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Electricity',
//ASM                   uid='electricity-mobile',
//AST                   uid='electricity-tablet',
//ASD                   uid='electricity-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
                  )
                  .addPanels(graph_electricity.graphs()),


            currency_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Currency',
//ASM                   uid='currency-mobile',
//AST                   uid='currency-tablet',
//ASD                   uid='currency-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-1y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Interest',
//ASM                   uid='interest-mobile',
//AST                   uid='interest-tablet',
//ASD                   uid='interest-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
//ASM                   hideControls=true,
//AST                   hideControls=true,
//ASD                   hideControls=false,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//AST                   tags=['private', 'tablet'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-25y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
