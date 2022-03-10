from __future__ import print_function

import glob
import os
import sys

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_MODULE_ROOT = os.path.abspath("{}/..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/*/*/".format("{}/../../../../../..".format(os.path.dirname(os.path.realpath(__file__))))):
    if dir_module.split("/")[-2] == "homeassistant":
        sys.path.insert(0, "{}/src/main/python".format(dir_module))
sys.path.insert(0, DIR_MODULE_ROOT)

from homeassistant.build import load_env
from homeassistant.build import load_entity_metadata

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.janeandgraham.com:443"

if __name__ == "__main__":
    env = load_env(DIR_MODULE_ROOT)
    metadata_df = load_entity_metadata()

    metadata_udmutilities_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    dnsmasq_conf_root_path = os.path.join(DIR_MODULE_ROOT, "../../../src/main/resources/config/udm-dnsmasq")
    for dnsmasq_conf_path in glob.glob(os.path.join(dnsmasq_conf_root_path, "{}*".format(DNSMASQ_CONF_PREFIX))):
        os.remove(dnsmasq_conf_path)
    unifi_clients = {}
    unifi_session = requests.Session()
    unifi_session.post('{}/api/auth/login'.format(UNIFI_CONTROLLER_URL), json={
        'username': env["UNIFI_ADMIN_USER"],
        'password': env["UNIFI_ADMIN_KEY"]
    }, verify=False).raise_for_status()
    unifi_clients_response = unifi_session.get('{}/proxy/network/api/s/default/list/user'.format(UNIFI_CONTROLLER_URL), verify=False)
    unifi_clients_response.raise_for_status()
    for unifi_client in unifi_clients_response.json()['data']:
        unifi_clients[unifi_client["mac"]] = unifi_client["name"] if "name" in unifi_client else (
            unifi_client["hostname"] if "hostname" in unifi_client else "")
    unifi_clients_response = unifi_session.get('{}/proxy/network/api/s/default/stat/device'.format(UNIFI_CONTROLLER_URL), verify=False)
    unifi_clients_response.raise_for_status()
    for unifi_client in unifi_clients_response.json()['data']:
        unifi_clients[unifi_client["mac"]] = unifi_client["name"] if "name" in unifi_client else ""


    metadata_udmutilities_dnsmasq = {}
    metadata_udmutilities_df =metadata_udmutilities_df.fillna('')
    for vlan in metadata_udmutilities_df["connection_vlan"].unique():
        metadata_udmutilities_vlan_df = metadata_udmutilities_df[(metadata_udmutilities_df["connection_vlan"] == vlan)]
        metadata_udmutilities_vlan_df = metadata_udmutilities_vlan_df.set_index(
            metadata_udmutilities_vlan_df["connection_ip"].str.split(".").str[3].apply(lambda x: '{0:0>3}'.format(x))
        ).sort_index()
        metadata_udmutilities_dicts = [row.dropna().to_dict() for index, row in metadata_udmutilities_vlan_df.iterrows()]
        dnsmasq_conf_path = os.path.join(DIR_MODULE_ROOT, dnsmasq_conf_root_path, "{}-{}-custom.conf".format(
            DNSMASQ_CONF_PREFIX,
            vlan.replace("net", "vlan" + vlan.split("_")[2].replace("br", "")) if len(vlan)>0 else "untagged"
        ))
        metadata_udmutilities_dnsmasq[dnsmasq_conf_path] = []
        for metadata_udmutilities_dict in metadata_udmutilities_dicts:
            if "connection_ip" in metadata_udmutilities_dict and len(metadata_udmutilities_dict["connection_ip"])>0:
                metadata_udmutilities_dnsmasq[dnsmasq_conf_path].append("dhcp-host=set:{}{},{},{}\n".format(
                    (metadata_udmutilities_dict["connection_vlan"] + ",") if len(vlan)>0 else "",
                    metadata_udmutilities_dict["connection_mac"],
                    metadata_udmutilities_dict["connection_ip"],
                    metadata_udmutilities_dict["device_name"],
                ))
        for dnsmasq_conf_path in metadata_udmutilities_dnsmasq:
            with open(dnsmasq_conf_path, "w") as dnsmasq_conf_file:
                for metadata_udmutilities_dnsmasq_line in metadata_udmutilities_dnsmasq[dnsmasq_conf_path]:
                    dnsmasq_conf_file.write(metadata_udmutilities_dnsmasq_line)
                    # if metadata_udmutilities_dict["connection_mac"] in unifi_clients:
                    #     if unifi_clients[metadata_udmutilities_dict["connection_mac"]] != metadata_udmutilities_dict["device_name"]:
                    #         print("Build script [udmutilities] dnsmasq config host [{}] doesn't match unifi controller alias [{}]".format(
                    #             metadata_udmutilities_dict["device_name"],
                    #             unifi_clients[metadata_udmutilities_dict["connection_mac"]],
                    #         ), file=sys.stderr)
                    #     else:
                    #         print("Build script [udmutilities] dnsmasq config host [{}] matches unifi controller alias [{}]".format(
                    #             metadata_udmutilities_dict["device_name"],
                    #             unifi_clients[metadata_udmutilities_dict["connection_mac"]],
                    #         ))
                    # else:
                    #     print("Build script [udmutilities] dnsmasq config host [{}] not found in unifi controller".format(
                    #         metadata_udmutilities_dict["device_name"],
                    #     ), file=sys.stderr)
            print("Build script [udmutilities] dnsmasq config persisted to [{}]".format(dnsmasq_conf_path))
