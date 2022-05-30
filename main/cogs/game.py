# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
from datetime import datetime
import logging
import re

from typing import TYPE_CHECKING, Any, Optional, TypedDict
from unicodedata import category

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands
from discord.ext.commands.view import StringView


# Local application imports
from main.cogs.utils.paginator import TabularPages

if TYPE_CHECKING:
    from main.Zen import Zen
    from main.cogs.utils.context import Context


log = logging.getLogger(__name__)
NOT_ENABLED = '`Error - System Not Enabled.`'
SYSTEM = 'game'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Game
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class StringMemberTransformer(app_commands.Transformer):
    @classmethod
    async def transform(
            cls, interaction: discord.Interaction, value: str
    ) -> list[discord.Member]:
        view = StringView(value)
        result = []
        ctx: Context = await commands.Context.from_interaction(interaction)
        ctx.current_parameter = str

        while True:
            view.skip_ws()
            ctx.current_argument = arg = view.get_quoted_word()
            if arg is None:
                break

            # This propagates the exception
            converted = await commands.converter.run_converters(
                ctx, commands.converter.MemberConverter, arg, str)
            result.append(converted)

        return result


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Game
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Game(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #               App Commands Settings
    game_group = app_commands.Group(
        name='game', description='Commands related to running a game on the server.')

    # __________________ Game Enabled __________________
    # __________________ Game Enabled __________________
    # __________________ Game Enabled __________________

    channels_group = app_commands.Group(
        name='channel',
        description='Commands related to managing game channels.',
        parent=game_group
    )

    # _________________ Create Channel _________________
    @channels_group.command(name='create')
    @app_commands.describe(name="Name of the channel.")
    async def create_game_channel(
        self,
        interaction: discord.Interaction,
        name: str
    ) -> None:
        """Creates a game channel."""
        # Defer
        await interaction.response.defer()

        # Validation
        if not await self._get_game_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        # Data Builder
        conn = self.bot.pool
        guild = interaction.guild
        member = interaction.user

        # Get game category
        game_category, channel_limit = await self._get_game_settings(guild)

        try:
            sql = '''SELECT channels FROM game_channels
                     WHERE server_id=$1 AND user_id=$2'''
            res = await conn.fetchrow(sql, guild.id, member.id)

        except Exception:
            log.error('Error while getting channels.', exc_info=True)
            return await interaction.edit_original_message(content='Error')

        channels: set[int] = set(res['channels']) if res is not None else set()
        if len(channels) >= channel_limit:
            return await interaction.edit_original_message(
                "You've reached the max limit of game channels that you can own.")

        # Sanitize name
        name = re.sub(r'[^0-9a-zA-Z ]+', '',
                      name.lower().replace(' ', '-')[:20])

        # Text Channel Perms
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(
                read_messages=True,
                manage_messages=True,
                manage_threads=True,
                mention_everyone=False,
            )
        }

        channel = await guild.create_text_channel(
            name=name, overwrites=overwrites, category=game_category
        )

        channels.add(channel.id)

        try:
            sql = '''INSERT INTO game_channels(server_id, user_id, channels)
                     VALUES($1, $2, $3)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET channels=$3'''
            await conn.execute(sql, guild.id, member.id, list(channels))
        except Exception:
            log.error('Error while updating channels in db.', exc_info=True)
            return

        return await interaction.edit_original_message(
            content=f'Successfully set up Play Channels. {channel.mention}'
        )

    # __________________ Game Enabled __________________
    @channels_group.command(name='delete')
    @app_commands.describe(channel='Name of the channel.')
    async def delete_game_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ) -> None:
        """Deletes a game channel."""
        await interaction.response.defer()

        # Validation
        if not await self._get_game_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        # Data Builder
        conn = self.bot.pool
        guild = interaction.guild
        member = interaction.user
        is_admin = member.guild_permissions.administrator
        is_moderator = member.guild_permissions.moderate_members

        # Get game category
        category, _ = await self._get_game_settings(guild)

        # Get channels
        try:
            sql = '''SELECT channels FROM game_channels
                     WHERE server_id=$1 AND user_id=$2'''
            res = await conn.fetchrow(sql, guild.id, member.id)
        except Exception:
            log.error('Error while getting channels.', exc_info=True)
            return await interaction.edit_original_message(content='Error')

        channels: set[int] = set(res['channels']) if res is not None else set()

        # Sanity check
        if category.id != channel.category_id:
            return await interaction.edit_original_message(
                content='`Error: Channel is not part of game category.'
            )

        # Check if channel is owned or admin
        if channel.id not in channels and not (is_admin or is_moderator):
            return await interaction.edit_original_message(
                content="`Error: This channel doesn't belong to you.`"
            )

        channels.remove(channel.id)

        # Update db
        try:
            sql = '''INSERT INTO game_channels(server_id, user_id, channels)
                     VALUES($1, $2, $3)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET channels=$3'''
            await conn.execute(sql, guild.id, member.id, list(channels))
        except Exception:
            log.error('Error while updating channels.', exc_info=True)
            return await interaction.edit_original_message(content='Error')

        msg = f'Successfully deleted ${channel.name}.'
        await interaction.edit_original_message(content=msg)
        await channel.delete()

        return

    # __________________ Add Users to Game Channel __________________
    @channels_group.command(name='add')
    @app_commands.describe(channel='Add to channel.', users='List of users.')
    async def add_to_game_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        users: app_commands.Transform[list[discord.Member], StringMemberTransformer],
    ) -> None:
        """Adds users to a game channel."""

        # Defer Response
        await interaction.response.defer()

        # Validation
        if not await self._get_game_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        # Data Builder
        conn = self.bot.pool
        guild = interaction.guild
        member = interaction.user
        is_admin = member.guild_permissions.administrator
        is_moderator = member.guild_permissions.moderate_members

        # Get Category
        category, _ = await self._get_game_settings(guild)

        # Sanity check
        if category.id != channel.category_id:
            return await interaction.edit_original_message(
                content='`Error: Channel is not part of game category.'
            )

        # Get channels
        try:
            sql = '''SELECT channels FROM game_channels
                     WHERE server_id=$1 AND user_id=$2'''
            res = await conn.fetchrow(sql, guild.id, member.id)
        except Exception:
            log.error('Error while getting channels.', exc_info=True)
            return await interaction.edit_original_message(content='Error')

        channels: set[int] = set(res['channels']) if res is not None else set()

        # Check if channel is owned or admin
        if channel.id not in channels and not (is_admin or is_moderator):
            return await interaction.edit_original_message(
                content="`Error: This channel doesn't belong to you.`"
            )

        # Add users to channel
        overwrites = channel.overwrites
        new_overwrites = {
            u: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            ) for u in users}

        overwrites.update(new_overwrites)
        print(overwrites)

        await channel.set_permissions(permissions=overwrites)

        msg = f"Added {', '.join([u.display_name for u in users])} to {channel.mention}"

        return await interaction.edit_original_message(content=msg)

    # __________________ Remove Users from Game Channel __________________
    @channels_group.command(name='remove')
    @app_commands.describe(channel='Remove from channel.', users='List of users.')
    async def remove_from_game_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        users: app_commands.Transform[list[discord.Member], StringMemberTransformer],
    ) -> None:
        """Removes users from a game channel."""

        # Defer Response
        await interaction.response.defer()

        # Validation
        if not await self._get_game_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        # Data Builder
        conn = self.bot.pool
        guild = interaction.guild
        member = interaction.user
        is_admin = member.guild_permissions.administrator
        is_moderator = member.guild_permissions.moderate_members

        # Get Category
        category, _ = await self._get_game_settings(guild)

        # Sanity check
        if category.id != channel.category_id:
            return await interaction.edit_original_message(
                content='`Error: Channel is not part of game category.'
            )

        # Get channels
        try:
            sql = '''SELECT channels FROM game_channels
                     WHERE server_id=$1 AND user_id=$2'''
            res = await conn.fetchrow(sql, guild.id, member.id)
        except Exception:
            log.error('Error while getting channels.', exc_info=True)
            return await interaction.edit_original_message(content='Error')

        channels: set[int] = set(res['channels']) if res is not None else set()

        # Check if channel is owned or admin
        if channel.id not in channels and not (is_admin or is_moderator):
            return await interaction.edit_original_message(
                content="`Error: This channel doesn't belong to you.`"
            )

        # Remove users from channel
        overwrites = channel.overwrites

        for u in users:
            overwrites.pop(u)

        print(overwrites)

        await channel.set_permissions(permissions=overwrites)

        msg = f"Removed {', '.join([u.display_name for u in users])} to {channel.mention}"

        return await interaction.edit_original_message(content=msg)

    # __________________ Game Enabled __________________
    # __________________ Game Enabled __________________
    events_group = app_commands.Group(
        name='event',
        description='Commands related to managing game events.',
        parent=game_group
    )

    # __________________ Game Enabled __________________
    # __________________ Game Enabled __________________
    # __________________ Game Enabled __________________
    # __________________ Game Enabled __________________
    async def _get_game_settings(
        self, guild: discord.Guild
    ) -> tuple[discord.CategoryChannel, int]:
        try:
            conn = self.bot.pool
            sql = '''SELECT game_category, game_channels_limit FROM settings
                     WHERE server_id=$1'''
            res = await conn.fetchrow(sql, guild.id)

            if res is None:
                raise ValueError

            category: discord.CategoryChannel = guild.get_channel(
                res['game_category'])
            limit: int = res['game_channels_limit']

            return (category, limit)

        except Exception:
            log.error('Error while getting game settings.', exc_info=True)
            return

    # __________________ Game Enabled __________________
    @alru_cache(maxsize=128)
    async def _get_game_enabled(self, server_id: int) -> Optional[bool]:
        # Get pool
        conn = self.bot.pool

        try:
            sql = 'SELECT enable_game FROM settings WHERE server_id=$1'
            res = await conn.fetchrow(sql, server_id)

            if res is not None:
                return res['enable_game']
            else:
                return None

        except Exception:
            log.error('Error while checking enabled game.', exc_info=True)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Game(bot))
