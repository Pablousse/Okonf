import os.path
import pytest

from okonf.connectors import LocalHost
from okonf.facts.python import Virtualenv, PipInstalled


@pytest.mark.asyncio
async def test_Virtualenv():
    host = LocalHost()
    path = '/tmp/virtualenv'

    assert not os.path.exists(path)
    assert not await Virtualenv(path).check(host)

    assert await Virtualenv(path).apply(host)
    assert os.path.isdir(path)
    assert await Virtualenv(path).check(host)


@pytest.mark.asyncio
async def test_PipInstalled():
    host = LocalHost()
    packages = ['hereby']
    virtualenv = '/tmp/virtualenv'

    await Virtualenv(virtualenv).apply(host)

    assert not await PipInstalled(packages, virtualenv).check(host)

    assert await PipInstalled(packages, virtualenv).apply(host)
    assert await PipInstalled(packages, virtualenv).check(host)
