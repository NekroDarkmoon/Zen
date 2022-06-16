#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations

# Standard library imports
import datetime
import logging
import inspect
import itertools

from collections import Counter
from typing import TYPE_CHECKING, Any, Optional, Union
import asyncpg

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import menus


# Local application imports
from main.cogs.utils import formats, time
from main.cogs.utils.context import Context, GuildContext
from main.cogs.utils.paginator import ZenPages


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                  Group Help Page Source
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GroupHelpPageSource(menus.ListPageSource):
    def __init__(
        self,
        group: Union[commands.Group,
                     commands.Cog],
        commands: list[commands.Command],
        *,
        prefix: str
    ) -> None:
        super().__init__(entries=commands, per_page=6)
        self.group: Union[commands.Group, commands.Cog] = group
        self.prefix: str = prefix
        self.title: str = f'{self.group.qualified_name} Commands'
        self.description: str = self.group.description

    async def format_page(self, menu: ZenPages, commands: list[commands.Command]):
        embed = discord.Embed(
            title=self.title, description=self.description, colour=discord.Colour(0xA8B9CD))

        for command in commands:
            signature = f'{command.qualified_name} {command.signature}'
            embed.add_field(
                name=signature, value=command.short_doc or 'No help given...', inline=False)

        maximum = self.get_max_pages()
        if maximum > 1:
            embed.set_author(
                name=f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} commands)')

        embed.set_footer(
            text=f'Use "{self.prefix}help command" for more info on a command.')
        return embed


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                     Help Select Menu
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class HelpSelectMenu(discord.ui.Select['HelpMenu']):
    def __init__(self, commands: dict[commands.Cog, list[commands.Command]], bot: Zen):
        super().__init__(
            placeholder='Select a category...',
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands: dict[commands.Cog, list[commands.Command]] = commands
        self.bot: Zen = bot
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label='Index',
            emoji='\N{WAVING HAND SIGN}',
            value='__index',
            description='The help page showing how to use the bot.',
        )
        for cog, commands in self.commands.items():
            if not commands:
                continue
            description = cog.description.split('\n', 1)[0] or None
            emoji = getattr(cog, 'display_emoji', None)
            self.add_option(label=cog.qualified_name, value=cog.qualified_name,
                            description=description, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == '__index':
            await self.view.rebind(FrontPageSource(), interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message('Somehow this category does not exist?', ephemeral=True)
                return

            commands = self.commands[cog]
            if not commands:
                await interaction.response.send_message('This category has no commands for you', ephemeral=True)
                return

            source = GroupHelpPageSource(
                cog, commands, prefix=self.view.ctx.clean_prefix)
            await self.view.rebind(source, interaction)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                       Front Page Source
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FrontPageSource(menus.PageSource):
    def is_paginating(self) -> bool:
        # This forces the buttons to appear even in the front page
        return True

    def get_max_pages(self) -> Optional[int]:
        # There's only one actual page in the front page
        # However we need at least 2 to show all the buttons
        return 2

    async def get_page(self, page_number: int) -> Any:
        # The front page is a dummy
        self.index = page_number
        return self

    def format_page(self, menu: HelpMenu, page: Any):
        embed = discord.Embed(
            title='Bot Help', colour=discord.Colour(0xA8B9CD))
        embed.description = inspect.cleandoc(
            f"""
            Hello! Welcome to the help page.
            Use "{menu.ctx.clean_prefix}help command" for more info on a command.
            Use "{menu.ctx.clean_prefix}help category" for more info on a category.
            Use the dropdown menu below to select a category.
        """
        )

        if self.index == 0:
            embed.add_field(
                name='Who are you?',
                value=('Someone'),
                inline=False,
            )
        elif self.index == 1:
            entries = (
                ('<argument>', 'This means the argument is __**required**__.'),
                ('[argument]', 'This means the argument is __**optional**__.'),
                ('[A|B]', 'This means that it can be __**either A or B**__.'),
                (
                    '[argument...]',
                    'This means you can have multiple arguments.\n'
                    'Now that you know the basics, it should be noted that...\n'
                    '__**You do not type in the brackets!**__',
                ),
            )

            embed.add_field(name='How do I use this bot?',
                            value='Reading the bot signature is pretty simple.')

            for name, value in entries:
                embed.add_field(name=name, value=value, inline=False)

        return embed


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                        Help Menu
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class HelpMenu(ZenPages):
    def __init__(self, source: menus.PageSource, ctx: Context) -> None:
        super().__init__(source, ctx=ctx, compact=True)

    def add_categories(self, commands: dict[commands.Cog, list[commands.Command]]) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(commands, self.ctx.bot))
        self.fill_items()

    async def rebind(self, source: menus.PageSource, interaction: discord.Interaction) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                  Paginated Help Command
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PaginatedHelpCommand(commands.HelpCommand):
    context: Context

    def __init__(self):
        super().__init__(
            command_attrs={
                'cooldown': commands.CooldownMapping.from_cooldown(1, 3.0, commands.BucketType.member),
                'help': 'Shows help about the bot, a command, or a category',
            }
        )

    async def on_help_command_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.CommandInvokeError):
            # Ignore missing permission errors
            if isinstance(error.original, discord.HTTPException) and error.original.code == 50013:
                return

            await ctx.send(str(error.original))

    def get_command_signature(self, command: commands.Command) -> str:
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = f'[{command.name}|{aliases}]'
            if parent:
                fmt = f'{parent} {fmt}'
            alias = fmt
        else:
            alias = command.name if not parent else f'{parent} {command.name}'
        return f'{alias} {command.signature}'

    async def send_bot_help(self, mapping):
        bot = self.context.bot

        def key(command) -> str:
            cog = command.cog
            return cog.qualified_name if cog else '\U0010ffff'

        entries: list[commands.Command] = await self.filter_commands(bot.commands, sort=True, key=key)

        all_commands: dict[commands.Cog, list[commands.Command]] = {}
        for name, children in itertools.groupby(entries, key=key):
            if name == '\U0010ffff':
                continue

            cog = bot.get_cog(name)
            assert cog is not None
            all_commands[cog] = sorted(
                children, key=lambda c: c.qualified_name)

        menu = HelpMenu(FrontPageSource(), ctx=self.context)
        menu.add_categories(all_commands)
        await self.context.release()
        await menu.start()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(GroupHelpPageSource(
            cog, entries, prefix=self.context.clean_prefix), ctx=self.context)
        await self.context.release()
        await menu.start()

    def common_command_formatting(self, embed_like, command):
        embed_like.title = self.get_command_signature(command)
        if command.description:
            embed_like.description = f'{command.description}\n\n{command.help}'
        else:
            embed_like.description = command.help or 'No help found...'

    async def send_command_help(self, command):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour(0xA8B9CD))
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(
            group, entries, prefix=self.context.clean_prefix)
        self.common_command_formatting(source, group)
        menu = HelpMenu(source, ctx=self.context)
        await self.context.release()
        await menu.start()


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                        Meta Cog
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Meta(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot
        self.old_help_command: Optional[commands.HelpCommand] = bot.help_command
        bot.help_command = PaginatedHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = self.old_help_command

    async def cog_command_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))

    @commands.command()
    async def ping(self, ctx: Context) -> None:
        """Ping commands are stupid."""
        await ctx.send("Ping commands are stupid.")

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #                 Info Commands
    @commands.hybrid_group(invoke_without_command=True)
    async def info(self, ctx: Context) -> None:
        """ Display information related to the target. """

        if ctx.invoked_subcommand is None:
            await ctx.send_help('info')

    @info.command('avatar')
    @app_commands.describe(user='Selected User')
    async def user_avatar(
        self, ctx: Context, user: discord.Member | discord.User
    ) -> None:
        """Shows a user's enlarged avatar (if possible)."""
        # Databuilder
        user = user or ctx.author
        avatar = user.display_avatar.with_static_format('png')

        e = discord.Embed()
        e.set_author(name=str(user), url=avatar)
        e.set_image(url=avatar)
        await ctx.send(embed=e)

    @info.command('user')
    @app_commands.describe(user='Selected User')
    async def user_info(
        self, ctx: Context, user: discord.Member | discord.User
    ) -> None:
        """ Display Information about a user. """
        await ctx.typing()

        # Data builder
        user = user or ctx.author
        roles = [role.name.replace('@', '@\u200b')
                 for role in getattr(user, 'roles', [])]

        def format_date(dt: datetime.datetime) -> str:
            if dt is None:
                return "N/A"
            return f'{time.format_dt(dt, "F")} ({time.format_relative(dt)})'

        e = discord.Embed()
        e.set_author(name=str(user))
        e.add_field(name='ID', value=user.id, inline=False)
        e.add_field(name='Joined', value=format_date(
            getattr(user, 'joined_at', None)), inline=False)
        e.add_field(name='Created', value=format_date(
            user.created_at), inline=False)

        voice = getattr(user, 'voice', None)
        if voice is not None:
            vc = voice.channel
            other_people = len(vc.members) - 1
            voice = f'{vc.name} with {other_people} others' if other_people else f'{vc.name} by themselves'
            e.add_field(name='Voice', value=voice, inline=False)

        if roles:
            e.add_field(name='Roles', value=', '.join(roles) if len(
                roles) < 10 else f'{len(roles)} roles', inline=False)

        colour = user.colour
        if colour.value:
            e.colour = colour

        sql = '''SELECT channel_id, last_msg FROM logger
                 WHERE server_id=$1 AND user_id=$2
              '''
        record: asyncpg.Record = await self.bot.pool.fetchrow(
            sql, ctx.guild.id, user.id
        )

        if record is not None:
            val = f'{time.format_relative(record["last_msg"])}'
            val += f' in {ctx.guild.get_channel(record["channel_id"]).mention}'
            e.add_field(name='Last Message', value=val, inline=False)

        if user.display_avatar:
            e.set_thumbnail(url=user.display_avatar)

        if isinstance(user, discord.User):
            e.set_footer(text='This member is not in this server.')

        await ctx.send(embed=e)

    @info.command('server')
    @app_commands.describe(idx='Guild ID')
    async def server_info(
        self, ctx: GuildContext, idx: Optional[int]
    ) -> None:
        """ Shows information about the server."""
        await ctx.typing()

        if idx is not None and await self.bot.is_owner(ctx.author):
            guild = self.bot.get_guild(idx)
            if guild is None:
                return await ctx.send(f'Invalid Guild ID given.')

        else:
            guild = ctx.guild

        roles = [role.name.replace('@', '@\u200b') for role in guild.roles]

        if not guild.chunked:
            await guild.chunk(cache=True)

        # Get Channel counts
        everyone = guild.default_role
        everyone_perms = everyone.permissions.value
        secret = Counter()
        totals = Counter()
        for channel in guild.channels:
            allow, deny = channel.overwrites_for(everyone).pair()
            perms = discord.Permissions(
                (everyone_perms & ~deny.value) | allow.value)
            channel_type = type(channel)
            totals[channel_type] += 1
            if not perms.read_messages:
                secret[channel_type] += 1
            elif isinstance(channel, discord.VoiceChannel) and (not perms.connect or not perms.speak):
                secret[channel_type] += 1

        e = discord.Embed(title=guild.name, colour=discord.Color.random())
        e.description = f'**ID**: {guild.id}\n**Owner**: {guild.owner}'

        if guild.icon:
            e.set_thumbnail(url=guild.icon.url)

        channel_info = list()
        key_to_emoji = {
            discord.TextChannel: '<:text_channel:586339098172850187>',
            discord.VoiceChannel: '<:voice_channel:586339098524909604>',
        }

        for key, total in totals.items():
            secrets = secret[key]
            try:
                emoji = key_to_emoji[key]
            except KeyError:
                continue

            if secrets:
                channel_info.append(f'{emoji} {total} ({secrets} locked)')
            else:
                channel_info.append(f'{emoji} {total}')

        info = list()
        features = set(guild.features)
        all_features = {
            'ANIMATED_ICON': 'Animated Icon',
            'BANNER': 'Banner',
            'COMMERCE': 'Commerce',
            'COMMUNITY': 'Community Server',
            'DISCOVERABLE': 'Server Discovery',
            'FEATURABLE': 'Featured',
            'INVITE_SPLASH': 'Invite Splash',
            'NEWS': 'News Channels',
            'PARTNERED': 'Partnered',
            'VANITY_URL': 'Vanity Invite',
            'VERIFIED': 'Verified',
            'VIP_REGIONS': 'VIP Voice Servers',
            'WELCOME_SCREEN_ENABLED': 'Welcome Screen',
            'LURKABLE': 'Lurkable',
            'TICKETED_EVENTS_ENABLED': 'Ticketed Events',
            'MONETIZATION_ENABLED': 'Monetization Enabled',
            'THREE_DAY_THREAD_ARCHIVE': 'Thread Archive Time - 3 Days',
            'SEVEN_DAY_THREAD_ARCHIVE': 'Thread Archive Time - 7 Days',
            'PRIVATE_THREADS': 'Private Threads',
            'ROLE_ICONS': 'Role Icons',
        }

        for feature, label in all_features.items():
            if feature in features:
                info.append(f'{ctx.tick(True)}: {label}')

        if info:
            e.add_field(name='Features', value='\n'.join(info))

        e.add_field(name='Channels', value='\n'.join(channel_info))

        if guild.premium_tier != 0:
            boosts = f'Level {guild.premium_tier}\n{guild.premium_subscription_count} boosts'
            last_boost = max(
                guild.members, key=lambda m: m.premium_since or guild.created_at)
            if last_boost.premium_since is not None:
                boosts = f'{boosts}\nLast Boost: {last_boost} ({time.format_relative(last_boost.premium_since)})'
            e.add_field(name='Boosts', value=boosts, inline=False)

        bots = sum(m.bot for m in guild.members)
        fmt = f'Total: {guild.member_count} ({formats.Plural(bots):bot})'

        e.add_field(name='Members', value=fmt, inline=False)
        e.add_field(name='Roles', value=', '.join(roles)
                    if len(roles) < 10 else f'{len(roles)} roles')

        emoji_stats = Counter()
        for emoji in guild.emojis:
            if emoji.animated:
                emoji_stats['animated'] += 1
                emoji_stats['animated_disabled'] += not emoji.available
            else:
                emoji_stats['regular'] += 1
                emoji_stats['disabled'] += not emoji.available

        fmt = (
            f'Regular: {emoji_stats["regular"]}/{guild.emoji_limit}\n'
            f'Animated: {emoji_stats["animated"]}/{guild.emoji_limit}\n'
        )
        if emoji_stats['disabled'] or emoji_stats['animated_disabled']:
            fmt = f'{fmt}Disabled: {emoji_stats["disabled"]} regular, {emoji_stats["animated_disabled"]} animated\n'

        fmt = f'{fmt}Total Emoji: {len(guild.emojis)}/{guild.emoji_limit*2}'
        e.add_field(name='Emoji', value=fmt, inline=False)
        e.set_footer(text='Created').timestamp = guild.created_at
        await ctx.send(embed=e)

    @info.command('self')
    async def self_info(
        self, ctx: Context
    ) -> None:
        pass

    @info.command('role')
    @app_commands.describe(role='Selected Role')
    async def role_info(
        self, ctx: GuildContext, role: discord.Role
    ) -> None:
        pass

    @info.command('channel')
    @app_commands.describe(channel='Selected Channel')
    async def channel_info(
        self, ctx: GuildContext, channel: GuildChannel
    ) -> None:
        pass

    @info.command('permissions')
    @app_commands.describe(member='Selected Member', channel='Selected Channel')
    async def permissions(
        self,
        ctx: GuildContext,
        member: Optional[discord.Member] = None,
        channel: Optional[GuildChannel] = None
    ) -> None:
        pass
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


async def setup(bot: Zen) -> None:
    await bot.add_cog(Meta(bot))
