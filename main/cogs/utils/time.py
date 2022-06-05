# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations
import datetime

# Standard library imports
import logging
from typing_extensions import Self

import parsedatetime as pdt

from typing import TYPE_CHECKING, Any, Optional

# Third party imports
from discord.ext import commands


# Local application imports
from main.cogs.utils.formats import Plural, human_join, format_dt as format_dt


if TYPE_CHECKING:
    from utils.context import Context


log = logging.getLogger(__name__)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Human Time
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class HumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(
        self,
        argument: str,
        *,
        now: Optional[datetime.datetime] = None
    ) -> None:
        now = now or datetime.datetime.utcnow()
        dt, status = self.calendar.parseDT(argument, sourceTime=now)

        if not status.hasDateOrTime:
            raise commands.BadArgument(
                'Invalid time provided, try e.g. "tomorrow" or "3 days"')

        if not status.hasTime:
            dt: datetime.datetime = dt.replace(
                hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond
            )

        self.dt: datetime.datetime = dt
        self._past: bool = dt < now

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> Self:
        return cls(argument, now=ctx.message.created_at)

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                  Friendly Time Result
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FriendlyTimeResult:
    dt: datetime.datetime
    arg: str

    __slots__ = ('dt', 'arg')

    def __init__(self, dt: datetime.datetime) -> None:
        self.dt = dt
        self.arg = ''

    async def ensure_constraints(
        self,
        ctx: Context,
        uft: UserFriendlyTime,
        now: datetime.datetime,
        remaining: str
    ) -> None:
        if self.dt < now:
            raise commands.BadArgument('This time is in the past.')

        if not remaining:
            if uft.default is None:
                raise commands.BadArgument('Missing argument after time.')
            remaining = uft.default

        if uft.converter is not None:
            self.arg = await uft.converter.convert(ctx, remaining)
        else:
            self.arg = remaining


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                    User Friendly Time
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class UserFriendlyTime:
    pass


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                      Format Relative
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def format_relative(dt: datetime.datetime) -> str:
    return format_dt(dt, 'R')
