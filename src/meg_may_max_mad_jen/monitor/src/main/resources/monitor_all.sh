#!/bin/bash

update_interval=30
session_name="host_stats_live"
session_hosts=("macmini-mad" "macmini-max" "macmini-may" "macmini-meg")
session_script="/root/install/monitor/latest/monitor.sh"

tmux kill-session -t "${session_name}" 2>/dev/null
tmux new-session -d -s "${session_name}"
tmux split-window -h -t "${session_name}:0"
tmux select-pane -t 0
tmux split-window -v -t "${session_name}:0"
tmux select-pane -t 1
tmux split-window -v -t "${session_name}:0"
tmux select-layout -t "${session_name}:0" tiled

tmux set-option -g automatic-rename off
tmux set-option -g allow-rename off
tmux set-option -t "${session_name}:0" pane-border-status top
tmux set-option -t "${session_name}:0" pane-border-format "#{pane_index}: #{pane_title}"

for host in "${session_hosts[@]}"; do
  ssh -4 -T "${host}" "echo 'Connection to \$(hostname) successful ... '"
done

for ((i = 0; i < ${#session_hosts[@]}; i++)); do
  host="${session_hosts[$i]}"
  tmux select-pane -t "${session_name}:0.$i"
  tmux select-pane -T "${host}"
  tmux send-keys -t "${session_name}:0.$i" \
    "while true; do
      clear
      ssh -4 -T ${host} '${session_script} $(tput cols 2>/dev/null)'
      sleep ${update_interval}
      tmux select-pane -T ${host}
    done" C-m
done

tmux attach-session -t "${session_name}"
