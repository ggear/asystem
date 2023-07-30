#!/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

set -e
set -o pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

# Bootstrap with altitude '193m' and create user 'graham' with password '$HOMEASSISTANT_KEY_GRAHAM'
# Create user 'jane' with password '$HOMEASSISTANT_KEY_JANE'
# Create API Long-Lived Access Tokens and store in '.env_all_key'
# Install integrations manually (no option to do so programmatically):
#   - MQTT (local push, no internet, yaml has details but is now unfortunately now deprecated)
#   - Big Ass Fans (local push, no internet after initial firmware upgrade, each fan is automatically discovered)
#   - UniFi Protect (local push, no internet, requires Protect IP, user, password and Areas config - has not been yaml configured since at least Nov 2020)
#   - Apple (local push, no internet, add tv/home-pod through UI with paring code prompts)
#   - TP-Link Smart Home (local polling, no internet, requires Areas to be manually configured)
#   - Google Cast (local polling, requires internet, requires IP CSV which could be hacked in - see 'custom_packages/media.yaml')
#   - Brother Printer (local polling, no internet, requires manual config with IP)
#   - Google (local push, requires internet, need to add new devices and enter HASS 'graham' password)
#   - Withings (cloud polling, requires internet, requires manual config of profile 'Graham' and authentication)
#   - Netatmo (cloud polling, requires internet, requires manual config by logging into 'netatmo.com' and providing Areas)
#   - Bureau of Meteorology (cloud polling, requires internet, requires manual config and then restart - see 'custom_packages/weather.yaml' which could be hacked in)

# Delete integrations manually:
#   - Internet Radio
#   - Meteorologisk institutt Weather

# Todo:

#   - WebOS (local push, no internet)

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
