# Signature version plan

Status: complete. The library, `mlserver`, the spec, the migration, the 1001 trial and the cleanup of 7.1 are done and released or ready to release with the next `mlmodels` release. Delete this plan when that release has shipped. Owner of the outcome is `model.md` (sections named below); this plan is removed when the work lands.

## 1. Problem

A breaking signature change to a `served` model is today a new notebook, so a new workspace, new data and a new model name (10.2). That is the only way an old client keeps working while a new one moves, and it is heavy. An `embedded` target is exempt because it is released in lockstep with its one consumer.

## 2. Decision

A served model carries an integer **signature version**, starting at 1000 like runs and models, never reused, gaps allowed. It is part of the served name. A breaking change bumps it in place. The newest live version and the one before it (N and N-1) are served, and anything older is retired. Clients pin the version they support and move on their own release.

Considered and rejected: an unversioned "latest" name (it breaks a caller the moment the signature moves), retention inside `mlserver` (it can retire N-2 while N failed to load, against R7), registry tags for family and version (the name carries both), and the suffix inside the project, signature and golden names (no replay compares `model_name`, so it buys nothing and touches every loader and embed).

## 3. Rules

1. **Field.** `signature.json` holds `"signature_version"` as its second key, after `schema`. MD006: every target MUST carry an integer of 1000 or more (not a boolean). Only a served target's version is acted on, so an `embedded` or `local` project carries it unchanged.
2. **Baseline.** `metadata.json` gains an optional last field, `baseline`, the signature document of the last release of a served target. `fab release` writes it with `release`, packaging never clears it, and the next release replaces it. It is absent for a target that was never released and for `embedded` and `local` targets, so the layout schema stays 2 and no other `metadata.json` changes. Where `release` is set and `baseline` is absent, as in the one served workspace today, packaging seeds `baseline` from `release.signature`, so existing files need no migration. `release` keeps its meaning (null until released), and a content change still nulls it. Today `record_project` writes `release` as null on any content change, so an additive edit followed by a breaking edit passes at the same version, because the second edit has no baseline.
3. **Compatibility**, against `baseline`, whose version and the new one must both be present. It is one gate, in `record_project` at package time, and `fab release` does not repeat it, because it writes `baseline` from a project that already passed:
   - lower than the baseline: `GateError` Package, signature, "went down";
   - equal: today's additive-only check (`signature_findings`), with its message ending "bump signature_version";
   - higher: no check.
4. **Served name.** `served_name(name, signature)` is `<name>_<signature_version>`, read from the signature document, with 1000 when it has none. It is one pure function in `_signature.py` beside `registered_name`. The registry model, the served name and the pin in a client are this value, and `<served_name>_preview` is its preview. The project, signature, golden, manifest and loaders keep the plain name.
5. **Naming.** A notebook name MUST NOT be all digits or end in `_<digits>`, which keeps `<stem>_<digits>` unambiguous as a version, so `c_1000` cannot collide with any future version of `c`. WS015, added to 6.1. This one rule is enough: a lint that checked names for uniqueness across workspaces would only see the versions that exist today.
6. **Retirement.** `publish` of a workspace, once its served name is `READY` in the production index, ranks the registered models matching `^<stem>_\d+$` that hold a `release` alias, keeps the top two and the version just published, and removes `release` from the rest. It skips, with a warning, any version a repository source still pins (rule 7). It does nothing when `mlserver` is unreachable. Registry versions are never deleted, and `mlserver` unloads a model with no alias by the loop it already runs, within one poll (30 seconds) and with no restart.
7. **Pins.** A scan of the repository sources finds `/v2/models/<stem>[_<digits>][_preview]/` in code and configuration (not in `target/`, `.go/`, notebooks, plans or `mlmodels` tests). It feeds retirement (rule 6) and `status`, and is not a lint. It reads the working tree and not what is deployed, so the N-1 grace period is the real protection and the scan only catches a client left behind in the tree.
8. **Status.** `model.sh status` warns when more than two versions of a family are live, when the registry holds a version newer than git, when a pin is not live, and when a pin is the older of the two live versions ("move before the next bump").

## 4. Tags

No new tags. The installed MLflow (3.18.0) limits a model-registry tag value to 100000 characters, so the compact `metadata` tag is safe and stays as 10.3 specifies. The work is constants only: `PROJECT_TAG_SNAPSHOT_VERSION`, `PROJECT_TAG_INPUTS_SHA256`, `PROJECT_TAG_RELEASED_AT` and `PROJECT_TAG_METADATA` replace the literals in `_release.py` and `_registry.py` and in the tests. `REGISTRY_VOCABULARY` is unchanged, since `mlserver` reads only `content_sha256`, `project_flavour` and `release_version`.

## 5. Changes

### 5.1 Specification (`model.md`)

- 1.1 terms: **Signature version**, **Served name**.
- R10: a breaking change of a served model bumps the signature version and so the served name.
- 3.1 signature row and the Workspace signature paragraph: the field and who may carry it.
- 6.1: the trailing-digits naming rule and a Served Name row in the table.
- 7.1 stage 7 gate and 7.2: replace "new model name, served side by side" with N and N-1.
- 9.1: MD006 and WS015. 9.2: the coverage row for R10.
- 10.2: add the optional `baseline` field of `metadata.json`, replace the two breaking-change bullets and keep the embedded exception.
- 10.3: registered name is the served name, retirement owned by the release function, tag constants.
- 10.4: unchanged in behaviour, add that N-1 is a live alias and not a rule of the loop.
- 10.5: preview name, and the trial of section 7 as the first use.
- 10.6: the retirement step, the `status` warnings and the signature gate. The `fab generate` signature check that 10.6 describes does not exist in code, where the only check is in `record_project`, so the text is corrected to the one Package gate.
- 10.7: a served client MUST pin a signature version and MUST be released to move.
- Module `CLAUDE.md`: one sentence in Shape on the served name. No test names.

### 5.2 `mlmodels`

- `_constants.py`: tag constants, `SIGNATURE_VERSION_FIRST = 1000`, the family pattern.
- `_signature.py`: `served_name`, `build_signature(..., signature_version=None)`.
- `_scaffold.py`: every new notebook gets `signature_version` 1000, `--local` included.
- `_lint_workspace.py`: WS015.
- `_metadata.py`: `baseline` in `METADATA_ORDER`, its type under MD002, MD006 in `lint_metadata`, `record_project` seeding and keeping it and checking `signature_findings` against it per rules 2 and 3.
- `workflow/register.py`, `workflow/pull.py`, `_registry.py`: pass `served_name` for the registered model and keep the MLflow experiment on the plain name, so the runs of a notebook stay in one experiment across versions.
- `testing.py`: a served project it builds defaults to `signature_version` 1000.
- `_release.py`: `release_workspaces` writes `baseline` with `release`. `publish`, `wait_served`, `status_lines` and `_registry_state` use `served_name`. Add retirement, the pin scan and the new warnings. `workspaces()` keeps the plain name as its key.
- Locate where `fab systest` builds `<name>_preview` for the served reference consumer. `model.sh systest` only runs the notebooks with `--register`, so the served target test is in `_runner.py`, not yet read, and the name passed there becomes the served name. This is the first task, because the loaders stay unchanged only if the call takes the name as an argument.
- No loader, embed or reference-consumer change. The served `main` already takes the server and the name as arguments.

### 5.3 `mlserver`

- `registry/sync.py`: replace the per-model `search_model_versions` calls with one paged fetch grouped by name, and page `search_registered_models`, whose default of 100 would otherwise leave the 101st model unserved (confirmed in the installed client).
- `sync()`: delete a model's directory only when the `unload` call succeeded or the server was unreachable, and keep it, retrying on the next poll, when the server refused. Today the result is ignored, so a refused unload leaves the model in memory with no files.
- Check that the installed client accepts `search_model_versions` with an empty filter, and otherwise page per name.
- No vocabulary or retention change.

### 5.4 Clients

- `meg/homeassistant/.../custom_packages/weather.yaml`: the URL pins `_1000` at migration and `_1001` after the trial. It is the only repository client.

### 5.5 Lint and gates

Rule codes reuse the existing families, and nothing here adds one.

| Check | Kind | Where |
|---|---|---|
| MD006, `signature_version` valid for every target, and `baseline` only on a served target | lint | `lint_metadata` |
| MD002, `baseline` is an object when present | lint | the existing field-type check |
| WS015, notebook name not all digits and not ending in `_<digits>` | lint | `_lint_workspace.py` |
| Version and additive check against `baseline` | `GateError` Package, signature | `record_project`, once |
| Name uniqueness, pins, retirement, `status` warnings | not lints | none |

## 6. Tests

Each new rule gets a test that fails when the rule is removed.

- Lint: MD006 for each target kind, for a value below 1000, a non-integer and a boolean, and for `baseline` on a non-served target. WS015 for `1000`, `c_1000` and `pm_25`, and not for `co2`.
- Baseline: an additive edit followed by a breaking edit at the same version fails the gate, a released workspace with no `baseline` is seeded from `release`, a signature with no version is a finding, and `fab release` and a later content change keep `baseline`.
- Package gate: lower, equal-additive, equal-breaking, higher.
- `served_name` and its callers through `register_preview`, `publish`, `wait_served` and `status_lines`.
- Retirement against the sqlite registry the existing tests use: 1000 and 1001 retire nothing, 1002 retires 1000, a preview-only version counts for nothing, a failed or unreachable `mlserver` retires nothing, a pinned version is skipped, a re-run converges, the legacy unsuffixed model ranks lowest, and publishing the third-newest version keeps it.
- Pin scan over a temporary tree, including the legacy and preview forms.
- `sync.py`: more than 100 registered models are all served, one version fetch serves any number of models, and a refused unload keeps the directory for the next poll.

Scope runs to the files touched (`-k`), and run the full suite once before release.

## 7. Trial on `homeassistant/weatherstation/battery`

The control is `rackmains/ups/battery`, embedded, which changes nothing.

1. **Baseline.** `model.sh status` is clean.
2. **Migrate.** Add `signature_version` 1000, rerun the notebook (the project hash changes once), `fab systest`, `fab release`. The registry gains `homeassistant_weatherstation_battery_1000` and the legacy model stays live as N-1. Change the HA URL to `_1000` and release HA.
3. **Second version, a test only.** The model does not change and is not made stateful. Bump `signature_version` to 1001 and reword the description of one input in `signature.json`. Rewording is a change to a released entry, so today's check calls it breaking, which proves the check is skipped at a higher version. The bump is not required by any real change and exists to exercise the scheme. Run `fab unittest` and `fab systest`, where `_1001_preview` serves beside `_1000`, then `fab release`. Expect `_1000` and `_1001` `READY`, the legacy model unloaded by retirement, `status` clean except the pin warning on `_1000`. Version 1001 is then permanent, since a version is never reused, and 1000 retires when 1002 ships.
4. **Move the client.** HA pins `_1001`, is released, and the warning clears.
5. **Not done live.** A third version is covered by the retirement tests and is not released for the trial.
6. **Clean up.** Section 7.1, after the legacy model is retired.

### 7.1 Cleanup after the trial

Done once the legacy unsuffixed model had lost its `release` alias (the trial retired it) and no client called it.

1. Done. `live_signatures` and `served_pins` (`_release.py`) match `<stem>_<digits>` only, so the unsuffixed model no longer ranks as version 0 and is no longer a pin.
2. Done. `signature_findings` reports a signature with no `signature_version`, released or new, and `served_name` raises for one. `mlmodels.testing.build_project` passes version 1000 by default, and the registration test builds its signature with one.
3. Not done, and the plan was wrong. Seeding `baseline` from `release.signature` in `record_project` is not migration code. A project released as `embedded` carries no `baseline`, so when it becomes `served` the seed is what keeps the compatibility check, which `test_an_embedded_project_may_change_its_released_signature_in_place_and_a_served_one_may_not` covers. It stays, with its test and the spec sentence.
4. Done. The legacy cases of the retirement and ranking tests now use numbered versions only, a test of the pin family covers look-alike names, and the spec no longer says a missing version reads as 1000 or that the unsuffixed model ranks as version 0.
5. Checked. The repository no longer names the unsuffixed model, the unit tests of `mlmodels` and `mlserver` pass, and each removed rule's test fails without it.

## 8. Order and acceptance

0. Read `_runner.py` and settle where the served preview name is built, and check the empty-filter call of `search_model_versions`.
1. Spec edits (5.1), reviewed before code.
2. The `baseline` field, its seed and release write and the Package gate, with the additive-then-breaking test, ahead of everything else because the version rules depend on it.
3. Tag constants, then the signature field, scaffold, MD006, WS015 and the version gate, with their tests.
4. `served_name` and its callers, then retirement, pin scan and `status`.
5. `mlserver` paging, the refused-unload fix and their tests.
6. Format and lint everything touched, `shellcheck` if a script changed, scoped tests, then the trial of section 7. Releases are run by the user, so the trial is a chained script in `/tmp` with a status file for the assistant to monitor.

Done when the trial ends as described, `status` is clean, the retirement tests pass and fail without their rules, and a regenerated embed of every consumer is byte-identical.

## 9. Risks

- The first release changes the content hash of the one served model, which is expected.
- N-1 is frozen: git holds only the newest project, a refit reaches N only, and the older model is recoverable from its release tag and the registry.
- Pin detection finds clients in this repository only, and reads the tree and not what is deployed.
- `baseline` and `release` hold the same document after a release, and differ after a content change. `metadata.json` is written only by tooling, so a hand edit of `baseline` is not guarded.
- Retirement waits for a confirmed `READY`, so an unreachable `mlserver` leaves three versions live until the next publish.
