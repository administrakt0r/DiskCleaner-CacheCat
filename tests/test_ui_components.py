import pytest
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

def test_category_filters():
    from ui_components import matches_category_filter
    assert matches_category_filter("All", "Thumbnail previews", "Usually safe") is True
    assert matches_category_filter("Safe Caches", "Thumbnail previews", "Usually safe") is True
    assert matches_category_filter("Safe Caches", "Project build output", "Review first") is False
    assert matches_category_filter("Large Files", "Large file", "Review first") is True
    assert matches_category_filter("Large Files", "Thumbnail previews", "Usually safe") is False
    assert matches_category_filter("Build Files", "Project build output", "Review first") is True
    assert matches_category_filter("Dependencies", "Installed Node dependencies", "Reinstall / rebuild") is True
    assert matches_category_filter("Dependencies", "Python virtual environment", "Review first") is True

def test_disk_usage_bar_initialization():
    from ui_components import DiskUsageBar
    bar = DiskUsageBar()
    assert isinstance(bar, Gtk.Widget)
    bar.set_capacity(used_bytes=50 * (1024**3), free_bytes=50 * (1024**3), selected_bytes=5 * (1024**3))
    assert bar.used_bytes == 50 * (1024**3)
    assert bar.free_bytes == 50 * (1024**3)
    assert bar.selected_bytes == 5 * (1024**3)

def test_apply_custom_theme():
    from ui_components import apply_custom_theme
    # Should apply CSS provider without throwing
    apply_custom_theme()
