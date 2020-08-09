VERSION=latest \
  DATA_DIR=./target/runtime-system \
  LOCAL_IP=$(/usr/sbin/ipconfig getifaddr en1) \
  docker-compose --no-ansi run --service-ports anode anode -v
