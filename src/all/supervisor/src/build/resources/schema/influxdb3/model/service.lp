################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# supervisor/service [health and utilisation of one service on one host]
#   cadence 6s
#   tag module [always 'supervisor']
#   tag host [name of the host running the service:
#     macmini-mad,
#     macmini-max,
#     macmini-may,
#     macmini-meg,
#     raspbpi-jen,
#     raspbpi-jil]
#   tag service* [name of the monitored service:
#     grafana,
#     homeassistant,
#     influxdb,
#     influxdb3,
#     letsencrypt,
#     mariadb,
#     mlflow,
#     mlserver,
#     network,
#     nginx,
#     openra,
#     plex,
#     postgres,
#     sabnzbd,
#     sonarr,
#     supervisor,
#     tempstat,
#     vernemq,
#     weewx,
#     wrangle,
#     zigbee2mqtt]
#   field status - 6s [service is running and healthy]
#   field status_trend - 6s [service is running and healthy, smoothed across the trend window]
#   field backup_status - 6s [service backup completed]
#   field backup_status_trend - 6s [service backup completed, smoothed across the trend window]
#   field health_status - 6s [service healthcheck passed]
#   field health_status_trend - 6s [service healthcheck passed, smoothed across the trend window]
#   field configured_status - 6s [service is configured as expected]
#   field configured_status_trend - 6s [service is configured as expected, smoothed across the trend window]
#   field name - 6s [service image name] (not persisted)
#   field version - 6s [service image version] (not persisted)
#   field used_processor % 6s [processor used by the service]
#   field used_processor_trend % 6s [processor used by the service, smoothed across the trend window]
#   field used_memory % 6s [memory used by the service against its ceiling]
#   field used_memory_trend % 6s [memory used by the service against its ceiling, smoothed across the trend window]
#   field used_disk_ops % 6s [disk operations used by the service]
#   field used_disk_ops_trend % 6s [disk operations used by the service, smoothed across the trend window]
#   field used_network % 6s [network throughput used by the service]
#   field used_network_trend % 6s [network throughput used by the service, smoothed across the trend window]
#   field up_time s 6s [time the service has been up] (not persisted)
#   field max_memory MiB 6s [memory ceiling configured for the service] (not persisted)
#   field restart_count - 6s [restarts of the service]
#   field restart_count_trend - 6s [restarts of the service, smoothed across the trend window]

supervisor,
  module=supervisor,
  host=<string>,
  service=<string>
    status=<0|1>,
    status_trend=<0|1>,
    backup_status=<0|1>,
    backup_status_trend=<0|1>,
    health_status=<0|1>,
    health_status_trend=<0|1>,
    configured_status=<0|1>,
    configured_status_trend=<0|1>,
    used_processor=<int>,
    used_processor_trend=<int>,
    used_memory=<int>,
    used_memory_trend=<int>,
    used_disk_ops=<int>,
    used_disk_ops_trend=<int>,
    used_network=<int>,
    used_network_trend=<int>,
    restart_count=<float>,
    restart_count_trend=<float>
  <timestamp>
