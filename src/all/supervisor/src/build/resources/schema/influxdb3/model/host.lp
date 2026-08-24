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
#   field status - 6s [host is reporting metrics]
#   field status_trend - 6s [host is reporting metrics, smoothed across the trend window]
#   field used_processor % 6s [processor time used across all cores of the host]
#   field used_processor_trend % 6s [processor time used across all cores of the host, smoothed across the trend window]
#   field used_memory % 6s [memory in use as a share of the total memory of the host]
#   field used_memory_trend % 6s [memory in use as a share of the total memory of the host, smoothed across the trend window]
#   field allocated_memory % 6s [memory ceilings of the installed services as a share of the total memory of the host, capped at one hundred]
#   field allocated_memory_trend % 6s [memory ceilings of the installed services as a share of the total memory of the host, capped at one hundred, smoothed across the trend window]
#   field failed_log_messages % 6s [kernel log messages at error level within the trend window, as a share of a ten message budget]
#   field failed_log_messages_trend % 6s [kernel log messages at error level within the trend window, as a share of a ten message budget, smoothed across the trend window]
#   field failed_shares - 6s [shares failing to mount or report, not yet implemented and always zero]
#   field failed_shares_trend - 6s [shares failing to mount or report, not yet implemented and always zero, smoothed across the trend window]
#   field failed_backups - 6s [backups failing to complete, not yet implemented and always zero]
#   field failed_backups_trend - 6s [backups failing to complete, not yet implemented and always zero, smoothed across the trend window]
#   field warn_temperature_of_max % 6s [hottest processor temperature as a share of its warning ceiling, zero at forty degrees and full at sixty degrees]
#   field warn_temperature_of_max_trend % 6s [hottest processor temperature as a share of its warning ceiling, zero at forty degrees and full at sixty degrees, smoothed across the trend window]
#   field spin_fan_speed_of_max % 6s [fastest fan speed as a share of its rated maximum speed]
#   field spin_fan_speed_of_max_trend % 6s [fastest fan speed as a share of its rated maximum speed, smoothed across the trend window]
#   field life_used_drives % 6s [life used by the most worn drive, not yet implemented and always zero]
#   field life_used_drives_trend % 6s [life used by the most worn drive, not yet implemented and always zero, smoothed across the trend window]
#   field used_system_space % 6s [system volume space used, not yet implemented and always zero]
#   field used_system_space_trend % 6s [system volume space used, not yet implemented and always zero, smoothed across the trend window]
#   field used_share_space % 6s [share volume space used, not yet implemented and always zero]
#   field used_share_space_trend % 6s [share volume space used, not yet implemented and always zero, smoothed across the trend window]
#   field used_backup_space % 6s [backup volume space used, not yet implemented and always zero]
#   field used_backup_space_trend % 6s [backup volume space used, not yet implemented and always zero, smoothed across the trend window]
#   field used_swap_space % 6s [swap space used, not yet implemented and always zero]
#   field used_swap_space_trend % 6s [swap space used, not yet implemented and always zero, smoothed across the trend window]
#   field used_disk_ops % 6s [disk operations used against capacity, not yet implemented and always zero]
#   field used_disk_ops_trend % 6s [disk operations used against capacity, not yet implemented and always zero, smoothed across the trend window]
#   field used_network % 6s [network throughput used against capacity, not yet implemented and always zero]
#   field used_network_trend % 6s [network throughput used against capacity, not yet implemented and always zero, smoothed across the trend window]
#   field running_time s 6s [time the host has been up, not yet implemented and always zero] (not persisted)
#   field temperature °C 6s [hottest processor temperature, from the package sensor, the system on chip sensor or a drive sensor offset upwards]
#   field temperature_trend °C 6s [hottest processor temperature, from the package sensor, the system on chip sensor or a drive sensor offset upwards, smoothed across the trend window]
#   field services - 6s [every service configured for the host is running and healthy] (not persisted)
#   field services_max_memory MiB 6s [memory ceilings summed across the installed services configured for the host] (not persisted)

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
