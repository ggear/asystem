import glob
import os
import re
import sys
from os.path import *

import pandas as pd
import requests
import urllib3

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import load_env
from homeassistant.generate import load_modules
from homeassistant.generate import write_certificates

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.local.janeandgraham.com:443"

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules(load_disabled=False, load_infrastrcture=False)
    metadata_df = load_entity_metadata()

    write_certificates("appdaemon", join(DIR_ROOT, "src/main/resources/image"))

    print("Build generate script [appdaemon] completed".format())
