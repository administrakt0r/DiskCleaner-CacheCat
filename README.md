# CacheCat DiskCleaner utility · Cute & Powerful Disk Cleaner

See what is taking up space on your Linux desktop, then choose what to remove. CacheCat is an adorable, animated disk cleaner featuring our expressive pixel-art cat companion who hunts down bloated caches, project build clutter, and large files.


## Features & Controls

- **✨ Select Safe**: One-click batch selection of all low-risk caches (thumbnails, pip, npm, shader caches, etc.) without manual checking.
- **Quick Selection Controls**: Select All and Deselect All buttons.
- **Category Filter Pills**: Instantly toggle between `All`, `Safe Caches`, `Build Files`, `Dependencies`, and `Large Files`.
- **Instant Search**: Filter targets on the fly by typing in the search box.
- **📁 Open in File Manager**: Inspect any folder or file before deleting it via right-click context menu or the bottom action button.
- **🗑️ Trash Manager**: View desktop Trash size and empty it directly from CacheCat.
- **Expanded Targets**:
  - Package caches: npm, pnpm, yarn, pip, uv, poetry, cargo, composer, go, bun.
  - Project build outputs: `node_modules`, `target`, `dist`, `build`, `.next`, `.nuxt`, `.turbo`, `.svelte-kit`.
  - Python environments: `.venv` and `venv` directories.
  - Developer tooling: VS Code, JetBrains IDE caches, ccache, sccache, Mesa shaders, Cypress, Playwright.
  - Browser caches: Google Chrome, Chromium, Firefox, Brave, Microsoft Edge.
  - Flatpak and sandboxed application caches.
  - APT package cache (`sudo apt-get clean`).
  - Top 40 largest regular files.

## First launch

1. Double-click **CacheCat** on this desktop or select **CacheCat** in the applications menu.
2. The installed shortcuts point to the current project folder. If you move the folder, run `sh launch.sh` inside it and update the shortcuts to point to its new location.
3. If a requirement is missing, the launcher shows the package command and asks for permission. Press Enter to decline or type **y** to proceed.

Use a graphical Linux session with Python 3.9 or newer, PyGObject and GTK 3. Automatic setup recognizes APT, DNF, pacman and Zypper. Start the app as your regular user.

## Review and clean

The **App / tool** column identifies the likely owner from known cache paths and project markers. Select a row to read its cleanup advice.
- **Usually safe** (Green): Recognized caches. Safe to delete; apps rebuild or download them when needed.
- **Review first** (Amber): Build outputs, virtual environments, diagnostic logs, or large files.
- **Reinstall / rebuild** (Blue): Installed dependencies (like `node_modules`) that require reinstalling before running projects.

Large files move safely to your desktop Trash. Selected cache and build folders are permanently deleted upon confirmation.

## Privacy

Scanning and cleanup run 100% locally on your machine. No telemetry, no remote reporting, no accounts.

## Uninstall

Close CacheCat, then double-click **Uninstall Disk Cleaner.desktop**, or run `sh uninstall.sh` from the project folder. Type **REMOVE** to confirm.
