#/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

set -e
set -o pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

# Create users manually (no option to do so programmatically currently):
#   - jane (password $HOMEASSISTANT_KEY_JANE)
#   - graham (password $HOMEASSISTANT_KEY_GRAHAM)

# Install integrations manually (no option to do so programmatically currently):
#   - Sonos
#   - Apple TV
#   - Withings
#   - Google Cast
#   - Unifi Protect
#   - Philips hue (allow groups)
#   - SenseME (have to add for each device)
#   - TP-Link Smart Home (configure each device integration after adding primary integration)
#   - Bureau of Meteorology (gooseberry_hill for observations, darlington_forecast for weather forecast, 7 day forecast)

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
