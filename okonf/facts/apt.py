import re
from okonf.facts.abstract import Fact

RE_UPGRADEABLE = r'([^\/]+)\/([^\s]+)\s+([^\s]+)\s+(\w+)\s+' \
                 r'\[upgradable from:\s+([^\s]+)\]$'


def parse_upgradeable(lines):
    for line in lines:
        match = re.match(RE_UPGRADEABLE, line)
        if match:
            name, source, next_version, arch, version = match.groups()
            yield name, {
                'source': source,
                'next_version': next_version,
                'arch': arch,
                'version': version,
            }


class AptPresent(Fact):

    def __init__(self, name, sudo=True):
        self.name = name
        self.sudo = sudo

    async def enquire(self, host):
        status = await host.run("dpkg -l {}".format(self.name), check=False)
        for line in status.split('\n'):
            if re.match(r"ii\s+{}(\:amd64)?\s+".format(self.name), line):
                return True
        return False

    async def enforce(self, host):
        if self.sudo:
            await host.run("sudo apt-get install -y {}".format(self.name))
        else:
            await host.run("apt-get install -y {}".format(self.name))
        return True

    @property
    def description(self):
        return str(self.name)


class AptAbsent(AptPresent):

    def __init__(self, name, purge=False, sudo=True):
        self.purge = purge
        super(AptAbsent, self).__init__(name=name, sudo=sudo)

    async def enquire(self, host):
        return not await super().enquire(host)

    async def enforce(self, host):
        purge = '--purge' if self.purge else ''
        if self.sudo:
            await host.run("apt-get remove {} -y {}".format(purge, self.name))
        else:
            await host.run("sudo apt-get remove {} -y {}".format(purge, self.name))
        return True


class AptUpdated(Fact):

    def __init__(self, names=tuple()):
        self.names = names

    async def enquire(self, host):
        return False

    async def enforce(self, host):
        await host.run("sudo apt-get update")
        return True


class AptUpgraded(Fact):

    def __init__(self, names=tuple()):
        self.names = names

    async def info(self, host):
        names_str = ' '.join(self.names)
        status = await host.run("apt list --upgradeable {}".format(names_str))

        if status.startswith('Listing...\n'):
            status = status[len('Listing...\n'):]

        return {
            name: values
            for name, values in parse_upgradeable(status.split('\n'))
        }

    async def enquire(self, host):
        upgradeable = await self.info(host)
        return len(upgradeable) == 0

    async def enforce(self, host):
        await host.run("sudo apt-get upgrade")
        return True
