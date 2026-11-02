import os.path

from library.config import MODULE_DIR


def init_env(prod_env=True):
    env = {}
    for name in (".env", ".env_prod") if prod_env else (".env",):
        env.update(_read_env(os.path.join(MODULE_DIR, name)))
    return env


def _read_env(path):
    env = {}
    with open(path) as env_file:
        for env_line in env_file:
            env_line = env_line.replace("export ", "").rstrip()
            if not env_line.startswith("#") and "=" in env_line:
                env_key, env_value = env_line.split("=", 1)
                env[env_key] = env_value
    return env
