# CMD Helper — portable Windows command & error reference

A small portable Windows program with **379 CMD commands and fixes for Windows
errors** (installation, updates, blue screens, drivers, network, boot, login…),
all searchable, plus a **Fix my error** tab: paste any error message and get the
solution. No install needed — one `.exe` you can keep on a USB stick.

> **Bel 3arabe:** program portable fi kel el commands taba3 CMD w 7ellet
> el errors el mashhoura. Bta3mel search (bel English aw Arabizi metel
> "internet ma 3am yemshi", "wifi password", "blue screen") w bterja3lak el
> jaweb, w fik ta3mel copy aw run lal command direct.

## Fix my error

Paste the error text (or describe the problem, in English, Arabic or Arabizi) and press
**Find solution** (`Ctrl+Enter`):

1. Error codes are picked out of the text — `0x80070643`, `Error 1603`, `Code 43`,
   `-2147024891`, stop codes like `DPC_WATCHDOG_VIOLATION`, file names like `MSVCP140.dll`.
2. **What Windows says** — the official meaning of each code, read from Windows itself, so
   even codes that are not in the database get explained (works offline).
3. **Best matching solutions** from the offline database, with *Copy command* /
   *Open in Commands tab* links.
4. Not solved? **Ask AI** gives a step-by-step answer for *any* Windows problem, in the
   language you wrote in, and you can ask follow-ups. **Search online** opens a Google search.

### Ask AI (optional)

Uses Claude by Anthropic. It needs internet and an API key from
<https://console.anthropic.com/settings/keys> (paid per use). Put the key in **AI settings**
(or set the `ANTHROPIC_API_KEY` environment variable). The key is stored in `settings.json`
next to the exe — don't share that folder with the key inside. Everything else works
without a key or internet.

## Features

- **Search** by any words: command name, problem, error code (`0x80070002`),
  error message (`access is denied`), even Arabizi (`net ma 3am yemshi`).
- You can also paste a whole error message into the search box.
- **Categories**: Errors & Fixes, Installation Errors, Windows Install & Upgrade,
  Drivers & Device Errors (all Device Manager codes), System & Login Errors (blue
  screens, profile, PIN, activation…), Basics, Files & Folders, Disk & Storage,
  Network & Internet, System Info, Processes & Services, Users, Shutdown & Power,
  Windows Repair, Windows Update, Security, Batch scripting, PowerShell, Quick Open (Win+R).
- **Copy command** (or double-click) / **Run in CMD** / **Run as Admin**.
  Commands with placeholders like `<WiFi name>` ask you for the value first;
  dangerous commands (delete, format…) ask for confirmation.
- **★ Favorites** and **+ Add my own** commands — saved in `my_commands.json`
  and `favorites.json` next to the exe, so they travel with it.

Shortcuts: `Ctrl+F` focus search · `Enter`/`↓` jump to results · `Esc` clear search.

## Get the .exe

**Ready-made:** download [`release/CMD-Helper.exe`](release/CMD-Helper.exe) (64-bit Windows 10/11,
~20 MB, no install). Put it in any folder or on a USB stick and double-click it.
Its SHA-256 is in `release/CMD-Helper.exe.sha256`.

To build it yourself instead:

**Option 1 — GitHub (no Python needed):** every push that changes `CmdHelper/`
builds the exe on a Windows machine. Open the repo's **Actions** tab →
*Build CMD Helper (Windows)* → latest run → download **CMD-Helper-portable**
(a zip containing `CMD-Helper.exe`). You can also start the build by hand with
*Run workflow*. Pushing a tag like `cmd-helper-v1.0` also publishes it as a Release.

**Option 2 — build on your PC:** install Python 3 from python.org (tick
*Add python.exe to PATH*), then double-click `build.bat`. The exe appears in
`CmdHelper\dist\CMD-Helper.exe`.

**Option 3 — run from source:** with Python installed, double-click `run.bat`
(it installs the `anthropic` package used by Ask AI).

> Windows SmartScreen may warn about an unsigned exe the first time:
> *More info → Run anyway*.

## Adding commands to the built-in list

Built-in entries live in `commands.json` (one object per entry):

```json
{
  "cat": "Network & Internet",
  "title": "Flush DNS cache",
  "cmd": "ipconfig /flushdns",
  "desc": "What it does / how it fixes the problem",
  "example": "optional extra examples",
  "tags": ["dns", "site not loading"],
  "admin": true,
  "danger": false
}
```

Rebuild the exe after editing it. For personal entries just use **+ Add my own** in the app.
