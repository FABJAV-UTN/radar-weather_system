import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.data.database import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py
config.set_main_option("sqlalchemy.url", settings.database_url)


def include_object(object, name, type_, reflected, compare_to):
    """
    Ignorar tablas del sistema de PostGIS.
    Alembic no debe tocar tablas internas de extensiones.
    """
    if type_ == "table":
        # Ignorar tablas del tiger geocoder y otras del sistema PostGIS
        ignored_prefixes = (
            "pagc_",
            "tiger_",
            "topology",
            "spatial_ref_sys",
            "layer",
            "geocode_",
            "loader_",
            "zip_",
            "county",
            "cousub",
            "place",
            "tract",
            "bg",
            "tabblock",
            "zcta5",
            "addr",
            "addrfeat",
            "edges",
            "faces",
            "featnames",
            "state",
            "direction_lookup",
            "street_type_lookup",
            "secondary_unit_lookup",
            "county_lookup",
            "countysub_lookup",
            "place_lookup",
        )
        if name.startswith(ignored_prefixes) or name in (
            "layer",
            "topology",
            "spatial_ref_sys",
        ):
            return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()