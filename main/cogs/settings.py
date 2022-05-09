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
#                  Create Settings Instance
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def create_settings_instance(pool: Pool, server_id: int) -> None:

    ...


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Settings
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Settings(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #               App Commands Settings
    settings_group = app_commands.Group(
        name='settings', description='Server settings for the bot')

    @commands.group()
    async def settings(self, ctx: Context) -> None:
        if not ctx.invoked_subcommand:
            return await ctx.send_help(self)

    # __________________ Logging Channel  _____________________
    @settings_group.command(name='loggingchannel')
    @app_commands.describe(channel='Selected Channel', value='On or Off')
    async def loggingchannel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        value: bool
    ) -> None:
        """
        Set the logging channel for this server.
        """
        # Defer interaction
        interaction.response.defer()

        # Update database
        conn = self.bot.pool

        # Check if exists
        try:
            sql = '''SELECT * FROM settings WHERE server_id=$1'''
            res = await conn.fetchrow(sql, interaction.guild_id)
        except Exception:
            log.error('Database query error.', exc_info=True)

        if res is None:
            create_settings_instance(conn, interaction.guild_id)

        # Update
        try:
            chn: Optional[int] = channel.id if value else None
            sql = ''' UPDATE settings SET logging_channel=$2
                      WHERE server_id=$1'''
            await conn.execute(sql, interaction.guild_id, chn)

        except Exception:
            log.error('Database query error.', exc_info=True)

        # TODO: Update Cache

        # Send Update
        if value:
            msg = f'Logging channel set to {channel.mention}.'
        else:
            msg = 'Logging Channel Unset.'

        interaction.response.edit_message(msg)

    # __________________ Enable Leveling  _____________________
    @settings_group.command(name='enablexp')
    @app_commands.describe(choice='On or Off')
    async def enable_levels(self, interaction: discord.Interaction, choice: bool) -> None:
        """Enable the leveling system for this guild."""
        pass

    # _________________ Enable Reputation  _____________________

    @settings_group.command(name='enablerep')
    @app_commands.describe(choice='On or Off')
    async def enable_rep(self, interaction: discord.Interaction, choice: bool) -> None:
        """Enable the reputation system for this guild."""
        ...

     # ________________ Enable Playchannels  ___________________
    @settings_group.command(name='enableplaychns')
    @app_commands.describe(choice='On or Off')
    async def enable_playchannels(self, interaction: discord.Interaction, choice: bool) -> None:
        """Enable the play channel system for this guild."""
        ...

    role_rewards_group = app_commands.Group(
        name='rewards',
        description='Set up role rewards for different systems.',
        parent=settings_group
    )

    # ____________________ Create Reward  _____________________

    @role_rewards_group.command(name='set')
    @app_commands.describe(
        system='Select the system for which the reward is awarded.',
        target='Selected role for reward.',
        value='Value for when reward is awarded.')
    async def set_role_rewards(
        self,
        interaction: discord.Interaction,
        system: Literal['Rep', 'Xp'],
        target: discord.Role,
        value: int
    ) -> None:
        """Set a role as a reward."""
        ...

    # ____________________ Remove Reward  _____________________

    @role_rewards_group.command(name='remove')
    @app_commands.describe(
        system='Select the system for the reward.',
        target='Selected role ro remove.')
    async def remove_role_rewards(
        self,
        interaction: discord.Interaction,
        system: Literal['Rep', 'Xp'],
        target: discord.Role
    ):
        """"Remove a role as a reward."""
        ...

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen):
    await bot.add_cog(Settings(bot))
