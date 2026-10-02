import pytest

from app.adapters.database import database_url


@pytest.fixture(autouse=True)
def clear_database_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_USER", "DATABASE_NAME", "DATABASE_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_database_url_raises_when_unset_or_blank(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        database_url()


def test_database_url_uses_environment_value(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://configured@database:5432/custom"
    monkeypatch.setenv("DATABASE_URL", url)
    assert database_url().render_as_string(hide_password=False) == url


@pytest.mark.parametrize(
    "value",
    [
        "not-a-url-private-password",
        "postgresql+asyncpg://user:private-password@localhost:badport/database",
        "sqlite:///database",
        "postgresql://user:private-password@localhost/database",
        "postgresql+asyncpg://user:private-password@localhost:70000/database",
    ],
)
def test_database_url_rejects_invalid_configuration_without_exposing_credentials(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(RuntimeError) as error:
        database_url()
    assert "DATABASE_URL" in str(error.value)
    assert "private-password" not in str(error.value)


@pytest.mark.parametrize("password", ["", "   "])
def test_database_password_override_rejects_blank_values(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@database/custom")
    monkeypatch.setenv("DATABASE_PASSWORD", password)
    with pytest.raises(RuntimeError, match="DATABASE_PASSWORD must not be blank"):
        database_url()


@pytest.mark.parametrize("name", ["DATABASE_USER", "DATABASE_NAME"])
@pytest.mark.parametrize("value", ["", "   "])
def test_database_user_and_name_overrides_reject_blank_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db:5432")
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=f"{name} must not be blank"):
        database_url()
