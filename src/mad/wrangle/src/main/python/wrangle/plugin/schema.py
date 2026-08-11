from asystem.schema.document import SchemaDatabaseDimension, SchemaDatabaseMeasure, SchemaDatabaseRelation

from .currency import PAIRS as CURRENCY_PAIRS
from .currency import PERIODS as CURRENCY_PERIODS
from .equity import DIMENSIONS_CHANGE_PERIODS
from .equity import PORTFOLIO_TICKER_MAP as EQUITY_PORTFOLIO_TICKERS
from .equity import PORTFOLIO_TICKERS_MANUAL as EQUITY_MANUAL_TICKERS
from .equity import PORTFOLIO_TICKERS_NODATA as EQUITY_NODATA_TICKERS
from .equity import STOCK as EQUITY_STOCK
from .interest import LABELS as INTEREST_LABELS
from .interest import PERIODS as INTEREST_PERIODS

CADENCE = "1d"

EQUITY_TICKERS = sorted(
    ({ticker.strip() for ticker in EQUITY_STOCK} |
     {ticker.strip() for ticker in EQUITY_PORTFOLIO_TICKERS.values()} |
     {ticker.strip() for ticker in EQUITY_MANUAL_TICKERS}) -
    {ticker.strip() for ticker in EQUITY_NODATA_TICKERS})

EQUITY_SPOT_TYPES = [
    "market-volume-spot",
    "price-close",
    "price-close-base",
    "price-close-spot",
]


def database_schema():
    return [_currency(), _interest(), _equity()]


def table_name(relation):
    return relation.path.split("/", 1)[0]


def _currency():
    measures_all = [_measure("snapshot", "1d", "$", "closing rate for the currency pair")]
    measures_all += [_measure("delta", f"{days:0.0f}d", "%", f"change in the rate across [{label}]")
                     for label, days in CURRENCY_PERIODS.items()]
    return SchemaDatabaseRelation(
        path="currency/rate",
        description="foreign exchange rates published by the Reserve Bank of Australia",
        cadence=CADENCE,
        entities=list(CURRENCY_PAIRS),
        dimensions=[SchemaDatabaseDimension(key="entity", description="currency pair", subject=True)],
        measures=measures_all)


def _interest():
    measures_all = [_measure("mean", "1mo", "%", "mean rate across the month")]
    measures_all += [_measure("mean", f"{months / 12:0.0f}y", "%",
                              f"mean rate across [{label}]")
                     for label, months in INTEREST_PERIODS.items()]
    return SchemaDatabaseRelation(
        path="interest/rate",
        description="interest and inflation rates published by the Reserve Bank of Australia",
        cadence=CADENCE,
        entities=list(INTEREST_LABELS),
        dimensions=[SchemaDatabaseDimension(key="entity", description="rate series", subject=True)],
        measures=measures_all)


def _equity():
    measures_all = [_measure(metric_type, "1d", "$", "daily {} reading".format(metric_type.replace("-", " ")))
                    for metric_type in EQUITY_SPOT_TYPES]
    for change_period in DIMENSIONS_CHANGE_PERIODS:
        for price_type in ("price-close", "price-close-base", "price-close-spot"):
            measures_all.append(_measure(
                f"{price_type}-{change_period}d-change-percentage",
                f"{change_period}d", "%",
                "change in {} across [{}] days".format(price_type.replace("-", " "), change_period)))
    return SchemaDatabaseRelation(
        path="equity/ticker",
        description="equity prices and volumes downloaded per ticker",
        cadence=CADENCE,
        entities=EQUITY_TICKERS,
        dimensions=[SchemaDatabaseDimension(key="entity", description="ticker symbol", subject=True)],
        measures=measures_all)


def _measure(metric_type, period, unit, description):
    return SchemaDatabaseMeasure(key=metric_type, kind="float", unit=unit, description=description, period=period)
