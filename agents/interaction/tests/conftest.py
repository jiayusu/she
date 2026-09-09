"""测试公共夹具。"""

import pytest

from she_engine import Engine, EngineConfig
from she_engine.llm import MockProvider
from she_engine.memory import FileMemoryStore, InMemoryStore


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
