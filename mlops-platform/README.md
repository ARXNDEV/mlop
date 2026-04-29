# mlops-platform

End-to-end MLOps observability platform with automated retraining, drift detection, deterministic A/B testing, and a live monitoring dashboard.

## Services
- Airflow: http://localhost:8080 (admin/admin)
- FastAPI: http://localhost:8000 (OpenAPI at /docs)
- Dashboard: http://localhost:3000
- MLflow: http://localhost:5000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin)

## Quickstart
```bash
cd mlops-platform
cp .env.example .env
docker compose up --build
```

## Typical workflow
- Generate simulated batches:
  ```bash
  docker compose exec api python -m ml.data_simulator --steps 50 --drift-magnitude 0.3
  ```
- Run drift check DAG hourly (or trigger manually in Airflow).
- When retraining promotes a new model, the API hot-reloads via `/admin/reload`.

## Testing
```bash
cd mlops-platform
pytest -q
```
