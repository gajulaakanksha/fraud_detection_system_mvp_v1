"""Loads the active model version's packaged artifact (model + preprocessor
+ feature order + locked thresholds, produced by
ml/training/09_package_model.py) and caches it in-process.

Loaded once per process, not per request -- re-loading a ~1.5MB joblib
artifact on every score would blow the P50<100ms latency budget for no
reason.
"""
import threading
import uuid
from dataclasses import dataclass

import joblib
import shap
from sqlalchemy.orm import Session

from app.models.model_version import ModelVersion

_lock = threading.Lock()


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

        package = joblib.load(mv.artifact_uri)
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


def reset_cache() -> None:
    """Test/ops hook -- forces the next get_active_model() call to reload."""
    global _cache
    with _lock:
        _cache = None
