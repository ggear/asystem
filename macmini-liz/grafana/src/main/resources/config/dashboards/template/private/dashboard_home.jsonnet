local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

//ASM grafanaDashboardFolder:: 'Private_Mobile',
//AST grafanaDashboardFolder:: 'Private_Tablet',
//ASD grafanaDashboardFolder:: 'Private_Desktop',

      grafanaDashboards:: {

            interest_dashboard:
                  dashboard.new(
                        schemaVersion=30,
                        title='Home',
//ASM                   uid='home-mobile',
//AST                   uid='home-tablet',
//ASD                   uid='home-desktop',
//ASM                   editable=false,
//AST                   editable=false,
//ASD                   editable=true,
                        hideControls=true,
                  )
                  .addPanels(

                        local grafana = import 'grafonnet/grafana.libsonnet';
                        local dashboard = grafana.dashboard;
                        local text = grafana.text;
                        local dashlist = grafana.dashlist;

                        [

                              text.new(
//ASM                               title='Mobile Portals',
//AST                               title='Tablet Portals',
//ASD                               title='Desktop Portals',
                                    span=null,
                                    mode='html',
                                    content='
<p style="text-align: center">
      <a href="/">All</a>
          &nbsp;&nbsp;|&nbsp;&nbsp;
//ASM <a href="#" onClick="location.href=\'/d/home-mobile/home?orgId=1\'";return false;">Public</a>
//AST <a href="#" onClick="location.href=\'/d/home-tablet/home?orgId=1\'";return false;">Public</a>
//ASD <a href="#" onClick="location.href=\'/d/home-desktop/home?orgId=1\'";return false;">Public</a>
</p>
                                    ',
                              )
                                  { gridPos: { x: 0, y: 0, w: 8, h: 2 } }
                              ,

                              dashlist.new(
//ASM                               title='Private Mobile Dashboards',
//AST                               title='Private Tablet Dashboards',
//ASD                               title='Private Desktop Dashboards',
//ASM                               tags=['mobile', 'private'],
//AST                               tags=['tablet', 'private'],
//ASD                               tags=['desktop', 'private'],
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
