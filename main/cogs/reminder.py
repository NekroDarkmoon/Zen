#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import argparse
from multiprocessing.connection import Connection
import shlex
import asyncpg
import asyncio
import datetime
import enum
import logging
import re

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any, Callable, MutableMapping, Optional, Sequence, Union
from typing_extensions import Annotated

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext import menus


# Local application imports
from main.cogs.utils import cache, checks, db, time


if TYPE_CHECKING:
    from typing_extensions import Self
    from utils.context import Context, GuildContext
    from main.Zen import Zen


GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Timer
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Timer:
    __slots__ = ('args', 'kwargs', 'event', 'id', 'created_at', 'expires')

    def __init__(self, *, record: asyncpg.Record) -> None:
        self.id = record.id['id']

        extra = record['extra']
        self.args: Sequence[Any] = extra.get('args', [])
        self.kwargs: dict[str, Any] = extra.get('kwargs', [])
        self.event: str = record['event']
        self.created_at: datetime.datetime = record['created']
        self.expires: datetime.datetime = record['expires']

    @property
    def human_delta(self) -> str:
        return time.format_relative(self.created_at)

    @property
    def author_id(self) -> Optional[int]:
        if self.args:
            return int(self.args[0])
        return None

    @classmethod
    def temp(
        cls,
        *,
        expires: datetime.datetime,
        created: datetime.datetime,
        event: str,
        args: Sequence[Any],
        kwargs: dict[str, Any]
    ) -> Self:
        pseudo = {
            'id': None,
            'extra': {'args': args, 'kwargs': kwargs},
            'event': event,
            'created': created,
            'expires': expires,
        }

        return cls(record=pseudo)

    def __eq__(self, other: object) -> bool:
        try:
            return self.id == other.id
        except AttributeError:
            return False

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f'<Timer created={self.created_at} expires={self.expires} event={self.event}>'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Reminder(commands.Cog):
    """ Reminders to do something."""

    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = Optional[Timer] = None
        self._task = bot.loop.create_task(self.dispatch_timers())

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{ALARM CLOCK}')

    async def cog_command_error(self, ctx: Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
        if isinstance(error, commands.TooManyArguments):
            await ctx.send(f'You called the {ctx.command.name} command with too many arguments.')

    def cog_unload(self) -> None:
        self._task.cancel()

    # ********************************************************
    #                      Time Functions
    async def get_active_timer(
        self, *, connection: Optional[asyncpg.Connection] = None, days: int = 7
    ) -> Optional[Timer]:
        # Data builder
        conn = connection or self.bot.pool

        sql = '''SELECT * FROM reminders WHERE expires < (CURRENT_DATE + $1::interval)
                 ORDER BY expires LIMIT 1'''
        res = await conn.fetchrow(sql, datetime.timedelta(days=days))

        return Timer(record=res) if res else None

    async def wait_for_active_timers(
        self, *, connection: Optional[asyncpg.Connection] = None, days: int = 7
    ):
        async with db.MaybeAcquire(connection=connection, pool=self.bot.pool) as conn:
            timer = await self.get_active_timer(connection=conn, days=days)
            if timer is not None:
                self._have_data.set()
                return timer

            self._have_data.clear()
            self._current_timer = None
            await self._have_data.wait()

            return await self.get_active_timer(connection=conn, days=days)

    async def call_timer(self, timer: Timer) -> None:
        sql = '''DELETE FROM reminders WHERE id=$1'''
        await self.bot.pool.execute(sql, timer.id)

        event_name = f'{timer.event}_timer_complete'
        self.bot.dispatch(event_name, timer)

    async def dispatch_timers(self) -> None:
        try:
            while not self.bot.is_closed():
                # can only asyncio.sleep for up to ~48 days reliably
                # so we're gonna cap it off at 40 days
                # see: http://bugs.python.org/issue20493
                timer = self._current_timer = await self.wait_for_active_timers(days=40)
                now = datetime.datetime.utcnow()

                if timer.expires >= now:
                    to_sleep = (timer.expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)

        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

    async def short_timer_optimization(self, seconds: int, timer: Timer) -> None:
        await asyncio.sleep(seconds)
        event_name = f'{timer.event}_timer_complete'
        self.bot.dispatch(event_name, timer)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen):
    await bot.add_cog(Reminder(bot))
