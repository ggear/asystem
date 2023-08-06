import glob
import os
import re
from os.path import *

import pandas as pd
import requests
import sys
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
for dir_module in glob.glob(join(DIR_ROOT, "../../*/*")):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, join(dir_module, "src/build/python"))

from homeassistant.generate import load_env
from homeassistant.generate import load_modules
from homeassistant.generate import load_entity_metadata

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.janeandgraham.com:443"

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules()
    metadata_df = load_entity_metadata()

    metadata_dhcp_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_identifiers"].str.len() > 0) &
        (metadata_df["connection_vlan"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    dnsmasq_conf_root_path = join(DIR_ROOT, "src/main/resources/config/udm-dnsmasq")
    metadata_dhcp_df = metadata_dhcp_df.fillna('')
    if not metadata_dhcp_df.loc[metadata_dhcp_df["connection_ip"] != '', :]["connection_ip"].is_unique:
        raise Exception("Build generate script [udmutilities] found non-unique IP addresses!")
    if not metadata_dhcp_df.loc[metadata_dhcp_df["connection_mac"] != '', :]["connection_mac"].is_unique:
        raise Exception("Build generate script [udmutilities] found non-unique MAC addresses!")
    for dnsmasq_conf_path in glob.glob(join(dnsmasq_conf_root_path, "{}*".format(DNSMASQ_CONF_PREFIX))):
        os.remove(dnsmasq_conf_path)
    unifi_clients = {}
    unifi_session = requests.Session()
    unifi_server_up = True
    try:
        unifi_session.post('{}/api/auth/login'.format(UNIFI_CONTROLLER_URL), json={
            'username': env["UNIFI_ADMIN_USER"],
            'password': env["UNIFI_ADMIN_KEY"]
        }, verify=False).raise_for_status()
        unifi_clients_response = unifi_session.get('{}/proxy/network/api/s/default/list/user'.format(UNIFI_CONTROLLER_URL), verify=False)
    except:
        unifi_server_up = False
    if not unifi_server_up or unifi_clients_response.status_code != 200:
        print("Build generate script [udmutilities] could not connect to UniFi")
    else:
        for unifi_client in unifi_clients_response.json()['data']:
            unifi_clients[unifi_client["mac"]] = unifi_client["name"] if "name" in unifi_client else (
                unifi_client["hostname"] if "hostname" in unifi_client else "")
        unifi_clients_response = unifi_session.get('{}/proxy/network/api/s/default/stat/device'.format(UNIFI_CONTROLLER_URL), verify=False)
        if unifi_clients_response.status_code != 200:
            print("Build generate script [udmutilities] could not connect to UniFi")
        else:
            for unifi_client in unifi_clients_response.json()['data']:
                unifi_clients[unifi_client["mac"]] = unifi_client["name"] if "name" in unifi_client else ""
    metadata_dhcp_ips = {}
    metadata_dhcp_hosts = {}
    metadata_dhcp_dnsmasq = {}
    for vlan in metadata_dhcp_df["connection_vlan"].unique():
        metadata_dhcp_vlan_df = metadata_dhcp_df[(metadata_dhcp_df["connection_vlan"] == vlan)]
        metadata_dhcp_vlan_df = metadata_dhcp_vlan_df.set_index(
            metadata_dhcp_vlan_df["connection_ip"].str.split(".").str[3].apply(lambda x: '{0:0>3}'.format(x))
        ).sort_index()
        metadata_dhcp_dicts = [row.dropna().to_dict() for index, row in metadata_dhcp_vlan_df.iterrows()]
        dnsmasq_conf_path = join(dnsmasq_conf_root_path, "{}-{}-custom.conf".format(
            DNSMASQ_CONF_PREFIX,
            vlan.replace("net", "vlan" + vlan.split("_")[2].replace("br", "")) if len(vlan) > 0 else "vlanX"
        ))
        metadata_dhcp_dnsmasq[dnsmasq_conf_path] = []
        for metadata_dhcp_dict in metadata_dhcp_dicts:
            metadata_dhcp_dnsmasq[dnsmasq_conf_path].append("dhcp-host={},{}{}\n".format(
                metadata_dhcp_dict["connection_mac"],
                (metadata_dhcp_dict["connection_ip"] + ",") \
                    if "connection_ip" in metadata_dhcp_dict and len(metadata_dhcp_dict["connection_ip"]) > 0 else "",
                metadata_dhcp_dict["device_identifiers"],
            ))
            if "connection_ip" in metadata_dhcp_dict and len(metadata_dhcp_dict["connection_ip"]) > 0:
                if metadata_dhcp_dict["device_identifiers"] not in metadata_dhcp_hosts:
                    metadata_dhcp_hosts[metadata_dhcp_dict["device_identifiers"]] = \
                        [metadata_dhcp_dict["connection_ip"]]
                else:
                    metadata_dhcp_hosts[metadata_dhcp_dict["device_identifiers"]] \
                        .append(metadata_dhcp_dict["connection_ip"])
    for dnsmasq_conf_path in metadata_dhcp_dnsmasq:
        with open(dnsmasq_conf_path, "w") as dnsmasq_conf_file:
            for metadata_dhcp_dnsmasq_line in metadata_dhcp_dnsmasq[dnsmasq_conf_path]:
                dnsmasq_conf_file.write(metadata_dhcp_dnsmasq_line)
                mac = metadata_dhcp_dnsmasq_line.split("=")[1].split(",")[0].strip()
                name = metadata_dhcp_dnsmasq_line.split("=")[1].split(",")[-1].strip()
                if mac in unifi_clients:
                    if unifi_clients[mac] != name and unifi_clients[mac] != "":
                        print("Build generate script [udmutilities] dnsmasq config host [{}] doesn't match UniFi alias [{}]".format(
                            name,
                            unifi_clients[mac],
                        ), file=sys.stderr)
                    else:
                        print("Build generate script [udmutilities] dnsmasq config host [{}] matches UniFi alias [{}]".format(
                            name,
                            unifi_clients[mac],
                        ))
                else:
                    if not re.match(r"u??\-.*", name):
                        print("Build generate script [udmutilities] dnsmasq config host [{}] not found in UniFi".format(
                            name,
                        ), file=sys.stderr)
        print("Build generate script [udmutilities] dnsmasq config persisted to [{}]".format(dnsmasq_conf_path))

    metadata_dhcp_ips = {}
    hosts_conf_path = join(DIR_ROOT, "src/main/resources/config/udm-utilities/run-pihole/custom.list")
    for metadata_dhcp_host in metadata_dhcp_hosts:
        metadata_dhcp_hosts[metadata_dhcp_host].sort()
        metadata_dhcp_ips[metadata_dhcp_hosts[metadata_dhcp_host][0]] = metadata_dhcp_host
    with open(hosts_conf_path, "w") as hosts_conf_file:
        for metadata_dhcp_ip in sorted(metadata_dhcp_ips):
            hosts_conf_file.write("{} {}.janeandgraham.com {}\n".format(
                metadata_dhcp_ip,
                metadata_dhcp_ips[metadata_dhcp_ip],
                metadata_dhcp_ips[metadata_dhcp_ip]
            ))

    metadata_dhcpaliases_path = abspath(join(dnsmasq_conf_root_path, "dhcp.dhcpServers-aliases.conf"))
    with open(metadata_dhcpaliases_path, 'w') as metadata_hass_file:
        for name in modules:
            if "{}_HTTP_PORT".format(name.upper()) in modules[name][1]:
                metadata_hass_file.write("cname={},{}.janeandgraham.com,{}\n".format(
                    name,
                    name,
                    modules["nginx"][0][0],
                ))
