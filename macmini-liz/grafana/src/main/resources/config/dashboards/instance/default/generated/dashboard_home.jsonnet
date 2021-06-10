local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Default',

      grafanaDashboards:: {

            home_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Home',
                        uid='home-default',
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
                              ) { gridPos: { x: 0, y: 0, w: 6, h: 3 } },

                              dashlist.new(
                                    title='Mobile Dashbaords',
                                    tags=['mobile', 'published'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              ) { gridPos: { x: 0, y: 0, w: 3, h: 20 } },

                              dashlist.new(
                                    title='Desktop Dashbaords',
                                    tags=['desktop', 'published'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              ) { gridPos: { x: 3, y: 0, w: 3, h: 20 } },

                        ],

                  ),

      },
}
