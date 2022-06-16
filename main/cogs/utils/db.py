#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations


# Standard library imports
import json
import logging
from typing import TYPE_CHECKING

# Third party imports
import asyncpg


# Local application imports
from main.settings import schema


if TYPE_CHECKING:
    from typing_extensions import Self


log = logging.getLogger(__name__)

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                           Error
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


class SchemaError(Exception):
    pass


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Maybe Acquire
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class MaybeAcquire:
    def __init__(self, connection, *, pool) -> None:
        self.connection = connection
        self.pool = pool
        self._cleanup = False

    async def __aenter__(self):
        if self.connection is None:
            self._cleanup = True
            self._connection = c = await self.pool.acquire()
            return c
        return self.connection

    async def __aexit__(self, *args):
        if self._cleanup:
            await self.pool.release(self._connection)


# --------------------------------------------------------------------------
#                                    DB Class
# --------------------------------------------------------------------------
class DB:
    @classmethod
    async def create_pool(cls, uri: str, **kwargs):
        def _encode_jsonb(value):
            return json.dumps(value)

        def _decode_jsonb(value):
            return json.loads(value)

        old_init = kwargs.pop('init', None)

        async def init(conn):
            await conn.set_type_codec('jsonb', schema='pg_catalog', encoder=_encode_jsonb, decoder=_decode_jsonb, format='text')
            if old_init is not None:
                await old_init(conn)

        cls._pool = pool = await asyncpg.create_pool(uri, init=init, **kwargs)
        log.info('Connected to db and acquired pool.')

        # Do db stuff
        try:
            await cls.create_schemas(pool)
        except Exception as e:
            print(e)

        return pool

    @classmethod
    def acquire_connection(cls, conn):
        return MaybeAcquire(conn, pool=cls._pool)

    # Create Schemas
    @classmethod
    async def create_schemas(cls, conn):
        sql_queries: dict = schema.tables
        ct: str = "CREATE TABLE IF NOT EXISTS"

        # Optionally create tables
        for table, query in sql_queries.items():
            sql: str = f"{ct} {table}({query})"
            await conn.execute(sql)

        # TODO: Optionally create indexes

    # Get Migrations.
    @classmethod
    def get_migrations(cls):
        pass

    # Migrate if needed.
    @classmethod
    def migrate(cls, conn):
        pass

    # Data integrity checks.
    # Log information
