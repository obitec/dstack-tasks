import email.message
import json
import os
import smtplib
import socket

import requests
from invoke import task

from .base import LOCAL_PREFIX, REMOTE_PREFIX, env


@task
def send_mail(send_to, message, subject=None, mail_host=None):
    email_from = os.getenv('NOTIFY_EMAIL_FROM', None)
    email_domain = os.getenv('NOTIFY_EMAIL_DOMAIN', socket.getfqdn())
    email_from = email_from or f"Server Alert <no-reply@{email_domain}>"
    subject = subject or 'Server Alert'

    msg = email.message.Message()
    msg['From'] = email_from
    msg['To'] = send_to
    msg['Subject'] = subject
    msg.add_header('Content-Type', 'text')
    msg.set_payload(message)
    s = smtplib.SMTP(mail_host)
    s.send_message(msg)
    s.quit()


@task
def send_alert(ctx, message, backend):
    headers = {'Content-Type': 'application/json'}
    hooks = {
        'teams': 'NOTIFY_TEAMS_HOOK',
        'slack': 'NOTIFY_SLACK_HOOK',
        'telegram': 'NOTIFY_TELEGRAM_HOOK',
    }
    web_hook = os.getenv(hooks[backend])
    if not env.dry_run:
        data = {'text': message}
        if backend == 'telegram':
            data.update({'chat_id': os.getenv('NOTIFY_TELEGRAM_CHAT_ID')})
        requests.post(web_hook, headers=headers, data=json.dumps(data))
    else:
        print(REMOTE_PREFIX if getattr(ctx, 'host', False) else LOCAL_PREFIX, f'POST "{message}" to {web_hook[:25]}...')
