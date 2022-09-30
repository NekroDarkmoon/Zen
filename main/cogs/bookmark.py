# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations
from email import message

# Standard library imports
import logging

from datetime import datetime
from typing import TYPE_CHECKING, Optional

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands


# Local application imports
from main.cogs.utils import formats, time

if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context


log = logging.getLogger(__name__)
NOT_ENABLED = '`Error - System Not Enabled.`'
SYSTEM = 'bookmark'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          XP
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Bookmark(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    async def cog_check(self, ctx: Context) -> bool:
        return False if ctx.guild is None else True

    # ______________________ Listeners _______________________
    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent
    ):

        # TODO: Uncomment
        # if not await self._get_bookmark_enabled(reaction.message.guild.id):
        #     return

        if payload.guild_id is None:
            if payload.emoji.name == '\N{CROSS MARK}':
                await self._delete_bookmark_message(
                    payload.message_id, payload.user_id
                )
            return

        if payload.emoji.name != '\N{BOOKMARK}':
            return

        # Fetch message
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        member = payload.member

        await self._handle_reaction(message, member)

    async def _handle_reaction(
        self,
        message: discord.Message,
        member: discord.Member
    ) -> None:
        # Data builder
        author = message.author
        e = discord.Embed(title='Message',
                          colour=discord.Colour.random())
        e.description = message.content

        for a in message.attachments:
            e.add_field(name='Attachment', value=a, inline=False)

        if len(message.attachments) == 1:
            e.set_image(url=message.attachments[0])

        e.url = message.to_reference().jump_url
        e.timestamp = message.created_at
        e.set_author(name=author, icon_url=author.display_avatar)

        content = f'Bookmark Created: {time.format_dt(datetime.utcnow(), "F")}'
        content += f'\n{message.jump_url}'

        sent_msg = await member.send(content=content, embed=e)

        # Add delete reaction
        await sent_msg.add_reaction('\N{CROSS MARK}')

    async def _delete_bookmark_message(
        self,
        message_id: int,
        user_id: int
    ):
        user: discord.User = await self.bot.fetch_user(user_id)
        message: discord.Message = await user.fetch_message(message_id)

        # Delete message
        await message.delete()

    # _______________ Bookmark Enabled  __________________
    @alru_cache(maxsize=128)
    async def _get_bookmark_enabled(self, server_id: int) -> Optional[bool]:
        # Get pool
        conn = self.bot.pool

        try:
            sql = 'SELECT enable_bookmark FROM settings WHERE server_id=$1'
            res = await conn.fetchrow(sql, server_id)

            if res is not None:
                return res['enable_bookmark']
            else:
                return None

        except Exception:
            log.error('Error while checking enable bookmark.', exc_info=True)
            return None

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen):
    await bot.add_cog(Bookmark(bot))
