#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations
import asyncio

# Standard library imports
import logging
import random
import os

from typing import TYPE_CHECKING, Optional


# Third party imports
import discord

from discord.ext import commands
from google.oauth2.service_account import Credentials
from gspread import authorize

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
class SheetHandler:
    def __init__(self, sheet_ids: list) -> None:
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        self.sheet_ids = set()
        self._active = False
        self.credentials = None

        self._connect()

    def _connect(self) -> None:
        if os.path.exists('./main/settings/credentials.json'):
            self.credentials = Credentials.from_service_account_file(
                './main/settings/credentials.json',
                scopes=self.SCOPES
            )
            self._active = True
        else:
            return log.error("Unable to find credentials file. Aborting connection.")

        self.sheetClient = authorize(self.credentials)


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
        sheet_ids = list(
            bot.google_sheet_ids.all().values()
        )
        self.sheetHandler = SheetHandler(sheet_ids)

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild.id in [719063399148814418, 739684323141353597]

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
