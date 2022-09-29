#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from typing import Callable, TypeVar
from discord.ext import commands
from discord import app_commands

from main.cogs.utils.context import GuildContext

T = TypeVar('T')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                       Async Checks
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def check_guild_permissions(ctx, perms, check=all):
    """Checks guild wide permissions for a user.

    Args:
        ctx (_type_): _description_
        perms (_type_): _description_
        check (_type_, optional): _description_. Defaults to all.

    Returns:
        _type_: _description_
    """
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.guild is None:
        return False

    resolved = ctx.author.guild_permissions
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


async def check_permissions(ctx, perms, *, check=all) -> bool:
    """Checks a user for certain permissions.

    Args:
        ctx (_type_): _description_
        perms (_type_): _description_
        check (_type_, optional): _description_. Defaults to all.

    Returns:
        bool: _description_
    """
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    resolved = ctx.channel.permissions_for(ctx.author)
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Checks
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def has_permissions(*, check=all, **perms):
    async def pred(ctx):
        return await check_permissions(ctx, perms, check=check)

    return commands.check(pred)


def has_guild_permissions(*, check=all, **perms: bool):
    async def pred(ctx: GuildContext):
        return await check_guild_permissions(ctx, perms, check=check)

    return commands.check(pred)


# These do not take channel overrides into account

def hybrid_permissions_check(**perms: bool) -> Callable[[T], T]:
    async def pred(ctx: GuildContext):
        return await check_guild_permissions(ctx, perms)

    def decorator(func: T) -> T:
        commands.check(pred)(func)
        app_commands.default_permissions(**perms)(func)
        return func

    return decorator


def is_manager():
    return hybrid_permissions_check(manage_guild=True)


def is_mod():
    return hybrid_permissions_check(ban_members=True, manage_messages=True)


def is_admin():
    return hybrid_permissions_check(administrator=True)


def is_in_guilds(*guild_ids: int):
    def predicate(ctx: GuildContext) -> bool:
        guild = ctx.guild
        if guild is None:
            return False

        return guild.id in guild_ids

    return commands.check(predicate)
