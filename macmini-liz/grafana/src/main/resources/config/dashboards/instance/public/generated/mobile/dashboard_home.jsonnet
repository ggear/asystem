local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Mobile',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Home',
                        uid='home-mobile',
                        editable=true,
                  )
                  .addPanels(

                        local grafana = import 'grafonnet/grafana.libsonnet';
                        local dashboard = grafana.dashboard;
                        local dashlist = grafana.dashlist;

                        [

                              dashlist.new(
                                    title='Mobile Dashbaords',
                                    tags=['mobile', 'published'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              ) { gridPos: { x: 0, y: 0, w: 3, h: 12 } },

                        ],

                  ),

      },
}
