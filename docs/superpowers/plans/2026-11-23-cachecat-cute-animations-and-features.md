# CacheCat Cute Animations & Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform CacheCat into an engaging, animated, and feature-rich Linux disk cleaner with cute multi-state cat mascot animations, smooth animated disk usage visualizer, live cleanup progress ticker, smart selection controls, and expanded cleaner targets.

**Architecture:** Maintain a zero-dependency, native GTK 3 + PyGObject architecture in Python. Modularize into clear units: an animated sprite/mascot engine (`mascot.py`), an extended scanning & scanner target engine (`scanner.py`), custom modern GTK CSS & animated widgets (`ui_components.py`), and the main window coordinator (`app.py`).

**Tech Stack:** Python 3.9+, GTK 3 (via PyGObject), GLib, GdkPixbuf, Pango, standard library (`pathlib`, `shutil`, `subprocess`, `threading`, `heapq`).

**Spec:** User request: "cute ones as our cat is and put as much as in there u like it must be kewl and awesome app". Deliver a cute cat companion with expressive pixel-art animation states (idle purr/blink, active scanning hunt, sweeping/dusting cleanup, victory purr/stars), interactive speech bubble/meow reaction, animated disk space capacity bar, batch selection ("Select Safe", "Deselect All"), quick category filters, "Open in File Manager" action, Trash cleaner, and extended targets (Docker, venv, IDE caches).

## Global Constraints

- Must run on Linux with Python 3.9+ and PyGObject / GTK 3 without requiring heavy external pip packages.
- Must honor `gtk-enable-animations` setting for motion accessibility.
- Preserve all existing safety protections: canonical path checks, mountpoint protection, device id verification, and confirmation dialogs.
- Clean separation of UI logic, animation loops, and background scanning threads to keep the UI at 60 FPS without jank.

## Review Focus

1. Rapid user clicks during active scan or animation ticks must not cause race conditions or unhandled GLib exceptions.
2. Animated sprites must correctly clean up timers when windows close or scan states change to prevent memory leaks or background CPU usage.
3. Category filters must accurately update selection totals without deselecting items hidden from the current filter.
4. "Open in File Manager" must handle non-existent, deleted, or permission-restricted paths safely.
5. Trash bin calculation and cleanup must gracefully handle systems where trash directories don't exist yet or contain unreadable files.

---

### Task 1: Pixel-Art Mascot Animation Engine (`mascot.py`)

**Files:**
- Create: `mascot.py`
- Test: `tests/test_mascot.py`

**Interfaces:**
- Consumes: `cachecat.xpm`
- Produces: `MascotAnimator` class with states:
  - `IDLE`: Subtle breathing, occasional ear twitch and gentle blink
  - `SCANNING`: Eyes looking left/right, whiskers twitching, active hunting mode
  - `CLEANING`: Sweeping broom / paw dusting animation with sparkles
  - `SUCCESS`: Happy closed-eye smile `(^•ω•^)`, sparkling stars / heart reaction
  - `meow()`: On-click reaction (purr / meow frame + tooltip or speech bubble)

- [ ] **Step 1: Write test for MascotAnimator frame generation and state switching**

```python
# tests/test_mascot.py
import pytest
from pathlib import Path

def test_mascot_animator_initialization():
    from mascot import MascotAnimator, MascotState
    animator = MascotAnimator(Path("cachecat.xpm"))
    assert animator.state == MascotState.IDLE
    pixbuf = animator.get_current_frame()
    assert pixbuf is not None
    assert pixbuf.get_width() == 64
    assert pixbuf.get_height() == 64

def test_mascot_animator_state_transition():
    from mascot import MascotAnimator, MascotState
    animator = MascotAnimator(Path("cachecat.xpm"))
    animator.set_state(MascotState.SCANNING)
    assert animator.state == MascotState.SCANNING
    frame1 = animator.get_current_frame()
    animator.tick()
    frame2 = animator.get_current_frame()
    assert frame1 is not None and frame2 is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_mascot.py`
Expected: FAIL with "No module named 'mascot'"

- [ ] **Step 3: Implement `MascotAnimator` in `mascot.py`**

Implement `MascotAnimator` loading `cachecat.xpm`, generating sprite frames for `IDLE`, `SCANNING`, `CLEANING`, and `SUCCESS` states using pixbuf manipulation (ear twitching, eye tracking, broom/paw cleaning, victory stars) with an update `tick()` method.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_mascot.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mascot.py tests/test_mascot.py
git commit -m "feat: add multi-state pixel-art mascot animation engine"
```

---

### Task 2: Extended Cleanup Targets & Trash Engine (`scanner.py`)

**Files:**
- Create: `scanner.py`
- Modify: `app.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: filesystem paths, mountpoints
- Produces:
  - `scan(found, root, progress, large_files, minimum, cancel, include_trash)`
  - `get_trash_info() -> tuple[int, int]` (count, total_bytes)
  - `empty_trash() -> tuple[int, int]` (deleted_count, freed_bytes)
  - New targets: Docker caches, Python `.venv` / `venv`, JetBrains/VS Code caches, Flatpak app cache.

- [ ] **Step 1: Write tests for extended scanner targets and trash utilities**

```python
# tests/test_scanner.py
from pathlib import Path
from scanner import cleanup_roots, project_target, assessment

def test_extended_project_targets():
    assert project_target(Path("/tmp/proj/.venv"), {"pyproject.toml"}) == "Python virtual environment"
    assert project_target(Path("/tmp/proj/venv"), {"requirements.txt"}) == "Python virtual environment"

def test_assessment_extended_targets():
    app, advice, reason = assessment("/tmp/proj/.venv", "Python virtual environment")
    assert app == "Python venv"
    assert "Review first" in advice
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scanner.py`
Expected: FAIL with "No module named 'scanner'"

- [ ] **Step 3: Implement extended scanning logic in `scanner.py`**

Extract and extend scanner functions from `app.py` to `scanner.py`: add `.venv` detection, IDE caches (`.cache/JetBrains`, `.config/Code/Cache`), Flatpak caches (`.var/app/*/cache`), and Trash measurement/empty helpers.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scanner.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scanner.py tests/test_scanner.py
git commit -m "feat: add extended cleaner targets and trash management utilities"
```

---

### Task 3: Modern UI Components & Animated Disk Bar (`ui_components.py`)

**Files:**
- Create: `ui_components.py`
- Test: `tests/test_ui_components.py`

**Interfaces:**
- Produces:
  - `DiskUsageBar(Gtk.Box)`: Animated multi-color usage gauge showing Used, Selected for Cleanup (animated pulsing/striped), and Free space.
  - `CategoryFilterBar(Gtk.Box)`: Filter toggle pills (`All`, `Safe Caches`, `Build Files`, `Dependencies`, `Large Files`).
  - `CuteSpeechBubble(Gtk.Popover / Gtk.EventBox)`: Adorable dialogue popover for CacheCat meows and tips.
  - `apply_custom_theme()`: GTK CSS injection with smooth transitions, modern pill badges for safety advice, and clean typography.

- [ ] **Step 1: Write tests for UI component creation and filtering helpers**

```python
# tests/test_ui_components.py
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ui_components import matches_category_filter

def test_category_filters():
    assert matches_category_filter("All", "Thumbnail previews", "Usually safe") is True
    assert matches_category_filter("Safe Caches", "Thumbnail previews", "Usually safe") is True
    assert matches_category_filter("Safe Caches", "Project build output", "Review first") is False
    assert matches_category_filter("Large Files", "Large file", "Review first") is True
    assert matches_category_filter("Build Files", "Project build output", "Review first") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ui_components.py`
Expected: FAIL with "No module named 'ui_components'"

- [ ] **Step 3: Implement `ui_components.py`**

Create `DiskUsageBar`, `matches_category_filter`, cute CSS styles with color-coded safety badges, and interactive speech bubble popovers.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ui_components.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui_components.py tests/test_ui_components.py
git commit -m "feat: add animated disk capacity gauge and modern CSS badge styling"
```

---

### Task 4: Integrate Animation Loops, Mascot Interactions & Quick Selection in `app.py`

**Files:**
- Modify: `app.py`
- Modify: `README.md`

**Interfaces:**
- Wires together `MascotAnimator`, `DiskUsageBar`, `CategoryFilterBar`, and `scanner.py`.
- Features added:
  - Interactive Cat Mascot: Click to meow / purr with cute speech bubbles ("Purr! Found 2.4 GB of hairballs!", "Cleaning up now, meow!").
  - Animated cat states during scanning, cleaning, and victory completion.
  - "✨ Select Safe" one-click button: quickly selects all "Usually safe" items.
  - "Deselect All" button.
  - Right-click / button: "Open in File Manager" (`Gio.AppInfo.launch_default_for_uri`).
  - Search / Filter bar to find targets quickly.
  - Live animated cleaning progress counter showing MB freed in real-time.

- [ ] **Step 1: Update `app.py` with the complete feature set and animations**
- [ ] **Step 2: Test launching and running scans programmatically and verifying all flows**
- [ ] **Step 3: Update `README.md` to document the new features, cat mascot animations, and shortcuts**
- [ ] **Step 4: Commit**

```bash
git add app.py README.md
git commit -m "feat: integrate cute cat animations, animated disk bar, and quick selection"
```

---

### Task 5: End-to-End Verification and Polish

**Files:**
- `app.py`, `mascot.py`, `scanner.py`, `ui_components.py`

- [ ] **Step 1: Run full test suite (`pytest`) to ensure 100% pass rate**
- [ ] **Step 2: Verify desktop app launch and execution via `launch.sh`**
- [ ] **Step 3: Verify clean exit on window close and cancel buttons without orphaned threads**
- [ ] **Step 4: Commit all final changes**
