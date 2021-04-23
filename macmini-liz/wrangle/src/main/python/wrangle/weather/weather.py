from __future__ import print_function

import datetime
import os

import pandas as pd

from .. import library

DAILY_START_MONTH = 1
DAILY_START_YEAR = 2009
DAILY_URL = "ftp://ftp.bom.gov.au/anon/gen/clim_data//IDCKWCDEA0/tables/wa/perth_airport/perth_airport-{}{:02d}.csv"

DAILY_HISTORIC_RAIN_FILE = "IDCJAC0009_009021_1800_Data.csv"
DAILY_HISTORIC_SOLAR_FILE = "IDCJAC0016_009021_1800_Data.csv"
DAILY_HISTORIC_MAXTEMP_FILE = "IDCJAC0010_009021_1800_Data.csv"

MONTHLY_STATS_URL = "http://www.bom.gov.au/clim_data/cdio/tables/text/IDCJCM0039_009021.csv"

WEEKLY_FORECAST_URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDW12300.xml"

LINE_PROTOCOL = "weather,source={},type={},period={} {}="


class Weather(library.Library):

    def run(self):
        new_data = False
        weather_df = pd.DataFrame()
        now = datetime.datetime.now()

        for year in range(DAILY_START_YEAR, now.year + 1):
            for month in range(DAILY_START_MONTH if year == DAILY_START_YEAR else 1, (now.month + 1) if year == now.year else 13):
                daily_url = DAILY_URL.format(year, month)
                daily_file = os.path.join(self.input, daily_url.split("/")[-1])
                file_status = self.ftp_download(daily_url, daily_file, check=False, force=year == now.year and month == now.month)
                if file_status[0]:
                    new_data = file_status[1]

        monthly_stats_file = os.path.join(self.input, MONTHLY_STATS_URL.split("/")[-1])
        file_status = self.http_download(MONTHLY_STATS_URL, monthly_stats_file)
        if file_status[0]:
            new_data = file_status[1]

        weekly_forecast_file = os.path.join(self.input, WEEKLY_FORECAST_URL.split("/")[-1])
        file_status = self.ftp_download(WEEKLY_FORECAST_URL, weekly_forecast_file)
        if file_status[0]:
            new_data = file_status[1]

        if not new_data:
            self.print_log("No new data found")

    def __init__(self, profile_path=".profile"):
        super(Weather, self).__init__("Weather", "1SiOrwMf-DgNQ19wRNbE7itzd4RWT829v", profile_path)
