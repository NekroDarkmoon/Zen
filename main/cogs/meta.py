# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Standard library imports
import aiohttp
import datetime
import logging
import os
import sys
import traceback

from typing import TYPE_CHECKING

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands


# Local application imports
from main.cogs.utils.context import Context


if TYPE_CHECKING:
    from main.Zen import Zen

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                        Meta Cog
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Meta(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot = bot

    @commands.command()
    async def ping(self, ctx: Context) -> None:
        """Ping commands are stupid."""
        await ctx.send("Ping commands are stupid.")
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen) -> None:
    await bot.add_cog(Meta(bot))
