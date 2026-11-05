# pm25

The plan for the `homeassistant_airquality_pm25` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `homeassistant` |
| **Model** | `airquality` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/homeassistant/airquality/pm25/notebook.ipynb` |
| **Registered Model** | `homeassistant_airquality_pm25` (`model.md` 6.1) |
| **Project Flavour** | `wasm` (`model.md` 3.2), a saturating curve like `example/wasm/saturate` |
| **Consumers** | Served by `mlserver`, embedded in Python, Rust or Go if a consumer appears |

**Status, 2026-11-05.** A placeholder beside `hotwater/temp`. The notebook, the directories and this plan are scaffolded; nothing is fitted or built.

## Intent

Make the PM2.5 readings of the four air purifiers comparable, and trustworthy, by correcting the part of each reading that follows the room temperature and then levels off. A reading in one room should mean the same airborne particles as the same number in another, so the Air Quality panel and any automation that acts on the number (switching a purifier up, warning about a high room) stop reacting to temperature.

## What the data shows

Checked 2026-11-05 against InfluxDB, table `sensor__pm25`, hourly means since the template entities began on 2026-10-09, against the matching room temperature:

| Room | Entity | Room temperature | Hours | Correlation with temperature | Mean PM2.5 by temperature, coldest to warmest fifth |
|---|---|---|---|---|---|
| Dining | `template_dining_air_purifier_pm25` | `office_dining_temperature`, 13 to 25 °C | 348 | 0.66 | 13, 9, 16, 22, 32 |
| Lounge | `template_lounge_air_purifier_pm25` | `office_lounge_temperature`, 13 to 24 °C | 235 | 0.63 | 7, 12, 16, 18, 25 |
| Kitchen | `template_kitchen_air_purifier_pm25` | `kitchen_temperature`, 13 to 26 °C | 259 | 0.27 | 5, 4, 5, 6, 7 |
| Parents | `template_parents_air_purifier_pm25` | `parents_temperature`, 14 to 26 °C | 137 | -0.16 | 4, 4, 4, 4, 3 |

So the reading rises with temperature in the dining room and the lounge, weakly in the kitchen, and not at all in the parents' room. **That is a correlation and not yet a finding**: cooking, heating, occupancy and the time of day all move temperature and particles together, and the data cannot separate them until they are controlled for. No levelling off is visible below 25 °C in the dining room, so the plateau is a hypothesis, to be tested against the warmer months now starting.

## Signals

| Signal | Entity | Notes |
|---|---|---|
| Reading | `template_<room>_air_purifier_pm25` for dining, lounge, kitchen, parents | Whole numbers, 0 to 116 since 2026-10-09 |
| Earlier reading | `dining_air_purifier_pm25`, `lounge_air_purifier_pm25`, `parents_air_purifier_pm25` | Ended 2026-10-02 to 2026-10-06. The template entities replaced them when the ids were pinned, so a longer history needs both, joined at 2026-10-09. The old ones use -1 for no reading, which is not a particle count |
| Room temperature | `office_dining_temperature`, `office_lounge_temperature`, `kitchen_temperature`, `parents_temperature` | The `compensation_sensor_*` variants exist for the same rooms and are to be compared |
| Room humidity | `office_dining_humidity`, `office_lounge_humidity`, `kitchen_humidity`, `parents_humidity` | Optical particle counters over-read in humid air, so humidity is a likely second driver |
| Fan speed | `<room>_air_purifier_fan_speed` | The reading depends on air moving through the sensor, so compare only at the same speed |
| Purifier state | `<room>_air_purifier` | Excludes readings while off |
| Outdoor | `bom_darlington_humidity` and the roof sensors | Outdoor temperature and humidity, to tell indoor sources from the weather |

## Planned signature

Inputs are the raw PM2.5 reading, the room temperature and, once shown to matter, the room humidity and the fan speed. Output is the corrected PM2.5, `homeassistant_airquality_pm25_ugm3`. No state is carried. A `wasm` module imports `tanh` and `exp` from the host (`model.md` 4.1) and carries the per-room fitted values as constants.

## Approach

1. **Clean.** Drop -1 and readings while the purifier is off, join the old and new entities at 2026-10-09, align to a common 5 minute grid, and keep the fan speed.
2. **Look before fitting.** For each room plot the reading against temperature in bins, at fixed fan speed and with the time of day held (compare 03:00 to 05:00 only, when nobody is cooking or moving), and again by humidity. If the relation survives the quiet hours it is the sensor and not the room.
3. **Choose the form.** A gain that rises with temperature and saturates, `reading = true * (1 + a * tanh((temperature - t0) / w))`, which inverts to the correction. Fit with `scipy.optimize.least_squares` and a robust loss, as `weewx/console/battery` does for its curve, then compare with a straight line so the saturating form has to earn its extra parameters.
4. **Find a reference.** Calibration needs something true to calibrate against. Options, in order of cost: the four purifiers against one another in the same room for a week (relative calibration, free, and it says which sensor drifts); one calibrated laser PM2.5 monitor moved between rooms (an absolute reference, a purchase); the nearest public air quality station for outdoor particles with a window open.
5. **Evaluate.** Split by time and not by random hour (`model.md` 6.3). Accept when the corrected readings of co-located purifiers agree within a stated limit, and report the residual by temperature, so a remaining slope is visible.
6. **Ship** only the rooms whose relation is real. A room with no temperature dependence, as the parents' room appears to be, gets a gain of one and is documented as such.

## Open decisions

- **Reference.** Relative agreement between purifiers, a purchased reference monitor or a public station. Without one the model can only make the rooms agree, not make them right.
- **Per room or shared.** The same sensor model in four rooms may share one curve, or the gain may differ by unit. The data above suggests it differs.
- **Humidity.** Whether humidity explains more than temperature, since the two move together indoors.
- **Flavour.** `wasm` suits a fixed curve with a plateau. A fan speed or humidity term that interacts with temperature may need `pyfunc`.
- **Where it runs.** Whether the corrected value replaces the template entity in Home Assistant or is published beside it. The template entities are pinned by id from `entity_metadata.xlsx` (the entity rows, not code), so a new corrected entity is a row there.

## Data to get

| Data | Why | Where from |
|---|---|---|
| A week of the four purifiers side by side in one room | Relative calibration with the room held constant | The purifiers, moved |
| A reference PM2.5 reading | An absolute scale | A calibrated monitor, or a public station for outdoors |
| Warm months of readings | Whether it levels off at high temperature | InfluxDB, as summer arrives |
| Purifier fan speed history | Compare like with like | `<room>_air_purifier_fan_speed` |
| Cooking and occupancy markers | To separate the room from the sensor | Kitchen power plug, presence sensors |

## To do

1. Pull the dining and lounge readings, temperature, humidity and fan speed into the `training`, `validation` and `backtest` splits, by time.
2. Do steps 1 and 2 of the approach and write down what the quiet-hours plot shows before choosing a form.
3. Decide the reference, then fit, build the module and write the golden samples for cold, mid and hot rooms and a missing input.
