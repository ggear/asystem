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
    uptime_seconds=$(awk '{print $1}' /proc/uptime)
    downtime_percent=$(awk -v up="$uptime_seconds" 'BEGIN {printf "%.1f", (1-(up/(30*24*60*60)))*100}')
    echo "Down Tme=${downtime_percent}%"
    echo "Used Mem=${mem_percent}%"
    echo "Temp Max=${temp_percent}%"
    echo "Used Swp=${swap_percent}%"
    echo "Used CPU=${cpu}%"
    echo "Used Dsk=${disk_used}%"
  done
)
mapfile -t container_stats < <(docker ps --format "{{.Names}}\t{{.Status}}")

print_stats() {
  local -n arr=$1
  local heading1=$2
  local heading2=$3
  local column_width=$4
  local num_cols=$5
  local total_width=55
  local RED='\033[0;31m'
  local GREEN='\033[0;32m'
  local NC='\033[0m'

  printf "%${total_width}s\n" | tr ' ' '-'
  for ((c = 0; c < num_cols; c++)); do
    printf "%-${column_width}s %-${column_width}s  " "$heading1" "$heading2"
  done
  printf "\n"
  printf "%${total_width}s\n" | tr ' ' '-'
  local count=0
  for item in "${arr[@]}"; do
    if [[ "$item" == *$'\t'* ]]; then
      key=$(echo "$item" | awk -F'\t' '{print $1}')
      value=$(echo "$item" | awk -F'\t' '{print $2}')
    elif [[ "$item" == *=* ]]; then
      key=$(echo "$item" | cut -d'=' -f1)
      value=$(echo "$item" | cut -d'=' -f2-)
    else
      key="$item"
      value=""
    fi
    if [[ "$value" == *"unhealthy"* ]] || ([[ "$value" == *"%"* ]] && (($(echo "${value%\%} > 80" | bc -l)))); then
      printf "%-${column_width}s ${RED}%-${column_width}s${NC}  " "$key" "$value"
    else
      printf "%-${column_width}s ${GREEN}%-${column_width}s${NC}  " "$key" "$value"
    fi
    count=$((count + 1))
    if ((count % num_cols == 0)); then
      printf "\n"
    fi
  done
  if ((count % num_cols != 0)); then
    printf "\n"
  fi
}

print_stats host_stats "Host" "Metric" 15 2
print_stats container_stats "Container" "Status" 15 1
