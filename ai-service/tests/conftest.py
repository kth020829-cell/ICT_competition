"""테스트 공통 설정.

두 가지를 보장한다.

1. **개발자의 `.env`가 테스트 결과를 바꾸지 않는다.** `AI_MODE=remote` 로 개발
   중인 사람과 `mock` 인 사람의 결과가 달라지면 테스트가 신뢰를 잃는다.
   기본값을 mock으로 고정하고, 필요한 테스트만 명시적으로 바꾼다.

2. **기본 테스트는 네트워크도 비용도 쓰지 않는다.** VLM을 실제로 부르는
   테스트는 `@pytest.mark.vlm` 을 달고, `RUN_VLM_TESTS=1` 일 때만 돈다.

       pytest tests -q                    # 무료·오프라인
       RUN_VLM_TESTS=1 pytest tests -q    # 실제 API 호출 포함
"""

from __future__ import annotations

import os

import pytest

from app.core.config import get_settings


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "vlm: 실제 Claude API를 호출한다 (RUN_VLM_TESTS=1 에서만 실행)"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_VLM_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="실제 API 호출. RUN_VLM_TESTS=1 로 실행하세요.")
    for item in items:
        if "vlm" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _mock_mode_by_default(monkeypatch: pytest.MonkeyPatch):
    """AI_MODE를 mock으로 고정한다.

    `get_settings()` 가 lru_cache라 환경변수를 바꾼 뒤 캐시를 비워야 반영된다.
    테스트 전후로 비워서 서로 영향을 주지 않게 한다.
    """
    monkeypatch.setenv("AI_MODE", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def remote_mode(monkeypatch: pytest.MonkeyPatch):
    """실제 추론 경로를 타야 하는 테스트용."""
    monkeypatch.setenv("AI_MODE", "remote")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
