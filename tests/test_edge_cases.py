import pytest
import threading
import time
from pathlib import Path
import tempfile
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from app import App
from scanner import scan, ScanStopped

def test_scan_cancellation():
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ScanStopped):
        scan(root=Path("/tmp"), cancel=cancel)

def test_search_and_filter_empty_result():
    app = App()
    app.model.append([False, "Thumbnail previews", "10.0 MiB", "/test/thumb", (10485760, []), 10485760, "", "Linux", "Usually safe", "", "● Usually safe"])
    
    # Filter by non-existent query
    app.search_entry.set_text("nonexistent_random_pattern_xyz")
    app.filter_model.refilter()
    
    # Check that visible rows in filter_model is 0
    visible_count = len(list(app.filter_model))
    assert visible_count == 0
    
    # Clear query
    app.search_entry.set_text("")
    app.filter_model.refilter()
    assert len(list(app.filter_model)) == 1
    
    app.destroy()

def test_stop_scan_flow():
    app = App()
    app.cancel_scan()
    assert app.cancel.is_set()
    app.stopped()
    assert "Scan stopped" in app.status.get_text()
    app.destroy()
