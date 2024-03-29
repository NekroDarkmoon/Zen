# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging
from typing import TYPE_CHECKING, Literal, Optional

# Third party imports
import discord  # noqa

from discord import app_commands
from discord.ext import commands

# Local application imports


if TYPE_CHECKING:
    from asyncpg import Pool
    from main.Zen import Zen
    from utils.context import Context
    from main.cogs.loggingCog import LoggingCog
    from main.cogs.xp import XP
    from main.cogs.rep import Rep
    from main.cogs.game import Game


log = logging.getLogger(__name__)
GuildWritableChannels = discord.TextChannel | discord.CategoryChannel | discord.ForumChannel | discord.Thread  # type: ignore


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
#                  Create Settings Instance
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def create_settings_instance(pool: Pool, guild: discord.Guild) -> None:
    """Create a settings instance for a guild."""
    try:
        sql = '''INSERT INTO settings(server_id, owner_id)
                                     VALUES($1, $2)
              '''
        await pool.execute(sql, guild.id, guild.owner_id)
    except Exception:
        log.error('Unable to create guild settings', exc_info=True)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Settings
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Settings(commands.Cog):
    """Settings for the bot."""

    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #               App Commands Settings
    settings_group = app_commands.Group(name='settings', description='Server settings for the bot')

    @commands.group()
    async def settings(self, ctx: Context) -> None:
        """Settings Group for the settings command"""
        if not ctx.invoked_subcommand:
            return await ctx.send_help(self)

    # __________________ Logging Channel  _____________________
    @settings_group.command(name='loggingchannel')
    @app_commands.describe(channel='Selected Channel', value='On or Off')
    async def loggingchannel(self, interaction: discord.Interaction, channel: discord.TextChannel, value: bool) -> None:
        """
        Set the logging channel for this server.
        """
        # Defer interaction
        await interaction.response.defer()

        # Update database
        conn = self.bot.pool

        # Check if exists
        await self._check_existence(interaction.guild)

        # Update
        try:
            chn: Optional[int] = channel.id if value else None
            sql = ''' UPDATE settings SET logging_channel=$2
                      WHERE server_id=$1'''
            await conn.execute(sql, interaction.guild_id, chn)

        except Exception:
            log.error('Database query error.', exc_info=True)

        # Update Cache
        cog: Optional[LoggingCog] = self.bot.get_cog('LoggingCog')  # type: ignore
        if cog is not None:
            cog._get_logging_channel.cache_clear()
        else:
            log.error(f'Cog not found - {cog}.', exc_info=True)

        # Send Update
        if value:
            msg = f'Logging channel set to {channel.mention}.'
        else:
            msg = 'Logging Channel Unset.'

        await interaction.edit_original_response(content=msg)

    # __________________ Enable Leveling  _____________________
    @settings_group.command(name='enablexp')
    @app_commands.describe(choice='On or Off')
    async def enable_levels(self, interaction: discord.Interaction, choice: bool) -> None:
        """Enable the leveling system for this guild."""
        # Defer
        await interaction.response.defer()
        conn = self.bot.pool

        # Check if exists
        await self._check_existence(interaction.guild)

        # Update
        try:
            sql = ''' UPDATE settings SET enable_leveling=$2
                      WHERE server_id=$1'''
            await conn.execute(sql, interaction.guild_id, choice)

        except Exception:
            log.error('Error while updating xp settings.', exc_info=True)
            return

        # Update Cache
        cog: Optional[XP] = self.bot.get_cog('XP')  # type: ignore
        if cog is not None:
            cog._get_xp_enabled.cache_clear()
        else:
            log.error(f'Cog not found - {cog}.', exc_info=True)
            return

        # Send Update
        if choice:
            msg = 'XP system is now enabled'
        else:
            msg = 'XP system is now disabled.'

        await interaction.edit_original_response(content=msg)

    # _________________ Enable Reputation  _____________________
    @settings_group.command(name='enablerep')
    @app_commands.describe(choice='On or Off')
    async def enable_rep(self, interaction: discord.Interaction, choice: bool) -> None:
        """Enable the reputation system for this guild."""
        # Defer
        await interaction.response.defer()
        conn = self.bot.pool

        # Check if exists
        await self._check_existence(interaction.guild)

        # Update
        try:
            sql = '''UPDATE settings SET enable_rep=$2
                      WHERE server_id=$1'''
            await conn.execute(sql, interaction.guild_id, choice)

        except Exception:
            log.error('Error while updating rep settings.', exc_info=True)
            return

        # Update Cache
        cog: Optional[Rep] = self.bot.get_cog('Rep')  # type: ignore
        if cog is not None:
            cog._get_rep_enabled.cache_clear()
        else:
            log.error(f'Cog not found - {cog}.', exc_info=True)
            return

        # Send Update
        if choice:
            msg = 'Rep system is now enabled'
        else:
            msg = 'Rep system is now disabled.'

        await interaction.edit_original_response(content=msg)

    # _____________ Exclude Channels Rep  _____________________
    @commands.command(name='exclude_rep')
    @commands.has_permissions(administrator=True)
    async def exclude_rep(
        self,
        ctx: Context,
        action: Literal['add', 'remove', 'list'],
        channels: commands.Greedy[discord.TextChannel | discord.CategoryChannel | discord.ForumChannel],
    ) -> None:
        """Disable rep in certain channels

        Usage: `exclude_rep <add | remove | list> ["channel..."]`
        """
        # Data builder
        conn = self.bot.pool
        guild = ctx.guild
        channel_ids = {c.id for c in channels}

        # Check if exists
        await self._check_existence(guild)

        # Update db
        try:
            sql = '''SELECT excluded_rep_channels FROM settings WHERE server_id=$1'''
            res = await conn.fetchrow(sql, guild.id)

            if res is None:
                log.error('Error while excluding channels.', exc_info=True)

            existing_channels = set(res['excluded_rep_channels'])

            if action == 'add':
                channel_ids = channel_ids.union(existing_channels)

            elif action == 'remove':
                channel_ids = existing_channels.difference(channel_ids)

            elif action == 'list':
                mentions = [self.bot.get_channel(c).mention for c in existing_channels]

                msg = f"Rep can't be gained in the following channels: {', '.join( mentions)}"
                await ctx.reply(content=msg)
                return

            else:
                return

            sql = '''UPDATE settings 
                     SET excluded_rep_channels=$2
                     WHERE server_id=$1'''
            await conn.execute(sql, guild.id, list(channel_ids))

        except Exception:
            log.error('Error while excluding channels.', exc_info=True)

        # Update Cache
        cog: Optional[Rep] = self.bot.get_cog('Rep')  # type: ignore
        if cog is not None:
            cog._get_excluded_channels.cache_clear()
        else:
            log.error(f'Cog not found - {cog}.', exc_info=True)
            return

        await ctx.reply('Updated Excluded Channels.')
        return

    # ________________ Enable Game System  ___________________
    @settings_group.command(name='enablegame')
    @app_commands.describe(choice='On or Off')
    async def enable_game(
        self, interaction: discord.Interaction, choice: bool, category: discord.CategoryChannel, max_channels: Optional[int]
    ) -> None:
        """Enable the game system for this guild."""
        # Defer
        await interaction.response.defer()
        conn = self.bot.pool

        # Check if exists
        await self._check_existence(interaction.guild)

        # Update
        try:
            sql = f'''UPDATE settings 
                     SET enable_game=$2,
                         game_category=$3
                        {",game_channels_limit=$4" if max_channels is not None else ""}
                     WHERE server_id=$1'''
            if max_channels is None:
                await conn.execute(sql, interaction.guild_id, choice, category.id)
            else:
                await conn.execute(sql, interaction.guild_id, choice, category.id, max_channels)

        except Exception:
            log.error('Error while updating game settings.', exc_info=True)
            return

        # Update Cache
        cog: Optional[Game] = self.bot.get_cog('Game')
        if cog is not None:
            cog._get_game_enabled.cache_clear()
        else:
            log.error(f'Cog not found - {cog}.', exc_info=True)
            return

        # Send Update
        if choice:
            msg = 'Game system is now enabled'
        else:
            msg = 'Game system is now disabled.'

        await interaction.edit_original_response(content=msg)

    role_rewards_group = app_commands.Group(
        name='rewards', description='Set up role rewards for different systems.', parent=settings_group
    )

    # ____________________ Create Reward  _____________________
    @role_rewards_group.command(name='set')
    @app_commands.describe(
        system='Select the system for which the reward is awarded.',
        role='Selected role for reward.',
        value='Value for when reward is awarded.',
    )
    async def set_role_rewards(
        self, interaction: discord.Interaction, system: Literal['Rep', 'XP'], role: discord.Role, value: int
    ) -> None:
        """Set a role as a reward."""
        # Defer
        await interaction.response.defer()

        # Check if exists
        await self._check_existence(interaction.guild)

        # Data builder
        conn = self.bot.pool
        guild = interaction.guild

        try:
            sql = '''INSERT INTO rewards (server_id, role_id, type, val)
                     VALUES ($1, $2, $3, $4)
                     ON CONFLICT (server_id, role_id, type)
                     DO UPDATE SET val=$4
            '''
            await conn.execute(sql, guild.id, role.id, system.lower(), value)

            msg = f'`{role.name}` has been set as a reward for the `{system}` system.'
            await interaction.edit_original_response(content=msg)

        except Exception:
            log.error('Error while setting role reward.', exc_info=True)

    # ____________________ Remove Reward  _____________________
    @role_rewards_group.command(name='remove')
    @app_commands.describe(system='Select the system for the reward.', role='Selected role ro remove.')
    async def remove_role_rewards(self, interaction: discord.Interaction, system: Literal['Rep', 'XP'], role: discord.Role):
        """ "Remove a role as a reward."""
        # Defer
        await interaction.response.defer()

        # Check if exists
        await self._check_existence(interaction.guild)

        # Data builder
        conn = self.bot.pool
        guild = interaction.guild

        try:
            sql = '''DELETE FROM rewards 
                    WHERE EXISTS
                        (SELECT val FROM rewards 
                        WHERE server_id=$1 AND role_id=$2 AND type=$3)
            '''
            await conn.execute(sql, guild.id, role.id, system.lower())

            msg = f'`{role.name}` has been removed as a reward for the `{system}` system.'
            await interaction.edit_original_response(content=msg)

        except Exception:
            log.error('Error while setting role reward.', exc_info=True)

    # ________________ Check Guild Data  ___________________
    async def _check_existence(self, guild: discord.Guild | None) -> None:
        if not guild:
            return

        # Check if exists
        conn = self.bot.pool
        try:
            sql = '''SELECT * FROM settings WHERE server_id=$1'''
            res = await conn.fetchrow(sql, guild.id)

            if res is None:
                await create_settings_instance(conn, guild)

        except Exception:  # pylint: disable=broad-except
            log.error('Database query error.', exc_info=True)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    """Load the Settings cog."""
    await bot.add_cog(Settings(bot))
