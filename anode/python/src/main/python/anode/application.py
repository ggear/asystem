import os

_APP_CONF = dict(
    line.strip().split("=") for line in
    open(os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__), "application.properties")))
    if not line.startswith("#") and not line.startswith("\n"))
APP_NAME = _APP_CONF["APP_NAME"]
APP_NAME_ESCAPED = _APP_CONF["APP_NAME_ESCAPED"]
APP_VERSION = _APP_CONF["APP_VERSION"]
APP_VERSION_NUMERIC = int(_APP_CONF["APP_VERSION_NUMERIC"])

_APP_MODEL_CONF = dict(
    line.strip().split("=") for line in
    open(os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__), "avro", "model.properties")))
    if not line.startswith("#") and not line.startswith("\n"))
APP_MODEL_VERSION = _APP_MODEL_CONF["MODEL_VERSION"]
APP_MODEL_ENERGYFORECAST_INTERDAY_PROD_VERSION = _APP_MODEL_CONF["MODEL_ENERGYFORECAST_INTERDAY_PROD_VERSION"]
APP_MODEL_ENERGYFORECAST_INTRADAY_PROD_VERSION = _APP_MODEL_CONF["MODEL_ENERGYFORECAST_INTRADAY_PROD_VERSION"]
APP_MODEL_ENERGYFORECAST_INTERDAY_BUILD_VERSION = _APP_MODEL_CONF["MODEL_ENERGYFORECAST_INTERDAY_BUILD_VERSION"]
APP_MODEL_ENERGYFORECAST_INTRADAY_BUILD_VERSION = _APP_MODEL_CONF["MODEL_ENERGYFORECAST_INTRADAY_BUILD_VERSION"]
