import heapq
import os
import stat
import subprocess
import threading
import re
import shutil
from pathlib import Path

HOME = Path.home()
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache")
DATA = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")
TRASH = DATA / "Trash"
APT = Path("/var/cache/apt/archives")

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
    "VS Code cache": "VS Code",
    "JetBrains cache": "JetBrains IDE",
    "Docker build cache": "Docker",
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


def size(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024


def identity(s):
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def cleanup_roots():
    roots = {CACHE / sub: label for sub, label in CATEGORIES.items()}
    roots.update({
        HOME / ".npm/_cacache": "npm download cache",
        HOME / ".npm/_npx": "npx temporary installs",
        HOME / ".npm/_logs": "npm logs",
        DATA / "pnpm/store": "pnpm package store",
        CACHE / "pnpm": "pnpm cache",
        CACHE / "node-gyp": "Node.js build headers",
        CACHE / "yarn": "Yarn cache",
        HOME / ".gradle/caches": "Gradle caches",
        HOME / ".cargo/registry/cache": "Cargo crate downloads",
        HOME / ".bun/install/cache": "Bun package cache",
        CACHE / "Code/Cache": "VS Code cache",
        CACHE / "Code/CachedData": "VS Code cache",
        CACHE / "VSCodium/Cache": "VS Code cache",
        CACHE / "JetBrains": "JetBrains cache",
        HOME / ".docker/buildx/refs": "Docker build cache",
    })
    
    # Browsers
    for browser in ("google-chrome", "chromium", "microsoft-edge", "BraveSoftware/Brave-Browser"):
        for pattern in ("Default/Cache", "Profile */Cache", "Default/Code Cache", "Profile */Code Cache"):
            for path in (CACHE / browser).glob(pattern):
                roots[path] = "Browser cache"
    for path in (CACHE / "mozilla/firefox").glob("*/cache2"):
        roots[path] = "Firefox HTTP cache"
        
    # Flatpak app caches
    for path in (HOME / ".var/app").glob("*/cache"):
        roots[path] = f"Flatpak app cache ({path.parent.name})"

    pnpm_home = os.environ.get("PNPM_HOME")
    if pnpm_home:
        roots[Path(pnpm_home) / "store"] = "pnpm package store"
    return roots


def project_target(path, siblings):
    if path.name in {".venv", "venv"} and any(sig in siblings for sig in {"pyproject.toml", "requirements.txt", "setup.py", "Pipfile"}):
        return "Python virtual environment"
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
    return None


def assessment(label, kind):
    path = Path(label)
    cache_app = CACHE_APPS.get(kind)
    if kind == "Browser cache":
        try:
            browser = path.relative_to(CACHE).parts[0]
            cache_app = {"google-chrome": "Google Chrome", "chromium": "Chromium",
                         "microsoft-edge": "Microsoft Edge", "BraveSoftware": "Brave"}.get(browser, "Web Browser")
        except Exception:
            cache_app = "Web Browser"
    if kind == "Python tooling cache":
        cache_app = {".pytest_cache": "pytest", ".ruff_cache": "Ruff",
                     ".mypy_cache": "mypy"}.get(path.name, "Python tooling")
    if cache_app:
        return cache_app, "Usually safe", "Recognized cache. Close the app first. It can rebuild or download these files when needed."
    if kind in DOWNLOAD_APPS:
        return DOWNLOAD_APPS[kind], "Reinstall / rebuild", "Removing these files can interrupt projects or offline work until the tool restores them."
    if kind == "Python virtual environment":
        return "Python venv", "Review first", f"Virtualenv in {path.parent.name}. Can be recreated if you have requirements.txt or pyproject.toml."
    if kind == "Python bytecode cache":
        return "Python", "Review first", "Python can regenerate bytecode if you still have the matching source files."
    if kind.startswith("Flatpak app cache"):
        return "Flatpak", "Usually safe", "Cached data for sandboxed desktop application. Will recreate as needed."
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
    try:
        with open("/proc/self/mountinfo", encoding="utf-8", errors="surrogateescape") as mounts:
            for line in mounts:
                mount = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), line.split()[4])
                yield Path(mount)
    except OSError:
        return


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


def get_trash_info():
    """Returns (file_count, total_size_bytes) of user's desktop trash."""
    files_dir = TRASH / "files"
    if not files_dir.is_dir():
        return 0, 0
    count = 0
    total = 0
    try:
        for entry in os.scandir(files_dir):
            count += 1
            try:
                s = entry.stat(follow_symlinks=False)
                total += s.st_size
                if entry.is_dir(follow_symlinks=False):
                    for root, dirs, files in os.walk(entry.path):
                        for f in files:
                            try:
                                total += os.path.getsize(os.path.join(root, f))
                            except OSError:
                                pass
            except OSError:
                pass
    except OSError:
        pass
    return count, total


def empty_trash():
    """Permanently deletes items inside Trash files and info directories."""
    deleted = 0
    freed = 0
    for subdir in ("files", "info"):
        target_dir = TRASH / subdir
        if target_dir.is_dir():
            for item in target_dir.iterdir():
                try:
                    s = item.stat(follow_symlinks=False)
                    freed += s.st_size
                    if item.is_dir(follow_symlinks=False):
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    deleted += 1
                except OSError:
                    pass
    return deleted, freed


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
        if base in (HOME / ".local/share/Trash", TRASH):
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

    if root == HOME and Path("/usr/bin/apt-get").exists() and APT.is_dir():
        try:
            total = sum(p.stat().st_size for p in APT.glob("*.deb") if p.is_file())
            if total and total >= minimum:
                rows.append(("All downloaded APT packages (administrator)", total, "System", []))
        except OSError:
            pass

    rows.sort(key=lambda row: -row[1])
    rows.extend((path, n, "Large file", [(n, path, ident)])
                for n, path, ident in sorted(largest, reverse=True))
    return rows, errors
