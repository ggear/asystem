local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Desktop',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Home',
                        uid='home-desktop',
                        editable=true,
                  )
                  .addPanels(

                        local grafana = import 'grafonnet/grafana.libsonnet';
                        local dashboard = grafana.dashboard;
                        local dashlist = grafana.dashlist;

                        [

                              dashlist.new(
                                    title='Desktop Dashbaords',
                                    tags=['desktop', 'published'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              ) { gridPos: { x: 0, y: 0, w: 3, h: 20 } },

                        ],

                  ),

      },
}
