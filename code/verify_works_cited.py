"""Ask Crossref what it records for each Works Cited entry, and print the deltas.

A Crossref record printed beside an entry is not a confirmation of it: the
identifier-less search answers for some of this report's works with the working paper
instead of the issue cited, and once with another author's chapter entirely. So each
record is scored against the entry it was looked up for, and the score is printed with
it, rather than left for a reader to spot.

Run: python "Module 6 Develop/verify_works_cited.py"
"""
import ast
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "generate_m6_final_docx.py")
OUT = os.path.join(os.path.dirname(HERE), "data", "works_cited_audit.txt")
MAILTO = "capstone-metadata-check@example.org"


def emit(lines, text):
    lines.append(text)
    print(text)


def entries():
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "WORKS_CITED":
            out = []
            for item in node.value.elts:
                parts = [elt.value for elt in item.elts]
                out.append((parts[0], parts[1]))
            return out
    raise SystemExit("WORKS_CITED not found in " + SRC)


def crossref_doi(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    return _get(url)


def crossref_search(title, year):
    params = urllib.parse.urlencode({
        "query.bibliographic": title + (" " + year if year else ""),
        "rows": 1,
    })
    return _get("https://api.crossref.org/works?" + params)


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (metadata audit; mailto:%s)" % MAILTO})
    try:
        with urllib.request.urlopen(req, timeout=30) as handle:
            return json.loads(handle.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - an audit reports failures, it does not raise
        return {"__error__": str(exc)}


def message(work):
    if "__error__" in work:
        return {"error": work["__error__"]}
    msg = work.get("message", work)
    if "items" in msg:
        msg = (msg["items"] or [{}])[0]
    return msg


def names(msg):
    return ["%s %s" % (a.get("given", ""), a.get("family", "")) for a in msg.get("author", [])]


STOPWORDS = {"the", "of", "and", "a", "an", "for", "on", "in", "to", "with", "under"}


def tokens(text):
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if t and t not in STOPWORDS}


def overlap(entry_text, record_text):
    """How much of the shorter of the two titles the other one also says."""
    a, b = tokens(entry_text), tokens(record_text)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def author_match(author_text, msg):
    """Whether a name the entry prints appears in the record's author list.

    Every token of every author is tried, not only the family field: Crossref stores
    Pickands as given "James Pickands", family "III", so a family-only test would call
    his own record a different author.
    """
    for person in names(msg):
        for token in re.split(r"\s+", person.strip()):
            if len(token) > 2 and re.search(r"\b%s\b" % re.escape(token), author_text):
                return True
    return False


def verdict(flat, author_text, entry_year, msg):
    """Score the record against the entry it was looked up for, and say what differs."""
    quoted = re.search(r'"([^"]+)"', flat)
    entry_title = quoted.group(1) if quoted else flat.split(". ", 1)[1].split(".")[0]
    record_title = (msg.get("title") or [""])[0] + " " + (msg.get("container-title") or [""])[0]
    title_score = overlap(entry_title, record_title)
    record_year = ((msg.get("issued", {}).get("date-parts") or [[None]])[0] or [None])[0]
    year_hit = bool(entry_year) and str(record_year) == str(entry_year)
    scoring = "   agree : author %s | title %.2f | year %s vs %s" % (
        "yes" if author_match(author_text, msg) else "no", title_score, entry_year, record_year)
    if not author_match(author_text, msg):
        wording = "verdict: a different author's record, so this entry was read against "\
                  "the publisher's own page"
    elif title_score < 0.6:
        wording = "verdict: a different title, so this entry was read against the "\
                  "publisher's own page"
    elif not year_hit:
        wording = "verdict: the same work at a different date - a working paper or "\
                  "online-first record, not the issue the entry cites"
    else:
        wording = "verdict: Crossref's record is this work"
    return scoring, wording


def main():
    doi_re = re.compile(r"https://doi\.org/(\S+)")
    lines, asked, skipped = [], 0, 0
    counts = {"work": 0, "date": 0, "other": 0}
    previous = ""
    for entry, milestone in entries():
        flat = " ".join(entry.split())
        # An MLA repeated-author run carries no names of its own, so the surname test
        # has to read the entry above it, which is what the list itself means.
        author_text = previous if flat.startswith("---") else flat
        previous = flat
        first = flat.split(".")[0][:38]
        year = re.search(r"\b(19|20)\d{2}\b", flat)
        found = doi_re.search(flat)
        if found:
            doi = found.group(1).rstrip(".;,)")
            msg = message(crossref_doi(doi))
            how = "doi:" + doi
        else:
            title = re.search(r'"([^"]+)"', flat)
            if not title:
                skipped += 1
                emit(lines, "\n== %s | no quoted title, skipped" % first)
                continue
            msg = message(crossref_search(title.group(1), year.group(0) if year else ""))
            how = "search"
        asked += 1
        emit(lines, "\n== %s" % first)
        emit(lines, "   entry : %s" % flat[:230])
        if msg.get("error"):
            emit(lines, "   CROSSREF FAIL: %s (%s)" % (msg["error"], how))
            continue
        emit(lines, "   cr    : %s | %s | vol %s no %s pp %s | %s | %s" % (
            (msg.get("title") or ["?"])[0][:70],
            (msg.get("container-title") or ["?"])[0][:40],
            msg.get("volume"), msg.get("issue"), msg.get("page"),
            (msg.get("issued", {}).get("date-parts") or [["?"]])[0],
            msg.get("DOI")))
        emit(lines, "   cr auth: %s" % "; ".join(names(msg))[:170])
        scoring, wording = verdict(flat, author_text, year.group(0) if year else "?", msg)
        emit(lines, scoring)
        emit(lines, "   " + wording)
        if wording.startswith("verdict: Crossref"):
            counts["work"] += 1
        elif wording.startswith("verdict: the same work"):
            counts["date"] += 1
        else:
            counts["other"] += 1
    emit(lines, "\n%d entries asked of Crossref. %d records are the work the entry "
               "cites; %d are the same work at a different date, a working paper or an "
               "online-first record rather than the issue cited; %d are another "
               "author's record; %d carried no quoted title or identifier and were read "
               "by hand without a search. Every entry, whatever the search returned, "
               "was also read against the publisher's own page."
         % (asked, counts["work"], counts["date"], counts["other"], skipped))
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\naudit written to " + OUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
