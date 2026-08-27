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
#     cloudflare,
#     grafana,
#     homeassistant,
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
#     tasmota,
#     tempstat,
#     vernemq,
#     weewx,
#     wrangle,
#     zigbee2mqtt]
#   field status - 6s [service is running and reporting metrics]
#   field status_trend - 6s [service is running and reporting metrics, smoothed across the trend window]
#   field backup_status - 6s [service backup completed, always true until implemented]
#   field backup_status_trend - 6s [service backup completed, always true until implemented, smoothed across the trend window]
#   field health_status - 6s [service container healthcheck reported healthy]
#   field health_status_trend - 6s [service container healthcheck reported healthy, smoothed across the trend window]
#   field configured_status - 6s [service is configured as expected, not yet implemented]
#   field configured_status_trend - 6s [service is configured as expected, not yet implemented, smoothed across the trend window]
#   field name - 6s [service container name] (not persisted)
#   field version - 6s [service version, from the container image tag or the installed environment] (not persisted)
#   field used_processor % 6s [processor time used by the service across all cores]
#   field used_processor_trend % 6s [processor time used by the service across all cores, smoothed across the trend window]
#   field used_memory % 6s [memory in use by the service, excluding page cache, against its ceiling]
#   field used_memory_trend % 6s [memory in use by the service, excluding page cache, against its ceiling, smoothed across the trend window]
#   field used_disk_ops % 6s [block device throughput used by the service against a 100 MiB per second budget]
#   field used_disk_ops_trend % 6s [block device throughput used by the service against a 100 MiB per second budget, smoothed across the trend window]
#   field used_network % 6s [network throughput used by the service against a 1000 Mbit per second budget]
#   field used_network_trend % 6s [network throughput used by the service against a 1000 Mbit per second budget, smoothed across the trend window]
#   field up_time s 6s [time the service container has been running] (not persisted)
#   field max_memory MiB 6s [memory ceiling declared for the service in its compose file] (not persisted)
#   field restart_count - 6s [restarts of the service container since it was created]
#   field restart_count_trend - 6s [restarts of the service container since it was created, smoothed across the trend window]

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
