local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local timepicker = grafana.timepicker;
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
            
      grafanaDashboardFolder:: 'Public_Tablet',
            
      grafanaDashboards:: {

            currency_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Currency',
                        uid='currency-tablet',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['public', 'tablet'],
                        time_from='now-1y', refresh='', timepicker=timepicker.new(refresh_intervals=['30m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Interest',
                        uid='interest-tablet',
                        editable=false,
                        hideControls=true,
                        graphTooltip='shared_tooltip',
                        tags=['public', 'tablet'],
                        time_from='now-25y', refresh='', timepicker=timepicker.new(refresh_intervals=['30m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
