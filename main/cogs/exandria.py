#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations
import asyncio

# Standard library imports
import logging
import random
import re

from pathlib import Path
from typing import TYPE_CHECKING


# Third party imports
import discord
from discord.ext import commands


# Local application imports
from main.settings import config
from main.cogs.utils.config import Config
from main.cogs.utils.context import Context


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
        self.participants: Config[list[int]] = Config(
            './events/tr/participants.json', loop=bot.loop)

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild.id in [719063399148814418, 739684323141353597]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Validation
        if message.channel.id in [947881939732410379, 739684323807985686]:
            await self._handle_themed_event(message)

            # Add participant
            if message.author.bot or message.author.id == 157433182331863040:
                return

            participants = self.participants.get(message.guild.id, [])
            participants = set(participants)
            participants.add(message.author.id)
            await self.participants.put(message.guild.id, list(participants))

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
            # Place into other
            folder = 'other'
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

    # -----------------------------------------------------------------------
    #                               Commands
    @commands.command(name='start_theme')
    @commands.has_permissions(administrator=True)
    async def start_theme(self, ctx: Context, region: str) -> None:
        # Create content
        separator = '```\n.' + ('\n' * 50) + '.\n```'
        month = discord.utils.utcnow().strftime('%B %Y')
        content = f"`Month of {month} - Region {region.upper()}`\n"
        content += f"`Map -->` https://media.discordapp.net/attachments/725862865176625254/946156671405809754/exandria_themed_space.png"
        content += '\n`For event information check` --> <#970866227935334450>'

        # Empty participants
        await self.participants.put(ctx.guild.id, [])

        # Send to channel
        await ctx.send(separator)
        await ctx.send(content)
        await asyncio.sleep(3)
        await ctx.send('```\n \n```')

        # Delete original message
        await ctx.message.delete()

    @commands.command(name='end_theme')
    @commands.has_permissions(administrator=True)
    async def end_theme(self, ctx: Context, region: str) -> None:
        guild = ctx.guild

        # Get data
        participants = self.participants.get(guild.id, [])
        num_p = len(participants)
        winner = random.choice(participants)
        participants = [(await self.bot.get_or_fetch_member(guild, p)).__str__() for p in participants]

        # Content
        content = f'<@&980602495564939264> \n\n'
        content += f'`DRAW PRIZE GOES TO:` {(await self.bot.get_or_fetch_member(guild, winner)).mention}\n'
        content += f'`END OF REGION {region.upper()}. All submitted resources will be compiled into a document shortly and be available for consumption.`'
        content += f'\n\n`Thank you to everyone that participated.'
        content += f' Stats: {{participants: {num_p}}}`\n'
        content += f'`Participants: {", ".join(participants)}`'

        await ctx.send(content)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen) -> None:
    await bot.add_cog(Exandria(bot))
