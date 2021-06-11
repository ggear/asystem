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
                                    mode='html',
                                    content='
<ul>
	<li><a href="https://grafana.janeandgraham.com?orgId=1" onClick="window.location.reload(true);return false;">Public Dashbaords</a></li>
	<li><a href="https://grafana.janeandgraham.com?orgId=2" onClick="window.location.reload(true);return false;">Private Dashbaords</a></li>
</ul>
                                    ',
                              ) { gridPos: { x: 0, y: 0, w: 6, h: 3 } },

                              dashlist.new(
                                    title='Dashbaords',
                                    tags=['mobile'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              ) { gridPos: { x: 0, y: 0, w: 3, h: 20 } },

                              dashlist.new(
                                    title='Dashbaords',
                                    tags=['desktop'],
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
