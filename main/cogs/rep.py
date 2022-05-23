# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
from datetime import datetime
import logging
import random
import re

from typing import TYPE_CHECKING, Literal, Optional

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands


# Local application imports
from main.cogs.utils.paginator import TabularPages
from main.cogs.utils.formats import format_dt

if TYPE_CHECKING:
    from main.Zen import Zen
    from main.cogs.utils.context import Context


log = logging.getLogger(__name__)
NOT_ENABLED = 'Error - System Not Enabled.'
SYSTEM = 'rep'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          XP
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Rep(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #               App Commands Settings
    rep_group = app_commands.Group(
        name='rep', description='Rep Commands.')

    # ______________________ Give Rep _______________________
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Check if xp enabled
        if not await self._get_rep_enabled(message.guild.id):
            return

        def check(msg):
            checks = [
                r'(?<!no )(?<![A-z])th(a?n?(k|x)s?)(?![A-z])',
                r'(?<!no )(?<![A-z])ty(vm)?(?![A-z])',
                r'(?<![A-z])dankee?(?![A-z])',
                r'(?<![A-z])ありがとう?(?![A-z])',
                r':upvote:',
            ]

            return any([re.search(x, msg) for x in checks])

        if len(message.mentions) == 0 or not check(message.content.lower()):
            return

        # Data builder
        conn = self.bot.pool
        guild = message.guild
        author = message.author
        users = [u for u in message.mentions if u.id !=
                 author.id and not u.bot]
        now = datetime.now()

        if len(users) == 0:
            return

        try:
            sql = '''INSERT INTO rep (server_id, user_id, rep)
                     VALUES ($1, $2, $3)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET rep=rep.rep + $3,
                                   last_received = $4
                     '''
            vals = [(guild.id, u.id, 1, now) for u in users]
            await conn.executemany(sql, vals)

            self.bot.dispatch('rep_given', guild, users)

            sql = '''INSERT INTO logger (server_id, user_id, channel_id, last_gave_rep)
                     VALUES ($1, $2, $3, $4)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET last_gave_rep=$4
                     '''
            await conn.execute(sql, guild.id, author.id, message.channel.id, now)

        except Exception:
            log.error("Error when giving rep on message.", exc_info=True)
            return

        msg = f'`Gave rep to {", ".join([u.display_name for u in users])}`'
        await message.reply(content=msg)

    # ________________________ Get XP _______________________
    @commands.Cog.listener(name='on_rep_received')
    async def on_rep_received(self, message: discord.Message, level: int) -> None:
        # Data builder
        conn = self.bot.pool
        member = message.author
        guild = message.guild
        roles: list[discord.Role] = list()

        msg = f'`{member.display_name} reached level {level}.`'
        await message.channel.send(content=msg, delete_after=15)

        try:
            sql = '''SELECT role_id FROM rewards 
                     WHERE server_id=$1 AND type=$2 AND val<=$3'''
            res: list[int] = await conn.fetch(sql, guild.id, SYSTEM, level)

            if len(res) == 0:
                return

            for entry in res:
                if member.get_role(entry['role_id']) is None:
                    roles.append(guild.get_role(entry['role_id']))

            if len(roles) < 1:
                return

            await member.add_roles(*roles)

        except Exception:
            log.error('Error while granting role rewards.', exc_info=True)
            return

        msg = f'`{member.display_name} gained the following role(s): '
        msg += f"{', '.join(role.name for role in roles)}`"

        await message.channel.send(content=msg, delete_after=15)

    # ________________________ Get XP _______________________
    @rep_group.command(name='get')
    @app_commands.describe(member='Gets the rep data for a user.')
    async def display_rep(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None
    ) -> None:
        """ Get the rep information of a member or yourself. """

        # Defer
        await interaction.response.defer()

        # Validation
        if not await self._get_rep_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        member = member or interaction.user
        conn = self.bot.pool

        try:
            # Get xp info
            sql = ''' SELECT * FROM rep
                      INNER JOIN logger
                      ON
                        rep.server_id=logger.server_id
                      AND
                        rep.user_id=logger.user_id
                      WHERE rep.server_id=$1 AND rep.user_id=$2
            '''
            res = await conn.fetchrow(sql, interaction.guild_id, member.id)
        except Exception:
            log.error("Error while getting rep data.", exc_info=True)
            return

        # Build message
        rep: int = res['rep'] if res is not None else 0
        last_gave: str = format_dt(
            res['last_gave_rep'], 'R') if res is not None else 'Never'
        last_received: str = format_dt(
            res['last_received'], 'R') if res is not None else 'Never'

        e = discord.Embed(title=member.display_name,
                          color=discord.Color.random())
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name='Rep', value=f'`{rep}`', inline=False)
        e.add_field(name='Last Gave', value=last_gave, inline=True)
        e.add_field(name='Last Received', value=last_received, inline=True)

        await interaction.edit_original_message(embed=e)

    # # _______________________ Give XP  ______________________
    # @rep_group.command('give')
    # @app_commands.describe(member='User to give rep.', rep='Rep amount')
    # async def givexp(self, ctx: Context, member: discord.Member, rep: int) -> None:
    #     """Gives another member rep - Requires admin

    #     Usage: `giverep "username"/@mention/id xp_amt`
    #     """

    #     # Validation
    #     if not await self._get_xp_enabled(ctx.guild.id):
    #         return await ctx.reply(content=NOT_ENABLED)

    #     if xp < 1:
    #         e = discord.Embed(
    #             title='Error.',
    #             description='Unable to give none/negative xp.',
    #             color=discord.Color.red())
    #         await ctx.send(embed=e)

    #     conn = self.bot.pool

    #     try:
    #         sql = '''SELECT * FROM xp WHERE server_id=$1 AND user_id=$2'''
    #         res = await conn.fetchrow(sql, ctx.guild.id, member.id)

    #         new_xp = res['xp'] + xp if res is not None else xp
    #         level = self._calc_level(new_xp)

    #         sql = '''INSERT INTO xp(server_id, user_id, xp, level)
    #                  VALUES($1, $2, $3, $4)
    #                  ON CONFLICT (server_id, user_id)
    #                  DO UPDATE SET xp=$3, level=$4
    #             '''
    #         await conn.execute(sql, ctx.guild.id, member.id, new_xp, level)

    #     except Exception:
    #         log.error("Error while getting xp data.", exc_info=True)
    #         return

    #     await ctx.reply(f'{member.display_name} now has {new_xp} xp.')

    # ______________________ Set XP  ______________________
    @commands.command(name='setrep')
    @commands.has_permissions(administrator=True)
    async def setrep(self, ctx: Context, member: discord.Member, rep: int) -> None:
        """Set the rep for a member - Requires admin

        Usage: `setrep "username"/@mention/id rep_amt`
        """
        # Validation
        if not await self._get_xp_enabled(ctx.guild.id):
            return await ctx.reply(content=NOT_ENABLED)

        # Data builder
        conn = self.bot.pool

        try:
            sql = '''INSERT INTO rep(server_id, user_id, rep)
                     VALUES($1, $2, $3)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET rep=$3
            '''
            await conn.execute(sql, ctx.guild.id, member.id, rep)

        except Exception:
            log.error("Error while getting rep data.", exc_info=True)
            return

        await ctx.message.delete(delay=10)
        await ctx.send(
            content=f'{member.display_name} now has {rep} rep.',
            reference=ctx.message.to_reference(),
            delete_after=10
        )

    # _____________________  XP Board  ______________________
    @rep_group.command(name='leaderboard')
    @app_commands.describe(page='Go to a specific page.')
    async def leaderboard(self, interaction: discord.Interaction, page: Optional[int]) -> None:
        """ Display the Rep leaderboard for the server. """
        # Defer
        await interaction.response.defer()

        # Validation
        if not await self._get_rep_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        guild = interaction.guild
        conn = self.bot.pool

        # Get data
        try:
            sql = '''SELECT 
                     DENSE_RANK () OVER (
                         ORDER BY rep DESC, last_received ASC
                     ) rank, 
                     user_id, rep FROM rep 
                     WHERE server_id=$1
                     LIMIT 50'''

            rows = await conn.fetch(sql, interaction.guild_id)
        except Exception:
            log.error('Error while retrieving rep data', exc_info=True)

        # Make data usable
        data = [{
            'Rank': row['rank'],
            'User': (await self.bot.get_or_fetch_member(guild, row['user_id'])).__str__(),
            'Rep': row['rep'],
        } for row in rows]

        # Start paginator
        ctx = await commands.Context.from_interaction(interaction)

        p = TabularPages(
            entries=data, ctx=ctx, headers='keys')
        p.embed.set_author(name=interaction.user.display_name)
        await p.start()

    # _____________________ XP Enabled  _____________________
    # _____________________ XP Rewards  _____________________
    @rep_group.command(name='rewards')
    async def rewards(self, interaction: discord.Interaction) -> None:
        """ Display rep associated rewards. """
        # Defer
        await interaction.response.defer()

        # Validation
        if not await self._get_rep_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        conn = self.bot.pool
        guild = interaction.guild
        try:
            sql = '''SELECT role_id, val FROM rewards WHERE
                     server_id=$1 AND type=$2
                     ORDER BY val ASC'''
            rows = await conn.fetch(sql, guild.id, SYSTEM)
        except Exception:
            log.error('Error while displaying rewards.', exc_info=True)

        if len(rows) == 0:
            return

        # Convert to usable data

        data = [[guild.get_role(row['role_id']).name, row['val']]
                for row in rows]
        headers = ['Role', 'Level']

        # Start paginator
        ctx = await commands.Context.from_interaction(interaction)

        p = TabularPages(
            entries=data, ctx=ctx, headers=headers)
        p.embed.set_author(name=interaction.user.display_name)
        await p.start()

    # _____________________ Get Last Message  _____________________
    # _____________________ Rep Enabled  _____________________
    @alru_cache(maxsize=128)
    async def _get_rep_enabled(self, server_id: int) -> Optional[bool]:
        # Get pool
        conn = self.bot.pool

        try:
            sql = 'SELECT enable_rep FROM settings WHERE server_id=$1'
            res = await conn.fetchrow(sql, server_id)

            if res is not None:
                return res['enable_rep']
            else:
                return None

        except Exception:
            log.error('Error while checking enabled rep.', exc_info=True)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Rep(bot))
