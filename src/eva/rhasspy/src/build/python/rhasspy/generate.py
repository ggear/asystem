from os.path import *

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import load_env
from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_bootstrap()
    write_healthcheck()
