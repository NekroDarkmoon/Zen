#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from __future__ import annotations

# Standard library imports
import datetime
from typing import Any, Iterable, Optional, Sequence

# Third party imports
import discord
from discord import app_commands
from discord.ext import commands

# Local application imports


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Plural
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Plural:
    def __init__(self, value: int) -> None:
        self.value = value

    def __format__(self, format_spec: str) -> str:
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'

        if abs(v) != 1:
            return f'{v} {plural}'

        return f'{v} {singular}'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                       Human Join
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def human_join(seq: Sequence[str], delim: str = ', ', final: str = 'or') -> str:
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return delim.join(seq[:-1] + f'{final} {seq[-1]}')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                       TabularData
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class TabularData:
    def __init__(self) -> None:
        self._widths: list[int] = list()
        self._columns: list[str] = list()
        self._rows: list[list[str]] = list()

    def set_columns(self, columns: list[str]) -> None:
        self._columns = columns
        self._widths = [len(c) + 2 for c in columns]

    def add_row(self, row: Iterable[Any]) -> None:
        rows = [str(r) for r in row]
        self._rows.append(rows)
        for idx, elem, in enumerate(rows):
            width = len(elem) + 2
            if width > self._widths[idx]:
                self._widths[idx] = width

    def add_rows(self, rows: Iterable[Iterable[Any]]) -> None:
        for row in rows:
            self.add_row(row)

    def render(self) -> str:
        """Renders a table in rST format.
        Example:
        +-------+-----+
        | Name  | Age |
        +-------+-----+
        | Alice | 24  |
        |  Bob  | 19  |
        +-------+-----+
        """

        sep = '+'.join('-' * w for w in self._widths)
        sep = f'+{sep}+'

        to_draw = [sep]

        def get_entry(d):
            elem = '|'.join(f'{e:^{self._widths[i]}}' for i, e in enumerate(d))
            return f'|{elem}|'

        to_draw.append(get_entry(self._columns))
        to_draw.append(sep)

        for row in self._rows:
            to_draw.append(get_entry(row))

        to_draw.append(sep)
        return '\n'.join(to_draw)

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         format dt
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


def format_dt(
        dt: datetime.datetime,
        style: Optional[str] = None,
        add_tz: bool = True
) -> str:
    if dt.tzinfo is None and add_tz:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    if style is None:
        return f'<t:{int(dt.timestamp())}>'

    return f'<t:{int(dt.timestamp())}:{style}>'


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                       Color String
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def text_color(content: str, color: str = None) -> str:
    if color == 'red':
        return f'```diff\n- {content}```'
    elif color == 'orange':
        return f'```cs\n#{content}```'
    elif color == 'yellow':
        return f'```fix\n {content}```'
    elif color == 'green':
        return f'```diff\n+ {content}```'
    elif color == 'cyan':
        return f'```yaml\n{content}```'
    elif color == 'blue':
        return f'```ini\n[{content}]```'
    else:
        return f'```\n{content}```'
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Owner
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
