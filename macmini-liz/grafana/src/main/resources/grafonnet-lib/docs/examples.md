# Examples

Simple Grafana 5.x dashboard:

Please note that the layout has changed, no `row` objects and new possible
nesting of `panel` objects. You need to set `schemaVersion` parameter on
dashboard object to at least 16.

```jsonnet
local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local row = grafana.row;
local singlestat = grafana.singlestat;
local prometheus = grafana.prometheus;
local template = grafana.template;

dashboard.new(
  'JVM',
  schemaVersion=16,
  tags=['java'],
)
.addTemplate(
  grafana.template.datasource(
    'PROMETHEUS_DS',
    'prometheus',
    'Prometheus',
    hide='label',
  )
)
.addTemplate(
  template.new(
    'env',
    '$PROMETHEUS_DS',
    'label_values(jvm_threads_current, env)',
    label='Environment',
    refresh='time',
  )
)
.addTemplate(
  template.new(
    'job',
    '$PROMETHEUS_DS',
    'label_values(jvm_threads_current{env="$env"}, job)',
    label='Job',
    refresh='time',
  )
)
.addTemplate(
  template.new(
    'instance',
    '$PROMETHEUS_DS',
    'label_values(jvm_threads_current{env="$env",job="$job"}, instance)',
    label='Instance',
    refresh='time',
  )
)
.addPanel(
  singlestat.new(
    'uptime',
    format='s',
    datasource='Prometheus',
    span=2,
    valueName='current',
  )
  .addTarget(
    prometheus.target(
      'time() - process_start_time_seconds{env="$env", job="$job", instance="$instance"}',
    )
  ), gridPos={
    x: 0,
    y: 0,
    w: 24,
    h: 3,
  }
)
```

Simple Grafana 4.x dashboard:

```jsonnet
local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local row = grafana.row;
local singlestat = grafana.singlestat;
local prometheus = grafana.prometheus;
local template = grafana.template;

dashboard.new(
  'JVM',
  tags=['java'],
)
.addTemplate(
  grafana.template.datasource(
    'PROMETHEUS_DS',
    'prometheus',
    'Prometheus',
    hide='label',
  )
)
.addTemplate(
  template.new(
    'env',
    '$PROMETHEUS_DS',
    'label_values(jvm_threads_current, env)',
    label='Environment',
    refresh='time',
  )
)
.addTemplate(
  template.new(
    'job',
    '$PROMETHEUS_DS',
    'label_values(jvm_threads_current{env="$env"}, job)',
    label='Job',
    refresh='time',
  )
)
.addTemplate(
  template.new(
    'instance',
    '$PROMETHEUS_DS',
    'label_values(jvm_threads_current{env="$env",job="$job"}, instance)',
    label='Instance',
    refresh='time',
  )
)
.addRow(
  row.new()
  .addPanel(
    singlestat.new(
      'uptime',
      format='s',
      datasource='Prometheus',
      span=2,
      valueName='current',
    )
    .addTarget(
      prometheus.target(
        'time() - process_start_time_seconds{env="$env", job="$job", instance="$instance"}',
      )
    )
  )
)
```

Find more examples in the repo [examples](https://github.com/grafana/grafonnet-lib/tree/master/examples) directory.
