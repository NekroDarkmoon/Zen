#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import asyncio
import asyncpg
import datetime
import logging
import textwrap

from typing import TYPE_CHECKING, Any, Optional, Sequence
from typing_extensions import Annotated

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import menus


# Local application imports
from main.cogs.utils import db, formats, time
from main.cogs.utils.paginator import ZenPages


if TYPE_CHECKING:
    from typing_extensions import Self
    from utils.context import Context
    from main.Zen import Zen


GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Timer
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Timer:
    __slots__ = ('args', 'kwargs', 'event', 'id', 'created_at', 'expires')

    def __init__(self, *, record: asyncpg.Record) -> None:
        self.id = record['id']

        extra = record['extra']
        self.args: Sequence[Any] = extra.get('args', [])
        self.kwargs: dict[str, Any] = extra.get('kwargs', [])
        self.event: str = record['event']
        self.created_at: datetime.datetime = record['created_at']
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
        created_at: datetime.datetime,
        event: str,
        args: Sequence[Any],
        kwargs: dict[str, Any]
    ) -> Self:
        pseudo = {
            'id': None,
            'extra': {'args': args, 'kwargs': kwargs},
            'event': event,
            'created_at': created_at,
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
#                         Pages
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ReminderPagesSource(menus.ListPageSource):
    async def format_page(self, menu, entries: list[asyncpg.Record]) -> discord.Embed:
        for idx, (_id, expires, message) in enumerate(entries, start=menu.current_page * self.per_page):
            shorten = textwrap.shorten(message, width=512)
            menu.embed.add_field(
                name=f'{_id}: {time.format_relative(expires) }',
                value=shorten,
                inline=False
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        return menu.embed


class ReminderPages(ZenPages):
    def __init__(self, entries, *, ctx: Context, per_page: int = 12):
        super().__init__(ReminderPagesSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(color=discord.Color.random())


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
        created_at: datetime.datetime
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
            now = kwargs.pop('created_at')
        except KeyError:
            now = discord.utils.utcnow()

        when: datetime.datetime = when.astimezone(
            datetime.timezone.utc).replace(tzinfo=None)
        now = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        timer = Timer.temp(event=event, args=args,
                           kwargs=kwargs, expires=when, created_at=now)
        delta = (when - now).total_seconds()

        if delta <= 120:
            self.bot.loop.create_task(
                self.short_timer_optimization(delta, timer))
            return timer

        sql = '''INSERT INTO reminders (event, extra, expires, created_at)
                 VALUES ($1, $2::jsonb, $3, $4)
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
        *,
        when: Annotated[time.FriendlyTimeResult, time.UserFriendlyTime(
            commands.clean_content, default='...')]
    ) -> None:

        timer = await self.create_timer(
            when.dt,
            'reminder',
            ctx.author.id,
            ctx.channel.id,
            when.arg,
            connection=ctx.db,
            created_at=ctx.message.created_at,
            message_id=ctx.message.id,
        )

        delta = time.human_timedelta(when.dt, source=timer.created_at)
        await ctx.send(f'Alright {ctx.author.mention}, in {delta}: {when.arg}')

    @remind.command(name='list')
    async def reminder_list(self, ctx: Context) -> None:
        """Shows currently running reminders."""
        sql = """SELECT id, expires, extra #>> '{args, 2}'
                 FROM reminders
                 WHERE event = 'reminder'
                 AND extra #>> '{args, 0}' = $1
                 ORDER BY expires
              """

        records = await ctx.db.fetch(sql, str(ctx.author.id))

        if len(records) == 0:
            return await ctx.send('`No currently running reminders.`')

        e = discord.Embed(title='Reminders', color=discord.Colour.random())

        # Add Paginator
        p = ReminderPages(entries=records, per_page=10, ctx=ctx)
        p.embed.set_author(name=ctx.author.display_name)
        p.embed.set_thumbnail(url=ctx.author.display_avatar)
        await p.start()

    @remind.command(name='delete')
    @app_commands.describe(id='Reminder id')
    async def reminder_delete(self, ctx: Context, id: int) -> None:
        """Deletes a reminder by its ID.

        To get a reminder ID, use the reminder list command.

        You must own the reminder to delete it, obviously.
        """
        sql = """ DELETE FROM reminders
                  WHERE id=$1
                  AND event='reminder'
                  AND extra #>> '{args, 0}'=$2
              """
        status = await ctx.db.execute(sql, id, str(ctx.author.id))

        if status == 'DELETE 0':
            return await ctx.send('`Could not delete any reminders with that ID.`')

        if self._current_timer and self._current_timer.id == id:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await ctx.send('`Successfully deleted reminder.`')

    @remind.command(name='clear')
    async def reminder_clear(self, ctx: Context) -> None:
        """Clears all reminders you have set."""
        sql = """SELECT COUNT(*)
                 FROM reminders
                 WHERE event = 'reminder'
                 AND extra #>> '{args,0}' = $1;
              """

        author_id = str(ctx.author.id)
        total: asyncpg.Record = await ctx.db.fetchrow(sql, author_id)
        total = total[0]
        if total == 0:
            return await ctx.send('`You do not have any reminders to delete.`')

        # TODO: Convert to interaction
        confirm = await ctx.prompt(f'Are you sure you want to delete {formats.Plural(total):reminder}?')
        if not confirm:
            return await ctx.send('Aborting')

        sql = """DELETE FROM reminders WHERE event = 'reminder' AND extra #>> '{args,0}' = $1;"""
        await ctx.db.execute(sql, author_id)

        # Check if the current timer is the one being cleared and cancel it if so
        if self._current_timer and self._current_timer.author_id == ctx.author.id:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await ctx.send(f'Successfully deleted {formats.Plural(total):reminder}.')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Reminder(bot))
