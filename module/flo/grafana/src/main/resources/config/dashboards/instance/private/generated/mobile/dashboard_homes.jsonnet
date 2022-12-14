local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Private_Default',

      grafanaDashboards:: {

            home_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Home',
                        uid='private-home-default',
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
      <a href="#" onClick="location.href=\'/?orgId=1\'";return false;">Public</a>
          &nbsp;&nbsp;|&nbsp;&nbsp;
      <a href="#" onClick="location.href=\'/?orgId=2\'";return false;">Private</a>
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
