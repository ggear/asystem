local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

//ASD grafanaDashboardFolder:: 'Private_Desktop',
//ASM grafanaDashboardFolder:: 'Private_Mobile',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Home',
//ASD                   uid='home-desktop',
//ASM                   uid='home-mobile',
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
                                    mode='html',
                                    content='
<ul>
	<li><a href="https://grafana.janeandgraham.com?orgId=1" onClick="window.location.reload(true);return false;">Public Dashbaords</a></li>
	<li><a href="https://grafana.janeandgraham.com?orgId=2" onClick="window.location.reload(true);return false;">Private Dashbaords</a></li>
</ul>
                                    ',
                              ) { gridPos: { x: 0, y: 0, w: 3, h: 3 } },

                              dashlist.new(
                                    title='Dashbaords',
//ASM                               tags=['mobile', 'private'],
//ASD                               tags=['desktop', 'private'],
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
