#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations
import re

# Standard library imports
import logging

from typing import TYPE_CHECKING

# Third party imports
import discord
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands

# Local application imports
from main.cogs.utils.context import Context

if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          XP
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Hashtag(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.message.guild is not None

    @commands.Cog.listener(name='on_message')
    async def on_message(self, message: discord.Message) -> None:

        if message.guild is None:
            return

        # Data builder
        guild = message.guild
        channel = message.channel
        content = message.content
        member = message.author
        hashtags = await self._get_hashtags(guild)

        # TODO: Add exceptions
        exceptions = list()

        if channel.id not in hashtags:
            return

        if member.id == self.bot.user.id:
            return

        # Check content
        found = re.search(r'\[.*?\]', content)

        if found is None:
            e = discord.Embed(
                title='Error',
                description='Please add relevant tags to your post.',
                color=discord.Colour.red())

            await message.delete(delay=15)
            await message.channel.send(embed=e, reference=message.to_reference(), delete_after=15)

        return

    # --------------------------------------------------
    #               App Commands Settings
    hashtag_group = app_commands.Group(
        name='hashtag', description='Hashtag Commands.')

    @hashtag_group.command(name='require')
    @app_commands.describe(channel='Selected Channel', enable='Enable / Disable')
    async def restrict(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        enable: bool
    ) -> None:
        """ Require content posted in a channel to have hashtags. """
        # Defer
        await interaction.response.defer()

        # Data builder
        conn = self.bot.pool
        guild = interaction.guild
        member = interaction.user

        # Admin Check
        if not member.guild_permissions.administrator:
            return await interaction.edit_original_message(
                content='`Error: Insufficient permissions.`'
            )

        # Get hashtags
        hashtags = await self._get_hashtags(guild)

        if enable:
            hashtags.add(channel.id)
        else:
            hashtags.remove(channel.id)

        # Update db
        try:
            sql = '''UPDATE settings SET 
                     hashtags=$2 WHERE server_id=$1'''
            await conn.execute(sql, guild.id, list(hashtags))
        except Exception:
            log.error('Error while updating hashtags.', exc_info=True)
            return interaction.edit_original_message(content='Error')

        # Clear cache
        self._get_hashtags.cache_clear()

        state = 'now' if enable else 'no longer'
        msg = f'Channel {state} requires ` [ tag ] `.'
        return await interaction.edit_original_message(content=msg)

    # ______________________ Get Hashtags _______________________
    @alru_cache(maxsize=72)
    async def _get_hashtags(self, guild) -> set[int]:
        """ Get hashtags of a server"""
        try:
            conn = self.bot.pool
            sql = ''' SELECT hashtags FROM settings
                      WHERE server_id=$1'''
            res = await conn.fetchrow(sql, guild.id)

            if res is None:
                raise ValueError

            return set(res['hashtags'])

        except Exception:
            log.error('Error while fetching hashtag channels', exc_info=True)
            return set()


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen) -> None:
    await bot.add_cog(Hashtag(bot))
