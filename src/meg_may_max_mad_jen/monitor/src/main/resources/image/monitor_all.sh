#!/bin/bash

update_interval=30
session_name="host_stats_live"
session_hosts=("macmini-mad" "macmini-max" "macmini-may" "macmini-meg")
session_script="/root/install/monitor/latest/image/monitor.sh"

chmod +x "${session_script}"

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

for i in {0..3}; do
  host="${session_hosts[$i]}"
  tmux select-pane -t "${session_name}:0.$i"
  tmux select-pane -T "${host}"
  tmux send-keys "printf '\033]2;${host}\033\\'" C-m
  tmux send-keys "while true; do clear; ssh -4 -T ${host} "${session_script}" || echo 'Host unreachable: ${host}'; sleep ${update_interval}; done" C-m
  #tmux send-keys "while true; do clear; ssh -4 -T ${host} docker ps --format \\\"table\\ {{.Names}}\\\t\\\t{{.Status}}\\\" || echo 'Host unreachable: ${host}'; sleep ${update_interval}; done" C-m
  #tmux send-keys "while true; do clear; ssh -4 -T ${host} docker stats --no-stream --format \\\"table\\ {{.Name}}\\\t{{.CPUPerc}}\\\t{{.MemUsage}}\\\" || echo 'Host unreachable: ${host}'; sleep ${update_interval}; done" C-m
done

tmux attach-session -t "${session_name}"
