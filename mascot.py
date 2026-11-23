import random
from enum import Enum
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf

class MascotState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    CLEANING = "cleaning"
    SUCCESS = "success"

MEOW_QUOTES = [
    "Purr! I sniffed out some stale cache hairballs!",
    "Meow! Ready to pounce on bloated caches!",
    "Mrrrp? 'Select Safe' picks all risk-free caches in one click!",
    "Purrrr... a clean disk is as cozy as a warm sunbeam.",
    "Paw-some! Reclaiming gigabytes gives your system room to breathe!",
    "*nuzzles your cursor* Let's tidy up those folders!",
    "Meow meow! Build folders can grow huge if you don't watch 'em!",
    "Purr! Remember to check 'Usually safe' items first!",
]

class MascotAnimator:
    def __init__(self, xpm_path: Path, target_size: int = 64):
        self.target_size = target_size
        self.base_pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(xpm_path))
        self.state = MascotState.IDLE
        self.tick_count = 0
        self.current_frame_idx = 0
        
        # Build animation frames for each state
        self.frames = {
            MascotState.IDLE: self._build_idle_frames(),
            MascotState.SCANNING: self._build_scanning_frames(),
            MascotState.CLEANING: self._build_cleaning_frames(),
            MascotState.SUCCESS: self._build_success_frames(),
        }
        
    def _scale(self, pixbuf: GdkPixbuf.Pixbuf) -> GdkPixbuf.Pixbuf:
        return pixbuf.scale_simple(self.target_size, self.target_size, GdkPixbuf.InterpType.NEAREST)

    def _copy(self) -> GdkPixbuf.Pixbuf:
        return self.base_pixbuf.copy()

    def _build_idle_frames(self) -> list[GdkPixbuf.Pixbuf]:
        """Idle frames: regular face, gentle blink, soft ear twitch."""
        f0 = self._copy() # regular open eyes
        
        # Blink frame
        f_blink = self._copy()
        for x in (6, 15):
            for y in (9, 11):
                self.base_pixbuf.copy_area(x, 8, 3, 1, f_blink, x, y)
            self.base_pixbuf.copy_area(x, 9, 3, 1, f_blink, x, 10)
            
        # Left ear twitch
        f_ear_l = self._copy()
        # Shift tip of left ear slightly
        self.base_pixbuf.copy_area(4, 1, 2, 2, f_ear_l, 3, 2)
        
        # Right ear twitch
        f_ear_r = self._copy()
        self.base_pixbuf.copy_area(18, 1, 2, 2, f_ear_r, 19, 2)
        
        # Timeline: 16 ticks idle loop: mostly f0, with occasional blink and ear twitches
        sequence = [f0] * 10 + [f_blink, f_blink] + [f0] * 4 + [f_ear_l] * 2 + [f0] * 4 + [f_ear_r] * 2
        return [self._scale(f) for f in sequence]

    def _build_scanning_frames(self) -> list[GdkPixbuf.Pixbuf]:
        """Scanning frames: eyes darting left, center, right with whiskers active."""
        # Look left: move pupils in eye boxes (left eye box is x:6..8, y:9..11; right eye box is x:15..17, y:9..11)
        f_left = self._copy()
        # Move white pupil from col 7 to col 6
        for y in (9, 10):
            # erase old pupil: replace with dark #343047
            self.base_pixbuf.copy_area(6, 10, 1, 1, f_left, 7, y)
            # draw pupil at x=6
            self.base_pixbuf.copy_area(7, 10, 1, 1, f_left, 6, y)
        for y in (9, 10):
            self.base_pixbuf.copy_area(15, 10, 1, 1, f_left, 16, y)
            self.base_pixbuf.copy_area(16, 10, 1, 1, f_left, 15, y)

        # Look right: move pupil to col 8 and col 17
        f_right = self._copy()
        for y in (9, 10):
            self.base_pixbuf.copy_area(8, 10, 1, 1, f_right, 7, y)
            self.base_pixbuf.copy_area(7, 10, 1, 1, f_right, 8, y)
        for y in (9, 10):
            self.base_pixbuf.copy_area(17, 10, 1, 1, f_right, 16, y)
            self.base_pixbuf.copy_area(16, 10, 1, 1, f_right, 17, y)

        f_center = self._copy()

        # Alert wide-eyes hunting frame: enlarge eye pupils
        f_wide = self._copy()
        for y in (9, 10):
            self.base_pixbuf.copy_area(7, 10, 1, 1, f_wide, 6, y)
            self.base_pixbuf.copy_area(7, 10, 1, 1, f_wide, 8, y)
            self.base_pixbuf.copy_area(16, 10, 1, 1, f_wide, 15, y)
            self.base_pixbuf.copy_area(16, 10, 1, 1, f_wide, 17, y)

        sequence = [f_left] * 3 + [f_center] * 2 + [f_right] * 3 + [f_wide] * 2
        return [self._scale(f) for f in sequence]

    def _build_cleaning_frames(self) -> list[GdkPixbuf.Pixbuf]:
        """Cleaning frames: sweeping paw movements and dust sparkles."""
        f0 = self._copy()
        
        # Determined eyes
        f_sweep1 = self._copy()
        # Draw sweeping paw on left
        for x in (3, 4, 5):
            for y in (15, 16):
                self.base_pixbuf.copy_area(11, 12, 1, 1, f_sweep1, x, y)
        # Add dust sparkle on left (cream dot)
        self.base_pixbuf.copy_area(10, 13, 1, 1, f_sweep1, 2, 14)
        self.base_pixbuf.copy_area(10, 13, 1, 1, f_sweep1, 1, 15)

        f_sweep2 = self._copy()
        # Draw sweeping paw on right
        for x in (18, 19, 20):
            for y in (15, 16):
                self.base_pixbuf.copy_area(11, 12, 1, 1, f_sweep2, x, y)
        # Add dust sparkle on right
        self.base_pixbuf.copy_area(10, 13, 1, 1, f_sweep2, 21, 14)
        self.base_pixbuf.copy_area(10, 13, 1, 1, f_sweep2, 22, 15)

        sequence = [f_sweep1] * 3 + [f0] * 2 + [f_sweep2] * 3
        return [self._scale(f) for f in sequence]

    def _build_success_frames(self) -> list[GdkPixbuf.Pixbuf]:
        """Success celebration: happy smiling eyes with victory sparkles."""
        f_happy1 = self._copy()
        # Happy arched closed eyes (^^)
        for x in (6, 7, 8):
            self.base_pixbuf.copy_area(x, 8, 1, 1, f_happy1, x, 9)
            self.base_pixbuf.copy_area(15, 16, 17, 1, f_happy1, x + 9, 9)
        # Sparkles around head (yellow/cream dots)
        self.base_pixbuf.copy_area(7, 10, 1, 1, f_happy1, 2, 8)
        self.base_pixbuf.copy_area(7, 10, 1, 1, f_happy1, 21, 8)
        self.base_pixbuf.copy_area(7, 10, 1, 1, f_happy1, 11, 2)

        f_happy2 = self._copy()
        for x in (6, 7, 8):
            self.base_pixbuf.copy_area(x, 8, 1, 1, f_happy2, x, 9)
            self.base_pixbuf.copy_area(15, 16, 17, 1, f_happy2, x + 9, 9)
        # Sparkles shifted
        self.base_pixbuf.copy_area(7, 10, 1, 1, f_happy2, 1, 7)
        self.base_pixbuf.copy_area(7, 10, 1, 1, f_happy2, 22, 7)
        self.base_pixbuf.copy_area(7, 10, 1, 1, f_happy2, 12, 1)

        sequence = [f_happy1] * 4 + [f_happy2] * 4
        return [self._scale(f) for f in sequence]

    def set_state(self, state: MascotState):
        if self.state != state:
            self.state = state
            self.current_frame_idx = 0
            self.tick_count = 0

    def tick(self) -> GdkPixbuf.Pixbuf:
        self.tick_count += 1
        frame_list = self.frames[self.state]
        self.current_frame_idx = (self.current_frame_idx + 1) % len(frame_list)
        return frame_list[self.current_frame_idx]

    def get_current_frame(self) -> GdkPixbuf.Pixbuf:
        frame_list = self.frames[self.state]
        return frame_list[self.current_frame_idx]

    def meow(self) -> str:
        """Returns a cute meow quote for user interaction."""
        return random.choice(MEOW_QUOTES)
