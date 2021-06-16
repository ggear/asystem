local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
            
//ASM grafanaDashboardFolder:: 'Public_Mobile',
//AST grafanaDashboardFolder:: 'Public_Tablet',
//ASD grafanaDashboardFolder:: 'Public_Desktop',
            
      grafanaDashboards:: {

            currency_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Currency',
//ASM                   uid='currency-mobile',
//AST                   uid='currency-tablet',
//ASD                   uid='currency-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['public', 'mobile'],
//AST                   tags=['public', 'tablet'],
//ASD                   tags=['public', 'desktop'],
                        time_from='now-5y', refresh=''
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Interest',
//ASM                   uid='interest-mobile',
//AST                   uid='interest-tablet',
//ASD                   uid='interest-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['public', 'mobile'],
//AST                   tags=['public', 'tablet'],
//ASD                   tags=['public', 'desktop'],
                        time_from='now-25y', refresh=''
                  )
                  .addPanels(graph_interest.graphs()),

  },
}
