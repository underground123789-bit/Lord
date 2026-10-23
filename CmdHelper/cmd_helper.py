"""
CMD Helper - portable Windows command & error reference.

Searchable library of CMD commands and fixes for common Windows errors, plus a
"Fix my error" tab: paste any error message and it finds the error codes, shows
what Windows says they mean, lists the matching fixes, and (optionally) asks
Claude AI when the offline database has no answer.
Runs as a single portable .exe (see build.bat / GitHub Actions workflow).
Your own entries are saved in "my_commands.json" next to the program,
so the whole thing can live on a USB stick.
"""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, simpledialog, ttk
from urllib.parse import quote_plus

import ai_helper
import error_tools

APP_NAME = "CMD Helper"
ALL = "All categories"
FAVS = "★ Favorites"
MINE = "My commands"


def resource_path(name):
    """Path to a file bundled inside the exe (or next to the script)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def portable_dir():
    """Folder where the exe/script lives - user data is stored here."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


USER_FILE = os.path.join(portable_dir(), "my_commands.json")
FAV_FILE = os.path.join(portable_dir(), "favorites.json")
SETTINGS_FILE = os.path.join(portable_dir(), "settings.json")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        messagebox.showerror(APP_NAME, f"Could not save {path}:\n{e}")
        return False


def entry_key(e):
    return f"{e.get('cat', '')}|{e.get('title', '')}"


def search(entries, query):
    """Rank entries by where the query words hit (title > command > tags > text).

    Entries matching every word come first; if none match them all, entries
    matching most of the words are shown instead, so loose phrases still work.
    """
    words = query.lower().split()
    if not words:
        return list(entries)
    full, partial = [], []
    for e in entries:
        title = e.get("title", "").lower()
        cmd = e.get("cmd", "").lower()
        first = cmd.split("\n")[0][:40]
        tags = " ".join(e.get("tags", [])).lower()
        rest = " ".join([e.get("desc", ""), e.get("example", ""), e.get("cat", "")]).lower()
        score, hits = 0, 0
        for w in words:
            for field, points in ((title, 10), (first, 8), (tags, 6), (cmd, 4), (rest, 2)):
                if w in field:
                    score += points
                    hits += 1
                    break
        if hits == len(words):
            full.append((score, e))
        elif hits:
            partial.append((hits * 100 + score, e))
    scored = full or partial
    scored.sort(key=lambda s: -s[0])
    return [e for _, e in scored]


def to_one_line(command):
    """Multi-line entries are joined with & so they run one after another."""
    return " & ".join(l.strip() for l in command.splitlines()
                      if l.strip() and not l.strip().startswith("::"))


def is_script(command):
    """Batch-file snippets (labels, %%vars) can't run as a single CMD line."""
    lines = [l.strip() for l in command.splitlines()]
    return "%%" in command or any(l.startswith(":") and not l.startswith("::") for l in lines)


def run_in_cmd(command, admin=False):
    line = to_one_line(command)
    if os.name != "nt":
        messagebox.showinfo(APP_NAME, "Running commands only works on Windows.\n\n" + line)
        return
    # /s strips only the outer quotes, so the line reaches CMD exactly as written.
    args = f'/s /k "{line}"'
    if admin:
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", args, None, 1)
    else:
        subprocess.Popen("cmd.exe " + args, creationflags=subprocess.CREATE_NEW_CONSOLE)


class EntryDialog(tk.Toplevel):
    """Add / edit one of your own commands."""

    def __init__(self, master, entry=None, on_save=None):
        super().__init__(master)
        self.title("Edit command" if entry else "Add your own command")
        self.on_save = on_save
        self.transient(master)
        self.grab_set()
        entry = entry or {}
        pad = {"padx": 6, "pady": 3}
        self.vars = {}
        for row, (key, label) in enumerate([("title", "Title"), ("cat", "Category"), ("tags", "Search tags (comma separated)")]):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", **pad)
            val = entry.get(key, MINE if key == "cat" else "")
            if key == "tags":
                val = ", ".join(entry.get("tags", []))
            v = tk.StringVar(value=val)
            ttk.Entry(self, textvariable=v, width=60).grid(row=row, column=1, sticky="we", **pad)
            self.vars[key] = v
        self.admin = tk.BooleanVar(value=entry.get("admin", False))
        ttk.Checkbutton(self, text="Needs Administrator", variable=self.admin).grid(row=3, column=1, sticky="w", **pad)
        self.texts = {}
        for row, (key, label, h) in enumerate([("cmd", "Command(s)", 5), ("desc", "Description / solution", 6), ("example", "Example / notes", 3)], start=4):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="nw", **pad)
            t = tk.Text(self, width=60, height=h, wrap="word", font=("Consolas", 10))
            t.insert("1.0", entry.get(key, ""))
            t.grid(row=row, column=1, sticky="nsew", **pad)
            self.texts[key] = t
        btns = ttk.Frame(self)
        btns.grid(row=7, column=1, sticky="e", **pad)
        ttk.Button(btns, text="Save", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left")
        self.columnconfigure(1, weight=1)

    def save(self):
        title = self.vars["title"].get().strip()
        if not title:
            messagebox.showwarning(APP_NAME, "Title is required.", parent=self)
            return
        data = {
            "title": title,
            "cat": self.vars["cat"].get().strip() or MINE,
            "tags": [t.strip() for t in self.vars["tags"].get().split(",") if t.strip()],
            "admin": self.admin.get(),
            "user": True,
        }
        for key, t in self.texts.items():
            data[key] = t.get("1.0", "end").strip()
        if self.on_save:
            self.on_save(data)
        self.destroy()


def make_text(master, **kw):
    """Read-only rich text area with the tags used for entries and answers."""
    t = tk.Text(master, wrap="word", font=("Segoe UI", 10), padx=10, pady=10,
                relief="flat", background="#fbfbfb", state="disabled", **kw)
    t.tag_configure("title", font=("Segoe UI", 15, "bold"), spacing3=4)
    t.tag_configure("meta", foreground="#666666", spacing3=8)
    t.tag_configure("admin", foreground="#b00020", font=("Segoe UI", 10, "bold"))
    t.tag_configure("h", font=("Segoe UI", 11, "bold"), spacing1=10, spacing3=3)
    t.tag_configure("bold", font=("Segoe UI", 10, "bold"))
    t.tag_configure("item", font=("Segoe UI", 11, "bold"), foreground="#0b57d0", spacing1=8)
    t.tag_configure("code", font=("Consolas", 11), background="#1e1e1e",
                    foreground="#d4d4d4", lmargin1=8, lmargin2=8, rmargin=8,
                    spacing1=2, spacing3=2)
    t.tag_configure("icode", font=("Consolas", 10), background="#e8e8e8")
    t.tag_configure("link", foreground="#0b57d0", underline=True)
    t.tag_configure("ok", foreground="#1e7e34", font=("Segoe UI", 10, "bold"))
    t.tag_configure("warn", foreground="#b00020")
    t.tag_bind("link", "<Enter>", lambda e: t.configure(cursor="hand2"))
    t.tag_bind("link", "<Leave>", lambda e: t.configure(cursor=""))
    return t


class LinkMaker:
    """Creates clickable text links in a Text widget."""

    def __init__(self, text):
        self.text = text
        self.n = 0

    def insert(self, label, action):
        self.n += 1
        tag = f"lnk{self.n}"
        self.text.insert("end", label, ("link", tag))
        self.text.tag_bind(tag, "<Button-1>", lambda e: action())

    def reset(self):
        for tag in self.text.tag_names():
            if tag.startswith("lnk"):
                self.text.tag_delete(tag)
        self.n = 0


INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|`[^`\n]+`)")


def render_markdown(text, md, links, copy):
    """Insert simple Markdown (headings, **bold**, `code`, ``` blocks) into a Text widget."""
    in_code, block = False, []
    for line in md.splitlines():
        if line.strip().startswith("```"):
            if in_code:
                code = "\n".join(block)
                text.insert("end", code + "\n", "code")
                links.insert("Copy", lambda c=code: copy(c))
                text.insert("end", "\n")
                block = []
            in_code = not in_code
            continue
        if in_code:
            block.append(line)
            continue
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            text.insert("end", m.group(1) + "\n", "h")
            continue
        for part in INLINE_RE.split(line):
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                text.insert("end", part[2:-2], "bold")
            elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                text.insert("end", part[1:-1], "icode")
            else:
                text.insert("end", part)
        text.insert("end", "\n")
    if block:
        text.insert("end", "\n".join(block) + "\n", "code")


class SettingsDialog(tk.Toplevel):
    """API key / model for the optional Ask AI feature."""

    def __init__(self, master, settings, on_save):
        super().__init__(master)
        self.title("AI settings")
        self.transient(master)
        self.grab_set()
        self.on_save = on_save
        pad = {"padx": 8, "pady": 4}
        info = ("Ask AI uses Claude (Anthropic) to answer errors that are not in the offline list.\n"
                "It needs internet and an API key from console.anthropic.com (paid per use).\n"
                "The key is saved in settings.json next to this program - anyone who has\n"
                "this folder can read it, so don't share the folder with the key inside.")
        ttk.Label(self, text=info, justify="left").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(self, text="API key").grid(row=1, column=0, sticky="w", **pad)
        self.key = tk.StringVar(value=settings.get("api_key", ""))
        self.key_entry = ttk.Entry(self, textvariable=self.key, width=60, show="•")
        self.key_entry.grid(row=1, column=1, sticky="we", **pad)
        self.show = tk.BooleanVar()
        ttk.Checkbutton(self, text="Show key", variable=self.show,
                        command=lambda: self.key_entry.configure(show="" if self.show.get() else "•")
                        ).grid(row=2, column=1, sticky="w", **pad)
        ttk.Label(self, text="Model").grid(row=3, column=0, sticky="w", **pad)
        self.model = tk.StringVar(value=settings.get("model", ai_helper.DEFAULT_MODEL))
        ttk.Entry(self, textvariable=self.model, width=60).grid(row=3, column=1, sticky="we", **pad)
        btns = ttk.Frame(self)
        btns.grid(row=4, column=1, sticky="e", **pad)
        ttk.Button(btns, text="Get a key", command=lambda: webbrowser.open(
            "https://console.anthropic.com/settings/keys")).pack(side="left", padx=4)
        ttk.Button(btns, text="Save", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left")
        self.columnconfigure(1, weight=1)

    def save(self):
        self.on_save({"api_key": self.key.get().strip(),
                      "model": self.model.get().strip() or ai_helper.DEFAULT_MODEL})
        self.destroy()


class FixTab(ttk.Frame):
    """Paste an error -> codes explained, matching fixes, optional AI answer."""

    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.settings = load_json(SETTINGS_FILE, {})
        self.ai_messages = []
        self.ai_busy = False
        self.chunks = queue.Queue()

        ttk.Label(self, text="Paste or type your error message or problem "
                             "(English, Arabic or Arabizi), e.g. \"Error 0x80070643\", "
                             "\"MSVCP140.dll was not found\", \"internet ma 3am yemshi\":"
                  ).pack(anchor="w")
        self.input = tk.Text(self, height=5, wrap="word", font=("Segoe UI", 11), undo=True)
        self.input.pack(fill="x", pady=4)
        self.input.bind("<Control-Return>", lambda e: (self.find(), "break")[1])

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Find solution  (Ctrl+Enter)", command=self.find).pack(side="left")
        self.ask_btn = ttk.Button(bar, text="Ask AI", command=self.ask_ai)
        self.ask_btn.pack(side="left", padx=4)
        ttk.Button(bar, text="Search online", command=self.search_online).pack(side="left")
        ttk.Button(bar, text="Paste", command=self.paste).pack(side="left", padx=4)
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left")
        ttk.Button(bar, text="AI settings", command=self.open_settings).pack(side="right")

        out = ttk.Frame(self)
        out.pack(fill="both", expand=True)
        self.out = make_text(out)
        sb = ttk.Scrollbar(out, orient="vertical", command=self.out.yview)
        self.out.configure(yscrollcommand=sb.set)
        self.out.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.links = LinkMaker(self.out)
        self._intro()

    # ----- output helpers -----
    def _begin(self, clear=True):
        self.out.configure(state="normal")
        if clear:
            self.links.reset()
            self.out.delete("1.0", "end")

    def _end(self):
        self.out.configure(state="disabled")

    def _intro(self):
        self._begin()
        self.out.insert("end", "Fix my error\n", "title")
        self.out.insert("end",
                        "1. Paste the full error text (or a screenshot's text) above and press Find solution.\n"
                        "2. CMD Helper picks out error codes, stop codes and file names, shows what Windows "
                        "says they mean, and lists the matching fixes from its offline database.\n"
                        "3. Not found or not fixed? Press Ask AI for a step-by-step answer (needs internet "
                        "and an API key - see AI settings), or Search online.\n\n"
                        "Tip: in the Commands tab you can also paste an error into the search box.")
        self._end()

    def text(self):
        return self.input.get("1.0", "end").strip()

    def paste(self):
        try:
            self.input.insert("insert", self.clipboard_get())
        except tk.TclError:
            pass

    def clear(self):
        self.input.delete("1.0", "end")
        self.ai_messages = []
        self._intro()
        self.input.focus_set()

    def search_online(self):
        q = self.text()
        if q:
            webbrowser.open("https://www.google.com/search?q=" + quote_plus("Windows " + q[:300]))

    # ----- offline analysis -----
    def explanations(self, info):
        lines = []
        for c in info["codes"]:
            lines.append((c, error_tools.explain_code(c)))
        for n in info["numbers"]:
            lines.append((f"error {n}", error_tools.explain_number(n)))
        return lines

    def find(self):
        q = self.text()
        if not q:
            self.input.focus_set()
            return
        results, info = error_tools.rank(self.app.entries, q)
        self._begin()
        found = [x for x in (info["codes"] + info["stops"] + info["files"]
                             + [f"error {n}" for n in info["numbers"]])]
        if found:
            self.out.insert("end", "Detected: ", "h")
            self.out.insert("end", ", ".join(found) + "\n")
        expl = [(c, m) for c, m in self.explanations(info) if m]
        if expl:
            self.out.insert("end", "What Windows says:\n", "h")
            for c, m in expl:
                self.out.insert("end", f"  {c}: ", "bold")
                self.out.insert("end", m + "\n")
        if results:
            self.out.insert("end", f"\nBest matching solutions ({len(results)}):\n", "h")
            for e in results:
                self.out.insert("end", e["title"] + "\n", "item")
                if e.get("admin"):
                    self.out.insert("end", "⚠ Needs CMD as Administrator\n", "admin")
                if e.get("desc"):
                    self.out.insert("end", e["desc"] + "\n")
                if e.get("cmd"):
                    self.out.insert("end", e["cmd"] + "\n", "code")
                    self.links.insert("Copy command", lambda c=e["cmd"]: self.app.copy_text(c))
                    self.out.insert("end", "   ")
                self.links.insert("Open in Commands tab", lambda x=e: self.app.open_entry(x))
                self.out.insert("end", "\n")
        else:
            self.out.insert("end", "\nNo match in the offline database.\n", "h")
            self.out.insert("end", "Try fewer/other words, or the exact error code. ")
        self.out.insert("end", "\nNot solved? ", "bold")
        self.links.insert("Ask AI", self.ask_ai)
        self.out.insert("end", "  or  ")
        self.links.insert("Search online", self.search_online)
        self.out.insert("end", "\n")
        self._end()
        self.out.yview_moveto(0)

    # ----- AI -----
    def api_key(self):
        return self.settings.get("api_key") or ai_helper.key_from_env()

    def open_settings(self):
        def on_save(data):
            self.settings.update(data)
            save_json(SETTINGS_FILE, self.settings)
        SettingsDialog(self, self.settings, on_save)

    def ask_ai(self):
        if self.ai_busy:
            return
        q = self.text()
        if not q:
            self.input.focus_set()
            return
        if not self.api_key():
            if messagebox.askyesno(APP_NAME, "Ask AI needs an Anthropic API key.\n\nOpen AI settings now?"):
                self.open_settings()
            return
        content = q
        expl = [f"{c} = {m}" for c, m in self.explanations(error_tools.extract(q)) if m]
        if expl:
            content += "\n\n[Windows' own description of the codes: " + "; ".join(expl) + "]"
        follow_up = bool(self.ai_messages)
        self.ai_messages.append({"role": "user", "content": content})
        self._begin(clear=not follow_up)
        self.out.insert("end", "\n\nYou: " if follow_up else "You: ", "bold")
        self.out.insert("end", q + "\n\n")
        self.out.insert("end", "AI answer\n", "title")
        self.out.mark_set("ai_start", "end-1c")
        self.out.mark_gravity("ai_start", "left")
        self.out.insert("end", "Thinking…", "meta")
        self._end()
        self.out.see("end")
        self.ai_busy = True
        self.ask_btn.configure(text="Asking…")
        self.ask_btn.state(["disabled"])
        self.answer = ""
        threading.Thread(target=self._ai_worker, args=(list(self.ai_messages),), daemon=True).start()
        self.after(80, self._poll)

    def _ai_worker(self, messages):
        try:
            blocks = ai_helper.ask(self.api_key(), messages, lambda t: self.chunks.put(("text", t)),
                                   model=self.settings.get("model") or ai_helper.DEFAULT_MODEL)
            self.chunks.put(("done", blocks))
        except ai_helper.AIError as e:
            self.chunks.put(("error", str(e)))
        except Exception as e:  # never leave the UI stuck
            self.chunks.put(("error", f"Unexpected error: {e}"))

    def _poll(self):
        finished = None
        while True:
            try:
                kind, data = self.chunks.get_nowait()
            except queue.Empty:
                break
            if kind == "text":
                self.answer += data
            else:
                finished = (kind, data)
        self._begin(clear=False)
        self.out.delete("ai_start", "end-1c")
        if finished and finished[0] == "error":
            self.ai_messages.pop()  # keep the conversation valid for a retry
            self.out.insert("end", "\n" + finished[1] + "\n", "warn")
        elif finished:
            self.ai_messages.append({"role": "assistant", "content": finished[1]})
            render_markdown(self.out, self.answer, self.links, self.app.copy_text)
            self.out.insert("end", "\nAsk a follow-up: type it above and press Ask AI again "
                                   "(Clear starts a new question).\n", "meta")
        else:
            self.out.insert("end", self.answer or "Thinking…", () if self.answer else "meta")
        self._end()
        self.out.see("end")
        if finished:
            self.ai_busy = False
            self.ask_btn.configure(text="Ask AI")
            self.ask_btn.state(["!disabled"])
            if finished[0] == "done":
                self.input.delete("1.0", "end")
        else:
            self.after(80, self._poll)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - Windows commands & error fixes")
        self.geometry("1150x700")
        self.minsize(800, 500)

        self.builtin = load_json(resource_path("commands.json"), [])
        self.user = load_json(USER_FILE, [])
        self.favs = set(load_json(FAV_FILE, []))
        self.shown = []

        self._build_ui()
        self.refresh()
        self.search_entry.focus_set()

    # ---------- UI ----------
    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=24)

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(8, 2)).pack(fill="x", side="bottom")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=4, pady=4)
        lib = ttk.Frame(self.nb)
        self.nb.add(lib, text="  Commands & fixes  ")
        self.fix_tab = FixTab(self.nb, self)
        self.nb.add(self.fix_tab, text="  Fix my error  ")

        top = ttk.Frame(lib, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.refresh())
        self.search_entry = ttk.Entry(top, textvariable=self.query, font=("Segoe UI", 12))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.search_entry.bind("<Down>", lambda e: self._focus_list())
        self.search_entry.bind("<Return>", lambda e: self._focus_list())
        self.search_entry.bind("<Escape>", lambda e: self.query.set(""))
        self.cat = tk.StringVar(value=ALL)
        self.cat_box = ttk.Combobox(top, textvariable=self.cat, state="readonly", width=26)
        self.cat_box.pack(side="left", padx=4)
        self.cat_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(top, text="+ Add my own", command=self.add_entry).pack(side="left", padx=4)

        body = ttk.PanedWindow(lib, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        left = ttk.Frame(body)
        self.tree = ttk.Treeview(left, columns=("cat",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Command / problem")
        self.tree.heading("cat", text="Category")
        self.tree.column("#0", width=330)
        self.tree.column("cat", width=130)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_selected())
        self.tree.bind("<Double-1>", lambda e: self.copy_cmd())
        body.add(left, weight=2)

        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        self.detail = make_text(right)
        dsb = ttk.Scrollbar(right, orient="vertical", command=self.detail.yview)
        self.detail.configure(yscrollcommand=dsb.set)

        btns = ttk.Frame(right)
        btns.pack(side="bottom", fill="x", pady=6)
        self.btn_copy = ttk.Button(btns, text="Copy command", command=self.copy_cmd)
        self.btn_run = ttk.Button(btns, text="Run in CMD", command=lambda: self.run_cmd(False))
        self.btn_admin = ttk.Button(btns, text="Run as Admin", command=lambda: self.run_cmd(True))
        self.btn_fav = ttk.Button(btns, text="☆ Favorite", command=self.toggle_fav)
        self.btn_edit = ttk.Button(btns, text="Edit", command=self.edit_entry)
        self.btn_del = ttk.Button(btns, text="Delete", command=self.delete_entry)
        for b in (self.btn_copy, self.btn_run, self.btn_admin, self.btn_fav, self.btn_edit, self.btn_del):
            b.pack(side="left", padx=3)
        self.detail.pack(side="left", fill="both", expand=True)
        dsb.pack(side="right", fill="y")
        body.add(right, weight=3)

        self.bind("<Control-f>", lambda e: (self.search_entry.focus_set(), self.search_entry.select_range(0, "end")))
        self.bind("<Control-c>", lambda e: self.copy_cmd() if self.focus_get() == self.tree else None)
        self._set_buttons(None)

    def open_entry(self, e):
        """Show one entry in the Commands tab."""
        self.nb.select(0)
        self.cat.set(ALL)
        self.query.set(e.get("title", ""))
        for i, x in enumerate(self.shown):
            if x is e:
                self.tree.selection_set(str(i))
                self.tree.see(str(i))
                break

    def copy_text(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.set("Copied: " + text.splitlines()[0][:100])

    def _focus_list(self):
        kids = self.tree.get_children()
        if kids:
            self.tree.focus_set()
            self.tree.selection_set(kids[0])
            self.tree.focus(kids[0])

    # ---------- data ----------
    @property
    def entries(self):
        return self.builtin + self.user

    def refresh(self):
        cats = sorted({e.get("cat", "") for e in self.entries})
        self.cat_box["values"] = [ALL, FAVS] + cats
        cat = self.cat.get()
        pool = self.entries
        if cat == FAVS:
            pool = [e for e in pool if entry_key(e) in self.favs]
        elif cat != ALL:
            pool = [e for e in pool if e.get("cat") == cat]
        q = self.query.get()
        self.shown = []
        if len(q.split()) > 4 or any(error_tools.extract(q).values()):
            self.shown = error_tools.rank(pool, q, limit=60)[0]
        if not self.shown:
            self.shown = search(pool, q)
        self.tree.delete(*self.tree.get_children())
        for i, e in enumerate(self.shown):
            star = "★ " if entry_key(e) in self.favs else ""
            self.tree.insert("", "end", iid=str(i), text=star + e.get("title", ""), values=(e.get("cat", ""),))
        self.status.set(f"{len(self.shown)} of {len(self.entries)} entries   |   "
                        f"Tip: double-click = copy, Ctrl+F = search, your data: {USER_FILE}")
        if self.shown:
            self.tree.selection_set("0")
        else:
            self._render(None)

    def current(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.shown[int(sel[0])]

    def show_selected(self):
        self._render(self.current())

    def _render(self, e):
        d = self.detail
        d.configure(state="normal")
        d.delete("1.0", "end")
        if e is None:
            d.insert("end", "Nothing found.\n\n", "title")
            d.insert("end", "Try fewer or different words (e.g. \"internet\", \"wifi password\", "
                            "\"delete folder\", \"access denied\", \"blue screen\").\n"
                            "You can also add your own entry with \"+ Add my own\".")
        else:
            d.insert("end", e.get("title", "") + "\n", "title")
            d.insert("end", f"Category: {e.get('cat', '')}" + ("   (your entry)" if e.get("user") else "") + "\n", "meta")
            if e.get("admin"):
                d.insert("end", "⚠ Needs CMD as Administrator\n", "admin")
            if e.get("desc"):
                d.insert("end", "What it does / solution\n", "h")
                d.insert("end", e["desc"] + "\n")
            if e.get("cmd"):
                d.insert("end", "Command\n", "h")
                d.insert("end", e["cmd"] + "\n", "code")
            if e.get("example"):
                d.insert("end", "Examples / notes\n", "h")
                d.insert("end", e["example"] + "\n", "code")
            if e.get("tags"):
                d.insert("end", "\nTags: " + ", ".join(e["tags"]), "meta")
        d.configure(state="disabled")
        self._set_buttons(e)

    def _set_buttons(self, e):
        has_cmd = bool(e and e.get("cmd"))
        for b in (self.btn_copy, self.btn_run, self.btn_admin):
            b.state(["!disabled"] if has_cmd else ["disabled"])
        self.btn_fav.state(["!disabled"] if e else ["disabled"])
        self.btn_fav.configure(text="★ Unfavorite" if e and entry_key(e) in self.favs else "☆ Favorite")
        mine = bool(e and e.get("user"))
        self.btn_edit.state(["!disabled"] if mine else ["disabled"])
        self.btn_del.state(["!disabled"] if mine else ["disabled"])

    # ---------- actions ----------
    def copy_cmd(self):
        e = self.current()
        if not e or not e.get("cmd"):
            return
        self.copy_text(e["cmd"])

    def run_cmd(self, admin):
        e = self.current()
        if not e or not e.get("cmd"):
            return
        cmd = e["cmd"]
        if is_script(cmd):
            self.copy_cmd()
            messagebox.showinfo(APP_NAME, "This is a batch script, not a single command.\n\n"
                                          "It was copied - paste it into Notepad and save it as a .bat file.")
            return
        for ph in dict.fromkeys(re.findall(r"<[A-Za-z][^<>]*>", cmd)):
            value = simpledialog.askstring(APP_NAME, f"Enter a value for {ph}:", parent=self)
            if not value:
                return
            cmd = cmd.replace(ph, value)
        if e.get("danger") and not messagebox.askyesno(
                APP_NAME, "⚠ This command can delete data or change system settings.\n\nRun it anyway?",
                icon="warning"):
            return
        run_in_cmd(cmd, admin or e.get("admin", False))

    def toggle_fav(self):
        e = self.current()
        if not e:
            return
        k = entry_key(e)
        self.favs.symmetric_difference_update({k})
        save_json(FAV_FILE, sorted(self.favs))
        sel = self.tree.selection()
        self.refresh()
        if sel and sel[0] in self.tree.get_children():
            self.tree.selection_set(sel[0])

    def add_entry(self):
        def on_save(data):
            self.user.append(data)
            save_json(USER_FILE, self.user)
            self.query.set(data["title"])
        EntryDialog(self, on_save=on_save)

    def edit_entry(self):
        e = self.current()
        if not e or not e.get("user"):
            return
        idx = self.user.index(e)

        def on_save(data):
            self.user[idx] = data
            save_json(USER_FILE, self.user)
            self.refresh()
        EntryDialog(self, entry=e, on_save=on_save)

    def delete_entry(self):
        e = self.current()
        if not e or not e.get("user"):
            return
        if messagebox.askyesno(APP_NAME, f"Delete \"{e['title']}\"?"):
            self.user.remove(e)
            save_json(USER_FILE, self.user)
            self.refresh()


if __name__ == "__main__":
    if os.name == "nt":
        try:  # crisp text on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()
