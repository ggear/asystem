#/bin/bash

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
#   - Philips Hue (local push, requires internet for firmware upgrades, config requires button to be pushed)
#   - SenseME (local push, no internet after initial firmware upgrade, config requires each fan IP could be hacked or discovery fixed)

# Delete integrations manually:
#   - Meteorologisk institutt (Met.no)






#   - TP-Link Smart Home (local polling, no internet, yaml config)
#   - Brother Printer (local polling, no internet)

#   - Unifi Protect (local push, no internet)

#   - Apple (local push, requires internet)
#   - Sonos (local push, requires internet)
#   - Google Cast (local polling, requires internet)

#   - Netatmo (cloud polling, requires internet)
#   - Withings (cloud polling, requires internet)
#   - Bureau of Meteorology - gooseberry_hill for observations, darlington_forecast for weather forecast, 7 day forecast (cloud polling, requires internet)


echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
