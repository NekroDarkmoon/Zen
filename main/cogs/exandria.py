#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations

# Standard library imports
import datetime
import logging
import inspect
import itertools
import os
import re
import sys
import traceback

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union


# Third party imports
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import menus


# Local application imports
from main.settings import config
from main.cogs.utils import formats, time
from main.cogs.utils.context import Context, GuildContext
from main.cogs.utils.paginator import ZenPages


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Exandria(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot
        self.approved_tags = config.approved_tags

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild in [719063399148814418, 739684323141353597]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Validation
        if message.channel.id in [947881939732410379, 739684323807985686]:
            await self._handle_themed_event(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        # Validation
        if before.channel.id in [947881939732410379, 739684323807985686]:
            await self._handle_themed_delete(before)
            await self._handle_themed_event(after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        # Validation
        if message.channel.id in [947881939732410379, 739684323807985686]:
            await self._handle_themed_delete(message)

    # -----------------------------------------------------------------------
    #                          Create and Edit
    async def _handle_themed_event(self, message: discord.Message) -> None:
        # Validation
        if message.author.bot:
            return

        # Data builder
        member = message.author
        content = f'{message.content}\n'
        idx = f'{member.id}_{message.id}'
        location = './events/tr/'

        # Extract Primary Tag
        m = re.findall(r"\[(\w+)\]", content.split('\n')[0])
        if len(m) == 0:
            return

        primary_tag: str = m[1] if 'entry' in m[0].lower() else m[0]

        # Possibly scan all tags
        if primary_tag.lower() not in self.approved_tags:
            # TODO: Place into other
            folder = 'other'
            return
        else:
            folder = primary_tag.lower()

        content = f'{content}\n\nAuthor: {member.__str__()}'

        # Place in correct folder
        out_f = Path(f'{location}{folder}/{idx}')
        out_f.parent.mkdir(exist_ok=True, parents=True)
        out_f.write_text(content, encoding='utf-8')

    # -----------------------------------------------------------------------
    #                               Delete
    async def _handle_themed_delete(self, message: discord.Message) -> None:
        # Validation
        if message.author.bot:
            return

        # Data builder
        member = message.author
        content = f'{message.content}\n'
        idx = f'{member.id}_{message.id}'
        location = './events/tr/'

        # Extract Primary Tag
        m = re.findall(r"\[(\w+)\]", content.split('\n')[0])
        if len(m) == 0:
            return

        primary_tag: str = m[1] if 'entry' in m[0].lower() else m[0]

        # Possibly scan all tags
        if primary_tag.lower() not in self.approved_tags:
            # TODO: Place into other
            folder = 'other'
            return
        else:
            folder = primary_tag.lower()

        # Place in correct folder
        out_f = Path(f'{location}{folder}/{idx}')
        out_f.parent.mkdir(exist_ok=True, parents=True)
        out_f.unlink()


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen) -> None:
    await bot.add_cog(Exandria(bot))
