local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

//ASD grafanaDashboardFolder:: 'Desktop',
//ASM grafanaDashboardFolder:: 'Mobile',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
//ASD                   title='Home',
//ASM                   title='Home',
//ASD                   uid='home-desktop',
//ASM                   uid='home-mobile',
                        editable=true,
                  )
                  .addPanels(

                        local grafana = import 'grafonnet/grafana.libsonnet';
                        local dashboard = grafana.dashboard;
                        local dashlist = grafana.dashlist;

                        [

                              dashlist.new(
//ASM                               title='Mobile Dashbaords',
//ASD                               title='Desktop Dashbaords',
//ASM                               tags=['mobile', 'published'],
//ASD                               tags=['desktop', 'published'],
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
