#!/bin/bash

# 22 Bertram St
GEOHASH=$(curl -sf https://api.weather.bom.gov.au/v1/locations?search=-31.918381,116.079391 | jq -r .data[0].geohash)
curl -sf https://api.weather.bom.gov.au/v1/locations/${GEOHASH} | jq
curl -sf https://api.weather.bom.gov.au/v1/locations/${GEOHASH%?}/observations | jq

# Gooseberry Hill BOM Weather Station
GEOHASH=$(curl -sf https://api.weather.bom.gov.au/v1/locations?search=-31.94,116.05 | jq -r .data[0].geohash)
curl -sf https://api.weather.bom.gov.au/v1/locations/${GEOHASH} | jq
curl -sf https://api.weather.bom.gov.au/v1/locations/${GEOHASH%?}/observations | jq
