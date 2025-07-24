// WARNING: This file is written by the build process, any manual edits will be lost!

local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

      grafanaDashboardFolder:: 'Private_Tablet',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Home',
                        uid='home-tablet',
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
                                    title='Tablet Portals',
                                    span=null,
                                    mode='html',
                                    content='
<p style="text-align: center">
      <a href="#" onClick="location.href=\'/?kiosk=1\'";return false;">All</a>
          &nbsp;&nbsp;|&nbsp;&nbsp;
      <a href="#" onClick="location.href=\'/d/home-tablet/home?orgId=1\'";return false;">Public</a>
</p>
                                    ',
                              )
                                  { gridPos: { x: 0, y: 0, w: 8, h: 2 } }
                              ,

                              dashlist.new(
                                    title='Private Tablet Dashboards',
                                    tags=['tablet', 'private'],
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
