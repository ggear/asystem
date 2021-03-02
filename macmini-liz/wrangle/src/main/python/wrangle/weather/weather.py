from __future__ import print_function

import datetime
import os

import pandas as pd

from .. import script

CLIMATE_START_MONTH = 1
CLIMATE_START_YEAR = 2020
OBS_START_MONTH = 1
OBS_START_YEAR = 2009

STATS_URL = "http://www.bom.gov.au/clim_data/cdio/tables/text/IDCJCM0039_009021.csv"
CLIMATE_URL = "http://www.bom.gov.au/climate/dwo/{}{:02d}/text/IDCJDW6110.{}{:02d}.csv"
OBS_URL = "ftp://ftp.bom.gov.au/anon/gen/clim_data//IDCKWCDEA0/tables/wa/perth_airport/perth_airport-{}{:02d}.csv"
LINE_PROTOCOL = "interest,source={},type={},period={} {}="


class Weather(script.Script):

    def run(self):
        new_data = False
        weather_df = pd.DataFrame()
        now = datetime.datetime.now()
        stats_file = os.path.join(self.input, STATS_URL.split("/")[-1])
        file_status = self.http_download(STATS_URL, stats_file)
        if file_status[0]:
            new_data = file_status[1]
            pd.read_csv(stats_file, warn_bad_lines=False, error_bad_lines=False)

        for year in range(CLIMATE_START_YEAR, now.year + 1):
            for month in range(CLIMATE_START_MONTH if year == CLIMATE_START_YEAR else 1, (now.month + 1) if year == now.year else 13):
                climate_url = CLIMATE_URL.format(year, month, year, month)
                climate_file = os.path.join(self.input, climate_url.split("/")[-1])
                file_status = self.http_download(climate_url, climate_file)
                if file_status[0]:
                    new_data = file_status[1]
                    pd.read_csv(climate_file, warn_bad_lines=False, error_bad_lines=False)

        for year in range(OBS_START_YEAR, now.year + 1):
            for month in range(OBS_START_MONTH if year == OBS_START_YEAR else 1, (now.month + 1) if year == now.year else 13):
                obs_url = OBS_URL.format(year, month)
                obs_file = os.path.join(self.input, obs_url.split("/")[-1])
                file_status = self.http_download(obs_url, obs_file, check=False, force=year == now.year and month == now.month)
                if file_status[0]:
                    new_data = file_status[1]
                    pd.read_csv(obs_file, warn_bad_lines=False, error_bad_lines=False)

        if not new_data:
            self.print_log("No new data found")

    def __init__(self):
        super(Weather, self).__init__("Weather", "", "")
