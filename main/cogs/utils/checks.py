#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from discord.ext import commands

from main.cogs.utils.context import GuildContext

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


def is_mod():
    async def pred(ctx: GuildContext) -> bool:
        return await check_guild_permissions(ctx, {'manage_guild': True})

    return commands.check(pred)


def is_admin():
    async def pred(ctx: GuildContext) -> bool:
        return await check_guild_permissions(ctx, {'administrator': True})

    return commands.check(pred)
