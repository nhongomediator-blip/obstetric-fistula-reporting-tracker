"""
================================================================================
ENVIRONMENT SETUP
================================================================================

Some Windows/Anaconda installations cannot find a working PROJ
coordinate-system database, which raises a CRSError in the geospatial
scripts. This module searches the likely locations, tests each
candidate by trying to use it and keeps the first that works.

Usage: add these lines at the top of a script, before importing
geopandas:

    from environment_setup import fix_proj_database
    fix_proj_database()
================================================================================
"""

import os
import sys


def _looks_like_a_real_database(candidate_path):
    """
    Checks whether a candidate folder contains a PROJ database that
    ACTUALLY WORKS, not just a file that happens to exist there. A broken
    or incompatible proj.db can still be present as a file, so this
    function goes further: it points pyproj at the folder and tries to
    genuinely build a well-known coordinate system (EPSG:4326) with it.
    If that succeeds without error, the folder is confirmed working.

    Args:
        candidate_path (str): Folder to test.

    Returns:
        bool: True if this folder contains a working PROJ database.
    """
    if not candidate_path:
        return False

    db_file = os.path.join(candidate_path, "proj.db")
    if not os.path.exists(db_file):
        return False

    try:
        import pyproj.datadir
        from pyproj import CRS

        pyproj.datadir.set_data_dir(candidate_path)
        CRS("EPSG:4326")  # deliberately triggers a real CRSError if this folder doesn't work
        return True
    except Exception:
        return False


def fix_proj_database():
    """
    Searches a short list of common locations for a WORKING PROJ
    coordinate-system database, and configures pyproj to use the first one
    that actually succeeds (not just the first one where a file happens to
    exist). Prints which location was used, or a warning if none worked.

    Returns:
        str or None: The folder path that was used, or None if no working
            database could be found anywhere on this machine.
    """
    import pyproj.datadir

    candidates = []

    # 1. The standard Anaconda location, built from wherever THIS machine's
    #    Python is actually installed (not a hardcoded username or drive).
    #    This is checked FIRST because, on this project's development
    #    machine, this was the location that actually worked, while
    #    pyproj's own self-reported default (checked next) was broken --
    #    a known conflict on some Anaconda installations.
    conda_root = os.path.dirname(os.path.dirname(sys.executable))
    candidates.append(os.path.join(conda_root, "Library", "share", "proj"))

    # 2. Ask pyproj itself where it thinks its data lives (the "normal"
    #    answer, correct on most non-Anaconda installations).
    try:
        candidates.append(pyproj.datadir.get_data_dir())
    except Exception:
        pass

    # 3. Whatever this machine's PROJ_DATA environment variable says, if set.
    if os.environ.get("PROJ_DATA"):
        candidates.append(os.environ.get("PROJ_DATA"))

    # Test each candidate for real; use the first one that genuinely works.
    for path in candidates:
        if _looks_like_a_real_database(path):
            print(f"[environment_setup] PROJ database found and verified working: {path}")
            return path

    print("[environment_setup] WARNING: none of the usual locations contained a "
          "working PROJ database. If you see a CRSError next, this needs manual "
          "troubleshooting -- see the project README.")
    return None
