import pandas as pd
import urllib3

from asystem import *

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_container_volumes()
