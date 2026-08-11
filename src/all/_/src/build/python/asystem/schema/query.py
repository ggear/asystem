import re
from dataclasses import dataclass

NULL = "-"
YES = "yes"
NO = "no"
SUBJECT = "*"
UNDECLARED = "<string>"
WIDTH = 300
CELL = 8
KEYED = 15
STAMPED = 19
SAMPLES = 100
GUARD = 100
BUCKET = "1 day"
BUCKETS = ("1 minute", "5 minute", "15 minute", "1 hour", "6 hour", "1 day")
DURATIONS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "h": 3600,
    "hour": 3600,
    "d": 86400,
    "day": 86400,
}


@dataclass
class SchemaDialect:
    source: object = None
    predicates: object = None
    groups: object = None
    measured: object = None
    counted: object = None
    stamped: object = None
    entity: object = None
    declared: object = None
    undeclared: object = None
    bucket: object = None
    subject: object = None
    alias: object = None
    aggregate: object = None
    windowed: object = None
    floor: str = ""


def banner(prefix="#"):
    rule = prefix * (80 // len(prefix))
    return "{0}\n{1} WARNING: This file is written by the build process, any manual edits will be lost!\n{0}".format(
        rule, prefix)


def vocabulary(relation, prefix="#", tags=(), entities=None):
    lines = ["{} {} [{}]".format(prefix, relation.path, relation.description)]
    if relation.cadence:
        lines.append("{}   cadence {}".format(prefix, relation.cadence))
    for dimension in list(tags) + list(relation.dimensions):
        lines += _tagged(relation, dimension, prefix, entities)
    for measure in relation.measures:
        lines.append("{}   field {} {} {} [{}]{}".format(
            prefix, measure.key, measure.unit or NULL, relation.span(measure) or NULL,
            measure.description, "" if measure.persist else " (not persisted)"))
    return lines


def expanded(relation, dimension, entities=None):
    values = dimension.entities or (entities or {}).get(dimension.key)
    if values is None:
        values = relation.entities if dimension.subject else []
    return list(values)


def select(selectors, source, predicates=(),
           group_by=(), having=(), order_by=()):
    width = max([len(expression) for expression, alias in selectors if alias and "\n" not in expression] or [0])
    rendered = []
    for expression, alias in selectors:
        if "\n" in expression:
            wrapped = indent(expression)
            rendered.append("\n".join(wrapped[:-1] + ["{} AS {}".format(wrapped[-1], alias)] if alias else wrapped))
        else:
            rendered.append("    {} AS {}".format(expression.ljust(width), alias) if alias else "    {}".format(expression))
    lines = ["SELECT"]
    lines += [line + "," for line in rendered[:-1]] + rendered[-1:]
    lines.append("FROM {}".format(source))
    if predicates:
        lines.append("WHERE")
        for index, predicate in enumerate(predicates):
            lines += indent(predicate if index == 0 else "AND " + predicate)
    if group_by:
        lines.append("GROUP BY {}".format(", ".join(group_by)))
    if having:
        lines.append("HAVING {}".format(" AND ".join(having)))
    if order_by:
        lines.append("ORDER BY {}".format(", ".join(order_by)))
    return "\n".join(lines)


def unioned(arms, order_by=()):
    joined = "\nUNION ALL\n".join(arm for arm in arms if arm)
    if joined and order_by:
        joined += "\nORDER BY {}".format(", ".join(order_by))
    return joined


def describe_statements(document, dialect):
    relations = sorted((relation for relation in document.relations if relation.persisted),
                       key=lambda relation: (dialect.source(relation), relation.path))
    return render_statements([
        "-- dimensions", _describe_relations(relations, dialect),
        "-- measures", _describe_measures(document, dialect),
        "-- entities", _describe_entities(relations, dialect)])


def query_statements(relations, dialect):
    statements = []
    for relation in relations:
        if not relation.persisted:
            statements.append("-- {} [{}] declares no persisted measure, so nothing is written for it"
                              .format(relation.path, relation.description))
            continue
        bucket = bucketed(relation.cadence, dialect.floor or None)
        heading = "-- {} [{}] every {}, bucketed [{}] across the newest two buckets".format(
            relation.path, relation.description, relation.cadence, bucket)
        selectors, keyed = [], {}
        for measure in relation.persisted:
            for function, suffix in aggregations(measure, relation.cadence):
                alias = "_".join(part for part in (dialect.alias(relation, measure), suffix) if part)
                selectors.append((dialect.aggregate(relation, measure, function), alias))
                keyed[alias] = measure.key
        if not selectors:
            continue
        subjects = dialect.subject(relation)
        label = labels(["bucket"] + [key for _, key in subjects] + [alias for _, alias in selectors])
        parts = parted(selectors, len(subjects) + 1, {alias: label[alias].strip('"') for _, alias in selectors})
        for index, part in enumerate(parts):
            statements.append(heading)
            statements.append("-- part {} of {}:".format(index + 1, len(parts)))
            rendered = [(dialect.bucket(bucket), label["bucket"])]
            rendered += [(expression, label[key]) for expression, key in subjects]
            rendered += [(expression, label[alias]) for expression, alias in part]
            grouping = [label["bucket"]] + [expression for expression, _ in subjects]
            statements.append(select(rendered, dialect.source(relation),
                                     dialect.windowed(relation, {keyed[alias] for _, alias in part}, bucket),
                                     group_by=grouping, order_by=grouping))
    return render_statements(statements)


def labels(names):
    return {name: '"{}"'.format(titled(name)) for name in names}


def titled(name):
    return " ".join(word.capitalize() for word in name.split("_"))


def bucketed(cadence, floor=None):
    span = duration(cadence)
    wanted = span * SAMPLES if span else duration(BUCKET)
    least = (duration(floor) or 0) if floor else 0
    return next((candidate for candidate in BUCKETS if (duration(candidate) or 0) >= (wanted or 0) and (duration(candidate) or 0) >= least), BUCKETS[-1])


def recent(source, bucket=BUCKET, now="now()"):
    return ["time >= {} - INTERVAL '{}'".format(now, guarded(bucket)), "time >= (SELECT max(time) FROM {}) - INTERVAL '{}'".format(source, bucket)]


def guarded(bucket, factor=GUARD):
    count, unit = bucket.split(" ", 1)
    return "{} {}".format(int(count) * factor, unit)


def parted(selectors, keys, headers=None, width=WIDTH):
    room = max(width - (STAMPED + 3) - (keys - 1) * (KEYED + 3) - 1, CELL + 3)
    parts, current, used = [], [], 0
    for selector in selectors:
        header = (headers or {}).get(selector[1], selector[1])
        if not isinstance(header, str):
            header = selector[1] if isinstance(selector[1], str) else ""
        cost = max(len(header), CELL) + 3
        if current and used + cost > room:
            parts.append(current)
            current, used = [], 0
        current.append(selector)
        used += cost
    return parts + ([current] if current else [])


def aggregations(measure, cadence=None):
    if measure.kind == "bool":
        return [("avg", "fraction")]
    if measure.kind == "int":
        return [("last", "")]
    span, bucket = duration(cadence), duration(BUCKET)
    if span is None or bucket is None or span >= bucket:
        return [("avg", "")]
    return [("avg", "avg"), ("min", "min"), ("max", "max")]


def duration(period):
    matched = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-z]+)\s*", (period or "").lower())
    if not matched:
        return None
    unit = matched.group(2)
    unit = unit if unit in DURATIONS else unit.rstrip("s")
    return float(matched.group(1)) * DURATIONS[unit] if unit in DURATIONS else None


def indent(text, pad="    "):
    return [pad + line for line in text.split("\n")]


def literals(column, values, negate=True, width: int | None = 92, pad="        "):
    quoted = ["'{}'".format(str(value).replace("'", "''")) for value in values]
    wrap = float("inf") if width is None else width
    lines, current = [], ""
    for index, value in enumerate(quoted):
        separator = "," if index < len(quoted) - 1 else ""
        if current and len(pad) + len(current) + 1 + len(value) + len(separator) > wrap:
            lines.append(current)
            current = ""
        current += (" " if current else "") + value + separator
    if current:
        lines.append(current)
    if len(lines) == 1:
        return "{} {}IN ({})".format(column, "NOT " if negate else "", lines[0])
    return "\n".join(["{} {}IN (".format(column, "NOT " if negate else "")] + indent("\n".join(lines)) + [")"])


def render_statements(rendered):
    blocks, block = [], []
    for statement in [statement for statement in rendered if statement]:
        if block and not block[-1].startswith("--"):
            blocks.append(block)
            block = []
        block.append(statement if statement.startswith("--") else statement + ";")
    if block:
        blocks.append(block)
    return banner("--") + "\n\n" + "\n\n".join("\n".join(block) for block in blocks) + "\n"


def declared_measure(relation, measure, unit, period):
    return [
        ("'{}'".format(relation.path), "relation"),
        ("'{}'".format(measure.key), "measure"),
        ("'{}'".format(measure.kind), "kind"),
        ("'{}'".format(unit), "unit"),
        ("'{}'".format(period), "period")
    ]


def declared_entity(relation, column=None):
    if relation.subject is None or not relation.entities:
        return "'{}'".format(NULL)
    return "CASE WHEN {} THEN '{}' ELSE '{}' END".format(
        literals(column or relation.subject.key, relation.entities, negate=False), YES, NO)


def dimension_label(relation):
    return "/".join(key.key + (SUBJECT if key.subject else "") for key in relation.dimensions) or NULL


def grouping_keys(entity, declared_expression):
    return [entity] + ([declared_expression] if declared_expression.startswith("CASE") else [])


def stamped(function, expression):
    return "CAST({}({}) AS VARCHAR)".format(function, expression)


def _tagged(relation, dimension, prefix, entities=None):
    values = expanded(relation, dimension, entities)
    heading = "{}   tag {}{} [{}".format(
        prefix, dimension.key, SUBJECT if dimension.subject else "", dimension.description)
    if not values and not dimension.subject:
        return [heading + "]"]
    if not values:
        values = [UNDECLARED]
    return ([heading + ":"] +
            ["{}     {},".format(prefix, value) for value in values[:-1]] +
            ["{}     {}]".format(prefix, values[-1])])


def _describe_relations(relations, dialect):
    return unioned([
        select([("'{}'".format(relation.path), "relation"), ("'{}'".format(dimension_label(relation)), "dimension"),
                ("{}".format(len(relation.measures)), "measures"),
                ("'{}'".format(relation.cadence), "cadence"),
                ("count(*)", "rows"), (stamped("min", "time"), "oldest"), (stamped("max", "time"), "newest")],
               dialect.source(relation), dialect.predicates(relation))
        for relation in relations], order_by=["rows DESC"])


def _describe_measures(document, dialect):
    arms = []
    for group, relations in dialect.groups(document):
        declared, keyed = set(), set()
        for relation in relations:
            persisted = {measure.key for measure in relation.persisted}
            for measure in relation.measures:
                keyed.add(measure.key)
                if measure.key not in persisted:
                    continue
                declared.add(measure.key)
                arms.append(select(
                    declared_measure(relation, measure, measure.unit or NULL, relation.span(measure) or NULL) + [
                        (dialect.counted(measure), "rows"),
                        (dialect.stamped("min", measure), "oldest"),
                        (dialect.stamped("max", measure), "newest")],
                    dialect.source(relation), dialect.measured(relation, measure)))
        arms.append(dialect.undeclared(group, relations, sorted(declared), sorted(keyed)))
    return unioned(arms, order_by=["rows DESC NULLS LAST"])


def _describe_entities(relations, dialect):
    arms = [relation for relation in relations if relation.dimensions]
    return unioned([
        select([("'{}'".format(relation.path), "relation"),
                ("'{}'".format(dimension_label(relation)), "dimension"), (dialect.entity(relation), "entity"),
                (dialect.declared(relation), "declared"), ("count(*)", "rows"),
                (stamped("min", "time"), "oldest"), (stamped("max", "time"), "newest")],
               dialect.source(relation), dialect.predicates(relation),
               group_by=grouping_keys(dialect.entity(relation), dialect.declared(relation)))
        for relation in arms], order_by=["rows DESC"])
