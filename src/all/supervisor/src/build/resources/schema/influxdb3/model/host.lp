################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# supervisor/host [health and utilisation of one host]
#   cadence 6s
#   tag module [always 'supervisor']
#   tag host* [name of the monitored host:
#     macmini-mad,
#     macmini-max,
#     macmini-may,
#     macmini-meg,
#     raspbpi-jen,
#     raspbpi-jil]
#   field status - 6s [host is reachable and healthy]
#   field status_trend - 6s [host is reachable and healthy, smoothed across the trend window]
#   field used_processor % 6s [processor used across the host]
#   field used_processor_trend % 6s [processor used across the host, smoothed across the trend window]
#   field used_memory % 6s [memory used across the host]
#   field used_memory_trend % 6s [memory used across the host, smoothed across the trend window]
#   field allocated_memory % 6s [memory allocated to services across the host]
#   field allocated_memory_trend % 6s [memory allocated to services across the host, smoothed across the trend window]
#   field failed_log_messages % 6s [kernel log messages at error level over the trend window, as a share of a ten message budget]
#   field failed_log_messages_trend % 6s [kernel log messages at error level over the trend window, as a share of a ten message budget, smoothed across the trend window]
#   field failed_shares - 6s [shares failing to mount or report]
#   field failed_shares_trend - 6s [shares failing to mount or report, smoothed across the trend window]
#   field failed_backups - 6s [backups failing to complete]
#   field failed_backups_trend - 6s [backups failing to complete, smoothed across the trend window]
#   field warn_temperature_of_max % 6s [hottest drive temperature as a share of its warning threshold]
#   field warn_temperature_of_max_trend % 6s [hottest drive temperature as a share of its warning threshold, smoothed across the trend window]
#   field spin_fan_speed_of_max % 6s [fastest fan speed as a share of its maximum]
#   field spin_fan_speed_of_max_trend % 6s [fastest fan speed as a share of its maximum, smoothed across the trend window]
#   field life_used_drives % 6s [most worn drive life used]
#   field life_used_drives_trend % 6s [most worn drive life used, smoothed across the trend window]
#   field used_system_space % 6s [system volume space used]
#   field used_system_space_trend % 6s [system volume space used, smoothed across the trend window]
#   field used_share_space % 6s [share volume space used]
#   field used_share_space_trend % 6s [share volume space used, smoothed across the trend window]
#   field used_backup_space % 6s [backup volume space used]
#   field used_backup_space_trend % 6s [backup volume space used, smoothed across the trend window]
#   field used_swap_space % 6s [swap space used]
#   field used_swap_space_trend % 6s [swap space used, smoothed across the trend window]
#   field used_disk_ops % 6s [disk operations used against capacity]
#   field used_disk_ops_trend % 6s [disk operations used against capacity, smoothed across the trend window]
#   field used_network % 6s [network throughput used against capacity]
#   field used_network_trend % 6s [network throughput used against capacity, smoothed across the trend window]
#   field running_time s 6s [time the host has been up] (not persisted)
#   field temperature °C 6s [hottest drive temperature]
#   field temperature_trend °C 6s [hottest drive temperature, smoothed across the trend window]
#   field services - 6s [every service on the host is healthy] (not persisted)
#   field services_max_memory MiB 6s [memory ceiling summed across the services on the host] (not persisted)

supervisor,
  module=supervisor,
  host=<string>
    status=<0|1>,
    status_trend=<0|1>,
    used_processor=<int>,
    used_processor_trend=<int>,
    used_memory=<int>,
    used_memory_trend=<int>,
    allocated_memory=<int>,
    allocated_memory_trend=<int>,
    failed_log_messages=<int>,
    failed_log_messages_trend=<int>,
    failed_shares=<int>,
    failed_shares_trend=<int>,
    failed_backups=<int>,
    failed_backups_trend=<int>,
    warn_temperature_of_max=<int>,
    warn_temperature_of_max_trend=<int>,
    spin_fan_speed_of_max=<int>,
    spin_fan_speed_of_max_trend=<int>,
    life_used_drives=<int>,
    life_used_drives_trend=<int>,
    used_system_space=<int>,
    used_system_space_trend=<int>,
    used_share_space=<int>,
    used_share_space_trend=<int>,
    used_backup_space=<int>,
    used_backup_space_trend=<int>,
    used_swap_space=<int>,
    used_swap_space_trend=<int>,
    used_disk_ops=<int>,
    used_disk_ops_trend=<int>,
    used_network=<int>,
    used_network_trend=<int>,
    temperature=<float>,
    temperature_trend=<float>
  <timestamp>
