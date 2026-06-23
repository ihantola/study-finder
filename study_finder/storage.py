"""Persist normalized records to a CSV (the raw cache is handled by the client)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd


def write_csv(records: Sequence[dict], path: Path) -> Path:
    """Write records to ``path`` as CSV, creating parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(list(records))
    df.to_csv(path, index=False)
    return path
