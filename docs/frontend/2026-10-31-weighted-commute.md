# Weighted commute reference — 31 October 2026

The user asked to give public transport and driving greater influence than cycling/walking, particularly for longer active journeys. The catalogue now uses a display-only weighted reference rather than an equal average.

Base product weights are public transport 50%, driving 30%, cycling 15% and walking 5%. These are product defaults, not measured modal-use rates. Cycling over 30 minutes receives half its default weight and over 60 minutes a quarter. Walking over 15 minutes receives half; walking over 30 minutes remains excluded unless explicitly selected, in which case it receives a quarter. Adjustment uses the upper bound when a reference is a range. Missing modes are excluded; remaining weights normalise to 100%. A sole remaining mode retains its own duration even if its raw weight was reduced.

Weighted time is sum(duration times adjusted weight) divided by total adjusted weight. Ranges retain weighted lower/upper bounds rounded outward; exact references round to the nearest minute. Public transport counts once, retaining the selected valid route and its constraints. No backend filter, saved profile, journey duration or source record is modified.

The catalogue remains compact; hovering its time shows actual shares. Property details add a collapsed Commute weighting disclosure with defaults, actual shares and duration rules. The normal compact mode grid remains intact.

Validation: two new weighting regressions failed before implementation and passed afterwards; 66 frontend unit tests, five focused desktop/mobile/filter browser scenarios, seven product-guide tests and the production build passed. Public help and its canonical manifest were updated. Only public product-help index rows were refreshed after a SQLite backup, preserving other sources and vectors. The local frontend hot reloads the change without a backend restart.

User follow-up: removed the Commute weighting disclosure and catalogue weight tooltip from the product UI. Public help no longer exposes the implementation weights. The calculation and mode-specific filtering remain intact.
