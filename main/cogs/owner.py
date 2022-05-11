#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations

# Standard library imports
import logging

from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, Mapping, Optional

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands

# Local application imports
import main.cogs.utils.formats as formats


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread


log = logging.getLogger(__name__)

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Owner
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


class Owner(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot

    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(hidden=True)
    async def load(self, ctx: Context, *, cog: str) -> None:
        """Loads a Cog"""
        try:
            await self.bot.load_extension(cog)
        except commands.ExtensionError as e:
            await ctx.reply(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def unload(self, ctx: Context, *, cog: str) -> None:
        """Unloads a Cog"""
        try:
            await self.bot.unload_extension(f'main.cogs.{cog}')
        except commands.ExtensionError as e:
            await ctx.reply(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def reload(self, ctx: Context, *, cog: str) -> None:
        try:
            await self.bot.reload_extension(f'main.cogs.{cog}')
        except commands.ExtensionError as e:
            await ctx.reply(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def reload_all(self, ctx: Context) -> None:
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

    @commands.command(hidden=True)
    @commands.guild_only()
    async def leave(self, ctx: Context) -> None:
        """Makes the bot leave the current guild."""
        assert ctx.guild is not None
        await ctx.guild.leave()

    @commands.command()
    @commands.guild_only()
    async def sync(
        self,
        ctx: Context,
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal['~', '*']] = None
    ) -> None:

        assert ctx.guild is not None

        if not guilds:
            if spec == '~':
                fmt = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == '*':
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                fmt = await ctx.bot.tree.sync(guild=ctx.guild)
            else:
                fmt = await ctx.bot.tree.sync()

            await ctx.reply(
                f"Synced {formats.Plural(len(fmt)):command} {'globally' if spec is None else 'to the current guild.'}"
            )

            return

        fmt = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                fmt += 1

        await ctx.reply(f"Synced tree to {formats.Plural(fmt):guild}.")


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen) -> None:
    await bot.add_cog(Owner(bot))
