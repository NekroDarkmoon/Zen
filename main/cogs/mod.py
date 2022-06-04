#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import argparse
import shlex
import asyncpg
import asyncio
import datetime
import enum
import logging
import re

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any, Callable, MutableMapping, Optional, Union
from typing_extensions import Annotated

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext import menus


# Local application imports
from main.cogs.utils import cache, time, checks


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context, GuildContext

    class ModGuildContext(GuildContext):
        cog: Mod
        guild_config: ModConfig


GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Arguments(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise RuntimeError(message)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class RaidMode(enum.Enum):
    off = 0
    on = 1
    strict = 2

    def __str__(self) -> str:
        return self.name


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ModConfig:
    __slots__ = {
        'raid_mode', 'id', 'bot', 'broadcast_channel_id', 'mention_count',
        'safe_mention_channel_ids', 'mute_role_id', 'muted_members',
    }

    bot: Zen
    raid_mode: int
    id: int
    broadcast_channel_id: Optional[int]
    mention_count: Optional[int]
    safe_mention_channel_ids: set[int]
    muted_members: set[int]
    mute_role_id: Optional[int]

    @classmethod
    async def from_record(cls, record: Any, bot: Zen):
        self = cls()

        self.bot = bot
        self.raid_mode = record['raid_mode']
        self.id = record['id']
        self.broadcast_channel_id = record['broadcast_channel_id']
        self.mention_count = record['mention_count']
        self.safe_mention_channel_ids = set(
            record['safe_mention_channel_ids'] or [])
        self.muted_members = set(record['muted_members'] or [])
        self.mute_role_id = record['mute_role_id']
        return self

    @property
    def broadcast_chanel(self) -> Optional[discord.TextChannel]:
        guild = self.bot.get_guild(self.id)
        return guild and guild.get_channel(self.broadcast_channel_id)

    @property
    def mute_role(self) -> Optional[discord.Role]:
        guild = self.bot.get_guild(self.id)
        return guild and self.mute_role_id and guild.get_role(self.mute_role_id)

    def is_muted(self, member: discord.abc.Snowflake) -> bool:
        return member.id in self.muted_members

    async def apply_mute(self, member: discord.Member, reason: Optional[str]) -> None:
        if self.mute_role_id:
            await member.add_roles(discord.Object(id=self.mute_role_id), reason=reason)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Converters
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def can_execute_action(
    ctx: GuildContext, user: discord.Member, target: discord.Member
) -> bool:
    return user.id == ctx.bot.owner_id or user == ctx.guild.owner or user.top_role > target.top_role


class MemberID(commands.Converter):
    async def convert(self, ctx: GuildContext, argument: str):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(
                    f"{argument} is not a valid member or member ID") from None
            else:
                m = await ctx.bot.get_or_fetch_member(ctx.guild.id, member_id)
                if m is None:
                    return type('_Hackban', (), {id: member_id, '__str__': lambda s: f'Member ID {s.id}'})()

        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument(
                'You cannot do this action on this user due to role hierarchy.')

        return m


class BannedMember(commands.Converter):
    async def convert(self, ctx: GuildContext, argument: str):
        if argument.isdigit():
            member_id = int(argument, base=10)
            try:
                return await ctx.guild.fetch_ban(discord.Object(id=member_id))
            except discord.NotFound:
                raise commands.BadArgument(
                    'This member has not been banned before.') from None

        entity = await discord.utils.find(lambda u: str(u.user) == argument, ctx.guild.bans(limit=None))

        if entity is None:
            raise commands.BadArgument(
                'This member has not been banned before.')

        return entity


class ActionReason(commands.Converter):
    async def convert(self, ctx: GuildChannel, argument: str):
        ret = f'{ctx.author} (ID: {ctx.author.id}): {argument}'

        if len(ret) > 512:
            reason_max = 512 - len(ret) + len(argument)
            raise commands.BadArgument(
                f'Reason is too long ({len(argument)}/{reason_max})')

        return ret


def safe_reason_append(base: str, to_append: str) -> str:
    appended = base + f'({to_append})'
    if len(appended) > 512:
        return base

    return appended


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class CooldownByContent(commands.CooldownMapping):
    def _bucket_key(self, msg: discord.Message) -> tuple[int, str]:
        return (msg.channel.id, msg.content)


class SpamChecker:
    """This spam checker does a few things.
    1) It checks if a user has spammed more than 10 times in 12 seconds
    2) It checks if the content has been spammed 15 times in 17 seconds.
    3) It checks if new users have spammed 30 times in 35 seconds.
    4) It checks if "fast joiners" have spammed 10 times in 12 seconds.
    5) It checks if a member spammed `config.mention_count * 2` mentions in 12 seconds.

    The second case is meant to catch alternating spam bots while the first one
    just catches regular singular spam bots.

    From experience these values aren't reached unless someone is actively spamming.
    """

    def __init__(self) -> None:
        self.by_content = CooldownByContent.from_cooldown(
            15, 17.0, commands.BucketType.member)
        self.by_user = commands.CooldownMapping.from_cooldown(
            10, 12.0, commands.BucketType.user)
        self.last_join: Optional[datetime.datetime] = None
        self.new_user = commands.CooldownMapping.from_cooldown(
            30, 35.0, commands.BucketType.channel)
        self._by_mentions: Optional[commands.CooldownMapping] = None
        self._by_mentions_rate: Optional[int] = None

        # user_id flag mapping (for about 30 minutes)
        self.fast_joiners: MutableMapping[int, bool] = cache.ExpiringCache(
            seconds=1800.0)
        self.hit_and_run = commands.CooldownMapping.from_cooldown(
            10, 12, commands.BucketType.channel)

    def by_mentions(self, config: ModConfig) -> Optional[commands.CooldownMapping]:
        if not config.mention_count:
            return None

        mention_threshold = config.mention_count * 2
        if self._by_mentions_rate != mention_threshold:
            self._by_mentions = commands.CooldownMapping.from_cooldown(
                mention_threshold, 12, commands.BucketType.member)
            self._by_mentions_rate = mention_threshold
        return self._by_mentions

    def is_new(self, member: discord.Member) -> bool:
        now = discord.utils.utcnow()
        seven_days_ago = now - datetime.timedelta(days=7)
        ninety_days_ago = now - datetime.timedelta(days=90)
        return member.created_at > ninety_days_ago and member.joined_at is not None and member.joined_at > seven_days_ago

    def is_spamming(self, message: discord.Message, config: ModConfig) -> bool:
        if message.guild is None:
            return False

        current = message.created_at.timestamp()

        if message.author.id in self.fast_joiners:
            bucket = self.hit_and_run.get_bucket(message)
            if bucket.update_rate_limit(current):
                return True

        if self.is_new(message.author):
            new_bucket = self.new_user.get_bucket(message)
            if new_bucket.update_rate_limit(current):
                return True

        user_bucket = self.by_user.get_bucket(message)
        if user_bucket.update_rate_limit(current):
            return True

        content_bucket = self.by_content.get_bucket(message)
        if content_bucket.update_rate_limit(current):
            return True

        if self.is_mention_spam(message, config, current):
            return True

        return False

    def is_fast_join(self, member: discord.Member) -> bool:
        joined = member.joined_at or discord.utils.utcnow()
        if self.last_join is None:
            self.last_join = joined
            return False
        is_fast = (joined - self.last_join).total_seconds() <= 2.0
        self.last_join = joined
        if is_fast:
            self.fast_joiners[member.id] = True
        return is_fast

    def is_mention_spam(self, message: discord.Message, config: ModConfig, current: float) -> bool:
        mapping = self.by_mentions(config)
        if mapping is None:
            return False
        mention_bucket = mapping.get_bucket(message, current)
        mention_count = sum(not m.bot and m.id !=
                            message.author.id for m in message.mentions)
        return mention_bucket.update_rate_limit(current, tokens=mention_count) is not None


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class NoMuteRole(commands.CommandError):
    def __init__(self) -> None:
        super().__init__('This server does not have a mute role set up.')


# Decorator
def can_mute():
    async def predicate(ctx: ModGuildContext) -> bool:
        is_owner = await ctx.bot.is_owner(ctx.author)
        if ctx.guild is None:
            return False

        if not ctx.author.guild_permissions.manage_roles and not is_owner:
            return False

        # This will only be used within this cog.
        # type: ignore
        ctx.guild_config = config = await ctx.cog.get_guild_config(ctx.guild.id)
        role = config and config.mute_role
        if role is None:
            raise NoMuteRole()
        return ctx.author.top_role > role

    return commands.check(predicate)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Mod
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Mod(commands.Cog):
    """ Moderation commands. """

    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot
        self._spam_check: defaultdict[int,
                                      SpamChecker] = defaultdict(SpamChecker)

        self._data_batch: defaultdict[int,
                                      list[tuple[int, Any]]] = defaultdict(list)
        self._batch_lock = asyncio.Lock()
        self._disable_lock = asyncio.Lock()
        self.batch_updates.add_exception_type(asyncpg.PostgresConnectionError)
        self.batch_updates.start()

        self.message_batches: defaultdict[tuple[int, int], list[str]] = defaultdict(
            list)
        self._batch_message_lock = asyncio.Lock()
        self.bulk_send_messages.start()

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='DiscordCertifiedModerator', id=847961544124923945)

    def __repr__(self) -> str:
        return '<cogs.Mod>'

    def cog_unload(self) -> None:
        self.batch_updates.stop()
        self.bulk_send_messages.stop()

    async def cog_command_error(self, ctx: GuildContext, error: commands.CommandError) -> None:
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.Forbidden):
                await ctx.send('I do not have permission to execute this action.')
            elif isinstance(original, discord.NotFound):
                await ctx.send(f'This entity does not exist: {original.text}')
            elif isinstance(original, discord.HTTPException):
                await ctx.send('Somehow, an unexpected error occurred. Try again later?')
        elif isinstance(error, NoMuteRole):
            await ctx.send(str(error))

    async def bulk_insert(self) -> None:
        sql = '''UPDATE guild_mog_config
                 SET muted_members = x.result_array
                 FROM jsonb_to_recordset($1::jsonb) AS
                 x ( guild_id BIGINT, result_array BIGINT[] )
                 WHERE guild_mod_config.id = x.guild.id
                '''

        if not self._data_batch:
            return

        final_data = []
        for guild_id, data in self._data_batch.items():
            config = await self.get_guild_config(guild_id)

            if config is None:
                continue

            as_set = config.muted_members
            for member_id, insertion in data:
                func = as_set.add if insertion else as_set.discard
                func(member_id)

            final_data.append(
                {'guild_id': guild_id, 'result_array': list(as_set)})
            self.get_guild_config.invalidate(self, guild_id)

        await self.bot.pool.execute(sql, final_data)
        self._data_batch.clear()

    @tasks.loop(seconds=15.0)
    async def batch_updates(self) -> None:
        async with self._batch_lock:
            await self.bulk_insert()

    @tasks.loop(seconds=10.0)
    async def bulk_send_messages(self) -> None:
        async with self._batch_message_lock:
            for ((guild_id, channel_id), messages) in self.message_batches.items():
                guild = self.bot.get_guild(guild_id)
                channel: Optional[discord.abc.Messageable] = guild and guild.get_channel(
                    channel_id)
                if channel is None:
                    continue

                paginator = commands.Paginator(suffix='', prefix='')
                for message in messages:
                    paginator.add_line(message)

                for page in paginator.pages:
                    try:
                        await channel.send(page)
                    except discord.HTTPException:
                        pass

            self.message_batches.clear()

    @cache.cache()
    async def get_guild_config(self, guild_id: int) -> Optional[ModConfig]:
        sql = '''SELECT * FROM guild_mod_config WHERE id=$1'''
        async with self.bot.pool.acquire(timeout=300.0) as conn:
            record = await conn.fetchrow(sql, guild_id)

            if record is not None:
                return await ModConfig.from_record(record, self.bot)

            return None

    async def check_raid(
        self,
        config: ModConfig,
        guild_id: int,
        member: discord.Member,
        message: discord.Message
    ) -> None:
        if config.raid_mode != RaidMode.strict.value:
            return

        checker = self._spam_check[guild_id]
        if not checker.is_spamming(message, config):
            return

        try:
            await member.ban(reason='Auto-ban from spam (strict raid mode ban)')
        except discord.HTTPException:
            log.info(
                f'[Raid Mode] Failed to ban {member} (ID: {member.id}) from server {member.guild} via strict mode.')
        else:
            log.info(
                f'[Raid Mode] Banned {member} (ID: {member.id}) from server {member.guild} via strict mode.')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        author = message.author

        # Validation
        if author.id in (self.bot.user.id, self.bot.owner_id):
            return

        if message.guild is None or not isinstance(author, discord.Member):
            return

        if author.bot or author.guild_permissions.manage_messages:
            return

        guild_id = message.guild.id
        config = await self.get_guild_config(guild_id)
        if config is None:
            return

        # Check raid mode
        await self.check_raid(config, guild_id, author, message)

        # Auto ban tracking for mention spams begins here
        if len(message.mentions) <= 3:
            return

        if not config.mention_count:
            return

        # Check if it meets the thresholds required
        mention_count = sum(not m.bot and m.id !=
                            author.id for m in message.mentions)

        if mention_count < config.mention_count:
            return

        if message.channel.id in config.safe_mention_channel_ids:
            return

        try:
            await author.ban(reason=f'Spamming mentions ({mention_count} mentions)')
        except Exception as e:
            log.info(
                f'Failed to autoban member {author} (ID: {author.id}) in guild ID {guild_id}')
        else:
            to_send = f'Banned {author} (ID: {author.id}) for spamming {mention_count} mentions.'
            async with self._batch_message_lock:
                self.message_batches[(
                    guild_id, message.channel.id)].append(to_send)

            log.info(
                f'Member {author} (ID: {author.id}) has been autobanned from guild ID {guild_id}')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        guild_id = member.guild.id

        config = await self.get_guild_config(guild_id)
        if config is None:
            return

        if config.is_muted(member):
            return await config.apply_mute(member, 'Member was previously muted.')

        if not config.raid_mode:
            return

        now = discord.utils.utcnow()

        is_new = member.created_at > (now - datetime.timedelta(days=7))
        checker = self._spam_check[guild_id]

        # Do the broadcasted message to the channel
        title = 'Member Joined'
        if checker.is_fast_join(member):
            colour = 0xDD5F53  # red
            if is_new:
                title = 'Member Joined (Very New Member)'
        else:
            colour = 0x53DDA4  # green

            if is_new:
                colour = 0xDDA453  # yellow
                title = 'Member Joined (Very New Member)'

        e = discord.Embed(title=title, colour=colour)
        e.timestamp = now
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
        e.add_field(name='ID', value=member.id)
        assert member.joined_at is not None
        e.add_field(name='Joined', value=time.format_dt(member.joined_at, "F"))
        e.add_field(name='Created', value=time.format_relative(
            member.created_at), inline=False)

        if config.broadcast_chanel:
            try:
                await config.broadcast_chanel.send(embed=e)
            except discord.Forbidden:
                async with self._disable_lock:
                    await self.disable_raid_mode(guild_id)

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        if before.roles == after.roles:
            return

        guild_id = after.guild.id

        config = await self.get_guild_config(guild_id)
        if config is None:
            return

        if config.mute_role_id is None:
            return

        before_has = before.get_role(config.mute_role_id)
        after_has = after.get_role(config.mute_role_id)

        if before_has == after_has:
            return

        async with self._batch_lock:
            self._data_batch[guild_id].append((after.id, after_has))

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild_id = role.guild.id

        config = await self.get_guild_config(guild_id)
        if config is None or config.mute_role_id != role.id:
            return

        sql = """UPDATE guild_mod_config SET (mute_role_id, muted_members)
                 = (NULL, '{}'::BIGINT[])
                 WHERE id=$1
              """
        await self.bot.pool.execute(sql, guild_id)
        self.get_guild_config.invalidate(self, guild_id)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #                         Commands
    @commands.hybrid_group(invoke_without_command=True)
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def mod(self, ctx: GuildContext) -> None:
        """ Mod Commands """
        if ctx.invoked_subcommand is None:
            await ctx.send_help('mod')

    # _______________________ New Users _________________________
    @mod.command('newusers')
    @app_commands.describe(count='Number of members - Max 25')
    async def newusers(
            self,
            ctx: GuildContext,
            count: Optional[int] = 5
    ) -> None:
        """Tells you the newest members of the server.

        This is useful to check if any suspicious members have
        joined.

        The count parameter can only be up to 25.
        """
        await ctx.typing()

        count = max(min(count, 25), 5)

        if not ctx.guild.chunked:
            members = await ctx.guild.chunk(cache=True)

        members = sorted(
            ctx.guild.members, key=lambda m: m.joined_at or ctx.guild.created_at, reverse=True)[:count]

        e = discord.Embed(title='New Members', color=discord.Color.green())

        for m in members:
            joined = m.joined_at or datetime.datetime(1970, 1, 1)
            body = f'Joined {time.format_relative(joined)}\nCreated {time.format_relative(m.created_at)}'
            e.add_field(name=f'{m} (ID: {m.id})', value=body, inline=False)

        await ctx.send(embed=e)

    # _______________________ Raid Group _________________________
    @mod.group('raid', invoke_without_subcommand=True)
    @checks.is_mod()
    async def raid(self, ctx: GuildContext) -> None:
        """Controls raid mode on the server.

       Calling this command with no arguments will show the current raid
       mode information.

       You must have Manage Server permissions to use this command or
       its subcommands.
       """

        # Moderator Validation
        if not ctx.author.guild_permissions.manage_guild:
            return

        sql = "SELECT raid_mode, broadcast_channel FROM guild_mod_config WHERE id=$1;"

        row = await ctx.db.fetchrow(sql, ctx.guild.id)
        if row is None:
            fmt = 'Raid Mode: off\nBroadcast Channel: None'
        else:
            ch = f'<#{row[1]}>' if row[1] else None
            mode = RaidMode(row[0]) if row[0] is not None else RaidMode.off
            fmt = f'Raid Mode: {mode}\nBroadcast Channel: {ch}'

        await ctx.send(fmt)

    # _______________________ Raid On _________________________
    @raid.command(name='on')
    @checks.is_mod()
    async def raid_on(
        self,
        ctx: GuildContext,
        channel: Optional[discord.TextChannel]
    ) -> None:
        """Enables basic raid mode on the server.

          When enabled, server verification level is set to high
          and allows the bot to broadcast new members joining
          to a specified channel.

          If no channel is given, then the bot will broadcast join
          messages on the channel this command was used in.
          """
        await ctx.typing()

        # Moderator Validation
        if not ctx.author.guild_permissions.manage_guild:
            return

        channel_id: int = channel.id if channel else ctx.channel.id

        try:
            await ctx.guild.edit(verification_level=discord.VerificationLevel.high)
        except discord.HTTPException:
            await ctx.send('\N{WARNING SIGN} Could not set verification level.')

        query = """INSERT INTO guild_mod_config (id, raid_mode, broadcast_channel)
                   VALUES ($1, $2, $3) ON CONFLICT (id)
                   DO UPDATE SET
                        raid_mode = EXCLUDED.raid_mode,
                        broadcast_channel = EXCLUDED.broadcast_channel;
                """

        await ctx.db.execute(query, ctx.guild.id, RaidMode.on.value, channel_id)
        self.get_guild_config.invalidate(self, ctx.guild.id)
        await ctx.send(f'Raid mode enabled. Broadcasting join messages to <#{channel_id}>.')

    # _______________________ Raid Off _________________________
    @raid.command(name='off')
    @checks.is_mod()
    async def raid_off(self, ctx: GuildContext) -> None:
        """Disables raid mode on the server.

        When disabled, the server verification levels are set
        back to Low levels and the bot will stop broadcasting
        join messages.
        """
        await ctx.typing()

        # Moderator Validation
        if not ctx.author.guild_permissions.manage_guild:
            return

        try:
            await ctx.guild.edit(verification_level=discord.VerificationLevel.low)
        except discord.HTTPException:
            await ctx.send('\N{WARNING SIGN} Could not set verification level.')
        await self.disable_raid_mode(ctx.guild.id)
        await ctx.send('Raid mode disabled. No longer broadcasting join messages.')

    # _______________________ Raid Strict _________________________
    @raid.command(name='strict')
    @checks.is_mod()
    async def raid_strict(
        self,
        ctx: GuildContext,
        channel: Optional[discord.TextChannel]
    ) -> None:
        """Enables strict raid mode on the server.

        Strict mode is similar to regular enabled raid mode, with the added
        benefit of auto-banning members that are spamming. The threshold for
        spamming depends on a per-content basis and also on a per-user basis
        of 15 messages per 17 seconds.

        If this is considered too strict, it is recommended to fall back to regular
        raid mode.
        """
        await ctx.typing()

        # Moderator Validation
        if not ctx.author.guild_permissions.manage_guild:
            return

        channel_id: int = channel.id if channel else ctx.channel.id

        perms = ctx.me.guild_permissions
        if not (perms.kick_members and perms.ban_members):
            return await ctx.send('\N{NO ENTRY SIGN} I do not have permissions to kick and ban members.')

        try:
            await ctx.guild.edit(verification_level=discord.VerificationLevel.high)
        except discord.HTTPException:
            await ctx.send('\N{WARNING SIGN} Could not set verification level.')

        query = """INSERT INTO guild_mod_config (id, raid_mode, broadcast_channel)
                   VALUES ($1, $2, $3) ON CONFLICT (id)
                   DO UPDATE SET
                        raid_mode = EXCLUDED.raid_mode,
                        broadcast_channel = EXCLUDED.broadcast_channel;
                """

        await ctx.db.execute(query, ctx.guild.id, RaidMode.strict.value, channel_id)
        self.get_guild_config.invalidate(self, ctx.guild.id)
        await ctx.send(f'Raid mode enabled strictly. Broadcasting join messages to <#{channel_id}>.')

    # _______________________ Raid Off _________________________
    async def disable_raid_mode(self, guild_id) -> None:
        sql = '''INSERT INTO guild_mod_config (id, raid_mode, broadcast_channel)
                    VALUES ($1, $2, NULL)
                    ON CONFLICT (id)
                    DO UPDATE SET
                    raid_mode = EXCLUDED.raid_mode,
                    broadcast_channel = NULL'''

        await self.bot.pool.execute(sql, guild_id, RaidMode.off.value)
        self._spam_check.pop(guild_id, None)
        self.get_guild_config.invalidate(self, guild_id)

    # ______________________ Cleanup Commands _________________________
    async def _basic_cleanup_strategy(self, ctx: GuildContext, search: int):
        count = 0
        async for msg in ctx.history(limit=search, before=ctx.message):
            if msg.author == ctx.me and not (msg.mentions or msg.role_mentions):
                await msg.delete()
                count += 1
        return {'Bot': count}

    async def _complex_cleanup_strategy(self, ctx: GuildContext, search: int):
        prefixes = tuple(self.bot.get_guild_prefixes(
            ctx.guild))  # thanks startswith

        def check(m):
            return m.author == ctx.me or m.content.startswith(prefixes)

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    async def _regular_user_cleanup_strategy(self, ctx: GuildContext, search: int):
        prefixes = tuple(self.bot.get_guild_prefixes(ctx.guild))

        def check(m):
            return (m.author == ctx.me or m.content.startswith(prefixes)) and not (m.mentions or m.role_mentions)

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    @commands.command()
    async def cleanup(self, ctx: GuildContext, search: int = 100):
        """Cleans up the bot's messages from the channel.

        If a search number is specified, it searches that many messages to delete.
        If the bot has Manage Messages permissions then it will try to delete
        messages that look like they invoked the bot as well.

        After the cleanup is completed, the bot will send you a message with
        which people got their messages deleted and their count. This is useful
        to see which users are spammers.

        Members with Manage Messages can search up to 1000 messages.
        Members without can search up to 25 messages.
        """

        strategy = self._basic_cleanup_strategy
        is_mod = ctx.channel.permissions_for(ctx.author).manage_messages
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            if is_mod:
                strategy = self._complex_cleanup_strategy
            else:
                strategy = self._regular_user_cleanup_strategy

        if is_mod:
            search = min(max(2, search), 1000)
        else:
            search = min(max(2, search), 25)

        spammers = await strategy(ctx, search)
        deleted = sum(spammers.values())
        messages = [
            f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(),
                              key=lambda t: t[1], reverse=True)
            messages.extend(
                f'- **{author}**: {count}' for author, count in spammers)

        await ctx.send('\n'.join(messages), delete_after=10)

    # ______________________ Kick Command _________________________
    @mod.command(name='kick')
    @checks.has_permissions(kick_members=True)
    async def kick(
        self,
        ctx: GuildContext,
        member: Annotated[discord.abc.Snowflake, MemberID],
        reason: Annotated[Optional[str], ActionReason] = None
    ) -> None:
        """Kicks a member from the server.

        In order for this to work, the bot must have Kick Member permissions.
        To use this command you must have Kick Members permission.
        """
        # Moderator Validation
        if not ctx.author.guild_permissions.kick_members:
            return

        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        confirm = await ctx.prompt(f'This will kick {member.__str__()}. Are you sure?', reacquire=False)
        if not confirm:
            return await ctx.send('Aborting.')

        await ctx.guild.kick(member, reason=reason)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')

    # ______________________ Ban Command _________________________
    @mod.command(name='ban')
    @checks.has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: GuildContext,
        member: Annotated[discord.abc.Snowflake, MemberID],
        reason: Annotated[Optional[str], ActionReason] = None
    ) -> None:
        """Bans a member from the server.

        In order for this to work, the bot must have Ban Member permissions.
        To use this command you must have Ban Members permission.
        """
        # Moderator Validation
        if not ctx.author.guild_permissions.ban_members:
            return

        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        confirm = await ctx.prompt(f'This will ban {member.__str__()}. Are you sure?', reacquire=False)
        if not confirm:
            return await ctx.send('Aborting.')

        await ctx.guild.ban(member, reason=reason)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')



# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen):
    await bot.add_cog(Mod(bot))
