# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations
from datetime import datetime

# Standard library imports
import logging
from math import floor
import random
import re

from typing import TYPE_CHECKING, Optional

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord import app_commands
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
#                          XP
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class XP(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #               App Commands Settings
    xp_group = app_commands.Group(
        name='xp', description='XP Commands.')

    # ______________________ Give XP _______________________

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Validation
        if re.search(r"^[^\"\'\.\w]", message.content) or message.author.bot:
            return

        # Check if xp enabled
        if not self._get_xp_enabled(message.guild.id):
            return

        # Data builder
        conn = self.bot.pool
        guild = message.guild
        author = message.author
        time = message.created_at

        try:
            # TODO: Generate XP and data
            # TODO: Update DB
            pass
        except Exception:
            log.error("Error when giving rep on message.", exc_info=True)

    # ________________________ Get XP _______________________
    @xp_group.command(name='get')
    @app_commands.describe(member='Gets the xp data for a user.')
    async def display_xp(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None
    ) -> None:
        # Defer
        await interaction.response.defer()

        # Validation
        if not self._get_xp_enabled(interaction.guild_id):
            return

        member = member or interaction.user
        conn = self.bot.pool

        try:
            # Get xp info
            sql = ''' SELECT * FROM xp 
                      INNER JOIN logger 
                      ON 
                        xp.server_id=logger.server_id 
                      AND
                        xp.user_id=logger.user_id
                      WHERE server_id=$1 AND user_id=$2
            '''
            res = conn.execute(sql, interaction.guild_id, member.id)
        except Exception:
            log.error("Error while getting xp data.", exc_info=True)

        # Build message
        xp: int = res['xp'] if res['xp'] is not None else 0
        level: int = res['level'] if res['level'] is not None else 0
        next_level_xp: int = self._calc_xp(level)
        needed_xp: int = next_level_xp - xp
        num_msgs: int = res['msg_count'] if res['msg_count'] is not None else 0

        msg = f'''You are level {level}, with {xp} xp.
        Level {level + 1} requires a total of {next_level_xp}: You need {needed_xp} more xp.
        '''

        e = discord.Embed(title=member.display_name,
                          color=discord.Color.random())
        e.description = msg
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name='XP', value=f'{xp}/{needed_xp}', inline=True)
        e.add_field(name='Level', value=level, inline=True)
        e.add_field(name='Messages', value=num_msgs, inline=True)

        await interaction.edit_original_message(embed=e)

    # _______________________ Give XP  ______________________
    @commands.command(name='givexp')
    @commands.has_permissions(administrator=True)
    async def givexp(self, ctx: Context, member: discord.Member, xp: int) -> None:
        """Gives another member xp - Requires admin

        Usage: `givexp "username"/@mention/id xp_amt`
        """

        # Validation
        if xp < 1:
            e = discord.Embed(
                title='Error.',
                description='Unable to give none/negative xp.',
                color=discord.Color.red())
            await ctx.send(embed=e)

        conn = self.bot.pool

        try:
            sql = '''SELECT * FROM xp WHERE server_id=$1 AND user_id=$2'''

        except Exception:
            pass

    # _____________________ XP Enabled  _____________________
    # _____________________ XP Enabled  _____________________
    # _____________________ XP Enabled  _____________________
    # _____________________ XP Enabled  _____________________
    # _______________________ Gen XP  _______________________
    def _gen_xp(self, msg: str) -> int:
        # TODO: Math it

        # FIXME:
        return random.randint(15, 25)

    # _____________________ Calc XP  _______________________
    def _calc_xp(self, level: int) -> int:
        base = 400
        inc = 200
        return floor((base * level) + (inc * level * (level - 1) * 0.5))

    # _____________________ Calc Level  _____________________

    def _calc_level(self, xp: int) -> int:
        level = 1
        while xp >= self.calcXP(level):
            level += 1

        return level

    # _____________________ XP Enabled  _____________________

    @alru_cache(maxsize=128)
    async def _get_xp_enabled(self, server_id: int) -> Optional[bool]:
        # Get pool
        conn = self.bot.pool

        try:
            sql = 'SELECT enable_leveling FROM settings WHERE server_id=$1'
            res = await conn.fetchrow(sql, server_id)

            if res is not None:
                return res['enable_leveling']
            else:
                return None

        except Exception:
            log.error('Error while checking enabled xp.', exc_info=True)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(XP(bot))
