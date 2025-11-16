from pathlib import Path

import gi

gi.require_version("Nemo", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

DB_DIR = Path.home() / ".local" / "share" / "nemo-tags"
DB_PATH = DB_DIR / "tags.json"
ICONS_DIR = DB_DIR / "icons"
VIEWS_DIR = DB_DIR / "views"
EMBLEMS_DIR = DB_DIR / "emblems"
