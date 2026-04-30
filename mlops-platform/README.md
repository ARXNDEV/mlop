# mlops-platform
Production-grade MLOps observability platform: training → registry → serving → monitoring, with drift-triggered retraining, deterministic A/B testing, and a live dashboard.

## Architecture
```
                           ┌──────────────────────────┐
                           │        Dashboard          │
                           │   Next.js (port 3000)     │
                           └─────────────┬────────────┘
                                         │ REST
                                         v
┌───────────────┐   registry/metrics   ┌──────────────────────────┐   scrape    ┌───────────────┐
│    MLflow      │<─────────────────────│           API             │────────────>│  Prometheus    │
│ (port 5000)    │                      │ FastAPI (port 8000)       │             │ (port 9090)    │
└───────┬────────┘                      └─────────────┬────────────┘             └───────┬───────┘
        │                                             │                                  │
        │ backend-store                               │ A/B stats                         │ dashboards
        v                                             v                                  v
┌───────────────┐                             ┌───────────────┐                 ┌───────────────┐
│   Postgres     │<────────────────────────────│     Redis      │                 │    Grafana     │
│ (port 5432)    │                             │                │                 │ (port 3001)    │
└───────┬────────┘                             └───────────────┘                 └───────────────┘
        │
        │ exporter
        v
┌───────────────┐
│ Postgres Exp.  │
│ (port 9187)    │
└───────────────┘

┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ Airflow (port 8080) runs: drift_check_hourly → (if drift) retrain_pipeline → API reload   │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites
- Docker Desktop
- Docker Compose v2
- Python 3.11 (optional, for local scripts/tests)
- Node 20 (optional, for local dashboard dev)

## Quick start
```bash
git clone https://github.com/ARXNDEV/mlop.git
cd mlop/mlops-platform
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m ml.data_simulator --steps 50 --drift-magnitude 0.3
open http://localhost:3000
```

## Service URLs
| Service | URL |
|--------:|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| MLflow | http://localhost:5001 |
| Airflow | http://localhost:8080 |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |

## Demo walkthrough (drift → retrain → promotion)
1. Start the stack with `docker compose up -d --build`.
2. Generate drifted streaming batches with `python -m ml.data_simulator`.
3. In Airflow, enable the `drift_check_hourly` DAG and trigger it manually.
4. Drift DAG evaluates the latest batch, computes per-feature PSI, and posts drift + report metadata to the API.
5. If drift exceeds `DRIFT_THRESHOLD`, the DAG triggers `retrain_pipeline`.
6. Retrain pipeline validates schema, trains a new model, evaluates against the F1 gate (>= 0.75), and registers to MLflow.
7. If the new model improves production by `RETRAIN_METRIC_THRESHOLD`, it is promoted to Production; otherwise it remains Staging.
8. API hot-reloads models via `POST /admin/reload` and the dashboard/Grafana reflect the new active versions.

## Key design decisions
- PSI over KS test: PSI is simple, interpretable, and supports per-feature drift ranking for dashboards and triage.
- Deterministic A/B routing: user_id hashing ensures consistent experiences per user and avoids cross-model leakage.
- MLflow Staging → Production gates: prevents regressions by requiring measurable improvement over current production.
- Async FastAPI with 2 workers: supports concurrent batch inference and avoids a single-process bottleneck.

## Project structure
```
mlops-platform/
  airflow/
    dags/
      drift_check.py
      retrain_pipeline.py
  api/
    main.py
    core/
    routers/
    middleware/
    models/
  dashboard/
    app/
    components/
    lib/
  ml/
    train.py
    evaluate.py
    drift_detector.py
    model_registry.py
    data_simulator.py
  monitoring/
    prometheus.yml
    grafana/
  tests/
```

## Running tests
```bash
pytest tests/ -v
```

## Internship talking points
- Built an end-to-end MLOps system: orchestration, registry, serving, and observability in one Dockerized stack.
- Implemented drift detection with per-feature PSI and integrated evidence (HTML reports) into a UI workflow.
- Added deterministic A/B routing with Redis-backed aggregates and significance testing.
- Exposed metrics to Prometheus and shipped pre-provisioned Grafana dashboards for latency, accuracy/drift, and A/B monitoring.
- Automated model lifecycle with Airflow gates and production promotion rules to prevent regressions.
