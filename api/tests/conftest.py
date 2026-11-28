import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import ModelRegistry


class StubDetector:
    def detect(self, image):
        return None


class StubBreed:
    classes = ["gir"]
    threshold = 0.45
    labels = {"model_name": "stub"}

    def predict(self, image, box=None, top_k=3, species=None):
        return {"breed": "gir", "confidence": 0.9, "unsure": False, "top": []}


@pytest.fixture
def settings():
    return Settings(load_models=False, max_upload_mb=1, _env_file=None)


def make_client(settings, registry):
    return TestClient(create_app(settings, registry))


@pytest.fixture
def client(settings):
    reg = ModelRegistry(detector=StubDetector(), breed=StubBreed(),
                        info={"detector": {"name": "stub"}, "breed": {"name": "stub"}})
    with make_client(settings, reg) as c:
        yield c
