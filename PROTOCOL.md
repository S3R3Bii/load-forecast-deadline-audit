# Fixed source and analysis plan

## Decision and scope

How does substituting later load-forecast documents change the error reported for a fixed prior-day scheduling cutoff? Demonstrate a deadline guard using real published documents, with authored failure cases that distinguish archive ordering from decision-time eligibility.

Original historical context: EIA-930/NOAA residual modeling with season and authority holdouts has not run because original field vintages were unverified. This independent execution uses ERCOT's public NP3-561-CD forecast documents and NP6-345-CD actual-load reports. It is a five-day descriptive audit, with no fitted model, tuning, calibrated interval or confirmatory generalization claim.

## Fixed cohort, cutoffs and selection

Operating days: every hour of 25, 26, 27, 28 and 29 October 2026. Series: Coast, East, FarWest, North, NorthCentral, SouthCentral, Southern, West and SystemTotal. SystemTotal is its own reported field; never sum it together with zones or assume it equals their sum exactly. Native date/hour and DSTFlag are retained. All cohort hours are Central daylight time, UTC−05:00; reject any unexpected date, hour, missing field, duplicate, nonfinite/negative load, or DSTFlag other than N. General repeated-hour handling is outside this pilot and must fail closed.

For each operating day D, select the latest report with offset-aware PublishDate at or before each fixed cutoff: D−1 at12:00 (day_ahead), D at12:00 (same_day_noon), D at23:59:59 (end_of_day). Require age no more than90 minutes and a unique CSV/XML pair with the same declared PublishDate. In a tie between distinct publications, fail rather than choose by outcome. Selection uses metadata only. The two same-day selectors violate the prior-day deadline by design and are diagnostic comparators, never eligible scheduling inputs. Mark every observation whose document was published after its target interval began or ended.

Use the captured forecast listing from31 October2026 00:40:39UTC, whose first/last publication stamps were inspected. For actuals select the earliest available unique CSV/XML pair published on D+1, and require all24 target-day hours and all nine fields. Actuals are retrospective reference labels only; no claim that they are settlement-final, revision-free or available before scheduling. Do not fill gaps, shift cutoffs, drop days/zones or pick a revised target based on scores. Any source gate failure leaves this execution incomplete.

## Complete analysis, no search

Export all5×24×9×3=3,240 comparison rows with publication provenance, signed forecast-minus-actual error inMW, absolute/squared error, cutoff age and interval timing. Report MAE(MW), MSE(MW²), RMSE(MW), mean error(MW), WAPE(absolute errors divided by sum positive actuals), maximum absolute error and maximum positive actual-minus-forecast deviation, by each of27 series/policy combinations and each of135 day/series/policy combinations. All planned cases remain visible. No zone-volume aggregation beyond the published system series; no arbitrary positive-load threshold.

For each of15 day/policy combinations on SystemTotal and all135 day/series/policy combinations, report the forecast peak, actual peak, signed peak-size error, peak-hour sets including ties, and whether the actual-peak hour is included in the forecast maximum. No reserve requirement or financial impact is inferred from load error. Report per-day changes in system MAE and the signed comparison against day_ahead for both late policies; do not select the better policy.

Use exact Decimal sums/products of source numeric tokens. MAE/WAPE division and square root use60-digit arithmetic; an independent80-digit checker uses Fraction sufficient sums and math/Decimal independently with absolute1e−45 tolerance for displayed derived values. Native values, selectors, counts, identities, timing flags and sufficient sums must agree exactly. No random seed, learned coefficient, hyperparameter selection, statistical significance, confidence interval or untouched-test claim applies. Five adjacent days and related zones are dependent and cannot support seasonal or multi-authority inference.

## Independent checks and practical exercise

Reconcile every selected native CSV field against the paired XML using a separate parser, and reconstruct target-day joins and selectors with SQLite independently of production helpers. Retain all document IDs, declared publication times, download URLs, archive/payload hashes, source listing and fixed input hashes. Source capture and independent reconciliation must pass and be committed before error summaries run. Freeze code/source dependencies before the first descriptive score command; source data already exist, so this is a workflow order check rather than analyst blindness.

Implement a CLI that accepts an aware deadline and candidate documents and either selects the newest eligible document or returns unavailable with a reason. Never fall back to an after-deadline document. Authored tests cover late-only inputs, exact deadline equality, duplicate publication ties, missing/stale reports, naive timestamps, numeric/schema defects, source date/hour identities, timezone/DST rejection and peak ties. The exercise uses an actual cohort day plus authored cases; it is local software evidence, not operational validation.

## Acceptance and presentation

Required gates: source/rights and full support; independent native/numeric/timing reconciliation; all fixed cases; deterministic offline replay in CPython3.10 and3.12; privacy; natural executive-accessible README; source-bound figures and rendered manuscript; exact candidate/main Linux CI, same tested tree, annotated tag and verified portfolio metadata. Each gate is pass/fail/unknown. Grade4 means these scoped criteria pass, not that forecasting or real scheduling improved. Limit source/numerical/presentation review to three substantive rounds,45 active minutes and60 review-specific calls including earlier related checks. Preserve failures and stop on a persistent substantive defect after one targeted retry. The EIA original-vintage limitation and broader unrun proposal stay explicit.
