#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import asyncio
import datetime
import enum
import logging
import inspect
import itertools
import os
import sys
import traceback

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Optional, Union
import asyncpg

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext import menus


# Local application imports
from main.cogs.utils import cache
from main.cogs.utils.context import Context, GuildContext
from main.cogs.utils.paginator import ZenPages


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class RaidMode(enum.Enum):
    off = 0
    on = 1
    strict = 2

    def __str__(self) -> str:
        return self.name


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ModConfig:
    pass


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class NoMuteRole(commands.CommandError):
    def __init__(self) -> None:
        super().__init__('This server does not have a mute role set up.')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class SpamChecker:
    def __init__(self) -> None:
        pass


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Mod
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Mod(commands.Cog):
    """ Moderation commands. """

    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot
        self._spam_check: defaultdict[int,
                                      SpamChecker] = defaultdict(SpamChecker)

        self._data_batch: defaultdict[int,
                                      list[tuple[int, Any]]] = defaultdict(list)
        self._batch_lock = asyncio.Lock(loop=bot.loop)
        self._disable_lock = asyncio.Lock(loop=bot.loop)
        self.batch_updates.add_exception_type(asyncpg.PostgresConnectionError)
        self.batch_updates.start()

        self.message_batches: defaultdict[tuple[int, int], list[str]] = defaultdict(
            list)
        self._batch_message_lock = asyncio.Lock(loop=bot.loop)
        self.bulk_send_messages.start()

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='DiscordCertifiedModerator', id=847961544124923945)

    def __repr__(self) -> str:
        return '<cogs.Mod>'

    def cog_unload(self) -> None:
        self.batch_updates.stop()
        self.bulk_send_messages.stop()

    async def cog_command_error(self, ctx: GuildContext, error: commands.CommandError) -> None:
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.Forbidden):
                await ctx.send('I do not have permission to execute this action.')
            elif isinstance(original, discord.NotFound):
                await ctx.send(f'This entity does not exist: {original.text}')
            elif isinstance(original, discord.HTTPException):
                await ctx.send('Somehow, an unexpected error occurred. Try again later?')
        elif isinstance(error, NoMuteRole):
            await ctx.send(str(error))

    async def bulk_insert(self) -> None:
        sql = '''UPDATE guild_mog_config
                 SET muted_members = x.result_array
                 FROM jsonb_to_recordset($1::jsonb) AS
                 x ( guild_id BIGINT, result_array BIGINT[] )
                 WHERE guild_mod_config.id = x.guild.id
                '''

        if not self._data_batch:
            return

        final_data = []
        for guild_id, data in self._data_batch.items():
            config = await self.get_guild_config(guild_id)

            if config is None:
                continue

            as_set = config.muted_members
            for member_id, insertion in data:
                func = as_set.add if insertion else as_set.discard
                func(member_id)

            final_data.append(
                {'guild_id': guild_id, 'result_array': list(as_set)})
            self.get_guild_config.invalidate(self, guild_id)

        await self.bot.pool.execute(sql, final_data)
        self._data_batch.clear()

    @tasks.loop(seconds=15.0)
    async def batch_updates(self) -> None:
        async with self._batch_lock:
            await self.bulk_insert()

    @tasks.loop(seconds=10.0)
    async def bulk_send_messages(self) -> None:
        async with self._batch_message_lock:
            for ((guild_id, channel_id), messages) in self.message_batches.items():
                guild = self.bot.get_guild(guild_id)
                channel: Optional[discord.abc.Messageable] = guild and guild.get_channel(
                    channel_id)
                if channel is None:
                    continue

                paginator = commands.Paginator(suffix='', prefix='')
                for message in messages:
                    paginator.add_line(message)

                for page in paginator.pages:
                    try:
                        await channel.send(page)
                    except discord.HTTPException:
                        pass

            self.message_batches.clear()

    @cache.cache()
    async def get_guild_cache(self, guild_id: int) -> Optional[ModConfig]:
        sql = '''SELECT * FROM guild_mod_config WHERE id=$1'''
        async with self.bot.pool.acquire(timeout=300.0) as conn:
            record = await conn.fetchrow(sql, guild_id)

            if record is not None:
                return await ModConfig.from_record(record, self.bot)

            return None


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Mod(bot))
