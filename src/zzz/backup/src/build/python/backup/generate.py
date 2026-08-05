import json
from os.path import *

from fabfile import _get_modules_by_hosts
from asystem import load_bootstrap_entities

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()
