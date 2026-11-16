import json
from typing import Any

_MAX_CHARS = 20000


def jsonable(value: Any, *, max_chars: int = _MAX_CHARS) -> Any:
    try:
        dumped = json.dumps(value, default=str)
    except TypeError:
        dumped = json.dumps({"repr": repr(value)}, default=str)
    if len(dumped) > max_chars:
        return {"truncated": True, "preview": dumped[:max_chars]}
    return json.loads(dumped)
