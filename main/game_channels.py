# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
from datetime import datetime
import logging
import random
import re

from typing import TYPE_CHECKING, Optional, TypedDict

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands


# Local application imports
from main.cogs.utils.paginator import TabularPages

if TYPE_CHECKING:
    from main.Zen import Zen
    from main.cogs.utils.context import Context


log = logging.getLogger(__name__)
NOT_ENABLED = 'Error - System Not Enabled.'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          XP
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Game(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #               App Commands Settings
    game_group = app_commands.Group(
        name='game', description='Commands related to running a game on the server.')

    channels_group = app_commands.Group(
        name='channel',
        description='Commands related to managing game channels.',
        parent=game_group
    )

    events_group = app_commands.Group(
        name='event',
        description='Commands related to managing game events.',
        parent=game_group
    )


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen):
    await bot.add_cog(Game(bot))
