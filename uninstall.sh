#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
folder=$(pwd -P)
set -- cachecat.xpm app.py launch.sh uninstall.sh 'Disk Cleaner.desktop' 'Uninstall Disk Cleaner.desktop' README.md
echo "Remove CacheCat from $folder?"
echo "Close the app first. Only the following files in this folder will be removed:"
printf '  %s\n' "$@"
desktop=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
for shortcut in "$desktop/Disk Cleaner.desktop" "${XDG_DATA_HOME:-$HOME/.local/share}/applications/DiskCleaner.desktop"; do
    if [ -f "$shortcut" ] && cmp -s -- 'Disk Cleaner.desktop' "$shortcut"; then
        set -- "$@" "$shortcut"
        echo "  $shortcut"
    fi
done
echo "Shared system packages and other files will be kept."
printf 'Type REMOVE to uninstall, or press Enter to cancel: '
read -r answer || exit 0
[ "$answer" = REMOVE ] || exit 0
rm -f -- "$@"
cd /
if rmdir -- "$folder" 2>/dev/null; then
    echo "CacheCat removed."
else
    echo "CacheCat files removed. The folder still contains other items or cannot be removed."
fi
printf 'Press Enter to close. '
read -r answer || :
