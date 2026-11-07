# Screenshots

Captured from the running application against the deterministic seed
(`make reset`), so every number visible is real data this repository can
reproduce.

| file | what it shows |
|---|---|
| `overview-dark.jpg` | The shell: a floating navigation island and a pill header over a living background field, with the KPI row below. |
| `stock-alerts.jpg` | Standing low-stock alerts raised by `trg_stocklevels_au_alert`, in light mode. The two counts differ on purpose — 6 standing alerts against 114 lines currently below threshold. |
| `allocation-plan.jpg` | The dispatch dialog with its distance column: 3.8 → 593.3 → 663.0 → 788.0 → 833.6 km, strictly increasing, because the database orders candidates by the same haversine expression the dispatch uses. |
| `audit-log.jpg` | The append-only audit trail. The `stock_update` rows were written by a trigger, not by application code. |

## On the interface

Monochrome, with no hue anywhere. That is a constraint rather than a
preference: almost everything on these pages is a *state* — critical, short,
healthy, overdue — and those are normally carried by red, amber and green.
Doing without means each level needs a signal that is not colour, so severity
is expressed by **ink**: critical is inverted (solid fill, reversed text),
warning is an outline, healthy is a quiet grey. The result survives a
greyscale print and a colour-vision deficiency, and it is checked — a script
walks all fourteen routes and counts any painted element whose RGB channels
differ by more than a threshold.

The surfaces are layered translucent panels over a slowly drifting background
field, with a specular rim that is brightest where light would strike it. Blur
needs something behind it to be visible at all, which is what the field is for.
