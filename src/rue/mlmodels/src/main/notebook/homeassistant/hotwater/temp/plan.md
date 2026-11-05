# homeassistant / hotwater / temp

The plan for the `homeassistant_hotwater_temp` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `homeassistant` |
| **Model** | `hotwater` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/homeassistant/hotwater/temp/notebook.ipynb` |
| **Registered Model** | `homeassistant_hotwater_temp` (`model.md` 6.1) |
| **Project Flavour** | `wasm` (`model.md` 3.2) |
| **Worked Example** | The stateful model flow, replacing `rackmains/ups/battery` as the example (`plans/mlmodels.md` 4.1) |

**Status, 2026-10-31.** A placeholder. The notebook, the directories and this plan are scaffolded; nothing is fitted or built, and the `wasm`
flavour does not exist yet (`plans/mlmodels.md` 3).

## Intent

Report the hot water temperature at the pipe leaving the water heater, but only while hot water is flowing. When no hot water has flowed for a
while the pipe cools toward ambient and its reading is not the water temperature, so the model says it has cooled and reports no water
temperature. When flow starts it reports the temperature again. It MUST NOT mistake the tank being heated, by the booster or by solar, for flow.

## States

| State | Meaning | Water Temperature Reported |
|---|---|---|
| Cooled | No hot water has flowed for a while and the pipe is cooling toward ambient | No |
| Flowing | Hot water is flowing and the reading follows the water | Yes |
| Heated, No Flow | The tank is heated by the booster or by solar and the pipe warms by conduction | No |

## Signals

| Signal | Entity | Checked 2026-10-31 |
|---|---|---|
| Pipe temperature | `compensation_sensor_landing_festoons_plug_temperature` | 137,618 readings, median 20 s apart and at most 7 h, 17.2 to 66.5 °C |
| Solar radiation | `roof_max_solar_radiation` | 12,281 readings, 0 to 1,050. A proxy only; there is no tank or pump sensor |
| Booster commands | `water_heating_turn_on_water_heater_booster` and `_turn_off_` automations | Turn-on rows at 04:00 and 05:00 local (36 each) and 15:00 (42) |
| Booster plug power | `template_ceiling_water_booster_plug_proxy_power` | 35 readings, all 1.5 W, so it cannot be used |

## What the data shows

On 2026-10-26 the pipe sat at 20.5 °C overnight and then rose steadily from 03:30 to about 45 °C by 05:25, about 0.2 °C per minute and 25 °C
in two hours. That has the shape of the tank being heated and not of flow, though there is no flow meter to confirm it. The pipe rose again at
12:10 and from 14:50 on the same day. Rates between consecutive readings are mostly slow: about 86,000 of 137,600 are within 0.5 °C per
minute and 250 rise faster than 2 °C per minute, while 20,900 fall faster than 0.5 °C per minute, which a flow split has to explain.

## Planned signature

Inputs are the pipe temperature, the clock, the solar radiation, the booster's last on or off command and an ambient temperature. State holds a
smoothed temperature, a rate of change, the time since the last flow-like event and the last flowing temperature. Outputs are a state code, a
flow flag, a cooled flag and the water temperature while flowing. Output names start with `homeassistant_hotwater_`, and the unit suffix for
degrees is `_celsius`.

## Open decisions

- **Flow split.** There is no flow meter, so a split has to be constructed, for example from rises that exceed what the booster or solar can
  explain, and checked by hand on a few days.
- **Booster state.** Whether the automations' commands are reliable enough to stand for the booster being on.
- **Ambient.** Which sensor stands for ambient at the pipe.
- **Module.** `homeassistant` is assumed because the water-heating automations are there, and is to be confirmed.

## To do

1. Choose and write the flow split, and pull the data into the `training`, `validation` and `backtest` splits.
2. Fit the cooling decay and the flow and heating rate thresholds as a `wasm` model once a builder exists.
3. Write the golden samples for cooled, flowing, heated with no flow, and a missing input.
