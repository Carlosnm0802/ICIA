import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "database_schema.sql"


def _config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


def _table_names(connection: sqlite3.Connection) -> list[str]:
    return sorted(
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' "
            "AND name <> 'alembic_version'"
        )
    )


def _index_signature(
    connection: sqlite3.Connection,
) -> dict[str, tuple[str, int, int, tuple[str, ...]]]:
    signature = {}
    for table in _table_names(connection):
        for row in connection.execute(f'PRAGMA index_list("{table}")'):
            name = row[1]
            if name.startswith("sqlite_autoindex"):
                continue
            columns = tuple(
                item[2]
                for item in connection.execute(f'PRAGMA index_info("{name}")')
            )
            signature[name] = (table, row[2], row[4], columns)
    return signature


def _check_signature(
    connection: sqlite3.Connection,
    table: str,
) -> list[str]:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if row is None or row[0] is None:
        return []

    checks = []
    text = row[0]
    position = 0
    while True:
        start = text.upper().find("CHECK", position)
        if start == -1:
            break
        opening = text.find("(", start)
        if opening == -1:
            break
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    checks.append(
                        " ".join(text[opening + 1 : index].split()).lower()
                    )
                    position = index + 1
                    break
        else:
            break
    return sorted(checks)


def _object_signature(
    connection: sqlite3.Connection,
    kind: str,
) -> dict[str, str]:
    return {
        name: " ".join(sql.split())
        for name, sql in connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = ? AND name NOT LIKE 'sqlite_%'",
            (kind,),
        )
    }


def _schema_signature(database_path: Path) -> dict[str, object]:
    connection = sqlite3.connect(database_path)
    try:
        tables = _table_names(connection)
        return {
            "tables": tables,
            "columns": {
                table: list(
                    connection.execute(f'PRAGMA table_info("{table}")')
                )
                for table in tables
            },
            "foreign_keys": {
                table: sorted(
                    (row[2], row[3], row[4], row[5], row[6], row[7])
                    for row in connection.execute(
                        f'PRAGMA foreign_key_list("{table}")'
                    )
                )
                for table in tables
            },
            "checks": {
                table: _check_signature(connection, table) for table in tables
            },
            "indexes": _index_signature(connection),
            "triggers": _object_signature(connection, "trigger"),
            "views": _object_signature(connection, "view"),
        }
    finally:
        connection.close()


def _create_contract_database(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(SCHEMA_PATH.read_text())
    finally:
        connection.close()


@pytest.fixture
def migrated_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "migrated.db"
    command.upgrade(_config(database_path), "head")
    return database_path


def test_migration_matches_schema_contract(
    tmp_path: Path,
    migrated_database: Path,
) -> None:
    contract_database = tmp_path / "contract.db"
    _create_contract_database(contract_database)

    assert _schema_signature(migrated_database) == _schema_signature(
        contract_database
    )


def test_models_and_migration_are_in_sync(migrated_database: Path) -> None:
    command.check(_config(migrated_database))


def test_foreign_keys_are_enforced(migrated_database: Path) -> None:
    with sqlite3.connect(migrated_database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO grupos ("
                "sucursal_id, nombre, dias_semana, hora_inicio, hora_fin, "
                "precio_centavos"
                ") VALUES (999, 'Grupo', 'Lunes', '15:00', '17:00', 14000)"
            )


def test_folio_and_payment_triggers(migrated_database: Path) -> None:
    with sqlite3.connect(migrated_database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO sucursales (nombre, prefijo_folio) "
            "VALUES ('El Refugio', 'REF')"
        )
        assert connection.execute(
            "SELECT ultimo_consecutivo FROM folio_contadores "
            "WHERE sucursal_id = 1"
        ).fetchone() == (0,)
        connection.execute("INSERT INTO alumnos (nombre) VALUES ('Alumno')")
        connection.execute(
            "INSERT INTO pagos ("
            "folio, alumno_id, sucursal_id, tipo, monto_centavos, metodo"
            ") VALUES ('REF-0001', 1, 1, 'sesion', 14000, 'efectivo')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE pagos SET folio = 'REF-0002' WHERE id = 1"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM pagos WHERE id = 1")


def test_downgrade_removes_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "downgrade.db"
    config = _config(database_path)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        objects = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('trigger', 'view')"
            )
        }

    assert tables == {"alembic_version"}
    assert objects == set()
