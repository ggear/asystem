local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
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
                        graphTooltip='shared_tooltip',
                        tags=['public', 'tablet'],
                        time_from='now-5y', refresh=''
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Interest',
                        uid='interest-tablet',
                        editable=false,
                        graphTooltip='shared_tooltip',
                        tags=['public', 'tablet'],
                        time_from='now-25y', refresh=''
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
