#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging

from typing import TYPE_CHECKING

# Third party imports
import discord

from discord.ext import commands

if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = (
    discord.TextChannel
    | discord.VoiceChannel
    | discord.StageChannel
    | discord.CategoryChannel
    | discord.Thread
)

log = logging.getLogger("__name__")


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Exandria(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild.id in [719063399148814418, 739684323141353597]


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen) -> None:
    await bot.add_cog(Exandria(bot))
