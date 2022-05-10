# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging

from typing import TYPE_CHECKING, Optional

# Third party imports
from discord.ext import commands


# Local application imports


if TYPE_CHECKING:
    from utils.context import Context


log = logging.getLogger(__name__)
