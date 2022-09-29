# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import datetime
import logging
import discord
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
#                          Time
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Time(HumanTime):
    def __init__(
        self, argument: str, *, now: Optional[datetime.datetime] = None
    ) -> None:
        try:
            o = ShortTime(argument, now=now)
        except Exception as e:
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                        Future Time
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FutureTime(HumanTime):
    def __init__(self, argument: str, *, now: Optional[datetime.datetime] = None) -> None:
        super().__init__(argument, now=now)

        if self._past:
            raise commands.BadArgument('this time is in the past.')


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
    """That way quotes aren't absolutely necessary."""
    converter: commands.Converter
    default: Any

    __slots__ = ('converter', 'default')

    def __init__(
        self,
        converter: Optional[type[commands.Converter]
                            | commands.Converter] = None,
        *,
        default: Any = None
    ) -> None:
        if isinstance(converter, type) and issubclass(converter, commands.Converter):
            converter = converter()

        if converter is not None and not isinstance(converter, commands.Converter):
            raise TypeError('commands.Converter subclass necessary.')

        self.converter = converter
        self.default = default

    async def convert(self, ctx: Context, argument: str) -> FriendlyTimeResult:
        try:
            calendar = HumanTime.calendar
            regex = ShortTime.compiled
            now = ctx.message.created_at

            match = regex.match(argument)

            if match is not None and match.group(0):
                data = {k: int(v)
                        for k, v in match.groupdict(default=0).items()}
                remaining = argument[match.end():].strip()
                result = FriendlyTimeResult(now + relativedelta(**data))
                await result.ensure_constraints(ctx, self, now, remaining)
                return result

            # Apparently nlp does not like "from now"
            # It likes "from x" in other cases though so handle the 'now' case
            if argument.endswith('from now'):
                argument = argument[:-8].strip()

            if argument[:2] == 'me':
                if argument[:6] in ('me to ', 'me in ', 'me at '):
                    argument = argument[6:]

            elems = calendar.nlp(argument, sourceTime=now)
            if elems is None or len(elems) == 0:
                raise commands.BadArgument(INVALID_TIME)

            # Handle the following cases:
            # "date time" foo
            # date time foo
            # foo date time
            dt, status, begin, end, dt_str = elems[0]

            if not status.hasDateOrTime:
                raise commands.BadArgument(INVALID_TIME)

            if begin not in (0, 1) and end != len(argument):
                raise commands.BadArgument(
                    'Time is either in an inappropriate location, which '
                    'must be either at the end or beginning of your input, '
                    'or I just flat out did not understand what you meant. Sorry.'
                )

            # TODO: Convert to func
            if not status.hasTime:
                dt: datetime.datetime = dt.replace(
                    hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond
                )

            if status.accuracy == pdt.pdtContext.ACU_HALFDAY:
                dt = dt.replace(day=now.day+1)

            result = FriendlyTimeResult(
                dt.replace(tzinfo=datetime.timezone.utc))
            remaining = ''

            if begin in (0, 1):
                if begin == 1:
                    if argument[0] != '"':
                        raise commands.BadArgument(
                            'Expected quote before time input.')

                    if not (end < len(argument) and argument[end] == '"'):
                        raise commands.BadArgument(
                            'If time is quoted, you mused end quote it.')

                    remaining = argument[end + 1:].lstrip(',.!')

                else:
                    remaining = argument[end:].lstrip(' ,.!')

            elif len(argument) == end:
                remaining = argument[:begin].strip()

            await result.ensure_constraints(ctx, self, now, remaining)
            return result

        except:
            import traceback
            traceback.print_exc()
            raise


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def human_timedelta(
    dt: datetime.datetime,
    *,
    source: Optional[datetime.datetime] = None,
    accuracy: Optional[int] = 3,
    brief: bool = False,
    suffix: bool = True,
) -> str:
    now = source or datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    if dt > now:
        delta = relativedelta(dt, now)
        out_suffix = ''
    else:
        delta = relativedelta(now, dt)
        out_suffix = ' ago' if suffix else ''

    attrs = [
        ('year', 'y'),
        ('month', 'mo'),
        ('day', 'd'),
        ('hour', 'h'),
        ('minute', 'm'),
        ('second', 's'),
    ]

    output = list()
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + 's')
        if not elem:
            continue

        if attr == 'day':
            weeks = delta.weeks
            if weeks:
                if not brief:
                    output.append(format(Plural(weeks), 'week'))
                else:
                    output.append(f'{weeks}w')

        if elem <= 0:
            continue

        if brief:
            output.append(f'{elem}{brief_attr}')
        else:
            output.append(format(Plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return 'now'
    else:
        if not brief:
            return human_join(output, final='and') + out_suffix
        else:
            return ' '.join(output) + out_suffix

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                      Format Relative
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def format_relative(dt: datetime.datetime) -> str:
    return format_dt(dt, 'R')
