#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations
from unicodedata import name

# Standard library imports
import aiohttp
import datetime
import logging
import os
import sys
import traceback

from collections import defaultdict, Counter
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterable, Optional, Union
import asyncpg

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands

# Local application imports
import main.settings.config as config
from main.cogs.utils.config import Config
from main.cogs.utils.context import Context

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
description = "Hello, I'm a bot for TTRPG servers. I help with managing TTRPG communities."

log = logging.getLogger(__name__)

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


class ZenCommandTree(app_commands.CommandTree):
    async def tree_on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        assert interaction.command is not None

        e = discord.Embed(title='Command Error', colour=0xA32952)
        e.add_field(name='Command', value=interaction.command.name)
        (exc_type, exc, tb) = type(error), error, error.__traceback__
        trace = traceback.format_exception(exc_type, exc, tb)
        e.add_field(name="Error", value=f"```py\n{trace}\n```")
        e.timestamp = datetime.datetime.now(datetime.timezone.utc)
        hook = self.client.get_cog("Stats").webhook
        try:
            await hook.send(embed=e)
        except discord.HTTPException:
            pass


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                           Zen
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Zen(commands.AutoShardedBot):
    user: discord.ClientUser
    session: aiohttp.ClientSession
    pool: asyncpg.Pool
    command_stats: Counter[str]
    socket_stats: Counter[Any]
    gateway_handler: Any
    bot_app_info: discord.AppInfo

    def __init__(self) -> None:
        allowed_mentions = discord.AllowedMentions(
            roles=False, everyone=False, users=True)
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=config.prefix,
            description=description,
            pm_help=None,
            help_attr=dict(hidden=True),
            chunk_guilds_at_startup=False,
            heartbeat_timeout=180.0,
            allowed_mentions=allowed_mentions,
            intents=intents,
            enable_debug_events=True,
            tree_cls=ZenCommandTree,
        )

        self.client_id: str = config.client_id
        self.dev_guilds: set(config.guilds)
        self.resumes: defaultdict[int,
                                  list[datetime.datetime]] = defaultdict(list)
        self.identifies: defaultdict[int,
                                     list[datetime.datetime]] = defaultdict(list)

        self.spam_control = commands.CooldownMapping.from_cooldown(
            10, 12.0, commands.BucketType.user)

        self._auto_spam_count = Counter()
        self.command_stats = Counter()
        self.socket_stats = Counter()

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.prefixes: Config[list[str]] = Config(
            'main/settings/prefixes.json', loop=self.loop)
        self.blacklist: Config[bool] = Config(
            'main/settings/blacklist.json', loop=self.loop)

        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.owner.id
        self.guilds = config.guilds

        # Load Extensions
        for cog in [file.split('.')[0] for file in os.listdir('main/cogs') if file.endswith('.py')]:
            try:
                if cog != '__init__':
                    await self.load_extension(f'main.cogs.{cog}')
                    print(f'Loaded Cog - {cog}')

            except Exception as e:
                print(f'Failed to load cog {cog}.', file=sys.stderr)
                traceback.print_exc()

        # Set Status
        self.activity = discord.Activity(
            name=config.activity, type=discord.ActivityType.watching)

    @property
    def owner(self) -> discord.User:
        return self.bot_app_info.owner

    def _clear_gateway_data(self) -> None:
        one_week_ago = discord.utils.utcnow() - datetime.timedelta(days=7)
        for shard_id, dates in self.identifies.items():
            to_remove = [index for index, dt in enumerate(
                dates) if dt < one_week_ago]
            for index in reversed(to_remove):
                del dates[index]

        for shard_id, dates in self.resumes.items():
            to_remove = [index for index, dt in enumerate(
                dates) if dt < one_week_ago]
            for index in reversed(to_remove):
                del dates[index]

    async def before_identify_hook(self, shard_id: int, *, initial: bool):
        self._clear_gateway_data()
        self.identifies[shard_id].append(discord.utils.utcnow())
        await super().before_identify_hook(shard_id, initial=initial)

    async def on_command_error(self, ctx: Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send('This command cannot be used in private messages.')
        elif isinstance(error, commands.DisabledCommand):
            await ctx.author.send('Sorry. This command is disabled and cannot be used.')
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if not isinstance(original, discord.HTTPException):
                print(f'In {ctx.command.qualified_name}:', file=sys.stderr)
                traceback.print_tb(original.__traceback__)
                print(f'{original.__class__.__name__}: {original}',
                      file=sys.stderr)
        elif isinstance(error, commands.ArgumentParsingError):
            await ctx.send(str(error))

    # def get_raw_guild_prefixes(self, guild_id: int) -> list[str]:
    #     return self.prefixes.get(guild_id, ['?', '!'])

    # async def set_guild_prefixes(self, guild: discord.abc.Snowflake, prefixes: list[str]) -> None:
    #     if len(prefixes) == 0:
    #         await self.prefixes.put(guild.id, [])
    #     elif len(prefixes) > 10:
    #         raise RuntimeError('Cannot have more than 10 custom prefixes.')
    #     else:
    #         await self.prefixes.put(guild.id, sorted(set(prefixes), reverse=True))

    async def add_to_blacklist(self, object_id: int):
        await self.blacklist.put(object_id, True)

    async def remove_from_blacklist(self, object_id: int):
        try:
            await self.blacklist.remove(object_id)
        except KeyError:
            pass

    async def query_member_named(
            self, guild: discord.Guild, argument: str, *, cache: bool = False
    ) -> Optional[discord.Member]:
        """Queries a member by their name, name + discrim, or nickname.


        Args:
            guild (discord.Guild): The guild to query the member in.
            argument (str): The name, nickname, or name + discrim combo to check.
            cache (bool, optional): Whether to cache the results of the query. Defaults to False.

        Returns:
            Optional[discord.Member]: The member matching the query or None if not found.
        """

        if len(argument) > 5 and argument[-5] == '#':
            username, _, discrim = argument.rpartition('#')
            members = await guild.query_members(username, limit=100, cache=cache)
            return discord.utils.get(members, name=username, discriminator=discrim)
        else:
            members = await guild.query_members(argument, limit=100, cache=cache)
            return discord.utils.find(lambda m: m.name == argument or m.nick == argument, members)

    async def get_or_fetch_member(self, guild: discord.Guild, member_id: int) -> Optional[discord.Member]:
        """Looks up a member in cache or fetches if not found.
        Args:
        guild (discord.Guild): The guild to look in.
        member_id int: The member ID to search for.

        Returns:
        Optional[discord.Member]: The member or None if not found.
        """

        member = guild.get_member(member_id)
        if member is not None:
            return member

        shard: discord.ShardInfo = self.get_shard(
            guild.shard_id)  # type: ignore  # will never be None
        if shard.is_ws_ratelimited():
            try:
                member = await guild.fetch_member(member_id)
            except discord.HTTPException:
                return None
            else:
                return member

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        if not members:
            return None
        return members[0]

    async def resolve_member_ids(self, guild: discord.Guild, member_ids: Iterable[int]) -> AsyncIterator[discord.Member]:
        """Bulk resolves member IDs to member instances, if possible.
        Members that can't be resolved are discarded from the list.
        This is done lazily using an asynchronous iterator.
        Note that the order of the resolved members is not the same as the input.

        Args
        guild discord.Guild: The guild to resolve from.
        member_ids Iterable[int]: An iterable of member IDs.

        Yields:
        discord.Member: The resolved members.
        """

        needs_resolution = []
        for member_id in member_ids:
            member = guild.get_member(member_id)
            if member is not None:
                yield member
            else:
                needs_resolution.append(member_id)

        total_need_resolution = len(needs_resolution)
        if total_need_resolution == 1:
            shard: discord.ShardInfo = self.get_shard(
                guild.shard_id)  # type: ignore  # will never be None
            if shard.is_ws_ratelimited():
                try:
                    member = await guild.fetch_member(needs_resolution[0])
                except discord.HTTPException:
                    pass
                else:
                    yield member
            else:
                members = await guild.query_members(limit=1, user_ids=needs_resolution, cache=True)
                if members:
                    yield members[0]
        elif total_need_resolution <= 100:
            # Only a single resolution call needed here
            resolved = await guild.query_members(limit=100, user_ids=needs_resolution, cache=True)
            for member in resolved:
                yield member
        else:
            # We need to chunk these in bits of 100...
            for index in range(0, total_need_resolution, 100):
                to_resolve = needs_resolution[index: index + 100]
                members = await guild.query_members(limit=100, user_ids=to_resolve, cache=True)
                for member in members:
                    yield member

    async def on_ready(self) -> None:
        if not hasattr(self, 'uptime'):
            self.uptime = discord.utils.utcnow()

        print(f'Ready: {self.user} (ID: {self.user.id})')
        print(f'In {len(self.guilds)} guilds.')

    async def on_shard_resumed(self, shard_id) -> None:
        print(f'Shard ID {shard_id} has resumed...')
        self.resumes[shard_id].append(discord.utils.utcnow())

    async def on_shard_resumed(self, shard_id) -> None:
        print(f'Shard ID {shard_id} has resumed...')
        self.resumes[shard_id].append(discord.utils.utcnow())

    @discord.utils.cached_property
    def stats_webhook(self) -> None:
        wh_id, wh_token = self.config.stat_webhook
        hook = discord.Webhook.partial(
            id=wh_id, token=wh_token, session=self.session)
        return hook

    async def log_spammer(
        self, ctx: Context, message: discord.Message, retry_after: float, *, autoblock: bool = False
    ) -> Optional[discord.Webhook]:
        guild_name = getattr(ctx.guild, 'name', "No Guild (DM's)")
        guild_id = getattr(ctx.guild, 'id', None)

        fmt = 'User %s (ID %s) in guild %r (ID %s) spamming, retry_after: %.2fs'
        log.warning(fmt, message.author, message.author.id,
                    guild_name, guild_id, retry_after)
        if not autoblock:
            return

        wh = self.stats_webhook
        embed = discord.Embed(title='Auto-blocked Member', colour=0xDDA453)
        embed.add_field(
            name='Member', value=f'{message.author} (ID: {message.author.id})', inline=False)
        embed.add_field(name='Guild Info',
                        value=f'{guild_name} (ID: {guild_id})', inline=False)
        embed.add_field(
            name='Channel Info', value=f'{message.channel} (ID: {message.channel.id}', inline=False)
        embed.timestamp = discord.utils.utcnow()
        return await wh.send(embed=embed)

    async def get_context(self, origin: Union[discord.Interaction, discord.Message], /, *, cls=Context) -> Context:
        return await super().get_context(origin, cls=cls)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        await self.process_commands(message)

    async def process_commands(self, message: discord.Message) -> None:
        ctx = await self.get_context(message)

        if ctx.command is None:
            return

        if ctx.author.id in self.blacklist:
            return

        if ctx.guild is not None and ctx.guild.id in self.blacklist:
            return

        bucket = self.spam_control.get_bucket(message)
        current = message.created_at.timestamp()
        retry_after = bucket.update_rate_limit(current)
        author_id = message.author.id

        if retry_after and author_id != self.owner_id:
            self._auto_spam_count[author_id] += 1
            if self._auto_spam_count[author_id] >= 10:
                await self.add_to_blacklist(author_id)
                del self._auto_spam_count[author_id]
                await self.log_spammer(ctx, message, retry_after, autoblock=True)
            else:
                await self.log_spammer(ctx, message, retry_after)
            return
        else:
            self._auto_spam_count.pop(author_id, None)

        try:
            await self.invoke(ctx)
        finally:
            await ctx.release()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        if guild.id in self.blacklist:
            await guild.leave()

    async def close(self) -> None:
        await super().close()
        await self.session.close()

    async def start(self) -> None:
        try:
            await super().start(config.token, reconnect=True)
        except Exception as e:
            print(e)

    @property
    def config(self):
        return __import__('main.settings.config')
