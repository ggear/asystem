import json
from os.path import *

from fabfile import _get_modules_by_hosts
from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()
