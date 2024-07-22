# !/bin/bash

ROOT_DIR=$(dirname "$(readlink -f "$0")")

sigterm_handler() {
  exit 1
}
trap 'trap " " SIGINT SIGTERM SIGHUP; kill 0; wait; sigterm_handler' SIGINT SIGTERM SIGHUP

echo ''
"${ROOT_DIR}/../../share/10/media/parents/movies/Force Of Nature (2024)/._transcode_Force Of Nature (2024)/transcode.sh"
"${ROOT_DIR}/../../share/10/media/kids/movies/Sample Movie 8 (2024)/._transcode_Sample Movie 8 (2024)/transcode.sh"
"${ROOT_DIR}/../../share/10/media/parents/series/Sample Series/Season 1/._transcode_Sample-Series_s01e01/transcode.sh"
"${ROOT_DIR}/../../share/10/media/parents/series/Sample Series/Season 1/._transcode_Sample-Series_s01e02/transcode.sh"
"${ROOT_DIR}/../../share/10/media/parents/series/Sample Series/Season 1/._transcode_Sample-Series_s01e03/transcode.sh"
"${ROOT_DIR}/../../share/10/media/docos/movies/The Bad News Bears (1976)/._transcode_The Bad News Bears (1976)/transcode.sh"
"${ROOT_DIR}/../../share/10/media/kids/series/Sample Series 3/Season 1/._transcode_Sample-Series-3_s01e04/transcode.sh"
"${ROOT_DIR}/../../share/10/media/kids/movies/Kikis Delivery Service (1989)/._transcode_Kikis Delivery Service (1989)/transcode.sh"
