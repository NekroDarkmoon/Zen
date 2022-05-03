# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Standard library imports
import chunk
import aiohttp
import asyncpg
import datetime
import json
import logging
import os
import sys
import traceback

from collections import defaultdict, Counter
from typing import Any

# Third party imports
import discord
from discord import gateway
from discord import user
from discord import guild  # noqa
from discord import app_commands
from discord.ext import commands

# Local application imports
from cogs.utils.config import Config

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


class Zen(commands.Bot):
    user: discord.ClientUser
    session: aiohttp.ClientSession
    # pool: asyncpg.Pool
    command_stats: Counter[str]
    socket_stats: Counter[Any]
    gateway_handler: Any
    bot_app_info: discord.AppInfo

    def __init__(self) -> None:
        allowed_mentions = discord.AllowedMentions(
            roles=False, everyone=False, users=True)
        intents = discord.Intents.all()
        super().__init__(
            command_prefix='~',
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

        self.client_id: str = self.config['client_id']
        self.resumes: defaultdict[int,
                                  list[datetime.datetime]] = defaultdict(list)
        self.indentifies: defaultdict[int,
                                      list[datetime.datetime]] = defaultdict(list)

        self.spam_control = commands.CooldownMapping.from_cooldown(
            10, 12.0, commands.BucketType.user)

        self._auto_spam_count = Counter()
        self.command_stats = Counter()
        self.socket_stats = Counter()

    async def start(self) -> None:
        try:
            await super().start(self.configs['token'], reconnect=True)
        except Exception as e:
            print(e)

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.prefixes: Config[list[str]] = Config(
            'main/settings/prefixes.json', loop=self.loop)
        self.blacklist: Config[bool] = Config(
            'main/settings/blacklist.json', loop=self.loop)

        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.owner.id

        # Load Extensions
        for cog in [file.split('.')[0] for file in os.listdir('main/cogs') if file.endswith('.py')]:
            try:
                if cog != '__init__':
                    self.load_extension(f'main.cogs.{cog}')
                    print(f'Loaded cog {cog}')
            except Exception as e:
                print(f'Failed to load cog {cog}.', file=sys.stderr)
                traceback.print_exc()

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
