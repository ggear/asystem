local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Public_Desktop',

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
                        local text = grafana.text;
                        local dashlist = grafana.dashlist;

                        [

                              text.new(
                                    title='Portals',
                                    span=null,
                                    mode='markdown',
                                    content='
- [Public Dashbaords](https://grafana.janeandgraham.com?orgId=1)
- [Private Dashbaords](https://grafana.janeandgraham.com?orgId=2)
                                    ',
                              ) { gridPos: { x: 0, y: 0, w: 3, h: 3 } },

                              dashlist.new(
                                    title='Dashbaords',
                                    tags=['desktop', 'public'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              ) { gridPos: { x: 0, y: 3, w: 3, h: 20 } },

                        ],

                  ),

      },
}
