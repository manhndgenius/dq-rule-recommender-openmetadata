"""Keep the backend example aligned with the local PostgreSQL Compose file."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def test_backend_example_matches_local_postgres_compose():
    backend_env = _read_env(ROOT / "backend" / ".env.example")
    database_env = _read_env(ROOT / ".env.postgres.local.example")
    compose = (ROOT / "docker-compose.local-db.yml").read_text(
        encoding="utf-8"
    )

    assert backend_env["POSTGRES_HOST"] == "127.0.0.1"
    assert backend_env["POSTGRES_PORT"] == "5433"
    assert '"5433:5432"' in compose
    assert backend_env["POSTGRES_DB"] == database_env["POSTGRES_DB"]
    assert backend_env["POSTGRES_USER"] == database_env["POSTGRES_USER"]
    assert (
        backend_env["POSTGRES_PASSWORD"]
        == database_env["POSTGRES_PASSWORD"]
    )
