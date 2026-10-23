# CMD Helper — portable Windows command & error reference

A small portable Windows program with **264 CMD commands and fixes for common
Windows errors**, all searchable. No install needed — one `.exe` you can keep on
a USB stick.

> **Bel 3arabe:** program portable fi kel el commands taba3 CMD w 7ellet
> el errors el mashhoura. Bta3mel search (bel English aw Arabizi metel
> "internet ma 3am yemshi", "wifi password", "blue screen") w bterja3lak el
> jaweb, w fik ta3mel copy aw run lal command direct.

## Features

- **Search** by any words: command name, problem, error code (`0x80070002`),
  error message (`access is denied`), even Arabizi (`net ma 3am yemshi`).
- **Categories**: Basics, Files & Folders, Disk & Storage, Network & Internet,
  System Info, Processes & Services, Users, Shutdown & Power, Windows Repair,
  Windows Update, Security, Errors & Fixes, Batch scripting, PowerShell,
  Quick Open (Win+R).
- **Copy command** (or double-click) / **Run in CMD** / **Run as Admin**.
  Commands with placeholders like `<WiFi name>` ask you for the value first;
  dangerous commands (delete, format…) ask for confirmation.
- **★ Favorites** and **+ Add my own** commands — saved in `my_commands.json`
  and `favorites.json` next to the exe, so they travel with it.

Shortcuts: `Ctrl+F` focus search · `Enter`/`↓` jump to results · `Esc` clear search.

## Get the .exe

**Option 1 — GitHub (no Python needed):** every push that changes `CmdHelper/`
builds the exe on a Windows machine. Open the repo's **Actions** tab →
*Build CMD Helper (Windows)* → latest run → download **CMD-Helper-portable**
(a zip containing `CMD-Helper.exe`). You can also start the build by hand with
*Run workflow*. Pushing a tag like `cmd-helper-v1.0` also publishes it as a Release.

**Option 2 — build on your PC:** install Python 3 from python.org (tick
*Add python.exe to PATH*), then double-click `build.bat`. The exe appears in
`CmdHelper\dist\CMD-Helper.exe`.

**Option 3 — run from source:** with Python installed, double-click `run.bat`.

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
