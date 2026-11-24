"""Pure-Python stateful workbench package for Pytae (used by the IPython extension and CLI).

Organized into:
- `system`: paths, OS memory trimming, DataFrame inspection/conversion
- `settings`: persistent `%set` display settings (`~/.pytae/config.json`)
- `core`: stateful `Workbench` (checkpoints, strict restore, `%pt`, `%status`, `%free`)
- `export`: session pruning, `%pt` fluent Python transpilation, `.py`/`.ipynb` generation
- `history`: SQLite history inspection, search, export, and cell-by-cell `-load` replay
"""

from __future__ import annotations

from pytae.workbench.core import CheckpointRecord, CheckpointTableEntry, Workbench
from pytae.workbench.history import launch_ipython_cells, run_cli_history, run_cli_load
from pytae.workbench.settings import DisplaySettings
from pytae.workbench.system import (
    frame_columns,
    frame_kind,
    frame_memory_bytes,
    frame_shape_str,
    from_polars_frame,
    get_config_path,
    get_default_ipython_history_db,
    get_ipython_history_db,
    get_process_rss_mb,
    get_pytae_home,
    get_session_meta_dir,
    is_dataframe,
    is_user_var,
    release_memory,
    set_ipython_history_db,
    to_polars_frame,
)

__all__ = [
    "CheckpointRecord",
    "CheckpointTableEntry",
    "DisplaySettings",
    "Workbench",
    "frame_columns",
    "frame_kind",
    "frame_memory_bytes",
    "frame_shape_str",
    "from_polars_frame",
    "get_config_path",
    "get_default_ipython_history_db",
    "get_ipython_history_db",
    "get_process_rss_mb",
    "get_pytae_home",
    "get_session_meta_dir",
    "is_dataframe",
    "is_user_var",
    "launch_ipython_cells",
    "release_memory",
    "run_cli_history",
    "run_cli_load",
    "set_ipython_history_db",
    "to_polars_frame",
]
