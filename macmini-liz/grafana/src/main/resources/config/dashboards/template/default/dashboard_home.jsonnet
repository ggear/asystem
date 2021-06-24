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
                        editable=false,
                        hideControls=true,
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
<p style="text-align: center">
      <a href="https://grafana.janeandgraham.com?orgId=1" onClick="window.location.reload(true);return false;">Public</a>
          &nbsp;&nbsp;|&nbsp;&nbsp;
      <a href="https://grafana.janeandgraham.com?orgId=2" onClick="window.location.reload(true);return false;">Private</a>
</p>
                                    ',
                              )
                                  { gridPos: { x: 0, y: 0, w: 24, h: 2 } }
                              ,

                              dashlist.new(
                                    title='Mobile Dashboards',
                                    tags=['mobile'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              )
                                  { gridPos: { x: 0, y: 2, w: 8, h: 20 } }
                              ,

                              dashlist.new(
                                    title='Tablet Dashboards',
                                    tags=['tablet'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              )
                                  { gridPos: { x: 8, y: 2, w: 8, h: 20 } }
                              ,

                              dashlist.new(
                                    title='Desktop Dashboards',
                                    tags=['desktop'],
                                    recent=false,
                                    search=true,
                                    starred=false,
                                    headings=false,
                                    limit=100,
                              )
                                  { gridPos: { x: 16, y: 2, w: 8, h: 20 } }
                              ,

                        ],

                  ),

      },
}
