from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (registrasi tabel)
from app.config import load_settings
from app.db import Base, include_object

config = context.config
target_metadata = Base.metadata
connection = config.attributes.get("connection")

if connection is None:
    # Dipanggil dari CLI `alembic ...`: pakai konfigurasi environment yang sama dengan aplikasi.
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    config.set_main_option("sqlalchemy.url", load_settings().database_url.replace("%", "%%"))


def run_with(conn) -> None:
    context.configure(connection=conn, target_metadata=target_metadata,
                      render_as_batch=conn.dialect.name == "sqlite", compare_type=True,
                      include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
elif connection is not None:
    run_with(connection)
else:
    load_settings().data_dir.mkdir(parents=True, exist_ok=True)
    engine = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
                                poolclass=pool.NullPool)
    with engine.connect() as conn:
        run_with(conn)
