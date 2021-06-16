local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Public_Mobile',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Home',
                        uid='home-mobile',
                        editable=false,
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
                              ) { gridPos: { x: 0, y: 0, w: 8, h: 3 } },

                              dashlist.new(
                                    title='Public Mobile Dashbaords',
                                    tags=['mobile', 'public'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              ) { gridPos: { x: 0, y: 3, w: 8, h: 20 } },

                        ],

                  ),

      },
}
