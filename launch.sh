#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
# Use the distribution Python that owns the GTK bindings.
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
stop() {
    echo "$1"
    printf 'Press Enter to close. '
    read -r reply || :
    exit 1
}
ready() {
    python3 -B -c 'import sys, gi; assert sys.version_info >= (3, 9); gi.require_version("Gtk", "3.0"); from gi.repository import Gtk, Gio' 2>/dev/null
}
[ "$(id -u)" != 0 ] || stop "Start CacheCat as your regular desktop user."
if ! ready; then
    if command -v apt-get >/dev/null; then
        set -- apt-get install python3 python3-gi gir1.2-gtk-3.0
    elif command -v dnf >/dev/null; then
        set -- dnf install python3 python3-gobject gtk3
    elif command -v pacman >/dev/null; then
        set -- pacman -S --needed python python-gobject gtk3
    elif command -v zypper >/dev/null; then
        set -- zypper install python3 python3-gobject typelib-1_0-Gtk-3_0
    else
        stop "Install Python 3.9 or newer, PyGObject and GTK 3 with your software manager, then launch again."
    fi
    echo "CacheCat needs Python 3.9 or newer, PyGObject and GTK 3."
    echo "Your system package manager will resolve dependencies. Proposed command:"
    echo "  sudo $*"
    printf 'Install these requirements now? [y/N] '
    read -r reply || exit 0
    case $reply in y|Y|yes|Yes) ;; *) exit 0 ;; esac
    command -v sudo >/dev/null || stop "Ask your administrator to run the package command above."
    sudo -- "$@" || stop "Installation did not finish. Check the package manager message above."
    ready || stop "The system Python still cannot load GTK 3. Check the Python version and GTK bindings."
fi
python3 -B app.py || stop "CacheCat could not run. Check the message above and open it from a graphical desktop."
