#!/bin/sh

# TODO: Does not work, so I have not generated and productionised to be run on release yet, maybe one day?
# TODO: Reverse engineered API doc https://ubntwiki.com/products/software/unifi-controller/api
# TODO: Maybe use PHP UniFi-API-client as per https://github.com/Art-of-WiFi/UniFi-API-client?
# TODO: Maybe use ubios-udapi-client as per https://github.com/evaneaston/udm-host-records/tree/develop?

. ../../../../../.env

rm -rf ./.udm_api_cookie.txt
curl --cookie ./.udm_api_cookie.txt --cookie-jar ./.udm_api_cookie.txt -s -XPOST \
  https://unifi.janeandgraham.com/api/auth/login \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "username":"unifi",
        "password":"'${UNIFI_ADMIN_KEY}'"
      }' |
  jq && echo ""

# Works :)
# https://github.com/Art-of-WiFi/UniFi-API-client/blob/v1.1.83/src/Client.php#L1397
# return $this->fetch_results('/api/s/' . $this->site . '/list/user');
curl --cookie ./.udm_api_cookie.txt --cookie-jar ./.udm_api_cookie.txt -s \
  https://unifi.janeandgraham.com/proxy/network/api/s/default/stat/alluser \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" |
  jq && echo ""

# Does not work :(
# https://github.com/Art-of-WiFi/UniFi-API-client/blob/v1.1.83/src/Client.php#L448
# $payload = ['name' => $name];
# return $this->fetch_results_boolean('/api/s/' . $this->site . '/upd/user/' . trim($user_id), $payload);
curl --cookie ./.udm_api_cookie.txt --cookie-jar ./.udm_api_cookie.txt -s \
  https://unifi.janeandgraham.com/proxy/network/api/s/default/upd/user/65b5e9b49cda21068d5343fe \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "name":"ATEST"
      }' |
  jq && echo ""

# Does not work :(
# https://github.com/Art-of-WiFi/UniFi-API-client/blob/v1.1.83/src/Client.php#L1149
# $this->curl_method = 'PUT';
# $payload           = [
#    '_id'  => $client_id,
#    'name' => $name,
# ];
# return $this->fetch_results('/api/s/' . $this->site . '/rest/user/' . trim($client_id), $payload);
curl --cookie ./.udm_api_cookie.txt --cookie-jar ./.udm_api_cookie.txt -s -XPUT \
  https://unifi.janeandgraham.com/proxy/network/api/s/default/rest/user/65b5e9b49cda21068d5343fe \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
        "_id":"65b5e9b49cda21068d5343fe",
        "name":"ATEST"
      }' |
  jq && echo ""
