import os

from invoke import task

from .base import do
from .wrap import pip

service_template = """[Unit]
Description=dstack-bot
After=syslog.target network.target

[Service]
Type=simple
User={user}
WorkingDirectory=/home/{user}
ExecStart=/home/{user}/venv/bin/dbot
Restart=on-failure
EnvironmentFile=/home/{user}/.env

[Install]
WantedBy=multi-user.target
"""

env_template = """# dstack-bot config
TELEGRAM_BOT_TOKEN={token}
TELEGRAM_BOT_ADMIN1={admin1}
TELEGRAM_BOT_ADMIN2={admin2}
"""


@task
def install_dstack_bot(ctx):
    do(ctx, 'python3 -m venv venv')
    pip(ctx, 'install dstack-bot')
    user = os.getenv('USER_NAME')
    content = service_template.format(user=user)
    service_file = '/etc/systemd/system/dbot.service'
    do(ctx, f"printf '{content}' | sudo tee {service_file}", hide=True)
    # TODO: Must have already configured .env
    # token = os.getenv('TELEGRAM_BOT_TOKEN')
    # env_vars = env_template.format(token=token, admin=admin)
    # do(ctx, f"printf '' > .env", hide=True)
    do(ctx, 'systemctl enable dbot', sudo=True)
    do(ctx, 'systemctl start dbot', sudo=True)
    do(ctx, 'systemctl status dbot', sudo=True)
