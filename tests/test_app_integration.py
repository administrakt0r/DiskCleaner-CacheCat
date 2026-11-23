import pytest
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

def test_app_can_initialize():
    from app import App
    app = App()
    assert isinstance(app, Gtk.Window)
    assert app.animator is not None
    assert app.disk_bar is not None
    assert app.model is not None
    assert app.filter_model is not None
    # Clean up window
    app.destroy()

def test_select_safe_items():
    from app import App
    app = App()
    # Add dummy test rows: (selected, kind, size_str, label, items, bytes, tooltip, app, advice, reason, badge)
    app.model.append([False, "Thumbnail previews", "10.0 MiB", "/test/thumb", (10485760, []), 10485760, "", "Linux", "Usually safe", "", "● Usually safe"])
    app.model.append([False, "Project build output", "50.0 MiB", "/test/build", (52428800, []), 52428800, "", "Node", "Review first", "", "● Review first"])
    
    # Run select safe
    app.select_safe()
    rows = list(app.model)
    assert rows[0][0] is True  # Usually safe selected
    assert rows[1][0] is False # Review first not selected
    
    app.deselect_all()
    assert rows[0][0] is False
    assert rows[1][0] is False
    
    app.select_all()
    assert rows[0][0] is True
    assert rows[1][0] is True
    app.destroy()
