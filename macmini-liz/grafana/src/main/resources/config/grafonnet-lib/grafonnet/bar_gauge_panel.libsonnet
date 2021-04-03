{
  /**
   * Create a [bar gauge panel](https://grafana.com/docs/grafana/latest/panels/visualizations/bar-gauge-panel/),
   *
   * @name barGaugePanel.new
   *
   * @param title Panel title.
   * @param description (optional) Panel description.
   * @param datasource (optional) Panel datasource.
   * @param unit (optional) The unit of the data.
   * @param orientation (optional) The orientation of the guage.
   * @param display_mode (optional) The display mode of the guage.
   * @param thresholds (optional) An array of threashold values.
   *
   * @method addTarget(target) Adds a target object.
   * @method addTargets(targets) Adds an array of targets.
   */
  new(
    title,
    description=null,
    datasource=null,
    unit=null,
    min=null,
    max=null,
    orientation='horizontal',
    display_mode='basic',
    thresholds=[],
  ):: {
    type: 'bargauge',
    title: title,
    [if description != null then 'description']: description,
    datasource: datasource,
    targets: [
    ],
    fieldConfig: {
      defaults: {
        unit: unit,
        [if min != null then 'min']: min,
        [if max != null then 'max']: max,
        thresholds: {
          mode: 'absolute',
          steps: thresholds,
        },
      },
    },
    options: {
      orientation: orientation,
      displayMode: display_mode
    },
    _nextTarget:: 0,
    addTarget(target):: self {
      // automatically ref id in added targets.
      local nextTarget = super._nextTarget,
      _nextTarget: nextTarget + 1,
      targets+: [target { refId: std.char(std.codepoint('A') + nextTarget) }],
    },
    addTargets(targets):: std.foldl(function(p, t) p.addTarget(t), targets, self),
  },
}
