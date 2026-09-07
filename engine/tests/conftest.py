"""测试公共夹具。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from she_engine import Engine, EngineConfig          # noqa: E402
from she_engine.llm import MockProvider               # noqa: E402
from she_engine.memory import FileMemoryStore, InMemoryStore  # noqa: E402


@pytest.fixture
def mock_engine() -> Engine:
    return Engine(EngineConfig(provider=MockProvider(), session_level=1))


@pytest.fixture
def file_engine(tmp_path) -> Engine:
    return Engine(EngineConfig(
        provider=MockProvider(),
        memory=FileMemoryStore(str(tmp_path / "data")),
        session_level=1,
    ))


@pytest.fixture
def mem_store() -> InMemoryStore:
    return InMemoryStore()
