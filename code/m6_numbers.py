"""The only place the Module 6 report gets its numbers.

Module 4's own fixes checklist records several sentences whose figures had drifted
from the code, so this module exists to make that impossible rather than to catch it
later. Two rules:

1. Nothing in `generate_m6_final_docx.py` may contain a literal measured value. It
   asks for a manifest path and this layer formats it.
2. A path that resolves to null, or that does not exist, raises at build time with
   the path in the message. A silently missing number is how a table ends up
   reporting zero for a quantity nobody computed.

`audit_document` is the backstop: it reads the finished Word document the way a
reviewer will and refuses it if a Python artefact survived into the prose.
"""

import json
from pathlib import Path
import re

# Both supported layouts put the helper one level below the analysis data:
# repository/Module 6 Develop/m6_numbers.py and archive/code/m6_numbers.py.
# Never use the working directory or Module 6 Develop/data (an old snapshot).
# A helper placed directly at the analysis root also uses that root's data/.
_MODULE_DIR = Path(__file__).resolve().parent
_DATA_ROOT = (_MODULE_DIR.parent if _MODULE_DIR.name in {"Module 6 Develop", "code"}
              else _MODULE_DIR)
MANIFEST_PATH = str(_DATA_ROOT / "data" / "module6_metrics_manifest.json")

_MISSING = object()


def _split(path):
    """`optimisation.table[2].Breach Rate (%)` -> ["optimisation", "table", 2, ...]."""
    parts = []
    for token in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        parts.append(int(token[1:-1]) if token.startswith("[") else token)
    return parts


class Numbers:
    """Dotted-path access into the manifest, with the report's formatting conventions."""

    def __init__(self, manifest=None, path=MANIFEST_PATH):
        if manifest is None:
            with open(path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        self.manifest = manifest
        self.used = []

    # ------------------------------------------------------------------ access --
    def raw(self, path, default=_MISSING):
        node = self.manifest
        for key in _split(path):
            if isinstance(node, list):
                if not isinstance(key, int) or key >= len(node):
                    if default is _MISSING:
                        raise KeyError(f"manifest path has no element: {path}")
                    return default
                node = node[key]
            elif isinstance(node, dict):
                if key not in node:
                    if default is _MISSING:
                        raise KeyError(f"manifest path does not exist: {path}")
                    return default
                node = node[key]
            else:
                if default is _MISSING:
                    raise KeyError(f"manifest path runs off a scalar: {path}")
                return default
        self.used.append(path)
        return node

    def value(self, path):
        """A value that must be there. null is a missing value, not a zero."""
        node = self.raw(path)
        if node is None:
            raise KeyError(
                f"the manifest reports null at {path}; the section that produced it "
                f"explains why in null_meanings, and the report cannot use it as a "
                f"number")
        return node

    def records(self, path):
        node = self.value(path)
        if not isinstance(node, list):
            raise TypeError(f"{path} is not a list of records")
        return node

    # ---------------------------------------------------------------- formatting --
    @staticmethod
    def number(x, dp=2):
        if x is None:
            return "n/a"
        if isinstance(x, str):
            return x
        return f"{float(x):,.{dp}f}"

    @staticmethod
    def percent(x, dp=2):
        if x is None:
            return "n/a"
        if isinstance(x, str):
            return x
        return f"{float(x):.{dp}f}%"

    @staticmethod
    def p_value(x):
        if x is None:
            return "n/a"
        x = float(x)
        if x == 0.0:
            return "< 0.0001"
        if x < 1e-3:
            return f"{x:.1e}"
        return f"{x:.4f}"

    @staticmethod
    def dollars(x, dp=2):
        if x is None:
            return "n/a"
        return f"${float(x):,.{dp}f} m"

    @staticmethod
    def signed(x, dp=2):
        if x is None:
            return "n/a"
        return f"{float(x):+.{dp}f}"

    def cell(self, x, spec):
        if x is None:
            return "n/a"
        if spec in ("p", "pc", "pv", "usd", "sg", "str", None):
            return {"p": self.number, "pc": self.percent, "pv": self.p_value,
                    "usd": self.dollars, "sg": self.signed,
                    "str": (lambda v: str(v)), None: str}[spec](x)
        if isinstance(spec, str) and "{" in spec:
            return spec.format(x)
        if callable(spec):
            return spec(x)
        return self.number(x, spec)

    def table(self, path, columns):
        """Manifest records to (headers, rows) for `add_table_data`.

        A column is (key, header, spec), where spec is a decimal count, one of the
        short names "pv" "pc" "usd" "sg" "str", a format string, or a callable that
        receives the whole record. Only "pc", "usd" and "sg" take a fourth element
        for the decimal count.
        """
        headers = [c[1] for c in columns]
        rows = []
        for record in self.records(path):
            row = []
            for key, _header, *rest in columns:
                spec = rest[0] if rest else 2
                dp = rest[1] if len(rest) > 1 else 2
                value = record.get(key) if isinstance(record, dict) else None
                if callable(spec):
                    row.append(spec(record))
                elif isinstance(spec, int):
                    row.append(self.number(value, spec))
                elif spec == "pv":
                    row.append(self.p_value(value))
                elif spec == "pc":
                    row.append(self.percent(value, dp))
                elif spec == "usd":
                    row.append(self.dollars(value, dp))
                elif spec == "sg":
                    row.append(self.signed(value, dp))
                elif spec == "str":
                    row.append("n/a" if value is None else str(value))
                else:
                    row.append(self.cell(value, spec))
            rows.append(row)
        return headers, rows


# ----------------------------------------------------------------------- audit --

ARTEFACT_PATTERNS = [
    (re.compile(r"\bnan\b", re.I), "a NaN reached the page"),
    (re.compile(r"\bNone\b"), "a Python None reached the page"),
    # Deliberately narrower than "any braces". The equations are written in the same
    # ASCII style Module 4 used, so `P_{t-1}`, `F_R^{-1}` and `^{HS}` appear on the
    # page as subscripts and superscripts. A placeholder that survived to the page
    # came from a string that should have been an f-string, and is a bare `{name}`
    # or `{name:spec}` not hanging off the end of a math token.
    (re.compile(r"(?<![_A-Za-z0-9\^])\{[A-Za-z_][A-Za-z0-9_]*(?::[^{}]*)?\}"),
     "an unformatted placeholder reached the page"),
    (re.compile(r"\bobject at 0x[0-9a-f]+\b", re.I), "a Python object repr leaked"),
    (re.compile(r"\bTrue\b|\bFalse\b"), "a Python bool was printed instead of yes/no"),
]


def _texts(container):
    for paragraph in container.paragraphs:
        yield paragraph.text
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _texts(cell)


def audit_document(doc, label="report"):
    """Refuse a finished document that still carries a Python artefact."""
    offenders = []
    for text in _texts(doc):
        if not text.strip():
            continue
        for pattern, why in ARTEFACT_PATTERNS:
            found = pattern.search(text)
            if found:
                offenders.append(f"{why}: ...{text[max(0, found.start() - 45):found.end() + 45]}...")
    if offenders:
        raise AssertionError(
            f"{label} is not clean:\n  " + "\n  ".join(sorted(set(offenders))[:12]))
    return True
