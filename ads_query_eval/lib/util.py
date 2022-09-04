import hashlib
from datetime import datetime, timezone
from importlib import import_module

from passlib.context import CryptContext
from toolz import keyfilter

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def now(as_str=False, tz=timezone.utc):
    dt = datetime.now(tz=tz)
    return dt.isoformat() if as_str else dt


def today_as_str(tz=timezone.utc) -> str:
    return now(as_str=True, tz=tz).split("T", maxsplit=1)[0]


def import_via_dotted_path(dotted_path: str):
    module_name, _, member_name = dotted_path.rpartition(".")
    return getattr(import_module(module_name), member_name)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def pick(whitelist, d):
    return keyfilter(lambda k: k in whitelist, d)


def hash_of(s: str, algo="sha256") -> str:
    if algo not in hashlib.algorithms_guaranteed:
        raise ValueError(f"desired algorithm {algo} not supported")
    return getattr(hashlib, algo)(s.encode("utf-8")).hexdigest()
