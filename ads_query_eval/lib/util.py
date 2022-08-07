from datetime import datetime, timezone
from importlib import import_module


def now(as_str=False):
    dt = datetime.now(timezone.utc)
    return dt.isoformat() if as_str else dt


def import_via_dotted_path(dotted_path: str):
    module_name, _, member_name = dotted_path.rpartition(".")
    return getattr(import_module(module_name), member_name)
