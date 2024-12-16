// WARNING: This file is written by the build process, any manual edits will be lost!

local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local timepicker = grafana.timepicker;
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
            
//ASM grafanaDashboardFolder:: 'Public_Mobile',
//AST grafanaDashboardFolder:: 'Public_Tablet',
//ASD grafanaDashboardFolder:: 'Public_Desktop',
            
      grafanaDashboards:: {

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
//ASM                   tags=['public', 'mobile'],
//AST                   tags=['public', 'tablet'],
//ASD                   tags=['public', 'desktop'],
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
//ASM                   tags=['public', 'mobile'],
//AST                   tags=['public', 'tablet'],
//ASD                   tags=['public', 'desktop'],
                        time_from='now-25y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
