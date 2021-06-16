local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local graph_network = import 'graph_network.jsonnet';
local graph_electricity = import 'graph_electricity.jsonnet';
local graph_servers = import 'graph_servers.jsonnet';
local graph_water = import 'graph_water.jsonnet';
local graph_currency = import 'graph_currency.jsonnet';
local graph_interest = import 'graph_interest.jsonnet';
local graph_internet = import 'graph_internet.jsonnet';
local graph_conditions = import 'graph_conditions.jsonnet';
local graph_containers = import 'graph_containers.jsonnet';

{
            
//ASD grafanaDashboardFolder:: 'Private_Desktop',
//ASM grafanaDashboardFolder:: 'Private_Mobile',
            
      grafanaDashboards:: {

            network_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Network',
//ASM                   uid='network-mobile',
//ASD                   uid='network-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-2d', refresh=''
                  )
                  .addPanels(graph_network.graphs()),


            electricity_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Electricity',
//ASM                   uid='electricity-mobile',
//ASD                   uid='electricity-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_electricity.graphs()),


            servers_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Servers',
//ASM                   uid='servers-mobile',
//ASD                   uid='servers-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-2d', refresh=''
                  )
                  .addPanels(graph_servers.graphs()),


            water_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Water',
//ASM                   uid='water-mobile',
//ASD                   uid='water-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_water.graphs()),


            currency_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Currency',
//ASM                   uid='currency-mobile',
//ASD                   uid='currency-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-5y', refresh=''
                  )
                  .addPanels(graph_currency.graphs()),


            interest_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Interest',
//ASM                   uid='interest-mobile',
//ASD                   uid='interest-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-25y', refresh=''
                  )
                  .addPanels(graph_interest.graphs()),


            internet_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Internet',
//ASM                   uid='internet-mobile',
//ASD                   uid='internet-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-2d', refresh=''
                  )
                  .addPanels(graph_internet.graphs()),


            conditions_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Conditions',
//ASM                   uid='conditions-mobile',
//ASD                   uid='conditions-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-7d', refresh=''
                  )
                  .addPanels(graph_conditions.graphs()),


            containers_dashboard:
                  dashboard.new(
                        schemaVersion=26,
                        title='Containers',
//ASM                   uid='containers-mobile',
//ASD                   uid='containers-desktop',
//ASM                   editable=false,
//ASD                   editable=true,
                        graphTooltip='shared_tooltip',
//ASM                   tags=['private', 'mobile'],
//ASD                   tags=['private', 'desktop'],
                        time_from='now-1h', refresh=''
                  )
                  .addPanels(graph_containers.graphs()),

  },
}
