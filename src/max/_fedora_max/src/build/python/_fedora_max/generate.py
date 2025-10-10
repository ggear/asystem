import pandas as pd
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_volumes()
