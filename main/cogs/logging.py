# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging
import re

from itertools import zip_longest
from typing import TYPE_CHECKING, Optional

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord.ext import commands


# Local application imports
from main.cogs.utils.formats import text_color


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context


log = logging.getLogger(__name__)


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
    #                  Message Create
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Validation
        if message.guild is None:
            return

        if message.author.bot or not message.type == discord.MessageType.default:
            return

        # Data builder
        conn = self.bot.pool
        guild = message.guild.id
        member = message.author.id
        channel = message.channel.id

        try:
            sql = '''INSERT INTO logger (server_id, user_id, channel_id, last_msg, msg_count)
                     VALUES ($1, $2, $3, $4, $5)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET channel_id=$3,
                                   last_msg=$4,
                                   msg_count=logger.msg_count + $5
            '''
            await conn.execute(sql, guild, member, channel, discord.utils.utcnow(), 1)
        except Exception:
            log.error('Error while logging message.', exc_info=True)

    # --------------------------------------------------
    #                  Message delete
    @commands.Cog.listener(name='on_message_delete')
    async def on_message_delete(self, msg: discord.Message) -> None:
        if msg.guild is None:
            return

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
                        value=text_color(f'{author.name} - {author.id}', 'red'), inline=False)
            e.add_field(name='Channel',
                        value=text_color(original_channel.name, 'red'), inline=False)

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
    #                    Message Edit
    @commands.Cog.listener(name="on_message_edit")
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        # Validation
        if before.guild is None or after.guild is None:
            return

        if (before.author.bot) or (before.content == after.content):
            return

        channel_id = await self._get_logging_channel(before.guild.id)
        if channel_id is None:
            return

        # Databuilder
        author = before.author
        guild = before.guild
        original_channel = before.channel
        old_content = before.content.replace('@', '@\u200b')
        new_content = after.content.replace('@', '@\u200b')
        pre_attachments = before.attachments
        post_attachments = after.attachments
        log_channel = guild.get_channel(channel_id)

        if pre_attachments != []:
            pre_attachments = [x.proxy_url for x in pre_attachments]
        if post_attachments != []:
            post_attachments = [x.proxy_url for x in post_attachments]

        try:
            o_content_array = [old_content[i:i+1000]
                               for i in range(0, len(old_content), 1000)]
            n_content_array = [new_content[i:i+1000]
                               for i in range(0, len(new_content), 1000)]

            out_content = list(zip_longest(
                o_content_array, n_content_array, fillvalue='...'))

            embeds = list()
            auth = text_color(f'{author.name} - {author.id}', 'orange')
            chn = text_color(original_channel.name, 'orange')

            for idx, (old, new) in enumerate(out_content):
                title = f"Edited Message Log {'' if idx == 0 else '- ' + str(idx) }"
                e = discord.Embed(title=title, color=discord.Color.orange())

                e.add_field(name='Author', value=auth, inline=True)
                e.add_field(name='Channel', value=chn, inline=True)
                e.add_field(name='Prev Content', value=f'{old}', inline=False)
                e.add_field(name='New Content', value=f'{new}', inline=False)

                e.timestamp = before.edited_at

                embeds.append(e)

            await log_channel.send(embeds=embeds)

        except Exception:
            log.error('Error while logging edited message', exc_info=True)

    # --------------------------------------------------
    #                  On Member Update
    @commands.Cog.listener(name='on_member_update')
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        # Validate
        if before.guild is None or after.guild is None:
            return

        if before.bot or (before.nick == after.nick):
            return

        channel_id = await self._get_logging_channel(before.guild.id)
        if channel_id is None:
            return

        # Databuilder
        old_nick = text_color(before.nick, 'blue')
        new_nick = text_color(after.nick, 'blue')
        log_channel = self.bot.get_channel(channel_id)

        e = discord.Embed(title=f'{before.name}', colour=discord.Colour.blue())
        e.add_field(name='UserID', value=text_color(
            before.id, 'blue'), inline=False)
        e.add_field(name='Old Nickname', value=old_nick)
        e.add_field(name='Old Nickname', value=new_nick)
        e.timestamp = discord.utils.utcnow()

        await log_channel.send(embed=e)

    # --------------------------------------------------
    #                    Leave Logging
    @commands.Cog.listener(name='on_member_remove')
    async def on_member_remove(self, member: discord.Member) -> None:
        # Validation
        if member.guild is None:
            return

        channel_id = await self._get_logging_channel(member.guild.id)
        if channel_id is None:
            return

        log_channel = self.bot.get_channel(channel_id)

        e = discord.Embed(
            title=f'{member.name}#{member.discriminator}', color=discord.Color.red())
        e.description = f':outbox_tray: {member.mention} **has left the guild.**'
        if member.display_avatar:
            e.set_thumbnail(url=member.display_avatar)
        e.set_footer(text=f'ID: {member.id}')
        e.timestamp = discord.utils.utcnow()

        await log_channel.send(embed=e)

    # --------------------------------------------------
    #                     Ban Logging
    @commands.Cog.listener(name='on_member_ban')
    async def on_member_ban(
        self, guild: discord.Guild, user: discord.User | discord.Member
    ) -> None:
        # Validation
        channel_id = await self._get_logging_channel(guild.id)
        if channel_id is None:
            return

        log_channel = self.bot.get_channel(channel_id)

        e = discord.Embed(
            title=f'{user.name}#{user.discriminator}', color=discord.Color.red())
        e.description = f':outbox_tray: {user.mention} **has left the guild.**'
        e.set_thumbnail(url=user.avatar.url)
        e.set_footer(text=f'ID: {user.id}')
        e.timestamp = discord.utils.utcnow()

        await log_channel.send(embed=e)

    # --------------------------------------------------
    #                  Unban Logging
    @commands.Cog.listener(name='on_member_unban')
    async def on_member_unban(
        self, guild: discord.Guild, user: discord.User | discord.Member
    ) -> None:
        # Validation
        channel_id = await self._get_logging_channel(guild.id)
        if channel_id is None:
            return

        log_channel = self.bot.get_channel(channel_id)

        e = discord.Embed(
            title=f'{user.name}#{user.discriminator}', color=discord.Color.red())
        e.description = f':outbox_tray: {user.mention} **has left the guild.**'
        e.set_thumbnail(url=user.avatar.url)
        e.set_footer(text=f'ID: {user.id}')
        e.timestamp = discord.utils.utcnow()

        await log_channel.send(embed=e)

    # --------------------------------------------------
    #                  Get Logging Channel

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
