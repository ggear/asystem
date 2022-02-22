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
#   - Netatmo
#   - Withings
#   - Google Cast
#   - Unifi Protect
#   - Brother Printer
#   - Philips hue (allow groups)
#   - Apple (Lounge TV, Lounge Speaker)
#   - SenseME (have to add for each device)
#   - TP-Link Smart Home (have to add for each device)
#   - Adaptive Lighting ('default' profile created automatically, have to add 'bedroom' and 'nightlight' manually)
#   - Bureau of Meteorology (gooseberry_hill for observations, darlington_forecast for weather forecast, 7 day forecast)

# Delete integrations manually:
#   - Meteorologisk institutt (Met.no)

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
