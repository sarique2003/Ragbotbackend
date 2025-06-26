import os
from dotenv import load_dotenv

load_dotenv()
def get_env_value(var: str, default=None):
    var_val = os.getenv(var)
    if not var_val:
        if not default:
            raise (f"{var.upper()} environment variable is not set.")
        else:
            return default
    return var_val
