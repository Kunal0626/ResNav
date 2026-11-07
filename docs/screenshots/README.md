# Screenshots

Captured from the running application on 2026-11-07, against the deterministic
seed (`make reset`) with four requests dispatched, so every number visible is
real data this repository can reproduce.

| file | what it shows |
|---|---|
| `stock-alerts.jpg` | Standing low-stock alerts, raised by `trg_stocklevels_au_alert`. Note the two counts are deliberately different: 6 standing alerts against 119 lines currently below threshold. |
| `audit-log.jpg` | The append-only audit trail. The `stock_update` rows were written by a trigger, not by application code, which is why they cannot be skipped. |
| `allocation-plan.jpg` | The dispatch plan with its distance column: 3.8 km, 593.3 km, 663.8 km, 788.0 km, 833.8 km — strictly increasing, because the database orders candidates by the same haversine expression the dispatch itself uses. |
