# CacheCat

See what is taking up space on your Linux desktop, then choose what to remove. CacheCat shows recognized caches and up to 40 of the largest other files in your home folder. Every scan starts with an empty selection.

## First launch

1. Double-click **CacheCat** on this desktop or select **CacheCat** in the applications menu.
2. The installed shortcuts point to the current project folder. If you move the folder, run `sh launch.sh` inside it and update the shortcuts to point to its new location.
3. If a requirement is missing, the launcher shows the package command and asks for permission. Press Enter to decline or type **y** to proceed. Your package manager may ask for your sudo password in the terminal. Password characters are normally hidden.

Use a graphical Linux session with Python 3.9 or newer, PyGObject and GTK 3. Automatic setup recognizes APT, DNF, pacman and Zypper. On other distributions, install the requirements with your software manager. Start the app as your regular user.

## Scan options

Choose a folder, a minimum item size, and whether to include individual large files. Click **Run scan** to apply your choices. The moving scan bar shows folders visited and cleanup targets found. The path below it shows where CacheCat is working. Use **Stop scan** to discard partial results and change options.

## Review and clean

The **App / tool** column identifies the likely owner from known cache paths and project markers. Select a row to read its cleanup advice. **Usually safe** identifies recognized caches. **Reinstall / rebuild** flags items that may be needed for tools or projects to run. **Review first** includes build outputs, diagnostic history, and files with unknown ownership. CacheCat blinks while scanning when desktop animations are enabled.

- The scanner lists recognized cleanup folders as it finds them. When the scan finishes, review their full paths and sizes. Each row selects one entire folder.
- Results start in descending size order. Click **Size** to reverse the order. Hover over a shortened location to see the full path.
- Candidates include the npm download cache, npx installs, pnpm stores, project node_modules, and build outputs such as dist, build and .next next to a package.json. Review generated outputs before selecting them, especially if you keep release files there. Close tools using the selected folders before cleaning. Reinstall dependencies or rebuild projects when you need them again.
- A **Large file** row represents one file. Its size alone says nothing about whether you need it. Selected large files go to your desktop Trash. Restore them there if needed, or empty Trash yourself to release the space.
- Click **Review selection** and confirm to begin. Selected cleanup folders are permanently removed, including their current contents. On APT systems with cached packages, the optional system row runs `sudo apt-get clean` to clear the package download cache. Keep the launch terminal open for the password prompt.
- Read the completion report and choose **Run scan** for fresh results. Files that changed since scanning are skipped during individual file cleanup. Folder estimates use allocated disk blocks. Files shared through hard links, including pnpm packages, release their blocks only after the last link is removed.

## Privacy

Scanning and cleanup run locally. Paths are displayed in the window. The app writes no scan report or account configuration. Approved dependency installation uses the repositories configured in your system package manager.

## Uninstall

Close CacheCat, then double-click **Uninstall Disk Cleaner.desktop**, or run `sh uninstall.sh` from the project folder. Review the destination and filenames. Type **REMOVE** to confirm or press Enter to cancel. The uninstaller removes the distributed files, including this README and both shortcuts, then removes the folder if empty. Other files, Git history and shared system packages stay in place.
