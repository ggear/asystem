from os.path import *

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import load_env
from homeassistant.generate import load_modules

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules(load_disabled=False, load_infrastrcture=False)
    metadata_df = load_entity_metadata()

    print("Build generate script [rhasspy] completed".format())
