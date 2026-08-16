# Build context is the repo root (see infra/docker-compose.prod.yml), not
# backend/ alone -- seed_model_and_rules.py and model_loader.py both resolve
# ml/artifacts/ as a sibling of backend/ (parents[3] from a script under
# backend/app/scripts/), so that directory has to be reachable from this
# build, which a backend/-only context can't do.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# --no-deps: xgboost's Linux wheel otherwise pulls in a ~340MB nvidia-nccl-cu12
# package for multi-GPU distributed training this single-node CPU service
# never uses -- see the comment in requirements.txt. Its actual runtime deps
# (numpy, scipy) are already satisfied by shap/pandas above.
RUN pip install --no-cache-dir --no-deps xgboost==2.1.1

COPY backend/ .
COPY ml/artifacts/ /ml/artifacts/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
