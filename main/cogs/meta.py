#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations

# Standard library imports
import datetime
import inspect
import itertools
import logging
import os
from collections import Counter
from typing import TYPE_CHECKING, Any, Optional, Union

import asyncpg

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands, menus

# Local application imports
from main.cogs.utils import formats, time
from main.cogs.utils.context import Context, GuildContext
from main.cogs.utils.paginator import TabularPages, ZenPages

if TYPE_CHECKING:
    from utils.context import Context

    from main.Zen import Zen

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                  Group Help Page Source
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GroupHelpPageSource(menus.ListPageSource):
    def __init__(self, group: Union[commands.Group, commands.Cog], entries: list[commands.Command], *, prefix: str) -> None:
        super().__init__(entries=entries, per_page=6)
        self.group: Union[commands.Group, commands.Cog] = group
        self.prefix: str = prefix
        self.title: str = f'{self.group.qualified_name} Commands'
        self.description: str = self.group.description

    async def format_page(self, menu: ZenPages, commands: list[commands.Command]) -> discord.Embed:
        embed = discord.Embed(title=self.title, description=self.description, colour=discord.Colour.random())

        for command in commands:
            signature = f'{command.qualified_name} {command.signature}'
            embed.add_field(name=signature, value=command.short_doc or 'No help given...', inline=False)

        maximum = self.get_max_pages()
        if maximum > 1:
            embed.set_author(name=f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} commands)')

        embed.set_footer(text=f'Use "{self.prefix}help command" for more info on a command.')

        return embed


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                     Help Select Menu
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class HelpSelectMenu(discord.ui.Select['HelpMenu']):
    def __init__(self, entries: dict[commands.Cog, list[commands.Command]], bot: Zen):
        super().__init__(
            placeholder='Select a category...',
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands: dict[commands.Cog, list[commands.Command]] = entries
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
            self.add_option(label=cog.qualified_name, value=cog.qualified_name, description=description, emoji=emoji)

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

            source = GroupHelpPageSource(cog, commands, prefix=self.view.ctx.clean_prefix)
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

    def format_page(self, menu: HelpMenu, page: Any) -> discord.Embed:
        embed = discord.Embed(title='Bot Help', colour=discord.Colour.random())
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

            embed.add_field(name='How do I use this bot?', value='Reading the bot signature is pretty simple.')

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
            all_commands[cog] = sorted(children, key=lambda c: c.qualified_name)

        menu = HelpMenu(FrontPageSource(), ctx=self.context)
        menu.add_categories(all_commands)
        await menu.start()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(GroupHelpPageSource(cog, entries, prefix=self.context.clean_prefix), ctx=self.context)
        await menu.start()

    def common_command_formatting(self, embed_like, command):
        embed_like.title = self.get_command_signature(command)
        if command.description:
            embed_like.description = f'{command.description}\n\n{command.help}'
        else:
            embed_like.description = command.help or 'No help found...'

    async def send_command_help(self, command):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour.random())
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(group, entries, prefix=self.context.clean_prefix)
        self.common_command_formatting(source, group)
        menu = HelpMenu(source, ctx=self.context)

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

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #                 Cog Functions
    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{WHITE QUESTION MARK ORNAMENT}')

    def cog_unload(self) -> None:
        self.bot.help_command = self.old_help_command

    async def cog_command_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))

    @commands.hybrid_command()
    async def ping(self, ctx: Context) -> None:
        """Ping commands are stupid."""
        await ctx.send("Ping commands are stupid.")

    @commands.hybrid_command()
    async def source(self, ctx: Context, *, command: str = "") -> None:
        """Displays my full source code or for a specific command.

        To display the source code of a subcommand you can separate it by
        periods, e.g. tag.create for the create subcommand of the tag command
        or by spaces.
        """
        source_url = 'https://github.com/NekroDarkmoon/Zen'
        branch = 'main'
        if len(command) == 0:
            return await ctx.send(source_url)  # type: ignore

        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
        else:
            obj = self.bot.get_command(command.replace('.', ' '))
            if obj is None:
                await ctx.send('Could not find command.')
                return

            # since we found the command we're looking for, presumably anyway, let's
            # try to access the code itself
            src = obj.callback.__code__
            module = obj.callback.__module__
            filename = src.co_filename

        lines, first_line_no = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            if filename is None:
                await ctx.send('Could not find source for command.')
                return

            location = os.path.relpath(filename).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'
            source_url = 'https://github.com/Rapptz/discord.py'
            branch = 'master'

        final_url = f'<{source_url}/blob/{branch}/{location}#L{first_line_no}-L{first_line_no + len(lines) - 1}>'
        await ctx.send(final_url)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #                 Info Commands
    @commands.hybrid_group(invoke_without_command=True)
    async def info(self, ctx: Context) -> None:
        """Display information related to the target."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help('info')

    @info.command('avatar')
    @app_commands.describe(user='Selected User')
    async def user_avatar(self, ctx: Context, user: discord.Member | discord.User) -> None:
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
    async def user_info(self, ctx: Context, *, user: discord.Member | discord.User = None) -> None:
        """Display Information about a user."""
        await ctx.typing()

        if ctx.guild is None:
            await ctx.send(content='This command is not available in DMs.')
            return

        # Data builder
        user = user or ctx.author
        roles = [role.name.replace('@', '@\u200b') for role in getattr(user, 'roles', [])]

        def format_date(dt: datetime.datetime) -> str:
            if dt is None:
                return "N/A"
            return f'{time.format_dt(dt, "F")} ({time.format_relative(dt)})'

        e = discord.Embed()
        e.set_author(name=str(user))
        e.add_field(name='ID', value=user.id, inline=False)
        e.add_field(name='Joined', value=format_date(getattr(user, 'joined_at', None)), inline=False)  # type: ignore
        e.add_field(name='Created', value=format_date(user.created_at), inline=False)

        badges_to_emoji = {
            'partner': '<:partnernew:754032603081998336>',  # Discord Bots
            'verified_bot_developer': '<:verifiedbotdev:853277205264859156>',  # Discord Bots
            'hypesquad_balance': '<:balance:585763004574859273>',  # Discord Bots
            'hypesquad_bravery': '<:bravery:585763004218343426>',  # Discord Bots
            'hypesquad_brilliance': '<:brilliance:585763004495298575>',  # Discord Bots
            'bug_hunter': '<:bughunter:585765206769139723>',  # Discord Bots
            'hypesquad': '<:hypesquad_events:585765895939424258>',  # Discord Bots
            'early_supporter': ' <:supporter:585763690868113455> ',  # Discord Bots
            'bug_hunter_level_2': '<:goldbughunter:853274684337946648>',  # Discord Bots
            'staff': '<:staff_badge:1087023029105725481>',  # R. Danny
            'discord_certified_moderator': '<:certified_mod_badge:1087023030431129641>',  # R. Danny
            'active_developer': '<:active_developer:1087023031332900894>',  # R. Danny
        }

        misc_flags_descriptions = {
            'team_user': 'Application Team User',
            'system': 'System User',
            'spammer': 'Spammer',
            'verified_bot': 'Verified Bot',
            'bot_http_interactions': 'HTTP Interactions Bot',
        }

        set_flags = {flag for flag, value in user.public_flags if value}
        subset_flags = set_flags & badges_to_emoji.keys()
        badges = [badges_to_emoji[flag] for flag in subset_flags]

        if ctx.guild is not None and ctx.guild.owner_id == user.id:
            badges.append('<:owner:585789630800986114>')  # Discord Bots

        if isinstance(user, discord.Member) and user.premium_since is not None:
            e.add_field(name='Boosted', value=format_date(user.premium_since), inline=False)
            badges.append('<:booster:1087022965775925288>')  # R. Danny

        if badges:
            e.description = ''.join(badges)

        voice = getattr(user, 'voice', None)
        if voice is not None:
            vc = voice.channel
            other_people = len(vc.members) - 1
            voice = f'{vc.name} with {other_people} others' if other_people else f'{vc.name} by themselves'
            e.add_field(name='Voice', value=voice, inline=False)

        if roles:
            e.add_field(name='Roles', value=', '.join(roles) if len(roles) < 10 else f'{len(roles)} roles', inline=False)

        remaining_flags = (set_flags - subset_flags) & misc_flags_descriptions.keys()
        if remaining_flags:
            e.add_field(
                name='Public Flags',
                value='\n'.join(misc_flags_descriptions[flag] for flag in remaining_flags),
                inline=False,
            )

        color = user.color
        if color.value:
            e.color = color

        sql = '''SELECT channel_id, last_msg FROM logger
                 WHERE server_id=$1 AND user_id=$2
              '''
        record: asyncpg.Record = await self.bot.pool.fetchrow(sql, ctx.guild.id, user.id)

        if record is not None:
            val = f'{time.format_relative(record["last_msg"])}'
            val += f' in {ctx.guild.get_channel(record["channel_id"]).mention}'
            e.add_field(name='Last Message', value=val, inline=False)

        if user.display_avatar.url:
            e.set_thumbnail(url=user.display_avatar.url)

        if isinstance(user, discord.User):
            e.set_footer(text='This member is not in this server.')

        await ctx.send(embed=e)

    @info.command('server')
    @app_commands.describe(idx='Guild ID')
    async def server_info(self, ctx: GuildContext, idx: Optional[int] = None) -> None:
        """Shows information about the server."""
        await ctx.typing()

        if idx is not None and await self.bot.is_owner(ctx.author):
            guild = self.bot.get_guild(idx)
            if guild is None:
                await ctx.send(f'Invalid Guild ID given.')
                return

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
            perms = discord.Permissions((everyone_perms & ~deny.value) | allow.value)
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
            last_boost = max(guild.members, key=lambda m: m.premium_since or guild.created_at)
            if last_boost.premium_since is not None:
                boosts = f'{boosts}\nLast Boost: {last_boost} ({time.format_relative(last_boost.premium_since)})'
            e.add_field(name='Boosts', value=boosts, inline=False)

        bots = sum(m.bot for m in guild.members)
        fmt = f'Total: {guild.member_count} ({formats.Plural(bots):bot})'

        e.add_field(name='Members', value=fmt, inline=False)
        e.add_field(name='Roles', value=', '.join(roles) if len(roles) < 10 else f'{len(roles)} roles')

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
    async def self_info(self, ctx: Context) -> None:
        e = discord.Embed(
            title="Zen", description="Hello, I'm a bot for ttrpg servers. I help with managing ttrgp communities."
        )

        e.add_field(name="Bot ID", value=f"```{self.bot.user.id}```", inline=True)

        e.add_field(name="Guilds", value=f"```{len(self.bot.guilds)}```", inline=True)

        total_members = sum([g.member_count for g in self.bot.guilds if g.member_count is not None])
        e.add_field(name="Members", value=f"```{total_members}```", inline=False)

        slash_commands = len(self.bot.tree.get_commands())
        all_commands = len(self.bot.commands)

        e.add_field(name="Slash Commands", value=f"```{slash_commands}```")
        e.add_field(name="All Commands", value=f"```{all_commands}```")

        elapsed_time = datetime.datetime.now() - self.bot.start_time
        uptime = f"{round(elapsed_time.seconds / 3600, 2)} hours" if elapsed_time.days == 0 else f"{elapsed_time.days} days"

        e.add_field(name="Uptime", value=f"```{uptime}```", inline=False)

        # repo link
        e.add_field(name="Repo Link", value="https://github.com/NekroDarkmoon/Zen", inline=False)

        e.timestamp = datetime.datetime.now(tz=None)
        e.set_thumbnail(url=self.bot.user.avatar)

        await ctx.send(embed=e)

    @info.command('role')
    @app_commands.describe(role='Selected Role')
    async def role_info(self, ctx: GuildContext, role: discord.Role) -> None:
        """Get information on a role."""
        # Data builder

        idx = role.id
        members = role.members
        count = len(members)
        data = [{'Member': m.display_name} for m in members]

        p = TabularPages(entries=data, ctx=ctx, headers='keys')

        p.embed.title = f'{role.name} - {idx}'
        p.embed.colour = role.color
        p.embed.add_field(name='Member Count', value=f'`{count}`', inline=False)
        p.embed.set_author(name=ctx.author.display_name)
        await p.start()

    async def say_permissions(
        self, ctx: Context, member: discord.Member, channel: discord.abc.GuildChannel | discord.Thread
    ):
        permissions = channel.permissions_for(member)
        e = discord.Embed(color=member.color)
        avatar = member.display_avatar.with_static_format('png')
        e.set_author(name=str(member), url=avatar)
        allowed, denied = [], []
        for name, value in permissions:
            name = name.replace('_', ' ').replace('guild', 'server').title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)

        e.add_field(name='Allowed', value='\n'.join(allowed))
        e.add_field(name='Denied', value='\n'.join(denied))
        await ctx.send(embed=e)

    @info.command('permissions')
    @app_commands.describe(member='Selected Member', channel='Selected Channel')
    async def permissions(
        self, ctx: GuildContext, member: Optional[discord.Member] = None, channel: Optional[GuildChannel] = None
    ) -> None:
        """Shows a member's permissions in a specific channel.

        If no channel is given then it uses the current one.

        You cannot use this in private messages. If no member is given then
        the info returned will be yours.
        """
        channel = channel or ctx.channel
        if member is None:
            member = ctx.author

        await self.say_permissions(ctx, member, channel)

    @info.command()
    @commands.guild_only()
    async def botpermissions(self, ctx: GuildContext, *, channel: Optional[GuildChannel] = None):
        """Shows the bot's permissions in a specific channel.

        If no channel is given then it uses the current one.

        This is a good way of checking if the bot has the permissions needed
        to execute the commands it wants to execute.
        """
        channel = channel or ctx.channel
        member = ctx.guild.me
        await self.say_permissions(ctx, member, channel)

    @info.command()
    @commands.is_owner()
    async def debugpermissions(self, ctx: Context, guild_id: int, channel_id: int, author_id: int = None):
        """Shows permission resolution for a channel and an optional author."""

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return await ctx.send('Guild not found?')

        channel = guild.get_channel(channel_id)
        if channel is None:
            return await ctx.send('Channel not found?')

        if author_id is None:
            member = guild.me
        else:
            member = await self.bot.get_or_fetch_member(guild, author_id)

        if member is None:
            return await ctx.send('Member not found?')

        await self.say_permissions(ctx, member, channel)

    @commands.hybrid_command(aliases=['invite'])
    async def join(self, ctx: Context):
        """Posts my invite to allow you to invite me"""
        perms = discord.Permissions.all()
        perms.administrator = True
        await ctx.send(f'<{discord.utils.oauth_url(self.bot.client_id, permissions=perms)}>')

    @commands.hybrid_command(name='preview')
    @app_commands.describe(message='Message to preview')
    async def message_preview(self, ctx: GuildContext, message: discord.Message) -> None:
        """Generate a preview of a message.

        Can take links and ids.
        """
        e = discord.Embed(title='Message Preview', colour=discord.Colour.random())
        e.description = message.content

        for a in message.attachments:
            e.add_field(name='Attachment', value=a, inline=False)

        if len(message.attachments) == 1:
            e.set_image(url=message.attachments[0])

        e.url = message.to_reference().jump_url
        e.timestamp = datetime.datetime.utcnow()
        e.set_author(name=message.author, icon_url=message.author.display_avatar)
        await ctx.send(embed=e)


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
