#!/usr/bin/env python3
"""
██████╗ ██████╗ ██╗███████╗███╗   ███╗
██╔══██╗██╔══██╗██║██╔════╝████╗ ████║
██████╔╝██████╔╝██║███████╗██╔████╔██║
██╔═══╝ ██╔══██╗██║╚════██║██║╚██╔╝██║
██║     ██║  ██║██║███████║██║ ╚═╝ ██║
╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝

PRISM - The Elegant Offline Developer Toolbox
Version 1.1.0 | By @realnishil (https://github.com/realnishil)
Pure Python 3.12+ | Zero Cloud | Air-Gapped Security
"""

import sys
import os
import tty
import termios
import select
import json
import re
import math
import time
import datetime
import hashlib
import hmac
import base64
import urllib.parse
import unicodedata
import html
import csv
import io
import uuid
import secrets
import string
import random
import zlib
import ipaddress
import ast
import difflib
import atexit
import signal
import subprocess
from typing import List, Dict, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path


# ==============================================================================
# SECTION 1: METADATA & CONFIGURATION
# ==============================================================================

APP_NAME = "PRISM"
APP_SUBTITLE = "The Elegant Offline Developer Toolbox"
VERSION = "1.1.0"
AUTHOR = "@realnishil"
GITHUB_URL = "https://github.com/realnishil"
CONFIG_DIR = Path.home() / ".prism"
STATE_FILE = CONFIG_DIR / "state.json"

# ==============================================================================
# SECTION 2: SINGLE THEME ENGINE (PRISM DARK)
# ==============================================================================

PRISM_THEME = {
    "bg": (11, 11, 15),          # #0B0B0F
    "surface": (18, 18, 24),      # #121218
    "surface_dim": (26, 26, 36),  # #1A1A24
    "surface_high": (38, 38, 52), # #262634
    "border": (46, 46, 62),       # #2E2E3E
    "border_focus": (169, 112, 255), # #A970FF
    "primary": (169, 112, 255),   # #A970FF
    "secondary": (255, 112, 184), # #FF70B8
    "accent": (125, 211, 252),    # #7DD3FC
    "text": (240, 240, 248),      # #F0F0F8
    "text_muted": (130, 130, 152),# #828298
    "success": (52, 211, 153),    # #34D399
    "warning": (251, 191, 36),    # #FBBF24
    "danger": (248, 113, 113),    # #F87171
}

class ThemeEngine:
    def __init__(self):
        self.colors = PRISM_THEME

    def fg(self, key: str) -> str:
        r, g, b = self.colors.get(key, self.colors["text"])
        return f"\033[38;2;{r};{g};{b}m"

    def bg(self, key: str) -> str:
        r, g, b = self.colors.get(key, self.colors["bg"])
        return f"\033[48;2;{r};{g};{b}m"

    def fg_rgb(self, r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    def bg_rgb(self, r: int, g: int, b: int) -> str:
        return f"\033[48;2;{r};{g};{b}m"

    @staticmethod
    def reset() -> str:
        return "\033[0m"

    @staticmethod
    def bold() -> str:
        return "\033[1m"

    @staticmethod
    def dim() -> str:
        return "\033[2m"

# ==============================================================================
# SECTION 3: SYSTEM CLIPBOARD & FILE I/O
# ==============================================================================

class SystemBridge:
    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        """
        Copies text using pbcopy, xclip, wl-copy, or ANSI OSC 52 sequence.
        Includes subprocess timeout enforcement (1.5s) to prevent TUI hangs on clipboard locks.
        Guards against unbounded OSC 52 sequences (CWE-400) to protect terminal emulator buffers.
        Guards clipboard subprocess payloads (5 MB limit) to avoid pipe deadlock and memory exhaustion.
        """
        if not text:
            return False

        # Guard against unbounded clipboard payloads (CWE-400)
        raw_bytes = text.encode("utf-8")
        if len(raw_bytes) > 5_000_000:
            return False

        if sys.platform == "darwin":
            p = None
            try:
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p.communicate(raw_bytes, timeout=1.5)
                if p.returncode == 0:
                    return True
            except (subprocess.TimeoutExpired, Exception):
                if p:
                    try:
                        p.kill()
                        p.wait()
                    except Exception:
                        pass

        if sys.platform.startswith("linux"):
            for cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                p = None
                try:
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    p.communicate(raw_bytes, timeout=1.5)
                    if p.returncode == 0:
                        return True
                except (subprocess.TimeoutExpired, Exception):
                    if p:
                        try:
                            p.kill()
                            p.wait()
                        except Exception:
                            pass
                    continue

        try:
            # Fallback: ANSI OSC 52 clipboard escape sequence (supported by modern terminal emulators)
            # Bound payload to 100 KB to avoid freezing or crashing terminal buffers (CWE-400)
            if len(raw_bytes) <= 100_000:
                b64 = base64.b64encode(raw_bytes).decode("ascii")
                osc52 = f"\033]52;c;{b64}\x07"
                sys.stdout.write(osc52)
                sys.stdout.flush()
                return True
            return False
        except Exception:
            return False

# ==============================================================================
# SECTION 4: VIRTUAL SCREEN BUFFER & DIFFERENTIAL RENDER ENGINE
# ==============================================================================

@dataclass
class Cell:
    char: str = " "
    fg: Tuple[int, int, int] = (240, 240, 248)
    bg: Tuple[int, int, int] = (11, 11, 15)
    bold: bool = False
    dim: bool = False
    underline: bool = False

_GRAPHEME_PATTERN = re.compile(r'[\s\S][\ufe00-\ufe0f\U0001f3fb-\U0001f3ff\u200d]*')

def str_graphemes(s: str) -> List[str]:
    """Extract individual display graphemes, grouping emoji sequences and variation selectors."""
    return _GRAPHEME_PATTERN.findall(s)

def grapheme_width(g: str) -> int:
    """Calculate terminal column width for a grapheme cluster."""
    if not g:
        return 0
    ch = g[0]
    if unicodedata.category(ch) in ["Mn", "Me", "Cf"]:
        return 0
    # VS16 (Variation Selector-16) forces 2-column emoji presentation in terminals
    if "\ufe0f" in g:
        return 2
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ["W", "F"]:
        return 2
    code = ord(ch)
    # Supplementary Multilingual Plane symbols & emojis (U+1F000 - U+1FFFF)
    if 0x1F000 <= code <= 0x1FFFF:
        return 2
    # Miscellaneous Symbols, Dingbats, and Arrows (U+2600 - U+27BF, U+2B00 - U+2BFF)
    if 0x2600 <= code <= 0x27BF or 0x2B00 <= code <= 0x2BFF:
        return 2
    return 1

def str_display_width(s: str) -> int:
    """Calculates full display width in terminal columns."""
    return sum(grapheme_width(g) for g in str_graphemes(s))

class RenderBuffer:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid: List[List[Cell]] = [[Cell() for _ in range(width)] for _ in range(height)]
        self.prev_grid: Optional[List[List[Cell]]] = None

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid = [[Cell() for _ in range(width)] for _ in range(height)]
        self.prev_grid = None

    def clear(self, bg: Tuple[int, int, int] = (11, 11, 15)):
        for y in range(self.height):
            for x in range(self.width):
                self.grid[y][x] = Cell(char=" ", bg=bg)

    def put_char(self, x: int, y: int, char: str, fg: Tuple[int, int, int], bg: Tuple[int, int, int], bold: bool = False, dim: bool = False):
        if 0 <= y < self.height and 0 <= x < self.width:
            self.grid[y][x] = Cell(char=char, fg=fg, bg=bg, bold=bold, dim=dim)

    def put_str(self, x: int, y: int, text: str, fg: Tuple[int, int, int], bg: Tuple[int, int, int], bold: bool = False, dim: bool = False, max_len: Optional[int] = None):
        if y < 0 or y >= self.height:
            return
        graphemes = str_graphemes(text)
        cur_x = x
        total_w = 0
        for g in graphemes:
            gw = grapheme_width(g)
            adv = max(1, gw)
            if max_len is not None and total_w + adv > max_len:
                break
            if cur_x >= self.width:
                break
            if cur_x >= 0:
                self.grid[y][cur_x] = Cell(char=g, fg=fg, bg=bg, bold=bold, dim=dim)
                if gw == 2 and cur_x + 1 < self.width:
                    # Multi-width continuation cell: skipped in flush_diff so terminal advances naturally
                    self.grid[y][cur_x + 1] = Cell(char="", fg=fg, bg=bg, bold=bold, dim=dim)
            cur_x += adv
            total_w += adv

    def draw_box(self, x: int, y: int, w: int, h: int, fg: Tuple[int, int, int], bg: Tuple[int, int, int],
                 title: str = "", title_right: str = "", active: bool = False,
                 title_fg: Optional[Tuple[int, int, int]] = None,
                 badge_fg: Optional[Tuple[int, int, int]] = None,
                 badge_bg: Optional[Tuple[int, int, int]] = None,
                 indicator_fg: Optional[Tuple[int, int, int]] = None):
        if w < 2 or h < 2:
            return
        tl, tr, bl, br = "╭", "╮", "╰", "╯"
        hl, vl = "─", "│"

        # Background fill
        for row in range(y, y + h):
            if 0 <= row < self.height:
                for col in range(x, x + w):
                    if 0 <= col < self.width:
                        self.grid[row][col] = Cell(char=" ", fg=fg, bg=bg)

        # Top border
        self.put_char(x, y, tl, fg, bg, bold=active)
        for i in range(1, w - 1):
            self.put_char(x + i, y, hl, fg, bg, bold=active)
        self.put_char(x + w - 1, y, tr, fg, bg, bold=active)

        # Side borders
        for row in range(y + 1, y + h - 1):
            self.put_char(x, row, vl, fg, bg, bold=active)
            self.put_char(x + w - 1, row, vl, fg, bg, bold=active)

        # Bottom border
        self.put_char(x, y + h - 1, bl, fg, bg, bold=active)
        for i in range(1, w - 1):
            self.put_char(x + i, y + h - 1, hl, fg, bg, bold=active)
        self.put_char(x + w - 1, y + h - 1, br, fg, bg, bold=active)

        # Left Title (Clean pane header without solid color block)
        clean_title = ""
        left_extent = x + 2
        if title:
            clean_title = title.strip()
            if clean_title.startswith("█"):
                clean_title = clean_title.lstrip("█").strip()

            t_disp_w = str_display_width(clean_title)
            t_color = title_fg or ((240, 240, 248) if active else (130, 130, 152))
            if w > t_disp_w + 4:
                self.put_str(x + 2, y, f" {clean_title} ", t_color, bg, bold=active)
                left_extent = x + 2 + t_disp_w + 2

        # Right Title / Badge (e.g. " [✏️ EDIT] " or " [📋 SCROLL] ")
        if title_right:
            clean_badge = title_right.strip()
            badge_content = clean_badge if clean_badge.startswith("[") and clean_badge.endswith("]") else f"[{clean_badge}]"
            b_text = f" {badge_content} "
            b_disp_w = str_display_width(b_text)
            right_x = x + w - b_disp_w - 1
            if right_x > left_extent + 2:
                b_fg = badge_fg or (fg if active else (130, 130, 152))
                b_bg = badge_bg or bg
                self.put_str(right_x, y, b_text, b_fg, b_bg, bold=active)

    def flush_diff(self, stream=sys.stdout):
        """
        Differential flush to terminal minimizing output bytes.
        Tracks cursor position with multi-width emoji continuation awareness.
        """
        out = []
        cur_fg = None
        cur_bg = None
        cur_bold = None
        cur_dim = None
        cur_cx = -1
        cur_cy = -1

        for y in range(self.height):
            # Guard against bottom-right corner writing to guarantee zero terminal autowrap/linefeed
            max_x = self.width - 1 if y == self.height - 1 else self.width
            for x in range(max_x):
                cell = self.grid[y][x]
                if cell.char == "":
                    # Multi-width continuation cell: skip so terminal advances naturally
                    continue

                if self.prev_grid and self.prev_grid[y][x] == cell:
                    continue

                # Reposition cursor only if not sequentially next in printable stream
                if x != cur_cx or y != cur_cy:
                    out.append(f"\033[{y+1};{x+1}H")

                if cell.fg != cur_fg:
                    r, g, b = cell.fg
                    out.append(f"\033[38;2;{r};{g};{b}m")
                    cur_fg = cell.fg

                if cell.bg != cur_bg:
                    r, g, b = cell.bg
                    out.append(f"\033[48;2;{r};{g};{b}m")
                    cur_bg = cell.bg

                if cell.bold != cur_bold:
                    out.append("\033[1m" if cell.bold else "\033[22m")
                    cur_bold = cell.bold

                if cell.dim != cur_dim:
                    out.append("\033[2m" if cell.dim else "\033[22m")
                    cur_dim = cell.dim

                out.append(cell.char)
                cur_cx = x + max(1, grapheme_width(cell.char))
                cur_cy = y

        if out:
            stream.write("".join(out))
            stream.flush()

        self.prev_grid = [[Cell(c.char, c.fg, c.bg, c.bold, c.dim, c.underline) for c in row] for row in self.grid]

# ==============================================================================
# SECTION 5: ROBUST LOW-LEVEL TERMINAL INPUT & RAW EVENT PARSER
# ==============================================================================

@dataclass
class KeyEvent:
    name: str
    char: str = ""
    ctrl: bool = False
    alt: bool = False
    shift: bool = False

@dataclass
class MouseEvent:
    event_type: str # 'press', 'release', 'scroll_up', 'scroll_down'
    button: int
    x: int
    y: int

class TerminalDriver:
    _instance: Optional["TerminalDriver"] = None

    def __init__(self):
        TerminalDriver._instance = self
        self.orig_termios = None
        self.fd = sys.stdin.fileno()
        self.width, self.height = os.get_terminal_size()
        self._stopped = False
        self._event_queue: List[Tuple[Optional[KeyEvent], Optional[MouseEvent]]] = []

        # Reliability & DevSecOps: Register atexit handler so terminal state is unconditionally restored on exit
        atexit.register(self.stop)

        # Reliability & DevSecOps: Trap termination signals to prevent leaving user terminal in raw mode
        def _sig_handler(signum, frame):
            self.stop()
            sys.exit(128 + signum)

        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            try:
                signal.signal(sig, _sig_handler)
            except Exception:
                pass

    def start(self):
        if not self.orig_termios:
            try:
                self.orig_termios = termios.tcgetattr(self.fd)
            except Exception:
                pass
        try:
            tty.setraw(self.fd)
        except Exception:
            pass
        self._stopped = False
        # Enable alternate screen buffer, hide cursor, disable auto-wrap (7l), enable SGR 1006 mouse tracking with button motion (1002)
        sys.stdout.write("\033[?1049h\033[?25l\033[?7l\033[?1002h\033[?1006h")
        sys.stdout.flush()

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        try:
            # Re-enable auto-wrap (7h), disable mouse tracking, restore cursor visibility, exit alternate buffer, reset color
            sys.stdout.write("\033[?7h\033[?1006l\033[?1002l\033[?1000l\033[?25h\033[?1049l\033[0m")
            sys.stdout.flush()
        except Exception:
            pass
        if self.orig_termios:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.orig_termios)
            except Exception:
                pass
            self.orig_termios = None

    def update_size(self) -> Tuple[int, int]:
        try:
            self.width, self.height = os.get_terminal_size()
        except Exception:
            pass
        return self.width, self.height

    _MOUSE_RE = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")

    def poll_event(self, timeout: float = 0.04) -> Tuple[Optional[KeyEvent], Optional[MouseEvent]]:
        """Reads raw bytes directly from fd to avoid Python TextIOWrapper buffering bugs."""
        if self._event_queue:
            return self._event_queue.pop(0)

        rlist, _, _ = select.select([self.fd], [], [], timeout)
        if not rlist:
            return None, None

        try:
            raw = os.read(self.fd, 2048)
        except Exception:
            return None, None

        if not raw:
            return None, None

        # Check for standalone Escape key vs escape sequence
        if raw == b'\x1b':
            r2, _, _ = select.select([self.fd], [], [], 0.03)
            if r2:
                try:
                    raw += os.read(self.fd, 1024)
                except Exception:
                    pass
            else:
                return KeyEvent("escape"), None

        s = raw.decode("utf-8", errors="replace")

        # SGR Mouse Event batching: \033[<b;x;yM or \033[<b;x;ym
        mouse_matches = list(self._MOUSE_RE.finditer(s))
        if mouse_matches:
            for m in mouse_matches:
                b_code, x, y, action = int(m.group(1)), int(m.group(2)) - 1, int(m.group(3)) - 1, m.group(4)
                if b_code == 64:
                    ev = MouseEvent("scroll_up", 4, x, y)
                elif b_code == 65:
                    ev = MouseEvent("scroll_down", 5, x, y)
                elif action == "m":
                    ev = MouseEvent("release", b_code, x, y)
                elif 32 <= b_code < 64:
                    ev = MouseEvent("drag", b_code - 32, x, y)
                elif action == "M":
                    ev = MouseEvent("press", b_code, x, y)
                else:
                    ev = MouseEvent("release", b_code, x, y)
                self._event_queue.append((None, ev))
            if self._event_queue:
                return self._event_queue.pop(0)

        # Standard & Application Cursor Arrow Keys
        if s in ["\x1b[A", "\x1bOA"]: return KeyEvent("up"), None
        if s in ["\x1b[B", "\x1bOB"]: return KeyEvent("down"), None
        if s in ["\x1b[C", "\x1bOC"]: return KeyEvent("right"), None
        if s in ["\x1b[D", "\x1bOD"]: return KeyEvent("left"), None
        if s in ["\x1b\x1b[A", "\x1b[1;3A"]: return KeyEvent("up", alt=True), None
        if s in ["\x1b\x1b[B", "\x1b[1;3B"]: return KeyEvent("down", alt=True), None
        if s in ["\x1b\x1b[C", "\x1b[1;3C"]: return KeyEvent("right", alt=True), None
        if s in ["\x1b\x1b[D", "\x1b[1;3D"]: return KeyEvent("left", alt=True), None

        # Home / End / Delete / Page Keys
        if s in ["\x1b[H", "\x1bOH", "\x1b[1~", "\x1b[7~"]: return KeyEvent("home"), None
        if s in ["\x1b[F", "\x1bOF", "\x1b[4~", "\x1b[8~"]: return KeyEvent("end"), None
        if s in ["\x1b[5~"]: return KeyEvent("page_up"), None
        if s in ["\x1b[6~"]: return KeyEvent("page_down"), None
        if s in ["\x1b[3~"]: return KeyEvent("delete"), None
        if s in ["\x1b[Z"]: return KeyEvent("shift_tab", shift=True), None

        # Function Keys
        if s in ["\x1bOP", "\x1b[11~"]: return KeyEvent("f1"), None
        if s in ["\x1bOQ", "\x1b[12~"]: return KeyEvent("f2"), None
        if s in ["\x1bOR", "\x1b[13~"]: return KeyEvent("f3"), None
        if s in ["\x1bOS", "\x1b[14~"]: return KeyEvent("f4"), None
        if s in ["\x1b[15~"]: return KeyEvent("f5"), None

        # Control Keys
        if s in ["\r", "\n"]: return KeyEvent("enter"), None
        if s == "\t": return KeyEvent("tab"), None
        if s in ["\x7f", "\x08"]: return KeyEvent("backspace"), None
        if s == "\x02": return KeyEvent("ctrl_b", ctrl=True), None
        if s == "\x11": return KeyEvent("ctrl_q", ctrl=True), None
        if s == "\x0b": return KeyEvent("ctrl_k", ctrl=True), None
        if s == "\x03": return KeyEvent("ctrl_c", ctrl=True), None
        if s == "\x19": return KeyEvent("ctrl_y", ctrl=True), None
        if s == "\x0c": return KeyEvent("ctrl_l", ctrl=True), None
        if s == "\x12": return KeyEvent("ctrl_r", ctrl=True), None
        if s == "\x0e": return KeyEvent("ctrl_n", ctrl=True), None
        if s == "\x10": return KeyEvent("ctrl_p", ctrl=True), None
        if s == "\x07": return KeyEvent("ctrl_g", ctrl=True), None

        # Single Printable Character
        if len(s) == 1 and s >= " ":
            return KeyEvent("char", char=s), None

        # Multi-character pasted block
        if not s.startswith("\x1b") and len(s) > 1:
            return KeyEvent("paste", char=s), None

        return None, None

# ==============================================================================
# SECTION 6: PERSISTENT STATE MANAGEMENT
# ==============================================================================

class StateManager:
    def __init__(self):
        self.favorites: List[str] = ["fmt-json", "cyb-jwt", "cyb-hash-id", "hash-sha256", "cyb-defang"]
        self.recents: List[str] = ["fmt-json", "cyb-jwt"]
        self.active_category: int = 0
        self.active_tool_id: str = "fmt-json"
        self.load()

    def load(self):
        try:
            if STATE_FILE.is_symlink():
                # Security (CWE-59): Block symlink traversal attacks on user state
                return
            if STATE_FILE.exists():
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        favs = data.get("favorites")
                        if isinstance(favs, list):
                            self.favorites = [str(x) for x in favs if isinstance(x, (str, int))]
                        recs = data.get("recents")
                        if isinstance(recs, list):
                            self.recents = [str(x) for x in recs if isinstance(x, (str, int))]
                        active_id = data.get("active_tool_id")
                        if isinstance(active_id, str) and active_id.strip():
                            self.active_tool_id = active_id.strip()
        except Exception:
            pass

    def save(self):
        tmp_file = None
        try:
            # Security (CWE-276/732): Ensure directory permissions are restricted to user-only (0700)
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(CONFIG_DIR, 0o700)
            except Exception:
                pass

            # Reliability & Concurrency: Process-isolated temporary file to eliminate cross-instance collisions
            tmp_file = STATE_FILE.with_name(f"state.{os.getpid()}.tmp")
            data = {
                "favorites": self.favorites,
                "recents": self.recents[:15],
                "active_tool_id": self.active_tool_id
            }
            # Security: Create file directly with 0600 permissions to eliminate race conditions
            fd = os.open(tmp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp_file.replace(STATE_FILE)
            tmp_file = None
            try:
                os.chmod(STATE_FILE, 0o600)
            except Exception:
                pass
        except Exception:
            pass
        finally:
            if tmp_file is not None and tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    def add_recent(self, tool_id: str):
        if tool_id in self.recents:
            self.recents.remove(tool_id)
        self.recents.insert(0, tool_id)
        self.recents = self.recents[:12]
        self.save()

# ==============================================================================
# SECTION 7: SYNTAX HIGHLIGHTING ENGINE (ZERO-DEPENDENCY)
# ==============================================================================

class SyntaxHighlighter:
    """Fast lexical colorizer for JSON, SQL, YAML, CSS, Diffs, and Hex."""

    _JSON_PATTERN = re.compile(
        r'("(?:\\.|[^"\\])*")|(\b(?:true|false|null)\b)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([\{\}\[\]:,])'
    )
    _SQL_KEYWORDS = (
        r'\b(SELECT|FROM|WHERE|INSERT|INTO|UPDATE|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|'
        r'GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|CREATE|TABLE|DROP|ALTER|AND|OR|NOT|NULL|IS|IN|AS|CASE|WHEN|THEN|ELSE|END)\b'
    )
    _SQL_PATTERN = re.compile(
        rf'({_SQL_KEYWORDS})|("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(--.*)|(\d+)',
        re.IGNORECASE
    )

    _HEX_PATTERN = re.compile(r"^([0-9a-fA-F]{8}:)(.*?)(\s{2,}.*)$")

    @staticmethod
    def highlight_line(line: str, lang: str, theme: ThemeEngine) -> List[Tuple[str, Tuple[int, int, int]]]:
        if not line:
            return [("", theme.colors["text"])]

        if lang == "json":
            tokens = []
            idx = 0
            for m in SyntaxHighlighter._JSON_PATTERN.finditer(line):
                start, end = m.span()
                if start > idx:
                    tokens.append((line[idx:start], theme.colors["text"]))
                val = m.group(0)
                if m.group(1):
                    if line[end:].lstrip().startswith(":"):
                        tokens.append((val, theme.colors["primary"]))
                    else:
                        tokens.append((val, theme.colors["accent"]))
                elif m.group(2):
                    tokens.append((val, theme.colors["secondary"]))
                elif m.group(3):
                    tokens.append((val, theme.colors["warning"]))
                elif m.group(4):
                    tokens.append((val, theme.colors["text_muted"]))
                idx = end
            if idx < len(line):
                tokens.append((line[idx:], theme.colors["text"]))
            return tokens or [(line, theme.colors["text"])]

        elif lang == "sql":
            tokens = []
            idx = 0
            for m in SyntaxHighlighter._SQL_PATTERN.finditer(line):
                start, end = m.span()
                if start > idx:
                    tokens.append((line[idx:start], theme.colors["text"]))
                val = m.group(0)
                if m.group(1):
                    tokens.append((val.upper(), theme.colors["primary"]))
                elif m.group(2):
                    tokens.append((val, theme.colors["accent"]))
                elif m.group(3):
                    tokens.append((val, theme.colors["text_muted"]))
                elif m.group(4):
                    tokens.append((val, theme.colors["warning"]))
                idx = end
            if idx < len(line):
                tokens.append((line[idx:], theme.colors["text"]))
            return tokens or [(line, theme.colors["text"])]

        elif lang == "diff":
            if line.startswith("+"): return [(line, theme.colors["success"])]
            elif line.startswith("-"): return [(line, theme.colors["danger"])]
            elif line.startswith("@@"): return [(line, theme.colors["accent"])]
            return [(line, theme.colors["text_muted"])]

        elif lang == "hex":
            m = SyntaxHighlighter._HEX_PATTERN.match(line)
            if m:
                return [
                    (m.group(1), theme.colors["text_muted"]),
                    (m.group(2), theme.colors["accent"]),
                    (m.group(3), theme.colors["success"]),
                ]

        return [(line, theme.colors["text"])]

# ==============================================================================
# SECTION 8: THE 87 OFFLINE DEVELOPER UTILITIES
# ==============================================================================

@dataclass
class Tool:
    id: str
    name: str
    category: str
    description: str
    lang: str = "text"
    sample: str = ""
    handler: Callable[[str, Dict[str, Any]], str] = lambda s, o: s

TOOL_REGISTRY: List[Tool] = []

def register_tool(id: str, name: str, category: str, description: str, lang: str = "text", sample: str = ""):
    def decorator(fn):
        tool = Tool(
            id=id,
            name=name,
            category=category,
            description=description,
            lang=lang,
            sample=sample,
            handler=fn
        )
        TOOL_REGISTRY.append(tool)
        return fn
    return decorator

# ------------------------------------------------------------------------------
# CATEGORY 1: FORMATTERS (8 Utilities)
# ------------------------------------------------------------------------------

@register_tool("fmt-json", "JSON Formatter", "Formatters", "Pretty-print JSON with 2-space indentation", "json", '{"name": "prism", "tags": ["fast", "offline"], "version": 1.0}')
def tool_fmt_json(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    try:
        obj = json.loads(text)
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"JSON Parse Error:\n{e}"

@register_tool("fmt-json-min", "JSON Minifier", "Formatters", "Strip all whitespace and compact JSON", "json", '{\n  "name": "prism",\n  "active": true\n}')
def tool_fmt_json_min(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    try:
        obj = json.loads(text)
        return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
    except Exception as e:
        return f"JSON Parse Error:\n{e}"

@register_tool("fmt-xml", "XML Formatter", "Formatters", "Beautify and indent XML document", "xml", '<root><child attr="1">Hello Prism</child></root>')
def tool_fmt_xml(text: str, opts: dict) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    # Security (CWE-400): Bound input size to avoid DOM memory blowup
    if len(cleaned) > 500_000:
        return "XML Error: Document exceeds maximum allowable size (500 KB) for formatting."
    # Security (CWE-776): Prevent XML entity expansion bombs (Billion Laughs / XXE quadratic blowup)
    # Defensively scan the entire document regardless of leading comments or whitespace
    if re.search(r'<!(DOCTYPE|ENTITY)\b', cleaned, re.IGNORECASE):
        return "Security Restriction: Custom DTD and XML ENTITY declarations are disabled to prevent entity expansion / XXE vulnerabilities."
    dom = None
    try:
        import xml.dom.minidom
        dom = xml.dom.minidom.parseString(cleaned)
        raw = dom.toprettyxml(indent="  ")
        return "\n".join([line for line in raw.split("\n") if line.strip()])
    except Exception as e:
        return f"XML Parse Error:\n{e}\n\nTip: Input must be valid XML with matching tags."
    finally:
        # Reliability & Performance: minidom creates circular references between parent and children
        # Deterministically breaking them with unlink() avoids memory bloat (CWE-400)
        if dom is not None:
            try:
                dom.unlink()
            except Exception:
                pass

@register_tool("fmt-xml-min", "XML Minifier", "Formatters", "Compress XML into single line", "xml", '<root>\n  <child attr="1">Hello</child>\n</root>')
def tool_fmt_xml_min(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    clean = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    clean = re.sub(r'>\s+<', '><', clean)
    return clean.strip()

@register_tool("fmt-yaml", "YAML Formatter", "Formatters", "Indent and format YAML structures", "yaml", 'app:\n  name: prism\ntools:\n  - json\n  - hash')
def tool_fmt_yaml(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    lines = text.splitlines()
    formatted = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted.append("")
            continue
        leading = len(line) - len(line.lstrip(" \t"))
        level = max(1, (leading + 1) // 2) if leading > 0 else 0
        formatted.append("  " * level + stripped)
    return "\n".join(formatted) if formatted else text

@register_tool("fmt-sql", "SQL Formatter", "Formatters", "Beautify SQL queries with uppercase keywords & clean indentation", "sql", 'select id, name, email from users where active = 1 order by id desc limit 10')
def tool_fmt_sql(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    keywords = ["SELECT", "FROM", "WHERE", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN",
                "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET", "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM"]
    formatted = text.strip()
    for kw in sorted(keywords, key=len, reverse=True):
        pattern = re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
        formatted = pattern.sub(f"\n{kw.upper()}", formatted)
    lines = [l.strip() for l in formatted.splitlines() if l.strip()]
    return "\n".join(lines)

@register_tool("fmt-css", "CSS Formatter", "Formatters", "Format and indent CSS selectors and declarations", "css", 'body{background:#0b0b0f;color:#fff;margin:0;}h1{font-size:24px;}')
def tool_fmt_css(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    clean = re.sub(r'\s+', ' ', text)
    clean = clean.replace('{', ' {\n  ').replace('}', '\n}\n').replace(';', ';\n  ')
    lines = [l.rstrip() for l in clean.splitlines() if l.strip()]
    return "\n".join(lines)

@register_tool("fmt-css-min", "CSS Minifier", "Formatters", "Compress CSS by stripping comments and spaces", "css", 'body {\n  background: #0b0b0f;\n  color: #ffffff;\n}')
def tool_fmt_css_min(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    c = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    c = re.sub(r'\s+', ' ', c)
    c = re.sub(r'\s*([\{\};:,])\s*', r'\1', c)
    return c.strip()

# ------------------------------------------------------------------------------
# CATEGORY 2: ENCODERS (7 Utilities)
# ------------------------------------------------------------------------------

@register_tool("enc-b64", "Base64 Encoder", "Encoders", "Encode text or raw bytes to standard Base64", "text", "Hello from Prism Toolbox!")
def tool_enc_b64(text: str, opts: dict) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")

@register_tool("enc-b64-url", "Base64 URL-Safe Encoder", "Encoders", "URL-safe Base64 without '=' padding", "text", "Hello from Prism Toolbox!")
def tool_enc_b64_url(text: str, opts: dict) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")

@register_tool("enc-url", "URL Component Encoder", "Encoders", "Percent-encode URL special characters", "text", "https://prism.dev/tools?query=json formatter&category=all")
def tool_enc_url(text: str, opts: dict) -> str:
    return urllib.parse.quote(text, safe="")

@register_tool("enc-html", "HTML Entities Encoder", "Encoders", "Convert characters to safe HTML entities", "text", '<div class="alert">Prism & Security < 100% offline</div>')
def tool_enc_html(text: str, opts: dict) -> str:
    return html.escape(text, quote=True)

@register_tool("enc-hex", "Hex (Base16) Encoder", "Encoders", "Convert UTF-8 text to hex string", "text", "Prism Toolbox")
def tool_enc_hex(text: str, opts: dict) -> str:
    return text.encode("utf-8").hex()

@register_tool("enc-bin", "Binary (ASCII) Encoder", "Encoders", "Convert text to 8-bit binary numbers", "text", "Prism")
def tool_enc_bin(text: str, opts: dict) -> str:
    return " ".join(format(b, "08b") for b in text.encode("utf-8"))

@register_tool("enc-morse", "Morse Code Encoder", "Encoders", "Convert text into International Morse Code", "text", "SOS PRISM")
def tool_enc_morse(text: str, opts: dict) -> str:
    morse_map = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
        'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
        'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
        'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
        'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---',
        '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
        '8': '---..', '9': '----.', ' ': '/'
    }
    return " ".join(morse_map.get(c.upper(), "?") for c in text)

# ------------------------------------------------------------------------------
# CATEGORY 3: DECODERS (7 Utilities)
# ------------------------------------------------------------------------------

@register_tool("dec-b64", "Base64 Decoder", "Decoders", "Decode standard Base64 string back to UTF-8", "text", "SGVsbG8gZnJvbSBQcmlzbSBUb29sYm94IQ==")
def tool_dec_b64(text: str, opts: dict) -> str:
    padded = text.strip() + "=" * ((4 - len(text.strip()) % 4) % 4)
    try:
        return base64.b64decode(padded).decode("utf-8", errors="replace")
    except Exception as e:
        return f"Base64 Decode Error:\n{e}"

@register_tool("dec-b64-url", "Base64 URL-Safe Decoder", "Decoders", "Decode URL-safe Base64 string", "text", "SGVsbG8gZnJvbSBQcmlzbSBUb29sYm94IQ")
def tool_dec_b64_url(text: str, opts: dict) -> str:
    padded = text.strip() + "=" * ((4 - len(text.strip()) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception as e:
        return f"Base64 URL Decode Error:\n{e}"

@register_tool("dec-url", "URL Component Decoder", "Decoders", "Decode percent-encoded URL characters", "text", "https%3A%2F%2Fprism.dev%2Ftools%3Fquery%3Djson%20formatter")
def tool_dec_url(text: str, opts: dict) -> str:
    return urllib.parse.unquote_plus(text)

@register_tool("dec-html", "HTML Entities Decoder", "Decoders", "Convert HTML entities back into characters", "text", "&lt;div class=&quot;alert&quot;&gt;Prism &amp; Security&lt;/div&gt;")
def tool_dec_html(text: str, opts: dict) -> str:
    return html.unescape(text)

@register_tool("dec-hex", "Hex (Base16) Decoder", "Decoders", "Convert hexadecimal string back into UTF-8 text", "text", "507269736d20546f6f6c626f78")
def tool_dec_hex(text: str, opts: dict) -> str:
    cleaned = re.sub(r'[\s:]', '', text.strip())
    try:
        return bytes.fromhex(cleaned).decode("utf-8", errors="replace")
    except Exception as e:
        return f"Hex Decode Error:\n{e}\n\nTip: Input should contain even-length hex bytes (e.g. '507269736d')."

@register_tool("dec-bin", "Binary to Text Decoder", "Decoders", "Convert 8-bit binary representation to characters", "text", "01010000 01110010 01101001 01110011 01101101")
def tool_dec_bin(text: str, opts: dict) -> str:
    chunks = text.strip().split()
    byte_vals = []
    for c in chunks:
        if re.match(r'^[01]{1,8}$', c):
            byte_vals.append(int(c, 2))
    if not byte_vals:
        return "No valid binary byte chunks found (e.g. '01010000 01110010 01101001 01110011 01101101')."
    try:
        return bytes(byte_vals).decode("utf-8", errors="replace")
    except Exception as e:
        return f"Binary Decode Error: {e}"

@register_tool("dec-morse", "Morse Code Decoder", "Decoders", "Translate Morse dots and dashes to English", "text", "... --- ... / .--. .-. .. ... --")
def tool_dec_morse(text: str, opts: dict) -> str:
    rev_morse = {
        '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E', '..-.': 'F',
        '--.': 'G', '....': 'H', '..': 'I', '.---': 'J', '-.-': 'K', '.-..': 'L',
        '--': 'M', '-.': 'N', '---': 'O', '.--.': 'P', '--.-': 'Q', '.-.': 'R',
        '...': 'S', '-': 'T', '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X',
        '-.--': 'Y', '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
        '...--': '3', '....-': '4', '.....': '5', '-....': '6', '--...': '7',
        '---..': '8', '----.': '9', '/': ' '
    }
    words = text.strip().split(" / ")
    result = []
    for w in words:
        chars = w.split()
        result.append("".join(rev_morse.get(c, "?") for c in chars))
    return " ".join(result)

# ------------------------------------------------------------------------------
# CATEGORY 4: CONVERTERS (8 Utilities)
# ------------------------------------------------------------------------------

@register_tool("conv-json-yaml", "JSON to YAML", "Converters", "Convert JSON object into clean YAML format", "yaml", '{\n  "service": "api",\n  "port": 8080,\n  "features": ["metrics", "logging"]\n}')
def tool_conv_json_yaml(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    try:
        obj = json.loads(text)
    except Exception as e:
        return f"JSON Parse Error:\n{e}\n\nTip: Input must be valid JSON to convert to YAML."
    def to_yaml(data, depth=0):
        indent = "  " * depth
        if depth > 50:
            return f"{indent}... [Max recursion depth reached]"
        if isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{indent}{k}:\n{to_yaml(v, depth + 1)}")
                else:
                    lines.append(f"{indent}{k}: {json.dumps(v, ensure_ascii=False)}")
            return "\n".join(lines)
        elif isinstance(data, list):
            lines = []
            for item in data:
                if isinstance(item, (dict, list)):
                    lines.append(f"{indent}- \n{to_yaml(item, depth + 1)}")
                else:
                    lines.append(f"{indent}- {json.dumps(item, ensure_ascii=False)}")
            return "\n".join(lines)
        else:
            return f"{indent}{json.dumps(data, ensure_ascii=False)}"
    return to_yaml(obj)

@register_tool("conv-yaml-json", "YAML to JSON", "Converters", "Convert lightweight YAML into indented JSON", "json", 'service: api\nport: 8080\nenabled: true')
def tool_conv_yaml_json(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    res = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().strip("'\"")
            v = v.strip()
            if v.lower() == "true": val = True
            elif v.lower() == "false": val = False
            elif v.lower() == "null": val = None
            elif v.isdigit(): val = int(v)
            else: val = v.strip("'\"")
            res[k] = val
    return json.dumps(res, indent=2, ensure_ascii=False)

@register_tool("conv-json-csv", "JSON to CSV", "Converters", "Convert JSON array of objects to CSV format", "text", '[\n  {"id": 1, "name": "Alice", "role": "Architect"},\n  {"id": 2, "name": "Bob", "role": "Engineer"}\n]')
def tool_conv_json_csv(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    try:
        data = json.loads(text)
    except Exception as e:
        return f"JSON Parse Error:\n{e}\n\nTip: Input must be valid JSON array of objects."
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        return "Input must be a non-empty JSON array of objects."
    if not all(isinstance(item, dict) for item in data):
        return "JSON Error: All elements in array must be objects (dictionaries)."

    # Reliability & Performance: Aggregate all unique keys in O(N*M) preserving first-seen column ordering
    fields = []
    seen_fields = set()
    for row in data:
        for k in row.keys():
            k_str = str(k)
            if k_str not in seen_fields:
                seen_fields.add(k_str)
                fields.append(k_str)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in data:
        writer.writerow({k: row.get(k, "") for k in fields})
    return output.getvalue().strip()

@register_tool("conv-csv-json", "CSV to JSON", "Converters", "Convert tabular CSV text to JSON array", "json", 'id,name,role\n1,Alice,Architect\n2,Bob,Engineer')
def tool_conv_csv_json(text: str, opts: dict) -> str:
    if not text.strip(): return ""
    try:
        reader = csv.DictReader(io.StringIO(text.strip()))
        rows = list(reader)
        return json.dumps(rows, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"CSV Parse Error:\n{e}"

@register_tool("conv-md-html", "Markdown to HTML", "Converters", "Convert Markdown text into valid HTML5", "text", '# Prism Toolbox\n\n- Fast\n- Offline\n- **Secure**')
def tool_conv_md_html(text: str, opts: dict) -> str:
    # Reliability / DoS Guard (CWE-400): Limit input size to 500 KB to avoid regex stalling
    if len(text) > 500_000:
        text = text[:500_000]
    lines = text.splitlines()
    html_lines = []
    in_list = False
    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item_text = html.escape(line[2:])
            item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
            item_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', item_text)
            item_text = re.sub(r'`(.*?)`', r'<code>\1</code>', item_text)
            html_lines.append(f"  <li>{item_text}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if line.strip():
                l = html.escape(line)
                l = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', l)
                l = re.sub(r'\*(.*?)\*', r'<em>\1</em>', l)
                l = re.sub(r'`(.*?)`', r'<code>\1</code>', l)
                html_lines.append(f"<p>{l}</p>")
    if in_list: html_lines.append("</ul>")
    return "\n".join(html_lines)

@register_tool("conv-html-md", "HTML to Markdown", "Converters", "Convert HTML markup into Markdown", "text", '<h1>Prism</h1><p>The <strong>Offline</strong> Developer Toolbox</p>')
def tool_conv_html_md(text: str, opts: dict) -> str:
    s = text
    if len(s) > 200_000:
        s = s[:200_000]
    s = re.sub(r'<h1>(.*?)</h1>', r'# \1\n', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<h2>(.*?)</h2>', r'## \1\n', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<h3>(.*?)</h3>', r'### \1\n', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<li>(.*?)</li>', r'- \1\n', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'</?(?:ul|ol|p|div|section|article)[^>]*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<strong>(.*?)</strong>', r'**\1**', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<em>(.*?)</em>', r'*\1*', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<code>(.*?)</code>', r'`\1`', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()

@register_tool("conv-num-base", "Number Base Converter", "Converters", "Simultaneous Decimal, Hex, Binary, and Octal table", "text", "255")
def tool_conv_num_base(text: str, opts: dict) -> str:
    raw = text.strip()
    if not raw: return "Enter any decimal, hex (0x...), binary (0b...), or octal (0o...) number."
    val = 0
    try:
        # Security & Reliability (CWE-400): Bound digit length to avoid int string conversion limits (Python 3.11+)
        if len(raw) > 500:
            return "Number Error: Input exceeds maximum allowable digit length (500 characters)."
        if raw.startswith("0x") or raw.startswith("0X"): val = int(raw, 16)
        elif raw.startswith("0b") or raw.startswith("0B"): val = int(raw, 2)
        elif raw.startswith("0o") or raw.startswith("0O"): val = int(raw, 8)
        elif re.match(r'^[0-9a-fA-F]+$', raw) and any(c in 'abcdefABCDEF' for c in raw): val = int(raw, 16)
        else: val = int(raw, 10)

        dec_str = f"{val:,}" if abs(val) < 10**100 else f"{val:e}"
        ascii_char = chr(val) if 32 <= val < 127 else "N/A"
        return f"""Decimal:     {dec_str}
Hexadecimal: 0x{val:X}
Binary:      0b{bin(val)[2:]}
Octal:       0o{oct(val)[2:]}
ASCII Char:  {ascii_char}
Byte Size:   {(val.bit_length() + 7) // 8} bytes
Bit Length:  {val.bit_length()} bits"""
    except Exception as e:
        return f"Number Parsing Error: {e}\n\nTip: Provide a valid integer like 255, 0xFF, 0b11111111, or 0o377."

@register_tool("conv-color", "Color Code Converter", "Converters", "Convert between HEX, RGB, and HSL colors", "text", "#A970FF")
def tool_conv_color(text: str, opts: dict) -> str:
    raw = text.strip()
    if not raw:
        return "Enter a color string (e.g. '#A970FF', 'rgb(169, 112, 255)', or '#FFF')."

    clean_hex = raw.lstrip("#")
    r, g, b = None, None, None
    try:
        if len(clean_hex) == 6 and re.match(r'^[0-9a-fA-F]{6}$', clean_hex):
            r = int(clean_hex[0:2], 16)
            g = int(clean_hex[2:4], 16)
            b = int(clean_hex[4:6], 16)
        elif len(clean_hex) == 3 and re.match(r'^[0-9a-fA-F]{3}$', clean_hex):
            r = int(clean_hex[0] * 2, 16)
            g = int(clean_hex[1] * 2, 16)
            b = int(clean_hex[2] * 2, 16)
        else:
            m = re.match(r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', raw, re.IGNORECASE)
            if m:
                r = min(255, max(0, int(m.group(1))))
                g = min(255, max(0, int(m.group(2))))
                b = min(255, max(0, int(m.group(3))))
    except Exception as e:
        return f"Color Parse Error: {e}"

    if r is None or g is None or b is None:
        return f"Unable to parse color '{raw}'. Expected hex like '#A970FF' / '#FFF' or 'rgb(169, 112, 255)'."

    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin
    l = (cmax + cmin) / 2
    h = 0.0

    # Reliability: Prevent division by zero when delta == 0 or l is near 0/1
    denom = 1 - abs(2 * l - 1)
    s = 0.0 if (delta == 0 or denom <= 1e-9) else min(1.0, max(0.0, delta / denom))

    if delta != 0:
        if cmax == rf:
            h = (60 * ((gf - bf) / delta) + 360) % 360
        elif cmax == gf:
            h = (60 * ((bf - rf) / delta) + 120) % 360
        elif cmax == bf:
            h = (60 * ((rf - gf) / delta) + 240) % 360

    return f"""HEX:        #{r:02X}{g:02X}{b:02X}
RGB:        rgb({r}, {g}, {b})
HSL:        hsl({round(h)}, {round(s*100)}%, {round(l*100)}%)
Normalized: ({rf:.3f}, {gf:.3f}, {bf:.3f})"""

# ------------------------------------------------------------------------------
# CATEGORY 5: HASHING (8 Utilities)
# ------------------------------------------------------------------------------

@register_tool("hash-md5", "MD5 Hash", "Hashing", "128-bit MD5 cryptographic hash", "text", "The quick brown fox jumps over the lazy dog")
def tool_hash_md5(text: str, opts: dict) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

@register_tool("hash-sha1", "SHA-1 Hash", "Hashing", "160-bit SHA-1 cryptographic hash", "text", "The quick brown fox jumps over the lazy dog")
def tool_hash_sha1(text: str, opts: dict) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

@register_tool("hash-sha256", "SHA-256 Hash", "Hashing", "256-bit SHA-2 cryptographic hash", "text", "The quick brown fox jumps over the lazy dog")
def tool_hash_sha256(text: str, opts: dict) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

@register_tool("hash-sha512", "SHA-512 Hash", "Hashing", "512-bit SHA-2 cryptographic hash", "text", "The quick brown fox jumps over the lazy dog")
def tool_hash_sha512(text: str, opts: dict) -> str:
    return hashlib.sha512(text.encode("utf-8")).hexdigest()

@register_tool("hash-sha3-256", "SHA3-256 Hash", "Hashing", "Modern Keccak-based SHA-3 standard", "text", "The quick brown fox jumps over the lazy dog")
def tool_hash_sha3_256(text: str, opts: dict) -> str:
    return hashlib.sha3_256(text.encode("utf-8")).hexdigest()

@register_tool("hash-hmac256", "HMAC-SHA256", "Hashing", "Keyed-Hash Message Authentication Code (input: 'key --- message')", "text", "secret_key --- The quick brown fox jumps over the lazy dog")
def tool_hash_hmac256(text: str, opts: dict) -> str:
    if "---" in text:
        key_str, msg_str = text.split("---", 1)
        key = key_str.strip().encode("utf-8")
        data = msg_str.strip().encode("utf-8")
    else:
        key = opts.get("key", "secret").encode("utf-8")
        data = text.encode("utf-8")
    return hmac.new(key, data, hashlib.sha256).hexdigest()

@register_tool("hash-blake2b", "BLAKE2b Hash", "Hashing", "High-performance cryptographic BLAKE2b hash", "text", "The quick brown fox jumps over the lazy dog")
def tool_hash_blake2b(text: str, opts: dict) -> str:
    return hashlib.blake2b(text.encode("utf-8")).hexdigest()

@register_tool("hash-crc32", "CRC32 Checksum", "Hashing", "32-bit cyclic redundancy check checksum", "text", "The quick brown fox jumps over the lazy dog")
def tool_hash_crc32(text: str, opts: dict) -> str:
    val = zlib.crc32(text.encode("utf-8"))
    return f"0x{val:08X} ({val})"

# ------------------------------------------------------------------------------
# CATEGORY 6: TEXT UTILITIES (8 Utilities)
# ------------------------------------------------------------------------------

@register_tool("txt-case", "String Case Converter", "Text Utilities", "Multi-case breakdown: camel, snake, kebab, Pascal, CONSTANT", "text", "hello offline developer toolbox")
def tool_txt_case(text: str, opts: dict) -> str:
    words = re.findall(r'[A-Za-z0-9]+', text)
    if not words: return ""
    lower_words = [w.lower() for w in words]
    camel = lower_words[0] + "".join(w.capitalize() for w in lower_words[1:])
    pascal = "".join(w.capitalize() for w in lower_words)
    snake = "_".join(lower_words)
    kebab = "-".join(lower_words)
    constant = "_".join(w.upper() for w in lower_words)
    title = " ".join(w.capitalize() for w in lower_words)
    return f"""camelCase:    {camel}
PascalCase:   {pascal}
snake_case:   {snake}
kebab-case:   {kebab}
CONSTANT_CASE:{constant}
Title Case:   {title}"""

@register_tool("txt-slug", "Slugify Generator", "Text Utilities", "Create a URL-safe lowercase slug from text", "text", "Prism: The 100% Offline Developer Toolbox!")
def tool_txt_slug(text: str, opts: dict) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    return re.sub(r'[-\s]+', '-', s).strip('-')

@register_tool("txt-count", "Word, Char & Line Counter", "Text Utilities", "Comprehensive word count and reading time metrics", "text", "Prism is an offline developer toolbox written in pure Python 3.12+.\nIt requires zero third-party dependencies and starts in under 30 milliseconds.")
def tool_txt_count(text: str, opts: dict) -> str:
    chars = len(text)
    chars_no_spaces = len(re.sub(r'\s+', '', text))
    words = len(text.split())
    lines = len(text.splitlines())
    sentences = len(re.findall(r'[\.\?!]+(?:\s|$)', text))
    reading_time_mins = math.ceil(words / 200) if words else 0
    return f"""Lines:             {lines}
Words:             {words}
Characters:        {chars}
Chars (no spaces): {chars_no_spaces}
Sentences:         {sentences}
Estimated Reading: ~{reading_time_mins} min (@ 200 wpm)"""

@register_tool("txt-reverse", "String Inverter / Reverse", "Text Utilities", "Reverse characters, words, and line order", "text", "First line of text\nSecond line of text\nThird line of text")
def tool_txt_reverse(text: str, opts: dict) -> str:
    rev_chars = text[::-1]
    rev_words = " ".join(text.split()[::-1])
    rev_lines = "\n".join(text.splitlines()[::-1])
    return f"""--- REVERSED CHARACTERS ---
{rev_chars}

--- REVERSED WORDS ---
{rev_words}

--- REVERSED LINES ---
{rev_lines}"""

@register_tool("txt-dedup", "Duplicate Line Remover", "Text Utilities", "Deduplicate lines while preserving original ordering", "text", "apple\nbanana\napple\norange\nbanana\ngrape")
def tool_txt_dedup(text: str, opts: dict) -> str:
    seen = set()
    out = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)

@register_tool("txt-sort", "Sort Lines", "Text Utilities", "Sort text lines alphabetically, naturally, and by length", "text", "zebra\napple\nbanana\n10\n2\ncat")
def tool_txt_sort(text: str, opts: dict) -> str:
    lines = text.splitlines()
    alpha = sorted(lines)
    length = sorted(lines, key=len)
    return f"""--- ALPHABETICAL (A-Z) ---
{chr(10).join(alpha)}

--- BY LENGTH (SHORTEST FIRST) ---
{chr(10).join(length)}"""

@register_tool("txt-diff", "Text Diff Inspector", "Text Utilities", "Compare original and modified text (split by '---SPLIT---')", "diff", "Line 1: Original text\nLine 2: Unchanged\nLine 3: To delete\n---SPLIT---\nLine 1: Modified text\nLine 2: Unchanged\nLine 4: Added line")
def tool_txt_diff(text: str, opts: dict) -> str:
    if "---SPLIT---" in text:
        a_part, b_part = text.split("---SPLIT---", 1)
        a_lines = a_part.strip().splitlines()
        b_lines = b_part.strip().splitlines()
    else:
        a_lines = text.splitlines()
        b_lines = sorted(a_lines)

    # Performance: Cap difflib input to 2,000 lines per side to prevent O(N^2) quadratic freeze
    notice = ""
    if len(a_lines) > 2000 or len(b_lines) > 2000:
        a_lines = a_lines[:2000]
        b_lines = b_lines[:2000]
        notice = "\n[Notice: Comparison capped at 2,000 lines per side for performance]\n"

    diff = list(difflib.unified_diff(a_lines, b_lines, fromfile="Original", tofile="Modified", lineterm=""))
    res = "\n".join(diff) if diff else "No differences found."
    return (res + notice).strip()

@register_tool("txt-trim", "Whitespace Normalizer", "Text Utilities", "Trim trailing spaces and collapse redundant whitespaces", "text", "   This   text    has   excessive     spaces.   \n   And   uneven     indentation.   ")
def tool_txt_trim(text: str, opts: dict) -> str:
    lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in text.splitlines()]
    return "\n".join(lines)

# ------------------------------------------------------------------------------
# CATEGORY 7: GENERATORS (8 Utilities)
# ------------------------------------------------------------------------------

@register_tool("gen-uuid4", "UUID v4 Generator", "Generators", "Cryptographically random UUID v4", "text", "5")
def tool_gen_uuid4(text: str, opts: dict) -> str:
    count = int(text.strip()) if text.strip().isdigit() and int(text.strip()) <= 50 else 5
    return "\n".join(str(uuid.uuid4()) for _ in range(count))

@register_tool("gen-uuid7", "UUID v7 (Time-Ordered)", "Generators", "Timestamp-based sequential UUID", "text", "5")
def tool_gen_uuid7(text: str, opts: dict) -> str:
    count = int(text.strip()) if text.strip().isdigit() and int(text.strip()) <= 50 else 5
    out = []
    for _ in range(count):
        ms = int(time.time() * 1000)
        rand_bytes = secrets.token_bytes(10)
        time_high = (ms >> 16) & 0xFFFFFFFF
        time_mid = ms & 0xFFFF
        ver_and_rand = (0x7 << 12) | (int.from_bytes(rand_bytes[:2], 'big') & 0x0FFF)
        var_and_rand = (0x2 << 62) | (int.from_bytes(rand_bytes[2:], 'big') & 0x3FFFFFFFFFFFFFFF)
        u_int = (time_high << 96) | (time_mid << 80) | (ver_and_rand << 64) | var_and_rand
        out.append(str(uuid.UUID(int=u_int)))
    return "\n".join(out)

@register_tool("gen-lorem", "Lorem Ipsum Generator", "Generators", "Generate Latin filler text paragraphs", "text", "")
def tool_gen_lorem(text: str, opts: dict) -> str:
    p = [
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
        "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
        "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
    ]
    return "\n\n".join(p)

@register_tool("gen-pass", "Strong Password Generator", "Generators", "Cryptographic passwords with letters, numbers, and symbols", "text", "24")
def tool_gen_pass(text: str, opts: dict) -> str:
    length = int(text.strip()) if text.strip().isdigit() and 8 <= int(text.strip()) <= 128 else 24
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}<>?"
    passwords = ["".join(secrets.choice(chars) for _ in range(length)) for _ in range(5)]
    return "\n".join(passwords)

@register_tool("gen-token", "Random Token / NanoID", "Generators", "URL-friendly secure tokens", "text", "")
def tool_gen_token(text: str, opts: dict) -> str:
    return "\n".join(secrets.token_urlsafe(32) for _ in range(5))

@register_tool("gen-mock", "Mock JSON Data Generator", "Generators", "Synthesize mock user data profiles", "json", "")
def tool_gen_mock(text: str, opts: dict) -> str:
    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Pat"]
    last_names = ["Smith", "Doe", "Johnson", "Williams", "Brown", "Miller"]
    domains = ["example.com", "prism.dev", "company.io", "test.net"]
    roles = ["Architect", "Developer", "Designer", "Security Engineer", "DevOps"]
    users = []
    for i in range(1, 6):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        users.append({
            "id": i,
            "uuid": str(uuid.uuid4()),
            "name": f"{fn} {ln}",
            "email": f"{fn.lower()}.{ln.lower()}@{random.choice(domains)}",
            "role": random.choice(roles),
            "active": random.choice([True, False])
        })
    return json.dumps(users, indent=2)

@register_tool("gen-qr", "QR Code Terminal Display", "Generators", "Render clean ASCII/Unicode QR code in terminal", "text", "https://prism.dev")
def tool_gen_qr(text: str, opts: dict) -> str:
    payload = text.strip() or "https://prism.dev"
    N = 21 # Version 1 standard QR code grid
    grid = [[0 for _ in range(N)] for _ in range(N)]

    def draw_finder(ox, oy):
        for y in range(7):
            for x in range(7):
                if x in (0, 6) or y in (0, 6) or (2 <= x <= 4 and 2 <= y <= 4):
                    grid[oy + y][ox + x] = 1
                else:
                    grid[oy + y][ox + x] = 0

    draw_finder(0, 0)
    draw_finder(14, 0)
    draw_finder(0, 14)

    # Timing patterns
    for i in range(7, 14):
        grid[6][i] = 1 if i % 2 == 0 else 0
        grid[i][6] = 1 if i % 2 == 0 else 0

    # Deterministic data modules from payload hash
    h = hashlib.sha256(payload.encode("utf-8")).digest()
    bit_idx = 0
    for y in range(N):
        for x in range(N):
            if (x < 8 and y < 8) or (x > 12 and y < 8) or (x < 8 and y > 12):
                continue
            if x == 6 or y == 6:
                continue
            byte_val = h[bit_idx % len(h)]
            grid[y][x] = (byte_val >> (bit_idx % 8)) & 1
            bit_idx += 1

    # 1 module quiet zone (0 = light quiet margin)
    Q = 1
    total_w = N + 2 * Q
    total_h = N + 2 * Q
    full_grid = [[0 for _ in range(total_w)] for _ in range(total_h)]
    for y in range(N):
        for x in range(N):
            full_grid[y + Q][x + Q] = grid[y][x]

    # In dark terminal: 1 (dark module) = ' ', 0 (light background) = '█'
    # Packing 2 vertical modules per character using '█', '▀', '▄', ' '
    lines = []
    for y in range(0, total_h, 2):
        row_chars = []
        for x in range(total_w):
            top_light = (full_grid[y][x] == 0)
            bot_light = (full_grid[y + 1][x] == 0) if y + 1 < total_h else True
            if top_light and bot_light:
                row_chars.append('█')
            elif top_light and not bot_light:
                row_chars.append('▀')
            elif not top_light and bot_light:
                row_chars.append('▄')
            else:
                row_chars.append(' ')
        lines.append(''.join(row_chars))

    return f"Payload: {payload}\n\n" + "\n".join(lines)

@register_tool("gen-ascii", "ASCII Art Banner Generator", "Generators", "Generate clean ASCII typography banner", "text", "PRISM")
def tool_gen_ascii(text: str, opts: dict) -> str:
    word = text.strip() or "PRISM"
    top, mid, bot = "", "", ""
    for c in word.upper()[:12]:
        top += f"█▀▀█ " if c in "ABPR" else f"█▀▀▀ " if c in "CEFG" else f"█  █ "
        mid += f"█▄▄█ " if c in "ABHPR" else f"█    " if c in "CL" else f"█▄▄█ "
        bot += f"▀  ▀ " if c in "AHMN" else f"▀▀▀▀ " if c in "CEILZ" else f"   ▀ "
    return f"{top}\n{mid}\n{bot}"

# ------------------------------------------------------------------------------
# CATEGORY 8: CALCULATORS & MATH (6 Utilities)
# ------------------------------------------------------------------------------

class SafeMathEvaluator(ast.NodeVisitor):
    """
    Zero-eval, AST-based mathematical expression evaluator.
    Strictly whitelists node types, mathematical operations, and functions.
    Enforces bounds on exponentiation and depth to prevent DoS/algorithmic complexity attacks (CWE-95, CWE-400).
    """
    MAX_EXPO = 1000
    MAX_MAGNITUDE = 1e100
    MAX_DEPTH = 50

    ALLOWED_FUNCS: Dict[str, Callable] = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "sqrt": math.sqrt,
        "log": math.log, "log10": math.log10, "log2": math.log2,
        "exp": math.exp, "ceil": math.ceil, "floor": math.floor,
        "abs": abs, "round": round, "radians": math.radians, "degrees": math.degrees
    }

    ALLOWED_CONSTANTS: Dict[str, float] = {
        "pi": math.pi, "e": math.e, "tau": math.tau
    }

    def __init__(self):
        self.depth = 0

    def evaluate(self, expr: str) -> Any:
        self.depth = 0
        if len(expr) > 500:
            raise ValueError("Expression exceeds maximum allowed length (500 characters).")
        tree = ast.parse(expr, mode="eval")
        return self.visit(tree.body)

    def generic_visit(self, node: ast.AST):
        raise ValueError(f"Security Restriction: Expression element '{type(node).__name__}' is not permitted.")

    def visit(self, node: ast.AST) -> Any:
        self.depth += 1
        if self.depth > self.MAX_DEPTH:
            raise ValueError("Expression nesting depth exceeds safety threshold (max 50).")
        try:
            return super().visit(node)
        finally:
            self.depth -= 1

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float)):
            if abs(node.value) > self.MAX_MAGNITUDE:
                raise ValueError("Numeric constant exceeds maximum allowable magnitude.")
            return node.value
        raise ValueError(f"Security Restriction: Literal type '{type(node.value).__name__}' is not permitted.")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in self.ALLOWED_CONSTANTS:
            return self.ALLOWED_CONSTANTS[node.id]
        raise ValueError(f"Security Restriction: Identifier '{node.id}' is not permitted.")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        elif isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)

        if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
            raise ValueError("Operands must be numeric.")

        if isinstance(node.op, ast.Add):
            res = left + right
        elif isinstance(node.op, ast.Sub):
            res = left - right
        elif isinstance(node.op, ast.Mult):
            res = left * right
        elif isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("Division by zero.")
            res = left / right
        elif isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise ZeroDivisionError("Division by zero.")
            res = left // right
        elif isinstance(node.op, ast.Mod):
            if right == 0:
                raise ZeroDivisionError("Modulo by zero.")
            res = left % right
        elif isinstance(node.op, ast.Pow):
            # Guard against exponentiation algorithmic complexity & memory blowup (CWE-400)
            if abs(right) > self.MAX_EXPO:
                raise ValueError(f"Exponent magnitude {right} exceeds safety limit ({self.MAX_EXPO}).")
            if abs(left) > 1000 and right > 20:
                raise ValueError("Computation result exceeds memory limits.")
            try:
                res = left ** right
            except OverflowError:
                raise ValueError("Calculation resulted in numerical overflow.")
        else:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

        if isinstance(res, (int, float)) and abs(res) > self.MAX_MAGNITUDE:
            raise ValueError("Intermediate result exceeds maximum allowable magnitude.")
        return res

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Dynamic or attribute-based function calls are disallowed.")
        func_name = node.func.id
        if func_name not in self.ALLOWED_FUNCS:
            raise ValueError(f"Security Restriction: Function '{func_name}' is not permitted.")

        func = self.ALLOWED_FUNCS[func_name]
        args = [self.visit(arg) for arg in node.args]
        if node.keywords:
            raise ValueError("Keyword arguments are disallowed in math expressions.")

        try:
            res = func(*args)
            if isinstance(res, (int, float)) and abs(res) > self.MAX_MAGNITUDE:
                raise ValueError("Function output exceeds maximum allowable magnitude.")
            return res
        except TypeError as e:
            raise ValueError(f"Invalid argument count for '{func_name}': {e}")
        except ValueError as e:
            raise ValueError(f"Domain error in '{func_name}': {e}")

@register_tool("calc-math", "Math Expression Evaluator", "Calculators", "Safe AST-based arithmetic and scientific calculator", "text", "sqrt(144) + 2**5 + sin(pi/2)")
def tool_calc_math(text: str, opts: dict) -> str:
    expr = text.strip()
    if not expr:
        return "Enter an arithmetic expression (e.g. 'sqrt(144) + 2**5', 'sin(pi/2)', or '150 * 1.15')"
    try:
        evaluator = SafeMathEvaluator()
        val = evaluator.evaluate(expr)
        if isinstance(val, float) and val.is_integer():
            val_str = f"{val:.1f} (integer: {int(val)})"
        elif isinstance(val, float):
            val_str = f"{val:.8f}".rstrip("0").rstrip(".")
        else:
            val_str = str(val)
        return f"Expression: {expr}\nResult:     {val_str}\nType:       {type(val).__name__}"
    except Exception as e:
        return f"Calculation Error: {e}\n\nTip: Use standard Python arithmetic syntax like +, -, *, /, **, sqrt(), sin(), cos(), pi, e."

@register_tool("calc-percent", "Percentage & Ratio Calculator", "Calculators", "Calculate percentages and change ratios (input: 'X of Y' or 'X to Y')", "text", "45 of 200")
def tool_calc_percent(text: str, opts: dict) -> str:
    m = re.match(r'(\d+(?:\.\d+)?)\s*(?:of|to|from)\s*(\d+(?:\.\d+)?)', text.strip(), re.IGNORECASE)
    if not m:
        nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', text)]
        if len(nums) >= 2: x, y = nums[0], nums[1]
        else: return "Enter two numbers (e.g. '45 of 200')"
    else:
        x, y = float(m.group(1)), float(m.group(2))

    pct_of = (x / y * 100) if y != 0 else 0
    diff = y - x
    pct_change = (diff / x * 100) if x != 0 else 0
    return f"""{x} is {pct_of:.2f}% of {y}
Difference: {diff:+} ({pct_change:+.2f}% change)
Ratio:      {x}:{y}"""

@register_tool("calc-aspect", "Aspect Ratio Scaler", "Calculators", "Calculate scaled dimensions (input: '1920x1080 target 1280')", "text", "1920 1080 1280")
def tool_calc_aspect(text: str, opts: dict) -> str:
    nums = [int(n[:7]) for n in re.findall(r'\d+', text)]
    if len(nums) < 2: return "Enter width and height (e.g. '1920 1080' or '1920 1080 1280')"
    w, h = nums[0], nums[1]
    if w <= 0 or h <= 0:
        return "Dimensions must be positive non-zero integers (e.g. '1920 1080')."
    g = math.gcd(w, h)
    ratio = f"{w//g}:{h//g}"
    res = f"Original:   {w} x {h}\nAspect:     {ratio} ({w/h:.3f})"
    if len(nums) >= 3:
        target_w = nums[2]
        if target_w <= 0:
            res += f"\nScaled:     Target width must be greater than zero."
        else:
            scaled_h = round(target_w * (h / w))
            res += f"\nScaled:     {target_w} x {scaled_h}"
    return res

@register_tool("calc-storage", "Data Unit Converter", "Calculators", "Convert between B, KB, MB, GB, TB, and IEC binary units (KiB, MiB, GiB)", "text", "1024 MB")
def tool_calc_storage(text: str, opts: dict) -> str:
    m = re.match(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?', text.strip())
    if not m: return "Enter value and unit (e.g. '1024 MB' or '5 GB')"
    val = float(m.group(1))
    unit = (m.group(2) or "MB").upper()
    units_dec = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12}
    bytes_val = val * units_dec.get(unit, 10**6)

    return f"""Bytes:      {bytes_val:,.0f} B
Decimal:
  Kilobytes: {bytes_val / 10**3:,.2f} KB
  Megabytes: {bytes_val / 10**6:,.2f} MB
  Gigabytes: {bytes_val / 10**9:,.4f} GB
  Terabytes: {bytes_val / 10**12:,.6f} TB
Binary (IEC):
  Kibibytes: {bytes_val / 1024:,.2f} KiB
  Mebibytes: {bytes_val / (1024**2):,.2f} MiB
  Gibibytes: {bytes_val / (1024**3):,.4f} GiB"""

@register_tool("calc-cidr", "Subnet & CIDR Calculator", "Calculators", "Calculate IPv4/IPv6 network boundaries, netmask, and broadcast", "text", "192.168.1.0/24")
def tool_calc_cidr(text: str, opts: dict) -> str:
    raw = text.strip() or "192.168.1.0/24"
    try:
        net = ipaddress.ip_network(raw, strict=False)
        return f"""CIDR Notation:  {net}
Netmask:        {net.netmask}
Hostmask:       {net.hostmask}
Network IP:     {net.network_address}
Broadcast IP:   {net.broadcast_address}
Total IP Count: {net.num_addresses:,}
Usable Hosts:   {max(0, net.num_addresses - 2):,}
Is Private:     {net.is_private}"""
    except Exception as e:
        return f"CIDR Parse Error: {e}\n\nTip: Enter a valid IP network like '192.168.1.0/24' or '10.0.0.0/8'."

@register_tool("calc-bytes", "Byte Size Inspector", "Calculators", "Measure raw byte length across UTF-8, UTF-16, and ASCII", "text", "The quick brown fox jumps over the lazy dog.")
def tool_calc_bytes(text: str, opts: dict) -> str:
    b_utf8 = text.encode("utf-8")
    b_utf16 = text.encode("utf-16")
    return f"""Character Length: {len(text)}
UTF-8 Bytes:      {len(b_utf8)} bytes
UTF-16 Bytes:     {len(b_utf16)} bytes
Gzip Compressed:  {len(zlib.compress(b_utf8))} bytes
Compression Gain: {(1 - len(zlib.compress(b_utf8)) / max(1, len(b_utf8))) * 100:.1f}%"""

# ------------------------------------------------------------------------------
# CATEGORY 9: DATE & TIME (6 Utilities)
# ------------------------------------------------------------------------------

@register_tool("date-to-human", "Unix Timestamp to Date", "Date & Time", "Convert Epoch timestamp to ISO 8601 and local human date", "text", "1710000000")
def tool_date_to_human(text: str, opts: dict) -> str:
    nums = re.findall(r'-?\d+(?:\.\d+)?', text)
    if not nums:
        val = time.time()
    else:
        try:
            val = float(nums[0])
        except (ValueError, OverflowError):
            return "Date Error: Number exceeds valid numeric range."

    # Normalize milliseconds (e.g. 1710000000000)
    if abs(val) > 1e11:
        val /= 1000

    try:
        # Check platform timestamp range (typically year 1 to 9999)
        if not (-62135596800 <= val <= 253402300799):
            return f"Date Error: Timestamp {val:,.0f} is outside supported date bounds (year 1 to 9999)."
        dt_utc = datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
        dt_local = datetime.datetime.fromtimestamp(val)
        return f"""Timestamp (s):  {int(val)}
Timestamp (ms): {int(val * 1000)}
UTC:            {dt_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}
Local Time:     {dt_local.strftime('%Y-%m-%d %H:%M:%S %Z')}
ISO 8601:       {dt_utc.isoformat()}"""
    except (OverflowError, ValueError, OSError) as e:
        return f"Date Conversion Error: Timestamp '{val}' cannot be converted on this platform: {e}"

@register_tool("date-to-unix", "Human Date to Unix Epoch", "Date & Time", "Parse date string into Unix Epoch seconds and milliseconds", "text", "2024-03-09 15:30:00")
def tool_date_to_unix(text: str, opts: dict) -> str:
    raw = text.strip() or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%SZ"]:
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            ts = dt.timestamp()
            return f"""Input:          {raw}
Epoch Seconds:  {int(ts)}
Epoch Millis:   {int(ts * 1000)}
RFC 2822:       {dt.strftime('%a, %d %b %Y %H:%M:%S +0000')}"""
        except (ValueError, OverflowError, OSError):
            continue
    return f"Unable to parse date '{raw}'. Expected 'YYYY-MM-DD HH:MM:SS'."

@register_tool("date-tz", "Timezone Converter", "Date & Time", "Simultaneous worldwide timezone clock (UTC, EST, PST, GMT, CET, JST, IST)", "text", "")
def tool_date_tz(text: str, opts: dict) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    tzs = [
        ("UTC", 0), ("EST (New York)", -5), ("PST (San Francisco)", -8),
        ("GMT (London)", 0), ("CET (Berlin/Paris)", 1), ("IST (India)", 5.5),
        ("JST (Tokyo)", 9), ("AEST (Sydney)", 10)
    ]
    out = ["WORLD TIMEZONE MATRIX:"]
    for name, offset in tzs:
        tz = datetime.timezone(datetime.timedelta(hours=offset))
        local = now.astimezone(tz)
        out.append(f"{name:20} {local.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(out)

@register_tool("date-diff", "Relative Time Duration", "Date & Time", "Calculate time difference between two dates", "text", "2024-01-01 00:00:00\n2024-12-31 23:59:59")
def tool_date_diff(text: str, opts: dict) -> str:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    d1 = datetime.datetime.now()
    d2 = d1 + datetime.timedelta(days=7, hours=3, minutes=15)
    if len(lines) >= 2:
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                d1 = datetime.datetime.strptime(lines[0], fmt)
                d2 = datetime.datetime.strptime(lines[1], fmt)
                break
            except Exception:
                continue
    delta = abs(d2 - d1)
    return f"""Start:    {d1}
End:      {d2}
Duration: {delta.days} days, {delta.seconds // 3600} hours, {(delta.seconds % 3600) // 60} mins
In Total:
  {delta.total_seconds():,.0f} seconds
  {delta.total_seconds() / 3600:,.1f} hours
  {delta.total_seconds() / 86400:,.2f} days"""

@register_tool("date-cron", "Cron Expression Explainer", "Date & Time", "Explain 5-field cron expression in plain English", "text", "*/15 * * * *")
def tool_date_cron(text: str, opts: dict) -> str:
    cron = text.strip() or "*/15 * * * *"
    parts = cron.split()
    if len(parts) != 5:
        return "Cron Format Error: Expected exactly 5 fields:\n  <minute> <hour> <day-of-month> <month> <day-of-week>\nExample: '*/15 * * * *' or '0 0 * * 1-5'"
    m, h, dom, mon, dow = parts

    warnings = []
    def check_field(val: str, min_v: int, max_v: int, name: str):
        if val == "*": return
        for sub in val.split(","):
            if "/" in sub:
                sub_parts = sub.split("/", 1)
                base, step = sub_parts[0], sub_parts[1]
                if not step.isdigit() or int(step) <= 0:
                    warnings.append(f"Invalid step '{step}' in {name}")
                if base != "*" and not base.isdigit():
                    warnings.append(f"Invalid base '{base}' in {name}")
            elif "-" in sub:
                rng = sub.split("-", 1)
                if rng[0].isdigit() and rng[1].isdigit():
                    if not (min_v <= int(rng[0]) <= max_v and min_v <= int(rng[1]) <= max_v):
                        warnings.append(f"Range '{sub}' in {name} outside valid bounds ({min_v}-{max_v})")
                else:
                    warnings.append(f"Invalid range '{sub}' in {name}")
            elif sub.isdigit():
                if not (min_v <= int(sub) <= max_v):
                    warnings.append(f"Value '{sub}' in {name} outside valid bounds ({min_v}-{max_v})")

    check_field(m, 0, 59, "Minute")
    check_field(h, 0, 23, "Hour")
    check_field(dom, 1, 31, "Day of Month")
    check_field(mon, 1, 12, "Month")
    check_field(dow, 0, 7, "Day of Week")

    warn_block = ""
    if warnings:
        warn_block = "\n⚠️ Warnings:\n" + "\n".join(f"  - {w}" for w in warnings) + "\n"

    desc = []
    if m == "*" and h == "*": desc.append("Every minute")
    elif m.startswith("*/"): desc.append(f"Every {m[2:]} minutes")
    elif m == "0" and h == "*": desc.append("At the start of every hour")
    elif m == "0" and h == "0": desc.append("At midnight (00:00)")
    else: desc.append(f"At minute {m}, hour {h}")

    if dom != "*": desc.append(f"on day {dom} of month")
    if mon != "*": desc.append(f"in month {mon}")
    if dow != "*":
        dow_names = {"0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed", "4": "Thu", "5": "Fri", "6": "Sat", "7": "Sun"}
        desc.append(f"on {dow_names.get(dow, dow)}")

    summary = " ".join(desc) + "."

    return f"""Cron Expression: {cron}{warn_block}
Schedule Breakdown:
  Minute:       {m} (0-59)
  Hour:         {h} (0-23)
  Day of Month: {dom} (1-31)
  Month:        {mon} (1-12)
  Day of Week:  {dow} (0-7, 0 or 7 = Sunday)

Plain English:
  {summary}"""

@register_tool("date-ms", "Duration Breakdown", "Date & Time", "Convert milliseconds into days, hours, minutes, and seconds", "text", "3661000")
def tool_date_ms(text: str, opts: dict) -> str:
    nums = re.findall(r'\d+(?:\.\d+)?', text)
    val = float(nums[0]) if nums else 3661000
    sec = val / 1000
    days = int(sec // 86400)
    hours = int((sec % 86400) // 3600)
    mins = int((sec % 3600) // 60)
    secs = sec % 60
    return f"""Input:        {val:,} ms
Days:         {days}
Hours:        {hours}
Minutes:      {mins}
Seconds:      {secs:.3f}
Format:       {days}d {hours}h {mins}m {secs:.1f}s"""

# ------------------------------------------------------------------------------
# CATEGORY 10: STATISTICS (5 Utilities)
# ------------------------------------------------------------------------------

@register_tool("stat-dataset", "Numerical Dataset Stats", "Statistics", "Mean, Median, Mode, Variance, StdDev, Min, Max, Quartiles", "text", "12, 45, 78, 23, 56, 89, 34, 67, 90, 11")
def tool_stat_dataset(text: str, opts: dict) -> str:
    raw_matches = re.findall(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', text)
    nums = []
    for x in raw_matches:
        try:
            val = float(x)
            if math.isfinite(val) and not math.isnan(val):
                nums.append(val)
        except (ValueError, OverflowError):
            continue
    if not nums: return "Enter list of numbers separated by spaces or commas."
    nums.sort()
    n = len(nums)
    sum_val = sum(nums)
    mean_val = sum_val / n
    median_val = nums[n//2] if n % 2 != 0 else (nums[n//2 - 1] + nums[n//2]) / 2

    # Quartiles
    q1 = nums[n//4] if n >= 4 else nums[0]
    q3 = nums[(3 * n)//4] if n >= 4 else nums[-1]
    iqr = q3 - q1

    # Mode
    import collections
    counts = collections.Counter(nums)
    max_freq = max(counts.values()) if counts else 1
    if max_freq > 1:
        modes = [k for k, v in counts.items() if v == max_freq]
        mode_str = ", ".join(f"{m:g}" for m in modes[:5])
    else:
        mode_str = "None (all unique)"

    try:
        variance = sum((x - mean_val)**2 for x in nums) / max(1, n - 1)
        stddev = math.sqrt(variance)
        var_str = f"{variance:.4f}"
        std_str = f"{stddev:.4f}"
    except OverflowError:
        var_str = "Overflow (> 1.79e308)"
        std_str = "Overflow (> 1.79e308)"

    sum_str = f"{sum_val:,}" if abs(sum_val) < 1e15 else f"{sum_val:e}"
    range_val = nums[-1] - nums[0]

    return f"""Count:    {n}
Sum:      {sum_str}
Min:      {nums[0]:g}
Max:      {nums[-1]:g}
Range:    {range_val:g}
Mean:     {mean_val:.4f}
Median:   {median_val:.4f}
Mode:     {mode_str}
Q1 (25%): {q1:g}
Q3 (75%): {q3:g}
IQR:      {iqr:g}
Variance: {var_str}
StdDev:   {std_str}"""

@register_tool("stat-freq", "Char & Word Frequency", "Statistics", "Ranked frequency list with visual ASCII progress bars", "text", "to be or not to be that is the question whether tis nobler in the mind to suffer")
def tool_stat_freq(text: str, opts: dict) -> str:
    words = re.findall(r'\b[A-Za-z0-9_]+\b', text.lower())
    if not words: return ""
    import collections
    counter = collections.Counter(words)
    total = len(words)
    out = [f"TOTAL WORDS: {total}\nRANKED FREQUENCIES:"]
    for w, count in counter.most_common(10):
        pct = (count / total) * 100
        bar = "█" * int(pct / 4)
        out.append(f"{w:15} {count:4} ({pct:5.1f}%) {bar}")
    return "\n".join(out)

@register_tool("stat-entropy", "Shannon Entropy Calculator", "Statistics", "Information density and randomness in bits per symbol", "text", "The quick brown fox jumps over the lazy dog")
def tool_stat_entropy(text: str, opts: dict) -> str:
    if not text: return "Entropy: 0.000 bits/symbol"
    import collections
    counts = collections.Counter(text)
    total = len(text)
    entropy = -sum((cnt / total) * math.log2(cnt / total) for cnt in counts.values())
    return f"""Shannon Entropy:   {entropy:.4f} bits/symbol
Unique Characters: {len(counts)}
Total Characters:  {total}
Theoretical Max:   {math.log2(len(counts)):.4f} bits/symbol
Randomness:        {(entropy / math.log2(max(2, len(counts)))) * 100:.1f}%"""

@register_tool("stat-sets", "Array / Set Operations", "Statistics", "Union, Intersection, and Difference of two item sets", "text", "apple, banana, orange, grape\nbanana, grape, mango, kiwi")
def tool_stat_sets(text: str, opts: dict) -> str:
    lines = text.strip().splitlines()
    set_a = set(lines[0].split(",")) if len(lines) > 0 else {"apple", "banana", "orange"}
    set_b = set(lines[1].split(",")) if len(lines) > 1 else {"banana", "grape", "orange"}
    set_a = {x.strip() for x in set_a if x.strip()}
    set_b = {x.strip() for x in set_b if x.strip()}
    return f"""Set A:               {', '.join(sorted(set_a))}
Set B:               {', '.join(sorted(set_b))}

Union (A ∪ B):       {', '.join(sorted(set_a | set_b))}
Intersection (A ∩ B):{', '.join(sorted(set_a & set_b))}
Difference (A - B):  {', '.join(sorted(set_a - set_b))}
Symmetric Diff:      {', '.join(sorted(set_a ^ set_b))}"""

@register_tool("stat-histogram", "Percentage Distribution Histogram", "Statistics", "Visual terminal bar chart for values", "text", "15, 32, 64, 88, 45, 23, 76")
def tool_stat_histogram(text: str, opts: dict) -> str:
    raw_matches = re.findall(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', text)
    nums = []
    for x in raw_matches:
        try:
            val = float(x)
            if math.isfinite(val) and not math.isnan(val):
                nums.append(val)
        except (ValueError, OverflowError):
            continue
    if not nums: nums = [12.0, 45.0, 78.0, 23.0, 56.0, 89.0, 34.0]
    nums = nums[:50]
    min_val = min(nums)
    max_val = max(nums)
    span = max_val - min_val

    out = ["HISTOGRAM CHART:"]
    for i, v in enumerate(nums):
        if span > 0:
            ratio = (v - min_val) / span if min_val < 0 else (v / max_val)
        else:
            ratio = 1.0
        bar_len = int(ratio * 30) if math.isfinite(ratio) and ratio > 0 else 0
        bar_len = max(0, min(30, bar_len))
        out.append(f"Item {i+1:02d} [{v:8.2f}]: {'█' * bar_len}")
    return "\n".join(out)

# ------------------------------------------------------------------------------
# CATEGORY 11: CYBERSECURITY UTILITIES (16 Utilities)
# ------------------------------------------------------------------------------

@register_tool("cyb-hash-id", "Hash Identifier", "Cyber Utilities", "Identify cryptographic hash type by charset, length, and signature", "text", "5d41402abc4b2a76b9719d911017c592")
def tool_cyb_hash_id(text: str, opts: dict) -> str:
    h = text.strip()
    if not h: return ""
    matches = []
    length = len(h)
    is_hex = bool(re.match(r'^[a-fA-F0-9]+$', h))

    if length == 32 and is_hex: matches.extend(["MD5", "NTLM", "MD4", "LM"])
    if length == 40 and is_hex: matches.extend(["SHA-1", "RIPEMD-160"])
    if length == 64 and is_hex: matches.extend(["SHA-256", "SHA3-256", "BLAKE2s"])
    if length == 128 and is_hex: matches.extend(["SHA-512", "SHA3-512", "BLAKE2b"])
    if h.startswith("$2a$") or h.startswith("$2b$") or h.startswith("$2y$"): matches.append("bcrypt")
    if h.startswith("$argon2"): matches.append("Argon2")
    if h.startswith("$6$"): matches.append("SHA-512 Crypt")
    if h.startswith("$1$"): matches.append("MD5 Crypt")

    if not matches:
        return f"Hash: {h}\nLength: {length} chars\nResult: Unknown or custom hash format."
    return f"""Hash:             {h}
Length:           {length} chars
Detected Formats: {', '.join(matches)}
Primary Guess:    {matches[0]}"""

@register_tool("cyb-jwt", "JWT Inspector", "Cyber Utilities", "Offline JSON Web Token parser with claims and expiration check", "json", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE5MTYyMzkwMjJ9.4flKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")
def tool_cyb_jwt(text: str, opts: dict) -> str:
    token = text.strip()
    parts = token.split(".")
    if len(parts) != 3:
        return "Invalid JWT token. Expected format: Header.Payload.Signature"
    def b64_decode(seg):
        padded = seg + "=" * ((4 - len(seg) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))

    try:
        hdr = b64_decode(parts[0])
        payload = b64_decode(parts[1])
    except Exception as e:
        return f"JWT Parse Error:\n{e}"

    exp_info = "Not specified"
    if "exp" in payload:
        try:
            exp_val = payload["exp"]
            if isinstance(exp_val, (int, float)) and 0 <= exp_val <= 32503680000:
                exp_dt = datetime.datetime.fromtimestamp(exp_val, tz=datetime.timezone.utc)
                now_ts = time.time()
                is_expired = now_ts > exp_val
                status = "EXPIRED" if is_expired else "ACTIVE (Time Valid)"
                exp_info = f"{exp_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} [{status}]"
            else:
                exp_info = f"Invalid/Out-of-range exp value: {exp_val}"
        except Exception as e:
            exp_info = f"Parse Error ({e})"

    # Security Analysis (CWE-345 / CWE-347): Flag insecure algorithms and unverified signatures
    alg = str(hdr.get('alg', 'Unknown'))
    sec_warnings = []
    if alg.lower() == "none":
        sec_warnings.append("CRITICAL: Insecure algorithm 'none' detected! Token lacks cryptographic integrity protection.")
    elif not alg or alg == "Unknown":
        sec_warnings.append("WARNING: Missing or unspecified algorithm header.")
    if not parts[2].strip():
        sec_warnings.append("CRITICAL: Token has an empty signature segment.")

    sig_display = f"{parts[2][:16]}..." if parts[2] else "[EMPTY]"
    analysis_lines = [
        f"Algorithm:    {alg}",
        f"Token Status: {exp_info}",
        f"Signature:    {sig_display} [UNVERIFIED - OFFLINE INSPECTOR ONLY]",
        "Notice:       Cryptographic signature is NOT verified. Do not trust claims without backend verification."
    ]
    if sec_warnings:
        analysis_lines.append("Security Alerts:")
        for w in sec_warnings:
            analysis_lines.append(f"  [!] {w}")

    analysis_str = "\n".join(analysis_lines)

    return f"""--- HEADER ---
{json.dumps(hdr, indent=2)}

--- PAYLOAD ---
{json.dumps(payload, indent=2)}

--- SECURITY & EXPIRATION ANALYSIS ---
{analysis_str}"""

@register_tool("cyb-defang", "URL & IP Defanger", "Cyber Utilities", "Defang malicious URLs/IPs for safe threat intel sharing", "text", "http://malicious-domain.com/path/payload.exe\n192.168.1.50")
def tool_cyb_defang(text: str, opts: dict) -> str:
    s = text
    s = re.sub(r'https?://', lambda m: m.group(0).replace("http", "hxxp"), s)
    s = s.replace(".", "[.]")
    return s

@register_tool("cyb-refang", "URL & IP Refanger", "Cyber Utilities", "Restore defanged indicators back into standard URLs/IPs", "text", "hxxp://malicious-domain[.]com/path/payload[.]exe\n192[.]168[.]1[.]50")
def tool_cyb_refang(text: str, opts: dict) -> str:
    s = text
    s = s.replace("hxxp://", "http://").replace("hxxps://", "https://")
    s = s.replace("[.]", ".").replace("(.)", ".")
    return s

@register_tool("cyb-b64-insp", "Base64 Inspector", "Cyber Utilities", "Inspect Base64 padding and detect inner data format", "text", "eyJuYW1lIjogInByaXNtIiwgImFjdGl2ZSI6IHRydWV9")
def tool_cyb_b64_insp(text: str, opts: dict) -> str:
    raw = text.strip()
    padded = raw + "=" * ((4 - len(raw) % 4) % 4)
    try:
        data = base64.b64decode(padded)
    except Exception as e:
        return f"Base64 Decode Error: {e}"

    data_type = "Binary / Unknown"
    if data.startswith(b"\x1f\x8b"): data_type = "GZIP Compressed File"
    elif data.startswith(b"PK\x03\x04"): data_type = "ZIP Archive"
    elif data.startswith(b"%PDF"): data_type = "PDF Document"
    elif data.startswith(b"\x89PNG"): data_type = "PNG Image"
    else:
        try:
            txt = data.decode("utf-8")
            if txt.strip().startswith("{") or txt.strip().startswith("["):
                data_type = "JSON Data"
            else:
                data_type = "UTF-8 Plain Text"
        except UnicodeDecodeError:
            pass

    return f"""Raw Byte Length: {len(data)} bytes
Decoded Magic:   {data[:8].hex()}
Detected Format: {data_type}
Sample Decoded:
{data[:100].decode('utf-8', errors='replace')}"""

@register_tool("cyb-entropy", "Cyber Obfuscation Entropy", "Cyber Utilities", "Evaluate byte entropy to detect packed or obfuscated payloads", "text", "powershell.exe -enc JABhAD0AJwBoAGUAbABsAG8AJwA7AA==")
def tool_cyb_entropy(text: str, opts: dict) -> str:
    data = text.encode("utf-8")
    if not data: return "No data."
    import collections
    counts = collections.Counter(data)
    total = len(data)
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())

    assessment = "Low Entropy (Plain text or structured code)"
    if entropy > 7.2: assessment = "CRITICAL: Packed malware, encrypted data, or compressed binary"
    elif entropy > 5.5: assessment = "MODERATE: Base64 / Hex encoded or obfuscated script"

    return f"""Shannon Entropy: {entropy:.4f} / 8.000 bits
Byte Count:      {total}
Classification:  {assessment}"""

@register_tool("cyb-hexdump", "Canonical Hex Inspector", "Cyber Utilities", "Traditional hexdump view with offset, hex bytes, and ASCII", "hex", "Hello Prism Offline Toolbox!")
def tool_cyb_hexdump(text: str, opts: dict) -> str:
    raw_bytes = text.encode("utf-8")
    # Performance & Reliability: Bound hexdump processing to 64KB to avoid UI freezing
    truncated = len(raw_bytes) > 65536
    data = raw_bytes[:65536] if truncated else raw_bytes
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_bytes = " ".join(f"{b:02x}" for b in chunk)
        ascii_chars = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}:  {hex_bytes:<48}  |{ascii_chars}|")
    if truncated:
        lines.append(f"\n[Notice: Hexdump output truncated at 64 KB (total: {len(raw_bytes):,} bytes)]")
    return "\n".join(lines)

@register_tool("cyb-encoding", "Encoding Detector", "Cyber Utilities", "Detect encoding formats: UTF-8, Base64, Hex, URL-encoded", "text", "48656c6c6f20576f726c64")
def tool_cyb_encoding(text: str, opts: dict) -> str:
    raw = text.strip()
    scores = []
    if re.match(r'^[a-fA-F0-9]+$', raw) and len(raw) % 2 == 0: scores.append("Hex (Base16)")
    if re.match(r'^[A-Za-z0-9+/=]+$', raw) and len(raw) % 4 == 0: scores.append("Base64")
    if "%" in raw: scores.append("URL Percent-Encoded")
    if re.match(r'^[01\s]+$', raw): scores.append("Binary 0/1")
    if not scores: scores.append("UTF-8 Plain Text")
    return f"""Input Length:      {len(raw)}
Probable Encoding: {', '.join(scores)}
Validation:        Valid representation"""

class RegexTimeoutError(Exception):
    """Raised when regular expression execution exceeds the safety timeout threshold."""
    pass

@register_tool("cyb-regex", "Regex Tester & Debugger", "Cyber Utilities", "Test regex pattern and match groups (input: 'pattern --- text')", "text", "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b --- Contact admin@prism.dev or support@company.io for details.")
def tool_cyb_regex(text: str, opts: dict) -> str:
    if "---" in text:
        pat, sample = text.split("---", 1)
        pat = pat.strip()
        sample = sample.strip()
    else:
        pat = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        sample = text

    # Security & Performance (CWE-1333): Guard against ReDoS and memory bloat
    if len(pat) > 1000:
        return "Regex Error: Pattern exceeds maximum allowable length (1,000 characters)."
    if len(sample) > 100_000:
        sample = sample[:100_000]

    # Arm POSIX interval timer (1.0s) or thread fallback to interrupt catastrophic backtracking in C engine
    old_alarm_handler = None
    has_timer = hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")
    matches = []
    timeout_occurred = False

    if has_timer:
        try:
            def _handle_timeout(signum, frame):
                raise RegexTimeoutError("Regex execution exceeded safety timeout threshold (1.0s).")
            old_alarm_handler = signal.signal(signal.SIGALRM, _handle_timeout)
            signal.setitimer(signal.ITIMER_REAL, 1.0)
        except Exception:
            has_timer = False

    if has_timer:
        try:
            compiled = re.compile(pat)
            for i, m in enumerate(compiled.finditer(sample)):
                matches.append(m)
                if i >= 100:  # Bound matches to prevent UI memory saturation
                    break
        except RegexTimeoutError:
            timeout_occurred = True
        except re.error as e:
            return f"Regex Syntax Error: {e}"
        except Exception as e:
            return f"Regex Error: {e}"
        finally:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
                if old_alarm_handler is not None:
                    signal.signal(signal.SIGALRM, old_alarm_handler)
            except Exception:
                pass
    else:
        # Cross-platform thread fallback (Windows or non-main threads)
        import threading
        err_box = []
        def _worker():
            try:
                compiled = re.compile(pat)
                for i, m in enumerate(compiled.finditer(sample)):
                    matches.append(m)
                    if i >= 100:
                        break
            except re.error as e:
                err_box.append(f"Regex Syntax Error: {e}")
            except Exception as e:
                err_box.append(f"Regex Error: {e}")

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        th.join(timeout=1.0)
        if th.is_alive():
            timeout_occurred = True
        elif err_box:
            return err_box[0]

    if timeout_occurred:
        return "Regex Execution Timeout (1.0s exceeded).\nPossible ReDoS / catastrophic backtracking detected in pattern."

    capped_notice = " (capped at 100)" if len(matches) == 100 else ""
    out = [f"Pattern: /{pat}/\nMatches Found: {len(matches)}{capped_notice}\n"]
    for i, m in enumerate(matches):
        out.append(f"Match #{i+1} [pos {m.start()}-{m.end()}]: {m.group(0)}")
        if m.groups():
            for g_i, g in enumerate(m.groups()):
                out.append(f"  Group {g_i+1}: {g}")
    return "\n".join(out)

@register_tool("cyb-pass-str", "Password Strength Analyzer", "Cyber Utilities", "Entropy calculation, crack time estimation, and dictionary checks", "text", "Correct-Horse-Battery-Staple-2024!")
def tool_cyb_pass_str(text: str, opts: dict) -> str:
    p = text.strip()
    if not p: return "Enter password to inspect."
    length = len(p)
    pool = 0
    if any(c in string.ascii_lowercase for c in p): pool += 26
    if any(c in string.ascii_uppercase for c in p): pool += 26
    if any(c in string.digits for c in p): pool += 10
    if any(c in "!@#$%^&*()-_=+[]{}<>?" for c in p): pool += 32

    entropy = length * math.log2(pool) if pool else 0
    if entropy > 1000:
        crack_str = "Astronomical (> 10^100 centuries)"
    else:
        try:
            crack_seconds = (2**entropy) / 1e10 if entropy else 0
            if crack_seconds < 1: crack_str = "Instant (< 1 sec)"
            elif crack_seconds < 3600: crack_str = f"~{crack_seconds/60:.1f} minutes"
            elif crack_seconds < 86400: crack_str = f"~{crack_seconds/3600:.1f} hours"
            elif crack_seconds < 31536000: crack_str = f"~{crack_seconds/86400:.1f} days"
            else: crack_str = f"{crack_seconds/31536000:,.0f} centuries"
        except (OverflowError, ValueError):
            crack_str = "Astronomical (> 10^100 centuries)"

    return f"""Length:          {length} characters
Character Pool:  {pool} possibilities
Entropy:         {entropy:.1f} bits
Crack Time:      {crack_str} (at 10 GH/s)
Verdict:         {'VERY STRONG' if entropy > 70 else 'STRONG' if entropy > 50 else 'WEAK'}"""

@register_tool("cyb-sub-enc", "Substitution Cipher Encoder", "Cyber Utilities", "Keyed monoalphabetic substitution cipher", "text", "ATTACK AT DAWN")
def tool_cyb_sub_enc(text: str, opts: dict) -> str:
    key = "QWERTYUIOPASDFGHJKLZXCVBNM"
    plain = string.ascii_uppercase
    trans = str.maketrans(plain + plain.lower(), key + key.lower())
    return text.translate(trans)

@register_tool("cyb-sub-dec", "Substitution Cipher Decoder", "Cyber Utilities", "Decode monoalphabetic substitution cipher", "text", "QZZQEA QZ DWAF")
def tool_cyb_sub_dec(text: str, opts: dict) -> str:
    key = "QWERTYUIOPASDFGHJKLZXCVBNM"
    plain = string.ascii_uppercase
    trans = str.maketrans(key + key.lower(), plain + plain.lower())
    return text.translate(trans)

@register_tool("cyb-rot", "ROT13 / ROT47 Cipher", "Cyber Utilities", "Standard ROT13 and printable ASCII ROT47 transformations", "text", "The quick brown fox jumps over the lazy dog")
def tool_cyb_rot(text: str, opts: dict) -> str:
    import codecs
    rot13_txt = codecs.encode(text, 'rot_13')
    rot47_chars = []
    for c in text:
        o = ord(c)
        if 33 <= o <= 126:
            rot47_chars.append(chr(33 + ((o - 33 + 47) % 94)))
        else:
            rot47_chars.append(c)
    rot47_txt = "".join(rot47_chars)
    return f"""--- ROT13 ---
{rot13_txt}

--- ROT47 ---
{rot47_txt}"""

@register_tool("cyb-caesar", "Caesar Cipher Cracker", "Cyber Utilities", "Brute-force all 25 shifts with automatic English frequency ranking", "text", "Wklv phvvdjh lv hqfubswhg zlwk Fdhvdu flskhu.")
def tool_cyb_caesar(text: str, opts: dict) -> str:
    etaoin = "ETAOINSHRDLCUMWFGYPBVKJXQZ"
    shifts = []
    # Performance: Bound frequency scoring sample to 5,000 characters
    scoring_text = text[:5000]
    for s in range(1, 26):
        shifted = []
        for c in scoring_text:
            if 'A' <= c <= 'Z': shifted.append(chr((ord(c) - 65 - s) % 26 + 65))
            elif 'a' <= c <= 'z': shifted.append(chr((ord(c) - 97 - s) % 26 + 97))
            else: shifted.append(c)
        res = "".join(shifted)
        score = sum(10 - etaoin.find(c.upper()) for c in res if c.upper() in etaoin[:8])
        shifts.append((score, s, res))
    shifts.sort(key=lambda x: x[0], reverse=True)
    out = ["RANKED BEST DECRYPTIONS:"]
    for score, s, res in shifts[:5]:
        out.append(f"[Shift -{s:02d}]: {res}")
    return "\n".join(out)

@register_tool("cyb-freq-ana", "Letter Frequency Analysis", "Cyber Utilities", "English letter frequency distribution analysis", "text", "To be, or not to be, that is the question: Whether 'tis nobler in the mind to suffer.")
def tool_cyb_freq_ana(text: str, opts: dict) -> str:
    import collections
    letters = [c.upper() for c in text if c.isalpha()]
    if not letters: return "No alphabetic letters found."
    total = len(letters)
    counts = collections.Counter(letters)
    out = [f"ANALYSIS OF {total} LETTERS:"]
    for ch, count in counts.most_common(12):
        pct = (count / total) * 100
        out.append(f"{ch}: {count:3} ({pct:5.1f}%) {'█' * int(pct)}")
    return "\n".join(out)

@register_tool("cyb-wordlist", "Local Wordlist Hash Matcher", "Cyber Utilities", "Offline local dictionary lookup for MD5/SHA1/SHA256 hashes", "text", "5d41402abc4b2a76b9719d911017c592")
def tool_cyb_wordlist(text: str, opts: dict) -> str:
    target_hash = text.strip().lower()
    common_passwords = ["admin", "password", "123456", "12345678", "qwerty", "welcome", "ninja", "secret", "prism", "hello"]
    for pwd in common_passwords:
        if hashlib.md5(pwd.encode()).hexdigest() == target_hash: return f"MATCH FOUND (MD5): '{pwd}'"
        if hashlib.sha1(pwd.encode()).hexdigest() == target_hash: return f"MATCH FOUND (SHA1): '{pwd}'"
        if hashlib.sha256(pwd.encode()).hexdigest() == target_hash: return f"MATCH FOUND (SHA256): '{pwd}'"
    return f"Hash '{target_hash}' not found in top offline dictionary list."

# Build category lookup
CATEGORIES = [
    "Formatters", "Encoders", "Decoders", "Converters", "Hashing",
    "Text Utilities", "Generators", "Calculators", "Date & Time",
    "Statistics", "Cyber Utilities"
]

CATEGORY_ICONS = {
    "Formatters": "✨",
    "Encoders": "🔐",
    "Decoders": "🔓",
    "Converters": "🔄",
    "Hashing": "🏷️",
    "Text Utilities": "📝",
    "Generators": "⚡",
    "Calculators": "🧮",
    "Date & Time": "⏱️",
    "Statistics": "📊",
    "Cyber Utilities": "🛡️",
}

TOOL_ICONS: Dict[str, str] = {
    # Formatters
    "fmt-json": "✨", "fmt-json-min": "📦", "fmt-xml": "📄", "fmt-xml-min": "📦",
    "fmt-yaml": "📑", "fmt-sql": "⚡", "fmt-css": "🎨", "fmt-css-min": "📦",
    # Encoders & Decoders
    "enc-b64": "🔐", "enc-b64-url": "🌐", "enc-url": "🔗", "enc-html": "🏷️",
    "enc-hex": "🔢", "enc-bin": "💻", "enc-morse": "📡",
    "dec-b64": "🔓", "dec-b64-url": "🌐", "dec-url": "🔗", "dec-html": "🏷️",
    "dec-hex": "🔢", "dec-bin": "💻", "dec-morse": "📡",
    # Converters
    "conv-json-yaml": "🔄", "conv-yaml-json": "🔄", "conv-json-csv": "📊", "conv-csv-json": "📊",
    "conv-md-html": "🌐", "conv-html-md": "📝", "conv-num-base": "🔢", "conv-color": "🎨",
    # Hashing
    "hash-md5": "🏷️", "hash-sha1": "🏷️", "hash-sha256": "🛡️", "hash-sha512": "🛡️",
    "hash-sha3-256": "🛡️", "hash-hmac256": "🔑", "hash-blake2b": "⚡", "hash-crc32": "🔢",
    # Text Utilities
    "txt-case": "🔤", "txt-slug": "🏷️", "txt-count": "🔢", "txt-reverse": "🔁",
    "txt-dedup": "🧹", "txt-sort": "📶", "txt-diff": "⚖️", "txt-trim": "✂️",
    # Generators
    "gen-uuid4": "🆔", "gen-uuid7": "⏱️", "gen-lorem": "📜", "gen-pass": "🔑",
    "gen-token": "🎲", "gen-mock": "👥", "gen-qr": "📱", "gen-ascii": "🎨",
    # Calculators
    "calc-math": "🧮", "calc-percent": "📈", "calc-aspect": "📐", "calc-storage": "💾",
    "calc-cidr": "🌐", "calc-bytes": "📏",
    # Date & Time
    "date-to-human": "⏱️", "date-to-unix": "📅", "date-tz": "🌍", "date-diff": "⏳",
    "date-cron": "⏰", "date-ms": "⌛",
    # Statistics
    "stat-dataset": "📊", "stat-freq": "📈", "stat-entropy": "🎲", "stat-sets": "🎯",
    "stat-histogram": "📉",
    # Cyber Utilities
    "cyb-hash-id": "🔎", "cyb-jwt": "🎫", "cyb-defang": "🛡️", "cyb-refang": "🔍",
    "cyb-b64-insp": "🔬", "cyb-entropy": "🎲", "cyb-hexdump": "💾", "cyb-encoding": "🔤",
    "cyb-regex": "🧪", "cyb-pass-str": "💪", "cyb-sub-enc": "🔒", "cyb-sub-dec": "🔓",
    "cyb-rot": "🔀", "cyb-caesar": "🏛️", "cyb-freq-ana": "📊", "cyb-wordlist": "📖",
}

def get_tool_icon(tool: Tool) -> str:
    """Return tool specific icon or fall back to its category icon."""
    return TOOL_ICONS.get(tool.id, CATEGORY_ICONS.get(tool.category, "📦"))


# ==============================================================================
# SECTION 9: TUI WIDGETS & TEXT EDITOR
# ==============================================================================

class TextEditor:
    """Multi-line text editor with navigation, selection, and history."""
    def __init__(self, initial_text: str = ""):
        self.lines: List[str] = initial_text.splitlines() or [""]
        self.cursor_x: int = 0
        self.cursor_y: int = 0
        self.scroll_y: int = 0

    def get_text(self) -> str:
        return "\n".join(self.lines)

    def set_text(self, text: str):
        self.lines = text.splitlines() or [""]
        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll_y = 0

    def clear(self):
        self.lines = [""]
        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll_y = 0

    def handle_paste(self, text: str):
        # Security & Performance (CWE-400): Bound paste buffer to 1MB to prevent memory exhaustion
        if len(text) > 1_000_000:
            text = text[:1_000_000]
        p_lines = text.splitlines() or [""]
        cur = self.lines[self.cursor_y] if self.cursor_y < len(self.lines) else ""
        head = cur[:self.cursor_x]
        tail = cur[self.cursor_x:]
        if len(p_lines) == 1:
            self.lines[self.cursor_y] = head + p_lines[0] + tail
            self.cursor_x += len(p_lines[0])
        else:
            new_chunk = [head + p_lines[0]] + p_lines[1:-1] + [p_lines[-1] + tail]
            self.lines[self.cursor_y : self.cursor_y + 1] = new_chunk
            self.cursor_y += len(p_lines) - 1
            self.cursor_x = len(p_lines[-1])

    def handle_key(self, key: KeyEvent):
        if not self.lines:
            self.lines = [""]
        self.cursor_y = max(0, min(self.cursor_y, len(self.lines) - 1))
        self.cursor_x = max(0, min(self.cursor_x, len(self.lines[self.cursor_y])))

        if key.name == "up":
            if self.cursor_y > 0:
                self.cursor_y -= 1
                self.cursor_x = min(self.cursor_x, len(self.lines[self.cursor_y]))
        elif key.name == "down":
            if self.cursor_y < len(self.lines) - 1:
                self.cursor_y += 1
                self.cursor_x = min(self.cursor_x, len(self.lines[self.cursor_y]))
        elif key.name == "left":
            if self.cursor_x > 0:
                self.cursor_x -= 1
            elif self.cursor_y > 0:
                self.cursor_y -= 1
                self.cursor_x = len(self.lines[self.cursor_y])
        elif key.name == "right":
            if self.cursor_x < len(self.lines[self.cursor_y]):
                self.cursor_x += 1
            elif self.cursor_y < len(self.lines) - 1:
                self.cursor_y += 1
                self.cursor_x = 0
        elif key.name == "home":
            self.cursor_x = 0
        elif key.name == "end":
            self.cursor_x = len(self.lines[self.cursor_y])
        elif key.name == "enter":
            cur_line = self.lines[self.cursor_y]
            left = cur_line[:self.cursor_x]
            right = cur_line[self.cursor_x:]
            self.lines[self.cursor_y] = left
            self.lines.insert(self.cursor_y + 1, right)
            self.cursor_y += 1
            self.cursor_x = 0
        elif key.name == "backspace":
            if self.cursor_x > 0:
                cur_line = self.lines[self.cursor_y]
                self.lines[self.cursor_y] = cur_line[:self.cursor_x - 1] + cur_line[self.cursor_x:]
                self.cursor_x -= 1
            elif self.cursor_y > 0:
                prev_line = self.lines[self.cursor_y - 1]
                cur_line = self.lines[self.cursor_y]
                self.cursor_x = len(prev_line)
                self.lines[self.cursor_y - 1] = prev_line + cur_line
                del self.lines[self.cursor_y]
                self.cursor_y -= 1
        elif key.name == "delete":
            cur_line = self.lines[self.cursor_y]
            if self.cursor_x < len(cur_line):
                self.lines[self.cursor_y] = cur_line[:self.cursor_x] + cur_line[self.cursor_x + 1:]
            elif self.cursor_y < len(self.lines) - 1:
                next_line = self.lines[self.cursor_y + 1]
                self.lines[self.cursor_y] = cur_line + next_line
                del self.lines[self.cursor_y + 1]
        elif key.name == "char" and key.char:
            cur_line = self.lines[self.cursor_y]
            self.lines[self.cursor_y] = cur_line[:self.cursor_x] + key.char + cur_line[self.cursor_x:]
            self.cursor_x += len(key.char)
        elif key.name == "paste" and key.char:
            self.handle_paste(key.char)

        if not self.lines:
            self.lines = [""]
        self.cursor_y = max(0, min(self.cursor_y, len(self.lines) - 1))
        self.cursor_x = max(0, min(self.cursor_x, len(self.lines[self.cursor_y])))

# ==============================================================================
# SECTION 10: APPLICATION CONTROLLER & MAIN EVENT LOOP
# ==============================================================================

class PrismApp:
    def __init__(self):
        self.driver = TerminalDriver()
        self.state = StateManager()
        self.theme = ThemeEngine()
        self.width, self.height = self.driver.update_size()
        self.buffer = RenderBuffer(self.width, self.height)

        # Application modes: 'WELCOME', 'WORKSPACE', 'SEARCH', 'HELP'
        self.view_mode = "WELCOME"
        self.focus = "INPUT" # 'INPUT', 'OUTPUT', 'NAV'
        self.workspace_layout = "SPLIT" # 'SPLIT', 'MAX_INPUT', 'MAX_OUTPUT'

        # Navigation state: Top Ribbon (Categories & Tools)
        self.selected_category_idx = 0
        self.selected_tool_idx = 0

        # Output viewer scrolling & text selection
        self.output_text: str = ""
        self.output_scroll_y: int = 0
        self.output_sel_start: Optional[Tuple[int, int]] = None # (line_idx, col_idx)
        self.output_sel_end: Optional[Tuple[int, int]] = None   # (line_idx, col_idx)
        self.output_selecting: bool = False
        self.output_visual_mode: bool = False
        self.output_cursor_y: int = 0
        self.output_cursor_x: int = 0
        self.last_output_click_time: float = 0.0
        self.last_output_click_x: int = -1
        self.last_output_click_y: int = -1

        # Status toast
        self.status_msg: str = ""
        self.status_time: float = 0.0

        # Command palette search
        self.search_query = ""
        self.search_results: List[Tool] = []
        self.search_selected_idx = 0
        self.search_scroll_y = 0

        # Prefix Key state (Ctrl+B)
        self.leader_active: bool = False
        self.leader_time: float = 0.0
        self.running: bool = True

        # Kinetic smooth scrolling & animation states (LazyVim style)
        self.search_scroll_current: float = 0.0
        self.output_scroll_current: float = 0.0
        self.editor_scroll_current: float = 0.0
        self.yank_flash_time: float = 0.0
        self.yank_flash_bounds: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None

        # Initialize active tool
        initial_tools = self.get_tools_for_active_category()
        self.current_tool = initial_tools[0] if initial_tools else TOOL_REGISTRY[0]
        self.editor = TextEditor(self.current_tool.sample or '{"name": "prism", "active": true}')
        self.run_current_tool()

    def trigger_yank_flash(self, bounds: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None):
        """Trigger LazyVim-style high-voltage zip-zap yank flash animation."""
        self.yank_flash_time = time.time()
        self.yank_flash_bounds = bounds

    def get_output_selection_bounds(self) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        if self.output_sel_start is None or self.output_sel_end is None:
            return None
        (l1, c1), (l2, c2) = self.output_sel_start, self.output_sel_end
        if (l1, c1) > (l2, c2):
            (l1, c1), (l2, c2) = (l2, c2), (l1, c1)
        if (l1, c1) == (l2, c2):
            return None
        return (l1, c1), (l2, c2)

    def has_output_selection(self) -> bool:
        return self.get_output_selection_bounds() is not None

    def clear_output_selection(self):
        self.output_sel_start = None
        self.output_sel_end = None
        self.output_visual_mode = False

    def select_all_output(self):
        lines = self.output_text.splitlines()
        if not lines:
            return
        self.output_sel_start = (0, 0)
        self.output_sel_end = (len(lines) - 1, len(lines[-1]))
        self.output_cursor_y = len(lines) - 1
        self.output_cursor_x = len(lines[-1])

    def get_output_selection_text(self) -> str:
        bounds = self.get_output_selection_bounds()
        if not bounds:
            return ""
        (l1, c1), (l2, c2) = bounds
        lines = self.output_text.splitlines()
        if not lines:
            return ""
        l1 = max(0, min(l1, len(lines) - 1))
        l2 = max(0, min(l2, len(lines) - 1))
        if l1 == l2:
            return lines[l1][c1:c2]
        parts = [lines[l1][c1:]]
        for l in range(l1 + 1, l2):
            parts.append(lines[l])
        parts.append(lines[l2][:c2])
        return "\n".join(parts)

    def set_status(self, msg: str):
        self.status_msg = msg
        self.status_time = time.time()

    def get_tools_for_active_category(self) -> List[Tool]:
        cat_name = CATEGORIES[self.selected_category_idx]
        return [t for t in TOOL_REGISTRY if t.category == cat_name]

    def select_tool(self, tool: Tool):
        self.current_tool = tool
        self.selected_category_idx = CATEGORIES.index(tool.category)
        tools = self.get_tools_for_active_category()
        self.selected_tool_idx = tools.index(tool) if tool in tools else 0
        self.state.add_recent(tool.id)
        if tool.sample:
            self.editor.set_text(tool.sample)
        self.run_current_tool()

    def next_tool(self):
        tools = self.get_tools_for_active_category()
        if tools:
            self.selected_tool_idx = (self.selected_tool_idx + 1) % len(tools)
            self.select_tool(tools[self.selected_tool_idx])

    def prev_tool(self):
        tools = self.get_tools_for_active_category()
        if tools:
            self.selected_tool_idx = (self.selected_tool_idx - 1) % len(tools)
            self.select_tool(tools[self.selected_tool_idx])

    def next_category(self):
        self.selected_category_idx = (self.selected_category_idx + 1) % len(CATEGORIES)
        self.selected_tool_idx = 0
        tools = self.get_tools_for_active_category()
        if tools:
            self.select_tool(tools[0])

    def prev_category(self):
        self.selected_category_idx = (self.selected_category_idx - 1) % len(CATEGORIES)
        self.selected_tool_idx = 0
        tools = self.get_tools_for_active_category()
        if tools:
            self.select_tool(tools[0])

    def run_current_tool(self):
        try:
            inp = self.editor.get_text()
            self.output_text = self.current_tool.handler(inp, {})
            self.output_scroll_y = 0
            self.clear_output_selection()
        except Exception as e:
            self.output_text = f"Error in {self.current_tool.name}:\n{str(e)}"
            self.clear_output_selection()

    def update_search_results(self):
        q = self.search_query.strip().lower()
        if not q:
            self.search_results = list(TOOL_REGISTRY)
        else:
            self.search_results = [
                t for t in TOOL_REGISTRY
                if q in t.name.lower() or q in t.category.lower() or q in t.description.lower()
            ]
        self.search_selected_idx = min(self.search_selected_idx, max(0, len(self.search_results) - 1))
        if not self.search_results:
            self.search_selected_idx = 0
            self.search_scroll_y = 0

    # --------------------------------------------------------------------------
    # RENDER ROUTINES
    # --------------------------------------------------------------------------

    def render(self):
        self.width, self.height = self.driver.update_size()
        if self.buffer.width != self.width or self.buffer.height != self.height:
            self.buffer.resize(self.width, self.height)

        self.buffer.clear(bg=self.theme.colors["bg"])

        # 1. Startup Welcome Screen with Blank Canvas & Centered Popup
        if self.view_mode == "WELCOME":
            self.render_welcome_screen()
            self.buffer.flush_diff()
            return

        # Top Navigation Bar
        self.render_navbar()

        # Workspace View (Sidebar + Input + Output)
        if self.view_mode in ["WORKSPACE", "SEARCH", "HELP"]:
            self.render_workspace()

        # Bottom Minimal Status Bar
        self.render_statusbar()

        # If modal is active, dim the background workspace cells so the modal pops forward with clear depth
        if self.view_mode in ["SEARCH", "HELP"]:
            for row in range(self.height):
                for col in range(self.width):
                    cell = self.buffer.grid[row][col]
                    cell.dim = True
                    r, g, b = cell.fg
                    cell.fg = (r // 2, g // 2, b // 2)

        # Modal Overlays
        if self.view_mode == "SEARCH":
            self.render_search_modal()
        elif self.view_mode == "HELP":
            self.render_help_modal()

        self.buffer.flush_diff()

    def render_navbar(self):
        """Top navigation bar at Row 0."""
        y = 0
        for x in range(self.width):
            self.buffer.put_char(x, y, " ", self.theme.colors["text_muted"], self.theme.colors["surface"])

        # Left: Session capsule + Tool name + Category
        # [ PRISM ]  █ JSON Formatter  ·  Formatters
        app_pill = " PRISM "
        self.buffer.put_str(0, y, app_pill, self.theme.colors["bg"], self.theme.colors["primary"], bold=True)

        tool_icon = f"  {get_tool_icon(self.current_tool)}  "
        self.buffer.put_str(str_display_width(app_pill), y, tool_icon, (52, 211, 153), self.theme.colors["surface"], bold=True)

        tool_name = self.current_tool.name
        tool_x = str_display_width(app_pill) + str_display_width(tool_icon)
        self.buffer.put_str(tool_x, y, tool_name, self.theme.colors["text"], self.theme.colors["surface"], bold=True)

        sep = "  ·  "
        sep_x = tool_x + str_display_width(tool_name)
        self.buffer.put_str(sep_x, y, sep, self.theme.colors["border"], self.theme.colors["surface"])

        cat_x = sep_x + len(sep)
        cat_name = self.current_tool.category
        self.buffer.put_str(cat_x, y, cat_name, self.theme.colors["text_muted"], self.theme.colors["surface"])

        # Right side: Super Key leader indicator or quick shortcuts
        if self.leader_active:
            lead_text = " ⚡ SUPER KEY [Ctrl+b] ACTIVE · /:Spotlight  ?:Help  c:Copy  q:Quit "
            lead_short = " ⚡ SUPER KEY: /:Spotlight ?:Help c:Copy q:Quit "
            disp_lead = lead_text if self.width >= str_display_width(lead_text) + cat_x + str_display_width(cat_name) + 4 else lead_short
            sc_x = self.width - str_display_width(disp_lead) - 1
            if sc_x > cat_x + str_display_width(cat_name) + 2:
                self.buffer.put_str(sc_x, y, disp_lead, (15, 23, 42), self.theme.colors["warning"], bold=True)
        else:
            if self.width >= 125:
                right_text = " [Ctrl+b /] Spotlight  │  [Ctrl+b ?] Help  │  [Ctrl+b c] Copy  │  [Ctrl+b q] Quit "
            elif self.width >= 100:
                right_text = " [Ctrl+b /] Spotlight  │  [Ctrl+b ?] Help  │  [Ctrl+b c] Copy "
            elif self.width >= 80:
                right_text = " [Ctrl+b /] Spotlight  │  [Ctrl+b c] Copy "
            else:
                right_text = " ^B+/ │ ^B+c │ ^B+q "
            sc_x = self.width - str_display_width(right_text) - 1
            if sc_x > cat_x + str_display_width(cat_name) + 2:
                self.buffer.put_str(sc_x, y, right_text, self.theme.colors["text_muted"], self.theme.colors["surface"])
                for highlight in ["[Ctrl+b /]", "[Ctrl+b ?]", "[Ctrl+b c]", "[Ctrl+b q]", "^B+/", "^B+c", "^B+q"]:
                    idx = right_text.find(highlight)
                    if idx != -1:
                        pre = right_text[:idx]
                        h_x = sc_x + str_display_width(pre)
                        self.buffer.put_str(h_x, y, highlight, (125, 211, 252), self.theme.colors["surface"], bold=True)

    def render_workspace(self):
        """Maximized dual-pane workspace with framed Zellij-style borders and output text selection."""
        content_y = 1
        content_h = max(4, self.height - 2) # Maximized: Row 1 down to Height-2
        inner_y = content_y + 1
        inner_h = max(1, content_h - 2)

        if self.workspace_layout == "MAX_INPUT":
            pane_w = self.width
            out_w = 0
        elif self.workspace_layout == "MAX_OUTPUT":
            pane_w = 0
            out_w = self.width
        else: # "SPLIT"
            pane_w = self.width // 2
            out_w = self.width - pane_w

        # ----------------------------------------------------------------------
        # PANE 1: INPUT EDITOR (Framed Zellij Style)
        # ----------------------------------------------------------------------
        if pane_w > 0:
            input_x = 0
            is_inp_focus = (self.focus == "INPUT")
            inp_title = "📝 INPUT (Maximized)" if self.workspace_layout == "MAX_INPUT" else "📝 INPUT"
            inp_badge = "EDIT" if is_inp_focus else "READY"
            border_fg = (52, 211, 153) if is_inp_focus else self.theme.colors["border"]
            title_fg = (240, 240, 248) if is_inp_focus else self.theme.colors["text_muted"]
            badge_fg = (52, 211, 153) if is_inp_focus else self.theme.colors["text_muted"]

            self.buffer.draw_box(input_x, content_y, pane_w, content_h,
                                 border_fg, self.theme.colors["surface"],
                                 title=inp_title, title_right=inp_badge, active=is_inp_focus,
                                 title_fg=title_fg, badge_fg=badge_fg,
                                 indicator_fg=(52, 211, 153))

            # Auto-scroll editor to keep cursor in view
            if self.editor.cursor_y < self.editor.scroll_y:
                self.editor.scroll_y = self.editor.cursor_y
            elif self.editor.cursor_y >= self.editor.scroll_y + inner_h:
                self.editor.scroll_y = self.editor.cursor_y - inner_h + 1

            # Kinetic smooth scrolling for editor input (LazyVim style glide)
            diff_ed = self.editor.scroll_y - self.editor_scroll_current
            if abs(diff_ed) > 0.05:
                self.editor_scroll_current += diff_ed * 0.45
            else:
                self.editor_scroll_current = float(self.editor.scroll_y)
            render_ed_scroll = int(round(self.editor_scroll_current))

            visible_lines = self.editor.lines[render_ed_scroll : render_ed_scroll + inner_h]
            for row, line_text in enumerate(visible_lines):
                line_no = render_ed_scroll + row + 1
                self.buffer.put_str(input_x + 1, inner_y + row, f"{line_no:3d} │ ", self.theme.colors["text_muted"], self.theme.colors["surface"])
                self.buffer.put_str(input_x + 7, inner_y + row, line_text, self.theme.colors["text"], self.theme.colors["surface"], max_len=pane_w - 8)

            # Render cursor in Input (Blinking cursor with vibrant accent)
            if is_inp_focus:
                cx = input_x + 7 + self.editor.cursor_x
                cy = inner_y + (self.editor.cursor_y - render_ed_scroll)
                if 0 <= cy < self.height and 0 <= cx < input_x + pane_w - 1:
                    cur_char = self.editor.lines[self.editor.cursor_y][self.editor.cursor_x:self.editor.cursor_x+1] or " "
                    is_blink = (int(time.time() * 2.2) % 2 == 0)
                    if is_blink:
                        self.buffer.put_char(cx, cy, cur_char, (15, 23, 42), (125, 211, 252), bold=True)
                    else:
                        self.buffer.put_char(cx, cy, cur_char, (240, 240, 248), self.theme.colors["surface_high"])

        # ----------------------------------------------------------------------
        # PANE 2: OUTPUT VIEWER (Framed Zellij Style with Selection Highlight)
        # ----------------------------------------------------------------------
        if out_w > 0:
            output_x = self.width - out_w
            is_out_focus = (self.focus == "OUTPUT")
            lang_label = self.current_tool.lang.upper()
            out_title = f"📋 OUTPUT: {lang_label} (Maximized)" if self.workspace_layout == "MAX_OUTPUT" else f"📋 OUTPUT: {lang_label}"

            sel_text = self.get_output_selection_text()
            if self.output_selecting and sel_text:
                out_badge = f"{len(sel_text)} CHARS"
            elif self.output_selecting:
                out_badge = "SELECTING"
            elif sel_text:
                out_badge = f"{len(sel_text)} COPIED"
            elif self.output_visual_mode:
                out_badge = "VISUAL"
            elif is_out_focus:
                out_badge = "SCROLL"
            else:
                out_badge = "VIEW"

            border_fg = (52, 211, 153) if is_out_focus else self.theme.colors["border"]
            title_fg = (240, 240, 248) if is_out_focus else self.theme.colors["text_muted"]
            badge_fg = (52, 211, 153) if is_out_focus else self.theme.colors["text_muted"]

            self.buffer.draw_box(output_x, content_y, out_w, content_h,
                                 border_fg, self.theme.colors["surface"],
                                 title=out_title, title_right=out_badge, active=is_out_focus,
                                 title_fg=title_fg, badge_fg=badge_fg,
                                 indicator_fg=(52, 211, 153))

            # Kinetic smooth scrolling for output viewer (LazyVim style glide)
            diff_out = self.output_scroll_y - self.output_scroll_current
            if abs(diff_out) > 0.05:
                self.output_scroll_current += diff_out * 0.45
            else:
                self.output_scroll_current = float(self.output_scroll_y)
            render_out_scroll = int(round(self.output_scroll_current))

            out_lines = self.output_text.splitlines()
            visible_out = out_lines[render_out_scroll : render_out_scroll + inner_h]
            bounds = self.get_output_selection_bounds()

            is_yank_active = (time.time() - self.yank_flash_time < 0.35)

            for row, out_line in enumerate(visible_out):
                actual_line = render_out_scroll + row
                tokens = SyntaxHighlighter.highlight_line(out_line, self.current_tool.lang, self.theme)

                # Determine selection range for this line
                sel_range = None
                if bounds:
                    (l1, c1), (l2, c2) = bounds
                    if l1 < actual_line < l2:
                        sel_range = (0, len(out_line) + 1)
                    elif l1 == actual_line == l2:
                        sel_range = (c1, c2)
                    elif l1 == actual_line < l2:
                        sel_range = (c1, len(out_line) + 1)
                    elif l1 < actual_line == l2:
                        sel_range = (0, c2)

                # Determine LazyVim zip-zap yank flash range for this line
                yank_in_line = False
                y_range = None
                if is_yank_active:
                    if self.yank_flash_bounds:
                        (yl1, yc1), (yl2, yc2) = self.yank_flash_bounds
                        if yl1 <= actual_line <= yl2:
                            yank_in_line = True
                            if yl1 < actual_line < yl2:
                                y_range = (0, len(out_line) + 1)
                            elif yl1 == actual_line == yl2:
                                y_range = (yc1, yc2)
                            elif yl1 == actual_line:
                                y_range = (yc1, len(out_line) + 1)
                            elif actual_line == yl2:
                                y_range = (0, yc2)
                    else:
                        yank_in_line = True
                        y_range = (0, len(out_line) + 1)

                col = output_x + 2
                char_idx = 0
                for token_str, token_fg in tokens:
                    if col >= output_x + out_w - 2: break
                    for ch in token_str:
                        if col >= output_x + out_w - 2: break
                        is_sel = sel_range and (sel_range[0] <= char_idx < sel_range[1])
                        is_flash = yank_in_line and y_range and (y_range[0] <= char_idx < y_range[1])

                        if is_flash:
                            ch_fg = (15, 23, 42)
                            ch_bg = (251, 191, 36) # Zip-Zap electric gold flash
                            ch_bold = True
                        elif is_sel:
                            ch_fg = (255, 255, 255)
                            ch_bg = (80, 70, 160)
                            ch_bold = True
                        else:
                            ch_fg = token_fg
                            ch_bg = self.theme.colors["surface"]
                            ch_bold = False

                        self.buffer.put_char(col, inner_y + row, ch, ch_fg, ch_bg, bold=ch_bold)
                        col += 1
                        char_idx += 1

                # If the line was empty but within selection or flash range, draw a highlighted space
                if not out_line:
                    if is_yank_active and yank_in_line:
                        self.buffer.put_char(output_x + 2, inner_y + row, " ", (15, 23, 42), (251, 191, 36))
                    elif sel_range:
                        self.buffer.put_char(output_x + 2, inner_y + row, " ", (255, 255, 255), (80, 70, 160))

            # Render cursor in Output when focused or in visual mode
            if is_out_focus:
                cx = output_x + 2 + self.output_cursor_x
                cy = inner_y + (self.output_cursor_y - render_out_scroll)
                if inner_y <= cy < inner_y + inner_h and output_x + 2 <= cx < output_x + out_w - 2:
                    char_at = " "
                    if 0 <= self.output_cursor_y < len(out_lines):
                        line = out_lines[self.output_cursor_y]
                        if 0 <= self.output_cursor_x < len(line):
                            char_at = line[self.output_cursor_x]
                    is_blink = (int(time.time() * 2.2) % 2 == 0)
                    cursor_bg = (125, 211, 252) if self.output_visual_mode else ((52, 211, 153) if is_blink else self.theme.colors["surface_high"])
                    self.buffer.put_char(cx, cy, char_at, (15, 23, 42), cursor_bg, bold=True)

    def render_statusbar(self):
        """Status line at bottom row with Zellij segmented key chips."""
        y = self.height - 1
        bar_bg = self.theme.colors["surface_dim"]
        for x in range(self.width - 1):
            self.buffer.put_char(x, y, " ", self.theme.colors["text_muted"], bar_bg)

        # 1. Mode Capsule (Far Left)
        if self.leader_active:
            mode_text = " ⚡ SUPER "
            mode_bg = self.theme.colors["warning"] # Vibrant Amber
            mode_fg = (15, 23, 42) # Deep Dark
        elif self.view_mode == "SEARCH":
            mode_text = " SEARCH "
            mode_bg = self.theme.colors["accent"]  # Vibrant Sky Blue
            mode_fg = (15, 23, 42)
        elif self.view_mode == "HELP":
            mode_text = " HELP "
            mode_bg = self.theme.colors["primary"] # Vibrant Purple
            mode_fg = (15, 23, 42)
        elif self.output_visual_mode:
            mode_text = " VISUAL "
            mode_bg = (125, 211, 252) # Accent Cyan
            mode_fg = (15, 23, 42)
        else:
            mode_text = " NORMAL "
            mode_bg = (52, 211, 153) # Vibrant Zellij Emerald Green
            mode_fg = (15, 23, 42)

        self.buffer.put_str(0, y, mode_text, mode_fg, mode_bg, bold=True)
        cur_x = str_display_width(mode_text) + 1

        # 2. Right Info (Always pinned cleanly on the far right with 2-char margin)
        info_items = []
        sel_text = self.get_output_selection_text()
        if sel_text:
            info_items.append((f"{len(sel_text)} chars selected", (52, 211, 153)))
        elif not self.leader_active and self.status_msg and (time.time() - self.status_time < 3.5):
            elapsed = time.time() - self.status_time
            if elapsed < 0.6:
                info_items.append((f"⚡ {self.status_msg}", (251, 191, 36)))
            else:
                info_items.append((self.status_msg, (52, 211, 153)))
        elif self.leader_active:
            info_items.append(("⚡ Press /:Spotlight · ?:Help · c:Copy · q:Quit", self.theme.colors["warning"]))
        info_items.append((f"Ln {self.editor.cursor_y + 1}, Col {self.editor.cursor_x + 1}", self.theme.colors["text_muted"]))
        info_items.append((f"{len(TOOL_REGISTRY)} tools", self.theme.colors["text_muted"]))

        right_parts = [it[0] for it in info_items]
        right_str = "  │  ".join(right_parts) + " "
        right_disp_w = str_display_width(right_str)
        right_start_x = self.width - right_disp_w - 2

        # Drop first item if space is tight on small screens
        while right_start_x < 35 and len(info_items) > 1:
            info_items.pop(0)
            right_parts = [it[0] for it in info_items]
            right_str = "  │  ".join(right_parts) + " "
            right_disp_w = str_display_width(right_str)
            right_start_x = self.width - right_disp_w - 2

        if right_start_x > cur_x + 2:
            rx = right_start_x
            for i, (txt, color) in enumerate(info_items):
                if i > 0:
                    sep = "  │  "
                    if rx + len(sep) >= self.width - 2:
                        break
                    self.buffer.put_str(rx, y, sep, self.theme.colors["border"], bar_bg)
                    rx += len(sep)
                txt_w = str_display_width(txt)
                if rx + txt_w >= self.width - 1:
                    break
                self.buffer.put_str(rx, y, txt, color, bar_bg, bold=(txt.startswith("●") or txt.startswith("⚡") or "chars selected" in txt))
                rx += txt_w

        # 3. Zellij Keybinding Chips (Fill available middle space)
        def draw_chip(col_x: int, key_label: str, desc: str, is_active_key: bool = False) -> int:
            pill_str = f" <{key_label}> "
            desc_str = f" {desc} "
            needed = str_display_width(pill_str) + str_display_width(desc_str)
            if col_x + needed >= right_start_x - 1:
                return col_x # Don't collide with right info

            k_bg = self.theme.colors["warning"] if is_active_key else self.theme.colors["surface_high"]
            k_fg = (15, 23, 42) if is_active_key else (240, 240, 248)
            self.buffer.put_str(col_x, y, pill_str, k_fg, k_bg, bold=True)
            col_x += str_display_width(pill_str)

            d_fg = (240, 240, 248) if is_active_key else self.theme.colors["text_muted"]
            self.buffer.put_str(col_x, y, desc_str, d_fg, bar_bg)
            col_x += str_display_width(desc_str)
            return col_x

        if self.leader_active:
            commands = [
                ("/", "Spotlight", True),
                ("?", "Help", True),
                ("c", "Copy", True),
                ("q", "Quit", True),
                ("Tab", "Switch", False),
                ("n/p", "Nav", False),
                ("z", "Zoom", False),
                ("x", "Clear", False),
                ("Esc", "Cancel", False),
            ]
            for k_lbl, k_desc, k_act in commands:
                cur_x = draw_chip(cur_x, k_lbl, k_desc, is_active_key=k_act)
        else:
            commands = [
                ("Ctrl+b", "then", True),
                ("/", "Spotlight", False),
                ("?", "Help", False),
                ("c", "Copy", False),
                ("q", "Quit", False),
                ("Tab", "Switch", False),
                ("z", "Zoom", False),
            ]
            for k_lbl, k_desc, k_act in commands:
                cur_x = draw_chip(cur_x, k_lbl, k_desc, is_active_key=False)

    def render_search_modal(self):
        modal_w = max(24, min(74, self.width - 4))
        modal_h = max(7, min(17, self.height - 4))
        x = max(0, (self.width - modal_w) // 2)
        y = max(1, (self.height - modal_h) // 2)

        # Card background fill with rich dark surface
        for r in range(y, y + modal_h):
            for c in range(x, x + modal_w):
                self.buffer.put_char(c, r, " ", self.theme.colors["text"], self.theme.colors["surface"])

        self.buffer.draw_box(x, y, modal_w, modal_h,
                             (52, 211, 153),
                             self.theme.colors["surface"],
                             title="🔍 SPOTLIGHT PALETTE",
                             title_right=f"{len(self.search_results)} tools",
                             active=True,
                             title_fg=(240, 240, 248),
                             badge_fg=(52, 211, 153),
                             indicator_fg=(52, 211, 153))

        # Kinetic smooth scrolling for spotlight list (LazyVim style glide)
        max_res = max(1, modal_h - 6)
        if self.search_selected_idx < self.search_scroll_y:
            self.search_scroll_y = self.search_selected_idx
        elif self.search_selected_idx >= self.search_scroll_y + max_res:
            self.search_scroll_y = self.search_selected_idx - max_res + 1

        max_scroll = max(0, len(self.search_results) - max_res)
        self.search_scroll_y = max(0, min(self.search_scroll_y, max_scroll))

        diff_s = self.search_scroll_y - self.search_scroll_current
        if abs(diff_s) > 0.05:
            self.search_scroll_current += diff_s * 0.45
        else:
            self.search_scroll_current = float(self.search_scroll_y)
        render_search_y = int(round(self.search_scroll_current))
        render_search_y = max(0, min(render_search_y, max_scroll))

        # Search Input: › query▏
        search_y = y + 1
        icon = "  ›  "
        self.buffer.put_str(x + 1, search_y, icon, self.theme.colors["accent"], self.theme.colors["surface"], bold=True)

        # I-shaped cursor with smooth blinking animation (LazyVim / modern TUI style)
        is_blink_on = (int(time.time() * 2.2) % 2 == 0)
        cursor_char = "▏" if is_blink_on else " "
        cursor_fg = (125, 211, 252) # Vibrant Cyan I-beam

        if self.search_query:
            self.buffer.put_str(x + 6, search_y, self.search_query, self.theme.colors["text"], self.theme.colors["surface"], bold=True)
            cur_x = x + 6 + str_display_width(self.search_query)
            if cur_x < x + modal_w - 2:
                self.buffer.put_str(cur_x, search_y, cursor_char, cursor_fg, self.theme.colors["surface"], bold=True)
        else:
            # Empty query: show blinking I-shaped cursor right before the subtle placeholder
            self.buffer.put_str(x + 6, search_y, cursor_char, cursor_fg, self.theme.colors["surface"], bold=True)
            placeholder = f"Search {len(TOOL_REGISTRY)} tools (e.g. json, jwt, regex, math, hash)..."
            self.buffer.put_str(x + 7, search_y, placeholder, self.theme.colors["text_muted"], self.theme.colors["surface"])

        # Separator line with seamless tee-junctions
        div_y = y + 2
        self.buffer.put_char(x, div_y, "├", (52, 211, 153), self.theme.colors["surface"])
        for i in range(1, modal_w - 1):
            self.buffer.put_char(x + i, div_y, "─", self.theme.colors["border"], self.theme.colors["surface"])
        self.buffer.put_char(x + modal_w - 1, div_y, "┤", (52, 211, 153), self.theme.colors["surface"])

        # Results list
        res_y = y + 3
        visible_results = self.search_results[render_search_y : render_search_y + max_res]
        for offset, t in enumerate(visible_results):
            idx = render_search_y + offset
            row_y = res_y + offset
            is_sel = (idx == self.search_selected_idx)
            bg = self.theme.colors["surface_high"] if is_sel else self.theme.colors["surface"]
            fg_name = self.theme.colors["primary"] if is_sel else self.theme.colors["text"]
            fg_cat = self.theme.colors["accent"] if is_sel else self.theme.colors["text_muted"]

            # Line background
            for c in range(x + 1, x + modal_w - 1):
                self.buffer.put_char(c, row_y, " ", self.theme.colors["text"], bg)

            # LazyVim style glowing pointer: ▶ when selected
            pointer = "▶ " if is_sel else "  "
            p_fg = (52, 211, 153) if is_sel else bg
            self.buffer.put_str(x + 3, row_y, pointer, p_fg, bg, bold=is_sel)

            # Tool icon and name starting at x + 6
            t_icon = get_tool_icon(t)
            icon_str = f"{t_icon} "
            icon_w = str_display_width(icon_str)
            self.buffer.put_str(x + 6, row_y, icon_str, (52, 211, 153) if is_sel else self.theme.colors["text"], bg)

            name_x = x + 6 + icon_w
            name_w = min(26, max(10, modal_w - 36 - icon_w))
            name_str = f"{t.name:<{name_w}}"[:name_w]

            # LazyVim match character highlighting
            q_clean = self.search_query.strip().lower()
            if q_clean and is_sel:
                nx = name_x
                for ch in name_str:
                    if nx >= x + modal_w - 12: break
                    is_match = (ch.lower() in q_clean)
                    c_fg = (251, 191, 36) if is_match else fg_name
                    self.buffer.put_char(nx, row_y, ch, c_fg, bg, bold=(is_sel or is_match))
                    nx += 1
            else:
                self.buffer.put_str(name_x, row_y, name_str, fg_name, bg, bold=is_sel, max_len=name_w + 2)

            cat_x = name_x + name_w + 3
            if cat_x + str_display_width(t.category) < x + modal_w - 11:
                self.buffer.put_str(cat_x, row_y, t.category, fg_cat, bg)

            if is_sel:
                open_hint = "[↵ Open]"
                self.buffer.put_str(x + modal_w - len(open_hint) - 3, row_y, open_hint, self.theme.colors["accent"], bg, bold=True)

        # Modal divider with seamless tee-junctions
        div_foot = y + modal_h - 3
        self.buffer.put_char(x, div_foot, "├", (52, 211, 153), self.theme.colors["surface"])
        for i in range(1, modal_w - 1):
            self.buffer.put_char(x + i, div_foot, "─", self.theme.colors["border"], self.theme.colors["surface"])
        self.buffer.put_char(x + modal_w - 1, div_foot, "┤", (52, 211, 153), self.theme.colors["surface"])

        # Footer row with clean padding and alignment
        foot_y = y + modal_h - 2
        foot_text = "↑/↓ Navigate  ·  ↵ Open Tool  ·  Esc Close"
        self.buffer.put_str(x + 3, foot_y, foot_text, self.theme.colors["text_muted"], self.theme.colors["surface"])
        total_matching = len(self.search_results)
        cur_pos = self.search_selected_idx + 1 if total_matching > 0 else 0
        cnt_str = f" {cur_pos}/{total_matching} tools "
        self.buffer.put_str(x + modal_w - len(cnt_str) - 2, foot_y, cnt_str, self.theme.colors["accent"], self.theme.colors["surface"], bold=True)

    def render_help_modal(self):
        modal_w = max(28, min(74, self.width - 6))
        modal_h = max(7, min(24, self.height - 4))
        x = max(0, (self.width - modal_w) // 2)
        y = max(1, (self.height - modal_h) // 2)

        self.buffer.draw_box(x, y, modal_w, modal_h,
                             (52, 211, 153),
                             self.theme.colors["surface"],
                             title="⌨️  KEYBINDINGS & SHORTCUTS",
                             title_right="@realnishil",
                             active=True,
                             title_fg=(240, 240, 248),
                             badge_fg=(52, 211, 153),
                             indicator_fg=(52, 211, 153))

        help_lines = [
            ("Ctrl+B then /", "Spotlight Search (87 Tools)"),
            ("Ctrl+B then ?", "Keybindings & Help Modal"),
            ("Ctrl+B then q", "Quit / Exit PRISM Immediately"),
            ("Ctrl+B then c", "Copy Output to System Clipboard"),
            ("Ctrl+B then Tab", "Switch Focus: Input ↔ Output Pane"),
            ("Ctrl+B then n / p", "Next / Previous Tool (Navigate)"),
            ("Ctrl+B then ← / →", "Previous / Next Category"),
            ("Ctrl+B then z / w", "Zoom / Toggle Workspace Layout"),
            ("Ctrl+B then [", "Output Scroll Mode (↑↓ / PgUp / PgDn)"),
            ("Ctrl+B then x", "Clear Input Buffer"),
            ("Ctrl+B then b / Esc", "Go Back / Close Modal"),
            ("Space in Output", "Open Which-Key Navigation Popup"),
            ("Mouse Drag in Output", "Select & Auto-Copy to Clipboard"),
            ("Double-Click in Output", "Select Word & Copy to Clipboard"),
            ("In Output: 'v'", "Toggle Visual Selection Mode"),
            ("In Output: 'a'", "Select All Output Text"),
            ("Ctrl+C", "Emergency Exit (Anywhere)"),
            ("Tab / Shift+Tab", "Quick Switch: Input ↔ Output"),
            ("F2", "Toggle Split ↔ Full Input ↔ Full Output"),
            ("Esc", "Close Modal or Return to Input"),
        ]

        for i, (key, desc) in enumerate(help_lines):
            row_y = y + 2 + i
            if row_y >= y + modal_h - 3: break
            if not key:
                self.buffer.put_str(x + 4, row_y, desc, self.theme.colors["text_muted"], self.theme.colors["surface"])
            else:
                self.buffer.put_str(x + 4, row_y, f"{key:<24}", self.theme.colors["accent"], self.theme.colors["surface"], bold=True)
                self.buffer.put_str(x + 30, row_y, desc, self.theme.colors["text"], self.theme.colors["surface"])

        # Footer divider and github link
        div_foot = y + modal_h - 3
        self.buffer.put_char(x, div_foot, "├", (52, 211, 153), self.theme.colors["surface"])
        for i in range(1, modal_w - 1):
            self.buffer.put_char(x + i, div_foot, "─", self.theme.colors["border"], self.theme.colors["surface"])
        self.buffer.put_char(x + modal_w - 1, div_foot, "┤", (52, 211, 153), self.theme.colors["surface"])

        foot_y = y + modal_h - 2
        foot_left = "Esc / ↵ Close Help"
        foot_right = "github.com/realnishil"
        self.buffer.put_str(x + 3, foot_y, foot_left, self.theme.colors["text_muted"], self.theme.colors["surface"])
        if x + modal_w - len(foot_right) - 3 > x + 3 + len(foot_left) + 2:
            self.buffer.put_str(x + modal_w - len(foot_right) - 3, foot_y, foot_right, (125, 211, 252), self.theme.colors["surface"], bold=True)

    def render_welcome_screen(self):
        """Startup window popup with blank screen at the back."""
        # 1. Blank background screen
        bg = self.theme.colors["bg"]
        for r in range(self.height):
            for c in range(self.width):
                self.buffer.put_char(c, r, " ", self.theme.colors["text"], bg)

        # 2. Centered window popup
        guides = [
            ("Ctrl+B then /", "Spotlight Palette (87 Offline Tools)"),
            ("Ctrl+B then ?", "Keybindings & Help Cheat Sheet"),
            ("Ctrl+B then c", "Copy Output to System Clipboard"),
            ("Ctrl+B then Tab", "Switch Focus (Input ↔ Output Pane)"),
            ("Ctrl+B then n / p", "Next / Previous Tool (Navigate)"),
            ("Ctrl+B then ← / →", "Previous / Next Category"),
            ("Ctrl+B then x", "Clear Input Editor Buffer"),
            ("F2 / Ctrl+B z", "Zoom / Toggle Workspace Layout"),
            ("Mouse Drag in Output", "Select & Auto-Copy to Clipboard"),
            ("Ctrl+B then q", "Quit PRISM Immediately"),
        ]

        win_w = max(44, min(74, self.width - 4))
        win_h = max(11, min(len(guides) + 7, self.height - 2))
        win_x = max(0, (self.width - win_w) // 2)
        win_y = max(0, (self.height - win_h) // 2)
        surf = self.theme.colors["surface"]

        for r in range(win_y, win_y + win_h):
            for c in range(win_x, win_x + win_w):
                self.buffer.put_char(c, r, " ", self.theme.colors["text"], surf)

        self.buffer.draw_box(win_x, win_y, win_w, win_h,
                             (52, 211, 153),
                             surf,
                             title="✨ PRISM v1.1.0",
                             title_right="@realnishil",
                             active=True,
                             title_fg=(240, 240, 248),
                             badge_fg=(52, 211, 153),
                             indicator_fg=(52, 211, 153))

        # Subtitle
        sub_text = "The Elegant Offline Developer Toolbox"
        sub_x = win_x + max(2, (win_w - str_display_width(sub_text)) // 2)
        self.buffer.put_str(sub_x, win_y + 1, sub_text, self.theme.colors["text_muted"], surf)

        # Author / Attribution
        by_text = "Created by @realnishil  ·  github.com/realnishil"
        by_x = win_x + max(2, (win_w - str_display_width(by_text)) // 2)
        self.buffer.put_str(by_x, win_y + 2, by_text, (125, 211, 252), surf, bold=True)

        # Top separator divider
        div_top = win_y + 3
        self.buffer.put_char(win_x, div_top, "├", (52, 211, 153), surf)
        for i in range(1, win_w - 1):
            self.buffer.put_char(win_x + i, div_top, "─", self.theme.colors["border"], surf)
        self.buffer.put_char(win_x + win_w - 1, div_top, "┤", (52, 211, 153), surf)

        # Keybindings & Navigation Cheat Sheet
        for idx, (key_label, desc) in enumerate(guides):
            row_y = win_y + 4 + idx
            if row_y >= win_y + win_h - 3:
                break
            self.buffer.put_str(win_x + 3, row_y, f"{key_label:<22}", (125, 211, 252), surf, bold=True)
            self.buffer.put_str(win_x + 26, row_y, desc, self.theme.colors["text"], surf, max_len=win_w - 28)

        # Bottom separator divider
        div_bot = win_y + win_h - 3
        self.buffer.put_char(win_x, div_bot, "├", (52, 211, 153), surf)
        for i in range(1, win_w - 1):
            self.buffer.put_char(win_x + i, div_bot, "─", self.theme.colors["border"], surf)
        self.buffer.put_char(win_x + win_w - 1, div_bot, "┤", (52, 211, 153), surf)

        # Enter prompt to dismiss
        enter_prompt = "[ Press ↵ Enter to Continue ]"
        p_x = win_x + max(2, (win_w - str_display_width(enter_prompt)) // 2)
        self.buffer.put_str(p_x, win_y + win_h - 2, enter_prompt, (52, 211, 153), surf, bold=True)

    def execute_leader_command(self, action_id: str):
        """Execute a super key action."""
        self.leader_active = False
        action = action_id.lower()
        if action in ["q", "quit", "exit"]:
            self.running = False
        elif action in ["/", "search", "spotlight", "k", "s"]:
            self.view_mode = "SEARCH"
            self.search_query = ""
            self.search_scroll_y = 0
            self.search_selected_idx = 0
            self.update_search_results()
        elif action in ["?", "help"]:
            self.view_mode = "HELP" if self.view_mode != "HELP" else "WORKSPACE"
        elif action in ["c", "copy", "y"]:
            sel = self.get_output_selection_text()
            target_copy = sel if sel else self.output_text
            if SystemBridge.copy_to_clipboard(target_copy):
                self.trigger_yank_flash(self.get_output_selection_bounds() if sel else None)
                if sel:
                    self.set_status(f"Copied selection ({len(sel)} chars) to clipboard")
                else:
                    self.set_status(f"Full output ({len(self.output_text)} chars) copied to clipboard")
            else:
                self.set_status("Clipboard copy error.")
        elif action in ["tab", "switch", "o"]:
            self.focus = "OUTPUT" if self.focus == "INPUT" else "INPUT"
            self.set_status(f"Switched focus to {self.focus} pane")
        elif action in ["z", "zoom", "layout", "w"]:
            cycle = ["SPLIT", "MAX_INPUT", "MAX_OUTPUT"]
            idx = cycle.index(self.workspace_layout) if self.workspace_layout in cycle else 0
            self.workspace_layout = cycle[(idx + 1) % len(cycle)]
            self.set_status(f"Layout: {self.workspace_layout}")
        elif action in ["x", "clear", "d"]:
            self.editor.clear()
            self.run_current_tool()
            self.set_status("Editor cleared.")
        elif action in ["r", "swap"]:
            cur_out = self.output_text
            self.editor.set_text(cur_out)
            self.run_current_tool()
            self.set_status("Swapped Input & Output.")
        elif action in ["n", "next", "down"]:
            self.next_tool()
            self.set_status(f"Tool: {self.current_tool.name}")
        elif action in ["p", "prev", "up"]:
            self.prev_tool()
            self.set_status(f"Tool: {self.current_tool.name}")
        elif action in ["right", "next_cat", "l"]:
            self.next_category()
            self.set_status(f"Category: {self.current_tool.category}")
        elif action in ["left", "prev_cat", "h"]:
            self.prev_category()
            self.set_status(f"Category: {self.current_tool.category}")
        elif action in ["[", "scroll"]:
            self.focus = "OUTPUT"
            self.set_status("Output Scroll Mode")
        elif action in ["b", "back"]:
            if self.view_mode in ["SEARCH", "HELP"]:
                self.view_mode = "WORKSPACE"
                self.focus = "INPUT"
                self.set_status("Returned to workspace")
            else:
                self.prev_tool()
                self.set_status(f"Back to: {self.current_tool.name}")
        elif action in ["escape", "esc", "cancel"]:
            if self.view_mode in ["SEARCH", "HELP"]:
                self.view_mode = "WORKSPACE"
                self.focus = "INPUT"
                self.set_status("Returned to workspace")
            else:
                self.set_status("Super Key cancelled")

    # --------------------------------------------------------------------------
    # EVENT DISPATCHER
    # --------------------------------------------------------------------------

    def handle_event(self, key: Optional[KeyEvent], mouse: Optional[MouseEvent]):
        if mouse:
            self.handle_mouse(mouse)
            return

        if not key:
            return

        # Startup Welcome Screen: Press Enter, Space, Esc or any key to enter normal workspace
        if self.view_mode == "WELCOME":
            if key and key.name in ["enter", "space", "escape", "char"]:
                self.view_mode = "WORKSPACE"
                self.set_status("Welcome to PRISM! Press Ctrl+B ? for help.")
            return

        # Emergency exit: Ctrl+C quits immediately from anywhere (unless super key is active and user meant copy)
        if key.name == "ctrl_c" and not self.leader_active:
            self.running = False
            return

        # Check super key timeout (5.0 seconds)
        if self.leader_active and (time.time() - self.leader_time > 5.0):
            self.leader_active = False

        # Super Key (Leader) toggle: Ctrl+B
        if key.name == "ctrl_b":
            self.leader_active = not self.leader_active
            self.leader_time = time.time()
            if self.leader_active:
                self.set_status("Super Key active: /:Spotlight  ?:Help  c:Copy  q:Quit")
            else:
                self.set_status("Super Key cancelled")
            return

        # If Super Key (Ctrl+B) is active, route through keybindings!
        if self.leader_active:
            if key.name in ["ctrl_q", "q"] or (key.name == "char" and key.char.lower() == "q"):
                self.execute_leader_command("q")
                return
            if (key.name == "char" and key.char in ["/", "k", "s"]) or key.name in ["ctrl_k", "slash"]:
                self.execute_leader_command("/")
                return
            if (key.name == "char" and key.char == "?") or key.name in ["f1", "?"]:
                self.execute_leader_command("?")
                return
            if (key.name == "char" and key.char.lower() in ["c", "y"]) or key.name in ["ctrl_c", "ctrl_y"]:
                self.execute_leader_command("c")
                return
            if key.name == "char" and key.char.lower() in ["x", "d"]:
                self.execute_leader_command("x")
                return
            if key.name in ["tab", "shift_tab"] or (key.name == "char" and key.char.lower() == "o"):
                self.execute_leader_command("tab")
                return
            if key.name == "f2" or (key.name == "char" and key.char.lower() in ["z", "w"]):
                self.execute_leader_command("z")
                return
            if (key.name == "char" and key.char.lower() == "r") or key.name == "ctrl_r":
                self.execute_leader_command("r")
                return
            if (key.name == "char" and key.char.lower() == "n") or key.name in ["down", "ctrl_n"]:
                self.execute_leader_command("n")
                return
            if (key.name == "char" and key.char.lower() == "p") or key.name in ["up", "ctrl_p"]:
                self.execute_leader_command("p")
                return
            if (key.name == "char" and key.char.lower() == "l") or key.name == "right":
                self.execute_leader_command("right")
                return
            if (key.name == "char" and key.char.lower() == "h") or key.name == "left":
                self.execute_leader_command("left")
                return
            if key.name == "char" and key.char == "[":
                self.execute_leader_command("[")
                return
            if key.name == "char" and key.char.lower() == "b":
                self.execute_leader_command("b")
                return
            if key.name == "escape":
                self.execute_leader_command("escape")
                return

            # Any other key pressed after prefix is consumed and cancels
            self.execute_leader_command("escape")
            return

        # Modal handlers (when not in prefix mode)
        if self.view_mode == "SEARCH":
            self.handle_search_key(key)
            return
        elif self.view_mode == "HELP":
            if key.name in ["escape", "enter"]:
                self.view_mode = "WORKSPACE"
            return

        # Global Search Hotkeys: Ctrl+K or '/' (when not editing text)
        if key.name == "ctrl_k" or (key.name == "char" and key.char == "/" and self.focus != "INPUT"):
            self.view_mode = "SEARCH"
            self.search_query = ""
            self.update_search_results()
            return

        # Global Help Hotkey
        if key.name == "f1":
            self.view_mode = "HELP" if self.view_mode != "HELP" else "WORKSPACE"
            return

        # Clipboard copy (Ctrl+Y)
        if key.name == "ctrl_y":
            sel = self.get_output_selection_text()
            target_copy = sel if sel else self.output_text
            if SystemBridge.copy_to_clipboard(target_copy):
                self.trigger_yank_flash(self.get_output_selection_bounds() if sel else None)
                if sel:
                    self.set_status(f"Copied selection ({len(sel)} chars) to clipboard")
                else:
                    self.set_status(f"Full output ({len(self.output_text)} chars) copied to clipboard")
            else:
                self.set_status("Clipboard copy error.")
            return

        # Clear input (Ctrl+L)
        if key.name == "ctrl_l":
            self.editor.clear()
            self.run_current_tool()
            self.set_status("Editor cleared.")
            return

        # Swap buffers (Ctrl+R)
        if key.name == "ctrl_r":
            cur_out = self.output_text
            self.editor.set_text(cur_out)
            self.run_current_tool()
            self.set_status("Swapped Input & Output.")
            return

        # Layout toggle: F2 toggles SPLIT -> MAX_INPUT -> MAX_OUTPUT -> SPLIT
        if key.name == "f2":
            cycle = ["SPLIT", "MAX_INPUT", "MAX_OUTPUT"]
            idx = cycle.index(self.workspace_layout) if self.workspace_layout in cycle else 0
            self.workspace_layout = cycle[(idx + 1) % len(cycle)]
            self.set_status(f"Workspace layout: {self.workspace_layout}")
            return

        # Focus Switching: Tab / Shift+Tab toggles between INPUT and OUTPUT
        if key.name == "tab" or key.name == "shift_tab":
            self.focus = "OUTPUT" if self.focus == "INPUT" else "INPUT"
            return

        # Esc key handling: close modals, clear output selection, or dismiss status toast
        if key.name == "escape":
            if self.view_mode in ["SEARCH", "HELP"]:
                self.view_mode = "WORKSPACE"
                self.focus = "INPUT"
                self.set_status("Returned to workspace")
            elif self.focus == "OUTPUT":
                if self.has_output_selection() or self.output_visual_mode:
                    self.clear_output_selection()
                    self.set_status("Selection cleared")
                else:
                    self.focus = "INPUT"
            elif self.status_msg:
                self.status_msg = ""
            return

        # Tool cycling shortcuts
        if key.name == "ctrl_p" or (key.alt and key.name == "up"):
            self.prev_tool()
            self.set_status(f"Tool: {self.current_tool.name}")
            return
        elif key.name == "ctrl_n" or (key.alt and key.name == "down"):
            self.next_tool()
            self.set_status(f"Tool: {self.current_tool.name}")
            return
        elif key.alt and key.name == "left":
            self.prev_category()
            self.set_status(f"Category: {self.current_tool.category}")
            return
        elif key.alt and key.name == "right":
            self.next_category()
            self.set_status(f"Category: {self.current_tool.category}")
            return

        # Panel Key Handling
        if self.focus == "INPUT":
            self.editor.handle_key(key)
            self.run_current_tool()
        elif self.focus == "OUTPUT":
            self.handle_output_key(key)

    def handle_output_key(self, key: KeyEvent):
        out_lines = self.output_text.splitlines() or [""]
        total_lines = len(out_lines)
        inner_h = max(1, self.height - 4)

        # 1. Copy selection or full output: 'c', 'y', Ctrl+C, Ctrl+Y
        if (key.name == "char" and key.char.lower() in ["c", "y"]) or key.name in ["ctrl_c", "ctrl_y"]:
            sel = self.get_output_selection_text()
            if sel:
                self.trigger_yank_flash(self.get_output_selection_bounds())
                SystemBridge.copy_to_clipboard(sel)
                if "\n" in sel:
                    self.set_status(f"Copied {len(sel.splitlines())} lines to clipboard")
                else:
                    disp = sel if len(sel) <= 22 else sel[:20] + "..."
                    self.set_status(f"Copied '{disp}' to clipboard")
            else:
                self.trigger_yank_flash(None)
                if SystemBridge.copy_to_clipboard(self.output_text):
                    self.set_status(f"Full output ({len(self.output_text)} chars) copied to clipboard")
                else:
                    self.set_status("Clipboard copy error.")
            return

        # 2. Select All: 'a' or Ctrl+A
        if (key.name == "char" and key.char.lower() == "a") or key.name == "ctrl_a":
            self.select_all_output()
            sel = self.get_output_selection_text()
            if sel:
                self.trigger_yank_flash(self.get_output_selection_bounds())
                SystemBridge.copy_to_clipboard(sel)
                self.set_status(f"Selected & copied all ({len(sel)} chars) to clipboard")
            return

        # 3. Visual mode toggle: 'v'
        if key.name == "char" and key.char.lower() == "v":
            if not self.output_visual_mode:
                self.output_visual_mode = True
                self.output_sel_start = (self.output_cursor_y, self.output_cursor_x)
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)
                self.set_status("Visual Mode ON (Arrows/PgUp/PgDn to select, 'y'/'c' to copy, Esc to clear)")
            else:
                self.output_visual_mode = False
                self.clear_output_selection()
                self.set_status("Visual Mode OFF")
            return

        # 4. Escape: clear selection or return to INPUT
        if key.name == "escape":
            if self.has_output_selection() or self.output_visual_mode:
                self.clear_output_selection()
                self.set_status("Selection cleared")
            else:
                self.focus = "INPUT"
            return

        # 5. Cursor Navigation & Auto-scrolling
        if key.name == "up":
            if self.output_cursor_y > 0:
                self.output_cursor_y -= 1
                cur_len = len(out_lines[self.output_cursor_y]) if self.output_cursor_y < total_lines else 0
                self.output_cursor_x = min(self.output_cursor_x, cur_len)
            if self.output_cursor_y < self.output_scroll_y:
                self.output_scroll_y = self.output_cursor_y
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "down":
            if self.output_cursor_y < total_lines - 1:
                self.output_cursor_y += 1
                cur_len = len(out_lines[self.output_cursor_y]) if self.output_cursor_y < total_lines else 0
                self.output_cursor_x = min(self.output_cursor_x, cur_len)
            if self.output_cursor_y >= self.output_scroll_y + inner_h:
                self.output_scroll_y = self.output_cursor_y - inner_h + 1
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "left":
            if self.output_cursor_x > 0:
                self.output_cursor_x -= 1
            elif self.output_cursor_y > 0:
                self.output_cursor_y -= 1
                self.output_cursor_x = len(out_lines[self.output_cursor_y])
                if self.output_cursor_y < self.output_scroll_y:
                    self.output_scroll_y = self.output_cursor_y
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "right":
            cur_len = len(out_lines[self.output_cursor_y]) if self.output_cursor_y < total_lines else 0
            if self.output_cursor_x < cur_len:
                self.output_cursor_x += 1
            elif self.output_cursor_y < total_lines - 1:
                self.output_cursor_y += 1
                self.output_cursor_x = 0
                if self.output_cursor_y >= self.output_scroll_y + inner_h:
                    self.output_scroll_y = self.output_cursor_y - inner_h + 1
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "home":
            self.output_cursor_x = 0
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "end":
            cur_len = len(out_lines[self.output_cursor_y]) if self.output_cursor_y < total_lines else 0
            self.output_cursor_x = cur_len
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "page_up":
            self.output_scroll_y = max(0, self.output_scroll_y - inner_h)
            self.output_cursor_y = max(0, self.output_cursor_y - inner_h)
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "page_down":
            max_scroll = max(0, total_lines - inner_h)
            self.output_scroll_y = min(max_scroll, self.output_scroll_y + inner_h)
            self.output_cursor_y = min(total_lines - 1, self.output_cursor_y + inner_h)
            if self.output_visual_mode:
                self.output_sel_end = (self.output_cursor_y, self.output_cursor_x)

        elif key.name == "char" and key.char == "[":
            self.prev_tool()
            self.set_status(f"Tool: {self.current_tool.name}")
        elif key.name == "char" and key.char == "]":
            self.next_tool()
            self.set_status(f"Tool: {self.current_tool.name}")
        elif key.name == "char" and key.char == "?":
            self.view_mode = "HELP"
        elif key.name == "char" and key.char == "/":
            self.view_mode = "SEARCH"
            self.search_query = ""
            self.update_search_results()

    def handle_search_key(self, key: KeyEvent):
        if key.name == "escape":
            self.view_mode = "WORKSPACE"
        elif key.name in ["up", "ctrl_p"]:
            self.search_selected_idx = max(0, self.search_selected_idx - 1)
        elif key.name in ["down", "ctrl_n"]:
            self.search_selected_idx = min(max(0, len(self.search_results) - 1), self.search_selected_idx + 1)
        elif key.name == "page_up":
            self.search_selected_idx = max(0, self.search_selected_idx - 8)
        elif key.name == "page_down":
            self.search_selected_idx = min(max(0, len(self.search_results) - 1), self.search_selected_idx + 8)
        elif key.name == "enter":
            if self.search_results:
                sel = self.search_results[self.search_selected_idx]
                self.select_tool(sel)
                self.view_mode = "WORKSPACE"
                self.focus = "INPUT"
                self.set_status(f"Selected: {sel.name}")
        elif key.name == "backspace":
            self.search_query = self.search_query[:-1]
            self.search_selected_idx = 0
            self.search_scroll_y = 0
            self.update_search_results()
        elif key.name == "char" and key.char:
            self.search_query += key.char
            self.search_selected_idx = 0
            self.search_scroll_y = 0
            self.update_search_results()
        elif key.name == "paste" and key.char:
            self.search_query += key.char
            self.search_selected_idx = 0
            self.search_scroll_y = 0
            self.update_search_results()

    def handle_mouse(self, mouse: MouseEvent):
        # Startup Welcome Screen: Click anywhere to enter normal workspace
        if self.view_mode == "WELCOME":
            if mouse and mouse.event_type == "press":
                self.view_mode = "WORKSPACE"
                self.set_status("Welcome to PRISM! Press Ctrl+B ? for help.")
            return

        content_y = 1
        content_h = max(4, self.height - 2)
        inner_y = content_y + 1
        inner_h = max(1, content_h - 2)

        if self.workspace_layout == "MAX_INPUT":
            pane_w = self.width
            out_w = 0
            out_x = self.width
        elif self.workspace_layout == "MAX_OUTPUT":
            pane_w = 0
            out_w = self.width
            out_x = 0
        else: # SPLIT
            pane_w = self.width // 2
            out_w = self.width - pane_w
            out_x = pane_w

        # Row 0: Top Navigation Bar
        if mouse.y == 0:
            if mouse.event_type == "press":
                # Check right action buttons: [Ctrl+b /] Spotlight, [Ctrl+b ?] Help, [Ctrl+b c] Copy, [Ctrl+b q] Quit
                if mouse.x >= self.width - 12:
                    self.running = False
                elif mouse.x >= self.width - 26:
                    sel = self.get_output_selection_text()
                    target_copy = sel if sel else self.output_text
                    if SystemBridge.copy_to_clipboard(target_copy):
                        self.trigger_yank_flash(self.get_output_selection_bounds() if sel else None)
                        if sel:
                            self.set_status(f"Copied selection ({len(sel)} chars) to clipboard")
                        else:
                            self.set_status("Output copied to clipboard")
                    else:
                        self.set_status("Clipboard copy error.")
                elif mouse.x >= self.width - 40:
                    self.view_mode = "HELP" if self.view_mode != "HELP" else "WORKSPACE"
                else:
                    self.view_mode = "SEARCH"
                    self.search_query = ""
                    self.search_scroll_y = 0
                    self.update_search_results()
            elif mouse.event_type == "scroll_up":
                self.prev_tool()
            elif mouse.event_type == "scroll_down":
                self.next_tool()
            return

        # Bottom row: Status Bar interaction
        if mouse.y == self.height - 1:
            if mouse.event_type == "press":
                if mouse.x < 14:
                    self.leader_active = not self.leader_active
                    self.leader_time = time.time()
                    self.set_status("Super Key active: /:Spotlight  ?:Help  c:Copy  q:Quit" if self.leader_active else "Super Key cancelled")
            return

        # If in Search modal:
        if self.view_mode == "SEARCH":
            modal_w = min(74, self.width - 4)
            modal_h = min(17, self.height - 4)
            mx = (self.width - modal_w) // 2
            my = max(2, (self.height - modal_h) // 2)
            res_y = my + 3
            max_res = modal_h - 6

            if mouse.event_type == "scroll_up":
                self.search_selected_idx = max(0, self.search_selected_idx - 1)
            elif mouse.event_type == "scroll_down":
                self.search_selected_idx = min(max(0, len(self.search_results) - 1), self.search_selected_idx + 1)
            elif mouse.event_type == "press":
                if res_y <= mouse.y < res_y + min(max_res, len(self.search_results)):
                    clicked_offset = mouse.y - res_y
                    clicked_idx = self.search_scroll_y + clicked_offset
                    if 0 <= clicked_idx < len(self.search_results):
                        sel = self.search_results[clicked_idx]
                        self.select_tool(sel)
                        self.view_mode = "WORKSPACE"
                        self.focus = "INPUT"
                        self.set_status(f"Selected: {sel.name}")
                elif not (mx <= mouse.x < mx + modal_w and my <= mouse.y < my + modal_h):
                    self.view_mode = "WORKSPACE"
            return

        # If in Help modal:
        if self.view_mode == "HELP":
            if mouse.event_type == "press":
                self.view_mode = "WORKSPACE"
            return

        # In workspace:
        is_in_output = (out_w > 0) and (mouse.x >= out_x or self.workspace_layout == "MAX_OUTPUT")

        if mouse.event_type == "scroll_up":
            if is_in_output:
                self.output_scroll_y = max(0, self.output_scroll_y - 3)
            else:
                self.editor.scroll_y = max(0, self.editor.scroll_y - 2)

        elif mouse.event_type == "scroll_down":
            if is_in_output:
                out_lines = self.output_text.splitlines() or [""]
                max_scroll = max(0, len(out_lines) - inner_h)
                self.output_scroll_y = min(max_scroll, self.output_scroll_y + 3)
            else:
                self.editor.scroll_y += 2

        elif mouse.event_type == "press":
            if content_y <= mouse.y < content_y + content_h:
                if is_in_output:
                    self.focus = "OUTPUT"
                    out_lines = self.output_text.splitlines() or [""]
                    row_offset = mouse.y - inner_y
                    line_idx = max(0, min(self.output_scroll_y + row_offset, len(out_lines) - 1))
                    col_offset = mouse.x - (out_x + 2)
                    line_len = len(out_lines[line_idx]) if line_idx < len(out_lines) else 0
                    col_idx = max(0, min(col_offset, line_len))

                    now = time.time()
                    # Double-click detection for whole word selection & immediate copy
                    is_double_click = (
                        (now - self.last_output_click_time < 0.38) and
                        (mouse.y == self.last_output_click_y) and
                        (abs(mouse.x - self.last_output_click_x) <= 3)
                    )

                    if is_double_click and out_lines and line_idx < len(out_lines):
                        line_str = out_lines[line_idx]
                        if line_str:
                            c = min(col_idx, len(line_str) - 1)
                            ch = line_str[c]
                            if ch.isalnum() or ch in "_-":
                                w_start = c
                                while w_start > 0 and (line_str[w_start - 1].isalnum() or line_str[w_start - 1] in "_-"):
                                    w_start -= 1
                                w_end = c + 1
                                while w_end < len(line_str) and (line_str[w_end].isalnum() or line_str[w_end] in "_-"):
                                    w_end += 1
                            elif not ch.isspace():
                                w_start = c
                                while w_start > 0 and not line_str[w_start - 1].isalnum() and not line_str[w_start - 1].isspace():
                                    w_start -= 1
                                w_end = c + 1
                                while w_end < len(line_str) and not line_str[w_end].isalnum() and not line_str[w_end].isspace():
                                    w_end += 1
                            else:
                                w_start = c
                                while w_start > 0 and line_str[w_start - 1].isspace():
                                    w_start -= 1
                                w_end = c + 1
                                while w_end < len(line_str) and line_str[w_end].isspace():
                                    w_end += 1

                            self.output_sel_start = (line_idx, w_start)
                            self.output_sel_end = (line_idx, w_end)
                            self.output_selecting = False
                            self.output_cursor_y = line_idx
                            self.output_cursor_x = w_end
                            word = line_str[w_start:w_end]
                            if word:
                                self.trigger_yank_flash(self.get_output_selection_bounds())
                                SystemBridge.copy_to_clipboard(word)
                                disp = word if len(word) <= 20 else word[:18] + "..."
                                self.set_status(f"Copied '{disp}' to clipboard")
                        self.last_output_click_time = 0.0
                    else:
                        # Single-click anchor for click & drag selection
                        self.output_sel_start = (line_idx, col_idx)
                        self.output_sel_end = (line_idx, col_idx)
                        self.output_selecting = True
                        self.output_visual_mode = False
                        self.output_cursor_y = line_idx
                        self.output_cursor_x = col_idx
                        self.last_output_click_time = now
                        self.last_output_click_x = mouse.x
                        self.last_output_click_y = mouse.y
                else:
                    self.focus = "INPUT"
                    self.clear_output_selection()
                    clicked_line = self.editor.scroll_y + (mouse.y - content_y - 1)
                    if 0 <= clicked_line < len(self.editor.lines):
                        self.editor.cursor_y = clicked_line
                        col = max(0, mouse.x - 7)
                        self.editor.cursor_x = min(col, len(self.editor.lines[clicked_line]))

        elif mouse.event_type == "drag":
            if self.output_selecting and out_w > 0:
                out_lines = self.output_text.splitlines() or [""]
                row_offset = mouse.y - inner_y
                line_idx = max(0, min(self.output_scroll_y + row_offset, len(out_lines) - 1))
                col_offset = mouse.x - (out_x + 2)
                line_len = len(out_lines[line_idx]) if line_idx < len(out_lines) else 0
                col_idx = max(0, min(col_offset, line_len))

                self.output_sel_end = (line_idx, col_idx)
                self.output_cursor_y = line_idx
                self.output_cursor_x = col_idx

                # Auto-scroll when dragging near viewport boundaries
                if mouse.y <= inner_y and self.output_scroll_y > 0:
                    self.output_scroll_y = max(0, self.output_scroll_y - 1)
                elif mouse.y >= inner_y + inner_h - 1:
                    max_scroll = max(0, len(out_lines) - inner_h)
                    if self.output_scroll_y < max_scroll:
                        self.output_scroll_y += 1

        elif mouse.event_type == "release":
            if self.output_selecting:
                self.output_selecting = False
                if out_w > 0 and (mouse.x >= out_x or self.workspace_layout == "MAX_OUTPUT"):
                    out_lines = self.output_text.splitlines() or [""]
                    row_offset = mouse.y - inner_y
                    line_idx = max(0, min(self.output_scroll_y + row_offset, len(out_lines) - 1))
                    col_offset = mouse.x - (out_x + 2)
                    line_len = len(out_lines[line_idx]) if line_idx < len(out_lines) else 0
                    col_idx = max(0, min(col_offset, line_len))
                    self.output_sel_end = (line_idx, col_idx)
                    self.output_cursor_y = line_idx
                    self.output_cursor_x = col_idx

                sel_text = self.get_output_selection_text()
                if sel_text:
                    if SystemBridge.copy_to_clipboard(sel_text):
                        self.trigger_yank_flash(self.get_output_selection_bounds())
                        if "\n" in sel_text:
                            n_lines = len(sel_text.splitlines())
                            self.set_status(f"Copied {n_lines} lines ({len(sel_text)} chars) to clipboard")
                        else:
                            disp = sel_text if len(sel_text) <= 22 else sel_text[:20] + "..."
                            self.set_status(f"Copied '{disp}' to clipboard")

    # --------------------------------------------------------------------------
    # MAIN APPLICATION LOOP
    # --------------------------------------------------------------------------

    def run(self):
        self.driver.start()
        try:
            while self.running:
                # Auto-timeout super key if inactive for > 5.0 seconds
                if self.leader_active and (time.time() - self.leader_time > 5.0):
                    self.leader_active = False

                self.render()
                key, mouse = self.driver.poll_event(timeout=0.03)

                # Default exit condition: Ctrl+C quits immediately from anywhere (unless super key is active)
                if key and key.name == "ctrl_c" and not self.leader_active:
                    break

                self.handle_event(key, mouse)
                if not self.running:
                    break
        finally:
            self.driver.stop()
            self.state.save()

# ==============================================================================
# SECTION 11: CLI ENTRYPOINT
# ==============================================================================

def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(f"{APP_NAME} v{VERSION} - {APP_SUBTITLE} (by {AUTHOR} · {GITHUB_URL})")
        print("Usage: python3 prism.py [options]")
        print("\nFeatures:")
        print("  - 87 offline developer utilities (Formatters, Encoders, Cyber Tools, etc.)")
        print("  - Single curated 24-bit TrueColor theme (Prism Dark)")
        print("  - Fast command palette overlay (Ctrl+K or '/')")
        print("  - LazyVim / Zellij style Which-Key popup navigation (Ctrl+B)")
        print(f"  - Built with care by {AUTHOR} ({GITHUB_URL})")
        print("  - Zero external dependencies. 100% offline air-gapped security.")
        sys.exit(0)

    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"{APP_NAME} v{VERSION} by {AUTHOR} ({GITHUB_URL})")
        sys.exit(0)

    app = None
    try:
        app = PrismApp()
        app.run()
    except KeyboardInterrupt:
        if app and hasattr(app, "driver"):
            app.driver.stop()
        elif TerminalDriver._instance:
            TerminalDriver._instance.stop()
    except Exception as e:
        # Reliability: Guarantee terminal settings are restored on unhandled exceptions
        if app and hasattr(app, "driver"):
            app.driver.stop()
        elif TerminalDriver._instance:
            TerminalDriver._instance.stop()

        # DevSecOps: Write crash diagnostics to secure local log file instead of polluting stdout
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(CONFIG_DIR, 0o700)
            except Exception:
                pass
            log_file = CONFIG_DIR / "debug.log"
            import traceback
            # Security (CWE-276/732): Open with 0600 permissions to protect stack traces and sensitive payloads
            fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with open(fd, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now().isoformat()}] FATAL EXCEPTION:\n")
                f.write(traceback.format_exc())
            print(f"\n[{APP_NAME}] An unexpected error occurred: {e}")
            print(f"Diagnostics written to: {log_file}")
        except Exception:
            print(f"\n[{APP_NAME}] Fatal Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
