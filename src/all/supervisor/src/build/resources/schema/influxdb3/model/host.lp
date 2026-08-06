################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# supervisor/host [health and utilisation of one host]
#   cadence 6s
#   tag host* [name of the monitored host]
#   entity macmini-mad, macmini-max, macmini-may, macmini-meg, raspbpi-jen, raspbpi-jil
#   field status state 6s [host is reachable and healthy]
#   field status_trend state 6s [host is reachable and healthy, smoothed across the trend window]
#   field used_processor percent 6s [processor used across the host]
#   field used_processor_trend percent 6s [processor used across the host, smoothed across the trend window]
#   field used_memory percent 6s [memory used across the host]
#   field used_memory_trend percent 6s [memory used across the host, smoothed across the trend window]
#   field allocated_memory percent 6s [memory allocated to services across the host]
#   field allocated_memory_trend percent 6s [memory allocated to services across the host, smoothed across the trend window]
#   field failed_log_messages count 6s [log messages logged at error level]
#   field failed_log_messages_trend count 6s [log messages logged at error level, smoothed across the trend window]
#   field failed_shares count 6s [shares failing to mount or report]
#   field failed_shares_trend count 6s [shares failing to mount or report, smoothed across the trend window]
#   field failed_backups count 6s [backups failing to complete]
#   field failed_backups_trend count 6s [backups failing to complete, smoothed across the trend window]
#   field warn_temperature_of_max percent 6s [hottest drive temperature as a share of its warning threshold]
#   field warn_temperature_of_max_trend percent 6s [hottest drive temperature as a share of its warning threshold, smoothed across the trend window]
#   field spin_fan_speed_of_max percent 6s [fastest fan speed as a share of its maximum]
#   field spin_fan_speed_of_max_trend percent 6s [fastest fan speed as a share of its maximum, smoothed across the trend window]
#   field life_used_drives percent 6s [most worn drive life used]
#   field life_used_drives_trend percent 6s [most worn drive life used, smoothed across the trend window]
#   field used_system_space percent 6s [system volume space used]
#   field used_system_space_trend percent 6s [system volume space used, smoothed across the trend window]
#   field used_share_space percent 6s [share volume space used]
#   field used_share_space_trend percent 6s [share volume space used, smoothed across the trend window]
#   field used_backup_space percent 6s [backup volume space used]
#   field used_backup_space_trend percent 6s [backup volume space used, smoothed across the trend window]
#   field used_swap_space percent 6s [swap space used]
#   field used_swap_space_trend percent 6s [swap space used, smoothed across the trend window]
#   field used_disk_ops percent 6s [disk operations used against capacity]
#   field used_disk_ops_trend percent 6s [disk operations used against capacity, smoothed across the trend window]
#   field used_network percent 6s [network throughput used against capacity]
#   field used_network_trend percent 6s [network throughput used against capacity, smoothed across the trend window]
#   field running_time seconds 6s [time the host has been up] (not persisted)
#   field temperature Celsius 6s [hottest drive temperature]
#   field temperature_trend Celsius 6s [hottest drive temperature, smoothed across the trend window]
#   field services state 6s [every service on the host is healthy] (not persisted)
#   field services_max_memory megabytes 6s [memory ceiling summed across the services on the host] (not persisted)

supervisor,host=<host>
    status=<0|1>i,
    status_trend=<0|1>i,
    used_processor=<number>i,
    used_processor_trend=<number>i,
    used_memory=<number>i,
    used_memory_trend=<number>i,
    allocated_memory=<number>i,
    allocated_memory_trend=<number>i,
    failed_log_messages=<number>i,
    failed_log_messages_trend=<number>i,
    failed_shares=<number>i,
    failed_shares_trend=<number>i,
    failed_backups=<number>i,
    failed_backups_trend=<number>i,
    warn_temperature_of_max=<number>i,
    warn_temperature_of_max_trend=<number>i,
    spin_fan_speed_of_max=<number>i,
    spin_fan_speed_of_max_trend=<number>i,
    life_used_drives=<number>i,
    life_used_drives_trend=<number>i,
    used_system_space=<number>i,
    used_system_space_trend=<number>i,
    used_share_space=<number>i,
    used_share_space_trend=<number>i,
    used_backup_space=<number>i,
    used_backup_space_trend=<number>i,
    used_swap_space=<number>i,
    used_swap_space_trend=<number>i,
    used_disk_ops=<number>i,
    used_disk_ops_trend=<number>i,
    used_network=<number>i,
    used_network_trend=<number>i,
    temperature=<number>,
    temperature_trend=<number>
    <timestamp>
