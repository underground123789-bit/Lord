"""
Error analysis helpers: pull error codes out of pasted text and explain them.

On Windows the official message for any Win32 / HRESULT / NTSTATUS code comes
straight from the system (FormatMessage), so codes that are not in our own
database still get an explanation, offline.
"""

import os
import re

# Bug check (blue screen) codes -> names, as shown in Event Viewer / minidumps.
BUGCHECKS = {
    0x0A: "IRQL_NOT_LESS_OR_EQUAL",
    0x1A: "MEMORY_MANAGEMENT",
    0x1E: "KMODE_EXCEPTION_NOT_HANDLED",
    0x24: "NTFS_FILE_SYSTEM",
    0x3B: "SYSTEM_SERVICE_EXCEPTION",
    0x50: "PAGE_FAULT_IN_NONPAGED_AREA",
    0x7A: "KERNEL_DATA_INPAGE_ERROR",
    0x7B: "INACCESSIBLE_BOOT_DEVICE",
    0x7E: "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED",
    0x7F: "UNEXPECTED_KERNEL_MODE_TRAP",
    0x9F: "DRIVER_POWER_STATE_FAILURE",
    0xA0: "INTERNAL_POWER_ERROR",
    0xC2: "BAD_POOL_CALLER",
    0xC4: "DRIVER_VERIFIER_DETECTED_VIOLATION",
    0xD1: "DRIVER_IRQL_NOT_LESS_OR_EQUAL",
    0xEF: "CRITICAL_PROCESS_DIED",
    0xF4: "CRITICAL_OBJECT_TERMINATION",
    0x101: "CLOCK_WATCHDOG_TIMEOUT",
    0x109: "CRITICAL_STRUCTURE_CORRUPTION",
    0x116: "VIDEO_TDR_FAILURE",
    0x117: "VIDEO_TDR_TIMEOUT_DETECTED",
    0x119: "VIDEO_SCHEDULER_INTERNAL_ERROR",
    0x124: "WHEA_UNCORRECTABLE_ERROR",
    0x133: "DPC_WATCHDOG_VIOLATION",
    0x139: "KERNEL_SECURITY_CHECK_FAILURE",
    0x13A: "KERNEL_MODE_HEAP_CORRUPTION",
    0x154: "UNEXPECTED_STORE_EXCEPTION",
    0x18B: "SECURE_KERNEL_ERROR",
    0x1C7: "STORE_DATA_STRUCTURE_CORRUPTION",
}

# Common crash codes (NTSTATUS), in case Windows has no text for them.
NTSTATUS = {
    0xC0000005: "Access violation - the program read or wrote memory it shouldn't",
    0xC0000017: "Not enough memory",
    0xC0000022: "Access denied",
    0xC000007B: "Invalid image format - usually a 32/64-bit DLL mismatch",
    0xC00000FD: "Stack overflow",
    0xC000012F: "Bad image - the file is not a valid Windows program or is damaged",
    0xC0000135: "A required DLL was not found (often .NET Framework)",
    0xC0000142: "A DLL failed to initialize",
    0xC0000409: "Stack buffer overrun - the program detected a crash and closed",
    0xC0000428: "Invalid image hash / digital signature",
}

# Words that carry no meaning when someone pastes a whole error message.
STOPWORDS = set("""
a an the and or of to in on at for from by with is are was were be been it this that these those
i my me you your we our they their he she his her its as if not no but so do does did done can
could would should will has have had there here what which who when where why how please help
error occurred occur message code windows window computer pc try again later click ok cancel
file program app application failed failure problem issue unable cannot can't couldn't
also because then still after before when while into same just get got keep keeps showing shows says said
something anything everything does doesn't don't won't isn't any some all one more very much
3am ma fi shi bas eza w aw ya ana enta lama kif lesh ma3 3ande 3endi bado badi bade fiye
""".split())

HEX_RE = re.compile(r"\b0x[0-9a-f]{1,8}\b", re.I)
BARE_HEX_RE = re.compile(r"\b(?:8007|8024|800f|8004|c000|c004|c190|8000|c1900|8019|8023|8073|a00f|803f)[0-9a-f]{3,4}\b", re.I)
NEG_DEC_RE = re.compile(r"(?<![\w.])-(\d{9,10})\b")
NUM_CODE_RE = re.compile(r"\b(?:error|code|err|exit code|error code)[\s:#]*(\d{1,5})\b", re.I)
STOP_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+){2,}\b")
FILE_RE = re.compile(r"\b[\w\-.]+\.(?:dll|sys|exe|msi)\b", re.I)


def extract(text):
    """Return the interesting pieces of an error message.

    {"codes": ["0x80070643", ...], "numbers": ["1603"], "stops": [...], "files": [...]}
    """
    codes = []

    def add(code):
        code = "0x%08x" % (int(code, 16) & 0xFFFFFFFF) if int(code, 16) > 0xFFFF else "0x%x" % int(code, 16)
        if code not in codes:
            codes.append(code)

    for m in HEX_RE.findall(text):
        add(m)
    for m in BARE_HEX_RE.findall(text):
        add(m)
    for m in NEG_DEC_RE.findall(text):  # e.g. -2147024891 == 0x80070005
        n = (1 << 32) - int(m)
        if 0x80000000 <= n <= 0xFFFFFFFF:
            add("%x" % n)
    stops = list(dict.fromkeys(STOP_RE.findall(text)))
    for c in codes:  # 0x0000003b in a dump -> SYSTEM_SERVICE_EXCEPTION
        name = BUGCHECKS.get(int(c, 16))
        if name and name not in stops:
            stops.append(name)
    numbers = list(dict.fromkeys(NUM_CODE_RE.findall(text)))
    files = list(dict.fromkeys(f.lower() for f in FILE_RE.findall(text)))
    return {"codes": codes, "numbers": numbers, "stops": stops, "files": files}


def keywords(text):
    """Meaningful words of a (possibly long) pasted message, for searching."""
    words = re.findall(r"[\w.\-']+", text.lower())
    out = []
    for w in words:
        w = w.strip(".-'")
        if len(w) > 2 and w not in STOPWORDS and not w.isdigit() and w not in out:
            out.append(w)
    return out


def _format_message(code, module=None):
    """Ask Windows for the official text of an error code."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    FROM_SYSTEM, FROM_HMODULE, IGNORE_INSERTS = 0x1000, 0x800, 0x200
    flags = IGNORE_INSERTS | (FROM_HMODULE if module else FROM_SYSTEM)
    handle = None
    if module:
        handle = ctypes.windll.kernel32.LoadLibraryExW(module, None, 0x2)  # LOAD_LIBRARY_AS_DATAFILE
        if not handle:
            return None
    buf = ctypes.create_unicode_buffer(2048)
    n = ctypes.windll.kernel32.FormatMessageW(flags, wintypes.HMODULE(handle) if handle else None,
                                              code & 0xFFFFFFFF, 0, buf, len(buf), None)
    if handle:
        ctypes.windll.kernel32.FreeLibrary(handle)
    return buf.value.strip() if n else None


def explain_code(code):
    """Human explanation of a hex code string like '0x80070643'. May return None."""
    n = int(code, 16)
    if n in BUGCHECKS:
        return f"Blue screen stop code {BUGCHECKS[n]}"
    parts = []
    msg = _format_message(n)
    if not msg and n & 0xFFFF0000 == 0x80070000:  # HRESULT wrapping a Win32 error
        msg = _format_message(n & 0xFFFF)
    if not msg and n & 0xF0000000 == 0xC0000000:  # NTSTATUS
        msg = _format_message(n, "ntdll.dll")
    if not msg:
        msg = NTSTATUS.get(n)
    if not msg and n & 0xFFFF0000 == 0x80240000:
        msg = _format_message(n, "wuaueng.dll") or "Windows Update agent error"
    if msg:
        parts.append(msg)
    if n & 0xFFFF0000 == 0x80070000:
        parts.append(f"(= Windows error {n & 0xFFFF})")
    return " - ".join(parts) or None


def explain_number(num):
    """Explain a plain error number like 5 or 1603 (Win32 / installer errors)."""
    n = int(num)
    return _format_message(n) if n < 20000 else None


def rank(entries, text, limit=8):
    """Best database entries for a pasted error message.

    Error codes, stop codes and file names are strong evidence; ordinary
    words only add a little, so a long message still finds the right entry.
    """
    info = extract(text)
    strong = [c.lower() for c in info["codes"]]
    strong += [c.lower() for c in info["stops"]] + info["files"] + info["numbers"]
    # Short codes like 0x3b are only matched in their long dump form (0x0000003b).
    strong = [s for s in strong if not (s.startswith("0x") and len(s) < 6)]
    words = [w for w in keywords(text) if w not in strong]
    scored = []
    for e in entries:
        title = e.get("title", "").lower()
        tags = " ".join(e.get("tags", [])).lower()
        body = " ".join([e.get("desc", ""), e.get("cmd", ""), e.get("example", "")]).lower()
        everything = title + " " + tags + " " + body
        score = 0
        for s in strong:
            if s.isdigit():  # plain numbers must match as whole words
                hit = re.search(r"\b%s\b" % s, everything)
            else:
                hit = s in everything or s.replace("0x", "") in everything
            if hit:
                score += 40 if (s in title or s in tags) else 25
        hits = 0
        for w in words:
            if w in title:
                score += 5
                hits += 1
            elif w in tags:
                score += 4
                hits += 1
            elif w in body:
                score += 1
                hits += 1
        if words and not score >= 25:
            # without a code match, demand that a good part of the words match
            if hits < max(1, min(3, len(words) // 2)):
                continue
        if score:
            scored.append((score, e))
    scored.sort(key=lambda s: -s[0])
    return [e for _, e in scored[:limit]], info
