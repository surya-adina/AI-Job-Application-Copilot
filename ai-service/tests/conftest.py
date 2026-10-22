import pytest

TEST_SERVICE_TOKEN = "test-service-token-0123456789abcdef"


@pytest.fixture(autouse=True)
def no_real_api_clients(monkeypatch):
    """Tests must pass fakes explicitly; a real OpenAI client is never created."""

    def blocked():
        raise RuntimeError("Real OpenAI client requested in a test")

    monkeypatch.setattr("llm.client.get_default_client", blocked)
    monkeypatch.setattr("skills.embedding_client.get_embedding_client", blocked)


@pytest.fixture(autouse=True)
def service_token(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_TOKEN", TEST_SERVICE_TOKEN)
