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
#   field used_processor % 6s [processor time used across all cores]
#   field used_processor_trend % 6s [processor time used across all cores, smoothed across the trend window]
#   field used_memory % 6s [memory in use against the total fitted]
#   field used_memory_trend % 6s [memory in use against the total fitted, smoothed across the trend window]
#   field allocated_memory % 6s [memory ceilings of the installed services against the total fitted, capped at 100]
#   field allocated_memory_trend % 6s [memory ceilings of the installed services against the total fitted, capped at 100, smoothed across the trend window]
#   field failed_log_messages % 6s [kernel errors in the trend window against a 10 message budget]
#   field failed_log_messages_trend % 6s [kernel errors in the trend window against a 10 message budget, smoothed across the trend window]
#   field failed_shares % 6s [declared shares failing to mount or report, against those declared]
#   field failed_shares_trend % 6s [declared shares failing to mount or report, against those declared, smoothed across the trend window]
#   field failed_backups - 6s [backups failing to complete, not yet implemented]
#   field failed_backups_trend - 6s [backups failing to complete, not yet implemented, smoothed across the trend window]
#   field warn_temperature % 6s [hottest processor temperature against its warning ceiling, zero at 40 and full at 60 degrees]
#   field warn_temperature_trend % 6s [hottest processor temperature against its warning ceiling, zero at 40 and full at 60 degrees, smoothed across the trend window]
#   field spin_fan_speed % 6s [fastest fan speed against its rated maximum]
#   field spin_fan_speed_trend % 6s [fastest fan speed against its rated maximum, smoothed across the trend window]
#   field life_used_drives % 6s [rated endurance consumed by the most worn drive]
#   field life_used_drives_trend % 6s [rated endurance consumed by the most worn drive, smoothed across the trend window]
#   field used_home_space % 6s [space used by the volume holding the asystem home]
#   field used_home_space_trend % 6s [space used by the volume holding the asystem home, smoothed across the trend window]
#   field used_share_space % 6s [space used across the local share volumes, summed as one pool]
#   field used_share_space_trend % 6s [space used across the local share volumes, summed as one pool, smoothed across the trend window]
#   field used_backup_space % 6s [backup volume space used, not yet implemented]
#   field used_backup_space_trend % 6s [backup volume space used, not yet implemented, smoothed across the trend window]
#   field used_swap_space % 6s [swap space used, not yet implemented]
#   field used_swap_space_trend % 6s [swap space used, not yet implemented, smoothed across the trend window]
#   field used_disk_ops % 6s [disk operations used against capacity, not yet implemented]
#   field used_disk_ops_trend % 6s [disk operations used against capacity, not yet implemented, smoothed across the trend window]
#   field used_network % 6s [network throughput used against capacity, not yet implemented]
#   field used_network_trend % 6s [network throughput used against capacity, not yet implemented, smoothed across the trend window]
#   field running_time s 6s [time the host has been up, not yet implemented] (not persisted)
#   field temperature °C 6s [hottest processor temperature, from the package, system on chip or offset drive sensor]
#   field temperature_trend °C 6s [hottest processor temperature, from the package, system on chip or offset drive sensor, smoothed across the trend window]
#   field services - 6s [every configured service is running and healthy] (not persisted)
#   field services_max_memory MiB 6s [memory ceilings summed across the configured services] (not persisted)
#   field failed_drives % 6s [drives reporting new errors since discovery, against those fitted]
#   field failed_drives_trend % 6s [drives reporting new errors since discovery, against those fitted, smoothed across the trend window]

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
    warn_temperature=<int>,
    warn_temperature_trend=<int>,
    spin_fan_speed=<int>,
    spin_fan_speed_trend=<int>,
    life_used_drives=<int>,
    life_used_drives_trend=<int>,
    used_home_space=<int>,
    used_home_space_trend=<int>,
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
    temperature_trend=<float>,
    failed_drives=<int>,
    failed_drives_trend=<int>
  <timestamp>
