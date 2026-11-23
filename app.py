import heapq
import os
import stat
import subprocess
import threading
import re
import shutil
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, GObject, Gtk, Pango, GdkPixbuf

HOME = Path.home()
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache")
CATEGORIES = {
    "thumbnails": "Thumbnail previews",
    "pip/http": "Python package downloads",
    "pip/http-v2": "Python package downloads",
    "pip/wheels": "Cached Python wheels",
    "uv": "uv package cache",
    "pypoetry/artifacts": "Poetry package downloads",
    "composer/files": "Composer package downloads",
    "go-build": "Go build cache",
    "ccache": "C/C++ compiler cache",
    "sccache": "Compiler cache",
    "mesa_shader_cache": "Graphics shader cache",
    "mesa_shader_cache_db": "Graphics shader cache",
    "radv_builtin_shaders": "Graphics shader cache",
    "fontconfig": "Font lookup cache",
    "ms-playwright": "Playwright browser downloads",
    "puppeteer": "Puppeteer browser downloads",
    "Cypress": "Cypress test binaries",
}

APT = Path("/var/cache/apt/archives")


def size(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024


def identity(s):
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def cleanup_roots():
    data = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")
    roots = {CACHE / sub: label for sub, label in CATEGORIES.items()}
    roots.update({
        HOME / ".npm/_cacache": "npm download cache",
        HOME / ".npm/_npx": "npx temporary installs",
        HOME / ".npm/_logs": "npm logs",
        data / "pnpm/store": "pnpm package store",
        CACHE / "pnpm": "pnpm cache",
        CACHE / "node-gyp": "Node.js build headers",
        CACHE / "yarn": "Yarn cache",
        HOME / ".gradle/caches": "Gradle caches",
    })
    roots[HOME / ".cargo/registry/cache"] = "Cargo crate downloads"
    roots[HOME / ".bun/install/cache"] = "Bun package cache"
    for browser in ("google-chrome", "chromium", "microsoft-edge", "BraveSoftware/Brave-Browser"):
        for pattern in ("Default/Cache", "Profile */Cache", "Default/Code Cache", "Profile */Code Cache"):
            for path in (CACHE / browser).glob(pattern):
                roots[path] = "Browser cache"
    for path in (CACHE / "mozilla/firefox").glob("*/cache2"):
        roots[path] = "Firefox HTTP cache"
    pnpm_home = os.environ.get("PNPM_HOME")
    if pnpm_home:
        roots[Path(pnpm_home) / "store"] = "pnpm package store"
    return roots


def project_target(path, siblings):
    if path.name in {".pytest_cache", ".mypy_cache", ".ruff_cache"}:
        return "Python tooling cache"
    if path.name == "__pycache__":
        return "Python bytecode cache"
    if path.name == ".dart_tool" and "pubspec.yaml" in siblings:
        return "Dart tooling output"
    if path.name == "build" and "pubspec.yaml" in siblings:
        return "Flutter build output"
    if path.name == ".pnpm-store":
        return "pnpm package store"
    if "package.json" in siblings:
        if path.name == "node_modules":
            return "Installed Node dependencies"
        if path.name in {".next", ".nuxt", ".turbo", ".parcel-cache", ".svelte-kit",
                         "dist", "build", "coverage", ".output"}:
            return "Project build output"
    if path.name == "target" and {"Cargo.toml", "pom.xml"}.intersection(siblings):
        return "Project build output"
    if path.name == "build" and {"build.gradle", "build.gradle.kts"}.intersection(siblings):
        return "Gradle build output"


# Assess only recognized scanner categories. New categories default to review.
CACHE_APPS = {
    "Thumbnail previews": "Linux desktop",
    "Python package downloads": "pip",
    "Cached Python wheels": "pip",
    "uv package cache": "uv",
    "Poetry package downloads": "Poetry",
    "Composer package downloads": "Composer",
    "Go build cache": "Go",
    "C/C++ compiler cache": "ccache",
    "Compiler cache": "sccache",
    "Graphics shader cache": "Mesa",
    "Font lookup cache": "Fontconfig",
    "npm download cache": "npm",
    "pnpm cache": "pnpm",
    "Node.js build headers": "node-gyp",
    "Yarn cache": "Yarn",
    "Cargo crate downloads": "Cargo",
    "Bun package cache": "Bun",
    "Firefox HTTP cache": "Firefox",
}

DOWNLOAD_APPS = {
    "Playwright browser downloads": "Playwright",
    "Puppeteer browser downloads": "Puppeteer",
    "Cypress test binaries": "Cypress",
    "Installed Node dependencies": "Node.js",
    "Gradle caches": "Gradle",
    "pnpm package store": "pnpm",
    "npx temporary installs": "npx",
    "Dart tooling output": "Dart",
}


def assessment(label, kind):
    path = Path(label)
    cache_app = CACHE_APPS.get(kind)
    if kind == "Browser cache":
        browser = path.relative_to(CACHE).parts[0]
        cache_app = {"google-chrome": "Google Chrome", "chromium": "Chromium",
                     "microsoft-edge": "Microsoft Edge", "BraveSoftware": "Brave"}.get(browser)
    if kind == "Python tooling cache":
        cache_app = {".pytest_cache": "pytest", ".ruff_cache": "Ruff",
                     ".mypy_cache": "mypy"}.get(path.name)
    if cache_app:
        return cache_app, "Usually safe", "Recognized cache. Close the app first. It can rebuild or download these files when needed."
    if kind in DOWNLOAD_APPS:
        return DOWNLOAD_APPS[kind], "Reinstall / rebuild", "Removing these files can interrupt projects or offline work until the tool restores them."
    if kind == "Python bytecode cache":
        return "Python", "Review first", "Python can regenerate bytecode if you still have the matching source files."
    if kind.endswith("build output"):
        app = {"Flutter build output": "Flutter", "Gradle build output": "Gradle"}.get(kind)
        if not app and path.name == "target":
            app = "Cargo" if (path.parent / "Cargo.toml").is_file() else "Maven"
        if not app:
            app = {".next": "Next.js", ".nuxt": "Nuxt", ".svelte-kit": "SvelteKit",
                   ".parcel-cache": "Parcel", ".turbo": "Turborepo"}.get(path.name, "Node.js project")
        return app, "Review first", f"Build output in {path.parent.name}. Check for release artifacts or edited files before deleting the folder."
    if kind == "npm logs":
        return "npm", "Review first", "Deleting these logs removes diagnostic history."
    if kind == "System":
        return "APT", "Review first", "Clears all downloaded APT packages. Offline reinstalls may need another download."
    return "Unknown", "Review first", "CacheCat could not establish which app owns this item. Check the full path and contents before selecting it."


def mount_points():
    with open("/proc/self/mountinfo", encoding="utf-8", errors="surrogateescape") as mounts:
        for line in mounts:
            mount = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), line.split()[4])
            yield Path(mount)


def contains_mount(path):
    return any(mount.is_relative_to(path) for mount in mount_points())


def remove_folder(name, original):
    path = Path(name)
    if path.resolve() != path or identity(path.lstat()) != original or contains_mount(path):
        return False
    shutil.rmtree(path)
    return True


class ScanStopped(Exception):
    pass


def measure(path, cancel):
    with subprocess.Popen(["/usr/bin/du", "-sx", "-B1", "--", str(path)],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        while True:
            if cancel.is_set():
                process.kill()
                process.communicate()
                raise ScanStopped
            try:
                output, _ = process.communicate(timeout=0.2)
                return None if process.returncode else int(output.split(maxsplit=1)[0])
            except subprocess.TimeoutExpired:
                continue


def scan(found=None, root=HOME, progress=None, large_files=True, minimum=0, cancel=None):
    cancel = cancel or threading.Event()
    roots = cleanup_roots()
    rows = []
    largest = []
    errors = 0
    def skipped(_):
        nonlocal errors
        errors += 1
    mounted_trees = {ancestor for mount in mount_points() for ancestor in (mount, *mount.parents)}
    device = root.stat().st_dev
    visited = 0
    for folder, dirs, names in os.walk(root, onerror=skipped):
        if cancel.is_set():
            raise ScanStopped
        base = Path(folder)
        visited += 1
        if progress:
            progress(visited, folder, len(rows))
        if base in (HOME / ".local/share/Trash", Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share") / "Trash"):
            dirs.clear()
            continue
        siblings = set(names)
        for name in dirs[:]:
            path = base / name
            try:
                s = path.lstat()
                if s.st_dev != device or stat.S_ISLNK(s.st_mode):
                    dirs.remove(name)
                    continue
                kind = roots.get(path) or project_target(path, siblings)
                if kind:
                    dirs.remove(name)
                    if path in mounted_trees:
                        continue
                    if progress:
                        progress(visited, str(path), len(rows))
                    n = measure(path, cancel)
                    if n is None:
                        skipped(None)
                        continue
                    if n < minimum:
                        continue
                    row = (str(path), n, kind, [(n, str(path), identity(s))])
                    rows.append(row)
                    if found:
                        found(row)
            except OSError as e:
                skipped(e)
                if name in dirs:
                    dirs.remove(name)
        if not large_files:
            continue
        for name in names:
            if cancel.is_set():
                raise ScanStopped
            path = base / name
            try:
                s = path.lstat()
            except OSError as e:
                skipped(e)
                continue
            if not stat.S_ISREG(s.st_mode) or not s.st_size or s.st_size < minimum:
                continue
            item = (s.st_size, str(path), identity(s))
            if len(largest) < 40:
                heapq.heappush(largest, item)
            elif item > largest[0]:
                heapq.heapreplace(largest, item)
    if root == HOME and Path("/usr/bin/apt-get").exists():
        total = sum(p.stat().st_size for p in APT.glob("*.deb") if p.is_file())
        if total and total >= minimum:
            rows.append(("All downloaded APT packages (administrator)", total, "System", []))
    rows.sort(key=lambda row: -row[1])
    rows.extend((path, n, "Large file", [(n, path, ident)])
                for n, path, ident in sorted(largest, reverse=True))
    return rows, errors


class App(Gtk.Window):
    def __init__(self):
        super().__init__(title="CacheCat · Disk Cleaner")
        mascot = GdkPixbuf.Pixbuf.new_from_file(str(Path(__file__).with_name("cachecat.xpm")))
        self.set_icon(mascot)
        self.set_default_size(960, 600)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)
        self.add(box)
        heading = Gtk.Box(spacing=12)
        box.pack_start(heading, False, False, 0)
        blink = mascot.copy()
        # Close both eyes using pixels from the same sprite palette.
        for x in (6, 15):
            for y in (9, 11):
                mascot.copy_area(x, 8, 3, 1, blink, x, y)
            mascot.copy_area(x, 9, 3, 1, blink, x, 10)
        self.frames = [frame.scale_simple(64, 64, GdkPixbuf.InterpType.NEAREST)
                       for frame in (mascot, blink)]
        self.portrait = Gtk.Image.new_from_pixbuf(self.frames[0])
        heading.pack_start(self.portrait, False, False, 0)
        title = Gtk.Label(xalign=0)
        title.set_markup("<span size='xx-large' weight='bold'>CacheCat</span>\nDisk space cleaner")
        heading.pack_start(title, True, True, 0)
        self.capacity = Gtk.Label()
        self.capacity.get_style_context().add_class("dim-label")
        heading.pack_end(self.capacity, False, False, 0)
        options = Gtk.Box(spacing=8)
        box.pack_start(options, False, False, 0)
        options.pack_start(Gtk.Label(label="Scan folder"), False, False, 0)
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
        self.options = options
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_no_show_all(True)
        box.pack_start(self.progress, False, False, 0)
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        box.pack_start(self.status, False, False, 0)
        self.model = Gtk.ListStore(bool, str, str, str, object, GObject.TYPE_UINT64, str, str, str, str)
        tree = Gtk.TreeView(model=self.model)
        self.model.set_sort_column_id(5, Gtk.SortType.DESCENDING)
        tree.set_tooltip_column(6)
        tree.set_search_column(3)
        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self.toggle)
        tree.append_column(Gtk.TreeViewColumn("Select", toggle, active=0))
        for index, label in ((2, "Size"), (8, "Cleanup advice"), (7, "App / tool"), (1, "Type"), (3, "Location")):
            cell = Gtk.CellRendererText(ypad=5)
            column = Gtk.TreeViewColumn(label, cell, text=index)
            if index == 2:
                cell.set_property("xalign", 1.0)
                column.set_sort_column_id(5)
            else:
                column.set_sort_column_id(index)
            if index == 3:
                cell.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
                column.set_expand(True)
            tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(tree)
        box.pack_start(scroll, True, True, 0)
        self.detail = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.detail.set_no_show_all(True)
        box.pack_start(self.detail, False, False, 0)
        tree.get_selection().connect("changed", self.show_detail)
        bar = Gtk.Box(spacing=12)
        box.pack_end(bar, False, False, 0)
        self.refresh = Gtk.Button(label="Run scan")
        self.refresh.connect("clicked", self.start)
        bar.pack_start(self.refresh, False, False, 0)
        self.stop = Gtk.Button(label="Stop scan")
        self.stop.set_no_show_all(True)
        self.stop.connect("clicked", self.cancel_scan)
        bar.pack_start(self.stop, False, False, 0)
        self.clean = Gtk.Button(label="Review selection")
        self.clean.get_style_context().add_class("suggested-action")
        self.clean.connect("clicked", self.confirm)
        bar.pack_end(self.clean, False, False, 0)
        self.connect("destroy", Gtk.main_quit)
        self.start()

    def dialog(self, text, question=False):
        dlg = Gtk.MessageDialog(transient_for=self, modal=True, text=text,
            message_type=Gtk.MessageType.QUESTION if question else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.YES_NO if question else Gtk.ButtonsType.OK)
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
        self.progress.show()
        self.phase = 0
        self.tick()
        self.timer = GLib.timeout_add(125, self.tick)
        self.model.clear()
        self.clean.set_label("Review selection")
        self.clean.set_sensitive(False)
        self.refresh.set_sensitive(False)
        def report(count, path, targets):
            self.latest = count, path, targets

        def worker():
            try:
                usage = shutil.disk_usage(self.root)
                GLib.idle_add(self.capacity.set_text, f"{size(usage.free)} free of {size(usage.total)}")
                rows, errors = scan(lambda row: GLib.idle_add(self.add_row, row),
                                    self.root, report, large, minimum, self.cancel)
                if self.cancel.is_set():
                    raise ScanStopped
                GLib.idle_add(self.loaded, rows, errors)
            except ScanStopped:
                GLib.idle_add(self.stopped)
            except Exception as e:
                GLib.idle_add(self.failed, str(e))
        threading.Thread(target=worker, daemon=True).start()

    def cancel_scan(self, *_):
        self.cancel.set()
        self.stop.set_sensitive(False)

    def stopped(self):
        self.stop_progress()
        self.model.clear()
        self.refresh.set_sensitive(True)
        self.status.set_text("Scan stopped. Choose your scan options and run again.")

    def tick(self):
        count, path, targets = self.latest
        if Gtk.Settings.get_default().get_property("gtk-enable-animations"):
            self.progress.pulse()
            self.phase = (self.phase + 1) % 24
            self.portrait.set_from_pixbuf(self.frames[int(self.phase in (14, 15))])
        else:
            self.portrait.set_from_pixbuf(self.frames[0])
            self.progress.set_fraction(0)
        self.progress.set_text(f"Scanning  ·  {count:,} folders visited  ·  {targets:,} targets found")
        self.status.set_text(path)
        return True

    def stop_progress(self):
        GLib.source_remove(self.timer)
        self.portrait.set_from_pixbuf(self.frames[0])
        self.progress.hide()
        self.stop.hide()
        self.options.set_sensitive(True)

    def failed(self, error):
        self.stop_progress()
        self.model.clear()
        self.status.set_text("Scan failed — " + error)
        self.refresh.set_sensitive(True)

    def add_row(self, row):
        label, n, kind, items = row
        app, advice, reason = assessment(label, kind)
        tooltip = GLib.markup_escape_text(f"{label}\n{app} · {advice}\n{reason}")
        self.model.append([False, kind, size(n), label, (n, items), n, tooltip, app, advice, reason])

    def show_detail(self, selection):
        model, selected = selection.get_selected()
        if selected is None:
            self.detail.hide()
            return
        row = model[selected]
        self.detail.set_text(f"{row[7]} · {row[8]}  —  {row[9]}")
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
        status = (f"{len(targets)} cleanup targets ({size(total)})  ·  "
                  f"{len(rows) - len(targets)} large files. Select items to review."
                  if rows else "Scan complete. No cleanup targets or large files found.")
        if errors:
            status += f"  Skipped {errors} unreadable entries."
        self.status.set_text(status)
        self.refresh.set_sensitive(True)

    def toggle(self, _, path):
        if not self.refresh.get_sensitive():
            return
        row = self.model[path]
        row[0] = not row[0]
        chosen = [r[4][0] for r in self.model if r[0]]
        self.clean.set_sensitive(bool(chosen))
        self.clean.set_label(f"Review selection ({size(sum(chosen))})")

    def confirm(self, *_):
        selected = [r for r in self.model if r[0]]
        chosen = [(r[1], r[3], r[4]) for r in selected]
        summary = "\n".join(f"{r[7]} · {r[8]} — {r[3]}" for r in selected[:6])
        if len(chosen) > 6:
            summary += f"\n…and {len(chosen)-6} more"
        if not self.dialog(f"Clean {size(sum(data[0] for _, _, data in chosen))}?\n\n{summary}\n\nLarge files move to Trash. Empty Trash later to reclaim space. Selected folders and ALL current contents are permanently deleted. Review build folders for files you want to keep. Dependencies may need reinstalling. APT cleanup clears its entire download cache and asks for administrator access.", True):
            return
        self.set_sensitive(False)
        self.status.set_text("Cleaning selected items…")
        def worker():
            done = skipped = 0
            errors = []
            for kind, _, (_, items) in chosen:
                if kind == "System":
                    try:
                        subprocess.run(["sudo", "--", "/usr/bin/apt-get", "clean"], check=True)
                        done += 1
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
                    except (OSError, GLib.Error, RuntimeError) as e:
                        errors.append(str(e))
            GLib.idle_add(self.finished, done, skipped, errors)
        threading.Thread(target=worker, daemon=True).start()

    def finished(self, done, skipped, errors):
        self.set_sensitive(True)
        usage = shutil.disk_usage(self.root)
        self.capacity.set_text(f"{size(usage.free)} free of {size(usage.total)}")
        self.model.clear()
        self.clean.set_label("Review selection")
        self.clean.set_sensitive(False)
        self.status.set_text(f"Completed {done} actions. Skipped {skipped} changed files. {len(errors)} errors. Scan again for current results.")
        self.dialog(self.status.get_text() + ("\n" + errors[0] if errors else ""))


if __name__ == "__main__":
    App().show_all()
    Gtk.main()
