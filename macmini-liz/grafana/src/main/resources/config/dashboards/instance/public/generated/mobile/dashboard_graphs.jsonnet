local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
            
      grafanaDashboardFolder:: 'Mobile',
            
      grafanaDashboards:: {

            currency_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Currency',
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
                        title='Interest',
                        uid='interest-mobile',
                        editable=true,
                        graphTooltip='shared_tooltip',
                        tags=['published', 'mobile'],
                        time_from='now-5y', refresh=''
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
