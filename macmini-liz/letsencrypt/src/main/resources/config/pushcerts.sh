#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_HOME}" || exit

#TODO: while true, fswatch on .last_updated, then copy into git/anode, local/anode, udm-rack/unifi

# git/anode
# cat /Users/graham/_/dev/asystem/macmini-liz/letsencrypt/target/letsencrypt/live/janeandgraham.com/fullchain.pem /Users/graham/_/dev/asystem/macmini-liz/letsencrypt/target/letsencrypt/live/janeandgraham.com/privkey.pem > /Users/graham/_/dev/asystem/macmini-liz/anode/src/main/resources/config/.pem

# macmini-liz/anode
# cat /Users/graham/_/dev/asystem/macmini-liz/letsencrypt/target/letsencrypt/live/janeandgraham.com/fullchain.pem /Users/graham/_/dev/asystem/macmini-liz/letsencrypt/target/letsencrypt/live/janeandgraham.com/privkey.pem > /Users/graham/_/dev/asystem/macmini-liz/anode/src/main/resources/config/.pem

# udm-rack/host
# scp /Users/graham/_/dev/asystem/macmini-liz/letsencrypt/target/letsencrypt/live/janeandgraham.com/privkey.pem root@unifi:/mnt/data/unifi-os/unifi-core/config/unifi-core.key
# scp /Users/graham/_/dev/asystem/macmini-liz/letsencrypt/target/letsencrypt/live/janeandgraham.com/fullchain.pem root@unifi:/mnt/data/unifi-os/unifi-core/config/unifi-core.crt
