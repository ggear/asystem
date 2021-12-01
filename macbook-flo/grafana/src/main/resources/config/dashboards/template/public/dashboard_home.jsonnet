local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

{

//ASM grafanaDashboardFolder:: 'Public_Mobile',
//AST grafanaDashboardFolder:: 'Public_Tablet',
//ASD grafanaDashboardFolder:: 'Public_Desktop',

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
//ASM <a href="#" onClick="location.href=\'/d/home-mobile/home?orgId=2\'";return false;">Private</a>
//AST <a href="#" onClick="location.href=\'/d/home-tablet/home?orgId=2\'";return false;">Private</a>
//ASD <a href="#" onClick="location.href=\'/d/home-desktop/home?orgId=2\'";return false;">Private</a>
</p>
                                    ',
                              )
                                  { gridPos: { x: 0, y: 0, w: 8, h: 2 } }
                              ,

                              dashlist.new(
//ASM                               title='Public Mobile Dashboards',
//AST                               title='Public Tablet Dashboards',
//ASD                               title='Public Desktop Dashboards',
//ASM                               tags=['mobile', 'public'],
//AST                               tags=['tablet', 'public'],
//ASD                               tags=['desktop', 'public'],
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
