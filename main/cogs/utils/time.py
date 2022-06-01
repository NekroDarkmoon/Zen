# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations
import datetime

# Standard library imports
import logging

from typing import TYPE_CHECKING, Optional

# Third party imports
from discord.ext import commands


# Local application imports
from main.cogs.utils.formats import Plural, human_join, format_dt as format_dt


if TYPE_CHECKING:
    from utils.context import Context


log = logging.getLogger(__name__)


def format_relative(dt: datetime.datetime) -> str:
    return format_dt(dt, 'R')
