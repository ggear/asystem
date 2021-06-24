local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Private_Desktop',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Home',
                        uid='home-desktop',
                        editable=true,
                        hideControls=true,
                  )
                  .addPanels(

                        local grafana = import 'grafonnet/grafana.libsonnet';
                        local dashboard = grafana.dashboard;
                        local text = grafana.text;
                        local dashlist = grafana.dashlist;

                        [

                              text.new(
                                    title='Private Desktop Portals',
                                    span=null,
                                    mode='html',
                                    content='
<p style="text-align: center">
      <a href="https://grafana.janeandgraham.com/d/home-desktop/home?orgId=1" onClick="window.location.reload(true);return false;">Public</a>
          &nbsp;&nbsp;|&nbsp;&nbsp;
      <a href="https://grafana.janeandgraham.com/d/home-desktop/home?orgId=2" onClick="window.location.reload(true);return false;">Private</a>
</p>
                                    ',
                              )
                                  { gridPos: { x: 0, y: 0, w: 8, h: 2 } }
                              ,

                              dashlist.new(
                                    title='Private Desktop Dashboards',
                                    tags=['desktop', 'private'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              )
                                  { gridPos: { x: 0, y: 3, w: 8, h: 20 } }
                              ,

                        ],

                  ),

      },
}
