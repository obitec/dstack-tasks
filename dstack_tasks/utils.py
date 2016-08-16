import os
from typing import Callable, Iterable, Mapping

from fabric.context_managers import hide, settings
from fabric.operations import local, prompt


def get_result(cmd: str = 'echo "Hello, World!'):
    """Captures the result of a local command without noise
    :param cmd:
    :return:
    """
    with hide('output', 'running', 'warnings'), settings(warn_only=True):
        result = local(cmd, capture=True)
        return result if result else ''


def activate_venv(env: dict, style: str = 'conda', venv: str = 'env') -> None:
    """ Helper function to set Python virtual environment activation command

    Conda activation:
        unix        $ source activate <venv>
        nt          C:\> activate <venv>

    Python venv activation:
        bash/zsh 	$ source <venv>/bin/activate
        fish 	    $ . <venv>/bin/activate.fish
        cmd.exe 	C:\> <venv>\\Scripts\\activate.bat
        PowerShell 	PS C:\> <venv>\\Scripts\\Activate.ps1
    """
    # Configure env activation
    env['os'] = os.name

    # various styles
    activate = {
        'conda': {
            'posix': 'source activate ' + venv,
            'nt': 'activate ' + venv
        },
        'pip': {
            'posix': 'source ' + os.path.join(venv, 'bin/activate'),
            'nt': os.path.join(venv, 'Scripts/activate.bat')
        }
    }

    env['activate'] = activate[style][os.name]


def dirify(base_path: str = None, force_posix: bool = False) -> Callable[[str], str]:
    """Helper function that returns a partial function to build paths from base path

    :param base_path: The base path from where to build paths
    :param force_posix: Default is False. Forces posix paths if true, even on Windows.


    """
    if base_path is None:
        base_path = ''

    if force_posix:
        from posixpath import join
    else:
        from os.path import join

    def _dirify(relative_path: str = None) -> str:
        return join(base_path, relative_path)

    return _dirify


def vc(release_tag: str = None, release_type: str = None) -> str:
    """

    :param release_type: Possible values are patch, minor, major. Prompts for type if None.
    :param release_tag: SemVer: needs to be of the pattern v0.0.0. Environmental vairable: RELEASE_TAG
    :return:
    """
    _release_types = {
        '3': 'parch',
        '2': 'minor',
        '1': 'major',
    }

    if not release_tag:
        print('Please add RELEASE_TAG in .env file with following pattern: v0.0.0')
    else:
        if '-' in release_tag:
            n, a = release_tag.split('-')
            a = '-' + a
        else:
            n = release_tag
            a = ''

        major, minor, patch = n.strip('v').split('.')

        if release_type is None:
            release_type = prompt('Is this a major (1), minor (2) or patch (3) update?', default='3', )
            release_type = _release_types[release_type]

        if release_type == 'major':
            major = int(major)
            major += 1
            minor = 0
            patch = 0
        elif release_type == 'minor':
            minor = int(minor)
            minor += 1
            patch = 0
        elif release_type == 'patch':
            patch = int(patch)
            patch += 1
        else:
            pass

        tag = 'v{major}.{minor}.{patch}{a}'.format(**locals())

        return tag


def check_keys(collection: Mapping, keys: Iterable) -> bool:
    """
    Function to check whether keys are present in a dictionary and raise
    if they're.

    :return:
    """

    for var in keys:
        if not collection.get(var, False):
            raise Exception('Improperly configured! Key: "' + var + '" not set.')

    return True
