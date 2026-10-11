"""Keep local unit tests independent of any cloud credentials in the shell."""

import pytest


@pytest.fixture(autouse=True)
def no_live_provider_credentials(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("VOLC_API_KEY", raising=False)
