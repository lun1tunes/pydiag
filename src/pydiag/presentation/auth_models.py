from __future__ import annotations

from dataclasses import dataclass

__all__ = ["AuthUser"]


@dataclass(frozen=True)
class AuthUser:
    username: str
    display_name: str
    password: str
    is_admin: bool = True
    is_super_admin: bool = False
