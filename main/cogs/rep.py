# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
from datetime import datetime
from email import message
import logging
import random
import re

from typing import TYPE_CHECKING, Literal, Optional, TypedDict

# Third party imports
import discord  # noqa
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands


# Local application imports
from main.cogs.utils.paginator import TabularPages, SimplePages
from main.cogs.utils.formats import format_dt

if TYPE_CHECKING:
    from main.Zen import Zen
    from main.cogs.utils.context import Context


log = logging.getLogger(__name__)
NOT_ENABLED = 'Error - System Not Enabled.'
SYSTEM = 'rep'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                      Rep Log Pages
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class RepLogEntry(TypedDict):
    time: str
    giver: str
    receiver: str
    amount: int
    link: str


class RepLogEntry:
    __slots__ = ('time', 'giver', 'receiver', 'amount', 'link')

    def __init__(self, entry: RepLogEntry) -> None:
        self.time = entry['time']
        self.giver = entry['giver']
        self.receiver = entry['recipient']
        self.amount = entry['amount']
        self.link = entry['link']

    def __str__(self) -> str:
        msg = f'[{self.time}]({self.link}): `{self.giver}` gave `{self.receiver}` `{self.amount}` rep.'

        return msg


class RepLogPages(SimplePages):
    def __init__(self, entries: list[RepLogEntry], *, ctx: Context, per_page: int = 12):
        converted = [RepLogEntry(entry) for entry in entries]
        super().__init__(converted, ctx=ctx, per_page=per_page)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Rep
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Rep(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    # --------------------------------------------------
    #               App Commands Settings
    rep_group = app_commands.Group(
        name='rep', description='Rep Commands.')

    # ______________________ On Message Rep _______________________
    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        # Check if xp enabled
        if not await self._get_rep_enabled(message.guild.id):
            return

        # Check if forbidden channel
        if message.channel.id in await self._get_excluded_channels(message.guild.id):
            return

        if message.author.bot:
            return

        # Validation
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
        channel = message.channel
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

            self.bot.dispatch('rep_received', message, guild, users)

        except Exception:
            log.error("Error when giving rep on message.", exc_info=True)
            return

        msg = f'`Gave rep to {", ".join([u.display_name for u in users])}`'
        await message.reply(content=msg)

        await self._log_rep(guild, message, author, users, now)

    # ________________________ Rep Receive _______________________
    @commands.Cog.listener(name='on_rep_received')
    async def on_rep_received(
        self,
        message: discord.Message,
        guild: discord.Guild,
        members: list[discord.Member]
    ) -> None:
        # Data builder
        conn = self.bot.pool
        roles: list[discord.Role] = list()

        try:
            sql = '''SELECT user_id, rep FROM rep
                  WHERE server_id=$1 AND user_id=ANY($2::bigint[])'''
            rows = await conn.fetch(sql, guild.id, [u.id for u in members])

            # Data builder
            mem_idx = [m.id for m in members]
            max_rep = max([row['rep'] for row in rows])
            rep_data: list[tuple[int, int]] = [
                (row['user_id'], row['rep']) for row in rows]

            sql = '''SELECT role_id, val FROM rewards
                     WHERE server_id=$1 AND type=$2 and val<=$3'''
            res = await conn.fetch(sql, guild.id, SYSTEM, max_rep)

            if len(res) == 0:
                return

            for user, rep in rep_data:
                member = members[mem_idx.index(user)]
                for entry in res:
                    if entry['val'] <= rep and member.get_role(entry['role_id']) is None:
                        roles.append(guild.get_role(entry['role_id']))

                if len(roles) < 1:
                    continue

                await member.add_roles(*roles)

                msg = f'`{member.display_name} gained the following roles(s): '
                msg += f"{', '.join(role.name for role in roles)}`"

                await message.channel.send(content=msg, delete_after=15)
                roles.clear()

        except Exception:
            log.error('Error while fetching rep rewards.', exc_info=True)
            return

        return

    # _____________________ On Reaction Add _______________________
    @commands.Cog.listener(name='on_reaction_add')
    @commands.guild_only()
    async def on_reaction_add(
        self,
        reaction: discord.Reaction,
        member: discord.Member | discord.User
    ) -> None:

        # Active Validation
        if not await self._get_rep_enabled(reaction.message.guild.id):
            return

        # Data Builder
        author = reaction.message.author
        guild = reaction.message.guild
        channel = reaction.message.channel
        conn = self.bot.pool
        now = datetime.now()

        # Validation
        if channel.id in await self._get_excluded_channels(guild.id) or author.bot:
            return

        if author.id == member.id and not member.guild_permissions.administrator:
            return

        if 'upvote' not in reaction.emoji.__str__().lower():
            return

        try:
            sql = '''INSERT INTO rep (server_id, user_id, rep)
                     VALUES($1, $2, $3)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET rep=rep.rep + $3,
                                   last_received=$4'''
            await conn.execute(sql, guild.id, author.id, 1, now)
            await reaction.message.add_reaction('✅')

            self.bot.dispatch('rep_received', message, guild, [author])

        except Exception:
            log.error('Error while giving reaction rep', exc_info=True)
            return

        return await self._log_rep(guild, reaction.message, member, [author], now)

    # _____________________ On Reaction Remove _______________________
    @commands.Cog.listener(name='on_reaction_remove')
    @commands.guild_only()
    async def on_reaction_remove(
        self,
        reaction: discord.Reaction,
        member: discord.Member | discord.User
    ) -> None:
        # Active Validation
        if not await self._get_rep_enabled(reaction.message.guild.id):
            return

        # Data Builder
        author = reaction.message.author
        guild = reaction.message.guild
        channel = reaction.message.channel
        conn = self.bot.pool
        now = datetime.now()

        # Validation
        if channel.id in await self._get_excluded_channels(guild.id) or author.bot:
            return

        if author.id == member.id and not member.guild_permissions.administrator:
            return

        if 'upvote' not in reaction.emoji.__str__().lower():
            return

        try:
            sql = '''INSERT INTO rep (server_id, user_id, rep)
                     VALUES($1, $2, $3)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET rep=rep.rep - $3,
                                   last_received=$4'''
            await conn.execute(sql, guild.id, author.id, 1, now)

            reactions = [
                r for r in reaction.message.reactions if 'upvote' in r.__str__().lower()]

            if len(reactions) == 0:
                await reaction.message.remove_reaction(emoji='✅', member=self.bot.user)

        except Exception:
            log.error('Error while giving reaction rep', exc_info=True)
            return

        return await self._log_rep(guild, reaction.message, member, [author], now)

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

    # # _______________________ Give Rep  ______________________
    @rep_group.command(name='give')
    @app_commands.describe(member='User to give rep.', rep='Rep amount')
    async def giverep(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        rep: Optional[int]
    ) -> None:
        """Gives another member rep - Requires admin
        """
        # Defer
        await interaction.response.defer()
        rep = rep if rep is not None else 1

        # Validation
        if not await self._get_rep_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        is_admin = interaction.user.guild_permissions.administrator
        if (rep > 1 or rep < 1) and not is_admin:
            e = discord.Embed(
                title='Error.',
                description='Not authorized to give multi rep',
                color=discord.Color.red())
            await interaction.edit_original_message(embed=e)

        if (member.id == interaction.user.id) and not is_admin:
            e = discord.Embed(
                title='Error.',
                description="Can't give rep to yourself.",
                color=discord.Color.red())
            await interaction.edit_original_message(embed=e)

        # Data builder
        conn = self.bot.pool
        now = datetime.now()
        guild = interaction.guild
        author = interaction.user
        message = await interaction.original_message()

        try:
            sql = '''SELECT * FROM rep WHERE server_id=$1 AND user_id=$2'''
            res = await conn.fetchrow(sql, guild.id, member.id)

            new_rep = res['rep'] + rep if res is not None else rep

            sql = '''INSERT INTO rep(server_id, user_id, rep)
                     VALUES($1, $2, $3)
                     ON CONFLICT (server_id, user_id)
                     DO UPDATE SET rep=$3, last_received=$4
                '''
            await conn.execute(sql, guild.id, member.id, new_rep, now)

        except Exception:
            log.error("Error while getting xp data.", exc_info=True)
            return

        self.bot.dispatch('rep_received', interaction.message, guild, [member])
        await interaction.edit_original_message(content=f'{member.display_name} now has `{new_rep}` rep.')

        return await self._log_rep(guild, message, author, [member], now, amount=rep)

    # ______________________ Set XP  ______________________
    @commands.command(name='setrep')
    @commands.has_permissions(administrator=True)
    async def setrep(self, ctx: Context, member: discord.Member, rep: int) -> None:
        """Set the rep for a member - Requires admin

        Usage: `setrep "username"/@mention/id rep_amt`
        """
        # Validation
        if not await self._get_rep_enabled(ctx.guild.id):
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

    # ____________________ Display Log  ______________________
    @rep_group.command(name='log')
    @app_commands.describe(member='Gets the log for a user', link='Display Links')
    async def display_log(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member],
        link: Optional[bool]
    ) -> None:
        """ Displays the reputation log for the server."""
        # Defer
        await interaction.response.defer()

        # Validation
        if not await self._get_rep_enabled(interaction.guild_id):
            return await interaction.edit_original_message(content=NOT_ENABLED)

        # Data builder
        guild = interaction.guild
        conn = self.bot.pool

        try:
            if member is None:
                sql = '''SELECT * FROM rep_log
                         WHERE server_id=$1
                         ORDER BY time DESC
                    '''
                rows = await conn.fetch(sql, guild.id)
            else:
                sql = '''SELECT * FROM rep_log
                         WHERE server_id=$1 AND (giver=$2 OR receiver=$2)
                         ORDER BY time DESC
                      '''
                rows = await conn.fetch(sql, guild.id, member.id)

            if len(rows) == 0:
                return await interaction.edit_original_message(content='`No rep found for this server`')

        except Exception:
            log.error('Error while getting rep log data.', exc_info=True)

        # Get display ready
        data = [{
            'time': row['time'].strftime("%d %b %y %H:%M"),
            'giver': (await self.bot.get_or_fetch_member(guild, row['giver'])).__str__(),
            'recipient': (await self.bot.get_or_fetch_member(guild, row['receiver'])).__str__(),
            'amount': row['amount'],
            'link': row['message_link']
        } for row in rows]

        # Start Paginator
        ctx = await commands.Context.from_interaction(interaction)

        p = RepLogPages(entries=data, ctx=ctx)
        p.embed.set_author(name=interaction.user.display_name)
        await p.start()

        return

    # ____________________ Log Rep  ______________________
    async def _log_rep(
        self,
        guild: discord.Guild,
        message: discord.Message | discord.InteractionMessage,
        giver: discord.Member,
        receivers: list[discord.Member],
        time: datetime,
        amount: int = 1
    ) -> None:
        # Data builder
        conn = self.bot.pool
        channel = message.channel
        link = message.to_reference().jump_url

        try:
            # Add to regular logger
            sql = '''INSERT INTO logger (server_id, user_id, channel_id, last_gave_rep)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (server_id, user_id)
                    DO UPDATE SET last_gave_rep=$4
                    '''
            await conn.execute(sql, guild.id, giver.id, channel.id, time)

            # Add to rep logger
            sql = '''INSERT INTO rep_log(
                        server_id, giver, receiver, amount, message_link, time
                        )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    '''
            vals = [(guild.id, giver.id, r.id, amount, link, time)
                    for r in receivers]
            await conn.executemany(sql, vals)

        except Exception:
            log.error('Error while logging rep.', exc_info=True)

        return

    # _______________ Get Excluded Channels  __________________
    @alru_cache(maxsize=128)
    async def _get_excluded_channels(self, server_id: int) -> Optional[list[int]]:
        # Get pool
        conn = self.bot.pool

        try:
            sql = 'SELECT excluded_rep_channels FROM settings WHERE server_id=$1'
            res = await conn.fetchrow(sql, server_id)

            if res is not None:
                return res['excluded_rep_channels']
            else:
                return None
        except Exception:
            log.error('Error while fetching excluded channels.', exc_info=True)
            return None

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
            return None


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Rep(bot))
