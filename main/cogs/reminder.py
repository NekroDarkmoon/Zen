#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import argparse
from email.policy import default
from multiprocessing import connection
from multiprocessing.connection import Connection
import shlex
from threading import Thread
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
from discord import TextChannel, app_commands
from discord.ext import commands, tasks
from discord.ext import menus


# Local application imports
from main.cogs.utils import cache, checks, db, formats, time


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
        self._have_data = asyncio.Event()
        self._current_timer: Optional[Timer] = None
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
    #                      Timer Functions
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

    async def create_timer(self, *args: Any, **kwargs: Any) -> Timer:
        r"""Creates a timer.

        Parameters
        -----------
        when: datetime.datetime
            When the timer should fire.
        event: str
            The name of the event to trigger.
            Will transform to 'on_{event}_timer_complete'.
        \*args
            Arguments to pass to the event
        \*\*kwargs
            Keyword arguments to pass to the event
        connection: asyncpg.Connection
            Special keyword-only argument to use a specific connection
            for the DB request.
        created: datetime.datetime
            Special keyword-only argument to use as the creation time.
            Should make the timedeltas a bit more consistent.

        Note
        ------
        Arguments and keyword arguments must be JSON serialisable.

        Returns
        --------
        :class:`Timer`
        """

        when, event, *args = args

        try:
            connection = kwargs.pop('connection')
        except KeyError:
            connection = self.bot.pool

        try:
            now = kwargs.pop('created')
        except KeyError:
            now = discord.utils.utcnow()

        when: datetime.datetime = when.astimezone(
            datetime.timezone.utc).replace(tzinfo=None)
        now = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        timer = Timer.temp(event=event, args=args,
                           kwargs=kwargs, expires=when, created=now)
        delta = (when - now).total_seconds()

        if delta <= 120:
            self.bot.loop.create_task(
                self.short_timer_optimization(delta, timer))
            return timer

        sql = '''INSERT INTO reminders (event, extra, expires, created)
                 VALUES ($1, $2, $3, $4)
                 RETURNING id
              '''

        res = await connection.fetchrow(sql, event, {'args': args, 'kwargs': kwargs}, when, now)
        timer.id = res[0]

        # Only set the data check if it can be waited on
        if delta <= (86400 * 40):  # 40 Days
            self._have_data.set()

        # Check if this timer is earlier than our currently run timer
        if self._current_timer and when < self._current_timer.expires:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer

    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer: Timer) -> None:
        author_id, channel_id, message = timer.args

        try:
            channel = self.bot.get_channel(channel_id) or (await self.bot.fetch_channel(channel_id))
        except discord.HTTPException:
            return

        guild_id = channel.guild.id if isinstance(
            channel, (discord.TextChannel, discord.Thread)) else '@me'
        message_id: Optional[int] = timer.kwargs.get('message_id')
        msg = f'<@{author_id}>, {timer.human_delta}: {message}'
        view = discord.utils.MISSING

        if message_id:
            url = f'https://discord.com/channels/{guild_id}/{channel_id}/{message_id}'
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label='Go to original message', url=url))

        try:
            await channel.send(msg, view=view)
        except discord.HTTPException:
            log.error(
                'Error occurred while sending reminder message.', exc_info=True)
            return

    # ********************************************************
    #                      Commands
    @commands.hybrid_group(invoke_without_command=True)
    async def remind(
        self,
        ctx: Context,
        *,
        when: Annotated[time.FriendlyTimeResult, time.UserFriendlyTime(
            commands.clean_content, default='...')]
    ) -> None:
        """Reminds you of something after a certain amount of time.

        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:

        - "next thursday at 3pm do something funny"
        - "do the dishes tomorrow"
        - "in 3 days do the thing"
        - "2d unmute someone"

        Times are in UTC.
        """

        # Call _remind to support both slash and message command
        await self._remind(ctx, when=when)

    @remind.command(name='remindme')
    async def remindme(self, ctx: Context, msg: str) -> None:
        """Reminds you of something after a certain amount of time."""
        self._remind(ctx, when=msg)

    async def _remind(
        self,
        ctx: Context,
        when: Annotated[time.FriendlyTimeResult, time.UserFriendlyTime(
            commands.clean_content, default='...')]
    ) -> None:

        timer = await self.create_timer(
            when.dt,
            'reminder',
            ctx.author.id,
            when.arg,
            connection=ctx.db,
            created=ctx.message.created_at,
            message_id=ctx.message.id,
        )

        delta = time.human_timedelta(when.dt, source=timer.created_at)
        await ctx.send(f'Alright {ctx.author.mention}, in {delta}: {when.arg}')



# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Reminder(bot))
