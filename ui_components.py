import math
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from scanner import size

CUSTOM_CSS = b"""
/* CacheCat Modern UI Styling */
.cat-window {
    background-color: @theme_bg_color;
}

.cat-header {
    padding: 4px;
}

.cat-title-text {
    font-size: 20px;
    font-weight: 800;
}

.cat-subtitle {
    opacity: 0.75;
    font-size: 13px;
}

.cat-stat-badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 12px;
    background-color: alpha(@theme_selected_bg_color, 0.15);
    color: @theme_selected_bg_color;
}

.cat-pill {
    border-radius: 16px;
    padding: 3px 12px;
    font-size: 12px;
    font-weight: 600;
    transition: all 150ms ease-in-out;
}

.cat-btn-safe {
    background-image: linear-gradient(to bottom, #2ecc71, #27ae60);
    color: white;
    text-shadow: 0 1px rgba(0, 0, 0, 0.2);
    border-radius: 8px;
    font-weight: bold;
    padding: 6px 14px;
    transition: all 150ms ease-in-out;
}

.cat-btn-safe:hover {
    background-image: linear-gradient(to bottom, #39d97d, #2ecc71);
    box-shadow: 0 2px 6px rgba(46, 204, 113, 0.4);
}

.cat-btn-clean {
    border-radius: 8px;
    font-weight: bold;
    padding: 6px 18px;
    transition: all 150ms ease-in-out;
}

.cat-speech-bubble {
    border-radius: 16px;
    padding: 12px 16px;
    background-color: @theme_base_color;
    border: 2px solid #E88548;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.cat-speech-text {
    font-size: 13px;
    font-weight: 500;
    color: @theme_text_color;
}

.cat-usage-label {
    font-size: 12px;
    opacity: 0.85;
}
"""

def apply_custom_theme():
    provider = Gtk.CssProvider()
    provider.load_from_data(CUSTOM_CSS)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


def matches_category_filter(filter_name: str, kind: str, advice: str) -> bool:
    if filter_name == "All":
        return True
    if filter_name == "Safe Caches":
        return advice == "Usually safe"
    if filter_name == "Build Files":
        k = kind.lower()
        return "build" in k or "tooling" in k or "bytecode" in k or "output" in k
    if filter_name == "Dependencies":
        k = kind.lower()
        return ("dependencies" in k or "virtual environment" in k or 
                "package" in k or "store" in k or advice == "Reinstall / rebuild")
    if filter_name == "Large Files":
        return kind == "Large file"
    return True


class DiskUsageBar(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.used_bytes = 0
        self.free_bytes = 0
        self.selected_bytes = 0
        self.target_reclaim_ratio = 0.0
        self.current_reclaim_ratio = 0.0
        
        # Header stats row
        self.stats_row = Gtk.Box(spacing=10)
        self.pack_start(self.stats_row, False, False, 0)
        
        self.lbl_capacity = Gtk.Label(xalign=0)
        self.lbl_capacity.get_style_context().add_class("cat-usage-label")
        self.stats_row.pack_start(self.lbl_capacity, True, True, 0)
        
        self.lbl_reclaim = Gtk.Label(xalign=1)
        self.lbl_reclaim.get_style_context().add_class("cat-stat-badge")
        self.lbl_reclaim.set_no_show_all(True)
        self.stats_row.pack_end(self.lbl_reclaim, False, False, 0)
        
        # Custom Canvas Gauge
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(-1, 14)
        self.area.connect("draw", self._draw_bar)
        self.pack_start(self.area, False, False, 0)
        
        self.anim_timer = None

    def set_capacity(self, used_bytes: int, free_bytes: int, selected_bytes: int = 0):
        self.used_bytes = max(0, used_bytes)
        self.free_bytes = max(0, free_bytes)
        self.selected_bytes = max(0, selected_bytes)
        total = self.used_bytes + self.free_bytes
        
        if total > 0:
            pct_used = (self.used_bytes / total) * 100
            self.lbl_capacity.set_markup(
                f"<b>Disk Usage:</b> {size(self.used_bytes)} used ({pct_used:.1f}%) · "
                f"<b>{size(self.free_bytes)} free</b> of {size(total)}"
            )
            self.target_reclaim_ratio = min(1.0, self.selected_bytes / total)
        else:
            self.lbl_capacity.set_text("Disk capacity reading...")
            self.target_reclaim_ratio = 0.0

        if self.selected_bytes > 0:
            self.lbl_reclaim.set_markup(f"✨ <b>{size(self.selected_bytes)}</b> ready to clean")
            self.lbl_reclaim.show()
        else:
            self.lbl_reclaim.hide()
            
        self._start_animation()

    def _start_animation(self):
        if not Gtk.Settings.get_default().get_property("gtk-enable-animations"):
            self.current_reclaim_ratio = self.target_reclaim_ratio
            self.area.queue_draw()
            return
            
        if self.anim_timer is None:
            self.anim_timer = GLib.timeout_add(30, self._step_anim)

    def _step_anim(self):
        diff = self.target_reclaim_ratio - self.current_reclaim_ratio
        if abs(diff) < 0.002:
            self.current_reclaim_ratio = self.target_reclaim_ratio
            self.area.queue_draw()
            self.anim_timer = None
            return False
        self.current_reclaim_ratio += diff * 0.3
        self.area.queue_draw()
        return True

    def _draw_bar(self, widget, cr):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        radius = height / 2.0
        total = self.used_bytes + self.free_bytes
        if total <= 0:
            return

        # Background track (Free space)
        cr.save()
        self._rounded_rect(cr, 0, 0, width, height, radius)
        cr.set_source_rgba(0.25, 0.28, 0.35, 0.25)
        cr.fill()
        cr.restore()

        # Used portion
        used_ratio = min(1.0, self.used_bytes / total)
        used_w = width * used_ratio
        if used_w > 1:
            cr.save()
            self._rounded_rect(cr, 0, 0, width, height, radius)
            cr.clip()
            
            # Base used fill (Deep Slate Blue)
            cr.rectangle(0, 0, used_w, height)
            cr.set_source_rgba(0.35, 0.45, 0.75, 0.85)
            cr.fill()

            # Reclaimable portion inside used space (Golden Coral CacheCat color)
            reclaim_w = width * self.current_reclaim_ratio
            if reclaim_w > 1:
                reclaim_start = max(0, used_w - reclaim_w)
                cr.rectangle(reclaim_start, 0, reclaim_w, height)
                cr.set_source_rgba(0.91, 0.52, 0.28, 0.95)
                cr.fill()
            cr.restore()

    def _rounded_rect(self, cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()


class CuteSpeechPopover(Gtk.Popover):
    def __init__(self, relative_to: Gtk.Widget):
        super().__init__(relative_to=relative_to)
        self.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=8)
        self.add(box)
        self.label = Gtk.Label(wrap=True, max_width_chars=32)
        self.label.get_style_context().add_class("cat-speech-text")
        box.pack_start(self.label, True, True, 0)
        self.get_style_context().add_class("cat-speech-bubble")
        self.auto_timer = None

    def meow(self, text: str):
        self.label.set_markup(f"🐾 <i>\"{text}\"</i>")
        self.show_all()
        if self.auto_timer:
            GLib.source_remove(self.auto_timer)
        self.auto_timer = GLib.timeout_add_seconds(5, self._hide_popover)

    def _hide_popover(self):
        self.popdown()
        self.auto_timer = None
        return False
