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
#   - Google Cast
#   - Philips hue
#   - Sonos
#   - Apple TV
#   - TP-Link Smart Home
#   - SenseME (have to add for each device)
#   - Bureau of Meteorology (Gooseberry Hill for observations, Darlington Forecast for weather forecast, 7 day forecast)

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
