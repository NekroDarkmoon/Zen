# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging
import re
from typing import TYPE_CHECKING

# Third party imports
import discord  # noqa
from discord import utils
from discord.ext import commands

# Local application imports


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context


log = logging.getLogger(__name__)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Config
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Config
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Config
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Config
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Logging
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Logging(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #                  Message delete
    @commands.Cog.listener(name='on_message_delete')
    async def on_message_delete(self, msg: discord.Message) -> None:
        # Validation
        regex = "^[^\"\'\.\w]"  # noqa

        if re.search(regex, msg.content) or msg.author.bot or len(msg.content < 3):
            return

        # Vars
        author = msg.author
        original_channel = msg.channel
        content = msg.content
        guild = msg.guild
        attachments = msg.attachments

        if attachments != []:
            attachments = [x.proxy_url for x in attachments]


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen):
    await bot.add_cog(Logging(bot))
