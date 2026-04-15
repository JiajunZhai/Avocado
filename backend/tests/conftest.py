"""Keep RAG tests on TF-IDF so CI does not download embedding models."""
import os

import pytest
from fastapi.testclient import TestClient

import main

os.environ["RAG_RETRIEVAL"] = "tfidf"


@pytest.fixture()
def client():
    with TestClient(main.app) as c:
        yield c
