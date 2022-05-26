# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
from datetime import datetime
import logging

from typing import TYPE_CHECKING, Optional, TypedDict

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
NOT_ENABLED = 'Error - System Not Enabled.'
SYSTEM = 'game'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Game
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class multiMemberTransformer(app_commands.Transformer):
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
        """ Creates a game channel """
        pass

    # __________________ Game Enabled __________________
    @channels_group.command(name='delete')
    @app_commands.describe(name='Name of the channel.')
    async def delete_game_channel(
        self,
        interaction: discord.Interaction,
        name: str
    ) -> None:
        """ Deletes a game channel """
        pass

    # __________________ Game Enabled __________________
    @channels_group.command(name='add')
    @app_commands.describe(channel='Add to channel.', users='List of users.')
    async def add_to_game_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        users: app_commands.Transform[list[discord.Member], multiMemberTransformer],
    ) -> None:
        print(users)

        pass

    # __________________ Game Enabled __________________
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
