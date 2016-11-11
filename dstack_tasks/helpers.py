from fabric.api import env
from fabric.decorators import task


@task
def echo():
    from pprint import pprint
    show_envs = ['project_name', 'project_dir', 'project_path',
                 'release_tag', 'server_dotenv_path', 'local_dotenv_path',
                 'virtual_env', 'virtual_host', 'image_name', 'image_tag']

    custom_envs = {your_key: env[your_key] for your_key in show_envs}
    pprint(custom_envs)
