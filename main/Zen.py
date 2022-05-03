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

    def __init__(self):
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
        # TODO: Fix this
        self.prefixes: list[str] = ['~']
