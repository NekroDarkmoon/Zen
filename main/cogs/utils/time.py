# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations
import datetime

# Standard library imports
import datetime
import logging
import parsedatetime as pdt
import re


from dateutil.relativedelta import relativedelta
from typing_extensions import Self
from typing import TYPE_CHECKING, Any, Optional

# Third party imports
from discord.ext import commands


# Local application imports
from main.cogs.utils.formats import Plural, human_join, format_dt as format_dt


if TYPE_CHECKING:
    from utils.context import Context


log = logging.getLogger(__name__)
INVALID_TIME = 'Invalid time provided, try e.g. "tomorrow" or "3 days".'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Short Time
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ShortTime:
    compiled = re.compile(
        """
           (?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
           (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
           (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
           (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
           (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
           (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
           (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
        """,
        re.VERBOSE,
    )

    def __init__(
        self, argument: str, *, now: Optional[datetime.datetime] = None
    ) -> None:
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument('invalid time provided.')

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or datetime.datetime.utcnow()
        self.dt: datetime.datetime = now + relativedelta(**data)

        @classmethod
        async def convert(cls, ctx: Context, argument: str) -> Self:
            return cls(argument, now=ctx.message.created_at)


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
