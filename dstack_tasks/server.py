import json
import os

from invoke import task

from .base import env
from .notify import send_alert
from .wrap import do, machine


@task
def machine_create(ctx, name, driver='digitalocean', username='ubuntu', user_id=1000, port=22, compose_version=None):
    """Create a docker machine
    Automatically uses key and value pairs from .env

    Args:
        ctx: instance of invoke.Context
        name: The name of the machine.
        driver: digitalocean, virtualbox, aws, etc.
        username: Default ubuntu.
        user_id: Default 1000.
        port: Default 22.
        compose_version: Default None.

    Returns: None

    """
    template = 'create --driver {driver} {config} {name}'
    config = ' '.join(['--{key}={value}'.format(
        key=k, value=v) for k, v in os.environ.items() if k.startswith(driver + '-')])
    command = template.format(driver=driver, config=config, name=name)
    machine(ctx, command)
    machine(ctx, f'scp ./server/setup.sh {name}:/root/setup.sh')
    machine(ctx, f'ssh {name} -- "./setup.sh {username} {user_id} {port} {compose_version}"')
    machine(ctx, f'restart {name}')
    # TODO: get from docker-machine inspect
    config_file = f'~/.docker/machine/machines/{name}/config.json'
    do(ctx, f'sed -i.bak "s/root/{username}/;s/: 22,/: {port},/" {config_file}')
    create_ssh_config(ctx, name, write=True)
    machine_info(ctx, name)


@task
def machine_info(ctx, name):
    hostname = machine(ctx, f'ssh {name} hostname --fqdn', hide=True).stdout.strip('\n')
    username = machine(ctx, f'ssh {name} whoami', hide=True).stdout.strip('\n')
    ip, status = machine_status(ctx, name=name)
    if status == 'Running':
        send_alert(ctx,
                   message=f"Hello, World! I'm {username}@{hostname}, living at {ip}",
                   backend='telegram')


@task
def machine_status(ctx, name='default'):
    """Attempts to parse docker-machine ip, config and machine_status to get
    the path to the key file and the ip address.

    Args:
        ctx: instance of invoke.Context
        name: The name of the machine.

    Returns: ip, status

    """
    ip = machine(ctx, f'ip {name}').stdout.strip('\n')
    status = machine(ctx, f'status {name}').stdout.strip('\n')
    return ip, status


ssh_config_template = """
Host {MachineName}
    UseKeychain yes
    AddKeysToAgent yes
    HostName {IPAddress}
    Port {SSHPort}
    User {SSHUser}
    IdentityFile {SSHKeyPath}

"""


@task
def create_ssh_config(ctx, name, write=False):
    """

    Args:
        ctx:
        name:
        write: Default = False. Whether to save config to ~/.ssh/config

    Returns:

    """
    result = machine(ctx, f'inspect {name}', hide=True)
    if not env.dry_run:
        config = json.loads(result.stdout)
        home = os.path.expanduser('~')
        ssh_config = ssh_config_template.format(**config['Driver'])
        if write:
            with open(os.path.join(home, '.ssh/config'), 'a') as f:
                f.write(ssh_config)
        else:
            print(ssh_config)
            print(os.path.join(home, '.ssh/config'))
