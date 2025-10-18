#!/bin/bash

mapfile -t host_stats < <(
  awk '/MemAvailable/ {mem=$2} /SwapFree/ {swap=$2} END {print mem, swap}' /proc/meminfo | while read mem swap; do
    mem_total=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
    mem_percent=$(awk "BEGIN {printf \"%.1f\", ($mem_total-$mem)/$mem_total*100}")
    disk_used=$(df / | awk 'NR==2 {printf "%.1f", 100-$4/$2*100}')
    cpu=$(mpstat 1 2 | awk '/Average/ {printf "%.1f", 100 - $12}')
    swap_total=$(awk '/SwapTotal/ {print $2}' /proc/meminfo)
    swap_percent=$(awk "BEGIN {printf \"%.1f\", ($swap_total-$swap)/$swap_total*100}")
    max_temp=$(sensors | awk '/^Core/ {gsub(/\+/,""); gsub(/°C/,""); print $3}' | sort -nr | head -n1)
    temp_percent=$(awk -v t="$max_temp" -v m=90 'BEGIN {printf "%.1f", (t/m)*100}')
    downtime_percent=$(tuptime | awk '/System uptime:/ {for(i=1;i<=NF;i++){if($i ~ /%$/){gsub("%","",$i); up=$i}}} END {dp=100-up; if(dp<0) dp=0; if(dp>100) dp=100; printf "%.1f", dp}')
    echo "Down Tme=${downtime_percent}%"
    echo "Used Mem=${mem_percent}%"
    echo "Temp Max=${temp_percent}%"
    echo "Used Swp=${swap_percent}%"
    echo "Used CPU=${cpu}%"
    echo "Used Dsk=${disk_used}%"
  done
)
mapfile -t container_stats < <(docker ps --format "{{.Names}}\t{{.Status}}")

# Optimise for tput cols=64, tput lines=10
print_stats() {
  local -n arr=$1
  local heading1=$2
  local heading2=$3
  local column_width=$4
  local num_cols=$5
  local RED='\033[0;31m'
  local GREEN='\033[0;32m'
  local NC='\033[0m'
  local term_width
  local count=0 key value color
  for item in "${arr[@]}"; do
    case "$item" in
    *$'\t'*)
      key=${item%%$'\t'*}
      value=${item#*$'\t'}
      ;;
    *=*)
      key=${item%%=*}
      value=${item#*=}
      ;;
    *)
      key=$item
      value=""
      ;;
    esac
    if [[ "$value" == *"unhealthy"* ]] || [[ "$value" =~ ^([8-9][0-9]|100)\.%?$ ]]; then
      color=$RED
    else
      color=$GREEN
    fi
    printf "%-${column_width}s${color}%-${column_width}s${NC}" "$key" "$value"
    ((count++))
    if ((count % num_cols == 0)); then
      printf '\n'
    fi
  done
  ((count % num_cols != 0)) && printf '\n'
}

print_stats host_stats "Host" "Metric" 15 2
printf '%*s\n' "$(( $(tput cols + 0 ))" '' | tr ' ' '-'
print_stats container_stats "Container" "Status" 15 1
