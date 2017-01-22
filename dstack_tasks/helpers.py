from fabric.api import env
from fabric.decorators import task


@task
def echo() -> dict:
    """Task useful for debugging env variables and double checking context.

    Returns:
        Fabric env variables as set by config files, environmental variables, etc.

    """
    from pprint import pprint
    show_envs = [
        'pwd',
        'project_name',
        'project_dir',
        'server_dotenv_path',
        'local_dotenv_path',
        'venv_name',
        'venv_type',
        'virtual_host',
        'image_name',
        'tag',
        'organisation',
        'git_repo',
    ]

    custom_envs = {your_key: env[your_key] for your_key in show_envs}
    pprint(custom_envs)

    return custom_envs
