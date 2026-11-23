import pytest
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf

def test_mascot_animator_initialization():
    from mascot import MascotAnimator, MascotState
    animator = MascotAnimator(Path(__file__).parent.parent / "cachecat.xpm")
    assert animator.state == MascotState.IDLE
    pixbuf = animator.get_current_frame()
    assert pixbuf is not None
    assert pixbuf.get_width() == 64
    assert pixbuf.get_height() == 64

def test_mascot_animator_state_transition():
    from mascot import MascotAnimator, MascotState
    animator = MascotAnimator(Path(__file__).parent.parent / "cachecat.xpm")
    animator.set_state(MascotState.SCANNING)
    assert animator.state == MascotState.SCANNING
    frame1 = animator.get_current_frame()
    animator.tick()
    frame2 = animator.get_current_frame()
    assert frame1 is not None and frame2 is not None

def test_mascot_animator_all_states():
    from mascot import MascotAnimator, MascotState
    animator = MascotAnimator(Path(__file__).parent.parent / "cachecat.xpm")
    for state in (MascotState.IDLE, MascotState.SCANNING, MascotState.CLEANING, MascotState.SUCCESS):
        animator.set_state(state)
        assert animator.state == state
        for _ in range(10):
            animator.tick()
            assert animator.get_current_frame() is not None

def test_mascot_animator_meow():
    from mascot import MascotAnimator
    animator = MascotAnimator(Path(__file__).parent.parent / "cachecat.xpm")
    quote = animator.meow()
    assert isinstance(quote, str)
    assert len(quote) > 0
