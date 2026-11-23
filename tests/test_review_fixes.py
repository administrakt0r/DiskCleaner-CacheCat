import pytest
import os
import shutil
import tempfile
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from app import App
from scanner import empty_trash, TRASH

def test_c1_actions_bar_disabled_during_scan():
    app = App(auto_start=False)
    app.start()
    # Batch selection buttons must be disabled during active scan
    assert app.btn_select_safe.get_sensitive() is False
    assert app.btn_select_all.get_sensitive() is False
    assert app.btn_deselect_all.get_sensitive() is False
    assert app.clean.get_sensitive() is False
    app.cancel_scan()
    app.stopped()
    # Re-enabled after scan stopped
    assert app.btn_select_safe.get_sensitive() is True
    assert app.btn_select_all.get_sensitive() is True
    assert app.btn_deselect_all.get_sensitive() is True
    app.destroy()

def test_c2_window_destroy_cleans_timers_and_threads():
    app = App(auto_start=False)
    app.start()
    assert app.scan_timer is not None
    assert app.cancel.is_set() is False
    # Destroying window must cancel scan, remove timers without throwing
    app.destroy()
    assert app.cancel.is_set() is True
    assert app.scan_timer is None
    assert app.anim_timer is None

def test_c3_trash_recursive_size_and_permission_safety(monkeypatch):
    # Setup temporary fake trash dir
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_trash = Path(tmpdir)
        files_dir = tmp_trash / "files"
        info_dir = tmp_trash / "info"
        files_dir.mkdir(parents=True)
        info_dir.mkdir(parents=True)
        
        # Create a directory in files containing 10 KiB data
        sub = files_dir / "my_big_folder"
        sub.mkdir()
        (sub / "file1.txt").write_bytes(b"A" * 10240)
        (info_dir / "my_big_folder.trashinfo").write_text("[Trash Info]\nPath=/home/test")
        
        # Monkeypatch TRASH in scanner
        import scanner
        monkeypatch.setattr(scanner, "TRASH", tmp_trash)
        
        deleted, freed = empty_trash()
        assert deleted == 1  # Exactly 1 trashed item (not 2 counting .trashinfo)
        assert freed >= 10240  # Recursive size calculated, not 4096 directory inode

def test_i1_apt_row_open_location(monkeypatch):
    app = App(auto_start=False)
    app.model.append([False, "System", "50.0 MiB", "All downloaded APT packages (administrator)", (52428800, []), 52428800, "", "APT", "Review first", "", "● Review first"])
    app.tree.get_selection().select_path(Gtk.TreePath.new_first())
    
    opened_paths = []
    def fake_launch(uri, _):
        opened_paths.append(uri)
    monkeypatch.setattr(gi.repository.Gio.AppInfo, "launch_default_for_uri", fake_launch)
    
    app.on_open_selected_location()
    assert len(opened_paths) == 1
    assert "apt/archives" in opened_paths[0]
    app.destroy()

def test_i2_filter_scoped_selection():
    app = App(auto_start=False)
    # Row 0: Safe Cache
    app.model.append([False, "Thumbnail previews", "10.0 MiB", "/test/thumb", (10485760, []), 10485760, "", "Linux", "Usually safe", "", "● Usually safe"])
    # Row 1: Build file
    app.model.append([False, "Project build output", "50.0 MiB", "/test/build", (52428800, []), 52428800, "", "Node", "Review first", "", "● Review first"])
    
    # Filter to only Safe Caches
    app.active_filter = "Safe Caches"
    app.filter_model.refilter()
    assert len(list(app.filter_model)) == 1
    
    # Select all in this filtered view
    app.select_all()
    # Only visible safe cache row should be selected, NOT row 1
    assert app.model[0][0] is True
    assert app.model[1][0] is False
    
    # Deselect all in filtered view
    app.deselect_all()
    assert app.model[0][0] is False
    assert app.model[1][0] is False
    app.destroy()

def test_i3_markup_escaping():
    app = App(auto_start=False)
    # Add item with XML characters in reason and app
    app.model.append([False, "Thumbnail", "10.0 MiB", "/test/<foo>&<bar>", (10485760, []), 10485760, "", "App & Tool <Special>", "Usually safe", "Reason <x> & <y>", "● Usually safe"])
    app.tree.get_selection().select_path(Gtk.TreePath.new_first())
    # show_detail should not fail markup parsing
    app.show_detail(app.tree.get_selection())
    assert app.detail.get_visible() is True
    assert "&lt;x&gt;" in app.detail.get_text() or "<x>" in app.detail.get_text()
    
    # Popover text with & < >
    app.popover.meow("Text with <tag> & symbols")
    app.destroy()
