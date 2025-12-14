import re
from typing import Optional

def normalize_unit_suffix(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip().lower()

    # common cleanups
    s = s.replace(".", "")
    s = re.sub(r"\s+", "", s)

    mapping = {
        "lt": "l",
        "l": "l",
        "ml": "ml",
        "kg": "kg",
        "kilo": "kg",
        "g": "g",
        "gr": "g",
        "un": "un",
        "uni": "un",
        "unidad": "un",
        "unidade" : "un",
        "dose": "dose",
    }
    return mapping.get(s, s)
