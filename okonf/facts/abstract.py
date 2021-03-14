import logging
from abc import abstractmethod
from collections.abc import Iterable
from typing import List, Union, Tuple

import colorama
from colorama import Fore

from ..connectors.abstract import Host


def all_true(iterable) -> bool:
    """Recursive version of the all() function"""
    for element in iterable:
        if isinstance(element, Iterable):
            if not all_true(element):
                return False
        elif not element:
            return False
        else:
            pass
    return True


def any_true(iterable) -> bool:
    """Recursive version of the all() function"""
    for element in iterable:
        if isinstance(element, Iterable):
            if not any_true(element):
                return True
        elif element:
            return True
    return False


class FactCheck:

    def __init__(self, fact: 'Fact', result: Union[bool, Tuple]) -> None:
        assert isinstance(result, bool) or isinstance(result, list)
        self.fact = fact
        self.result = result

    def __bool__(self) -> bool:
        if isinstance(self.result, bool):
            return self.result
        else:
            return all_true(self.result)

    def __eq__(self, other) -> bool:
        return self.result == other

    def __repr__(self) -> str:
        if bool(self):
            return "{}{} {}{}".format(
                Fore.GREEN, 'Present', Fore.WHITE, self.fact)
        else:
            return "{}{} {}{}".format(
                Fore.RED, 'Absent', Fore.WHITE, self.fact)


class FactResult:

    def __init__(self, fact: 'Fact', result: Union[bool, Tuple, List]) -> None:
        assert isinstance(result, bool) or isinstance(result, list)
        self.fact = fact
        self.result = result

    def __bool__(self) -> bool:
        if isinstance(self.result, bool):
            return self.result
        else:
            return any_true(self.result)

    def __eq__(self, other) -> bool:
        return self.result == other

    def __repr__(self) -> str:
        if bool(self):
            return "{}{} {}{}".format(
                Fore.YELLOW, 'Changed', Fore.WHITE, self.fact)
        else:
            return "{}{} {}{}".format(
                Fore.MAGENTA, 'Unchanged', Fore.WHITE, self.fact)


class Fact:
    @abstractmethod
    async def enquire(self, host: Host) -> bool:
        """Run code to inspect the state of the host, return boolean status"""
        pass

    @abstractmethod
    async def enforce(self, host: Host) -> bool:
        """Apply the fact assuming it is not in place yet."""
        pass

    async def check(self, host: Host) -> FactCheck:
        result = FactCheck(self, await self.enquire(host))
        logging.info(str(result))
        return result

    async def apply(self, host: Host) -> FactResult:
        """Apply the fact if it is not in place yet, returns higher level result"""
        if not await self.check(host):
            result = FactResult(self, await self.enforce(host))
        else:
            result = FactResult(self, False)
        logging.info(str(result))
        return result

    @property
    def description(self) -> str:
        return str(self.__dict__)

    def __str__(self) -> str:
        arguments = (colorama.Fore.CYAN +
                     str(self.description) +
                     colorama.Style.RESET_ALL)
        return ' '.join((self.__class__.__name__, arguments))

    def __repr__(self) -> str:
        return "<{}[{}]>".format(self.__class__.__name__,
                                 self.description)
