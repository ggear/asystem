import contextlib
import glob
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from os.path import abspath, basename, dirname, join, realpath
from pathlib import Path
from unittest import mock

import pandas as pd
import yaml
from grafana_foundation_sdk.builders import stat as stats

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_REPOSITORY = abspath(join(DIR_ROOT, "../../.."))
DIR_DASHBOARDS = join(DIR_ROOT, "src/main/resources/data/dashboards")
GENERATE = join(DIR_ROOT, "src/build/python/grafana/generate.py")

sys.path.insert(0, join(DIR_REPOSITORY, "src/all/_/src/build/python"))
sys.argv = [GENERATE]

from asystem.schema.dialects import influxdb3, postgres
from asystem.schema.panel import judged
from asystem.schema.document import (
    SchemaDatabaseDimension,
    SchemaDatabaseMeasure,
    SchemaDatabaseRelation,
    SchemaDocument,
    load_schema_artifact,
    load_schema_document,
    parse_schema_document,
    render_schema_artifact,
    schema_source,
)

specification = importlib.util.spec_from_file_location("generate", GENERATE)
generate = importlib.util.module_from_spec(specification)
specification.loader.exec_module(generate)

ARTIFACTS = sorted(glob.glob(join(DIR_REPOSITORY, "src/*/*/src/build/resources/schema/*/document.json")))

HOSTS = SchemaDatabaseRelation(
    path="supervisor/host", cadence="6s", entities=["alpha", "beta"],
    dimensions=[SchemaDatabaseDimension(key="host", subject=True)],
    measures=[SchemaDatabaseMeasure(key="status", kind="bool"),
              SchemaDatabaseMeasure(key="used_processor", kind="int", unit="%"),
              SchemaDatabaseMeasure(key="restart_count", kind="float")])
SERVICES = SchemaDatabaseRelation(
    path="supervisor/service", cadence="6s", entities=["grafana"],
    dimensions=[SchemaDatabaseDimension(key="host"), SchemaDatabaseDimension(key="service", subject=True)],
    measures=[SchemaDatabaseMeasure(key="status", kind="bool")])
SUPERVISOR = SchemaDocument(module="supervisor", relations=[HOSTS, SERVICES])
RATES = SchemaDatabaseRelation(
    path="currency/rate", cadence="1d", entities=["AUD/GBP", "AUD/USD"],
    dimensions=[SchemaDatabaseDimension(key="entity", subject=True)],
    measures=[SchemaDatabaseMeasure(key="snapshot", kind="float", unit="$", period="1d"),
              SchemaDatabaseMeasure(key="delta", kind="float", unit="%", period="1d"),
              SchemaDatabaseMeasure(key="delta", kind="float", unit="%", period="7d")])
WRANGLE = SchemaDocument(module="wrangle", relations=[RATES])
COLUMNS = ["index", "entity_status", "device_via_device", "entity_namespace", "unique_id", "friendly_name",
           "entity_domain", "entity_group", "grafana_display_type", "unit_of_measurement", "grafana_kpi", "grafana_group"]
RACK_TOP = "compensation_sensor_rack_top_temperature"
RACK_BOTTOM = "compensation_sensor_rack_bottom_temperature"
LOUNGE_HUMIDITY = "office_lounge_humidity"


class SchemaArtifactTest(unittest.TestCase):

    def test_every_artifact_parses_and_round_trips(self):
        self.assertGreaterEqual(len(ARTIFACTS), 4, "artifacts: got {} want at least 4".format(len(ARTIFACTS)))
        for path in ARTIFACTS:
            module = basename(dirname(dirname(dirname(dirname(dirname(dirname(path)))))))
            document = load_schema_artifact(module, basename(dirname(path)), DIR_REPOSITORY)
            again = parse_schema_document(render_schema_artifact(document), module)
            self.assertEqual(again, document, "{}: round trip got a different document".format(path))

    def test_a_reflector_that_omits_a_database_key_is_refused(self):
        complete = {"key": "value", "kind": "float", "unit": "", "description": "", "persist": True, "period": "", "levels": None}
        omitted = {key: value for key, value in complete.items() if key != "period"}
        for measure, refused in [(complete, False), (omitted, True)]:
            text = json.dumps({"module": "probe", "database": {"relations": [{
                "path": "probe/reading", "description": "", "cadence": "", "entities": [],
                "dimensions": [], "measures": [measure]}]}})
            parse_schema_document(text, "probe")
            if refused:
                with self.assertRaises(ValueError):
                    parse_schema_document(text, "probe", True)
            else:
                parse_schema_document(text, "probe", True)

    def test_a_python_reflection_matches_its_committed_artifact(self):
        wrangle = join(DIR_REPOSITORY, "src/mad/wrangle")
        self.assertEqual(load_schema_document(wrangle).relations, load_schema_artifact("wrangle", "postgres").relations)

    def test_an_artifact_older_than_its_source_warns(self):
        repository = tempfile.mkdtemp()
        try:
            module = join(repository, "src/all/probe")
            artifact = join(module, "src/build/resources/schema/influxdb3/document.json")
            source = join(module, "src/main/python/probe/plugin/schema.py")
            for path in (artifact, source):
                Path(dirname(path)).mkdir(parents=True)
            Path(source).write_text("RELATIONS = []\n")
            for hashed, warns in [(schema_source(module), False), ("stale", True)]:
                Path(artifact).write_text(json.dumps({"source": hashed, "module": "probe"}))
                warnings = io.StringIO()
                with contextlib.redirect_stderr(warnings):
                    load_schema_artifact("probe", "influxdb3", repository)
                self.assertEqual("older than its source" in warnings.getvalue(), warns,
                                 "{}: warning got wrong".format(hashed))
        finally:
            shutil.rmtree(repository)


class LevelsTest(unittest.TestCase):

    def test_levels_parse_and_refuse_what_cannot_colour(self):
        def parsed(kind, levels):
            return parse_schema_document(json.dumps({"module": "probe", "database": {"relations": [{
                "path": "probe/reading", "description": "", "cadence": "", "entities": ["a", "b"],
                "dimensions": [{"key": "reading", "description": "", "subject": True, "entities": []}],
                "measures": [{"key": "value", "kind": kind, "unit": "%", "description": "", "persist": True, "period": "", "levels": levels}]}]}}), "probe", True)
        good = {"better": "higher", "amber": 85, "red": 50, "inclusive": True, "entities": {"a": {"amber": 35, "red": None}}}
        levels = parsed("float", good).relations[0].measures[0].levels
        self.assertEqual((levels.better, levels.amber, levels.red, levels.entities["a"].amber), ("higher", 85, 50, 35))
        for kind, refused in [("float", {**good, "better": "sideways"}), ("float", {**good, "red": 90}), ("bool", good),
                              ("float", {**good, "amber": "85"}), ("float", {**good, "entities": {"z": {"amber": 1, "red": None}}}),
                              ("float", {key: value for key, value in good.items() if key != "inclusive"}),
                              ("float", {"better": "higher", "amber": None, "red": None, "inclusive": True, "entities": {}})]:
            with self.assertRaises(ValueError, msg=str(refused)):
                parsed(kind, refused)

    def test_a_ladder_puts_the_bound_on_the_side_the_schema_says_is_healthy(self):
        epsilon = generate.LEVEL_EPSILON
        for levels, ladder in [
            (generate.Levels("higher", 85, None, True), [(None, "yellow"), (85, "green")]),
            (generate.Levels("higher", 50, 35, True), [(None, "red"), (35, "yellow"), (50, "green")]),
            (generate.Levels("higher", None, 35, False), [(None, "red"), (35 + epsilon, "green")]),
            (generate.Levels("lower", 2, None, True), [(None, "green"), (2 + epsilon, "yellow")]),
            (generate.Levels("lower", 70, 90, True), [(None, "green"), (70 + epsilon, "yellow"), (90 + epsilon, "red")]),
            (generate.Levels("lower", None, 80, False), [(None, "green"), (80, "red")]),
        ]:
            self.assertEqual(generate.levelled(levels), ladder, str(levels))

    def test_a_stat_colours_itself_from_the_levels_of_the_measure_it_shows(self):
        switches = generate.Relation("network", "ethernet/switch")
        declared = declared_levels(switches, "experience_pct")
        defaults = generate.stat("Wired", switches.query(["experience_pct"], None, ("min",))).build(1).build().spec.viz_config.spec.field_config.defaults
        self.assertEqual([(step.value, step.color) for step in defaults.thresholds.steps],
                         generate.levelled(generate.Levels(declared.better, declared.amber, declared.red, declared.inclusive)))

    def test_per_entity_levels_resolve_only_when_the_picked_entities_agree(self):
        experience = generate.Relation("network", "zigbee/experience")
        declared = declared_levels(experience, "experience_pct")
        self.assertNotEqual(declared.entities["router"].amber, declared.entities["mesh"].amber)
        for entity in ("router", "mesh"):
            self.assertEqual(experience.query(["experience_pct"], [entity]).levels.amber, declared.entities[entity].amber, entity)
        self.assertIsNone(experience.query(["experience_pct"]).levels)

    def test_only_an_operation_that_shows_the_worst_side_keeps_levels(self):
        experience, latency = generate.Relation("network", "ethernet/switch"), generate.Relation("network", "internet/target")
        for relation, measure, kept, dropped in [(experience, "experience_pct", [("min",), ("trough",)], [("max",), ("peak",)]),
                                                 (latency, "rtt_ms", [("max",), ("peak",)], [("min",), ("trough",)])]:
            for transforms in kept:
                self.assertIsNotNone(relation.query([measure], None, transforms).levels, f"{measure} {transforms}")
            for transforms in dropped:
                self.assertIsNone(relation.query([measure], None, transforms).levels, f"{measure} {transforms}")
        for relation, measure, kept, dropped in [(experience, "experience_pct", "min", "max"), (latency, "rtt_ms", "max", "min")]:
            self.assertIsNotNone(generate.stat("Kept", relation.query([measure]), kept).levels, f"{measure} reducer {kept}")
            self.assertIsNone(generate.stat("Dropped", relation.query([measure]), dropped).levels, f"{measure} reducer {dropped}")

    def test_the_levels_vocabulary_is_declared_alike_by_its_owner_and_every_go_emitter(self):
        owner = Path(DIR_REPOSITORY, "src/all/_/src/build/python/asystem/schema/document.py").read_text()
        declared = {"document.py": {(name, value) for name, value in re.findall(r'^BETTER_([A-Z]+) = "(\w+)"$', owner, re.M)}}
        for emitter in ("src/mad/network/src/main/go/network/internal/schema/schema.go",
                        "src/all/supervisor/src/main/go/supervisor/internal/schema/schema.go"):
            source = Path(DIR_REPOSITORY, emitter).read_text()
            declared[emitter] = {(name.upper(), value) for name, value in re.findall(r'^\s*Better([A-Z][a-z]+)\s+Better = "(\w+)"$', source, re.M)}
        for origin, vocabulary in declared.items():
            self.assertTrue(vocabulary, f"{origin}: parsed no levels vocabulary, the pattern no longer matches the source")
        self.assertEqual(len({frozenset(vocabulary) for vocabulary in declared.values()}), 1, f"levels vocabulary disagrees {declared}")

    def test_levels_drop_wherever_the_number_shown_is_not_the_number_judged(self):
        switches = generate.Relation("network", "ethernet/switch")
        for transforms in [("sum",), ("percent",), ("baseline",)]:
            self.assertIsNone(switches.query(["experience_pct"], None, transforms).levels, str(transforms))
        self.assertIsNone(switches.query(["experience_pct", "cpu_pct"]).levels)
        self.assertIsNotNone(switches.query(["experience_pct"], None, ("avg",)).levels)
        declared = declared_levels(switches, "experience_pct")
        mean = generate.stat("Mean", switches.query(["experience_pct"]), "mean").build(1).build().spec.viz_config.spec.field_config.defaults
        best = generate.stat("Best", switches.query(["experience_pct"]), "max").build(1).build().spec.viz_config.spec.field_config.defaults
        self.assertEqual([(step.value, step.color) for step in mean.thresholds.steps],
                         generate.levelled(generate.Levels(declared.better, declared.amber, declared.red, declared.inclusive)))
        self.assertEqual([(step.value, step.color) for step in best.thresholds.steps], generate.NEUTRAL_LADDER)

    def test_hand_written_thresholds_on_a_levelled_stat_are_refused_unless_deliberate(self):
        query = generate.Relation("network", "ethernet/switch").query(["experience_pct"], None, ("min",))
        with self.assertRaises(ValueError):
            generate.stat("Wired", query).thresholds(generate.higher_better(85, 95))
        generate.stat("Wired", query).thresholds(generate.higher_better(85, 95), override=True).build(1)

    def test_a_time_series_draws_its_measures_levels_as_a_dashed_line(self):
        def drawn(panel):
            defaults = panel.build(1).build().spec.viz_config.spec.field_config.defaults
            return getattr(defaults.custom.thresholds_style, "mode", None), [(step.value, step.color) for step in (defaults.thresholds.steps if defaults.thresholds else [])]
        loss = generate.Relation("network", "internet/target")
        declared = declared_levels(loss, "loss_pct")
        self.assertEqual(drawn(generate.series("Loss", loss.query(["loss_pct"]))),
                         ("dashed", generate.levelled(generate.Levels(declared.better, declared.amber, declared.red, declared.inclusive))))
        self.assertEqual(drawn(generate.series("Clients", generate.Relation("network", "wireless/accesspoint").query(["clients"])))[0], None)
        experience = generate.Relation("network", "zigbee/experience")
        self.assertEqual(drawn(generate.series("Zigbee", experience.query(["experience_pct"])))[0], None)

    def test_queries_whose_levels_disagree_need_explicit_thresholds(self):
        experience = generate.Relation("network", "zigbee/experience")
        queries = [experience.query(["experience_pct"], ["router"]), experience.query(["experience_pct"], ["mesh"])]
        with self.assertRaises(ValueError):
            generate.stat("Zigbee", queries).build(1)
        generate.stat("Zigbee", queries).thresholds(generate.higher_better(35, 50)).build(1)


class PanelSqlTest(unittest.TestCase):

    def test_a_level_follows_every_transform_that_keeps_its_meaning(self):
        for transforms, unit, levels, wanted in [
            ((), "", ("higher", 1, None, True), ("higher", 1, None, True)),
            (("percent", "avg"), "", ("higher", None, 1, True), ("higher", None, 100, True)),
            (("percent",), "%", ("higher", 85, None, True), None),
            (("complement",), "", ("higher", 1, None, True), ("lower", 0, None, True)),
            (("complement", "percent"), "", ("higher", 0.9, 0.5, True), ("lower", 10, 50, True)),
            (("invert",), "$", ("lower", 0.5, 0.8, True), ("higher", 2, 1.25, True)),
            (("invert",), "%", ("lower", 25, None, True), ("higher", -20, None, True)),
            (("invert",), "", ("lower", 0, 0.8, True), None),
            (("invert",), "%", ("higher", None, -100, True), None),
            (("peak",), "", ("lower", 100, None, True), ("lower", 100, None, True)),
            (("trough", "min"), "", ("higher", 35, None, True), ("higher", 35, None, True)),
            (("peak",), "", ("higher", 35, None, True), None),
            (("trough",), "", ("lower", 100, None, True), None),
            (("max",), "", ("higher", 35, None, True), None),
            (("sum",), "", ("higher", 1, None, True), None),
            (("counter",), "", ("lower", 5, None, True), None),
            (("baseline",), "$", ("lower", 0.5, None, True), None),
            (("compass",), "°", ("lower", 1, None, True), None),
        ]:
            self.assertEqual(judged(*levels, unit, transforms), wanted, "{}: levels got wrong".format(transforms))

    def test_transforms_render_into_the_series_statement(self):
        for dialect, relation, document, measures, transforms, wanted in [
            (influxdb3, HOSTS, SUPERVISOR, ["status"], ("percent", "min"),
             ["avg(status * 100)", "min(value) AS value", "GROUP BY time, measure", "measure AS metric"]),
            (influxdb3, HOSTS, SUPERVISOR, ["status"], ("complement", "sum"), ["avg(1 - status)", "sum(value)"]),
            (influxdb3, HOSTS, SUPERVISOR, ["restart_count"], ("counter",), ["max(restart_count)", "entity AS metric"]),
            (influxdb3, HOSTS, SUPERVISOR, ["used_processor"], ("peak",), ["max(used_processor)"]),
            (influxdb3, HOSTS, SUPERVISOR, ["used_processor"], ("trough",), ["min(used_processor)"]),
            (influxdb3, HOSTS, SUPERVISOR, ["used_processor"], ("bearing",), ["atan2(avg(sin(radians(used_processor))), avg(cos(radians(used_processor))))"]),
            (influxdb3, HOSTS, SUPERVISOR, ["used_processor"], ("compass",), ["atan2(avg(sin(radians(used_processor)))", "/ 22.5"]),
            (influxdb3, HOSTS, SUPERVISOR, ["status", "used_processor"], (),
             ["entity || ' ' || measure AS metric", "UNION ALL", "status IS NOT NULL", "service IS NULL"]),
            (influxdb3, SERVICES, SUPERVISOR, ["status"], (), ["concat(host, '/', service)", "service IS NOT NULL"]),
            (postgres, RATES, WRANGLE, ["snapshot"], ("invert", "baseline"),
             ["avg(1.0 / value)", "first_value(value) OVER (PARTITION BY metric ORDER BY time)",
              "$__timeGroupAlias(time, $__interval)"]),
            (postgres, RATES, WRANGLE, ["delta@7d"], ("invert",),
             ["avg(10000.0 / (100 + value) - 100)", "period = '7d'", "'delta' "]),
            (postgres, RATES, WRANGLE, ["delta"], (), ["'delta 1d' AS measure", "'delta 7d' AS measure"]),
        ]:
            sql = dialect.panel(relation, document, measures, None, transforms)
            for fragment in wanted:
                self.assertIn(fragment, sql, "{} {}: got no [{}]".format(measures, transforms, fragment))
            self.assertTrue(sql.endswith("ORDER BY time"), "{}: got unordered want ORDER BY time".format(measures))

    def test_entities_and_labels_render_as_a_filter_and_a_case(self):
        sql = postgres.panel(RATES, WRANGLE, ["snapshot"], ["AUD/GBP"], (), {"AUD/GBP": "GBP/AUD"})
        self.assertIn("entity IN ('AUD/GBP')", sql)
        self.assertIn("CASE entity WHEN 'AUD/GBP' THEN 'GBP/AUD' ELSE entity END", sql)
        self.assertIn("entity AS metric", sql)

    def test_labels_match_the_subject_when_the_entity_spans_several_dimensions(self):
        reading = SchemaDatabaseRelation(
            path="sensor__temperature", cadence="<on-change>",
            dimensions=[SchemaDatabaseDimension(key="entity_id", subject=True),
                        SchemaDatabaseDimension(key="unit_of_measurement")],
            measures=[SchemaDatabaseMeasure(key="value", kind="float")])
        sql = influxdb3.panel(reading, SchemaDocument(module="homeassistant", relations=[reading], discovered=True),
                              ["value"], ["roof"], (), {"roof": "Roof"})
        self.assertIn("CASE entity_id WHEN 'roof' THEN 'Roof' ELSE concat(entity_id, '/', unit_of_measurement) END",
                      sql)
        self.assertIn("entity_id IN ('roof')", sql)

    def test_invalid_selections_are_refused(self):
        for measures, chosen, transforms in [
            (["missing"], None, ()),
            (["delta@30d"], None, ()),
            (["snapshot"], ["AUD/EUR"], ()),
            (["snapshot"], None, ("unknown",)),
            (["snapshot"], None, ("sum", "max")),
        ]:
            with self.assertRaises(ValueError, msg="{} {} {}: got accepted want refused".format(
                    measures, chosen, transforms)):
                postgres.panel(RATES, WRANGLE, measures, chosen, transforms)

    def test_summaries_measure_freshness_coverage_and_volume(self):
        for statistic, wanted in [
            ("newest", ["to_unixtime($__timeTo()) - to_unixtime(max(time)) AS value", "host IN ('alpha')"]),
            ("oldest", ["to_unixtime($__timeTo()) - to_unixtime(min(latest)) AS value", "GROUP BY 1",
                        "time > $__timeTo() - INTERVAL '2592000 seconds'"]),
            ("entities", ["count(DISTINCT host)", "INTERVAL '600 seconds'", "100.0 * sum(reported)"]),
            ("metrics", ["CASE WHEN count(status) > 0 THEN 1 ELSE 0 END", "AS expected"]),
            ("volume", ["to_unixtime(time) > (3 * to_unixtime($__timeTo()) + to_unixtime($__timeFrom())) / 4",
                        "/ 4.0"]),
        ]:
            sql = influxdb3.summary([(HOSTS, ["alpha"])], SUPERVISOR, statistic, 300)
            for fragment in wanted:
                self.assertIn(fragment, sql, "{}: got no [{}]".format(statistic, fragment))

    def test_held_weights_each_row_by_the_time_until_the_next(self):
        sql = influxdb3.held(SERVICES, SUPERVISOR, "status", ["grafana"])
        for fragment in ["lead(time) OVER (PARTITION BY concat(host, '/', service) ORDER BY time)",
                         "coalesce(", "$__timeTo()", "100.0 * sum(value * held) / NULLIF(sum(held), 0)",
                         "service IN ('grafana')", "status IS NOT NULL"]:
            self.assertIn(fragment, sql, "held: got no [{}]".format(fragment))

    def test_summaries_combine_sources_and_scale_the_lookback_with_the_span(self):
        self.assertIn("min(value) AS value",
                      influxdb3.summary([(HOSTS, None), (HOSTS, ["beta"])], SUPERVISOR, "newest", 300))
        self.assertIn("max(value) AS value",
                      influxdb3.summary([(HOSTS, None), (HOSTS, ["beta"])], SUPERVISOR, "oldest", 300))
        monthly = postgres.summary([(RATES, None)], WRANGLE, "entities", 45 * 86400)
        self.assertIn("INTERVAL '15552000 seconds'", monthly)
        self.assertIn("count(DISTINCT entity)", monthly)
        with self.assertRaises(ValueError):
            influxdb3.summary([(HOSTS, None)], SUPERVISOR, "unknown", 300)


class SeriesTest(unittest.TestCase):

    def test_a_query_takes_its_unit_and_descriptions_from_the_measures_it_picks(self):
        rate = generate.Relation("wrangle", "currency/rate")
        weekly = rate.query(["delta@7d"])
        self.assertEqual((weekly.unit, weekly.description), ("%", "change in the rate across [1 Week Delta]"))
        self.assertEqual(rate.query(["snapshot"]).unit, "$")
        self.assertEqual(rate.query(["snapshot"], None, ("baseline",)).unit, "%")
        self.assertEqual(rate.query(["snapshot"], None, (), None, "").unit, "")
        self.assertEqual(rate.query(["snapshot"]).interval, "1d")
        self.assertEqual(generate.series("Weekly", weekly).build(1).build().spec.description,
                         "Generated: change in the rate across [1 Week Delta]")

    def test_mixed_units_are_refused_unless_one_is_given(self):
        rate = generate.Relation("wrangle", "currency/rate")
        with self.assertRaises(ValueError):
            rate.query(["snapshot", "delta@1d"])
        with self.assertRaises(ValueError):
            generate.series("Mixed", [rate.query(["snapshot"]), rate.query(["delta@1d"])])
        self.assertEqual(generate.series("Given", [rate.query(["snapshot"]), rate.query(["delta@1d"])], "%")
                         .build(1).build().spec.viz_config.spec.field_config.defaults.unit, "percent")

    def test_every_series_shows_the_legend_table_even_for_one_line(self):
        rate = generate.Relation("wrangle", "currency/rate")
        for queries in [rate.query(["snapshot"], ["AUD/GBP"]), rate.query(["snapshot"])]:
            legend = generate.series("Legend", queries).build(1).build().spec.viz_config.spec.options.legend
            self.assertEqual((legend.show_legend, legend.display_mode, legend.placement, legend.calcs),
                             (True, "table", "right", ["min", "max", "mean"]))

    def test_decimals_follow_the_unit(self):
        rate = generate.Relation("wrangle", "currency/rate")
        for query, decimals in [(rate.query(["snapshot"]), 3), (rate.query(["delta@1d"]), 1)]:
            defaults = generate.series("Decimals", query).build(1).build().spec.viz_config.spec.field_config.defaults
            self.assertEqual(defaults.decimals, decimals)

    def test_a_state_timeline_draws_its_labelled_states_inside_the_time_series_margins(self):
        visualization = generate.state("Up", generate.Relation("network", "ethernet/switch").query(["up"]), ("Down", "Up")).build(1).build().spec.viz_config
        layout = json.loads(visualization.spec.options["getOption"].split("\n", 1)[0].removeprefix("const layout = ").removesuffix(";"))
        self.assertEqual((visualization.group, layout), (generate.ECHARTS_PANEL, {
            "axis": generate.AXIS_WIDTH,
            "legend": generate.LEGEND_WIDTH,
            "states": [{"from": None, "colour": "red", "text": "Down"}, {"from": 1, "colour": "green", "text": "Up"}],
        }))
        query = generate.Series(influxdb3, generate.INFLUXDB3, "SELECT 1", "", "", "", "time_series")
        widths = {build.__name__: build("Plot", query).build(1).build().spec.viz_config.spec.field_config.defaults.custom.axis_width
                  for build in (generate.series, generate.steps, generate.points, generate.bars)}
        self.assertEqual(widths, dict.fromkeys(widths, generate.AXIS_WIDTH))

    def test_a_unit_maps_to_its_grafana_unit_or_falls_back_to_a_suffix(self):
        for unit, wanted in [("km/h", ("velocitykmh", 1)), ("furlong", ("suffix: furlong", 2)), ("", ("none", 2))]:
            defaults = generate.stat("Unit", generate.Series(influxdb3, generate.INFLUXDB3, "SELECT 1", unit, "", "", "table")).build(1).build().spec.viz_config.spec.field_config.defaults
            self.assertEqual((defaults.unit, defaults.decimals), wanted, "{}: unit got wrong".format(unit))

    def test_a_header_over_an_on_change_relation_needs_a_ceiling(self):
        relation = generate.Relation("homeassistant", "sensor__temperature")
        with self.assertRaises(ValueError):
            generate.header([(relation, [RACK_TOP])], "homeassistant")
        panels = generate.header([(relation, [RACK_TOP])], "homeassistant", 3600)
        self.assertEqual([panel.title for panel in panels],
                         ["Newest", "Oldest", "Availability", "Entities", "Metrics", "Volume"])
        steps = panels[5].build(1).build().spec.viz_config.spec.field_config.defaults.thresholds.steps
        self.assertEqual([(step.value, step.color) for step in steps], generate.VOLUME_LADDER)

    def test_a_template_takes_its_table_entity_and_scope_from_the_relation(self):
        ticker = generate.Relation("wrangle", "equity/ticker")
        series = ticker.sql("""
SELECT $entity, value
FROM $table
WHERE
    $scope
""", "%", "why it is hand-written", scope=ticker.scope("price-close-spot", ["AXJO"]))
        self.assertEqual(series.sql, "SELECT entity, value\nFROM equity\nWHERE\n    $__timeFilter(time)\n"
                                     "    AND type = 'price-close-spot'\n    AND period = '1d'\n    AND unit = '$'\n"
                                     "    AND entity IN ('AXJO')")
        self.assertEqual((series.dialect, series.datasource, series.unit, series.interval, series.description),
                         (postgres, generate.POSTGRES, "%", "1d", "why it is hand-written"))
        built = generate.series("Sql", series).build(1).build()
        self.assertEqual(built.spec.description, "Hand-written: why it is hand-written")
        self.assertEqual(generate.series("Mixed", [series, ticker.query(["price-close-spot"], ["AXJO"])], "%")
                         .build(1).build().spec.description,
                         "Hand-written: daily price close spot reading; why it is hand-written")
        self.assertEqual(built.spec.data.spec.queries[0].spec.query.group, postgres.GRAFANA)
        self.assertEqual(built.spec.data.spec.query_options.interval, "1d")

    def test_placeholders_and_values_must_pair_and_grafana_macros_are_left_alone(self):
        ticker = generate.Relation("wrangle", "equity/ticker")
        for statement, values in [("SELECT $entity FROM $table WHERE $missing", {}),
                                  ("SELECT $entity FROM $table", {"unused": "1"})]:
            with self.assertRaises(ValueError, msg=statement):
                ticker.sql(statement, "%", "", **values)
        self.assertEqual(ticker.sql("SELECT $__timeGroupAlias(time, $__interval) FROM $table", "%", "").sql,
                         "SELECT $__timeGroupAlias(time, $__interval) FROM equity")

    def test_a_scope_refuses_what_the_schema_does_not_declare_or_cannot_tell_apart(self):
        for path, measure, chosen in [("equity/ticker", "price-close-spot", ["NOPE"]),
                                      ("equity/ticker", "nope", ["AXJO"]),
                                      ("currency/rate", "delta", ["AUD/GBP"])]:
            with self.assertRaises(ValueError, msg="{} {} {}".format(path, measure, chosen)):
                generate.Relation("wrangle", path).scope(measure, chosen)


class LayoutTest(unittest.TestCase):

    def test_rows_wrap_under_their_tallest_panel(self):
        with declared("layout"):
            resource = generate.dashboard("layout", generate.WEEK_WINDOW, [panel(24, 3)],
                                          [[panel(5, 3), panel(5, 3), panel(5, 3), panel(9, 8),
                                            panel(5, 5), panel(5, 5)], [panel(24, 12)]])
        self.assertEqual(laid(resource), [(0, 0, 24, 3), (0, 3, 5, 3), (5, 3, 5, 3), (10, 3, 5, 3), (15, 3, 9, 8),
                                          (0, 6, 5, 5), (5, 6, 5, 5), (0, 11, 24, 12)])
        self.assertEqual([element["spec"]["id"] for element in resource["spec"]["elements"].values()],
                         list(range(1, 9)))

    def test_a_panel_wider_than_the_grid_is_refused(self):
        with declared("layout"), self.assertRaisesRegex(ValueError, "wider"):
            generate.dashboard("layout", generate.WEEK_WINDOW, [panel(25, 3)], [])

    def test_an_undeclared_or_repeated_dashboard_is_refused(self):
        with self.assertRaisesRegex(ValueError, "no folder"):
            generate.dashboard("undeclared", generate.WEEK_WINDOW, [panel(24, 3)], [])
        with declared("layout"), self.assertRaisesRegex(ValueError, "twice"):
            generate.dashboard("layout", generate.WEEK_WINDOW, [panel(24, 3)], [])
            generate.dashboard("layout", generate.WEEK_WINDOW, [panel(24, 3)], [])


class WriterTest(unittest.TestCase):

    def test_a_pulled_export_keeps_only_its_name_and_folder(self):
        pulled = {
            "apiVersion": "dashboard.grafana.app/v2",
            "kind": "Dashboard",
            "status": {},
            "metadata": {
                "name": "server",
                "namespace": "default",
                "resourceVersion": "9",
                "generation": 2,
                "labels": {},
                "annotations": {
                    generate.FOLDER: "home",
                    "grafana.app/updatedBy": "x",
                },
            },
            "spec": {
                "title": "Pulled",
            },
        }
        self.assertEqual(generate.normalised(pulled, "custom"), {
            "apiVersion": "dashboard.grafana.app/v2",
            "kind": "Dashboard",
            "spec": {
                "title": "Pulled",
            },
            "metadata": {
                "name": "custom",
                "annotations": {
                    generate.FOLDER: "home",
                },
            },
        })

    def test_sql_is_a_block_and_integral_floats_are_ints(self):
        dumped = generate.dumped({
            "b": 1.0,
            "a": "SELECT\n    1",
            "c": 0.5,
        })
        self.assertEqual(dumped, "a: |-\n  SELECT\n      1\nb: 1\nc: 0.5\n")

    def test_every_generated_dashboard_opens_with_one_navigation_bar_marking_itself(self):
        paths = sorted(glob.glob(join(DIR_DASHBOARDS, "generated/*.yaml")))
        self.assertTrue(paths, "generated: got none want some")
        for path in paths:
            resource = yaml.safe_load(Path(path).read_text())
            first = resource["spec"]["layout"]["spec"]["items"][0]["spec"]
            self.assertEqual((first["element"]["name"], first["y"], first["width"]), (generate.NAVIGATION_ELEMENT, 0, 24), "{}: navigation got missing".format(path))
            content = resource["spec"]["elements"][generate.NAVIGATION_ELEMENT]["spec"]["vizConfig"]["spec"]["options"]["content"]
            self.assertLess(content.index("HOME"), content.index("FINANCE"), path)
            self.assertLess(content.index("FINANCE"), content.index("SYSTEMS"), path)
            self.assertEqual(content.count('<span style="color:{}">'.format(generate.SECTION_COLOUR)), 3, "{}: sections got wrong".format(path))
            self.assertIn(" **{}**".format(resource["spec"]["title"]), content, "{}: current got unmarked".format(path))
            self.assertNotIn("(/d/{}?".format(basename(path)[:-5]), content, "{}: current got linked".format(path))

    def test_every_resource_is_pinned_and_rewrites_unchanged(self):
        versions = set()
        for path in glob.glob(join(DIR_DASHBOARDS, "*/*.yaml")):
            body = Path(path).read_text().split(generate.BANNER + "\n", 1)[-1]
            resource = yaml.safe_load(body)
            versions.add(resource["apiVersion"])
            self.assertEqual(generate.dumped(generate.normalised(resource, resource["metadata"]["name"])), body, "{}: rewrite got a different file".format(path))
        self.assertEqual(versions, generate.API_VERSIONS)


class MetadataTest(unittest.TestCase):

    def test_a_graph_break_splits_a_domain_into_panels(self):
        resource = metadata(entities(
            entity(RACK_TOP), entity("graph_break", device="_"), entity(RACK_BOTTOM)))
        panels = [element["spec"] for element in resource["spec"]["elements"].values() if element["spec"]["vizConfig"]["group"] == "timeseries"]
        self.assertEqual([panel["title"] for panel in panels], ["Rack", "Rack"])
        self.assertEqual({panel["vizConfig"]["spec"]["fieldConfig"]["defaults"]["unit"] for panel in panels}, {"celsius"})
        self.assertEqual({panel["description"] for panel in panels}, {"Generated: Home Assistant Group Rack"})

    def test_the_kpi_row_takes_marked_rows_then_each_panel_head_then_the_rest(self):
        marked = entities(entity(RACK_TOP), entity(RACK_BOTTOM, kpi="max"), entity("graph_break", device="_"),
                          entity(LOUNGE_HUMIDITY, domain="Lounge"))
        resource = metadata(marked)
        self.assertEqual(strip(resource), [
            (RACK_BOTTOM.title() + " Max", 8, ["max"]),
            (RACK_TOP.title(), 8, ["lastNotNull"]),
            (LOUNGE_HUMIDITY.title(), 8, ["lastNotNull"]),
        ])
        peaked = [element["spec"] for element in resource["spec"]["elements"].values() if element["spec"]["title"] == RACK_BOTTOM.title() + " Max"][0]
        self.assertEqual(peaked["description"], "Generated: Home Assistant entity {}, maximum across the window".format(RACK_BOTTOM))
        self.assertIn("max(value)", peaked["data"]["spec"]["queries"][0]["spec"]["query"]["spec"]["rawSql"])

    def test_kpi_titles_name_the_measurement_only_when_the_row_spans_several(self):
        mixed = entities(entity(RACK_TOP, kpi="max", domain="Climate", name="Rack"), entity(LOUNGE_HUMIDITY, domain="Climate", name="Lounge"),
                         entity(RACK_BOTTOM, domain="Climate", name="Rack Bottom Temperature"))
        self.assertEqual([title for title, _, _ in strip(metadata(mixed))],
                         ["Rack Temperature Max", "Lounge Humidity", "Rack Bottom Temperature"])
        alike = entities(entity(RACK_TOP, domain="Temperature", name="Top"), entity(RACK_BOTTOM, domain="Temperature", name="Bottom"))
        self.assertEqual([title for title, _, _ in strip(metadata(alike))], ["Top", "Bottom"])

    def test_the_kpi_row_holds_six_and_skips_repeated_entities_and_titles(self):
        temperatures = sorted(unique_id for unique_id, relation in generate.HASS_MEASUREMENTS.items() if relation.path == "sensor__temperature")[:8]
        self.assertEqual(len(temperatures), 8, "temperatures: got too few to fill the row")
        with contextlib.redirect_stderr(io.StringIO()):
            kpis = strip(metadata(entities(*[entity(unique_id, kpi="mean") for unique_id in temperatures])))
        self.assertEqual(kpis, [(unique_id.title() + " Mean", 4, ["mean"]) for unique_id in temperatures[:6]])
        with contextlib.redirect_stderr(io.StringIO()):
            kpis = strip(metadata(entities(
                entity(RACK_TOP), entity(RACK_TOP), entity(RACK_BOTTOM, name=RACK_TOP.title()), entity(LOUNGE_HUMIDITY, kpi="median", domain="Humidity"))))
        self.assertEqual(kpis, [(LOUNGE_HUMIDITY.title(), 12, ["lastNotNull"]), (RACK_TOP.title(), 12, ["lastNotNull"])])

    def test_bad_rows_degrade_the_panel_rather_than_fail_the_build(self):
        for rows, titles, unit, interpolation in [
            ([entity(RACK_TOP), entity("never_written_temperature")], ["Rack"], "celsius", "linear"),
            ([entity(RACK_TOP, display="Sparkline")], ["Rack"], "celsius", "linear"),
            ([entity("roof_rain_rate")], ["Rack"], "none", "linear"),
        ]:
            with contextlib.redirect_stderr(io.StringIO()):
                resource = metadata(entities(*rows))
            panels = [element["spec"] for element in resource["spec"]["elements"].values()
                      if element["spec"]["vizConfig"]["group"] == "timeseries"]
            self.assertEqual([panel["title"] for panel in panels], titles, "{}: titles got wrong".format(rows))
            defaults = panels[0]["vizConfig"]["spec"]["fieldConfig"]["defaults"]
            self.assertEqual((defaults["unit"], defaults["custom"]["lineInterpolation"]), (unit, interpolation),
                             "{}: unit or interpolation got wrong".format(rows))

    def test_a_change_of_unit_or_display_type_starts_a_new_panel(self):
        rows = entities(entity(RACK_TOP), entity(RACK_BOTTOM), entity(LOUNGE_HUMIDITY), entity(RACK_TOP + "_copy", display="Bars"))
        rows.loc[3, "unique_id"] = RACK_BOTTOM
        with contextlib.redirect_stderr(io.StringIO()):
            resource = metadata(rows)
        panels = [element["spec"] for element in resource["spec"]["elements"].values() if element["spec"]["vizConfig"]["group"] == "timeseries"]
        self.assertEqual([(panel["title"], panel["vizConfig"]["spec"]["fieldConfig"]["defaults"]["unit"], panel["vizConfig"]["spec"]["fieldConfig"]["defaults"]["custom"].get("drawStyle", "line"))
                          for panel in panels], [("Rack", "celsius", "line"), ("Rack", "percent", "line"), ("Rack", "celsius", "bars")])
        self.assertIn("max(value)", panels[2]["data"]["spec"]["queries"][0]["spec"]["query"]["spec"]["rawSql"])

    def test_labels_come_from_the_friendly_name_or_fall_back_to_the_id(self):
        with contextlib.redirect_stderr(io.StringIO()):
            labels = generate.friendly_names(entities(entity(RACK_TOP, name="Rack Top")), [RACK_TOP, RACK_BOTTOM])
        self.assertEqual(labels, {RACK_TOP: "Rack Top", RACK_BOTTOM: RACK_BOTTOM})

    def test_grafana_group_moves_or_shares_a_row_and_falls_back_to_entity_group(self):
        rows = entities(entity(RACK_TOP), entity(RACK_BOTTOM, group="Weather"), entity(LOUNGE_HUMIDITY, domain="Lounge", group="Weather, Diagnostics"))
        for group, wanted in [("Diagnostics", [RACK_TOP, LOUNGE_HUMIDITY]), ("Weather", [RACK_BOTTOM, LOUNGE_HUMIDITY])]:
            with contextlib.redirect_stderr(io.StringIO()):
                resource = metadata(rows, group.lower())
            sql = " ".join(query["spec"]["query"]["spec"]["rawSql"] for element in resource["spec"]["elements"].values()
                           if element["spec"]["vizConfig"]["group"] == "timeseries" for query in element["spec"]["data"]["spec"]["queries"])
            self.assertEqual([unique_id for unique_id in (RACK_TOP, RACK_BOTTOM, LOUNGE_HUMIDITY) if "'{}'".format(unique_id) in sql], wanted, "{}: entities got wrong".format(group))

    def test_points_draw_dots_and_an_angle_averages_as_a_bearing_on_a_16_point_compass(self):
        for unit, display, wanted in [("°", "Points", ("points", 0, 16, True)), ("°C", "Points", ("points", None, None, False)), ("°", "Lines", ("line", 0, 16, True))]:
            row = entity(RACK_TOP, display=display)
            row[9] = unit
            with contextlib.redirect_stderr(io.StringIO()):
                resource = metadata(entities(row))
            panel = [element["spec"] for element in resource["spec"]["elements"].values() if element["spec"]["title"] == "Rack"][0]
            defaults = panel["vizConfig"]["spec"]["fieldConfig"]["defaults"]
            got = (defaults["custom"].get("drawStyle", "line"), defaults.get("min"), defaults.get("max"), "atan2(" in panel["data"]["spec"]["queries"][0]["spec"]["query"]["spec"]["rawSql"])
            self.assertEqual(got, wanted, "{} {}: got wrong".format(unit, display))
            compass = [(mapping["options"]["from"], mapping["options"]["result"]["text"]) for mapping in defaults.get("mappings", [])]
            wanted_compass = ([(0, "N"), (0.5, "NNE"), (1.5, "NE")], (15.5, "N")) if unit == "°" else None
            self.assertEqual((compass[:3], compass[-1]) if compass else None, wanted_compass, "{} {}: compass got wrong".format(unit, display))

    def test_grafana_index_orders_and_splits_panels_and_accepts_decimals(self):
        rows = entities(entity(RACK_TOP, domain="First"), entity(RACK_BOTTOM, domain="First"), entity(LOUNGE_HUMIDITY, domain="Second"), entity(RACK_TOP + "_x", domain="Third"))
        rows["unique_id"] = [RACK_TOP, RACK_BOTTOM, LOUNGE_HUMIDITY, RACK_BOTTOM]
        rows["index"] = [10, 11, 20, 30]
        rows["grafana_index"] = [None, 40.5, None, "late"]
        with contextlib.redirect_stderr(io.StringIO()):
            resource = metadata(rows)
        items = {item["spec"]["element"]["name"]: item["spec"]["y"] for item in resource["spec"]["layout"]["spec"]["items"]}
        panels = [resource["spec"]["elements"][name]["spec"] for name in sorted(items, key=items.get) if items[name] >= 7]
        self.assertEqual([panel["title"] for panel in panels], ["First", "Second", "Third", "First"])
        self.assertEqual(["'{}'".format(RACK_BOTTOM) in panel["data"]["spec"]["queries"][0]["spec"]["query"]["spec"]["rawSql"] for panel in (panels[0], panels[3])], [False, True])

    def test_a_placed_panel_takes_its_position_from_its_order_among_the_metadata_panels(self):
        rows = entities(entity(RACK_TOP), entity(RACK_BOTTOM, domain="Other"))
        rows["index"] = [10, 20]
        with contextlib.redirect_stderr(io.StringIO()):
            resource = metadata(rows, placed={"First": (5, [[panel(24, 2)]]), "Middle": (15.5, [[panel(24, 3)]])})
        items = {item["spec"]["element"]["name"]: (item["spec"]["y"], item["spec"]["height"]) for item in resource["spec"]["layout"]["spec"]["items"]}
        laid_out = [(resource["spec"]["elements"][name]["spec"]["title"], items[name][1]) for name in sorted(items, key=items.get) if items[name][0] >= 7]
        self.assertEqual(laid_out, [("Panel", 2), ("Rack", 10), ("Panel", 3), ("Other", 10)])

    def test_an_unmeasured_entity_keeps_its_panel_and_draws_no_data(self):
        with contextlib.redirect_stderr(io.StringIO()):
            resource = metadata(entities(entity("never_written_temperature")))
        panels = [element["spec"] for element in resource["spec"]["elements"].values() if element["spec"]["vizConfig"]["group"] == "timeseries"]
        self.assertEqual([panel["title"] for panel in panels], ["Rack"])
        sql = panels[0]["data"]["spec"]["queries"][0]["spec"]["query"]["spec"]["rawSql"]
        self.assertIn("FROM sensor\n", sql)
        self.assertIn("entity_id IN ('never_written_temperature')", sql)

    def test_an_unmeasured_entity_in_an_unknown_namespace_is_left_off(self):
        stray = entity("never_written_temperature")
        stray[3] = "nowhere"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(metadata(entities(stray)))


def declared(uid):
    generate.DASHBOARDS.clear()
    return mock.patch.dict(generate.TITLES, {uid: uid.title()})


def metadata(rows, uid="diagnostics", placed=None):
    with declared(uid):
        return generate.metadata_dashboard(uid, 3600, rows, placed=placed)


def entities(*rows):
    return pd.DataFrame([dict(zip(COLUMNS, row, strict=True)) for row in rows], columns=COLUMNS)


def entity(unique_id, display="Lines", device="Device", kpi=None, domain="Rack", name=None, group=None):
    return [1, "Enabled", device, "sensor", unique_id, name or unique_id.title(), domain, "Diagnostics", display, None, kpi, group]


def strip(resource):
    kpis = []
    for item in resource["spec"]["layout"]["spec"]["items"]:
        if item["spec"]["y"] == 3:
            element = resource["spec"]["elements"][item["spec"]["element"]["name"]]["spec"]
            kpis.append((element["title"], item["spec"]["width"],
                         element["vizConfig"]["spec"]["options"]["reduceOptions"]["calcs"]))
    return kpis


def panel(width, height):
    query = generate.Series(influxdb3, generate.INFLUXDB3, "SELECT 1", "", "", "", "table")
    return generate.Panel("Panel", query, width, height, stats.VisualizationV2())


def laid(resource):
    return [(item["spec"]["x"], item["spec"]["y"], item["spec"]["width"], item["spec"]["height"])
            for item in resource["spec"]["layout"]["spec"]["items"]]


def declared_levels(relation, measure):
    return next(declared.levels for declared in relation.relation.measures if declared.key == measure)


if __name__ == "__main__":
    unittest.main()
