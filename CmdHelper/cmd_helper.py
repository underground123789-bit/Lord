"""
CMD Helper - portable Windows command & error reference.

Searchable library of CMD commands and fixes for common Windows errors.
Runs as a single portable .exe (see build.bat / GitHub Actions workflow).
Your own entries are saved in "my_commands.json" next to the program,
so the whole thing can live on a USB stick.
"""

import json
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

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

        top = ttk.Frame(self, padding=8)
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

        body = ttk.PanedWindow(self, orient="horizontal")
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
        self.detail = tk.Text(right, wrap="word", font=("Segoe UI", 10), padx=10, pady=10,
                              relief="flat", background="#fbfbfb", state="disabled")
        self.detail.tag_configure("title", font=("Segoe UI", 15, "bold"), spacing3=4)
        self.detail.tag_configure("meta", foreground="#666666", spacing3=8)
        self.detail.tag_configure("admin", foreground="#b00020", font=("Segoe UI", 10, "bold"))
        self.detail.tag_configure("h", font=("Segoe UI", 10, "bold"), spacing1=10, spacing3=3)
        self.detail.tag_configure("code", font=("Consolas", 11), background="#1e1e1e",
                                  foreground="#d4d4d4", lmargin1=8, lmargin2=8, rmargin=8,
                                  spacing1=2, spacing3=2)
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

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(8, 2)).pack(fill="x", side="bottom")

        self.bind("<Control-f>", lambda e: (self.search_entry.focus_set(), self.search_entry.select_range(0, "end")))
        self.bind("<Control-c>", lambda e: self.copy_cmd() if self.focus_get() == self.tree else None)
        self._set_buttons(None)

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
        self.shown = search(pool, self.query.get())
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
        self.clipboard_clear()
        self.clipboard_append(e["cmd"])
        self.status.set(f"Copied: {e['cmd'].splitlines()[0]}")

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
