import os
import tempfile

import pytest

# Use PostgreSQL when CI provides DATABASE_URL, otherwise a throwaway SQLite file.
if "DATABASE_URL" not in os.environ:
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
