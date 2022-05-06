#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations

# Standard library imports
from types import ModuleType
from typing import TYPE_CHECKING, Any, Mapping, Optional, Union

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands

# Local application imports


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Owner
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Owner(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(hidden=True)
    async def load_cog(self, ctx: Context, *, cog: str) -> None:
        """Loads a Cog"""
        try:
            await self.bot.load_extension(cog)
        except commands.ExtensionError as e:
            await ctx.reply(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def unload_cog(self, ctx: Context, *, cog: str) -> None:
        """Unloads a Cog"""
        try:
            await self.bot.unload_extension(f'main.cogs.{cog}')
        except commands.ExtensionError as e:
            await ctx.reply(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def reload_cog(self, ctx: Context, *, cog: str) -> None:
        try:
            await self.bot.reload_extension(f'main.cogs.{cog}')
        except commands.ExtensionError as e:
            await ctx.reply(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def reload_all_cogs(self, ctx: Context) -> None:
        cogs: Mapping[str, ModuleType] = self.bot.extensions
        msg = ''

        for key in list(cogs.keys()):
            try:
                await self.bot.reload_extension(key)
            except commands.ExtensionError as e:
                msg += f'{e.__class__.__name__}: {e}\n'
                continue

        if len(msg) > 0:
            await ctx.reply(msg)

        await ctx.message.add_reaction('\N{OK HAND SIGN}')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen) -> None:
    await bot.add_cog(Owner(bot))
