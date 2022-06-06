#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations

# Standard library imports
import asyncio
import io
import logging
import subprocess
import textwrap
import time
import traceback

from asyncpg import Record
from contextlib import redirect_stdout
from types import ModuleType
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal, Mapping, Optional, Union

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands

# Local application imports
import main.cogs.utils.formats as formats
from main.cogs.utils.formats import TabularData, Plural


if TYPE_CHECKING:
    from main.Zen import Zen
    from main.cogs.utils.context import Context


GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread


log = logging.getLogger(__name__)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Owner
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Owner(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot
        self._last_result: Optional[Any] = None
        self.sessions: set[int] = set()

    # -------------------------------------------------------
    #                    Cog Functions
    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    # -------------------------------------------------------
    #                   Helper Functions
    def cleanup_code(self, content: str) -> str:
        """Automatically removes code blocks from the code."""
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    async def run_process(self, command: str) -> list[str]:
        try:
            process = await asyncio.create_subprocess_shell(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            result = await process.communicate()

        except NotImplementedError:
            process = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]

    def get_syntax_error(self, e: SyntaxError) -> str:
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'

        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'

    # -------------------------------------------------------
    #                     Commands

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
        """ Reload a Cog"""
        try:
            await self.bot.reload_extension(f'main.cogs.{cog}')
        except commands.ExtensionError as e:
            await ctx.reply(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def reload_all(self, ctx: Context) -> None:
        """ Reload All Cogs"""

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
        """ Sync bot to all channels"""

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

    @commands.command(hidden=True)
    async def sql(self, ctx: Context, *, query: str):
        """Run some SQL."""
        query = self.cleanup_code(query)

        is_multistatement = query.count(';') > 1
        strategy: Callable[[str],
                           Union[Awaitable[list[Record]], Awaitable[str]]]
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = ctx.db.execute
        else:
            strategy = ctx.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if isinstance(results, str) or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`')

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {Plural(rows):row} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

    @commands.command(hidden=True, name='eval')
    async def _eval(self, ctx: Context, *, body: str) -> None:
        """ Evaluates code """

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, " ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

        if ret is None:
            if value:
                await ctx.send(f'```py\n{value}\n```')
        else:
            self._last_result = ret
            await ctx.send(f'```py\n{value}{ret}\n```')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen) -> None:
    await bot.add_cog(Owner(bot))
