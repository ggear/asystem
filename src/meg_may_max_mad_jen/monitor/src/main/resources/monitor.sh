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
    echo "Used CPU=${cpu}%"
    echo "Used Mem=${mem_percent}%"
    echo "Used Swp=${swap_percent}%"
    echo "Used Dsk=${disk_used}%"
    echo "Temp Max=${temp_percent}%"
  done
)
mapfile -t container_stats < <(docker ps --format "{{.Names}}\t{{.Status}}")

print_stats() {
  local -n arr=$1
  local heading1=$2
  local heading2=$3
  local RED='\033[0;31m'
  local GREEN='\033[0;32m'
  local NC='\033[0m'
  local column_width=15
  local dashes=$(printf "%0.s-" {1..40})

  printf "  \n%-${column_width}s %s\n" "$heading1" "$heading2"
  printf "%s" "${dashes}" && echo

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
    if [[ "$value" == *"unhealthy"* ]] || [[ "$value" =~ ([0-9]+(\.[0-9]+)?%) && $(echo "${value%\%} > 80" | bc -l) -eq 1 ]]; then
      printf "%-${column_width}s ${RED}%s${NC}\n" "$key" "$value"
    else
      printf "%-${column_width}s ${GREEN}%s${NC}\n" "$key" "$value"
    fi
  done
}

print_stats host_stats "Host" "Metric"
print_stats container_stats "Container" "Status"
