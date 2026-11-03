# weewx / forecast / roof

The plan for the `weewx_forecast_roof` model. It follows `spec.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `weewx` |
| **Model** | `forecast` |
| **Notebook** | `src/may/mlflow/src/main/model/weewx/forecast/roof/notebook.ipynb` |
| **Registered Model** | `weewx_forecast_roof` (`spec.md` 6.1) |
| **Project Flavor** | `onnx` (`spec.md` 3.2) |
| **Worked Example** | The learned model flow, replacing `example/onnx` as the example (`plans/mlflow.md` 4.1) |

**Status, 2026-10-31.** A placeholder. The notebook, the directories and this plan are scaffolded; nothing is fitted or built.

## Intent

Predict what the roof sensor will actually read from the Bureau of Meteorology forecast, by adjusting the forecast up or down. The adjustment
comes from the recent roof readings measured against the forecasts that were made for them, which captures the sensor's calibration, and from
local conditions such as solar radiation and wind, which capture how the roof differs from the Bureau's station. It replaces the earlier
`roof_vs_bom` candidate, which only corrected the Bureau's current reading.

## Signals

| Signal | Entity | Checked 2026-10-31 |
|---|---|---|
| Actual | `roof_temperature` | 19,690 readings, 6.4 to 30.8 °C |
| Forecast, daily maximum | `bom_darlington_temp_max_0` to `_7` | 22,488 readings each (10,171 for `_7`), 15 to 31 °C |
| Forecast, daily minimum | `bom_darlington_temp_min_0` to `_7` | 22,488 readings each, 3 to 20 °C |
| Forecast, later today | `bom_darlington_temp_later` | 22,488 readings, 5 to 31 °C |
| Bureau now | `bom_darlington_temp_now` and `bom_darlington_temp` | 22,488 and 22,644 readings |
| Solar radiation | `roof_max_solar_radiation` | 12,281 readings, 0 to 1,050 |
| Wind | `bom_darlington_wind_speed_kilometre` | 22,642 readings, 0 to 52 km/h |

## Planned model

A learned adjustment that takes the Bureau's forecast for a horizon, the recent error between the roof and the forecasts made for it, the solar
radiation and the wind, and returns the predicted roof temperature and the adjustment applied. The recent error is carried as state, an
exponentially weighted bias per horizon, so the model adapts as the sensor drifts. Outputs follow section 6.1: names start with `weewx_forecast_roof_`
and degrees end `_celsius`.

## Cautions

- **Little data.** There are about 79 days, so about 79 realised days per horizon, and the later horizons have fewer forecasts that have come
  true. Splits must be by run, whole days, and never random readings.
- **One site and one season.** From late winter to early summer only, so nothing is learned about autumn or winter.
- **Different stations.** The Bureau's station is not on the roof, so some of the adjustment is real site difference and not sensor error.
- **Module.** The owning module of the `roof_*` and `bom_*` entities is assumed to be `weewx` and is to be confirmed.

## To do

1. Build the dataset of realised roof readings paired with the forecast issued for them, under `training`, `validation` and `backtest`.
2. Fit with scikit-learn, convert with `skl2onnx` and replay the backtest through `onnxruntime`.
3. Write the golden samples, including a missing required input.
