"""Loads the active model version's packaged artifact (model + preprocessor
+ feature order + locked thresholds, produced by
ml/training/09_package_model.py) and caches it in-process.

Loaded once per process, not per request -- re-loading a ~1.5MB joblib
artifact on every score would blow the P50<100ms latency budget for no
reason.

artifact_uri (stored per model_version row, not hardcoded anywhere in code)
is either a local filesystem path or an s3://bucket/key URI -- which bucket,
if any, is entirely a deployment-time configuration choice (see
app/scripts/seed_model_and_rules.py), never a name baked into this module.
"""
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import joblib
import shap
from sqlalchemy.orm import Session

from app.models.model_version import ModelVersion

_lock = threading.Lock()


def _resolve_artifact_path(artifact_uri: str) -> str:
    """Local path -> returned as-is. s3://bucket/key -> downloaded to a temp
    file first. Credentials are never handled here -- boto3 picks them up
    from the EC2 instance's IAM role (or local AWS config) automatically."""
    parsed = urlparse(artifact_uri)
    if parsed.scheme != "s3":
        return artifact_uri

    import boto3  # imported lazily -- only needed when an S3 URI is actually used

    bucket, key = parsed.netloc, parsed.path.lstrip("/")
    suffix = Path(key).suffix or ".pkl"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    boto3.client("s3").download_file(bucket, key, tmp.name)
    return tmp.name


@dataclass
class LoadedModel:
    model_version_id: uuid.UUID
    version_tag: str
    model: object
    preprocessor: object
    feature_columns: list[str]
    output_feature_names: list[str]
    policy: dict
    shap_explainer: object


_cache: LoadedModel | None = None


def get_active_model(db: Session) -> LoadedModel:
    global _cache
    if _cache is not None:
        return _cache

    with _lock:
        if _cache is not None:  # re-check after acquiring the lock
            return _cache

        mv = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).one_or_none()
        if mv is None:
            raise RuntimeError(
                "No active model_version found. Run "
                "`python -m app.scripts.seed_model_and_rules` first."
            )

        local_path = _resolve_artifact_path(mv.artifact_uri)
        package = joblib.load(local_path)
        # Building the TreeExplainer parses the model's tree structure --
        # expensive enough (order of seconds) that doing it per-request was
        # blowing the P50<100ms budget by 30x. Cached once per process,
        # alongside the model itself.
        explainer = shap.TreeExplainer(package["model"])
        _cache = LoadedModel(
            model_version_id=mv.id,
            version_tag=mv.version_tag,
            model=package["model"],
            preprocessor=package["preprocessor"],
            feature_columns=package["feature_columns"],
            output_feature_names=package["output_feature_names"],
            policy=package["policy"],
            shap_explainer=explainer,
        )
        return _cache


def is_loaded() -> bool:
    """Backs the health endpoint -- deliberately checked, not assumed, so a
    broken model source (bad S3 key, unreachable bucket) shows up as an
    unhealthy container rather than a process that's "up" but would fail
    the first real scoring request."""
    return _cache is not None


def reset_cache() -> None:
    """Test/ops hook -- forces the next get_active_model() call to reload."""
    global _cache
    with _lock:
        _cache = None
