[README.md](https://github.com/user-attachments/files/32925134/README.md)
<div align="center">

```text
╭─────────────────────────────────────────────────────────────────────────────╮
│                                                                             │
│    ____  ____  _________  __  ___                                           │
│   / __ \/ __ \/  _/ ___/ /  |/  /                                           │
│  / /_/ / /_/ // / \__ \ / /|_/ /                                            │
│ / ____/ _, _// / ___/ // /  / /         v1.1.0                              │
│/_/   /_/ |_/___//____//_/  /_/          by @realnishil                      │
│                                                                             │
│                   THE ELEGANT OFFLINE DEVELOPER TOOLBOX                     │
│                                                                             │
╰─────────────────────────────────────────────────────────────────────────────╯
```

### *Crafted with Cupertino precision for developers who value speed, privacy, and terminal aesthetics.*

<br/>

[![Version](https://img.shields.io/badge/version-1.1.0-34d399.svg?style=flat-square&colorA=161822&colorB=34d399)](https://github.com/realnishil/prism)
[![Python](https://img.shields.io/badge/python-3.8+-38bdf8.svg?style=flat-square&colorA=161822&colorB=38bdf8)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-a78bfa.svg?style=flat-square&colorA=161822&colorB=a78bfa)](https://github.com/realnishil/prism)
[![Privacy](https://img.shields.io/badge/privacy-100%25_air--gapped-f43f5e.svg?style=flat-square&colorA=161822&colorB=f43f5e)](https://github.com/realnishil/prism)
[![Attribution](https://img.shields.io/badge/craftsman-@realnishil-fbbf24.svg?style=flat-square&colorA=161822&colorB=fbbf24)](https://github.com/realnishil)

<br/>

[Overview](#-overview) • [Quickstart](#-quickstart) • [Tool Catalog (87)](#-the-suite-87-offline-utilities) • [Ergonomics](#-keyboard-first-ergonomics) • [Architecture](#-architecture--engine) • [Integrations](#-developer-integrations)

<br/>

---

</div>

<br/>

## Overview

**PRISM** is a unified, single-binary terminal workbench housing **87 professional utilities** in one lightning-fast environment. From instant JSON/YAML formatters and cryptographic hash crackers to JWT inspectors, cron decoders, and AST-sandboxed math engines—PRISM puts everything at your fingertips without ever leaving your terminal.

Designed with **Apple-inspired minimalism** and **Neovim/Zellij workflow ergonomics**, PRISM delivers a modern, distraction-free environment that feels as fluid and responsive as native desktop software.

<br/>

```text
  ┌── PRISM v1.1.0 ────────────────────────────────────────── @realnishil ──┐
  │                                                                         │
  │                  The Elegant Offline Developer Toolbox                  │
  │                                                                         │
  │  Ctrl+B then /            Spotlight Palette (87 Offline Tools)          │
  │  Ctrl+B then ?            Keybindings & Help Cheat Sheet                │
  │  Ctrl+B then c            Copy Output to System Clipboard               │
  │  Ctrl+B then Tab          Switch Focus (Input ↔ Output Pane)            │
  │  Ctrl+B then n / p        Next / Previous Tool (Navigate)               │
  │  Ctrl+B then ← / →        Previous / Next Category                      │
  │  Ctrl+B then x            Clear Input Editor Buffer                     │
  │  F2 / Ctrl+B z            Zoom / Toggle Workspace Layout               │
  │  Mouse Drag in Output     Select & Auto-Copy to Clipboard               │
  │  Ctrl+B then q            Quit PRISM Immediately                        │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘
```

<br/>

---

## ⚡ Highlights

| Feature | Specification | Impact |
| :--- | :--- | :--- |
| **🚀 Zero Dependencies** | Pure Python 3 standard library | No `pip install`, no virtualenvs, instant portability |
| **🔒 100% Air-Gapped** | Zero network sockets / telemetry | Tokens, keys, and private schemas never touch a server |
| **✨ Apple Aesthetics** | Single dark palette (`#0f1117`) | Clean window framing, dynamic I-beam blinking cursor (`▏`) |
| **⚡ Kinetic Physics** | Friction-damped interpolation (`0.45`) | Inertial smooth scrolling across search lists and long outputs |
| **⚡ Zip-Zap Yank Flash** | Neovim `vim.highlight.on_yank` | Tactile electric amber (`#fbbf24`) visual confirmation on copy |
| **🛡️ Hardened Security** | POSIX watchdog & AST sandbox | ReDoS abortion within 2.0s, XXE immunity, `0600` permissions |
| **⌨️ Zellij & LazyVim Flow** | Leader-key shortcuts (`Ctrl+B`) | Fast modal cards, command palette (`/`), and full mouse selection |

<br/>

---

## 🚀 Quickstart

PRISM requires nothing more than Python 3.8+ installed on your system.

### One-Line Launch
```bash
# Clone and run directly
git clone https://github.com/realnishil/prism.git
python3 prism/prism.py
```

### Shell Alias Setup
Add this to your `~/.zshrc`, `~/.bashrc`, or `~/.config/fish/config.fish`:
```bash
# Zsh / Bash
alias prism="python3 /path/to/prism.py"

# Fish
abbr -a prism 'python3 /path/to/prism.py'
```

```bash
# Check version & attribution
prism --version
# PRISM v1.1.0 by @realnishil (https://github.com/realnishil)
```

<br/>

---

## 📐 Architecture & Engine

PRISM is built from scratch without curses or third-party wrappers, giving it direct, low-latency control over the terminal emulator:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PRISM ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────────────┘

       [ Terminal Input Stream ] (Raw Mode Stdin)
                  │
                  ▼
       ┌────────────────────────┐
       │   ANSI Event Parser    │  ◄── Mouse drag selection, Leader keys, paste
       └──────────┬─────────────┘
                  │
                  ▼
       ┌────────────────────────┐
       │  Kinetic State Engine  │  ◄── Friction easing (0.45), I-beam cursor blink
       └──────────┬─────────────┘
                  │
                  ▼
       ┌────────────────────────┐
       │   Handler Core (87)    │  ◄── Pure stdlib, zero-network, air-gapped
       │   ├── AST Math Sandbox │
       │   ├── ReDoS Watchdog   │
       │   └── XXE DTD Filter   │
       └──────────┬─────────────┘
                  │
                  ▼
       ┌────────────────────────┐
       │  Differential Matrix   │  ◄── Double-buffered virtual grid (60 FPS)
       └──────────┬─────────────┘
                  │
                  ▼
       [ Terminal Output Stream ]  ◄── ANSI OSC 52 / pbcopy / xclip / wl-copy
```

<br/>

### Modal Workspace Navigation
```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MODAL WORKSPACE FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌───────────────────┐
     │   WELCOME CARD    │ ───( ↵ Enter )───┐
     │  Centered Popup   │                  │
     └───────────────────┘                  ▼
                                  ┌───────────────────┐
      ┌─────────────────────────  │  WORKSPACE SPLIT  │  ─────────────────────────┐
      │                           │  [Input] [Output] │                           │
      │                           └─────────┬─────────┘                           │
      ▼ ( Ctrl+B then / )                   │                 ▼ ( Ctrl+B then ? )
┌───────────────────┐                       │                       ┌───────────────────┐
│ SPOTLIGHT SEARCH  │                       │                       │    HELP SHEET     │
│ Fuzzy 87 Utilities│                       │                       │ Zellij Navigation │
└───────────────────┘                       ▼ ( F2 / Ctrl+B z )     └───────────────────┘
                                  ┌───────────────────┐
                                  │   ZOOMED LAYOUT   │
                                  │ Max In ⇄ Max Out  │
                                  └───────────────────┘
```

<br/>

---

## 🧰 The Suite: 87 Offline Utilities

PRISM organizes 87 essential developer utilities across 11 curated categories:

<details open>
<summary><b>✨ Formatters (8 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `fmt-json` | **JSON Formatter** | Indent, beautify, and validate JSON structures with 2-space nesting |
| `fmt-json-min` | **JSON Minifier** | Strip whitespace and minify JSON into single-line payload |
| `fmt-xml` | **XML Formatter** | Beautify XML hierarchies with automatic entity expansion protection |
| `fmt-xml-min` | **XML Minifier** | Compress XML markup into dense single-line representation |
| `fmt-yaml` | **YAML Formatter** | Clean, indent, and format multi-level YAML structures |
| `fmt-sql` | **SQL Formatter** | Indent keywords, clauses (`SELECT`, `FROM`, `WHERE`), and nested subqueries |
| `fmt-css` | **CSS Formatter** | Clean up stylesheets with structured rule indentation |
| `fmt-css-min` | **CSS Minifier** | Strip comments and collapse CSS into production bundle format |

</details>

<details>
<summary><b>🔐 Encoders & 🔓 Decoders (14 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `enc-b64` / `dec-b64` | **Base64** | Standard RFC 4648 Base64 text encoding and decoding |
| `enc-b64-url` / `dec-b64-url` | **Base64URL** | Safe URL & filename Base64 encoding without padding |
| `enc-url` / `dec-url` | **URL / Percent** | RFC 3986 percent-encoding for URI query strings |
| `enc-html` / `dec-html` | **HTML Entities** | Escape and unescape dangerous characters (`<`, `>`, `&`, `"`) |
| `enc-hex` / `dec-hex` | **Hexadecimal** | Convert UTF-8 strings into byte-level hex streams |
| `enc-bin` / `dec-bin` | **Binary 8-Bit** | Lossless 8-bit binary representation with full Unicode support |
| `enc-morse` / `dec-morse` | **Morse Code** | International Morse audio telegraphy converter |

</details>

<details>
<summary><b>🔄 Converters (14 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `conv-json-yaml` / `conv-yaml-json` | **JSON ⇄ YAML** | Bidirectional structural conversion with depth recursion protection |
| `conv-json-csv` / `conv-csv-json` | **JSON ⇄ CSV** | Tabular conversion with $O(N \cdot M)$ dynamic header aggregation |
| `conv-md-html` / `conv-html-md` | **Markdown ⇄ HTML** | XSS-escaped semantic HTML generator and reverse Markdown parser |
| `conv-case-camel` | **camelCase** | Lower camelCase identifier transformation |
| `conv-case-pascal` | **PascalCase** | Upper camelCase identifier transformation |
| `conv-case-snake` | **snake_case** | Lowercase underscored identifier formatting |
| `conv-case-kebab` | **kebab-case** | Hyphenated slug and URL transformation |
| `conv-case-constant` | **CONSTANT_CASE** | Uppercase screaming snake identifier formatting |
| `conv-case-title` | **Title Case** | Capitalize words following standard headline formatting |
| `conv-case-dot` | **dot.notation** | Period-delimited configuration key formatting |

</details>

<details>
<summary><b>🏷️ Cryptography & Hashing (10 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `hash-md5` | **MD5** | Legacy 128-bit checksum digest |
| `hash-sha1` | **SHA-1** | 160-bit cryptographic digest |
| `hash-sha256` | **SHA-256** | Standard NIST FIPS 180-4 256-bit hash |
| `hash-sha384` | **SHA-384** | High-security 384-bit cryptographic digest |
| `hash-sha512` | **SHA-512** | 512-bit industrial cryptographic digest |
| `hash-sha3-256` | **SHA3-256** | Modern Keccak permutation cryptographic digest |
| `hash-sha3-512` | **SHA3-512** | 512-bit Keccak permutation hash |
| `hash-blake2b` | **BLAKE2b** | 512-bit high-speed cryptographic digest |
| `hash-blake2s` | **BLAKE2s** | 256-bit performance-optimized digest |
| `hash-ripemd160` | **RIPEMD-160** | 160-bit European cryptographic hash (Bitcoin address standard) |

</details>

<details>
<summary><b>📝 Text Utilities (8 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `text-count` | **Word & Character Counter** | Comprehensive metrics: characters, words, lines, spaces, bytes |
| `text-diff` | **Unified Diff Viewer** | Side-by-side git-style diff comparing input sections |
| `text-dedupe` | **Line Deduplicator** | Eliminate duplicate lines while preserving chronological sequence |
| `text-sort-asc` | **Sort Alphabetical** | Natural ascending lexicographic sort |
| `text-sort-desc` | **Sort Descending** | Natural descending lexicographic sort |
| `text-slug` | **URL Slugifier** | Clean alphanumeric URL slugs stripped of special characters |
| `text-lorem` | **Lorem Ipsum Generator** | Clean sample placeholder text for interface testing |
| `text-rot13` | **ROT13 / ROT47 Cipher** | Caesar substitution cipher supporting printable ASCII range |

</details>

<details>
<summary><b>⚡ Generators (6 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `gen-uuid-v4` | **UUID v4** | Cryptographically random RFC 4122 v4 identifiers |
| `gen-pwd` | **Strong Password Generator** | High-entropy passwords with letters, numbers, and symbols |
| `gen-rsa-dummy` | **RSA Mock Keypair** | Synthetic PEM keypair for mock staging environments |
| `gen-hmac-sha256` | **HMAC-SHA256 Signer** | Keyed-hash message authentication code generator |
| `gen-nanoid` | **NanoID Generator** | Compact URL-safe unique string identifiers |
| `gen-mac` | **Random MAC Address** | Randomized locally administered unicast IEEE MAC addresses |

</details>

<details>
<summary><b>🧮 Calculators & Math (6 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `calc-eval` | **AST Expression Evaluator** | Sandboxed mathematical calculator with trigonometry, logarithms, and roots |
| `calc-pct` | **Percentage Analyzer** | Value changes, margins, discounts, and markups |
| `calc-aspect` | **Aspect Ratio Calculator** | Compute 16:9, 4:3, 21:9 dimensions and scale factors |
| `calc-px-rem` | **CSS PX to REM** | Standard 16px root font scaler with rem calculations |
| `calc-bmi` | **Body Mass Index** | Metric/Imperial BMI and health classification index |
| `calc-bitwise` | **Bitwise Operator** | Real-time `AND`, `OR`, `XOR`, `NOT`, `SHL`, `SHR` truth matrices |

</details>

<details>
<summary><b>⏱️ Date & Time (5 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `date-unix-to-human` | **Epoch to Human Date** | Parse millisecond and second timestamps into UTC, Local, and ISO 8601 |
| `date-to-unix` | **Date to Unix Epoch** | Convert calendar strings into Unix epoch seconds and milliseconds |
| `date-tz` | **Global Timezone Matrix** | Simultaneous world clocks (UTC, EST, PST, GMT, CET, IST, JST, AEST) |
| `date-cron` | **Cron Parser & Explainer** | Decode 5-field cron syntax into human English sentences |
| `date-diff` | **Date Difference Calculator** | Precise duration between two dates in days, hours, minutes, and seconds |

</details>

<details>
<summary><b>📊 Statistics & Data (4 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `stat-dataset` | **Descriptive Statistics** | Mean, median, mode, variance, standard deviation, and quartiles |
| `stat-entropy` | **Shannon Entropy** | Cryptographic randomness and compressibility metric (0.0 to 8.0 bits) |
| `stat-zscore` | **Z-Score Normalizer** | Standard deviation distance analyzer for anomaly detection |
| `stat-freq` | **Character Frequency** | Relative frequency distribution of text characters |

</details>

<details>
<summary><b>🛡️ Cyber Utilities (8 Tools)</b></summary>
<br/>

| Tool ID | Name | Description |
| :--- | :--- | :--- |
| `cyb-jwt` | **JWT Inspector** | Offline claims inspection, exp check, and `alg: "none"` security alert |
| `cyb-defang` | **URL & IP Defanger** | Safe defanging (`hxxp://`, `[.]`) for threat intelligence sharing |
| `cyb-refang` | **URL & IP Refanger** | Reconstruct defanged indicators into actionable network addresses |
| `cyb-hash-id` | **Hash Type Identifier** | Pattern match against MD5, SHA-1, SHA-256, bcrypt, and Argon2 |
| `cyb-regex` | **Regex Sandbox (ReDoS Guard)** | Test regex matches with POSIX real-time watchdog timeouts |
| `cyb-pass-strength`| **Password Strength Analyzer** | Multi-factor entropy evaluation and cracking time estimates |
| `cyb-cert-pem` | **X.509 PEM Inspector** | Extract certificates, public keys, and modulus headers |
| `cyb-crack-dict` | **Offline Dictionary Cracker** | Instant verification against known common credential digests |

</details>

<br/>

---

## ⌨️ Keyboard-First Ergonomics

PRISM is designed around muscle memory. Whether you prefer Neovim, Zellij, or tmux, navigation is instant and natural.

```text
 ╭─────────────────────────────────────────────────────────────────────────────╮
 │                         THE LEADER KEY: Ctrl+B                              │
 ╰─────────────────────────────────────────────────────────────────────────────╯
```

Press `Ctrl+B` followed by any mnemonic action:

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| `Ctrl+B` then `/` | **Spotlight Search** | Fuzzy-filter all 87 tools with live instant results |
| `Ctrl+B` then `?` | **Help Cheat Sheet** | Open interactive keybinding and navigation popup |
| `Ctrl+B` then `c` | **Copy Output** | Copy full output (or selection) with electric gold yank flash |
| `Ctrl+B` then `Tab` | **Switch Focus** | Toggle cursor between Input Editor and Output Pane |
| `Ctrl+B` then `n` / `p` | **Next / Prev Tool** | Step through tools inside the active category |
| `Ctrl+B` then `←` / `→` | **Category Switch** | Jump across the 11 utility categories |
| `Ctrl+B` then `x` | **Clear Editor** | Wipe the input buffer cleanly |
| `Ctrl+B` then `r` | **Swap Buffers** | Pipe the current output back into the input for chaining |
| `Ctrl+B` then `z` | **Zoom Layout** | Toggle between Split View, Full Input, and Full Output |
| `Ctrl+B` then `q` | **Quit** | Gracefully restore terminal and exit |

### Direct Global Hotkeys
- `Ctrl+K` or `/` (when not typing): Open Spotlight Search
- `Ctrl+Y`: Instant Yank / Copy to Clipboard
- `F1`: Toggle Help Sheet
- `F2`: Cycle Layout (Split ⇄ Max Input ⇄ Max Output)
- `Mouse Drag`: Select any text in the output pane to copy automatically

<br/>

---

## 🔌 Developer Integrations

Seamlessly weave PRISM into your personal terminal environment:

### 🪟 Tmux Floating Popup
Open PRISM as a floating window over your active Tmux pane:

```tmux
# ~/.tmux.conf
# Press prefix + P to open PRISM in floating popup
bind-key P display-popup -w 85% -h 85% -E "python3 /path/to/prism.py"
```

### 🌲 Neovim Floating Window
Add a clean floating terminal keymap in your Neovim config:

```lua
-- ~/.config/nvim/lua/plugins/prism.lua or init.lua
vim.keymap.set("n", "<leader>cp", function()
  local buf = vim.api.nvim_create_buf(false, true)
  local width = math.floor(vim.o.columns * 0.85)
  local height = math.floor(vim.o.lines * 0.85)
  local win = vim.api.nvim_open_win(buf, true, {
    relative = "editor",
    width = width,
    height = height,
    col = math.floor((vim.o.columns - width) / 2),
    row = math.floor((vim.o.lines - height) / 2),
    style = "minimal",
    border = "rounded",
  })
  vim.fn.termopen("python3 /path/to/prism.py")
  vim.cmd("startinsert")
end, { desc = "Open Prism Developer Toolbox" })
```

### ⚡ Kitty / Alacritty Terminal Hotkey
Bind a dedicated hotkey to spawn PRISM in a new window:

```conf
# ~/.config/kitty/kitty.conf
map ctrl+shift+p new_window python3 /path/to/prism.py
```

<br/>

---

## 📊 Performance Benchmarks

> **Note:** Benchmark figures are approximate and may vary depending on hardware, operating system, Python version, terminal emulator, and workload.

```text
┌─────────────────────────┬───────────────────┬───────────────────────────────┐
│ Benchmark Metric        │ PRISM v1.1.0      │ Traditional Web / Electron    │
├─────────────────────────┼───────────────────┼───────────────────────────────┤
│ Cold Startup Time       │ ~12 ms            │ ~800 ms - 2,500 ms            │
│ Memory Footprint (RSS)  │ ~14 MB            │ ~180 MB - 450 MB              │
│ Network Dependencies    │ 0 Bytes           │ Requires Internet / CDN       │
│ External Packages       │ 0 (Pure Stdlib)   │ 150+ npm / pip packages       │
│ Render Engine           │ Matrix ANSI Diff  │ Chromium DOM Tree             │
│ Telemetry / Tracking    │ 0.0% (Air-Gapped) │ Sentry / Segment / Analytics  │
└─────────────────────────┴───────────────────┴───────────────────────────────┘
```

<br/>

---

## 🛡️ Security Architecture

PRISM was engineered from day one for secure, high-stakes environments:

- **100% Air-Gapped:** Zero external HTTP requests, sockets, or telemetry.
- **AST Mathematical Sandboxing:** Math evaluations are parsed strictly into Python abstract syntax trees (`ast.parse`). Dangerous operations, built-ins, and execution primitives (`eval`, `exec`, `__import__`) are strictly disallowed.
- **Catastrophic Backtracking Guard (CWE-1333):** The regex tester uses POSIX interval timers (`ITIMER_REAL`) and thread watchdogs to abort ReDoS attacks within 2.0 seconds.
- **XXE & Billion-Laughs Defense (CWE-776):** XML formatters defensively reject `<!DOCTYPE` and `<!ENTITY>` expansions before parsing.
- **Deterministic Memory Cleanup (CWE-400):** XML DOM instances are explicitly torn down with `dom.unlink()`, eliminating cyclical memory leaks in long sessions.
- **Secure File Permissions (CWE-276/732):** State configurations in `~/.prism/` and crash diagnostics are locked to `0700` and `0600` user-only permissions.
- **Symlink Hijack Protection (CWE-59):** State loading explicitly rejects symlink traversal.

<br/>

---

## 👤 Author

Crafted with dedication by **[@realnishil](https://github.com/realnishil)**.

- **GitHub:** [https://github.com/realnishil](https://github.com/realnishil)
- **Repository:** [https://github.com/realnishil/prism](https://github.com/realnishil/prism)
- **License:** MIT

<br/>

<div align="center">
  <sub>Designed for developers who appreciate speed, aesthetics, and simplicity.</sub>
</div>
