import os
from os.path import join
from hashlib import sha256
from tempfile import NamedTemporaryFile

from asyncssh import ProcessError

from okonf.connectors.exceptions import NoSuchFileError
from okonf.modules.abstract import Module
from okonf.utils import get_local_file_hash


class FilePresent(Module):
    """Ensure that a file is present"""

    def __init__(self, remote_path: str) -> None:
        self.remote_path = remote_path

    async def check(self, host):
        command = "ls -d {}".format(self.remote_path)
        return await host.run(command, check=False) != ''

    async def apply(self, host):
        await host.run("touch {}".format(self.remote_path))
        return True


class FileAbsent(FilePresent):
    """Ensure that a file is absent"""

    async def check(self, host):
        return not await FilePresent.check(self, host)

    async def apply(self, host):
        await host.run("rm {}".format(self.remote_path))
        return True


class FileHash(Module):
    """Ensure that a file has a given hash"""

    def __init__(self, remote_path, hash):
        self.remote_path = remote_path
        self.hash = hash

    async def get_hash(self, host):
        try:
            output = await host.run("sha256sum {}".format(self.remote_path),
                                    no_such_file=True)
        except (NoSuchFileError):
            return False
        return output.split(' ', 1)[0].encode()

    async def check(self, host):
        remote_hash = await self.get_hash(host)
        return remote_hash == self.hash

    async def apply(self, host):
        raise NotImplemented


class FileCopy(Module):
    """Ensure that a file is a copy of a local file"""

    def __init__(self, remote_path, local_path, remote_hash=None):
        """

        :param remote_path:
        :param local_path:
        :param remote_hash: Optional, hash of the remote file if known
        """
        self.remote_path = remote_path
        self.local_path = local_path
        self.remote_hash = remote_hash

    async def check(self, host):
        local_hash = get_local_file_hash(self.local_path)
        if self.remote_hash:
            return local_hash == self.remote_hash
        else:
            return await FileHash(self.remote_path, local_hash).check(host)

    async def apply(self, host):
        await host.put(self.remote_path, self.local_path)
        return True


class FileContent(Module):
    """Ensure that a file has a given content"""

    def __init__(self, remote_path, content):
        self.remote_path = remote_path
        self.content = content

    async def check(self, host):
        content_hash = sha256(self.content).hexdigest().encode()
        return await FileHash(self.remote_path, content_hash).check(host)

    async def apply(self, host):
        with NamedTemporaryFile() as tmpfile:
            tmpfile.write(self.content)
            tmpfile.seek(0)
            await host.put(self.remote_path, tmpfile.name)
        return True


class DirectoryPresent(Module):
    """Ensure that a directory is present"""

    def __init__(self, remote_path: str) -> None:
        self.remote_path = remote_path

    async def check(self, host):
        command = "ls -d {}".format(self.remote_path)
        return await host.run(command, check=False) != ''

    async def apply(self, host):
        await host.run("mkdir -p {}".format(self.remote_path))
        return True


class DirectoryAbsent(DirectoryPresent):
    """Ensure that a directory is absent"""

    async def check(self, host):
        return not await DirectoryPresent.check(self, host)

    async def apply(self, host):
        await host.run("rmdir {}".format(self.remote_path))
        return True


class DirectoryCopy(Module):
    """Ensure that a remote directory contains a copy of a local one"""

    def __init__(self, remote_path: str, local_path: str) -> None:
        self.remote_path = remote_path
        self.local_path = local_path

    async def info_files_hash(self, host) -> dict:
        try:
            command = "find %s -type f -exec sha256sum {} +" % self.remote_path
            output = await host.run(command, no_such_file=True)
            result = {}
            for line in output.strip().split('\n'):
                if not line:
                    continue
                hash, path = line.split()
                result[path] = hash
            return result
        except NoSuchFileError as error:
            return {}

    async def info_dirs_present(self, host):
        try:
            command = "find {} -type d".format(self.remote_path)
            output = await host.run(command, no_such_file=True)
            result = output.strip().split('\n')
            return result
        except NoSuchFileError as error:
            return []

    def _get_remote_path(self, path):
        assert path.startswith(self.local_path)
        rel_path = path[len(self.local_path):].strip('/')
        return join(self.remote_path, rel_path)

    def _get_local_path(self, path):
        assert path.startswith(self.remote_path)
        rel_path = path[len(self.remote_path):].strip('/')
        return join(self.local_path, rel_path)

    async def submodules(self, host):
        """This module can be defined entirely using other modules, so
        we return a structure with these modules that can be used for both
        check and apply instead of running code."""

        dirs_to_create = []
        files_to_copy = []
        dirs_to_remove = []
        files_to_remove = []

        existing_files = await self.info_files_hash(host)

        for root, dirs, files in os.walk(self.local_path):
            remote_root = self._get_remote_path(root)

            for dirname in dirs:
                dirs_to_create.append(
                    DirectoryPresent(join(remote_root, dirname))
                )

            for filename in files:
                remote_path = join(remote_root, filename)
                files_to_copy.append(
                    FileCopy(remote_path,
                             join(root, filename),
                             remote_hash=existing_files.get(remote_path))
                )

        for filepath in existing_files:
            local_path = self._get_local_path(filepath)
            if not os.path.isfile(local_path):
                files_to_remove.append(FileAbsent(filepath))

        existing_dirs = await self.info_dirs_present(host)
        for dirname in existing_dirs:
            local_path = self._get_local_path(dirname)
            if not os.path.isdir(local_path):
                dirs_to_remove.append(DirectoryAbsent(dirname))

        return (
            # Both copy/creation and removal can be concurrent:
            [
                # Must create directories before files
                dirs_to_create, files_to_copy,
            ],
            [
                # Must remove files before directories
                files_to_remove, dirs_to_remove,
            ]
        )
