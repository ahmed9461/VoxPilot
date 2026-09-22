from __future__ import annotations


def is_owner(user_id: int | None, owner_id: int) -> bool:
    return bool(user_id and owner_id and int(user_id) == int(owner_id))
