# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging
import re

from typing import TYPE_CHECKING, Optional

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord.ext import commands


# Local application imports
from main.cogs.utils.formats import format_dt


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

        if re.search(regex, msg.content) or msg.author.bot or len(msg.content) < 3:
            return

        channel_id = await self._get_logging_channel(msg.guild.id)
        if channel_id is None:
            return

        # Vars
        author = msg.author
        original_channel = msg.channel
        content = msg.content.replace('@', '@\u200b')
        guild = msg.guild
        attachments = msg.attachments
        log_channel = guild.get_channel(channel_id)

        if attachments != []:
            attachments = [x.proxy_url for x in attachments]

        try:
            contentArray = [content[i:i+1000]
                            for i in range(0, len(content), 1000)]

            e = discord.Embed(title='Deleted Message Log',
                              colour=discord.Colour.red())
            e.add_field(name='Author',
                        value=f'```{author.name} - {author.id}```', inline=False)
            e.add_field(name='Channel',
                        value=f'```{original_channel.name}```', inline=False)

            if attachments != []:
                e.add_field(name='Attachments', value='\n'.join(attachments))

            for c in contentArray:
                e.add_field(name='Content', value=f'{c}', inline=False)

            e.set_footer(text=f'Created at ')
            e.timestamp = msg.created_at

            await log_channel.send(embed=e)

        except Exception:
            log.error('Error while logging delete message', exc_info=True)

    # --------------------------------------------------
    #                  Get Logging Channel

    @alru_cache(maxsize=128)
    async def _get_logging_channel(self, server_id: int) -> Optional[int]:
        # Get pool
        conn = self.bot.pool

        # Return channel_id
        try:
            sql = 'SELECT logging_channel FROM settings WHERE server_id=$1'
            res = await conn.fetchrow(sql, server_id)

            if res is not None:
                return res['logging_channel']
            else:
                return None

        except Exception:
            log.error('Error while fetching log channel.', exc_info=True)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen):
    await bot.add_cog(Logging(bot))
