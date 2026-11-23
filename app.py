import os
import shutil
import subprocess
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gio, GLib, GObject, Gtk, Pango, GdkPixbuf, Gdk

from mascot import MascotAnimator, MascotState
from scanner import (
    HOME,
    ScanStopped,
    assessment,
    empty_trash,
    get_trash_info,
    identity,
    remove_folder,
    scan,
    size,
)
from ui_components import (
    CuteSpeechPopover,
    DiskUsageBar,
    apply_custom_theme,
    matches_category_filter,
)

XPM_PATH = Path(__file__).with_name("cachecat.xpm")


class App(Gtk.Window):
    def __init__(self, auto_start=True):
        super().__init__(title="CacheCat · Disk Cleaner")
        apply_custom_theme()

        self.animator = MascotAnimator(XPM_PATH)
        self.set_icon(self.animator.base_pixbuf)
        self.set_default_size(1020, 680)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
        self.add(main_box)

        # ------------------ Header Area ------------------
        header_box = Gtk.Box(spacing=14)
        main_box.pack_start(header_box, False, False, 0)

        # Clickable mascot with cursor
        self.portrait_event = Gtk.EventBox()
        self.portrait = Gtk.Image.new_from_pixbuf(self.animator.get_current_frame())
        self.portrait_event.add(self.portrait)
        self.portrait_event.connect("button-press-event", self.on_mascot_clicked)
        self.portrait_event.connect("realize", self._set_pointer_cursor)
        self.portrait_event.set_tooltip_text("Click CacheCat for a meow tip!")
        header_box.pack_start(self.portrait_event, False, False, 0)

        # Speech popover
        self.popover = CuteSpeechPopover(self.portrait)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_lbl = Gtk.Label(xalign=0)
        title_lbl.set_markup("<span size='x-large' weight='heavy'>CacheCat</span>")
        subtitle_lbl = Gtk.Label(xalign=0, label="Cute disk cleaner & cache hunter")
        subtitle_lbl.get_style_context().add_class("cat-subtitle")
        title_box.pack_start(title_lbl, False, False, 0)
        title_box.pack_start(subtitle_lbl, False, False, 0)
        header_box.pack_start(title_box, False, False, 0)

        # Animated Disk capacity bar
        self.disk_bar = DiskUsageBar()
        header_box.pack_start(self.disk_bar, True, True, 12)

        # ------------------ Scan Controls ------------------
        options = Gtk.Box(spacing=8)
        main_box.pack_start(options, False, False, 0)
        options.pack_start(Gtk.Label(label="Folder:"), False, False, 0)

        self.folder = Gtk.FileChooserButton.new("Choose a folder to scan", Gtk.FileChooserAction.SELECT_FOLDER)
        self.folder.set_filename(str(HOME))
        options.pack_start(self.folder, True, True, 0)

        self.minimum = Gtk.ComboBoxText()
        for label in ("All sizes", "10 MiB or more", "100 MiB or more", "1 GiB or more"):
            self.minimum.append_text(label)
        self.minimum.set_active(0)
        options.pack_start(self.minimum, False, False, 0)

        self.include_large = Gtk.CheckButton(label="Include large files")
        self.include_large.set_active(True)
        options.pack_start(self.include_large, False, False, 0)

        # Trash bin indicator & cleaner button
        self.btn_trash = Gtk.Button(label="Trash: ...")
        self.btn_trash.connect("clicked", self.on_empty_trash_clicked)
        options.pack_end(self.btn_trash, False, False, 0)
        self.update_trash_status()

        self.options = options

        # ------------------ Quick Actions & Filter Bar ------------------
        actions_bar = Gtk.Box(spacing=8)
        main_box.pack_start(actions_bar, False, False, 0)

        # Filter Pills
        actions_bar.pack_start(Gtk.Label(label="Filter:"), False, False, 0)
        self.active_filter = "All"
        self.filter_buttons = []
        for name in ("All", "Safe Caches", "Build Files", "Dependencies", "Large Files"):
            btn = Gtk.RadioButton.new_with_label_from_widget(
                self.filter_buttons[0] if self.filter_buttons else None, name
            )
            btn.set_mode(False) # Displays as toggle button
            btn.get_style_context().add_class("cat-pill")
            btn.connect("toggled", self.on_filter_toggled, name)
            actions_bar.pack_start(btn, False, False, 0)
            self.filter_buttons.append(btn)

        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search name or path...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        actions_bar.pack_start(self.search_entry, False, False, 4)

        # Batch Selection Shortcuts
        btn_box = Gtk.Box(spacing=6)
        actions_bar.pack_end(btn_box, False, False, 0)

        self.btn_select_safe = Gtk.Button(label="✨ Select Safe")
        self.btn_select_safe.get_style_context().add_class("cat-btn-safe")
        self.btn_select_safe.set_tooltip_text("Quickly select all safe caches without manual clicking")
        self.btn_select_safe.connect("clicked", lambda _: self.select_safe())
        btn_box.pack_start(self.btn_select_safe, False, False, 0)

        self.btn_select_all = Gtk.Button(label="All")
        self.btn_select_all.connect("clicked", lambda _: self.select_all())
        btn_box.pack_start(self.btn_select_all, False, False, 0)

        self.btn_deselect_all = Gtk.Button(label="None")
        self.btn_deselect_all.connect("clicked", lambda _: self.deselect_all())
        btn_box.pack_start(self.btn_deselect_all, False, False, 0)

        self.actions_bar = actions_bar

        # ------------------ Progress & Status ------------------
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_no_show_all(True)
        main_box.pack_start(self.progress, False, False, 0)

        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        main_box.pack_start(self.status, False, False, 0)

        # ------------------ TreeView & Models ------------------
        # Store cols:
        # 0: bool selected
        # 1: str type
        # 2: str size_str
        # 3: str path
        # 4: object items tuple
        # 5: uint64 bytes
        # 6: str tooltip
        # 7: str app
        # 8: str advice
        # 9: str reason
        # 10: str advice markup
        self.model = Gtk.ListStore(
            bool, str, str, str, object, GObject.TYPE_UINT64, str, str, str, str, str
        )

        self.filter_model = self.model.filter_new()
        self.filter_model.set_visible_func(self._row_visible_func)

        self.sort_model = Gtk.TreeModelSort(model=self.filter_model)
        self.sort_model.set_sort_column_id(5, Gtk.SortType.DESCENDING)

        self.tree = Gtk.TreeView(model=self.sort_model)
        self.tree.set_tooltip_column(6)
        self.tree.connect("button-press-event", self.on_tree_button_press)

        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self.toggle)
        self.tree.append_column(Gtk.TreeViewColumn("Select", toggle, active=0))

        # Size column
        cell_size = Gtk.CellRendererText(ypad=5, xalign=1.0)
        col_size = Gtk.TreeViewColumn("Size", cell_size, text=2)
        col_size.set_sort_column_id(5)
        self.tree.append_column(col_size)

        # Advice column with color markup
        cell_advice = Gtk.CellRendererText(ypad=5)
        col_advice = Gtk.TreeViewColumn("Cleanup advice", cell_advice, markup=10)
        col_advice.set_sort_column_id(8)
        self.tree.append_column(col_advice)

        # App column
        cell_app = Gtk.CellRendererText(ypad=5)
        col_app = Gtk.TreeViewColumn("App / tool", cell_app, text=7)
        col_app.set_sort_column_id(7)
        self.tree.append_column(col_app)

        # Type column
        cell_type = Gtk.CellRendererText(ypad=5)
        col_type = Gtk.TreeViewColumn("Type", cell_type, text=1)
        col_type.set_sort_column_id(1)
        self.tree.append_column(col_type)

        # Location column
        cell_path = Gtk.CellRendererText(ypad=5, ellipsize=Pango.EllipsizeMode.MIDDLE)
        col_path = Gtk.TreeViewColumn("Location", cell_path, text=3)
        col_path.set_expand(True)
        col_path.set_sort_column_id(3)
        self.tree.append_column(col_path)

        scroll = Gtk.ScrolledWindow()
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.tree)
        main_box.pack_start(scroll, True, True, 0)

        # Detail pane
        self.detail = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.detail.set_no_show_all(True)
        main_box.pack_start(self.detail, False, False, 0)
        self.tree.get_selection().connect("changed", self.show_detail)

        # ------------------ Bottom Action Bar ------------------
        bar = Gtk.Box(spacing=12)
        main_box.pack_end(bar, False, False, 0)

        self.refresh = Gtk.Button(label="🔍 Run scan")
        self.refresh.connect("clicked", self.start)
        bar.pack_start(self.refresh, False, False, 0)

        self.stop = Gtk.Button(label="⏹ Stop scan")
        self.stop.set_no_show_all(True)
        self.stop.connect("clicked", self.cancel_scan)
        bar.pack_start(self.stop, False, False, 0)

        self.btn_open_loc = Gtk.Button(label="📁 Open in File Manager")
        self.btn_open_loc.set_tooltip_text("Open selected item's folder in system file manager")
        self.btn_open_loc.connect("clicked", self.on_open_selected_location)
        bar.pack_start(self.btn_open_loc, False, False, 0)

        self.clean = Gtk.Button(label="🧹 Review selection")
        self.clean.get_style_context().add_class("suggested-action")
        self.clean.get_style_context().add_class("cat-btn-clean")
        self.clean.connect("clicked", self.confirm)
        bar.pack_end(self.clean, False, False, 0)

        self.connect("destroy", self.on_window_destroy)

        # Active animation ticker timer
        self.anim_timer = GLib.timeout_add(150, self.anim_tick)
        self.scan_timer = None
        self.cancel = None
        if auto_start:
            self.start()

    def _set_pointer_cursor(self, widget):
        window = widget.get_window()
        if window:
            window.set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "pointer"))

    def on_window_destroy(self, *_):
        if hasattr(self, "cancel") and self.cancel:
            self.cancel.set()
        if hasattr(self, "scan_timer") and self.scan_timer:
            GLib.source_remove(self.scan_timer)
            self.scan_timer = None
        if hasattr(self, "anim_timer") and self.anim_timer:
            GLib.source_remove(self.anim_timer)
            self.anim_timer = None
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def anim_tick(self):
        if Gtk.Settings.get_default().get_property("gtk-enable-animations"):
            frame = self.animator.tick()
            self.portrait.set_from_pixbuf(frame)
        return True

    def on_mascot_clicked(self, *_):
        quote = self.animator.meow()
        self.popover.meow(quote)

    def on_filter_toggled(self, button, name):
        if button.get_active():
            self.active_filter = name
            self.filter_model.refilter()

    def on_search_changed(self, entry):
        self.filter_model.refilter()

    def _row_visible_func(self, model, iter, _):
        kind = model.get_value(iter, 1)
        path = model.get_value(iter, 3)
        advice = model.get_value(iter, 8)
        app = model.get_value(iter, 7)

        # Category filter
        if not matches_category_filter(self.active_filter, kind, advice):
            return False

        # Text search filter
        query = self.search_entry.get_text().strip().lower()
        if query:
            match = (query in path.lower() or 
                     query in app.lower() or 
                     query in kind.lower())
            if not match:
                return False
        return True

    def select_safe(self):
        changed = False
        for row in self.model:
            if row[8] == "Usually safe":
                row[0] = True
                changed = True
        if changed:
            self.update_selection_summary()
            self.popover.meow("All safe caches selected! Ready for a quick clean.")

    def select_all(self):
        if self.active_filter != "All" or self.search_entry.get_text().strip():
            for filter_row in self.filter_model:
                child_iter = self.filter_model.convert_iter_to_child_iter(filter_row.iter)
                self.model.set_value(child_iter, 0, True)
        else:
            for row in self.model:
                row[0] = True
        self.update_selection_summary()

    def deselect_all(self):
        if self.active_filter != "All" or self.search_entry.get_text().strip():
            for filter_row in self.filter_model:
                child_iter = self.filter_model.convert_iter_to_child_iter(filter_row.iter)
                self.model.set_value(child_iter, 0, False)
        else:
            for row in self.model:
                row[0] = False
        self.update_selection_summary()

    def update_trash_status(self):
        count, total = get_trash_info()
        if count > 0:
            self.btn_trash.set_label(f"🗑️ Empty Trash ({size(total)})")
            self.btn_trash.set_sensitive(True)
        else:
            self.btn_trash.set_label("🗑️ Trash is empty")
            self.btn_trash.set_sensitive(False)

    def on_empty_trash_clicked(self, *_):
        count, total = get_trash_info()
        if count == 0:
            return
        if not self.dialog(f"Permanently delete {count} items ({size(total)}) currently in your Trash?", True):
            return
        deleted, freed = empty_trash()
        self.update_trash_status()
        self.dialog(f"Emptied Trash: removed {deleted} items, reclaimed {size(freed)}!")
        self.refresh_capacity()

    def refresh_capacity(self):
        try:
            usage = shutil.disk_usage(self.root)
            selected = sum(r[5] for r in self.model if r[0])
            self.disk_bar.set_capacity(usage.used, usage.free, selected)
        except Exception:
            pass

    def update_selection_summary(self):
        chosen = [r[5] for r in self.model if r[0]]
        total = sum(chosen)
        is_scanning = hasattr(self, "refresh") and not self.refresh.get_sensitive()
        self.clean.set_sensitive(bool(chosen) and not is_scanning)
        self.clean.set_label(f"Review selection ({size(total)})" if chosen else "Review selection")
        self.refresh_capacity()

    def toggle(self, _, path_str):
        if not self.refresh.get_sensitive():
            return
        # Convert path from sort model -> filter model -> child model
        sort_iter = self.sort_model.get_iter_from_string(path_str)
        filter_iter = self.sort_model.convert_iter_to_child_iter(sort_iter)
        child_iter = self.filter_model.convert_iter_to_child_iter(filter_iter)
        
        current = self.model.get_value(child_iter, 0)
        self.model.set_value(child_iter, 0, not current)
        self.update_selection_summary()

    def on_tree_button_press(self, tree, event):
        if event.button == 3: # Right click
            path_info = tree.get_path_at_pos(int(event.x), int(event.y))
            if path_info:
                path, col, _, _ = path_info
                tree.get_selection().select_path(path)
                self.show_context_menu(event)
                return True
        return False

    def show_context_menu(self, event):
        menu = Gtk.Menu()
        item_open = Gtk.MenuItem(label="📁 Open in File Manager")
        item_open.connect("activate", self.on_open_selected_location)
        menu.append(item_open)

        item_copy = Gtk.MenuItem(label="📋 Copy Path")
        item_copy.connect("activate", self.on_copy_selected_path)
        menu.append(item_copy)

        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def get_selected_path(self):
        selection = self.tree.get_selection()
        model, sort_iter = selection.get_selected()
        if sort_iter:
            return model.get_value(sort_iter, 3)
        return None

    def on_open_selected_location(self, *_):
        target = self.get_selected_path()
        if not target:
            return
        if target == "All downloaded APT packages (administrator)":
            p = Path("/var/cache/apt/archives")
        else:
            p = Path(target)
        if not p.exists():
            self.dialog(f"Location does not exist: {target}")
            return
        folder = p if p.is_dir() else p.parent
        try:
            Gio.AppInfo.launch_default_for_uri(folder.as_uri(), None)
        except Exception:
            try:
                subprocess.Popen(["xdg-open", str(folder)])
            except OSError:
                pass

    def on_copy_selected_path(self, *_):
        target = self.get_selected_path()
        if target:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(target, -1)

    def dialog(self, text, question=False):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            text=text,
            message_type=Gtk.MessageType.QUESTION if question else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.YES_NO if question else Gtk.ButtonsType.OK,
        )
        if question:
            dlg.set_default_response(Gtk.ResponseType.NO)
        result = dlg.run()
        dlg.destroy()
        return result == Gtk.ResponseType.YES

    def start(self, *_):
        self.root = Path(self.folder.get_filename() or HOME).resolve()
        minimum = (0, 10 << 20, 100 << 20, 1 << 30)[self.minimum.get_active()]
        large = self.include_large.get_active()
        self.latest = (0, str(self.root), 0)
        self.cancel = threading.Event()
        self.stop.set_sensitive(True)
        self.stop.show()
        self.options.set_sensitive(False)
        self.btn_select_safe.set_sensitive(False)
        self.btn_select_all.set_sensitive(False)
        self.btn_deselect_all.set_sensitive(False)
        self.progress.show()
        self.model.clear()
        self.clean.set_label("Review selection")
        self.clean.set_sensitive(False)
        self.refresh.set_sensitive(False)
        
        # Switch mascot to active hunting state
        self.animator.set_state(MascotState.SCANNING)
        self.progress.set_text("CacheCat is hunting for disk clutter...")

        self.scan_timer = GLib.timeout_add(100, self.scan_tick)

        def report(count, path, targets):
            self.latest = count, path, targets

        def worker():
            try:
                usage = shutil.disk_usage(self.root)
                GLib.idle_add(self.disk_bar.set_capacity, usage.used, usage.free, 0)
                rows, errors = scan(
                    lambda row: GLib.idle_add(self.add_row, row),
                    self.root,
                    report,
                    large,
                    minimum,
                    self.cancel,
                )
                if self.cancel.is_set():
                    raise ScanStopped
                GLib.idle_add(self.loaded, rows, errors)
            except ScanStopped:
                GLib.idle_add(self.stopped)
            except Exception as e:
                GLib.idle_add(self.failed, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def scan_tick(self):
        count, path, targets = self.latest
        if Gtk.Settings.get_default().get_property("gtk-enable-animations"):
            self.progress.pulse()
        self.progress.set_text(
            f"Hunting  ·  {count:,} folders visited  ·  {targets:,} targets found"
        )
        self.status.set_text(path)
        return True

    def cancel_scan(self, *_):
        self.cancel.set()
        self.stop.set_sensitive(False)

    def stopped(self):
        self.stop_progress()
        self.model.clear()
        self.refresh.set_sensitive(True)
        self.status.set_text("Scan stopped. Choose your scan options and run again.")
        self.animator.set_state(MascotState.IDLE)

    def stop_progress(self):
        if hasattr(self, "scan_timer") and self.scan_timer:
            GLib.source_remove(self.scan_timer)
            self.scan_timer = None
        self.progress.hide()
        self.stop.hide()
        self.options.set_sensitive(True)
        self.btn_select_safe.set_sensitive(True)
        self.btn_select_all.set_sensitive(True)
        self.btn_deselect_all.set_sensitive(True)

    def failed(self, error):
        self.stop_progress()
        self.model.clear()
        self.status.set_text("Scan failed — " + error)
        self.refresh.set_sensitive(True)
        self.animator.set_state(MascotState.IDLE)

    def add_row(self, row):
        label, n, kind, items = row
        app, advice, reason = assessment(label, kind)
        tooltip = GLib.markup_escape_text(f"{label}\n{app} · {advice}\n{reason}")
        
        # Color badge markup
        if advice == "Usually safe":
            badge = f"<span foreground='#2ecc71'>●</span> {advice}"
        elif advice == "Reinstall / rebuild":
            badge = f"<span foreground='#3498db'>●</span> {advice}"
        else:
            badge = f"<span foreground='#e67e22'>●</span> {advice}"
            
        self.model.append([
            False, kind, size(n), label, (n, items), n, tooltip, app, advice, reason, badge
        ])

    def show_detail(self, selection):
        model, selected = selection.get_selected()
        if selected is None:
            self.detail.hide()
            return
        row = model[selected]
        app_escaped = GLib.markup_escape_text(row[7])
        reason_escaped = GLib.markup_escape_text(row[9])
        self.detail.set_markup(f"<b>{app_escaped}</b> · {row[10]}  —  {reason_escaped}")
        self.detail.show()

    def loaded(self, rows, errors):
        if self.cancel.is_set():
            self.stopped()
            return
        self.stop_progress()
        self.model.clear()
        for row in rows:
            self.add_row(row)
        targets = [row for row in rows if row[2] != "Large file"]
        total = sum(row[1] for row in targets)
        status = (
            f"Found {len(targets)} cleanup targets ({size(total)}) and "
            f"{len(rows) - len(targets)} large files."
            if rows
            else "Scan complete. No cleanup targets or large files found."
        )
        if errors:
            status += f"  Skipped {errors} unreadable entries."
        self.status.set_text(status)
        self.refresh.set_sensitive(True)
        self.animator.set_state(MascotState.IDLE)
        self.update_selection_summary()
        self.update_trash_status()

    def confirm(self, *_):
        selected = [r for r in self.model if r[0]]
        chosen = [(r[1], r[3], r[4], r[5]) for r in selected]
        if not chosen:
            return
        summary = "\n".join(f"• {r[7]} · {r[8]} — {r[3]}" for r in selected[:6])
        if len(chosen) > 6:
            summary += f"\n…and {len(chosen)-6} more"
        total_size = sum(item[3] for item in chosen)
        
        msg = (
            f"Clean {size(total_size)}?\n\n{summary}\n\n"
            "Large files move to Trash safely.\n"
            "Selected cache and build folders will be permanently deleted.\n"
            "APT cleanup will request administrator access."
        )
        if not self.dialog(msg, True):
            return

        self.set_sensitive(False)
        self.animator.set_state(MascotState.CLEANING)
        self.progress.show()
        self.progress.set_fraction(0.0)

        def worker():
            done = skipped = 0
            freed = 0
            errors = []
            total_items = len(chosen)
            for idx, (kind, name_label, (_, items), item_bytes) in enumerate(chosen):
                GLib.idle_add(
                    self.progress.set_text,
                    f"Sweeping clutter: {idx+1}/{total_items} · {size(freed)} freed"
                )
                GLib.idle_add(self.progress.set_fraction, (idx + 1) / total_items)
                if kind == "System":
                    try:
                        subprocess.run(["sudo", "--", "/usr/bin/apt-get", "clean"], check=True)
                        done += 1
                        freed += item_bytes
                    except (OSError, subprocess.SubprocessError) as e:
                        errors.append(str(e))
                for _, name, original in items:
                    try:
                        path = Path(name)
                        if path.resolve() != path or identity(path.lstat()) != original:
                            skipped += 1
                            continue
                        if kind == "Large file":
                            Gio.File.new_for_path(name).trash(None)
                        else:
                            if not remove_folder(name, original):
                                skipped += 1
                                continue
                        done += 1
                        freed += item_bytes
                    except (OSError, GLib.Error, RuntimeError) as e:
                        errors.append(str(e))
            GLib.idle_add(self.finished, done, skipped, freed, errors)

        threading.Thread(target=worker, daemon=True).start()

    def finished(self, done, skipped, freed, errors):
        self.set_sensitive(True)
        self.progress.hide()
        self.refresh_capacity()
        self.model.clear()
        self.clean.set_label("Review selection")
        self.clean.set_sensitive(False)
        self.update_trash_status()
        self.status.set_text(
            f"Completed {done} actions ({size(freed)} freed). Skipped {skipped} changed files. "
            f"{len(errors)} errors. Run scan again for fresh results."
        )
        # Victory animation
        self.animator.set_state(MascotState.SUCCESS)
        self.popover.meow(f"Purr-fect! Reclaimed {size(freed)} of disk space! High paw! 🐾")
        self.dialog(self.status.get_text() + ("\n" + errors[0] if errors else ""))


if __name__ == "__main__":
    App().show_all()
    Gtk.main()
