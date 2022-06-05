#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import argparse
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
from main.cogs.utils import cache, time, checks


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

    async def dispatch_times(self) -> None:
        ...


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Reminder(bot))
