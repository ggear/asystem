from grafana_foundation_sdk.cog import builder as cogbuilder
from grafana_foundation_sdk.cog import variants as cogvariants
from grafana_foundation_sdk.models import dashboardv2

from asystem.schema.query import expanded, literals, select

STATISTICS = {
    "newest": "min",
    "oldest": "max",
    "entities": "ratio",
    "metrics": "ratio",
    "volume": "ratio",
}
LOOKBACK = 30 * 86400
BATCH = 2
QUARTERS = 4
TRANSFORMS = ("invert", "baseline", "percent", "complement", "counter", "peak", "trough", "bearing", "compass")
COMBINES = ("sum", "min", "max", "avg")
PERIOD = "@"


class Dataquery(cogvariants.Dataquery):

    def __init__(self, sql, form):
        self.sql = sql
        self.form = form

    def to_json(self):
        return {
            "editorMode": "code",
            "format": self.form,
            "rawQuery": True,
            "rawSql": self.sql,
        }


class Query(cogbuilder.Builder[dashboardv2.DataQueryKind]):

    def __init__(self, group, datasource, sql, form):
        self._internal = dashboardv2.DataQueryKind(
            group=group, version="v0", datasource=dashboardv2.Dashboardv2DataQueryKindDatasource(name=datasource),
            spec=Dataquery(sql, form))

    def build(self):
        return self._internal


def selected(relation, document, measures, kinds):
    picked = []
    for spec in measures:
        key, _, period = spec.partition(PERIOD)
        matched = [measure for measure in relation.carried(kinds) if measure.key == key
                   and (not period or relation.span(measure) == period)]
        if not matched:
            raise ValueError("Build generate script [{}] relation [{}] declares no persisted measure [{}] expected "
                             "one of [{}]".format(document.module, relation.path, spec, ",".join(
                                 sorted({measure.key for measure in relation.carried(kinds)}))))
        periods = {relation.span(other) for other in relation.measures if other.key == key}
        picked += [(measure, key if period or len(periods) == 1 else "{} {}".format(key, relation.span(measure)))
                   for measure in matched]
    return picked


def subjected(relation, document, entities):
    subject = relation.subject
    if entities is None:
        return None
    if subject is None:
        raise ValueError("Build generate script [{}] relation [{}] has no subject dimension to select entities [{}]"
                         .format(document.module, relation.path, ",".join(entities)))
    declared = expanded(relation, subject)
    unknown = sorted(set(entities) - set(declared)) if declared else []
    if unknown:
        raise ValueError("Build generate script [{}] relation [{}] declares no entities [{}]"
                         .format(document.module, relation.path, ",".join(unknown)))
    return list(entities)


def transformed(transforms, document, relation):
    unknown = sorted(set(transforms) - set(TRANSFORMS) - set(COMBINES))
    combined = [transform for transform in transforms if transform in COMBINES]
    if unknown or len(combined) > 1:
        raise ValueError("Build generate script [{}] relation [{}] transforms [{}] expected any of [{}] and at most "
                         "one of [{}]".format(document.module, relation.path, ",".join(transforms),
                                              ",".join(TRANSFORMS), ",".join(COMBINES)))
    return combined[0] if combined else None


def valued(expression, measure, transforms):
    if "invert" in transforms:
        expression = ("10000.0 / (100 + {}) - 100" if measure.unit == "%" else "1.0 / {}").format(expression)
    if "complement" in transforms:
        expression = "1 - {}".format(expression)
    if "percent" in transforms:
        expression = "{} * 100".format(expression)
    return expression


def aggregated(expression, transforms):
    if "bearing" in transforms or "compass" in transforms:
        mean = "degrees(atan2(avg(sin(radians({0}))), avg(cos(radians({0})))))".format(expression)
        bearing = "CASE WHEN {0} < -0.000001 THEN {0} + 360 ELSE abs({0}) END".format(mean)
        return bearing if "bearing" in transforms else "({}) / 22.5".format(bearing)
    if "counter" in transforms or "peak" in transforms:
        return "max({})".format(expression)
    if "trough" in transforms:
        return "min({})".format(expression)
    return "avg({})".format(expression)


def entitled(expression, subject, entities, labels):
    cases = " ".join("WHEN '{}' THEN '{}'".format(entity, label) for entity, label in sorted((labels or {}).items())
                     if entities is None or entity in entities)
    return "CASE {} {} ELSE {} END".format(subject, cases, expression) if cases else expression


def statement(arms, entities, picked, transforms, combine):
    measured = len(picked) > 1
    if combine:
        metric, value, grouped = "measure", "{}(value)".format(combine), "\nGROUP BY time, measure"
    else:
        many = entities is None or len(entities) > 1
        metric = "entity || ' ' || measure" if many and measured else ("entity" if many or not measured else "measure")
        value, grouped = "value", ""
    series = "SELECT\n    time,\n    {} AS metric,\n    {} AS value\nFROM (\n{}\n) AS arms{}".format(
        metric, value, indented("\nUNION ALL\n".join(arms)), grouped)
    if "baseline" in transforms:
        series = ("SELECT\n    time,\n    metric,\n"
                  "    (value / first_value(value) OVER (PARTITION BY metric ORDER BY time) - 1) * 100 AS value\n"
                  "FROM (\n{}\n) AS series".format(indented(series)))
    return series + "\nORDER BY time"


def summary_arm(statistic, table, predicates, entity, carried, now, start, epoch, span):
    if statistic not in STATISTICS:
        raise ValueError("Build generate script statistic [{}] expected one of [{}]"
                         .format(statistic, ",".join(STATISTICS)))
    window = ["$__timeFilter(time)"] + predicates
    lookback = predicates + ["time <= {}".format(now),
                             "time > {} - INTERVAL '{} seconds'".format(now, max(LOOKBACK, 4 * span))]
    newest = flat(select([("max(time)", "")], table, window))
    batch = window + ["time > ({}) - INTERVAL '{} seconds'".format(newest, BATCH * span)]
    recent = window + ["{} > ({} * {} + {}) / {}".format(epoch("time"), QUARTERS - 1, epoch(now), epoch(start),
                                                          QUARTERS)]
    if statistic == "newest":
        return select([("{} - {}".format(epoch(now), epoch("max(time)")), "value")], table, window)
    if statistic == "oldest":
        latest = select([(entity, "entity"), ("max(time)", "latest")], table, lookback, group_by=["1"])
        return select([("{} - {}".format(epoch(now), epoch("min(latest)")), "value")],
                      "(\n{}\n) AS entities".format(indented(latest)))
    reported, expected = {
        "entities": (scalar("count(DISTINCT {})".format(entity), table, batch),
                     scalar("count(DISTINCT {})".format(entity), table, lookback)),
        "metrics": (scalar(carried, table, batch), scalar(carried, table, window)),
        "volume": (scalar("count(*)", table, recent), "{} / {}.0".format(scalar("count(*)", table, window), QUARTERS)),
    }[statistic]
    return "SELECT\n    {} AS reported,\n    {} AS expected".format(reported, expected)


def combined(arms, statistic):
    if STATISTICS[statistic] == "ratio":
        return "SELECT\n    100.0 * sum(reported) / NULLIF(sum(expected), 0) AS value\nFROM (\n{}\n) AS arms".format(
            indented("\nUNION ALL\n".join(arms)))
    if len(arms) == 1:
        return arms[0]
    return "SELECT\n    {}(value) AS value\nFROM (\n{}\n) AS arms".format(
        STATISTICS[statistic], indented("\nUNION ALL\n".join(arms)))


def scalar(expression, table, predicates):
    return "({})".format(flat(select([(expression, "")], table, predicates)))


def flat(statement):
    return " ".join(line.strip() for line in statement.split("\n"))


def indented(statement):
    return "\n".join("    " + line for line in statement.split("\n"))


def restricted(column, entities):
    return [literals(column, entities, negate=False)] if entities else []

