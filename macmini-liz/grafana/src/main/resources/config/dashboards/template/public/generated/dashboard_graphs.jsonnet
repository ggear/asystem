local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
            
//ASD grafanaDashboardFolder:: 'Public_Desktop',
//ASM grafanaDashboardFolder:: 'Public_Mobile',
            
      grafanaDashboards:: {

            currency_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Currency',
//ASM                   uid='currency-mobile',
//ASD                   uid='currency-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['public', 'mobile'],
//ASD                   tags=['public', 'desktop'],
                        time_from='now-5y', refresh=''
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Interest',
//ASM                   uid='interest-mobile',
//ASD                   uid='interest-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['public', 'mobile'],
//ASD                   tags=['public', 'desktop'],
                        time_from='now-25y', refresh=''
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
