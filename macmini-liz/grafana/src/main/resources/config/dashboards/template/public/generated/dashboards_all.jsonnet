local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';

{
  grafanaDashboards:: {

    currency_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Currency (Desktop)',
// GRAPH_MOBILE:         title='Currency (Mobile)',
// GRAPH_DESKTOP:         uid='currency-dekstop',
// GRAPH_MOBILE:         uid='currency-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-5y', refresh=''
      )
      .addPanels(graph_currency.graphs()),


    interest_dashboard:
      dashboard.new(
        schemaVersion=26,
// GRAPH_DESKTOP:         title='Interest (Desktop)',
// GRAPH_MOBILE:         title='Interest (Mobile)',
// GRAPH_DESKTOP:         uid='interest-dekstop',
// GRAPH_MOBILE:         uid='interest-mobile',
        editable=true,
        graphTooltip='shared_tooltip',
// GRAPH_DESKTOP:         tags=['published', 'desktop'],
// GRAPH_MOBILE:         tags=['published', 'mobile'],
        time_from='now-5y', refresh=''
      )
      .addPanels(graph_interest.graphs()),

  },
}
