import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "clients" / "python"))


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    """Seed dataset + one trained model version in a temp dir."""
    d = tmp_path_factory.mktemp("kalkan")
    subprocess.run([sys.executable, str(ROOT / "scripts/build_dataset.py"), "--out", str(d / "data")],
                   check=True, capture_output=True)
    from kalkan.adapters.data.jsonl import JsonlDataSource
    from kalkan.adapters.registry.filesystem import FileSystemModelRegistry
    from kalkan.application.factory import PipelineFactory
    from kalkan.application.training import ModelTrainer
    reg = FileSystemModelRegistry(d / "models")
    v, _ = ModelTrainer(reg, JsonlDataSource(d / "data"), PipelineFactory()).train_new_version()
    reg.activate(v)
    return d


def make_app(trained, tmp_path, **overrides):
    from kalkan.api.app import create_app
    from kalkan.api.settings import Settings
    s = Settings(models_dir=trained / "models", data_dir=trained / "data", db_path=tmp_path / "k.db",
                 api_keys={}, admin_key="", policies={})
    for k, v in overrides.items():
        setattr(s, k, v)
    return create_app(s)
