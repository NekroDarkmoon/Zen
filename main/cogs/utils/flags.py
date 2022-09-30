# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging
import os
import sys
from turtle import title
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, TypeVar, overload
from typing_extensions import Self

# Third party imports
import discord
from discord.ext import commands

# Local application imports
# Enabling local imports
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_PATH)


if TYPE_CHECKING:
    from .context import Context

T = TypeVar('T', bound='BaseFlags')

log = logging.getLogger(__name__)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                    Numbered Page Modal
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class BaseFlags:
    __slots__ = ('value', )

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, self.__class__) and self.value == __o.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} value={self.value}>'

    def is_empty(self) -> bool:
        return self.value == 0

    def _has_flag(self, o: int) -> bool:
        return (self.value & o) == 0

    def _set_flag(self, o: int, toggle: bool) -> None:
        if toggle is True:
            self.value |= o
        elif toggle is False:
            self.value &= ~o
        else:
            raise TypeError(
                f'Value to set for {self.__class__.__name__} must be a bool.'
            )


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Flag Value
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class flag_value:
    def __init__(self, func: Callable[[Any], int]) -> None:
        self.flag: int = func(None)
        self.__doc__: Optional[str] = func.__doc__

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> Self:
        ...

    @overload
    def __get__(self, instance: T, owner: type[T]) -> bool:
        ...

    def __get__(self, instance: Optional[T], owner: type[T]) -> Any:
        if instance is None:
            return self
        return instance._has_flag(self.flag)

    def __set__(self, instance: BaseFlags, value: bool) -> None:
        instance._set_flag(self.flag, value)

    def __repr__(self) -> str:
        return f'<flag_value flag={self.flag!r}>'
