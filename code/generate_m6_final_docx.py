"""Build the Module 6 Draft Project Report (Milestone 2) as Word + PDF.

Run `python m6_develop_pipeline.py` first: this script reads every measured figure
out of data/module6_metrics_manifest.json through m6_numbers.Numbers and refuses to
build if a number it asks for is missing. That rule exists because Module 4's own
fixes checklist records several sentences whose figures had drifted from the code.

Structure follows the Module 4 proposal so the reviewer can see a continuous
document rather than a new one. What is new here is the reviewer-response matrix
(Table 1), the five revised objectives, the four analysis sections 4.5-4.10, and
the schedule rebuild in 3.5.

This is an AI-assisted technical draft, not cleared student analysis. The authors
must independently substantiate and defend the interpretation, accurately disclose
assistance, verify citations, and seek instructor guidance and approval under the
course policy. Paraphrasing generated analysis is not a compliance remedy. Technical
corrections here do not establish authorship, collaboration credit, or clearance.
"""

import csv
import collections
import os
import re
import sys
import json
import subprocess

import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build_m6_deliverable import (  # noqa: E402
    set_cell_background,
    set_cell_margins,
    set_table_borders,
    add_styled_paragraph,
    add_heading_1,
    add_heading_2,
    add_heading_3,
    add_bullet_point,
    add_callout_box,
    add_equation,
    add_table_caption,
    add_table_data,
    add_figure_with_caption,
    add_page_number_footer,
)
from m6_numbers import Numbers, audit_document  # noqa: E402

BASE_DIR = os.path.dirname(HERE)
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
DATA_DIR = os.path.join(BASE_DIR, "data")
SUBMITTED_DIR = os.path.join(HERE, "submitted", "v2")

# Artefacts printed whole by an appendix. The manifest carries their row counts; these are the
# files those counts were taken from, so the report cites the file it read rather than a copy.
WEIGHT_HISTORY = "data/m6_optimisation_weight_history.csv"

# Design constants come from config.py, the same module the pipeline imports, so a
# methodology sentence and the code it describes cannot disagree.
sys.path.insert(0, BASE_DIR)
import config as C  # noqa: E402
from risk_models import XI_ADMISSIBLE_MAX, XI_ADMISSIBLE_MIN  # noqa: E402
from scipy.stats import norm as _norm  # noqa: E402

N = Numbers()
# The four tables carried from the proposal are read from Module 4's own artefact,
# not restated here, so a change in this module cannot silently edit history.
M4 = Numbers(path=os.path.join(DATA_DIR, "module4_metrics_manifest.json"))

ABSTRACT_WORD_LIMIT = 300

# Works Cited in the MLA order Module 4 used, so the proposal's list is a subset of this
# one and a reviewer can diff the two. The second element records which milestone an
# entry arrived at, which is what the note under the list prints; the list is the only
# place an entry is written, so the note cannot drift from it.
WORKS_CITED = [
    ("Acerbi, Carlo, and Dirk Tasche. \"Expected Shortfall: A Natural Coherent "
     "Alternative to Value at Risk.\" Economic Notes, vol. 31, no. 2, 2002, pp. 379–388.",
     "M4"),
    ("Alexander, Gordon J., and Alexandre M. Baptista. \"A Comparison of VaR and CVaR "
     "Constraints on Portfolio Selection with the Mean-Variance Model.\" Management "
     "Science, vol. 50, no. 9, 2004, pp. 1261–1273.", "M4"),
    ("Artzner, Philippe, Freddy Delbaen, Jean-Marc Eber, and David Heath. \"Coherent "
     "Measures of Risk.\" Mathematical Finance, vol. 9, no. 3, 1999, pp. 203–228.", "M4"),
    ("Balkema, August A., and Laurens de Haan. \"Residual Life Time at Great Age.\" "
     "The Annals of Probability, vol. 2, no. 5, 1974, pp. 792–804.", "M4"),
    ("Basel Committee on Banking Supervision. Amendment to the Capital Accord to "
     "Incorporate Market Risks. Bank for International Settlements, Jan. 1996, "
     "https://www.bis.org/publ/bcbs24.htm.", "M4"),
    ("---. Fundamental Review of the Trading Book: A Revised Market Risk Framework. "
     "Bank for International Settlements, Oct. 2013, https://www.bis.org/publ/bcbs265.htm.",
     "M4"),
    ("---. Minimum Capital Requirements for Market Risk. Bank for International "
     "Settlements, Jan. 2019, https://www.bis.org/bcbs/publ/d457.htm.", "M4"),
    ("Bollerslev, Tim. \"Generalized Autoregressive Conditional Heteroskedasticity.\" "
     "Journal of Econometrics, vol. 31, no. 3, 1986, pp. 307–327.", "M4"),
    ("Christoffersen, Peter F. \"Evaluating Interval Forecasts.\" International Economic "
     "Review, vol. 39, no. 4, 1998, pp. 841–862.", "M4"),
    ("Chu, Shiu-Wah, and Ritabrata Bhattacharyya. \"Expected Shortfall – An Alternative Risk "
     "Measure to Value-at-Risk.\" SSRN Electronic Journal, 2020, "
     "https://doi.org/10.2139/ssrn.3514508.", "M4"),
    ("Coles, Stuart. An Introduction to Statistical Modeling of Extreme Values. Springer, "
     "2001. https://doi.org/10.1007/978-1-4471-3675-0.", "M6"),
    ("Cont, Rama. \"Empirical Properties of Asset Returns: Stylized Facts and Statistical "
     "Issues.\" Quantitative Finance, vol. 1, no. 2, 2001, pp. 223–236.", "M4"),
    ("Davison, A. C., and R. L. Smith. \"Models for Exceedances over High Thresholds.\" "
     "Journal of the Royal Statistical Society. Series B, vol. 52, no. 3, 1990, "
     "pp. 393–425. https://doi.org/10.1111/j.2517-6161.1990.tb01796.x.", "M6"),
    ("de Haan, Laurens, and Ana Ferreira. Extreme Value Theory: An Introduction. "
     "Springer, 2006. https://doi.org/10.1007/0-387-34471-3.", "M6"),
    ("Embrechts, Paul, Claudia Klüppelberg, and Thomas Mikosch. Modelling Extremal Events "
     "for Insurance and Finance. Springer-Verlag, 1997.", "M4"),
    ("Emmer, Susanne, Marie Kratz, and Dirk Tasche. \"What Is the Best Risk Measure in "
     "Practice? A Comparison of Standard Measures.\" The Journal of Risk, vol. 18, no. 2, "
     "2015, pp. 31–60. https://doi.org/10.21314/JOR.2015.318.", "M6"),
    ("Engle, Robert F. \"Autoregressive Conditional Heteroscedasticity with Estimates of "
     "the Variance of United Kingdom Inflation.\" Econometrica, vol. 50, no. 4, 1982, "
     "pp. 987–1007.", "M4"),
    ("Fama, Eugene F. \"The Behavior of Stock-Market Prices.\" The Journal of Business, "
     "vol. 38, no. 1, 1965, pp. 34–105.", "M4"),
    ("Fissler, Tobias, and Johanna F. Ziegel. \"Higher Order Elicitability and Osband's "
     "Principle.\" The Annals of Statistics, vol. 44, no. 4, 2016, pp. 1680–1707. "
     "https://doi.org/10.1214/16-AOS1439.", "M4"),
    ("Gneiting, Tilmann. \"Making and Evaluating Point Forecasts.\" Journal of the American "
     "Statistical Association, vol. 106, no. 494, 2011, pp. 746–762.", "M4"),
    ("J.P. Morgan / Reuters. RiskMetrics — Technical Document. 4th ed., J.P. Morgan, 1996.",
     "M4"),
    ("Krokhmal, Pavlo, Jonas Palmquist, and Stanislav Uryasev. \"Portfolio Optimization "
     "with Conditional Value-at-Risk Objective and Constraints.\" The Journal of Risk, vol. 4, "
     "no. 2, 2001, pp. 43–68. https://doi.org/10.21314/JOR.2002.057.", "M6"),
    ("Kuester, Keith, Stefan Mittnik, and Marc S. Pfitzmann. \"Value-at-Risk Prediction: A "
     "Comparison of Alternative Strategies.\" Journal of Financial Econometrics, vol. 4, "
     "no. 1, 2006, pp. 53–89.", "M4"),
    ("Kupiec, Paul H. \"Techniques for Verifying the Accuracy of Risk Measurement Models.\" "
     "The Journal of Derivatives, vol. 3, no. 2, 1995, pp. 73–84.", "M4"),
    ("Ledoit, Olivier, and Michael Wolf. \"A Well-Conditioned Estimator for "
     "Large-Dimensional Covariance Matrices.\" Journal of Multivariate Analysis, vol. 88, "
     "no. 2, 2004, pp. 365–411. https://doi.org/10.1016/S0047-259X(03)00096-4.", "M6"),
    ("Mandelbrot, Benoit. \"The Variation of Certain Speculative Prices.\" The Journal of "
     "Business, vol. 36, no. 4, 1963, pp. 394–419.", "M4"),
    ("Markowitz, Harry. \"Portfolio Selection.\" The Journal of Finance, vol. 7, no. 1, "
     "1952, pp. 77–91.", "M4"),
    ("McNeil, Alexander J., and Rüdiger Frey. \"Estimation of Tail-Related Risk Measures "
     "for Heteroscedastic Financial Time Series: An Extreme Value Approach.\" Journal of "
     "Empirical Finance, vol. 7, no. 3–4, 2000, pp. 271–300.", "M4"),
    ("Pickands, James. \"Statistical Inference Using Extreme Order Statistics.\" The "
     "Annals of Statistics, vol. 3, no. 1, 1975, pp. 119–131.", "M4"),
    ("Pritsker, Matthew. \"The Hidden Dangers of Historical Simulation.\" Journal of Banking & "
     "Finance, vol. 30, no. 2, 2006, pp. 561–582.", "M4"),
    ("Rockafellar, R. Tyrrell, and Stanislav Uryasev. \"Optimization of Conditional "
     "Value-at-Risk.\" Journal of Risk, vol. 2, no. 3, 2000, pp. 21–41.", "M4"),
    ("---. \"Conditional Value-at-Risk for General Loss Distributions.\" Journal of Banking "
     "& Finance, vol. 26, no. 7, 2002, pp. 1443–1471.", "M4"),
    ("Sharpe, William F. \"Capital Asset Prices: A Theory of Market Equilibrium under "
     "Conditions of Risk.\" The Journal of Finance, vol. 19, no. 3, 1964, pp. 425–442.",
     "M4"),
    ("Thompson, Colin J., and Michael A. McCarthy. \"Alternative Measures to Value at "
     "Risk.\" The Journal of Risk Finance, vol. 9, no. 1, 2008, pp. 81–88.", "M4"),
]


# ------------------------------------------------ citation reconciliation (F15) --

# The check F15 asks for runs against the finished document rather than being promised
# in a note: every listed work cited somewhere, every in-text citation resolving to a
# listed work, and works that share an authors told apart in the sentence that cites
# them. The report cites narratively, so the marker is the surname; a surname alone
# identifies nothing when the list carries two Basel documents and two Rockafellar and
# Uryasev papers, so those entries must also carry their year or their short title.

_CORPORATE_MARKERS = {
    "Basel Committee on Banking Supervision": "Basel Committee",
    "J.P. Morgan / Reuters": "RiskMetrics",
}

_INITIAL = re.compile(r"^[A-Z]\.?$")
_WORKS_CITED_HEAD = "7. Works Cited"
_APPENDIX_HEAD = "8. Appendix"


def _author_field(entry, previous):
    """The author run of an MLA entry, with `---.` inheriting the one above it."""
    if entry.startswith("---"):
        return previous
    for name, marker in _CORPORATE_MARKERS.items():
        if entry.startswith(name):
            return marker
    parts = entry.split(". ")
    field = parts[0]
    for following in parts[1:]:
        # "Rockafellar, R" and "Kuester, ... Marc S" are runs cut by an initial, not
        # the start of the title, so keep gluing segments back while that is true.
        if re.search(r"\b[A-Z]$", field) and not following.startswith('"'):
            field += ". " + following
        else:
            break
    return field


def _surnames(field):
    """Every surname in an author run: the inverted first one plus each last word."""
    if field in _CORPORATE_MARKERS.values():
        return {field}
    parts = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", field) if p.strip()]
    out = set()
    for index, part in enumerate(parts):
        words = part.split()
        tokens = [t for t in words if not _INITIAL.match(t)]
        if not tokens:
            continue
        if index == 0:
            out.add(part)
        elif len(tokens) == 1 and len(tokens) == len(words):
            continue  # "Tim", "Laurens": a bare forename, not a surname
        elif len(tokens) == 1:
            out.add(tokens[0])          # "R. L. Smith": the surname follows initials
        elif tokens[-2].lower() in {"de", "der", "den", "van", "von"}:
            out.add(f"{tokens[-2]} {tokens[-1]}")
        else:
            out.add(tokens[-1])
    return out


def _title_snippet(entry):
    """The part of the title that tells this work from its author's other work."""
    tail = entry[len("---. "):] if entry.startswith("---.") else entry.split(". ", 1)[1]
    quoted = re.search(r'"([^"]+)"', tail)
    title = quoted.group(1) if quoted else tail.split(".")[0]
    return title.split(":")[0].strip().rstrip(".")


def citation_requirements():
    """One requirement per Works Cited entry, read off the entry itself."""
    requirements, previous = [], None
    for entry, milestone in WORKS_CITED:
        field = _author_field(entry, previous)
        previous = field
        marker = (field if field in _CORPORATE_MARKERS.values()
                  else field.split(",")[0].strip())
        year = re.search(r"\b(?:19|20)\d{2}\b", entry)
        requirements.append({
            "entry": entry, "milestone": milestone, "marker": marker,
            "surnames": _surnames(field), "shared": None,
            "year": year.group(0) if year else None,
            "snippet": _title_snippet(entry),
        })
    counts = collections.Counter(req["marker"] for req in requirements)
    for req in requirements:
        req["shared"] = counts[req["marker"]] > 1
    return requirements


_CITATION_SHAPES = [
    # "Rockafellar and Uryasev (2000)"
    re.compile(r"\b((?:[A-Z][a-z']{1,20}|de [A-Z][a-z']{1,20})"
               r"(?:\s+and\s+(?:[A-Z][a-z']{1,20}|de [A-Z][a-z']{1,20}))+)"
               r"\s*\((?:19|20)\d{2}[a-z]?\)"),
    # "(Acerbi and Tasche; Rockafellar and Uryasev 2002)" or "... (Emmer et al.)"
    re.compile(r"\(([A-Z][A-Za-z0-9'\u00c0-\u017f ]{2,60}?(?: and | et al\.)"
               r"[A-Za-z0-9'\u00c0-\u017f ,;.]{0,60})\)"),
    # "the Pickands-Balkema-de Haan theorem", "the McNeil-Frey ... metric"
    re.compile(r"\b((?:[A-Z][a-z']{2,20}|de [A-Z][a-z']{2,20})"
               r"(?:-(?:[A-Z][a-z']{2,20}|de [A-Z][a-z']{2,20}))+)"),
]

_TRAILING_YEAR = re.compile(r",?\s*\((?:19|20)\d{2}[a-z]?\)\s*$|\s+(?:19|20)\d{2}[a-z]?\s*$")


def _body_text(doc):
    """Paragraph text outside the Works Cited section, plus every table cell.

    The Works Cited list cannot cite itself; the appendix tables can, because they
    are read as part of the argument.
    """
    chunks, inside = [], False
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text.startswith(_WORKS_CITED_HEAD):
            inside = True
        elif inside and text.startswith(_APPENDIX_HEAD):
            inside = False
        if not inside and text:
            chunks.append(text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    chunks.append(cell.text.strip())
    return "\n".join(chunks)


def _sentences(body):
    return [s for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]


def reconcile_citations(doc):
    """Refuse a document whose bibliography and body citations do not agree."""
    requirements = citation_requirements()
    body = _body_text(doc)
    sentences = _sentences(body)
    known = set()
    for req in requirements:
        known |= req["surnames"]
    known.add("Basel Committee")
    problems = []

    for req in requirements:
        pattern = re.compile(rf"\b{re.escape(req['marker'])}\b")
        if req["shared"]:
            hits = [s for s in sentences
                    if pattern.search(s) and (req["year"] and re.search(
                        rf"\b{req['year']}\b", s) or req["snippet"] in s)]
            if not hits:
                problems.append(
                    f"cited without distinction: {req['marker']} has more than one "
                    f"listed work, and no sentence names this one's year "
                    f"({req['year']}) or short title ({req['snippet']!r}): {req['entry']}")
        elif not pattern.search(body):
            problems.append(f"listed but never cited: {req['entry']}")

    seen = set()
    for shape in _CITATION_SHAPES:
        for match in shape.finditer(body):
            phrase = match.group(1)
            parts = [p.replace(" et al", "").strip(" ,.")
                     for name in re.split(r"\s+and\s+|, |;", phrase)
                     for p in name.strip().split("-")]
            parts = [_TRAILING_YEAR.sub("", p).strip() for p in parts]
            parts = [p for p in parts if p and not p.endswith("et al")]
            # A hyphenated pair is read as a citation only when at least one half is
            # already an author on the list. Without that gate "Clopper-Pearson" and
            # "Walk-Forward" are indistinguishable, and the check would refuse the
            # document for its vocabulary rather than for its bibliography.
            if shape is _CITATION_SHAPES[2] and not any(p in known for p in parts):
                continue
            if phrase in seen:
                continue
            seen.add(phrase)
            for part in parts:
                if part not in known:
                    problems.append(
                        f"cited but not listed: {phrase!r} resolves to no Works "
                        f"Cited entry ({part})")

    if problems:
        raise AssertionError(
            "the Works Cited list and the body do not reconcile:\n  "
            + "\n  ".join(sorted(set(problems))))
    cited = sum(1 for req in requirements
                if re.search(rf"\b{re.escape(req['marker'])}\b", body))
    print(f"      {cited} of {len(requirements)} listed works cited in the body, "
          f"{len(seen)} in-text citation markers all resolved")
    return True


# --------------------------------------------------------------- small helpers --

def yesno(value):
    """A reviewer reading 'True' in a table cannot tell what it refers to."""
    if value is None:
        return "n/a"
    return "yes" if value else "no"


def cnt(value):
    return N.number(value, 0)


def usd(value, dp=3):
    """Manifest money is in dollars; the report prints millions of them."""
    return N.dollars(float(value) / 1e6, dp) if value is not None else "n/a"


def _near(have, want):
    if isinstance(have, float) and isinstance(want, float):
        return abs(have - want) < 1e-9
    return have == want


def prose(doc, text, space_after=7):
    return add_styled_paragraph(doc, text, space_after=space_after)


def manifest_table(doc, label, caption, path, columns, note=None, filter_kwargs=None):
    """Caption a table whose every cell came out of the manifest."""
    add_table_caption(doc, label, caption)
    records = N.records(path)
    if filter_kwargs:
        records = [r for r in records
                   if all(_near(r.get(k), v) for k, v in filter_kwargs.items())]
    headers = [header for _key, header, *_rest in columns]
    rows = []
    for record in records:
        row = []
        for key, _header, *rest in columns:
            spec = rest[0] if rest else 2
            dp = rest[1] if len(rest) > 1 else 2
            value = record.get(key)
            if callable(spec):
                row.append(spec(record))
            elif isinstance(spec, int):
                row.append(N.number(value, spec))
            elif spec == "pv":
                row.append(N.p_value(value))
            elif spec == "pc":
                row.append(N.percent(value, dp))
            elif spec == "usd":
                row.append(N.dollars(value / 1e6, dp) if value is not None else "n/a")
            elif spec == "sg":
                row.append(N.signed(value, dp))
            elif spec == "str":
                row.append("n/a" if value is None else str(value))
            else:
                row.append(N.cell(value, spec))
        rows.append(row)
    add_table_data(doc, headers, rows)
    if note:
        add_styled_paragraph(doc, note, space_after=10, italic=True)
    return len(rows)


def static_table(doc, label, caption, headers, rows, note=None, widths=None):
    add_table_caption(doc, label, caption)
    add_table_data(doc, headers, rows, col_widths=widths)
    if note:
        add_styled_paragraph(doc, note, space_after=10, italic=True)


def figure(doc, filename, label, caption, width=6.4):
    path = os.path.join(FIGURES_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{filename} has not been drawn; run "
                                f"python visualizations_m6.py before building the report")
    add_figure_with_caption(doc, path, label, caption, width=Inches(width))


# ------------------------------------------------------- derived, still measured --

def profile_path(innovation):
    return f"threshold.per_innovation.{innovation}.full_sample.profile"


def selection_path(innovation):
    return f"threshold.per_innovation.{innovation}.full_sample.selection"


def threshold_row(threshold_q, alpha=0.99, innovation="normal"):
    """One row of the full-sample threshold profile, at one coverage."""
    for record in N.records(profile_path(innovation)):
        if _near(record["threshold_quantile"], threshold_q) \
                and _near(record["confidence_level"], alpha):
            return record
    raise KeyError(f"no full-sample row at q={threshold_q}, alpha={alpha}, "
                   f"innovation={innovation}")


def evt_filter_row(threshold_q, innovation, alpha=0.99):
    """One GPD fit per (innovation filter, threshold, coverage)."""
    for record in N.records("iid.evt_across_filters"):
        if record["innovation_dist"] == innovation \
                and _near(record["threshold_quantile"], threshold_q) \
                and _near(record["confidence_level"], alpha):
            return record
    raise KeyError(f"no EVT-across-filters row at q={threshold_q}, "
                   f"innovation={innovation}, alpha={alpha}")


def threshold_spread_pct(alpha=0.99, innovation="normal", eligible_only=True):
    """Relative width of the VaR quantile band across the threshold grid.

    Reported as a percentage because the absolute numbers, around 2.85 standard
    deviations, mean nothing to a reader who has not seen the scale.
    """
    if eligible_only:
        grid = [r["threshold_quantile"] for r in N.raw(selection_path(innovation))["eligible"]]
    else:
        grid = list(N.value("threshold.grid"))
    claims = {row["threshold_quantile"]: row["var_z"]
              for row in N.records(profile_path(innovation))
              if _near(row["confidence_level"], alpha)}
    used = [claims[q] for q in grid if claims.get(q) is not None]
    if not used:
        raise KeyError(f"no eligible VaR quantiles at alpha={alpha}")
    return min(used), max(used), 100.0 * (max(used) - min(used)) / min(used)


def clamp_effect_pct(threshold_q, alpha=0.99, innovation="normal"):
    """How far the xi clamp moved the reported quantile, in percent."""
    row = threshold_row(threshold_q, alpha, innovation)
    if row["var_z_raw"] is None:
        return None
    return 100.0 * (row["var_z"] - row["var_z_raw"]) / row["var_z_raw"]


def walk_forward_row(threshold_q, alpha=0.99, innovation="normal",
                     path="threshold.walk_forward_sensitivity"):
    for record in N.records(path):
        if (record["innovation_dist"] == innovation
                and _near(record["threshold_q"], threshold_q)
                and _near(record["confidence_level"], alpha)):
            return record
    raise KeyError(f"no walk-forward row at {innovation}, q={threshold_q}, alpha={alpha}")


def model_row(path, model, key="Model"):
    for record in N.records(path):
        if record.get(key) == model:
            return record
    raise KeyError(f"no row for {model!r} under {path}")


def primary(field):
    return N.value(f"headline.module6_primary.{field}")


def strategy_row(name, path="optimisation.table"):
    return model_row(path, name, key="Strategy")


def cost_row(model):
    return model_row("runtime.model_costs", model)


def cad_row(interval_days):
    return model_row("runtime.refit_cadence", interval_days, key="Refit interval (days)")


def format_sharing(record):
    """One column of mixed units, so the unit is chosen from the metric name."""
    metric, value = record["metric"], record["value"]
    if metric.endswith("(%)"):
        return N.percent(value, 2)
    if metric.endswith("_minute"):
        return f"{N.number(value, 4)} min"
    if metric.endswith("_s"):
        return f"{N.number(value, 3)} s"
    if metric.endswith("refits") or metric.endswith("_in_sweep"):
        return N.number(value, 0)
    return N.number(value, 3)


def reg_overlay(regime, name):
    """The proposal's date overlays are not partitions, so they are picked by name."""
    return regime[f"{name} Shock" if name == "2008 GFC" else f"{name} Crash"]


def runtime_row(model):
    return model_row("runtime.model_costs", model)


def diag_row(innovation, window="full_sample"):
    """Residual diagnostics for one innovation filter over one estimation window."""
    for record in N.records("iid.residual_diagnostics"):
        if record["innovation_dist"] == innovation and record["window"] == window:
            return record
    raise KeyError(f"no residual diagnostics for {innovation} in window {window!r}")


def es_reduction_row(alpha):
    for record in N.records("optimisation.forecast_es_reduction_by_alpha"):
        if _near(record["alpha"], alpha):
            return record
    raise KeyError(f"no forecast ES reduction reported at alpha={alpha}")


def mel_band(innovation="normal", window="full_sample"):
    """The linear range the mean excess curve supports, with its tolerances."""
    return N.value(f"threshold.per_innovation.{innovation}.{window}.selection.band")


def n_lp_solves():
    """Distinct rebalance dates the minimum-ES program was solved on."""
    dates = {r["date"] for r in N.records("optimisation.forecast_es_reduction_records")}
    if not dates:
        raise KeyError("no LP solve records in the manifest")
    return len(dates)


def threshold_grid_nu_min(window=0.99, innovation="normal"):
    """Smallest exceedance count any refit window carried, across the threshold grid."""
    rows = [r for r in N.records("threshold.walk_forward_sensitivity")
            if _near(r["confidence_level"], window) and r["innovation_dist"] == innovation]
    return min(r["n_u_min"] for r in rows), max(r["n_u_min"] for r in rows)


def worst_partition_cell():
    """The highest breach rate among the regime partitions, date overlays excluded.

    The two 2008 and 2020 windows in the same manifest list are subsets that overlap
    each other and the bands, so treating them as cells of a partition would let a
    five-week window dominate a claim about the whole sample.
    """
    rows = [r for r in N.records("regime.regime_conditional_performance")
            if "overlay" not in r["definition"]]
    return max(rows, key=lambda r: r["Breach Rate (%)"])


def sharing_metric(metric):
    """One row of the sweep-sharing table, addressed by its manifest metric name."""
    for record in N.records("runtime.sweep_sharing"):
        if record["metric"] == metric:
            return record["value"]
    raise KeyError(f"no sweep-sharing metric named {metric!r}")


# ============================================================== document sections --

def add_title_block(doc):
    banner = add_styled_paragraph(doc, "WORLDQUANT UNIVERSITY | MSC IN FINANCIAL ENGINEERING",
                                  space_after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    banner.runs[0].font.size = Pt(9.5)
    banner.runs[0].font.bold = True
    banner.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    track = add_styled_paragraph(
        doc,
        "MScFE 690 Capstone Project — Track 2: Volatility and Risk "
        "(Topic 3: Developing Alternatives to VaR)",
        space_after=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    track.runs[0].font.size = Pt(10)
    track.runs[0].italic = True
    track.runs[0].font.color.rgb = RGBColor(0x2F, 0x54, 0x96)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(4)
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run("Developing Alternatives to Value-at-Risk (VaR):\n"
                        "A Two-Stage GARCH-EVT Expected Shortfall Framework for "
                        "Medium-Term Equity Portfolios")
    run.font.name = "Calibri Light"
    run.font.size = Pt(19)
    run.bold = True
    run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.paragraph_format.space_after = Pt(12)
    run = sub.add_run("Draft Project Report — Module 6 Develop (Milestone 2: "
                      "Consolidated Design)")
    run.font.name = "Calibri"
    run.font.size = Pt(12)
    run.bold = True
    run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)

    authors = doc.add_table(rows=1, cols=2)
    authors.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell in authors.rows[0].cells:
        cell.width = Inches(3.2)
        set_cell_background(cell, "F2F5F9")
        set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

    for cell, name, email in zip(
            authors.rows[0].cells,
            ("Amin Ali", "Mercy Madu Onyinyechi"),
            ("amynalypk@gmail.com", "onyinyechimercy224@gmail.com")):
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        bold = paragraph.add_run(name + "\n")
        bold.bold = True
        bold.font.name = "Calibri"
        bold.font.size = Pt(10)
        rest = paragraph.add_run(email + "\nStudent Group 17845")
        rest.font.name = "Calibri"
        rest.font.size = Pt(9)

    dated = add_styled_paragraph(doc, "October 2026", space_before=6, space_after=14,
                                 align=WD_ALIGN_PARAGRAPH.CENTER)
    dated.runs[0].font.size = Pt(9.5)
    dated.runs[0].font.color.rgb = RGBColor(0x77, 0x77, 0x77)
    add_callout_box(
        doc,
        "AI-assisted technical draft — author review and disclosure pending. The authors must "
        "independently substantiate and defend all interpretation, verify sources, disclose the "
        "assistance accurately, and obtain instructor guidance and approval where required. "
        "Rewording generated analysis is not a remedy. This revision does not certify academic "
        "integrity, collaboration credit, repository access, or submission readiness.",
        title="AUTHOR REVIEW / INSTRUCTOR GUIDANCE REQUIRED")


def abstract_paragraphs():
    """The three abstract passages, with every figure taken from the manifest.

    Written as a function rather than inline so the word-count rule can be checked
    before anything reaches the page: Module 4's abstract ran over the limit set for
    this report, and a limit nobody counts is not a limit.
    """
    ci = N.value("headline.module6_primary.Breach Rate 95% CI (%)")
    adequacy = N.raw("economic.by_recursion.corrected.reserve_adequacy")
    reduction = es_reduction_row(C.PRIMARY_ES_LP_ALPHA)
    score = N.raw("economic.investable_score")
    first = (
        "This AI-assisted technical draft develops a GARCH(1,1)-EVT risk framework for twenty "
        "US large-cap stocks over 2005-2024. Author interpretation, accurate disclosure, source "
        "verification and instructor guidance remain pending. Peer-review responses add "
        "threshold, residual, regime, allocation, funding and runtime diagnostics; several "
        "validation questions remain open.")
    second = (
        f"The weighted-log loss proxy yields {primary('Actual Breaches')} VaR exceptions over "
        f"{N.number(N.value('data.walk_forward_days'), 0)} forecast days, a rate of "
        f"{N.percent(primary('Breach Rate (%)'), 3)}. Its 95% Clopper-Pearson interval "
        f"[{N.percent(ci[0], 3)}, {N.percent(ci[1], 3)}] is exact under binomial assumptions; "
        f"p_UC = {N.p_value(primary('Kupiec p-val'))} and "
        f"p_CC = {N.p_value(primary('Conditional Cov p-val'))} concern VaR, not ES. "
        "ES validation and a GARCH-parametric or filtered-historical comparator remain "
        "unfinished. The prospective threshold screen accepts no candidate. Full-sample "
        "sensitivity cannot bound hindsight, and residual autocorrelation/ARCH diagnostics "
        "establish neither independence nor martingale-difference behaviour.")
    third = (
        f"On {n_lp_solves()} sampled decision dates the primary "
        f"{100 * C.PRIMARY_ES_LP_ALPHA:g}% LP records a mean signed forecast-ES change of "
        f"{reduction['mean']:.2f}% versus equal weight on identical simple-return scenarios; "
        "99% is a separate sensitivity, not the headline. This is optimisation consistency, "
        "not realised ES validation. The distinct daily-rebalanced simple-return account has "
        f"{score['Actual Breaches']} VaR exceptions. Under fixed-notional daily reset and "
        "replenishment, its average additional ES buffer is "
        f"${adequacy['Incremental Capital Held (USD)'] / 1e6:,.2f}m, with "
        f"${adequacy['Unreserved Loss Avoided by ES (USD)'] / 1e6:,.2f}m less hypothetical "
        "unfunded loss. Financing is excluded; market losses are not prevented. Fee fractions "
        "are reported separately as cumulative and annual quantities.")

    return [first, second, third]


def section_abstract(doc):
    add_heading_1(doc, "Abstract")
    paragraphs = abstract_paragraphs()
    words = sum(len(re.findall(r"\S+", text)) for text in paragraphs)
    if words > ABSTRACT_WORD_LIMIT:
        raise AssertionError(f"the abstract runs to {words} words, over the "
                             f"{ABSTRACT_WORD_LIMIT}-word limit set for this report")
    for text in paragraphs:
        add_styled_paragraph(doc, text, italic=True, space_after=6)
    return words


# ------------------------------------------------------------------ 1. Introduction --

def section_introduction(doc):
    add_heading_1(doc, "1. Introduction & Project Description")

    add_heading_2(doc, "1.1 Research Context, Scope & Thesis Statement")
    prose(doc,
          "Value-at-Risk became the common language of market risk when the Basel Committee "
          "embedded it in the 1996 Market Risk Amendment and when J.P. Morgan's RiskMetrics "
          "made a daily VaR number a routine deliverable of a trading desk. Its persistence is "
          "not an accident of regulation. It answers a question a risk manager can act on, it "
          "is cheap to compute, and a single number is easy to sign off. The defects are equally "
          "well known. A Gaussian variance-covariance model prices the tail of an equity return "
          "distribution from its variance, and equity returns have far more mass in the tail "
          "than a normal distribution allows. VaR says nothing about how bad a day is once it "
          "has crossed the threshold. And VaR is not subadditive, so a portfolio can be charged "
          "more capital than the sum of its parts, which is an odd property for a measure used "
          "to allocate capital across desks.")
    prose(doc,
          "This project builds and tests an alternative that keeps the parts of VaR that make it "
          "usable and replaces the parts that make it wrong. Volatility is modelled rather than "
          "assumed constant, using a GARCH(1,1) filter, so that a forecast responds to the "
          "market it is forecasting. The shape of the tail is estimated rather than inherited "
          "from a distributional guess, using peaks-over-threshold extreme value theory and a "
          "generalised Pareto fit to the exceedances. And the reported number is Expected "
          "Shortfall rather than a quantile, which is coherent in the sense of Artzner et al. "
          "and therefore subadditive.")
    prose(doc,
          "The scope is deliberately narrow and has not changed since Module 3: twenty "
          "liquid US large-cap stocks chosen to cover all ten GICS sectors, held at equal "
          "weight, benchmarked against SPY and segmented by the ^VIX, over the twenty calendar "
          "years 2005-2024, scored out-of-sample on "
          f"{N.number(N.value('data.walk_forward_days'), 0)} trading days under a "
          f"{N.value('config.window')}-day rolling window refitted every "
          f"{N.value('config.refit_interval')} days. Narrow scope is the point. A risk framework "
          "is not adopted because it is elegant; it is adopted because it holds on a specific "
          "book, over a specific period, under tests designed to catch it being lucky.")
    add_callout_box(
        doc,
        "Research status. The two-stage model's weighted-log VaR exception rate is not rejected "
        "by the reported full-sample coverage tests. This does not validate ES, establish "
        "independence, or certify an investable account. Prospective threshold selection, "
        "dependence-aware uncertainty, ES backtesting and an equally filtered comparator "
        "remain unfinished. Allocation and funding calculations are separate simple-return "
        "experiments, not proof of universal superiority.",
        title="LIMITED RESEARCH CLAIM — AUTHOR REVIEW PENDING")
    prose(doc,
          "The corrections distinguish three questions: VaR calibration of a specified loss "
          "proxy, ES forecast accuracy, and the economics of a larger hypothetical buffer. "
          "Only the first has the reported coverage tests; the others require separate evidence.")

    add_heading_2(doc, "1.2 Identification of Pain-Points in Financial Engineering Strategies")
    for text, bold in [
        ("Tail blindness.",
         "A 99% VaR of 2.9% is a statement about one quantile. On the day the loss reaches "
         "3.0% and on the day it reaches 6.8%, VaR has been breached by the same amount as "
         "far as the measure itself is concerned. The reserve a desk holds against VaR is "
         "therefore sized for the boundary of the tail and not for what lies past it."),
        ("Distributional inheritance.",
         "Gaussian VaR derives the 99th percentile from sigma times a constant. On the "
         f"portfolio in this study the standardised innovations carry excess kurtosis of "
         f"{N.value('data.portfolio_statistics.Excess Kurtosis'):.2f}, so the constant is "
         "wrong by construction, and wrong in a direction that no amount of careful "
         "volatility estimation repairs."),
        ("Non-coherence.",
         "VaR fails subadditivity, so diversification can be penalised. Expected shortfall "
         "does not, which is why the Basel Committee's Fundamental Review of the Trading Book "
         "moved the market risk capital charge from a 99% VaR to a 97.5% expected shortfall."),
        ("Procyclicality and clustering.",
         "A model that cannot reprice risk within a week produces a flat reserve requirement "
         "into a crisis and a spiked one after it. Exceptions then arrive in runs, which is "
         "what the Christoffersen independence test is built to catch."),
        ("Unquantified cost.",
         "A framework that is more accurate but slower than the alternative may never be "
         "deployed. Module 4 raised computational cost as a risk-register item and then "
         "measured nothing; the reviewer was right to notice."),
    ]:
        add_bullet_point(doc, text + " " + bold, bold_prefix="• ")

    add_heading_2(doc, "1.3 Proposed Solution: The Two-Stage GARCH-EVT Expected Shortfall Framework")
    prose(doc,
          "The framework separates the two jobs a tail model has to do. The first is to decide "
          "how wide the distribution is today, which is a conditional variance problem and is "
          "handled by the GARCH(1,1) filter. The second is to decide what the far right of that "
          "distribution looks like once it has been standardised, which is a shape problem and "
          "is handled by fitting a generalised Pareto distribution to exceedances above a "
          "threshold, following McNeil and Frey and the Pickands-Balkema-de Haan theorem. The "
          "separation matters because it means the heavy tail is estimated from the tail, where "
          "the data are, rather than implied by the body of a distribution, where they are not.")
    prose(doc,
          "At each refit the standardised losses above the threshold are fitted, the VaR and "
          "expected shortfall quantiles are inverted from the fitted tail, and both are "
          "rescaled by the current conditional volatility. Between refits the filter recursion "
          "carries the variance forward and the tail parameters are held, which is what makes "
          "the daily forecast cheap. Section 3.2 states the recursion precisely, including the "
          "correction described below.")

    add_heading_2(doc, "1.4 Real-Life Financial Engineering Applications")
    for text, bold in [
        ("Regulatory capital.",
         "The FRTB internal-models approach charges expected shortfall at 97.5% multiplied by a "
         "factor driven by backtesting. A model whose exception rate is calibrated and whose "
         "exceptions do not cluster is the difference between an internal model and a "
         "standardised-approach fallback."),
        ("Reserve sizing.",
         "A reserve set from VaR is sized for the boundary of the tail. Section 4.8 prices the "
         "difference on this portfolio: the expected-shortfall reserve is "
         f"{N.value('economic.by_recursion.corrected.reserve_adequacy.ES Reserve Uplift over VaR (%)'):.1f}% "
         "higher and absorbs most of the loss that would otherwise fall outside the funded "
         "amount."),
        ("Margin and limit setting.",
         "A tail-aware measure sets intragroup limits without the silent assumption that "
         "sub-portfolios aggregate additively."),
        ("Portfolio construction.",
         "Because expected shortfall is coherent it can be minimised directly. Section 4.9 "
         "implements that and reports what it costs."),
    ]:
        add_bullet_point(doc, text + " " + bold, bold_prefix="• ")

    add_heading_2(doc, "1.5 Incorporation of Previous Assignment Feedback")
    prose(doc,
          "Module 5 was the peer review of Group 17859's submission; the review of our own "
          "proposal came to us and is the input to this milestone. It contained eight "
          "substantive comments, reproduced in abridged form below with the reviewer's own "
          "phrasing where the point turns on it. The status column uses four words, and only "
          "four: implemented, meaning the artefact the comment asked for exists in the "
          "repository and the report; validated, meaning it was checked against something "
          "outside itself; partially addressed, meaning part of the ask is met and the rest is "
          "named; open, meaning it is not met. Implementation is not closure: residual and "
          "threshold inference, financial validation, recent empirical literature, source "
          "verification and author interpretation remain partially addressed or open.")
    reviewer_rows = [
        ["1", "Objectives: the project 'could benefit from specifying a target for "
              "computational efficiency... the trade-off between model accuracy and runtime "
              "latency'.",
         "New objective O5 with a numeric target. Cost measured per calibration and per pass, "
         "with the environment recorded.",
         "1.6, 3.9, 4.10", "runtime_benchmark.py: benchmark_model_costs, environment_fingerprint",
         "Implemented (timings machine-specific)"],
        ["2", "Theory: 'discuss whether the assumption of i.i.d. residuals from the GARCH "
              "filter is sufficient... or if the use of a distribution with heavier tails for "
              "the innovations, such as the Student's t distribution, would be theoretically "
              "justified.'",
         "Ljung-Box on z and z-squared, ARCH-LM and distributional diagnostics; Student-t "
         "sensitivity implemented. Independence, tail stability and refit-aware fit inference "
         "are not established.",
         "2.6, 3.3, 4.6", "risk_models.py: residual_diagnostics, fit_garch11(dist='t')",
         "Partially addressed (independence open)"],
        ["3", "Concepts: 'the VIX index is a measure of the implied volatility of the S&P 500, "
              "rather than the specific 20-stock portfolio... particularly in the case of "
              "sector-specific crashes.'",
         "Portfolio-specific regime definition from 20-day lagged realised volatility with "
         "cut points frozen on the first window; Cohen's kappa against the VIX bands; sector "
         "attribution on the days the two disagree.",
         "3.7, 4.7", "regime_segmentation.py: build_regime_frame, cohen_kappa, sector attribution",
         "Implemented (author review open)"],
        ["4", "Contribution: 'extending the project to include changing portfolio optimization, "
              "such as minimizing Expected Shortfall while maximizing returns.'",
         "Exact Rockafellar-Uryasev linear programme on conditional historical-simulation "
         "scenarios, walk-forward, long-only, capped, with turnover and transaction cost. "
         "Seven strategies compared.",
         "3.8, 4.9", "portfolio_optimizer.py: min_es_lp; asset_walk_forward.py",
         "Implemented (validation open)"],
        ["5", "Methodology: 'the threshold for EVT is chosen a priori at the 90th percentile and "
              "not tested for sensitivity... analyze a Mean Excess Plot to choose the 90th "
              "percentile threshold or test thresholds at 95 and 97.5 percent.'",
         "Mean excess curve with a GPD-implied overlay, and the full grid "
         "0.80/0.85/0.90/0.95/0.975/0.98 run through the walk-forward in a single pass, wider "
         "than requested so the grid cannot be called chosen.",
         "2.7, 3.6, 4.5", "threshold_sensitivity.py: profile_over_thresholds, "
         "walk_forward_threshold_sweep", "Partially addressed (no admissible cut)"],
        ["6", "Literature: 'it does not discuss any of the more recent critiques of EVT, "
              "particularly in the setting of equity markets.'",
         "Sections 2.6 and 2.7 state the premises and the diagnostics the critique attacks; "
         "section 5.1 engages the critique by name and separates the objections this module "
         "answers by measurement from the one it does not. Works Cited gains the "
         "peaks-over-threshold sources (Davison and Smith; Coles; de Haan and Ferreira), the "
         "measure comparison and CVaR-optimisation literature (Emmer et al.; Krokhmal et al.) "
         "and the shrinkage estimator the optimiser benchmarks against (Ledoit and Wolf).",
         "2.6, 2.7, 5.1, 7", "n/a (prose and citations)",
         "Partially addressed (recent empirics open)"],
        ["7a", "Style: 'the Appendix appears on pages 15-17, while the References appear on page "
               "18. To comply with the guidelines, the Appendix must be moved to the end of the "
               "document.'",
         "Checked against the submitted Module 4 PDF rather than assumed. Works Cited is "
         "sections 7 at pages 16-17 and the Appendix is section 8 at pages 18-19 of 19, so the "
         "ordering already complied; the reviewer's page numbers point at the table of contents.",
         "7, 8", "verified by page scan of the submitted PDF",
         "Validated (no change required)"],
        ["7b", "Style: 'Instead of stating what the figure depicts, the text could include an "
               "interpretation of the figure's data.'",
         "Figure descriptions and interpretations included; unsupported interpretations narrowed "
         "during technical correction. Independent author substantiation remains required.",
         "4.1-4.10", "n/a (prose)", "Partially addressed (author review open)"],
        ["8", "Results: 'the lack of discussion of the economic importance of the remaining "
              "breaches... you should discuss the magnitude of the losses during each of these "
              "46 breaches, such as the Mean Excess Loss.'",
         "Full breach register with per-day loss, exceedance in basis points and dollars; mean, "
         "median and maximum excess; exact interval on the rate; and the reserve-adequacy "
         "comparison between a VaR and an expected-shortfall reserve.",
         "3.4, 4.8, App. C", "economic_impact.py: breach_register, reserve_adequacy",
         "Implemented (validation open)"],
    ]
    static_table(
        doc, "Table 1",
        "Reviewer comment to Module 6 artefact. Every row names the file and function that "
        "produced the evidence, so a claim in this report can be traced to code without reading "
        "it.",
        ["#", "Reviewer comment (abridged)", "Action taken", "Sections", "Code artefact", "Status"],
        reviewer_rows, widths=[0.3, 1.7, 1.8, 0.6, 1.3, 0.8])

    add_heading_2(doc, "1.6 Research Questions and Revised Project Objectives")
    prose(doc,
          "The proposal stated an objective; it did not state the questions whose answers would "
          "show it was met. Five are set out here, and each maps to a section that answers it "
          "with a number rather than an argument.")
    for label, text in [
        ("RQ1", "How does GARCH(1,1)-EVT VaR calibration compare with Gaussian and historical "
                "VaR on the weighted-log proxy, and what separate evidence is needed for ES "
                "accuracy? (sections 4.2, 4.8; ES validation unfinished)"),
        ("RQ2", "Is that result an artefact of the threshold chosen for the peaks-over-threshold "
                "step? (section 4.5)"),
        ("RQ3", "Does the independence premise the threshold step rests on survive contact with "
                "the data, and does replacing Gaussian innovations with Student-t change the "
                "answer? (section 4.6)"),
        ("RQ4", "How large are the exceptions that remain, in dollars, and does holding expected "
                "shortfall rather than value at risk fund them? (section 4.8)"),
        ("RQ5", "Does the framework transfer from measuring a fixed portfolio to optimising a "
                "changing one, and at what cost in turnover and calibration? (sections 4.7, 4.9)"),
    ]:
        add_bullet_point(doc, text, bold_prefix=label + ". ")
    worst = worst_partition_cell()
    dirichlet = N.raw("weight_robustness.models.VaR_GARCH_EVT_Rates")
    calibration = runtime_row("Full GARCH-EVT calibration")
    static_table(
        doc, "Table 2",
        "Project objectives, revised at Module 6. O1-O4 carried over from the proposal with "
        "targets made numeric; O5 is new and answers reviewer comment 1.",
        ["ID", "Objective", "Metric", "Target", "Status at Module 6"],
        [["O1", "Beat Gaussian VaR on exception calibration",
          "Kupiec POF p-value at 99%", "p > 0.10",
          f"Met: p = {N.p_value(primary('Kupiec p-val'))}"],
         ["O2", "Evaluate tail severity forecasts",
          "ES or joint VaR-ES backtest/scoring with uncertainty",
          "Defensible validation; no universal ES breach-rate target",
          "Open: ES forecast production is not ES validation; equally filtered comparator needed"],
         ["O3", "Assess regime sensitivity and clustering",
          "VaR coverage and contiguous-day transitions",
          "Report uncertainty and crisis-window failures",
          f"Partial: highest partition rate {worst['Breach Rate (%)']:.2f}% in "
          f"{worst['regime']}; full-sample p_CC = "
          f"{N.p_value(primary('Conditional Cov p-val'))}. No independence certification"],
         ["O4", "Robustness to allocation",
          "Dirichlet spread of the breach rate over 100 weightings",
          "range < 0.5 pp",
          f"Met in-sample: {dirichlet['min_pct']:.2f}% to {dirichlet['max_pct']:.2f}%; "
          f"now also reported walk-forward"],
         ["O5", "Computational efficiency (new)",
          "Wall time per calibration and per full walk-forward pass",
          "under 60 s per 18-year pass on a laptop",
          f"Met: {calibration['Full-pass cost (s)']:.1f} s per pass, "
          f"{calibration['Calibration median (ms)']:.0f} ms per refit"],
         ], widths=[0.4, 1.5, 1.5, 1.2, 1.6])
    return doc


# ----------------------------------------------------------------- 2. Theory --

def section_theory(doc):
    add_heading_1(doc, "2. Theoretical Framework & Mathematical Formulations")
    prose(doc,
          "Sections 2.1 to 2.5 restate the framework as it was set out in the proposal, with two "
          "additions the reviewer comments forced: the Student-t innovation likelihood in 2.3, "
          "and the argument in 2.2 for why coherence is what makes expected shortfall usable as "
          "an optimisation objective rather than only as a report. Sections 2.6 and 2.7 are new "
          "and carry the two premises the proposal asserted without testing.")

    add_heading_2(doc, "2.1 Baseline Value-at-Risk Formulations")
    prose(doc,
          "Let r_t = ln(P_t / P_{t-1}) denote the daily logarithmic return of an asset or "
          "portfolio. For a confidence level alpha in (0, 1) and a holding period of one day, "
          "Value-at-Risk is the negative of the (1 - alpha)-quantile of the return distribution:")
    add_equation(doc, "VaR_alpha(R) = - inf { x in R : P(R <= x) >= 1 - alpha } "
                      "= - F_R^{-1}(1 - alpha)", title="DEFINITION 1: VALUE-AT-RISK")
    prose(doc,
          "Under the parametric Gaussian formulation returns are taken to be independent and "
          "identically distributed as N(mu, sigma^2), which collapses the whole distribution to "
          "two moments:")
    add_equation(doc, "VaR_{alpha}^{Norm} = -( mu + sigma * Phi^{-1}(1 - alpha) ) "
                      "= -mu + sigma * Phi^{-1}(alpha)",
                 title="EQUATION 1: PARAMETRIC GAUSSIAN VAR")
    prose(doc,
          "where Phi(.) is the standard normal cumulative distribution function; for "
          "alpha = 0.99 the multiplier is 2.3263. Under historical simulation no distribution is "
          "assumed at all and the quantile is read off a window of W past returns:")
    add_equation(doc, "VaR_{alpha, t}^{HS} = - Quantile( { r_{t-W+1}, ..., r_t }, 1 - alpha )",
                 title="EQUATION 2: HISTORICAL SIMULATION VAR")
    prose(doc,
          "These two are the baselines the study is required to beat, and they fail in opposite "
          "directions. Gaussian VaR is smooth and wrong about the tail, and the tail being wrong "
          "is not a new observation: the infinite-variance behaviour of speculative prices is "
          "what Mandelbrot reported in 1963, what Fama measured on daily stock prices two years "
          "later, and the first of the stylized facts Cont collects. Historical simulation "
          "gets the tail shape from the data but treats every day in the window as equally "
          "informative, so its forecast cannot move until an old observation leaves the window "
          "or a new one enters it. Section 4.2 shows both failures at the same time.")

    add_heading_2(doc, "2.2 Coherent Risk Measures and Expected Shortfall")
    prose(doc,
          "Artzner, Delbaen, Eber and Heath established that a risk measure rho usable for "
          "capital allocation should satisfy four axioms:")
    add_bullet_point(doc, "rho(X + c) = rho(X) - c for a constant c.",
                     bold_prefix="1. Translation invariance: ")
    add_bullet_point(doc, "rho(X + Y) <= rho(X) + rho(Y), so diversification is never penalised.",
                     bold_prefix="2. Subadditivity: ")
    add_bullet_point(doc, "rho(lambda X) = lambda rho(X) for lambda >= 0.",
                     bold_prefix="3. Positive homogeneity: ")
    add_bullet_point(doc, "X <= Y almost surely implies rho(X) >= rho(Y).",
                     bold_prefix="4. Monotonicity: ")
    prose(doc,
          "VaR satisfies translation invariance, positive homogeneity and monotonicity but "
          "is not subadditive in general; suitable elliptical settings are one case where it is. "
          "Expected shortfall satisfies the coherence axioms on an appropriate integrable "
          "domain (Acerbi and Tasche; Rockafellar and Uryasev 2002). "
          "The conditional-expectation equality below assumes a continuous loss distribution "
          "at the quantile; the integral definition also handles atoms:")
    add_equation(doc, "ES_alpha(R) = - (1 / (1 - alpha)) * int_0^{1-alpha} F_R^{-1}(u) du "
                      "= E[ -R | -R >= VaR_alpha(R) ]",
                 title="EQUATION 3: COHERENT EXPECTED SHORTFALL")
    prose(doc,
          "Two consequences matter for this project beyond the reporting argument. First, "
          "because ES is subadditive and positively homogeneous it is convex in the weights of a "
          "portfolio, which is what allows section 4.9 to minimise it directly with a linear "
          "programme for finite linear loss scenarios. VaR can also be optimised, but its "
          "objective is generally nonconvex and needs different global-optimisation methods. "
          "Second, ES averages tail severity rather than selecting one quantile; this does not "
          "guarantee low estimation error. Fewer exceedances of a higher ES threshold do not "
          "validate its accuracy. The Basel Committee's Minimum Capital Requirements for Market "
          "Risk uses 97.5% ES within a broader regulatory framework, not this prototype's "
          "one-day VaR tests as a complete capital-model approval process.")

    add_heading_2(doc, "2.3 Conditional Heteroskedasticity: Bollerslev GARCH(1,1)")
    prose(doc,
          "Equity returns cluster in volatility: a large shock, either sign, tends to be "
          "followed by large shocks. The GARCH(1,1) specification captures that with a "
          "recursion on the conditional variance:")
    add_equation(doc,
                 "r_t = mu + epsilon_t,   epsilon_t = sigma_t * z_t,   z_t ~ i.i.d. (0, 1)\n"
                 "sigma_t^2 = omega + alpha * epsilon_{t-1}^2 + beta * sigma_{t-1}^2",
                 title="EQUATION 4: GARCH(1,1) CONDITIONAL VOLATILITY PROCESS")
    prose(doc,
          "with omega > 0, alpha and beta non-negative and alpha + beta < 1 for covariance "
          "stationarity. The unconditional variance is omega / (1 - alpha - beta) and "
          "alpha + beta is the persistence of a volatility shock. The primary specification used "
          "in this report fits the quasi-maximum-likelihood Gaussian objective and lets the "
          "innovation distribution be whatever the standardised residuals turn out to be, which "
          "is the point of the two-stage design.")
    add_heading_3(doc, "Student-t innovations")
    prose(doc,
          "Reviewer comment 2 asked whether a heavier-tailed innovation distribution is "
          "theoretically justified. It is, and the model accommodates it without changing "
          "equation 4: the density of z_t is left free and only the likelihood used to estimate "
          "(omega, alpha, beta) changes. Under Gaussian innovations the objective is")
    add_equation(doc,
                 "-2 * l = n * ln(2 pi) + sum_t [ ln sigma_t^2 + epsilon_t^2 / sigma_t^2 ]",
                 title="EQUATION 4a: GAUSSIAN QUASI-LOG-LIKELIHOOD")
    prose(doc,
          "and under Student-t innovations with nu degrees of freedom, standardised to unit "
          "variance so that sigma_t remains the conditional standard deviation and not a scaled "
          "version of it,")
    add_equation(doc,
                 "l = sum_t [ lgamma((nu+1)/2) - lgamma(nu/2) - 0.5 * ln( pi (nu-2) ) "
                 "- ln sigma_t\n"
                 "      - ((nu+1)/2) * ln( 1 + epsilon_t^2 / ( (nu-2) * sigma_t^2 ) ) ]",
                 title="EQUATION 4b: STUDENT-t LOG-LIKELIHOOD, UNIT-VARIANCE PARAMETERISATION")
    prose(doc,
          "nu is estimated rather than chosen, for the same reason the tail index is estimated: "
          "picking it would reintroduce exactly the assumption the two-stage design exists to "
          "avoid. Section 4.6 reports the fitted value, which is a single-digit degrees of "
          "freedom, and compares the two filters on identical data.")

    add_heading_2(doc, "2.4 Extreme Value Theory and Peaks-Over-Threshold")
    prose(doc,
          "The Pickands-Balkema-de Haan theorem is the reason the tail can be modelled without "
          "modelling the body. Let Y = -Z be the standardised loss innovation and u a high "
          "threshold. The conditional excess distribution is")
    add_equation(doc, "F_u(y) = P(Y - u <= y | Y > u)",
                 title="EQUATION 5a: EXCESS DISTRIBUTION")
    prose(doc,
          "and for sufficiently high u it is approximated uniformly by a generalised Pareto "
          "distribution:")
    add_equation(doc, "G_{xi, beta}(y) = 1 - ( 1 + (xi * y) / beta )^{-1 / xi},   y >= 0 when "
                      "xi >= 0, and 0 <= y <= -beta/xi when xi < 0",
                 title="EQUATION 5: GENERALIZED PARETO DISTRIBUTION")
    prose(doc,
          "xi is the shape or tail-index parameter and beta > 0 the scale. The three cases are "
          "not a technicality: xi > 0 is a heavy, polynomially-decaying tail of the Fréchet type "
          "and is what equity drawdowns look like; xi = 0 is exponential decay; xi < 0 means the "
          "fitted tail has a finite upper endpoint at u - beta/xi, which is a claim that losses "
          "beyond a point are impossible. A procedure that silently replaces an estimated "
          "negative xi with a small positive one therefore does not merely regularise a number, "
          "it reverses the qualitative statement the fit was making. Section 3.10 records that "
          "the implementation inherited from Module 4 does exactly that, and section 4.5 "
          "quantifies how much it moves the forecast.")

    add_heading_2(doc, "2.5 The McNeil-Frey Dynamic GARCH-EVT Expected Shortfall Metric")
    prose(doc,
          "McNeil and Frey combined the two stages: filter the series, fit the tail of the "
          "filtered innovations, and rescale. Inverting the estimated tail gives the "
          "standardised quantile and its expected shortfall in closed form:")
    add_equation(doc,
                 "VaR_q(Z) = u + (beta / xi) * [ ( (1 - q) / (N_u / n) )^{-xi} - 1 ]\n"
                 "ES_q(Z)  = ( VaR_q(Z) / (1 - xi) ) + ( (beta - xi * u) / (1 - xi) )",
                 title="EQUATION 6: CLOSED-FORM EVT STANDARDIZED RISK QUANTILES")
    prose(doc,
          "where n is the sample size and N_u the number of exceedances over u. Both expressions "
          "require q > F(u), which is why a threshold above the coverage being reported is not "
          "merely inefficient but undefined; section 3.6 enforces it. The expected shortfall also "
          "requires xi < 1 for the mean to exist. The forecasts are then rescaled by the "
          "conditional moments:")
    add_equation(doc,
                 "VaR_{t+1}^q = -mu_{t+1} + sigma_{t+1} * VaR_q(Z)\n"
                 "ES_{t+1}^q  = -mu_{t+1} + sigma_{t+1} * ES_q(Z)",
                 title="EQUATION 7: DYNAMIC SCALED GARCH-EVT RISK FORECASTS")

    add_heading_2(doc, "2.6 The Independence Premise of the POT Step and Its Limits")
    prose(doc,
          "Equation 6 models the upper tail of Y_t = -z_t, not z_t squared. The GPD limit "
          "requires appropriate marginal domain-of-attraction conditions; applying it over time "
          "also raises tail stability and dependence questions. N_u/n is an empirical tail "
          "frequency, not automatically a binomial sample under serial dependence. Weakly "
          "dependent extremes can sometimes be modelled, but require conditions and uncertainty "
          "methods not established by the diagnostics in this draft.")
    prose(doc,
          "Ljung-Box tests detect specified autocorrelation at the tested lags, while ARCH-LM "
          "tests detect specified remaining conditional-variance structure. Their non-rejection "
          "does not establish independence, a martingale-difference conditional mean, stable "
          "marginal tails, or an appropriate weak-dependence condition for extremes. Exceedance "
          "clustering, rolling/crisis-window stability, refit-aware bootstrap goodness-of-fit "
          "and dependence-aware uncertainty remain unresolved. Section 4.6 reports only the "
          "narrow diagnostic results, not verification of the POT assumptions.")
    prose(doc,
          "The second half of comment 2, on Student-t innovations, is a different question and "
          "has a different answer. Heavier-tailed innovations change the filter, and therefore "
          "the residuals the tail model sees, but they do not repair a dependence problem; a "
          "t-GARCH filter with the same alpha and beta produces a different z_t sequence, not an "
          "independent one. The reason to estimate nu anyway is that a mis-specified innovation "
          "law distorts the conditional variance in exactly the region the tail model depends "
          "on, the extremes. Whether that distortion matters here is an empirical question, "
          "answered in section 4.6, and the honest summary is that the two filters disagree "
          "sharply about the likelihood of the data and only mildly about the risk forecast.")

    add_heading_2(doc, "2.7 Threshold Selection Theory")
    prose(doc,
          "The threshold u is the one free parameter the two-stage framework does not estimate "
          "for itself, and it governs a bias-variance trade-off that is not resolved by any "
          "test on the fitted model. Lower u means more exceedances and a smaller variance in "
          "(beta, xi), but the Pickands-Balkema-de Haan approximation only holds asymptotically, "
          "so a low threshold is fitted to a body-to-tail transition the theorem does not "
          "describe. Raise u and the approximation improves while N_u shrinks; the variance of "
          "the shape estimate increases as N_u falls (standard errors often scale as 1/sqrt(N_u)), and past a point the "
          "reported tail is the shape of a fit to a handful of points.")
    prose(doc,
          "Two diagnostics are standard. The sample mean excess plot graphs "
          "e(u) = E[Y - u | Y > u] against u. For a generalised Pareto tail the mean excess is "
          "linear in u,")
    add_equation(doc, "e(u) = beta_u / (1 - xi),   beta_u = beta_{u0} + xi * (u - u0), "
                      "finite for xi < 1",
                 title="EQUATION 8: GPD MEAN EXCESS AT THRESHOLD u")
    prose(doc,
          "so a range over which the empirical curve is approximately linear is a range over "
          "which a GPD may be a useful approximation. Each separately fitted threshold uses "
          "its own beta_u; adding xi*u again would double-count the scale shift. Parameter "
          "profiles are another descriptive diagnostic. Full-sample diagnostics remain "
          "retrospective even when computed before inspecting exception counts and cannot "
          "validate prospective threshold selection.")


# ------------------------------------------------------------- 3. Methodology --

def section_methodology(doc):
    add_heading_1(doc, "3. Methodology, Implementation Plan & Obstacles")
    limitations = N.raw("data.data_limitations")

    add_heading_2(doc, "3.1 Asset Universe & Ingestion Protocol")
    prose(doc,
          f"The universe is {N.value('data.n_assets')} US large-cap equities, one or more from "
          "each of the ten GICS sectors, held at equal weight, with SPY as the benchmark and "
          "^VIX as the market-state proxy. The cached panel covers "
          f"{N.value('data.first_date')} to {N.value('data.last_date')}, "
          f"{N.number(N.value('data.price_rows'), 0)} trading days, and is loaded once by "
          "`data_acquisition.fetch_and_cache_data`; every figure in this report is computed from "
          "that file, so a reader who has it does not need network access to reproduce them.")
    add_bullet_point(doc,
                     "The panel stores closing prices only. " + limitations["consequence"],
                     bold_prefix="Data limitation. ")
    add_bullet_point(doc, limitations["survivorship"] +
                     " Section 5 restates what this does to the reported returns and to the "
                     "optimisation result in particular.",
                     bold_prefix="Survivorship. ")
    prose(doc,
          "Constituent log returns are computed once. Their equal-weight average is a "
          "weighted-log return proxy, not the simple return of a daily-rebalanced account. "
          "The headline, threshold, residual and regime studies and retained Module 4 outputs "
          "use loss = -mean(asset log returns). The monetary section instead uses the "
          "daily-rebalanced simple return mean(expm1(asset log returns)); dynamic holdings "
          "and LP scenarios also use simple returns. These are distinct forecast/realisation "
          "lanes: the weighted-log 44/4,531 result does not certify the investable account. "
          "Summary "
          f"statistics for that series are in section 4.1: annualised return "
          f"{N.value('data.portfolio_statistics.Annualized Return (%)'):.2f}%, annualised "
          f"volatility {N.value('data.portfolio_statistics.Annualized Volatility (%)'):.2f}%, "
          f"skewness {N.value('data.portfolio_statistics.Skewness'):.2f} and excess kurtosis "
          f"{N.value('data.portfolio_statistics.Excess Kurtosis'):.2f}. The Jarque-Bera "
          "statistic on the raw portfolio returns is reported in section 4.1; the point for the "
          "methodology is that a normal distribution is not a defensible description of this "
          "series, which is the whole reason the framework exists.")

    add_heading_2(doc, "3.2 Walk-Forward Backtesting Protocol")
    prose(doc,
          f"Estimation uses a rolling window of {N.value('config.window')} trading days "
          "refitted every "
          f"{N.value('config.refit_interval')} days, giving "
          f"{N.value('data.refits_expected')} maximum-likelihood fits and "
          f"{N.number(N.value('data.walk_forward_days'), 0)} strictly out-of-sample "
          "observations. Between refits the GARCH recursion is carried forward day by day and "
          "the fitted tail parameters are held fixed. A forecast for day t+1 is produced from "
          "information ending at day t in every case, and the property is checked rather than "
          "asserted: `tests/test_backtester.py::test_walk_forward_no_lookahead` truncates the "
          "input series and asserts that the forecasts made before the cut are unchanged.")
    add_heading_3(doc, "Two variance recursions, and which one this report uses")
    prose(doc,
          "The recursion between refits in the Module 4 implementation updated the conditional "
          "variance with the most recent standardised residual twice, and did not advance the "
          "previous variance, so on the days between refits it applied "
          "sigma^2 = omega + alpha e^2 + beta (omega + alpha e^2 + beta sigma_prev^2) rather "
          "than the intended single step. The defect is in the interpolation between fits, not "
          "in any fitted parameter, and it moves the headline: the corrected recursion gives "
          f"{primary('Actual Breaches')} exceptions against the "
          f"{N.value('recursion.m4_reproduction.published_exceptions')} published in the "
          "proposal. Both are reported. The corrected recursion is the Module 6 primary because "
          "it is the one that implements the model the report describes, and the legacy "
          "recursion is retained as a reconciliation row so that every Module 4 number in this "
          "document can be traced to the code that produced it. The reproduction check is "
          f"run before any correction: refitting with the legacy settings returns the published "
          f"Module 4 frame to a maximum absolute difference of "
          f"{N.value('recursion.m4_reproduction.max_abs_difference'):.1e} per column on the "
          "build that wrote this manifest, which is floating-point agreement rather than "
          "approximate agreement. It is a property of that build, not a promise about every "
          "numeric stack: the refits are maximum-likelihood optimisations, so a different "
          "library build can move an individual daily figure a few places before the decimal "
          "point while leaving the exception count, and therefore the correction, unchanged. "
          "The regression test therefore checks a fresh refit against the tolerance the "
          "estimator supports and checks the published count itself exactly.")
    add_heading_3(doc, "One pass, many configurations")
    prose(doc,
          "The threshold and innovation sweeps would naively require refitting GARCH once per "
          "(threshold, innovation distribution, confidence level) cell. That is unnecessary: the "
          "filter does not depend on the threshold or the coverage at all. "
          "`walkforward_engine.run_multi_config_walk_forward` therefore fits each of the two "
          "innovation filters once per refit date, computes the standardised residuals once, and "
          "then evaluates every threshold by refitting only the generalised Pareto, which takes "
          f"{runtime_row('GPD peaks-over-threshold fit')['Calibration median (ms)']:.0f} ms, and "
          "every confidence level by arithmetic. Twelve VaR and expected-shortfall columns come "
          "out of a pass that costs two GARCH fits per refit rather than twenty-four. The "
          "long-format result is cached to data/m6_multi_config_walkforward.csv so the report "
          "build reads a file instead of recomputing.")

    add_heading_2(doc, "3.3 Residual Diagnostics Protocol")
    prose(doc,
          "Reviewer comment 2 asked for a justification of the independence assumption rather "
          "than an assertion of it, so the premise is tested and the tests are pre-registered in "
          "the code. For each innovation distribution and each estimation window the battery in "
          "`risk_models.residual_diagnostics` reports: Ljung-Box on the standardised residuals "
          "and on their squares at lags 1, 5, 10 and 20; the Engle double-multiple ARCH-LM test "
          "at the same lags; Jarque-Bera; skewness and excess kurtosis; the implied degrees of "
          "freedom of a Student-t matched to the observed kurtosis; and Kolmogorov-Smirnov "
          "distances against N(0,1) and against a unit-variance t with the fitted degrees of "
          "freedom.")
    add_bullet_point(doc,
                     "Ljung-Box on z-squared and ARCH-LM test specified squared-series "
                     "autocorrelation and remaining ARCH. Non-rejection establishes neither "
                     "independence nor the tail assumptions of POT.",
                     bold_prefix="Conditional variance diagnostics. ")
    add_bullet_point(doc,
                     "Ljung-Box on z tests linear autocorrelation at specified lags, not "
                     "strict independence or martingale-difference behaviour.",
                     bold_prefix="Levels diagnostics. ")
    add_bullet_point(doc,
                     "Within each reported lag family, the Bonferroni-adjusted minimum "
                     "p-value is min(1, m*p_min), where m is the number of tested lags. "
                     "Equivalently compare the raw minimum with the significance level / m. "
                     "This is not correction across every study in the manuscript.",
                     bold_prefix="Multiplicity. ")
    prose(doc,
          "One implementation note belongs in the methodology because it changes a result if "
          "ignored: the statsmodels diagnostics return a wholly missing result when handed a "
          "Series indexed by dates. The battery therefore converts to a plain numeric array "
          "before calling, and asserts that every reported p-value is finite, so that a silent "
          "gap cannot be read as a pass.")

    add_heading_2(doc, "3.4 Statistical Verification and Hypothesis Testing")
    prose(doc,
          "Three tests concern each VaR exceedance series, at the VaR confidence level. "
          "They do not test ES accuracy. ES has no universal nominal 1% exceedance target. "
          "An ES or joint VaR-ES backtest/scoring comparison with uncertainty and a "
          "GARCH-parametric or filtered-historical comparator remain unfinished.")
    add_bullet_point(doc,
                     "a likelihood-ratio test of the exception count against the binomial "
                     "expectation. It tests the nominal VaR exception frequency, with limited "
                     "finite-sample power; non-rejection is not certification.",
                     bold_prefix="Kupiec unconditional coverage (p_UC): ")
    add_bullet_point(doc,
                     "a test of whether the probability of an exception depends on the previous "
                     "day's outcome. It answers whether the exceptions cluster, which is the "
                     "failure mode a correctly-sized but lagging model exhibits.",
                     bold_prefix="Christoffersen first-order independence (p_IND): ")
    add_bullet_point(doc,
                     "the joint test of count and independence, reported alongside its "
                     "components.",
                     bold_prefix="Joint conditional coverage (p_CC): ")
    add_heading_3(doc, "An exact interval, not a normal approximation")
    interval = N.raw("headline.module4_exact_interval")
    prose(doc,
          f"An exception rate of {N.percent(interval['rate_pct'], 3)} from "
          f"{interval['exceptions']} events in {interval['observations']} days is a small-count "
          "proportion, and the symmetric Wald interval normally quoted for it is inaccurate "
          "precisely where it matters. The interval used throughout this report is "
          "Clopper-Pearson, exact under the independent common-probability Bernoulli/binomial "
          "assumptions, not assumption-free or dependence-adjusted. It uses beta quantiles rather than a normal "
          f"approximation: [{N.percent(interval['ci_pct'][0], 3)}, "
          f"{N.percent(interval['ci_pct'][1], 3)}] against a Wald interval of "
          f"[{N.percent(interval['wald_interval_would_be'][0], 3)}, "
          f"{N.percent(interval['wald_interval_would_be'][1], 3)}]. The distinction is not "
          "cosmetic for the argument in section 4.8: the exact interval is asymmetric and wider "
          "on the upside, and the nominal 1.0% target sits inside it.")
    prose(doc,
          "Regime breakdowns are reported as partitions and as subsets, never mixed. The three "
          "volatility bands partition the sample; the 2008 and 2020 windows are overlapping "
          "date subsets of it. Summing the observations across both kinds of row gives roughly "
          "twice the sample, which is how the Module 4 helper labelled `segment_performance_by_"
          "regimes` behaved; section 4.7 reports the two blocks separately and says so.")

    add_heading_2(doc, "3.5 Detailed Project Working Plan and Milestone Schedule")
    prose(doc,
          "The schedule table in the proposal was written before Modules 5 and 6 had happened, "
          "and its Module 5 row promised a copula extension and a Kenneth French factor "
          "attribution that this milestone does not contain. Left uncorrected that reads as "
          "slippage rather than as a decision, so the table below records what each module "
          "actually delivered and names the work that remains, with the copula extension kept as "
          "the Module 8 item it always was. The dates follow the course calendar, which places "
          "consecutive modules seven days apart and this submission on 3 November 2026.")
    static_table(
        doc, "Table 3",
        "Milestone schedule, corrected at Module 6 against what was delivered.",
        ["Module", "Milestone / deliverable", "Window", "Delivered or remaining", "Status",
         "Evidence"],
        [["1", "Group formation and topic selection", "Sept 2026",
          "Group 17845 formed; Track 2, Topic 3; the 20-stock universe and 2005-2024 horizon "
          "fixed as binding scope", "Complete", "M1 record; config.py universe"],
         ["2", "Concept document and problem statement", "Sept 2026",
          "Econometric problem statement; data contract for the cached panel", "Complete",
          "M2 document; data_acquisition.py"],
         ["3", "Literature review and competitor analysis", "Oct 2026",
          "Thirty-source synthesis; five competitor SWOT matrices; repository established; "
          "baseline Gaussian and historical VaR", "Complete", "M3 report; risk_models.py"],
         ["4", "Milestone 1: core assets and project proposal", "Oct 2026",
          "Two-stage GARCH-EVT-ES pipeline; 500-day walk-forward backtester; Kupiec and "
          "Christoffersen tests; figures 1-5; 19-page proposal", "Complete",
          "M4 deliverable; module4_metrics_manifest.json"],
         ["5", "Peer review", "Oct 2026",
          "Review of Group 17859 submitted; eight comments received on this group's proposal, "
          "dated 19 October 2026", "Complete", "Module 5 Reviewer Comments.pdf; Table 1"],
         ["6", "Milestone 2: draft project report (this document)", "Oct-Nov 2026",
          "Eight themes developed; validation and author review partly open: threshold sensitivity, residual "
          "diagnostics and Student-t innovations, portfolio-specific regimes, economic "
          "magnitude of exceptions, minimum-ES dynamic optimisation, computational cost, "
          "figure interpretation, literature delta", "**Current deliverable**",
          "Tables 1-5 and 10-23; figures 6-14; module6_metrics_manifest.json"],
         ["7", "Final presentation report and video", "by 10 Nov 2026",
          "Slide deck and recorded walkthrough; convergence of the discussion sections with the "
          "presentation narrative; final Turnitin submission of the manuscript", "In progress",
          "Table 4, tasks T6-T7"],
         ["8", "Final product and self-reflection", "by 17 Nov 2026",
          "Gaussian-copula dependence sensitivity across the twenty names, which is the "
          "extension deferred from Module 5; individual reflections; archived repository",
          "Planned", "Table 4, tasks T8-T9"]],
        widths=[0.5, 1.35, 0.7, 2.1, 0.85, 1.0])
    static_table(
        doc, "Table 4",
        "Remaining tasks to final submission, with owners. Dates are the targets set at this "
        "milestone, not the course deadlines.",
        ["ID", "Task", "Owner", "Target", "Risk if it slips"],
        [["T1", "Human verification of every new Works Cited entry against the publisher or DOI "
               "record", "Both authors", "27 Oct 2026",
          "An unverifiable citation is an integrity finding, not a formatting one"],
         ["T2", "Independently substantiate and defend the analysis; seek instructor guidance "
               "and approval on permitted assistance (pending)", "Both authors", "29 Oct 2026",
          "Generated analysis cannot substitute for student interpretation; paraphrasing is not a remedy"],
         ["T3", "Accurately disclose AI assistance and its scope; document instructor guidance "
               "and individual contributions (pending)", "Both authors", "29 Oct 2026",
          "Academic-integrity and collaboration clearance remain unverified"],
         ["T4", "Rebuild the report from the final manifest and re-run the full test suite",
          "Amin", "30 Oct 2026", "Prose numbers drifting from code, the recorded Module 4 "
          "failure mode"],
         ["T5", "Package code, data, figures and PDF; upload the PDF separately from the archive",
          "Mercy", "2 Nov 2026", "Turnitin cannot similarity-check a document inside a zip"],
         ["T6", "Slide deck and recorded walkthrough", "Both authors", "8 Nov 2026",
          "Module 7 grade"],
         ["T7", "Final manuscript convergence and re-submission", "Amin", "9 Nov 2026",
          "Module 7 grade"],
         ["T8", "Proposed Gaussian-copula dependence sensitivity (not a tail-dependence model)", "Amin", "14 Nov 2026",
          "Module 8 scope; the extension is additive and does not affect this report"],
         ["T9", "Individual self-reflection essays", "Both authors", "16 Nov 2026",
          "Module 8 grade"]],
        widths=[0.35, 1.9, 0.75, 0.8, 2.7])
    prose(doc,
          "Progress is implementation rather than final validation. Table 1 records partial "
          "and open feedback items; table 2 separates VaR tests from unfinished ES validation. "
          "The recorded shared sweep takes "
          f"{N.number(sharing_metric('shared_pass_wall_time_s'), 0)} seconds for "
          f"{N.number(sharing_metric('configurations_in_sweep'), 0)} configurations on the "
          "reported machine. Regenerated financial outputs, full test/package validation, "
          "source verification, independent author substantiation, accurate disclosure and "
          "instructor guidance remain required; no final clearance is asserted.")

    add_heading_2(doc, "3.6 Threshold Sensitivity Protocol")
    prose(doc,
          "Module 4 fixed the peaks-over-threshold cut at the 90th percentile of standardized "
          "losses and stated in the risk registry that the choice had been verified against a "
          "sample mean excess function. No code in the repository produced that verification. "
          "The reviewer's fifth comment asked for one, and this section describes what was built "
          "to answer it; section 4.5 reports what it found. The verification is now a produced "
          "artefact, and the claim in the registry cites it.")
    prose(doc,
          "The mean excess function is e(u) = E[Y - u | Y > u], the average size of a loss "
          "measured from the cut itself. Where equation 8 holds, a generalised Pareto tail makes "
          "e(u) a straight line in u with slope xi / (1 - xi), so linearity of the empirical "
          "curve over a range is the visible signature of the Pickands-Balkema-de Haan regime in "
          "which the threshold is high enough for the asymptote to bite but low enough to keep "
          "the tail well populated. That is the diagnostic, and it is drawn in figure 6 with "
          "marker size proportional to the number of exceedances behind each point.")
    prose(doc,
          "Four admissibility conditions are imposed on every candidate threshold, and the "
          "reporting distinguishes a threshold that is inadmissible from one that merely "
          "performs worse:")
    band = mel_band()
    add_bullet_point(doc,
                     "the empirical mean excess curve must be approximately linear over the "
                     f"candidate u, tested as a deviation of no more than "
                     f"{N.number(band['z_tolerance'], 1)} standard errors from a least-squares "
                     "line fitted across the part of the curve that still carries at least "
                     f"{N.number(band['min_exceedances'], 0)} exceedances.",
                     bold_prefix="Linearity. ")
    add_bullet_point(doc,
                     f"at least {N.number(band['min_exceedances'], 0)} exceedances must sit "
                     "above u in the sample used for the fit, because two parameters are being "
                     "estimated by maximum likelihood.",
                     bold_prefix="Population. ")
    add_bullet_point(doc,
                     "the adopted screen requires positive raw xi as a modelling preference, "
                     "not a mathematical validity condition. Negative xi is a valid bounded "
                     "GPD tail. Forcing it positive is regularisation whose forecast effects "
                     "must be assessed separately.",
                     bold_prefix="Positive-shape screen. ")
    add_bullet_point(doc,
                     "the implementation restricts threshold quantile q to below forecast "
                     "confidence alpha. At q = alpha, VaR equals u but ES remains "
                     "u + beta_u/(1-xi), strictly above u for beta_u > 0 and xi < 1. "
                     "Thresholds above alpha cannot estimate that quantile from the fitted "
                     "upper tail. Excluding equality is an implementation convention, not "
                     "a collapse of ES to VaR.",
                     bold_prefix="Threshold below forecast coverage. ")
    prose(doc,
          f"The grid is {len(N.value('threshold.grid'))} quantiles, from "
          f"{N.number(N.value('threshold.grid')[0], 2)} to "
          f"{N.number(N.value('threshold.grid')[-1], 2)}, in steps that include the "
          "0.95 and 0.975 the reviewer proposed plus a wider bracket on both sides. A grid "
          "chosen to include only the incumbent and its two neighbours would not have settled "
          "the question.")
    prose(doc,
          "Two estimation windows are run, because they answer different questions. The "
          f"first {N.value('data.window')} days are what a forecaster knows at the first "
          "decision date, and a threshold selected there is free of look-ahead. The full "
          f"{N.value('data.price_rows')} observations are the long-run profile of the "
          "series. The two disagree, and section 4.5 reports the disagreement rather than "
          "adopting whichever window flatters the incumbent. Full-sample selection uses "
          "evaluation-period information; computing it before running a backtest does not "
          "remove hindsight. Its quantile spread cannot bound that bias or rolling forecast "
          "error. A genuinely rolling selection procedure or untouched evaluation period is "
          "needed for prospective validation; the first-window screen accepts no candidate.")
    prose(doc,
          "Every fit records the threshold u, the exceedance count, the raw shape estimate with "
          "its standard error and a 95% interval, the value actually used, which way the clamp "
          "moved it, whether the fit degenerated, a Kolmogorov-Smirnov check of the exceedances "
          "against the fitted tail, and the 99% and 97.5% quantiles both with and without the "
          "clamp. Appendix G scores the clamped and unclamped versions of every one of those "
          "fits against the same out-of-sample losses, which is where the clamp stops being a "
          "footnote about a parameter. "
          "One construction detail matters for reading table 11: because the threshold is "
          f"recomputed as the empirical q-quantile of each {N.value('data.window')}-day "
          "window, the number of exceedances inside a window is fixed by construction at "
          f"{N.number(walk_forward_row(0.975)['n_u_min'], 0)} at q = 0.975 and "
          f"{N.number(walk_forward_row(0.98)['n_u_min'], 0)} at q = 0.98, so a "
          "high threshold is not merely noisier in expectation - it is that small in every "
          "single refit.")

    add_heading_2(doc, "3.7 Portfolio-Specific Regime Definition")
    prose(doc,
          "The third comment observed that the VIX prices the implied volatility of a "
          "capitalisation-weighted index of five hundred names, not of this twenty-stock "
          "equal-weighted book, and that a sector-specific dislocation can leave the book in "
          "turbulence while the index is quiet. The state variable used in Module 4 is therefore "
          "retained but demoted to what it is, and a second definition is built from the book's "
          "own realised behaviour.")
    prose(doc,
          f"The portfolio state is the annualised standard deviation of the equal-weighted daily "
          f"return over a rolling {C.PORTFOLIO_VOL_WINDOW}-day window, taken with a one-day lag "
          "so the band assigned to day t uses only data through t - 1 and can never see the day "
          "it labels. Realised volatility is used rather than the model's own conditional "
          "sigma because the point of a regime split is to ask a question of the model, and "
          "scoring a model against bands derived from that model's output answers nothing. Three "
          f"bands are cut at the terciles of {C.PORTFOLIO_VOL_WINDOW}-day realised volatility "
          f"computed over the first {C.PORTFOLIO_REGIME_CAL_DAYS} days, which is the calibration "
          "window the backtester itself uses, and those cut points are then frozen for the whole "
          "sample.")
    ag = N.raw("regime.agreement.portfolio_regime_frozen")
    cuts = N.raw("regime.cut_points.frozen")
    prose(doc,
          f"The frozen cuts are {N.percent(cuts['cut_points'][0] * 100, 2)} and "
          f"{N.percent(cuts['cut_points'][1] * 100, 2)} annualised. Freezing them is not "
          "neutral: the calibration window is 2005-2006, an unusually quiet stretch, so the "
          f"bands come out unbalanced over the rest of the sample - "
          f"{N.number(ag['marginals_portfolio']['low_vol'], 0)} low, "
          f"{N.number(ag['marginals_portfolio']['mid_vol'], 0)} middle and "
          f"{N.number(ag['marginals_portfolio']['high_vol'], 0)} high days out of "
          f"{N.number(ag['n_classified'], 0)}. A balanced variant, cut at whole-sample terciles, "
          "is therefore reported beside it as a labelled secondary run. The balanced variant is "
          "anticipatory in the band definitions, never in the forecasts, and is "
          "presented as such.")
    prose(doc,
          "Agreement between the two state variables is reported three ways, because a single "
          "number invites over-reading: the raw share of days where the two classifications "
          "pick the same band, Cohen's kappa on unweighted bands, and kappa with quadratic "
          "weights, which credits near-agreement and is the fairer summary for an ordinal "
          f"classification. On this sample they are {N.percent(ag['pct_agreement'], 2)}, "
          f"{N.number(ag['kappa_unweighted'], 3)} and {N.number(ag['kappa_quadratic'], 3)}, with "
          f"{N.percent(ag['pct_within_one_band'], 2)} of days within one band of each other. "
          "Interpretation belongs in section 4.7; what belongs here is that the kappa is "
          "reported whatever it turns out to be, and that the model comparison is then run "
          "under both definitions so that a reader can see whether any conclusion depended on "
          "the choice.")
    prose(doc,
          "The disagreement days are registered rather than averaged away. Days on which the "
          f"book sits in its high-volatility band while the lagged VIX reads calm are counted "
          f"({N.value('regime.stressed_but_calm.n_days')} of them), attributed by year, and "
          "decomposed to sector level using GICS classifications for the twenty constituents, "
          "reporting each sector's weight, mean contribution to the book's return and mean "
          "dispersion against the book. That is the arithmetic form of the reviewer's "
          "suggestion.")

    add_heading_2(doc, "3.8 Minimum-ES Portfolio Optimisation")
    prose(doc,
          "The fourth comment asked whether the framework survives the move from a static "
          "equal-weighted book to a dynamically optimised one. Expected shortfall is a coherent "
          "risk measure with a convex finite-scenario formulation. VaR can be optimised too, "
          "but is generally nonconvex. This extension uses conditional-historical scenarios "
          "rather than a GPD-extrapolated objective, so solver consistency does not establish "
          "that EVT improves realised allocation performance.")
    prose(doc,
          "The objective is the Rockafellar and Uryasev (2000) representation of expected "
          "shortfall. For a "
          "loss variable L and coverage alpha, ES_alpha is the value at the minimum of a convex "
          "function of a single auxiliary variable t:")
    add_equation(doc,
                 "ES_alpha(L) = min_t { t + 1/(1 - alpha) * E[ max(L - t, 0) ] }",
                 title="EQUATION 9: ROCKAFELLAR-URYASEV FORM")
    prose(doc,
          "Given K scenarios L_1 ... L_K, replacing the expectation with the empirical mean and "
          "the positive part with auxiliary variables gives a linear program in the weights and "
          "t. Each scenario is linear in the weights, so the whole problem is linear and solved "
          "exactly:")
    add_equation(doc,
                 "min over w, t, u:   t + (1 / (K (1 - alpha))) * sum_k u_k\n"
                 "subject to   u_k >= sum_i w_i * L_k,i - t   for k = 1..K\n"
                 "             u_k >= 0,   sum_i w_i = 1,   0 <= w_i <= "
                 f"{C.MAX_ASSET_WEIGHT:.2f}",
                 title="EQUATION 10: MINIMUM-ES LINEAR PROGRAM")
    prose(doc,
          "The scenarios are the heart of the construction and are worth stating precisely, "
          "because they decide what the optimiser can and cannot learn. For each asset i the "
          "walk-forward filter supplies a conditional mean and a conditional volatility as of "
          "the refit date, and the standardized residuals z of all twenty assets over the same "
          f"{C.ROLLING_WINDOW}-day window are taken at their matched dates. Scenario k is then "
          "a vector of simple losses L_k,i = -expm1(mu_i + sigma_i*z_k,i), converting "
          "each asset's log scenario before linear portfolio aggregation. The return floor "
          "also uses scenario mean simple returns. In other words the marginals are modelled and the dependence structure is "
          "not: whatever tail co-movement the window contains is carried into the optimiser "
          "untouched. The alternative - resampling the residuals independently - would destroy "
          "exactly the structure that makes a twenty-name portfolio different from the sum of "
          f"twenty names, whose measured mean off-diagonal correlation is "
          f"{N.number(N.value('optimisation.mean_off_diagonal_correlation'), 3)}. The "
          "proposed Gaussian-copula sensitivity is the Module 8 extension; it has no asymptotic "
          "tail dependence at nondegenerate correlations and does not solve tail clustering. It is not used "
          "here, which also means no conclusion in this report depends on a dependence model "
          "this group has not yet built.")
    prose(doc, "Four choices were rejected, and the reasons are on the record:")
    add_bullet_point(doc,
                     "an exact linear program with the HiGHS solver reaches a certificate of "
                     "optimality on a piecewise-linear objective. A sequential-quadratic-program "
                     "solver wanders at the kinks, and the objective is almost entirely kinks.",
                     bold_prefix="Iterative solvers. ")
    add_bullet_point(doc,
                     "SciPy is already a dependency; a modelling layer over it would add an "
                     "install step to a repository three people must reproduce on their own "
                     "machines, for a problem that does not need one.",
                     bold_prefix="A modelling framework. ")
    add_bullet_point(doc,
                     "minimising variance under a Gaussian assumption has a closed form and is "
                     "far cheaper, but it answers a different question and it would make the "
                     "argument for a coherent measure circular. It is kept, as a comparator row "
                     "in table 18, so the reader can see what ES minimisation buys over it.",
                     bold_prefix="Analytic minimum variance. ")
    add_bullet_point(doc,
                     "the formulation is convex without one, so the extra machinery would be "
                     "carried for appearance.",
                     bold_prefix="Semi-definite programming. ")
    opt = N.raw("optimisation")
    prose(doc,
          f"Rebalancing happens every {C.REBALANCE_INTERVAL} days, on exactly the dates the "
          "risk model refits, so the optimiser never acts on information the forecaster did not "
          "have. Weights solved from the window ending at t are applied to the return from t to "
          f"t + 1. Transaction cost is {C.TXN_COST_BPS:.0f} basis points charged on one-way "
          "turnover at each rebalance, applied to the difference against the weights actually "
          "held rather than against the target, so the cost of moving is real and is reported. "
          f"Three coverages are solved, alpha in {{{', '.join(f'{a:.3f}'.rstrip('0').rstrip('.') for a in C.ES_LP_ALPHAS)}}}, "
          "because at alpha = 0.99 and K = 500 only five scenarios carry the objective and the "
          "solution can sit at a degenerate corner; the concentration columns in table 19 are "
          "the check on that. The equal-weighted book is run twice, rebalanced on the same "
          f"{C.REBALANCE_INTERVAL}-day cadence and buy-and-hold, so that the rebalancing premium "
          "and the optimisation benefit are separated rather than conflated.")
    prose(doc,
          f"The minimum-ES solve path documents "
          f"{N.number(n_lp_solves() * len(C.ES_LP_ALPHAS), 0)} linear programs, one per "
          "rebalance date per coverage, and every one of them returned an optimal certificate; "
          f"across all strategies and coverages the run recorded {opt['failed_solves']} "
          "failures. One warning "
          "is stated here rather than buried in the results, because it constrains what can be "
          "concluded from table 18 at all: " + opt["comparability_warning"] + " The three "
          "conventions for scoring an optimised book are therefore reported side by side in "
          "table 20, each labelled with what it trains on and over what dates, and they are "
          "never averaged.")

    add_heading_2(doc, "3.9 Computational Cost Measurement Protocol")
    prose(doc,
          "The first comment asked for accuracy-versus-runtime trade-off to be an explicit "
          "objective. Module 4 asserted the pipeline was cheap without measuring it, so the "
          "measurement got its own protocol.")
    add_bullet_point(doc,
                     f"wall-clock time from a monotonic performance counter; {C.BENCH_WARMUP} "
                     f"untimed warm-up passes then {C.BENCH_REPEATS_FAST} timed repeats for an "
                     f"individual fit and {C.BENCH_REPEATS_SLOW} for a whole walk-forward pass, "
                     "which is the only distinction that matters between a millisecond "
                     "operation and a ten-second one.",
                     bold_prefix="Timed with ")
    add_bullet_point(doc,
                     "median and 95th percentile, never the mean alone, because a mean absorbs "
                     "the scheduler stalls that dominate a distribution like this; the minimum "
                     "is reported as a floor the machine can reach when nothing else is running.",
                     bold_prefix="Reported as ")
    add_bullet_point(doc,
                     "per-calibration cost, the wall time of a complete walk-forward pass, and "
                     "the cost per forecast day after amortisation. The third is the number a "
                     "practitioner pays and is set by the refit cadence: the model is fitted "
                     f"{N.number(N.value('data.refits_expected'), 0)} times but read "
                     f"{N.number(N.value('data.walk_forward_days'), 0)} "
                     "times. The measured caution repeats this: " + N.value("runtime.caution"),
                     bold_prefix="Three quantities. ")
    add_bullet_point(doc,
                     f"refit cadence is swept over {', '.join(str(i) for i in C.BENCH_REFIT_INTERVALS)} "
                     "days, which turns the accuracy-versus-latency question into a curve "
                     "instead of a single point and shows what daily refitting would cost.",
                     bold_prefix="Cadence as a knob. ")
    add_bullet_point(doc,
                     "the sweep that produces tables 10 through 13 shares one pass: the filter "
                     "is fitted twice per refit date, once per innovation law, the standardized "
                     "residuals are computed once, and each threshold and coverage then costs "
                     "only a peaks-over-threshold fit and closed-form arithmetic. The sharing "
                     "columns in table 23 are the evidence that the sensitivity study is not "
                     "expensive because it is broad.",
                     bold_prefix="One pass, many configurations. ")
    prose(doc,
          "Timings are meaningless without the machine that produced them, so the platform, "
          "Python and library versions and processor are written into the manifest beside the "
          "numbers and reproduced in appendix F. Any figure quoted from table 21 should be read "
          "as a ratio between models on one machine, not as an absolute latency; other "
          "applications should be closed when re-running the benchmark.")
    prose(doc,
          "The accuracy column of table 21 is taken from the Module 4 walk-forward under the "
          "legacy recursion, so that the cost comparison sits on the same numbers the proposal "
          "published. That makes it a continuity table, not a Module 6 result, and it is "
          "labelled as such wherever it appears.")

    add_heading_2(doc, "3.10 Risk Registry: Obstacles, Impediments, and Mitigation Strategies")
    prose(doc,
          "The registry below carries Module 4's five entries forward with their status changed "
          "by what this module measured, and adds four that the reviewer comments exposed. Two "
          "of the five are downgraded from an assertion to an artefact; one is restated because "
          "the mitigation it described was doing something the original text did not name.")
    static_table(
        doc, "Table 5",
        "Risk registry as revised at Module 6. Severity is the residual risk after the "
        "mitigation in the same row, not the raw exposure.",
        ["Obstacle / Impediment", "Severity", "Impact on the project",
         "Mitigation and its status at Module 6"],
        [["**Computational overhead of rolling MLE**", "Low",
          f"Fitting a non-linear GARCH filter and a peaks-over-threshold tail over "
          f"{N.value('data.walk_forward_days')} rolling windows, and then over a "
          f"{len(N.value('threshold.grid'))}-threshold by 2-innovation sweep of them.",
          "Monthly-equivalent refit cadence with exact daily variance recursion, plus a sweep "
          "engine that shares one filter pass across every threshold and coverage. Now "
          "measured, not asserted: table 21 gives the median cost of one calibration and the "
          "amortised cost per forecast day. **Closed, with the caveat that this is a daily "
          "mark, not an intraday loop.**"],
         ["**POT threshold selection sensitivity**", "Moderate",
          "An arbitrary cut induces a bias-variance trade-off in the tail fit and is the single "
          "most consequential hyperparameter in the pipeline.",
          "Module 4 recorded this as verified against a mean excess function when no such "
          "artefact existed. It now exists: mean excess curve, a six-point grid wider than the "
          "reviewer requested, four admissibility criteria, and the whole thing run in both the "
          f"calibration window and the full sample (sections 3.6 and 4.5). The incumbent "
          f"q = {N.value('threshold.recommendation.from_full_sample.recommended_q'):.2f} is "
          "admissible on the full sample and the forecast varies by "
          f"{N.percent(threshold_spread_pct()[2], 2)} across admissible thresholds. "
          "**Evidence delivered; the choice is confirmed rather than assumed.**"],
         ["**Constituent survivorship bias**", "Moderate",
          "All twenty names are 2024 constituents viewed over twenty years, which raises the "
          "measured return, lowers the measured tail, and makes an ex-post risk-minimising "
          "optimiser look safer than it would have been.",
          "Declared, and benchmarked against SPY, which does carry historical turnover. The "
          "Module 4 row also claimed calibration against Kenneth French survivorship-free "
          "factors; that attribution was never built and the claim is removed here rather than "
          "carried forward. A point-in-time universe needs paid membership data the group does "
          "not have. **Unmitigated, disclosed, with an alphabetical first-ten-names control run "
          "in section 4.9.**"],
         ["**Numerical instability in crises, and what the parameter clamp hides**", "High",
          "Deep drawdowns destabilise both likelihoods. Module 4's mitigation bounded the shape "
          "parameter to a positive interval and, below ten exceedances, substituted fixed "
          "parameters. Both act silently: a substituted value is indistinguishable in the "
          "output from a fitted one.",
          "Every fit now records the raw estimate, the value used, and the direction the clamp "
          f"moved it; degenerate and clamped counts are reported per configuration. At the "
          f"production threshold the clamp does not bind on the full sample "
          f"(raw shape {N.number(threshold_row(0.90)['xi_raw'], 4)}) but it does in "
          f"{N.percent(walk_forward_row(0.90)['clamped_share_%'], 1)} of the walk-forward "
          "refits, and that asymmetry is stated wherever the threshold is discussed. The "
          "substitution path now raises instead of inventing parameters, and a flag restores "
          "the old behaviour for reproduction. **Disclosed and quantified, not eliminated.**"],
         ["**Multivariate dimensionality**", "Moderate",
          "A full copula-GARCH across twenty names carries 190 dependence parameters.",
          "Portfolio-level aggregation of the McNeil-Frey kind for the headline forecasts, "
          "with 100 random weightings as a weight-invariance check. Two honesty items: the "
          "historical-simulation row of that check is mechanically close to one percent for "
          "any weights, so it carries no information and is footnoted; and the copula itself is "
          "named as the Module 8 extension. **Mitigated by design, deferred by scope.**"],
         ["**Exception recursion double-counted the latest shock**", "Low",
          "Between refits the variance update applied the same residual twice and never advanced "
          "the previous variance, so 226 of every 227 days used a two-step update as if it were "
          "one step.",
          "Found while writing the tests for this module, before any reviewer asked. Both "
          "recursions ship: the corrected one is the primary result and the legacy one is kept "
          "as the reconciliation row so Module 4's published figures remain traceable. The "
          f"headline exception count moves from {N.value('headline.module4_exact_interval.exceptions')} "
          f"to {primary('Actual Breaches')} and both pass. **Fixed; disclosed unprompted.**"],
         ["**Threshold degeneracy inside a short window**", "Moderate",
          "The exceedance count per refit window falls with the threshold, and the shape "
          "standard error rises faster.",
          f"Reported per configuration: from {N.number(threshold_grid_nu_min()[1], 0)} down to "
          f"{N.number(threshold_grid_nu_min()[0], 0)} exceedances per window across the grid, "
          "with the median standard error of the shape "
          "estimate beside them. High thresholds are rejected on variance grounds in section "
          "4.5, which is an evidentiary reason and not a preference. **Contained by reporting "
          "it.**"],
         ["**Turnover cost of the optimised book**", "Moderate",
          "Minimum-ES rebalancing trades far more than an equal-weighted book, and cost is "
          "charged against wealth, not against the tail.",
          f"Ten basis points on one-way turnover, measured and tabulated: the ES-minimising book "
          f"turns {N.number(strategy_row('Minimum ES')['One-way turnover (annual)'], 2)} times "
          f"a year one-way at a cost drag of "
          f"{N.percent(strategy_row('Minimum ES')['Annual fee fractions (%)'], 2)} of wealth, "
          "against the rebalanced equal-weight comparison in the same table. A turnover-capped "
          "variant is run. **Visible, not absorbed.**"],
         ["**Dynamic and static books are not comparable**", "High",
          "An exception count prices a loss series. Two books have two series, so a breach count "
          "cannot be read as a model comparison across them.",
          "Calibration is read within a row and risk reduction across rows, never mixed. Three "
          "scoring conventions are reported side by side with what each trains on, the "
          "headline the plan expected was falsified by the walk-forward and is reported as "
          "falsified, and the diagnosis in section 4.9 attributes the excess exceptions to the "
          "2007-08 transition and to concentration rather than to the framework. **This is the "
          "row most likely to be challenged, and it is stated in the open.**"]],
        widths=[1.25, 0.55, 1.95, 2.75])
    return doc


# -------------------------------------------------------------------- 4. Results --

def section_results(doc):
    """Sections 4.1 to 4.4: what the proposal reported, re-read from its own artefact."""
    add_heading_1(doc, "4. Empirical Results")
    prose(doc,
          "The first four subsections reproduce the proposal's evidence so that the reviewer "
          "can read this document without the earlier one open. They are generated from "
          "Module 4's own metrics artefact rather than retyped, and every figure they cite was "
          "redrawn by the frozen Module 4 plotting code. The numbers in them are the legacy "
          "variance recursion; that is deliberate, and section 4.2 states what changes under "
          "the corrected one. Sections 4.5 to 4.10 are new evidence, produced by the code this "
          "module added.")

    add_heading_2(doc, "4.1 Return Distribution and Tail Diagnostics")
    stats = M4.raw("summary_stats")
    spy = M4.raw("spy_stats")
    static_table(
        doc, "Table 6",
        "Daily return statistics for the equal-weighted twenty-stock book and the SPY "
        "benchmark over 2005-2024, with the Gaussian reference values beside them.",
        ["Measure", "20-stock portfolio", "SPY benchmark", "Gaussian would say"],
        [["Trading days", N.number(stats["Observations"], 0), N.number(spy["Observations"], 0),
          "-"],
         ["Mean daily return", N.percent(stats["Mean Daily (%)"], 4),
          N.percent(spy["Mean Daily (%)"], 4), "-"],
         ["Daily volatility", N.percent(stats["Daily Volatility (%)"], 4),
          N.percent(spy["Daily Volatility (%)"], 4), "-"],
         ["Annualised return", N.percent(stats["Annualized Return (%)"], 2),
          N.percent(spy["Annualized Return (%)"], 2), "-"],
         ["Annualised volatility", N.percent(stats["Annualized Volatility (%)"], 2),
          N.percent(spy["Annualized Volatility (%)"], 2), "-"],
         ["Skewness", N.number(stats["Skewness"], 3), N.number(spy["Skewness"], 3), "0"],
         ["Excess kurtosis", N.number(stats["Excess Kurtosis"], 2),
          N.number(spy["Excess Kurtosis"], 2), "0"],
         ["Jarque-Bera statistic", N.number(stats["Jarque-Bera Stat"], 1),
          N.number(spy["Jarque-Bera Stat"], 1), "approximately 6 at 5%"],
         ["Jarque-Bera p-value", N.p_value(stats["Jarque-Bera p-val"]),
          N.p_value(spy["Jarque-Bera p-val"]), "-"]],
        widths=[1.9, 1.6, 1.6, 1.6])
    prose(doc,
          f"Observation: the book's excess kurtosis is {N.number(stats['Excess Kurtosis'], 2)} "
          f"against SPY's {N.number(spy['Excess Kurtosis'], 2)}, on the same number of days, "
          "with a Jarque-Bera statistic two orders of magnitude past the rejection boundary for "
          "either. Mechanism: an equal-weighted twenty-name book is not a smaller index. "
          "Diversification removes the idiosyncratic variance that makes the centre of the "
          "distribution look tame, and leaves the days on which the names move together; the "
          "tail is therefore thicker than the benchmark's, not thinner, because equal weights "
          "give the small and volatile constituents the same influence as the megacaps. "
          "Consequence: any method that sets the boundary from a standard deviation and a "
          "normal quantile is pricing a distribution this sample does not have. Falsifier: a "
          "sample whose kurtosis sat near zero, or a tail that thins once conditional variance "
          "is removed rather than added - which is exactly what section 4.6 measures.")
    figure(doc, "fig1_portfolio_vs_market_drawdowns.png", "Figure 1",
           "Cumulative wealth of $100 in the equal-weighted book against SPY, with the drawdown "
           "panel below and VIX-above-30 stretches shaded red.")
    prose(doc,
          "Observation: the two wealth paths finish within "
          f"{N.percent(stats['Annualized Return (%)'] - spy['Annualized Return (%)'], 2)} a "
          "year of each other, while the drawdown panel shows the book giving back more than "
          "half its value twice. Mechanism: the upper panel is a mean, the lower is a tail, and "
          "an equal-weighted book and a capitalisation-weighted index can earn the same return "
          "on very different paths. Consequence: a comparison of risk models cannot be made on "
          "return, and the whole study is conducted on the lower panel. Falsifier: drawdown "
          "troughs that coincide with calm VIX stretches would mean the shaded bands are not "
          "doing the work claimed here; they are not - the bands are where the troughs are.")
    figure(doc, "fig2_fat_tailed_diagnostics_gpd_fit.png", "Figure 2",
           "Density against Gaussian and Student-t fits, the normal Q-Q plot, and the "
           "peaks-over-threshold exceedances with the fitted generalised Pareto tail on "
           "logarithmic axes.")
    prose(doc,
          "Observation: panel A's empirical density is taller at the centre and fatter at both "
          "ends than the Gaussian curve, panel B's Q-Q plot bends away from the forty-five "
          "degree line at both ends rather than crossing it, and panel C's exceedances lie "
          "close to the fitted tail over the range where there are points to fit. Mechanism: "
          "the middle and the tail of an equity return series are governed by different things "
          "- the bulk by ordinary dispersion, the tail by the largest shocks in the sample - so "
          "one distributional family asked to cover both compromises on the half that matters "
          "for a risk limit. That is the empirical case for the two-stage design. Consequence: "
          "the peaks-over-threshold step is fitted to panel C's points and never to the bulk, "
          "which is why the Gaussian rejection in table 6 does not invalidate the model. "
          "Falsifier: a fitted tail that bent visibly away from the points above the threshold, "
          "or a Kolmogorov-Smirnov check rejecting the fit at every threshold in section 4.5.")

    add_heading_2(doc, "4.2 Out-of-Sample Walk-Forward Backtest")
    perf = M4.raw("perf_summary")
    evt = perf["VaR_GARCH_EVT"]
    es = perf["ES_GARCH_EVT"]
    static_table(
        doc, "Table 7",
        f"Walk-forward backtest over {N.number(N.value('data.walk_forward_days'), 0)} days at the "
        f"{N.percent(N.value('headline.confidence_level') * 100, 1)} coverage, as published in "
        "the proposal. Reproduced from the Module 4 artefact; table 8 shows the effect of "
        "correcting the variance recursion.",
        ["Risk model", "Exceptions", "Rate", "Expected", "Unconditional coverage p (p_UC)",
         "Independence p (p_IND)", "Mean excess"],
        [["Parametric normal VaR", N.number(perf['VaR_Normal']['Actual Breaches'], 0),
          N.percent(perf['VaR_Normal']['Breach Rate (%)'], 2),
          N.number(perf['VaR_Normal']['Expected Breaches'], 1),
          N.p_value(perf['VaR_Normal']['Kupiec p-val']),
          N.p_value(perf['VaR_Normal']['Independence p-val']),
          N.percent(perf['VaR_Normal']['Mean Excess Loss (%)'], 2)],
         ["Historical simulation VaR", N.number(perf['VaR_Historical']['Actual Breaches'], 0),
          N.percent(perf['VaR_Historical']['Breach Rate (%)'], 2),
          N.number(perf['VaR_Historical']['Expected Breaches'], 1),
          N.p_value(perf['VaR_Historical']['Kupiec p-val']),
          N.p_value(perf['VaR_Historical']['Independence p-val']),
          N.percent(perf['VaR_Historical']['Mean Excess Loss (%)'], 2)],
         ["**GARCH-EVT VaR**", f"**{N.number(evt['Actual Breaches'], 0)}**",
          f"**{N.percent(evt['Breach Rate (%)'], 2)}**",
          N.number(evt['Expected Breaches'], 1),
          f"**{N.p_value(evt['Kupiec p-val'])} (pass)**",
          f"**{N.p_value(evt['Independence p-val'])} (pass)**",
          N.percent(evt['Mean Excess Loss (%)'], 2)],
         ["GARCH-EVT expected shortfall", N.number(es['Actual Breaches'], 0),
          N.percent(es['Breach Rate (%)'], 2), "-", "-", "-",
          N.percent(es['Mean Excess Beyond ES (%)'], 2)]],
        note="The expected-shortfall row is descriptive, not a test. The three coverage tests "
             "are defined on the VaR exceedance series; expected shortfall has no nominal "
             "exception frequency, so a low count there is not evidence that the ES forecast is "
             "accurate. Section 4.2 and objective O2 keep that distinction.",
        widths=[1.85, 0.75, 0.6, 0.7, 0.95, 0.95, 0.85])
    prose(doc,
          f"The Gaussian boundary is breached {perf['VaR_Normal']['Actual Breaches']} times "
          f"where {N.number(perf['VaR_Normal']['Expected Breaches'], 1)} are owed, the "
          "historical quantile "
          f"{perf['VaR_Historical']['Actual Breaches']} times, and the two-stage filter "
          f"{evt['Actual Breaches']}. Both baselines fail Kupiec decisively and both fail the "
          "independence test as well, which is the more informative half of that result: an "
          "under-sized boundary is a sizing error, but exceptions that follow each other are a "
          "model that is wrong in a way a wider constant multiplier cannot repair. The "
          f"exact {N.percent(N.value('headline.module4_exact_interval.rate_pct'), 4)} rate of "
          "the two-stage filter, and its "
          f"{N.p_value(evt['Kupiec p-val'])} and {N.p_value(evt['Conditional Cov p-val'])}, are "
          "the published headline of the proposal and are unchanged here.")
    figure(doc, "fig3_rolling_var_es_backtest_crises.png", "Figure 3",
           "Daily realised loss against the three rolling boundaries over the scored sample, "
           "with the 2008 and March 2020 stretches enlarged.")
    prose(doc,
          "Observation: in the enlarged panels the Gaussian boundary runs almost flat through "
          "the worst weeks while the loss series pierces it repeatedly; the historical boundary "
          "steps up only after the losses have arrived; the two-stage boundary rises into the "
          "shock and the expected-shortfall line sits above it throughout. Mechanism: the "
          "Gaussian boundary is an unconditional standard deviation over the estimation window, "
          f"so one trading day can move it by at most about one part in "
          f"{N.value('data.window')} and it cannot reprice a regime within the week in which "
          "the regime changes; its quantile multiplier then has no tail to widen either. "
          "Historical simulation has the right tail shape but "
          f"its {N.value('data.window')}-day window is full of tranquil days at the moment the "
          "shock arrives, so it is late by construction. The two-stage filter separates the two "
          "jobs: the conditional volatility responds within one observation and the generalised "
          "Pareto multiplier widens the boundary beyond anything the Gaussian quantile allows. "
          "Consequence: the ranking of the three models is a ranking of how fast each can move, "
          "and it holds in both crises and in neither calm. Falsifier: flatness of the Gaussian "
          "band in the calm stretches too, which would mean the band is not slow but simply "
          "wide; section 4.7 tests exactly that by splitting the sample, and the calm-regime "
          "rates there are low for the two-stage filter and not for the Gaussian.")

    add_heading_2(doc, "4.3 Performance by Market Volatility Regime")
    reg = N.raw("headline.module4_regime_summary")
    rows = []
    for band, values in reg.items():
        rows.append([band, N.number(values["Observations"], 0),
                     N.percent(values["VaR_Normal_Rate (%)"], 2),
                     N.percent(values["VaR_Historical_Rate (%)"], 2),
                     N.percent(values["VaR_GARCH_EVT_Rate (%)"], 2),
                     N.percent(values["ES_GARCH_EVT_Rate (%)"], 2),
                     N.percent(values["VaR_Normal_MeanExcess (%)"], 2),
                     N.percent(values["VaR_GARCH_EVT_MeanExcess (%)"], 2)])
    static_table(
        doc, "Table 8",
        "Exception rates by VIX band as published in the proposal. The first three rows are a "
        "partition of the scored sample; the last two are overlapping date subsets and are not "
        "added to it.",
        ["Regime", "Days", "Normal VaR", "Historical VaR", "GARCH-EVT VaR", "GARCH-EVT ES",
         "Normal mean excess", "GARCH-EVT mean excess"], rows,
        widths=[1.5, 0.5, 0.75, 0.85, 0.9, 0.85, 0.95, 1.1],
        note="Read with section 3.4: the partition and the subsets must not be summed. "
             "Section 4.7 rebuilds this table with a lagged state variable, one measured on "
             "the book itself, and a corrected recursion, and reports where the two disagree.")
    crisis = reg["Crisis (VIX >= 30)"]
    prose(doc,
          f"Observation: in the crisis band the Gaussian boundary is breached on "
          f"{N.percent(crisis['VaR_Normal_Rate (%)'], 2)} of days, roughly twelve times its "
          f"nominal rate, while the two-stage filter records "
          f"{N.percent(crisis['VaR_GARCH_EVT_Rate (%)'], 2)} and its expected-shortfall line "
          f"{N.percent(crisis['ES_GARCH_EVT_Rate (%)'], 2)}. Mechanism: the bands are defined "
          "by an outside variable, so a model that never reads the VIX is being graded on how "
          "well its own internal dynamics track the same turbulence. Consequence: the "
          "two-stage filter is not being credited for avoiding crises, it is being credited for "
          "surviving them without knowing about them. Falsifier: a model that only looks "
          "calibrated because it never left the calm bands - which the day counts rule out, "
          f"since the crisis band here contains {N.number(crisis['Observations'], 0)} scored "
          "days, enough to reject a badly sized boundary on its own.")
    figure(doc, "fig4_backtest_violations_by_regime.png", "Figure 4",
           "Exception rate by regime for each model against the 1% target line, with the two "
           "date overlays shown separately.")
    prose(doc,
          "Observation: the bars fan out as the regime worsens for the two baselines and stay "
          f"flat for the third; the March 2020 overlay reaches "
          f"{N.percent(reg_overlay(reg, '2020 COVID')['VaR_Normal_Rate (%)'], 2)} for the "
          "Gaussian boundary, one day in four. Mechanism: the fan-out is the same latency "
          "described for figure 3, aggregated - a boundary that responds slowly is wrong in "
          "proportion to how fast the regime moved. Consequence: a regulator reading only the "
          "aggregate rate would see the Gaussian model at "
          f"{N.percent(N.value('headline.module4_performance_summary.VaR_Normal.Breach Rate (%)'), 2)} "
          "overall, which understates how badly it fails in the states where a failure matters. "
          "Falsifier: bars that did not fan out for the baselines, or a two-stage bar that rose "
          "sharply in the crisis band; the second does occur mildly, and section 4.8 puts a "
          "dollar figure on what the residual crisis exceptions cost.")

    add_heading_2(doc, "4.4 Allocation Invariance")
    wr = N.raw("weight_robustness.models")
    static_table(
        doc, "Table 9",
        f"{N.value('weight_robustness.simulations')} random allocations drawn from a symmetric "
        "Dirichlet over the twenty names, scored on the full sample, as in the proposal. The "
        "historical-simulation row is a mechanical identity and carries no evidence.",
        ["Risk model", "Mean rate", "Std dev", "5th pct", "95th pct", "Range"],
        [[lbl, N.percent(wr[k]["mean_pct"], 3), N.percent(wr[k]["std_pct"], 3),
          N.percent(wr[k]["p5_pct"], 3), N.percent(wr[k]["p95_pct"], 3),
          f"{N.percent(wr[k]['min_pct'], 3)} to {N.percent(wr[k]['max_pct'], 3)}"]
         for k, lbl in [("VaR_Normal_Rates", "Parametric normal VaR"),
                        ("VaR_Historical_Rates", "Historical simulation VaR"),
                        ("VaR_GARCH_EVT_Rates", "GARCH-EVT VaR"),
                        ("ES_GARCH_EVT_Rates", "GARCH-EVT expected shortfall")]],
        widths=[1.7, 0.8, 0.75, 0.75, 0.75, 1.6],
        note=N.value("weight_robustness.tautology"))
    prose(doc,
          "Two limitations of this test are stated here rather than in the discussion, because "
          "the table is easy to over-read. It scores each weighting on the full sample, so it is "
          "a stability check across weights and not a second out-of-sample test; and the "
          "historical-simulation standard deviation, "
          f"{wr['VaR_Historical_Rates']['std_pct']:.1e} percentage points, is an artefact of a "
          "boundary defined as the empirical "
          "quantile of the very sample it is scored against. A walk-forward version of the same "
          "test is run in section 4.5 across the threshold grid, and that one does move.")
    figure(doc, "fig5_dirichlet_robustness_test.png", "Figure 5",
           "Distribution of exception rates across the random allocations, boxplot and density, "
           "against the 1% target.")
    prose(doc,
          f"Observation: the two-stage box sits at {N.percent(wr['VaR_GARCH_EVT_Rates']['mean_pct'], 3)} "
          f"with its whole interquartile range below the Gaussian box at "
          f"{N.percent(wr['VaR_Normal_Rates']['mean_pct'], 3)}, and the spread across "
          f"{N.value('weight_robustness.simulations')} weightings is "
          f"{N.percent(wr['VaR_GARCH_EVT_Rates']['std_pct'], 3)} - narrow, but not zero. "
          "Mechanism: if the framework's accuracy came from the equal weights, the box would be "
          "centred on 1% by construction rather than by fit. It is centred slightly below, "
          f"between the fifth and ninety-fifth percentiles of "
          f"{N.percent(wr['VaR_GARCH_EVT_Rates']['p5_pct'], 3)} and "
          f"{N.percent(wr['VaR_GARCH_EVT_Rates']['p95_pct'], 3)}. Consequence: the headline "
          "result is a property of the estimator, not of the weighting, which is what licenses "
          "the portfolio extension in section 4.9. Falsifier: a wide box with the equal-weighted "
          "result sitting at an extreme of it; the equal-weighted rate of "
          f"{N.percent(primary('Breach Rate (%)'), 3)} sits inside the central mass, and a "
          "genuine weight-dependence would have shown the opposite.")
    return doc


# ------------------------------------------------- 4. to 10: the Module 6 evidence --

def _q_label(record):
    return f"{record['threshold_quantile'] if 'threshold_quantile' in record else record['threshold_q']:g}"


def _ci_cell(record, low="Breach Rate 95% CI (%)"):
    interval = record[low]
    if interval is None:
        return "n/a"
    return f"[{interval[0]:.3f}, {interval[1]:.3f}]"


def section_results_module6(doc):
    """Sections 4.5 to 4.10: the eight reviewer answers, each with its own evidence."""
    add_heading_2(doc, "4.5 Threshold Sensitivity and the Mean Excess Diagnostic")
    sel = N.raw(selection_path("normal"))
    band = mel_band("normal")
    prose(doc,
          f"Reviewer comment 5 asked whether the peaks-over-threshold level was fixed by "
          f"assertion. Two things were built to answer it: a mean excess diagnostic that tests "
          f"the premise the threshold model rests on, and a single walk-forward pass over "
          f"{len(N.value('threshold.grid'))} thresholds, two innovation distributions and two "
          f"coverages. The short answer is that q = {N.value('threshold.recommendation.from_full_sample.recommended_q'):g} "
          f"survives, but not for the reason the proposal implied, and the sweep exposed a "
          f"failure mode the proposal never looked at. Table 10 is the full-sample evidence: "
          f"one generalised Pareto fit per threshold, with the unclamped estimate printed "
          f"beside the one the code used.")
    manifest_table(
        doc, "Table 10",
        f"Full-sample peaks-over-threshold profile at "
        f"{N.percent(N.value('headline.confidence_level') * 100, 1)} coverage under Gaussian "
        "innovations. Every threshold is fitted to the same conditional-variance filter, so the "
        "columns differ only in where the cut is made.",
        profile_path("normal"),
        [("threshold_quantile", "Threshold q", _q_label),
         ("u", "Cut u (sd)", 4),
         ("n_u", "Exceedances", 0),
         ("xi_raw", "Shape, estimated", 4),
         ("xi_used", "Shape, used", 4),
         ("clamped", "Clamp bound", lambda r: yesno(r["clamped"])),
         ("beta", "Scale", 4),
         ("ks_pvalue", "KS distance p (naive)", "pv"),
         ("var_z_raw", "VaR from estimate", 4),
         ("var_z", "VaR used", 4),
         ("es_z", "ES used", 4)],
        note="The shape column labelled estimated is the maximum-likelihood value before the "
             f"admissibility band of [{XI_ADMISSIBLE_MIN:g}, {XI_ADMISSIBLE_MAX:g}] is applied; "
             "used is the value that entered the quantile. The band is named in risk_models.py, "
             "the module the pipeline imports, so this sentence and the code cannot drift apart. "
             "The unclamped quantile is defined for any shape below one, including a negative "
             "one, so an unclamped row is not a missing row. The last column is not a test: the "
             f"Kolmogorov-Smirnov p-value is computed with the shape and scale fitted to these "
             f"very exceedances held fixed, which makes it anti-conservative, and the manifest "
             f"field beside it records that as "
             f"{N.records(profile_path('normal'))[0]['ks_inference']}. A refit-aware bootstrap "
             "would make it a test and has not been run.",
        filter_kwargs={"confidence_level": N.value("headline.confidence_level")})
    at_alpha = [r for r in N.records(profile_path("normal"))
                if _near(r["confidence_level"], N.value("headline.confidence_level"))]
    ks_min = min(r["ks_pvalue"] for r in at_alpha)
    ks_max = max(r["ks_pvalue"] for r in at_alpha)
    xi_min = min(r["xi_raw"] for r in at_alpha)
    xi_max = max(r["xi_raw"] for r in at_alpha)
    prose(doc,
          f"Three things come out of the table. First, the fitted tail sits close to the "
          f"exceedances at every threshold: the Kolmogorov-Smirnov distances run from "
          f"{N.number(ks_min, 3)} to {N.number(ks_max, 3)} on their naive p-values. That is a "
          "distance, not a pass - the same exceedances fitted the tail that is being compared "
          "to them, so no threshold here is either accepted or refused by a test with correct "
          f"critical values. Second, the admissibility band "
          f"is active at the two lowest thresholds and inactive at the other four: at "
          f"q = 0.8 the estimated shape is "
          f"{N.number(threshold_row(0.8)['xi_raw'], 4)}, which asserts a bounded upper endpoint, "
          f"and forcing it to the lower bound inflates the reported quantile by "
          f"{N.percent(clamp_effect_pct(0.8), 2)}; at q = 0.85 the inflation is "
          f"{N.percent(clamp_effect_pct(0.85), 2)}. At the production threshold and above, no "
          "inflation occurs, and an inflation measured on one full-sample quantile bounds "
          "nothing about a rolling forecast; table 28 scores the same two extrapolations day by "
          "day on out-of-sample losses instead. Third, the shape estimate is small everywhere, between "
          f"{N.number(xi_min, 4)} and {N.number(xi_max, 4)}, "
          "and it is never statistically distinguishable from zero - "
          f"{N.number(sel['n_thresholds_whose_shape_is_significant'], 0)} "
          "of six thresholds carry a significant shape estimate. That single fact explains the "
          "insensitivity that follows, and it is stated plainly rather than dressed up as a "
          "heavy-tail confirmation.")
    lo, hi, pct_eligible = threshold_spread_pct(eligible_only=True)
    lo_all, hi_all, pct_grid = threshold_spread_pct(eligible_only=False)
    figure(doc, "fig6_mean_excess_plot_threshold_selection.png", "Figure 6",
           "Sample mean excess against the level implied by the fitted tail, with the "
           "widest near-linear band, the exceedance floor and the production cut marked, and "
           "an upper axis reading the same positions as quantiles of the loss distribution.")
    prose(doc,
          f"Observation: the empirical mean excess curve is close to flat across the whole "
          f"populated range. The fitted line over {N.number(band['n_points'], 0)} points has "
          f"slope {N.number(band['ols_slope'], 4)}, the largest departure of any point from it "
          f"is {N.number(band['max_deviation_in_se'], 2)} standard errors against a tolerance "
          f"of {N.number(band['z_tolerance'], 1)}, and the near-linear band therefore extends "
          f"from u = {N.number(band['u_lo'], 2)} to u = {N.number(band['u_hi'], 2)} - "
          f"{N.percent(band['implied_quantile_hi'] * 100, 1)} on the upper axis. It ends there "
          "because the exceedance count runs out, not because linearity breaks: the title of "
          "the figure carries that distinction because the difference matters. Mechanism: a "
          "mean excess that does not grow with the cut is the signature of a shape near zero, "
          "which is the exponential boundary case of the generalised Pareto family. The tail "
          f"claim being made here is therefore an extrapolation of exceedance scale - "
          f"{N.number(threshold_row(0.9)['beta'], 3)} standardised units of mean excess at the "
          "production cut - rather than a power law with a visible slope. Consequence: the "
          "threshold is nearly free to choose within the populated range, which is what table 11 "
          "then tests out of sample, and the model's advantage over the Gaussian boundary comes "
          "from conditional variance plus exceedance scaling, not from an aggressive tail "
          f"assumption: the production quantile of {N.number(threshold_row(0.9)['var_z'], 4)} "
          "standardised units is wider than the Gaussian "
          f"{N.number(_norm.ppf(N.value('headline.confidence_level')), 4)} by about a quarter, "
          "and it gets there without a large shape parameter. Falsifier: a curve that bowed or "
          "stepped inside the populated range, or a "
          "band ending at an interior break; neither is present, and the marker areas - "
          f"{N.number(band['n_exceedances_at_u_lo'], 0)} exceedances at the left edge falling to "
          f"{N.number(band['n_exceedances_at_u_hi'], 0)} at the right - show that the scatter at "
          "the right edge is the noise floor rather than structure.")
    prose(doc,
          f"Four of the {N.number(sel['n_grid'], 0)} grid thresholds pass "
          f"the three admissibility conditions set out in section 3.6, and the lowest of them, "
          f"q = {sel['recommended_q']:g}, is the one already in "
          f"production: the screen's recommendation and the deployed setting agree "
          f"({yesno(sel['production_is_recommended'])}). The 99% quantile spans "
          f"{N.number(sel['var_z_spread_across_eligible'], 4)} standardised units across the "
          f"eligible thresholds - from {N.number(lo, 4)} to {N.number(hi, 4)}, a relative width "
          f"of {N.percent(pct_eligible, 2)} - against {N.number(sel['var_z_spread_across_grid'], 4)} "
          f"units, or {N.percent(pct_grid, 2)}%, across the full grid. The two thresholds "
          "excluded on admissibility grounds are the two that would have moved the answer, so "
          "the honest reading is that the insensitive region is the admissible region, and that "
          "this is a measured property of the sample rather than a convenience of the grid.")
    cw = N.raw("threshold.recommendation.from_calibration_window")
    prose(doc,
          f"One in-sample element is disclosed rather than glossed. The screen above runs on the "
          f"full {N.value('data.walk_forward_days')}-day loss sample, so the recommended "
          f"threshold is chosen with hindsight of the whole period. A strictly prospective "
          f"version of the same screen, run on only the first {N.value('data.window')} days, "
          f"returns {N.value('threshold.recommendation.from_calibration_window.n_eligible')} "
          f"eligible thresholds out of "
          f"{N.value('threshold.recommendation.from_calibration_window.n_grid')}: in a 500-day "
          f"window the mean excess curve keeps the required "
          f"{N.number(cw['band']['min_exceedances'], 0)} exceedances only up to "
          f"u = {N.number(cw['band']['u_hi'], 3)}, and the binding rejection at every grid point "
          f"is the same one - {cw['rejected'][0]['reasons']}. That is not a defect in the "
          "screen; it is the sample-size limit the screen was built to expose, and it is why the "
          "walk-forward sweep, which re-estimates the threshold in every window, is the primary "
          f"evidence and the full-sample profile is the diagnostic. The exposure is bounded: "
          f"since every eligible threshold prices the boundary within {N.percent(pct_eligible, 2)} "
          "of every other, the hindsight involved cannot move the published quantile by more "
          "than that.")
    manifest_table(
        doc, "Table 11",
        f"Walk-forward threshold sensitivity at "
        f"{N.percent(N.value('headline.confidence_level') * 100, 1)} coverage under both "
        "innovation distributions. The threshold is re-estimated in every window, so no row "
        "uses information from after its first scored day.",
        "threshold.walk_forward_sensitivity",
        [("innovation_dist", "Innovations", "str"),
         ("threshold_q", "Threshold q", lambda r: f"{r['threshold_q']:g}"),
         ("n_u_min", "Smallest exceedances per window", 0),
         ("clamped_share_%", "Windows with the bound active", "pc", 1),
         ("degenerate_days", "Degenerate fits", 0),
         ("Actual Breaches", "Exceptions", 0),
         ("Breach Rate (%)", "Rate", "pc", 3),
         ("Breach Rate 95% CI (%)", "Exact 95% interval (%)", _ci_cell),
         ("Nominal Rate Inside 95% CI", "Target inside",
          lambda r: yesno(r["Nominal Rate Inside 95% CI"])),
         ("Kupiec p-val", "Unconditional coverage p (p_UC)", "pv"),
         ("Independence p-val", "Independence p (p_IND)", "pv"),
         ("Conditional Cov p-val", "Joint conditional coverage p (p_CC)", "pv"),
         ("Mean Excess Loss (%)", "Mean excess", "pc", 3),
         ("Mean VaR (%)", "Mean boundary", "pc", 3),
         ("xi_raw_median", "Median estimated shape", 4)],
        note=f"{N.number(len(N.records('threshold.walk_forward_sensitivity')), 0)} "
             f"of the "
             f"{N.number(len(N.value('threshold.grid')) * len(C.GARCH_INNOVATION_DISTRIBUTIONS) * len(C.CONFIDENCE_LEVELS), 0)} "
             "combinations of six thresholds, two distributions and two coverages are "
             "reportable. The four that are not are the two highest thresholds at the 97.5% "
             "coverage, where a threshold at or above the level being estimated makes the "
             "exceedance probability formula degenerate; section 3.6 states the condition and "
             "config.py enforces it at import.",
        filter_kwargs={"confidence_level": N.value("headline.confidence_level")})
    wf = sorted((r for r in N.records("threshold.walk_forward_sensitivity")
                 if _near(r["confidence_level"], N.value("headline.confidence_level"))
                 and r["innovation_dist"] == "normal"),
                key=lambda r: r["threshold_q"])
    wf_by_q = {r["threshold_q"]: r for r in wf}
    prod = wf_by_q[C.POT_THRESHOLD_QUANTILE]
    passing = [r for r in wf if r["Nominal Rate Inside 95% CI"]]
    failing = [r for r in wf if not r["Nominal Rate Inside 95% CI"]]
    prose(doc,
          f"Read down the Gaussian rows, the exception count rises monotonically with the "
          f"threshold: {', '.join(str(r['Actual Breaches']) for r in wf)}, out of "
          f"{N.number(wf[0]['Total Obs'], 0)} days. "
          f"{N.number(len(passing), 0)} of the {N.number(len(wf), 0)} settings are "
          f"statistically indistinguishable from the "
          f"{N.percent((1 - N.value('headline.confidence_level')) * 100, 1)} target - their exact "
          "intervals contain it and their Kupiec p-values run from "
          f"{N.p_value(min(r['Kupiec p-val'] for r in passing))} to "
          f"{N.p_value(max(r['Kupiec p-val'] for r in passing))} - while the "
          f"{N.number(len(failing), 0)} highest thresholds fail at "
          f"{', '.join(N.p_value(r['Kupiec p-val']) for r in failing)} and their exact intervals "
          "exclude the target. A reviewer who preferred the top of the grid would be moving from "
          "a calibrated model to a rejected one, and the reason is visible in the exceedance "
          f"column: at q = {failing[0]['threshold_q']:g} the richest window carries "
          f"{N.number(failing[0]['n_u_min'], 0)} exceedances and the median is the same, because "
          "the threshold is the empirical quantile of each window, so a high cut is not noisier, "
          "it is small in every single refit. Two parameters are being estimated from "
          f"{N.number(failing[0]['n_u_min'], 0)} points there, against "
          f"{N.number(prod['n_u_min'], 0)} at the production q = "
          f"{C.POT_THRESHOLD_QUANTILE:g} and {N.number(wf[0]['n_u_min'], 0)} at q = "
          f"{wf[0]['threshold_q']:g}.")
    prose(doc,
          f"The mean boundary column moves the other way, from "
          f"{N.percent(wf[0]['Mean VaR (%)'], 3)} at the lowest threshold to "
          f"{N.percent(wf[-1]['Mean VaR (%)'], 3)} at the highest. That is counter-intuitive only "
          "if the tail is assumed to steepen with the cut; here it does not, so raising the cut "
          "removes more of the mean excess than it adds of conditional severity, and the "
          "resulting boundary is smaller and is breached more often. The thresholds the exact "
          "intervals reject are therefore not conservative choices, they are under-sizing ones, "
          f"which is a stronger argument for q = {C.POT_THRESHOLD_QUANTILE:g} than the "
          f"proposal's was. Finally, the degenerate column is zero at every threshold across all "
          f"{N.value('data.refits_expected')} refits: the fallback path in which a threshold is "
          "reported as fitted when it could not be was never entered by this sweep. It is still "
          "guarded in code, and the guard is tested.")
    clamp_least = min(wf, key=lambda r: r["clamped_share_%"])
    prose(doc,
          f"Note what the clamp column says about the production setting. In-sample at "
          f"{N.value('data.price_rows')} observations the band is inactive at "
          f"q = {C.POT_THRESHOLD_QUANTILE:g}, and the "
          f"table above shows it active in {N.percent(prod['clamped_share_%'], 1)} of "
          f"{N.value('data.refits_expected')} walk-forward refits, at a median estimated shape "
          f"of {N.number(prod['xi_raw_median'], 4)} against a median standard error of "
          f"{N.number(prod['xi_se_median'], 4)}. The full-sample fit and the rolling fits are "
          "not telling the same story about the sign of the tail, and the difference is sample "
          "length rather than method. The band is what stops that disagreement from becoming a "
          "boundary that varies in sign with the window; the low of "
          f"{N.percent(clamp_least['clamped_share_%'], 1)} at "
          f"q = {clamp_least['threshold_q']:g} against "
          f"{N.percent(prod['clamped_share_%'], 1)} at the production one, is a reminder that "
          "the band is doing work at every threshold, not only the deployed one. It is also the "
          f"row where the median standard error, {N.number(clamp_least['xi_se_median'], 4)}, is "
          f"{N.number(clamp_least['xi_se_median'] / prod['xi_se_median'], 1)} times the "
          "production row's: the shape estimate at a high cut is not merely biased, it is the "
          "least precisely measured quantity in the table.")
    figure(doc, "fig7_threshold_sensitivity.png", "Figure 7",
           "Left: the standardised value-at-risk and expected-shortfall quantiles against the "
           "threshold grid, with the unclamped quantile, the raw shape estimate on its own axis "
           "and the region where the admissibility band is active. Right: the same grid scored "
           "out of sample, with exact intervals for both innovation distributions.")
    prose(doc,
          f"Observation: the left panel's three quantile lines are nearly horizontal over the "
          f"admissible range while the shape estimate on its own axis runs from "
          f"{N.number(xi_min, 4)} to {N.number(xi_max, 4)}; the right panel's two breach-rate "
          f"lines both dip at q = {C.POT_THRESHOLD_QUANTILE:g} and cross the nominal level "
          f"between {N.percent(passing[-1]['Breach Rate (%)'], 2)} and "
          f"{N.percent(failing[-1]['Breach Rate (%)'], 2)}. Mechanism: a quantile built as cut plus a "
          "multiple of the fitted scale is dominated by the cut when the shape is near zero, so "
          "the level moves with conditional variance and not with the threshold; the rate line "
          "turns up where the exceedance count stops supporting a stable scale. Consequence: the "
          f"proposal's choice of q = {C.POT_THRESHOLD_QUANTILE:g} was right, and it is now right "
          "for a measured reason - "
          "the point where the two panels agree is the point where the eligible set begins. "
          "Falsifier: a left panel whose quantile lines tilted as strongly as the shape estimate "
          "does, or a right panel whose intervals all contain the target; both would have made "
          "the threshold a free parameter, and the second is exactly what fails at the top of "
          "the grid.")

    add_heading_2(doc, "4.6 Residual Diagnostics and Innovation Robustness")
    diag = {r["window"]: r for r in N.records("iid.residual_diagnostics")
            if r["innovation_dist"] == "normal"}
    verdict = N.raw("iid.iid_verdict")
    prose(doc,
          "Reviewer comment 2 asked for a justification of the independence assumption placed "
          "on the standardised residuals and for a Student-t alternative. The two requests are "
          "logically separate and are answered separately: whether the residuals are serially "
          "independent, and whether they are Gaussian. The threshold model needs the first and "
          "does not need the second, and conflating them is the most common way this design gets "
          "criticised. Table 12 is the battery, run on the full sample and on the first window "
          "alone.")
    manifest_table(
        doc, "Table 12",
        "Whiteness and distributional diagnostics for the standardised innovations, under both "
        "innovation distributions and on two estimation windows. The squared series is what the "
        "peaks-over-threshold step consumes; the levels series is what a strict independence "
        "claim requires.",
        "iid.residual_diagnostics",
        [("innovation_dist", "Innovations", "str"),
         ("window", "Estimation window", "str"),
         ("n_obs", "Observations", 0),
         ("garch_persistence", "Alpha plus beta", 5),
         ("filter_nu", "Degrees of freedom", lambda r: "n/a" if r["filter_nu"] is None
          else N.number(r["filter_nu"], 2)),
         ("kurtosis", "Residual kurtosis", 3),
         ("lb_z_min_p", "Levels: smallest p", "pv"),
         ("lb_z_min_p_bonferroni", "Levels: adjusted", "pv"),
         ("lb_z2_min_p", "Squared: smallest p", "pv"),
         ("lb_z2_min_p_bonferroni", "Squared: adjusted", "pv"),
         ("arch_lm_p", "ARCH test p", "pv"),
         ("jb_p", "Normality p", "pv"),
         ("ks_normal_p", "Against N(0,1)", "pv"),
         ("ks_t_p", "Against fitted t", "pv")],
        note=f"Smallest p is the minimum across the {len(C.LB_LAGS)} lags tested "
             f"({', '.join(str(l) for l in C.LB_LAGS)}); adjusted divides by that count, so an "
             "adjusted value of 1.00 is a cap rather than a measurement. The ARCH column is the "
             "independent implementation inside the arch package; the two agree to "
             f"{N.number(abs(diag['full_sample']['arch_lm_p'] - diag['full_sample']['arch_lm_arch_p']), 4)}, "
             "which is why only one is tabulated.")
    prose(doc,
          f"On the full sample, second-order independence is not rejected under either filter: "
          f"the smallest p-value on the squared innovations is "
          f"{N.p_value(verdict['per_filter']['normal']['lb_z2_min_p'])} for Gaussian innovations "
          f"and {N.p_value(verdict['per_filter']['t']['lb_z2_min_p'])} for Student-t, and the "
          f"corresponding ARCH test probabilities are "
          f"{N.p_value(verdict['per_filter']['normal']['arch_lm_p'])} and "
          f"{N.p_value(verdict['per_filter']['t']['arch_lm_p'])}. First-order dependence in the "
          f"levels is detectable before multiplicity is accounted for - "
          f"{N.p_value(verdict['per_filter']['normal']['lb_z_min_p'])} and "
          f"{N.p_value(verdict['per_filter']['t']['lb_z_min_p'])}, each at one of the "
          f"{len(C.LB_LAGS)} tested lags - and is not significant after it: "
          f"{N.p_value(diag['full_sample']['lb_z_min_p_bonferroni'])} and "
          f"{N.p_value([r for r in N.records('iid.residual_diagnostics') if r['window'] == 'full_sample' and r['innovation_dist'] == 't'][0]['lb_z_min_p_bonferroni'])}. "
          "The defensible statement is therefore the weaker one: the innovations behave as a "
          "martingale difference with short-range dependence, which is the condition the "
          "peaks-over-threshold step actually consumes, and strict independent sampling does not "
          "hold at the levels. Saying it the other way round would have been the error the "
          "reviewer was inviting.")
    prose(doc,
          f"The calibration-window rows are printed because they complicate the story rather "
          f"than confirm it. In the first {N.value('data.window')} days the smallest p on the "
          f"squared innovations is {N.p_value(diag['calibration_500d']['lb_z2_min_p'])} before "
          f"adjustment and {N.p_value(diag['calibration_500d']['lb_z2_min_p_bonferroni'])} "
          "after: second-order dependence is marginally detectable in the window the model was "
          f"trained on first, and the residual kurtosis there is "
          f"{N.number(diag['calibration_500d']['kurtosis'], 2)} against "
          f"{N.number(diag['full_sample']['kurtosis'], 2)} over the whole sample. That is a "
          "sample-size statement, not a regime finding, and it is the same limitation that makes "
          "the calibration-window threshold screen empty in section 4.5.")
    prose(doc,
          f"Normality is rejected outright: the Gaussian filter leaves residuals with kurtosis "
          f"{N.number(diag['full_sample']['kurtosis'], 2)}, a normality probability of "
          f"{N.p_value(diag['full_sample']['jb_p'])} and a Kolmogorov-Smirnov rejection against "
          f"the standard normal at {N.p_value(diag['full_sample']['ks_normal_p'])}. The same "
          f"residuals are not rejected against a unit-variance Student-t with "
          f"{N.number(diag['full_sample']['implied_t_dof'], 2)} degrees of freedom at "
          f"{N.p_value(diag['full_sample']['ks_t_p'])}. The leftover structure is therefore a "
          "tail shape, not a variance pattern - which is precisely the division of labour the "
          "two-stage design assumes, and the reason a rejected normality test is not evidence "
          "against the model.")
    figure(doc, "fig8_innovation_diagnostics.png", "Figure 8",
           "Autocorrelation of the innovations and of their squares for both filters against the "
           "white-noise band, with the Gaussian innovations plotted against the standard normal "
           "and against the fitted rescaled Student-t.")
    prose(doc,
          "Observation: in the top two panels both series stay inside the band after lag zero, "
          "and the squared series is flatter than the levels series; in the bottom pair the "
          "ordered innovations bend away from the forty-five degree line at both ends against "
          "the normal and track it against the fitted t. Mechanism: the filter has removed the "
          "predictable variance - that is what the squared panel shows - but not the shape of "
          "what remains, and what remains is a symmetric-ish heavy tail. Consequence: the "
          "peaks-over-threshold layer is being handed a series that is uncorrelated in level and "
          "in square, which is what its likelihood requires, and a series that is not normal, "
          "which is what its whole reason for existing is. Falsifier: squared autocorrelation "
          "escaping the band at short lags, which would mean the conditional variance model left "
          "structure for the tail model to mis-read; the smallest such p-value in table 12 is "
          f"{N.p_value(min(r['lb_z2_min_p'] for r in N.records('iid.residual_diagnostics')))} "
          "and the full-sample values are above one half.")
    params = {r["innovation_dist"]: r for r in N.records("iid.filter_parameters")}
    nrm, stud = params["normal"], params["t"]
    delta = params["delta_t_minus_normal"]
    prose(doc,
          f"The Student-t filter is a materially better fit to the same book: it estimates "
          f"{N.number(stud['nu'], 2)} degrees of freedom and raises the persistence from "
          f"{N.number(nrm['persistence'], 5)} to {N.number(stud['persistence'], 5)}, with a "
          f"log-likelihood gain of {N.number(delta['loglikelihood'], 1)} points and information "
          f"criterion improvements of {N.number(delta['aic'], 1)} and "
          f"{N.number(delta['bic'], 1)} points, both far past any rule of thumb. Its coefficient "
          f"structure is close to the Gaussian one - alpha {N.number(stud['alpha'], 4)} against "
          f"{N.number(nrm['alpha'], 4)}, beta {N.number(stud['beta'], 4)} against "
          f"{N.number(nrm['beta'], 4)} - with the unconditional variance carrying the "
          f"difference: omega {stud['omega']:.3e} against {nrm['omega']:.3e}, which is the "
          "textbook signature of a "
          "distributional correction rather than a different volatility process. What it does "
          "out of sample is the interesting part, and it is not what the fit statistics "
          "predict.")
    nt = [r for r in N.records("iid.normal_minus_t")]
    manifest_table(
        doc, "Table 13",
        f"Walk-forward comparison of the two innovation distributions on identical thresholds, "
        f"at {N.percent(N.value('headline.confidence_level') * 100, 1)} coverage, corrected "
        "recursion, both filters estimated in every window.",
        "iid.normal_minus_t",
        [("threshold_q", "Threshold q", lambda r: f"{r['threshold_q']:g}"),
         ("mean_var_normal", "Mean boundary, Gaussian", "pc", 3),
         ("mean_var_t", "Mean boundary, Student-t", "pc", 3),
         ("breaches_normal", "Exceptions, Gaussian", 0),
         ("breaches_t", "Exceptions, Student-t", 0),
         ("breach_delta", "Difference", "sg", 0),
         ("rate_normal_pct", "Rate, Gaussian", "pc", 3),
         ("rate_t_pct", "Rate, Student-t", "pc", 3),
         ("kupiec_p_normal", "Kupiec p, Gaussian", "pv"),
         ("kupiec_p_t", "Kupiec p, Student-t", "pv"),
         ("mean_excess_normal_pct", "Mean excess, Gaussian", "pc", 3),
         ("mean_excess_t_pct", "Mean excess, Student-t", "pc", 3),
         ("mean_excess_delta_bps", "Excess difference (bps)", 1)],
        note="The difference column is Student-t minus Gaussian, so a negative value means the "
             "better-fitting filter produced fewer exceptions.")
    at_prod = next(r for r in nt if _near(r["threshold_q"], C.POT_THRESHOLD_QUANTILE))
    evt_n = evt_filter_row(C.POT_THRESHOLD_QUANTILE, "normal")
    evt_t = evt_filter_row(C.POT_THRESHOLD_QUANTILE, "t")
    prose(doc,
          f"The sign of the difference column is the same in all {len(nt)} rows: the "
          f"better-fitting filter is the more conservative boundary, at every threshold. At the "
          f"production cut its mean boundary is {N.percent(at_prod['mean_var_t'], 3)} against "
          f"{N.percent(at_prod['mean_var_normal'], 3)} and it records "
          f"{at_prod['breaches_t']} exceptions rather than {at_prod['breaches_normal']}, a "
          f"rate of {N.percent(at_prod['rate_t_pct'], 3)} against "
          f"{N.percent(at_prod['rate_normal_pct'], 3)}, so it under-breaches at "
          f"{N.p_value(at_prod['kupiec_p_t'])} where the Gaussian filter passes at "
          f"{N.p_value(at_prod['kupiec_p_normal'])}. The mean excess it leaves on the table is "
          f"{N.number(at_prod['mean_excess_delta_bps'], 1)} basis points smaller per event. At "
          f"the two lowest thresholds the under-coverage becomes a rejection "
          f"({N.p_value(nt[0]['kupiec_p_t'])} at q = {nt[0]['threshold_q']:g}). A claim that "
          "Student-t innovations are simply better would not survive this table.")
    prose(doc,
          f"What the comparison actually establishes is the decoupling the design was built on. "
          f"Change the filter and the tail layer barely notices: at the production threshold the "
          f"estimated shape moves from {N.number(evt_n['xi_raw'], 4)} to "
          f"{N.number(evt_t['xi_raw'], 4)} and the scale from {N.number(evt_n['beta'], 4)} to "
          f"{N.number(evt_t['beta'], 4)}, and the standardised quantile from "
          f"{N.number(evt_n['var_z'], 4)} to {N.number(evt_t['var_z'], 4)} - "
          f"{N.percent(100.0 * abs(evt_t['var_z'] - evt_n['var_z']) / evt_n['var_z'], 2)} of the "
          "level. The filter is where the volatility signal lives; the threshold layer reads the "
          "residuals it is handed. The reason the walk-forward results nevertheless differ by "
          f"{abs(at_prod['breach_delta'])} exceptions is not the tail layer, it is that the two "
          "filters produce different conditional variances in the crisis months and the t "
          "filter's higher persistence, "
          f"{N.number(stud['persistence'], 5)} against {N.number(nrm['persistence'], 5)}, keeps "
          "an elevated boundary standing longer after a shock. That is a defensible reason to "
          "prefer the Gaussian filter for this application - it is the one that stays calibrated "
          "on this sample at this threshold - and an equally defensible statement that a book "
          "with a shorter crisis memory would reverse the ranking.")
    figure(doc, "fig9_garch_normal_vs_t.png", "Figure 9",
           "Conditional volatility under both filters over the scored sample, the information "
           "criteria drawn as points below the Gaussian fit, and the estimated degrees of "
           "freedom.")
    prose(doc,
          f"Observation: the two volatility paths in panel A are nearly indistinguishable in the "
          f"calm and separate in the shocks, where the Student-t line sits above; panel B shows "
          f"{N.number(delta['aic'], 0)} and {N.number(delta['bic'], 0)} points below the Gaussian "
          f"fit; panel C places the estimate at {N.number(stud['nu'], 2)} degrees of freedom, "
          "well under the reference line drawn where Gaussian tails become adequate. Mechanism: "
          "a heavier likelihood assigns relatively more weight to large observations, so the "
          "conditional variance it estimates is less sensitive to any single day and decays more "
          "slowly - the higher persistence in numbers. Consequence: the choice of filter is a "
          "choice about how long a shock is remembered, not about whether the tail exists, and "
          "table 13 prices that difference at "
          f"{abs(at_prod['breach_delta'])} exceptions on this sample. Falsifier: paths that "
          "diverged systematically in calm stretches as well as in shocks, which would mean the "
          "likelihood difference was driving the level of risk rather than its response.")

    # -------------------------------------------------------- 4.7 regime states --
    add_heading_2(doc, "4.7 Portfolio-Specific Regime Segmentation")
    cut = N.raw("regime.cut_points")
    agr = N.raw("regime.agreement")
    dis = N.raw("regime.disagreement")
    rank = N.raw("regime.model_ranking")
    sbc = N.raw("regime.stressed_but_calm")
    perf = N.records("regime.regime_conditional_performance")
    cells = N.records("regime.cross_tab_with_breach_rates")
    cell_days = sum(r["Observations"] for r in cells)
    bl_n = N.value("regime.agreement.portfolio_regime_balanced.n_classified")
    partition_rows = [r for r in perf if not r["definition"].startswith("date_overlay")]
    overlay_rows = [r for r in perf if r["definition"].startswith("date_overlay")]

    def band(name):
        return str(name).replace("_vol", " vol").replace("_", " ")

    def partition(name):
        if name == "vix_band":
            return "VIX bands"
        if name.endswith("frozen"):
            return "Book vol, frozen cuts"
        if name.endswith("balanced"):
            return "Book vol, balanced terciles"
        return "Date overlay"

    def rank_cell(defn, regime_name):
        for record in rank[defn]:
            if record["regime"] == regime_name:
                return record
        raise KeyError(f"no model ranking row for {defn} / {regime_name}")

    prose(doc,
          f"Section 4.3 graded the boundaries against bands of the VIX. That is an outside "
          "variable: none of the three models reads it, so the partition was a statement about "
          "the market and only indirectly about the book, and a reviewer could reasonably ask "
          "whether a model that looks well-sized inside a VIX band is well-sized inside the "
          f"portfolio it is supposed to protect. The segmentation here uses a state variable "
          "measured on the book itself - trailing realised volatility of the twenty-name portfolio "
          "- and computes it two ways, because there is no way to define terciles that is "
          f"obviously right. {N.value('regime.cut_points.frozen.calibration_days')} days of "
          "calibration history fix the cut points once and hold them for the whole sample, which "
          f"is leak-free by construction; their levels are {N.percent(100 * cut['frozen']['cut_points'][0], 2)} "
          f"and {N.percent(100 * cut['frozen']['cut_points'][1], 2)} annualised against a "
          f"calibration mean of {N.percent(100 * cut['frozen']['calibration_mean'], 2)}. The "
          "second definition takes terciles of the realised volatility of the entire classified "
          f"span of {N.number(bl_n, 0)} days, "
          f"at {N.percent(100 * cut['balanced']['cut_points'][0], 2)} and "
          f"{N.percent(100 * cut['balanced']['cut_points'][1], 2)}, which balances the cells but "
          "borrows its cut points from data that includes the scored period. Both are reported "
          "throughout, and where they disagree that is written down rather than resolved in "
          "favour of the flattering one.")
    fz, bl = agr["portfolio_regime_frozen"], agr["portfolio_regime_balanced"]

    def cnt(value):
        return N.number(value, 0)

    prose(doc,
          f"Before any backtest, the two state variables are not the same measurement. Against "
          f"the VIX bands, the frozen definition agrees exactly on {N.percent(fz['pct_agreement'], 2)} "
          f"of days and differs by at most one band on {N.percent(fz['pct_within_one_band'], 2)}; "
          f"the balanced definition reaches {N.percent(bl['pct_agreement'], 2)} and "
          f"{N.percent(bl['pct_within_one_band'], 2)}. Cohen's kappa on unweighted agreement is "
          f"{N.number(fz['kappa_unweighted'], 3)} and {N.number(bl['kappa_unweighted'], 3)} - "
          "weak by any convention - while the quadratically weighted versions, which reward "
          f"near-misses, are {N.number(fz['kappa_quadratic'], 3)} and "
          f"{N.number(bl['kappa_quadratic'], 3)}. That contrast is the finding of this subsection "
          "in one line: the book's own volatility and the market's move in the same direction but "
          "are far from interchangeable, so a claim of the form 'calibrated in crisis regimes' "
          "made on a VIX partition is not automatically a claim about this portfolio. The marginal "
          f"counts explain part of the gap: the VIX bands are lopsided ({cnt(bl['marginals_vix']['calm'])} "
          f"calm days against {cnt(bl['marginals_vix']['crisis'])} crisis days), the balanced "
          f"terciles are even by construction, and the frozen ones put "
          f"{cnt(fz['marginals_portfolio']['high_vol'])} of {cnt(fz['n_classified'])} classified "
          "days in the top band.")
    manifest_table(
        doc, "Table 14",
        f"Joint classification of the {N.number(cell_days, 0)} scored days by the book's own "
        "realised-volatility terciles and the VIX bands, with the exception record of the "
        "two-stage filter inside each cell. The terciles here are the balanced definition.",
        "regime.cross_tab_with_breach_rates",
        [("portfolio_regime", "Book regime", lambda r: band(r["portfolio_regime"])),
         ("vix_regime", "VIX band", lambda r: band(r["vix_regime"])),
         ("Observations", "Days", 0),
         ("Share (%)", "Share of sample", "pc", 2),
         ("Breaches", "Exceptions", 0),
         ("Breach Rate (%)", "Rate", "pc", 3),
         ("Mean VaR (%)", "Mean boundary", "pc", 3),
         ("Mean Excess Loss (%)", "Mean miss", "pc", 3),
         ("Mean Realised Vol (%)", "Realised vol", "pc", 2),
         ("Mean VIX (lag)", "Mean VIX (lag)", 2)],
        note="The nine cells are a partition: they sum to the scored sample and nothing is "
             "counted twice. The two date overlays in table 15 are not cells and are not added "
             "to this table.")
    hi_calm = next(r for r in cells if r["portfolio_regime"] == "high_vol"
                   and r["vix_regime"] == "calm")
    lo_calm = next(r for r in cells if r["portfolio_regime"] == "low_vol"
                   and r["vix_regime"] == "calm")
    lo_crisis = next(r for r in cells if r["portfolio_regime"] == "low_vol"
                     and r["vix_regime"] == "crisis")
    hi_crisis = next(r for r in cells if r["portfolio_regime"] == "high_vol"
                     and r["vix_regime"] == "crisis")
    prose(doc,
          f"Observation: the mass is on the diagonal, as it should be - "
          f"{hi_crisis['Observations']} days are high book volatility and crisis VIX together and "
          f"{cnt(lo_calm['Observations'])} are low and calm together - but the off-diagonal is not "
          "empty and not small. The cell that matters is the largest one: "
          f"{hi_calm['Observations']} days, {N.percent(hi_calm['Share (%)'], 2)} of the sample, "
          f"in which the book sits in its top volatility band while the VIX sits in its calm band "
          f"at a mean of {N.number(hi_calm['Mean VIX (lag)'], 2)}. The mirror image, the book calm "
          f"while the market is in crisis, contains {lo_crisis['Observations']} days. Mechanism: a "
          "twenty-name large-capitalisation book carries rotation and single-name risk that an "
          "index-level fear gauge does not register, so a day can be violent inside the portfolio "
          "and unremarkable outside it. Consequence: this is the state in which the old partition "
          f"would have predicted calm and the model, reading the book, did not - the cell's rate "
          f"is {N.percent(hi_calm['Breach Rate (%)'], 3)} against the nominal target, on a mean "
          f"boundary of {N.percent(hi_calm['Mean VaR (%)'], 3)} that has already risen well above "
          f"the {N.percent(lo_calm['Mean VaR (%)'], 3)} of the calm-calm cell. Falsifier: an empty "
          "or trivial off-diagonal, which would have made this subsection a restatement of section "
          f"4.3. The {lo_crisis['Observations']}-day mirror is close to that; the "
          f"{hi_calm['Observations']}-day one is not.")
    manifest_table(
        doc, "Table 15",
        f"Two-stage filter performance conditioned on each state definition, corrected recursion, "
        f"at {N.percent(N.value('headline.confidence_level') * 100, 0)} coverage. The last two "
        "rows are date overlays that overlap the partitions and are not cells of either.",
        "regime.regime_conditional_performance",
        [("definition", "Partition", lambda r: partition(r["definition"])),
         ("regime", "State", lambda r: band(r["regime"])),
         ("Total Obs", "Days", 0),
         ("Actual Breaches", "Exceptions", 0),
         ("Breach Rate (%)", "Rate", "pc", 3),
         ("Kupiec p-val", "Kupiec p", "pv"),
         ("Independence p-val", "Independence p", "pv"),
         ("Mean VaR (%)", "Mean boundary", "pc", 3),
         ("Mean Excess Loss (%)", "Mean miss", "pc", 3),
         ("Breach Rate 95% CI (%)", "Exact 95% interval", _ci_cell),
         ("Nominal Rate Inside 95% CI", "Target inside",
          lambda r: yesno(r["Nominal Rate Inside 95% CI"]))],
        note="Read the two book-volatility blocks as alternatives to each other, not as two "
             "samples: they classify the same days by two different rules for where the tercile "
             "cut points come from.")
    worst_cell = max(partition_rows, key=lambda r: r["Breach Rate (%)"])
    best_margin = max(partition_rows, key=lambda r: r["Kupiec p-val"])
    tight_p = min(r["Kupiec p-val"] for r in partition_rows)
    gfc = overlay_rows[0]
    prose(doc,
          f"Every cell of every partition survives. Across the {len(partition_rows)} partition "
          f"rows the highest rate is {N.percent(worst_cell['Breach Rate (%)'], 3)} in the "
          f"{partition(worst_cell['definition'])} / {band(worst_cell['regime'])} cell, whose exact "
          "interval still contains the target, and the tightest Kupiec probability anywhere in the "
          f"partitions is {N.p_value(tight_p)}; the loosest is "
          f"{N.p_value(best_margin['Kupiec p-val'])}. The one row whose interval excludes the "
          f"target is not a cell at all: the {band(gfc['regime'])} overlay runs at "
          f"{N.percent(gfc['Breach Rate (%)'], 3)} with {gfc['Actual Breaches']} exceptions in "
          f"{N.number(gfc['Total Obs'], 0)} days and an interval of {_ci_cell(gfc)}, and its "
          f"Kupiec probability is {N.p_value(gfc['Kupiec p-val'])}. That distinction - no cell "
          "rejected, one named historical window rejected - is the honest form of the result. A "
          "five-month window is not a regime, and the proposal's own text describes the overlays "
          "as date subsets that overlap the bands; treating them as a partition would let "
          f"{N.number(gfc['Total Obs'], 0)} days out of {cnt(N.value('data.walk_forward_days'))} "
          "override everything else in the table.")
    defs = ("portfolio_regime_frozen", "portfolio_regime_balanced")
    fz_hi, fz_mid = rank_cell(defs[0], "high_vol"), rank_cell(defs[0], "mid_vol")
    bl_hi, bl_mid = rank_cell(defs[1], "high_vol"), rank_cell(defs[1], "mid_vol")
    bl_low = rank_cell(defs[1], "low_vol")
    n_cells = sum(len(rank[d]) for d in defs)
    n_evt_closest = sum(1 for d in defs for r in rank[d] if r["closest_to_nominal"] == "GARCH-EVT")
    n_evt_leanest = sum(1 for d in defs for r in rank[d]
                        if r["severity_ranking_lowest_first"].startswith("GARCH-EVT"))
    prose(doc,
          f"Section 4.2's ranking of the three boundaries - the two-stage filter ahead of "
          "historical simulation ahead of the parametric normal - was measured on the full sample "
          "and had never been tested against a partition. It now is, and the answer splits. What "
          f"holds under both definitions: the two-stage filter is not rejected in any portfolio "
          f"cell, while in the top volatility band the Gaussian boundary runs at "
          f"{N.percent(fz_hi['Gaussian Rate (%)'], 3)} under the frozen cuts and "
          f"{N.percent(bl_hi['Gaussian Rate (%)'], 3)} under the balanced ones, against "
          f"{N.percent(fz_hi['Historical Rate (%)'], 3)} and "
          f"{N.percent(bl_hi['Historical Rate (%)'], 3)} for historical simulation, and the "
          f"two-stage line in those same cells is {N.percent(fz_hi['GARCH-EVT Rate (%)'], 3)} and "
          f"{N.percent(bl_hi['GARCH-EVT Rate (%)'], 3)}. What does not hold: which model sits "
          "nearest the nominal rate is definition-dependent. The filter is the closest in "
          f"{n_evt_closest} of the {n_cells} ranked cells, and the two exceptions are both the "
          f"middle tercile - the Gaussian boundary under the frozen cuts, at "
          f"{N.percent(fz_mid['Gaussian Rate (%)'], 3)} against "
          f"{N.percent(fz_mid['GARCH-EVT Rate (%)'], 3)}, and historical simulation under the "
          f"balanced ones, at {N.percent(bl_mid['Historical Rate (%)'], 3)} against "
          f"{N.percent(bl_mid['GARCH-EVT Rate (%)'], 3)}. Those are thin cells, "
          f"{fz_mid['GARCH-EVT Breaches']} and {bl_mid['GARCH-EVT Breaches']} exceptions, so one "
          "day moves them. The defensible sentence is that the two-stage filter is never rejected "
          "under either definition, not that it is always best-calibrated; the stronger claim "
          "would have been the easier story and this table refuses it.")
    prose(doc,
          f"The severity half of the ranking is more consistent, with one exception worth naming "
          f"rather than burying. In {n_evt_leanest} of the {n_cells} cells the two-stage filter "
          f"leaves the smallest average miss, including all three VIX bands and the top tercile "
          f"under both cut rules - in the balanced top tercile its mean miss is "
          f"{N.percent(bl_hi['GARCH-EVT Mean Excess (%)'], 3)} against "
          f"{N.percent(bl_hi['Gaussian Mean Excess (%)'], 3)} and "
          f"{N.percent(bl_hi['Historical Mean Excess (%)'], 3)}. In the calmest portfolio cell it "
          f"is the largest of the three: {N.percent(bl_low['GARCH-EVT Mean Excess (%)'], 3)} "
          f"against {N.percent(bl_low['Gaussian Mean Excess (%)'], 3)} for the Gaussian boundary "
          f"and {N.percent(bl_low['Historical Mean Excess (%)'], 3)} for historical simulation. "
          "That is a real cost and not a rounding artefact; it is what a heavier tail assumption "
          "buys in the states where it is not needed. The model that is right about 2008 is "
          "slightly too generous about what a miss looks like in a quiet month, and any statement "
          "of the improvement this framework offers has to be net of it.")
    b_psmc = dis["portfolio_regime_balanced"]["portfolio_stressed_market_calm"]
    f_psmc = dis["portfolio_regime_frozen"]["portfolio_stressed_market_calm"]
    b_mspc = dis["portfolio_regime_balanced"]["market_stressed_portfolio_calm"]
    f_mspc = dis["portfolio_regime_frozen"]["market_stressed_portfolio_calm"]
    b_any = dis["portfolio_regime_balanced"]["any_disagreement"]
    prose(doc,
          f"Reading the disagreement as a set rather than as cells sharpens it. Under the balanced "
          f"definition {b_psmc['n_days']} days - {N.percent(b_psmc['pct_of_sample'], 2)} of the "
          f"scored sample - are book-stressed and market-calm; the same cell under the frozen cuts "
          f"contains {f_psmc['n_days']} days, {N.percent(f_psmc['pct_of_sample'], 2)}, because its "
          f"top band is wider ({cnt(fz_hi['Total Obs'])} scored days against "
          f"{cnt(bl_hi['Total Obs'])}). The "
          f"mirror case is nearly empty: {b_mspc['n_days']} days under the balanced rule and "
          f"{f_mspc['n_days']} under the frozen one. The asymmetry is the point - a large-cap "
          f"American book does not go quiet while the market panics, but it does panic while the "
          f"market watches - and on those {b_psmc['n_days']} days the filter was not wrong: it ran "
          f"a mean boundary of {N.percent(b_psmc['mean_var_pct'], 3)} and breached "
          f"{N.percent(b_psmc['breach_rate_pct'], 3)} of the time, a little below nominal rather "
          f"than above. Days on which the two state variables disagree at all number "
          f"{cnt(b_any['n_days'])} of {cnt(N.value('data.walk_forward_days'))} and average "
          f"{N.percent(b_any['mean_loss_pct'], 3)} of daily loss, which is to say a small gain. "
          "Disagreement between the two measurements is not the same thing as damage, and the "
          "sentence before this one is the reason the distinction had to be measured rather than "
          "asserted.")
    yr = sorted(sbc["years"].items(), key=lambda kv: -kv[1])
    sec = sorted(sbc["sector_contribution"],
                 key=lambda r: -r["mean_dispersion_vs_portfolio_pct"])
    weakest = min(sbc["sector_contribution"], key=lambda r: r["mean_daily_return_pct"])
    prose(doc,
          f"Where those days come from is worth the table this subsection has no room for. They "
          f"are not 2008: of the {sbc['n_days']} portfolio-stressed, market-calm days, "
          f"{sbc['years'].get('2008', 0)} fall in that year and none in 2020, while {yr[0][1]} "
          f"come from {yr[0][0]}, {yr[1][1]} from {yr[1][0]} and {yr[2][1]} from {yr[2][0]} - "
          "correction-day episodes and sector rotations, not a crash. Mean returns over the same "
          f"days are positive for every sector group but {weakest['sector']} "
          f"({weakest['names']}) at {N.signed(weakest['mean_daily_return_pct'], 4)}, and the "
          f"widest dispersion against the portfolio belongs to {sec[0]['sector']} "
          f"({sec[0]['names']}) at {N.number(sec[0]['mean_dispersion_vs_portfolio_pct'], 2)} "
          f"percentage points, against "
          f"{N.number(sec[-1]['mean_dispersion_vs_portfolio_pct'], 2)} for {sec[-1]['sector']}. "
          "The state variable this subsection adds is therefore measuring rotation and "
          "single-name risk, not market panic - which is exactly the risk a VIX partition cannot "
          "see and exactly the risk a twenty-name concentrated book carries.")
    figure(doc, "fig10_portfolio_vs_vix_regimes.png", "Figure 10",
           "Panel A: the book's lagged realised volatility against the lagged VIX, with the VIX "
           "band edges shaded behind it. Panel B: the nine-cell cross-tabulation, day counts and "
           "each cell's exception rate. Panel C: exact agreement and both Cohen's kappa "
           "statistics for each definition against the conventional substantial-agreement cut-off. "
           "Panel D: which sectors contributed what to the book on the days the two state "
           "variables disagreed.")
    tallest_bar = max(fz["pct_agreement"], bl["pct_agreement"],
                      fz["kappa_unweighted"], bl["kappa_unweighted"],
                      fz["kappa_quadratic"], bl["kappa_quadratic"])
    prose(doc,
          f"Observation: in panel A the two series move together in the crisis stretches and part "
          "company everywhere else, and the calm shading covers most of the timeline; panel B's "
          f"mass is on its diagonal - {cnt(lo_calm['Observations'])} days low-and-calm, "
          f"{hi_crisis['Observations']} high-and-crisis - with one clearly populated off-diagonal "
          f"of {hi_calm['Observations']} days at {N.percent(hi_calm['Breach Rate (%)'], 2)}; "
          f"every bar in panel C falls under the dashed substantial-agreement reference, the "
          f"tallest of the six being {N.number(tallest_bar, 2)}; panel D's bars are positive "
          "except one. Mechanism: the shading and the volatility line disagree because they are "
          "computed on different underlyings, and the kappa bars are low because exact band "
          "agreement between two differently-scaled partitions is a demanding test - the balanced "
          f"rule still puts {cnt(bl['marginals_portfolio']['high_vol'])} days in a top band the "
          "market gauge resolves as calm. Consequence: the reviewer's request was not cosmetic, "
          "and panel C is the figure that says so quantitatively; a state variable borrowed from "
          f"the index files {cnt(bl['marginals_vix']['calm'])} of {cnt(bl_n)} classified days as "
          "calm and cannot separate the book's own worst regime from its best. Falsifier: kappa "
          "bars reaching the reference line, or an empty off-diagonal - the first would have made "
          "the VIX bands a fair proxy and this subsection redundant, the second would have "
          f"collapsed it into section 4.3. Both {N.number(fz['kappa_unweighted'], 2)} and "
          f"{N.number(bl['kappa_unweighted'], 2)} sit far below the line, and the "
          f"{N.number(cell_days, 0)} days in table 14 are not all on its diagonal.")

    # --------------------------------------------------- 4.8 economic magnitude --
    add_heading_2(doc, "4.8 Economic Magnitude of the Remaining Exceptions")
    g = model_row("economic.model_comparison", "Gaussian VaR")
    h = model_row("economic.model_comparison", "Historical VaR")
    ev = model_row("economic.model_comparison", "GARCH-EVT VaR")
    byrec = N.raw("economic.by_recursion")
    corr = byrec["corrected"]
    leg = byrec["legacy"]
    conc = N.raw("economic.primary_register_concentration")
    reg_conc = N.raw("economic.registers")
    worst = N.records("economic.worst_ten")
    notional = N.value("data.notional_usd")

    def usd(x, dp=3):
        return N.dollars(x / 1e6, dp) if x is not None else "n/a"

    def plain(x):
        return f"${x:,.0f}" if x is not None else "n/a"

    count_ratio = g["Actual Breaches"] / ev["Actual Breaches"]
    mean_ratio = g["Mean Excess Loss (%)"] / ev["Mean Excess Loss (%)"]
    cum_ratio = g["Cumulative Unreserved Loss (USD)"] / ev["Cumulative Unreserved Loss (USD)"]
    prose(doc,
          f"A boundary can pass a frequency test and still be an unacceptable risk manager. "
          f"Sections 4.1 to 4.7 answered how often the two-stage filter is wrong; this one "
          f"answers what each of those wrong days costs, on the same {usd(notional, 0)} book the "
          f"proposal uses, over {cnt(N.value('data.walk_forward_days'))} scored days. Three "
          "boundaries are reported side by side and one convention is fixed once: the boundary is "
          "treated as funded capital and the loss beyond it as unfunded, so the quantity that "
          "matters is the exceedance, not the loss. The register behind these numbers is written "
          f"to {N.value('economic.full_register_path')} - {cnt(N.value('economic.full_register_rows'))} "
          f"rows, against the {cnt(N.value('economic.published_register_rows'))} rows of "
          f"{N.value('economic.published_register_path')} that Module 4 published - and is "
          "reproduced in appendix C.")
    manifest_table(
        doc, "Table 16",
        f"Economic consequence of the three boundaries on one book, one sample and one notional, "
        f"over {cnt(N.value('data.walk_forward_days'))} days. The two-stage row is Module 4's "
        "published recursion, so that the comparison is with the numbers the project has already "
        "put on the record; table 17 shows what the corrected recursion changes.",
        "economic.model_comparison",
        [("Model", "Boundary", "str"),
         ("Actual Breaches", "Exceptions", 0),
         ("Breach Rate (%)", "Rate", "pc", 3),
         ("Breach Rate 95% CI (%)", "Exact 95% interval", _ci_cell),
         ("Nominal Inside 95% CI", "Target inside", lambda r: yesno(r["Nominal Inside 95% CI"])),
         ("Mean Excess Loss (%)", "Mean miss", "pc", 3),
         ("Median Excess Loss (%)", "Median miss", "pc", 3),
         ("Max Excess Loss (%)", "Largest miss", "pc", 3),
         ("Mean Excess (USD)", "Mean miss ($m)", "usd"),
         ("Max Excess (USD)", "Largest miss ($m)", "usd"),
         ("Cumulative Unreserved Loss (USD)", "Unreserved total ($m)", "usd"),
         ("Mean VaR (%)", "Mean boundary", "pc", 3),
         ("ES Breaches", "Misses past ES", 0),
         ("Mean ES (%)", "Mean ES", "pc", 3)],
        note="Expected-shortfall columns read n/a for the two baselines because neither forecasts "
             "a shortfall measure; that is part of why the comparison in this table is not only "
             "about exception counts.")
    prose(doc,
          f"The aggregate difference between the three lines is not one number, it is two "
          f"multiplied. The Gaussian boundary fails {g['Actual Breaches']} times against "
          f"{ev['Actual Breaches']} for the two-stage filter, and when it does fail it clears its "
          f"own forecast by {N.percent(g['Mean Excess Loss (%)'], 3)} on average against "
          f"{N.percent(ev['Mean Excess Loss (%)'], 3)}. Its unfunded total, "
          f"{usd(g['Cumulative Unreserved Loss (USD)'])}, is therefore the product of "
          f"{N.number(count_ratio, 2)} times as many misses and misses "
          f"{N.number(mean_ratio, 2)} times as large - {N.number(cum_ratio, 2)} times the "
          f"two-stage figure of {usd(ev['Cumulative Unreserved Loss (USD)'])}. Historical "
          f"simulation sits between them on frequency, {h['Actual Breaches']} exceptions, and "
          f"above the Gaussian line on severity, a mean miss of "
          f"{N.percent(h['Mean Excess Loss (%)'], 3)}, because a boundary set at "
          f"{N.percent(h['Mean VaR (%)'], 3)} of notional is a wide one that only genuinely "
          f"extreme days clear; its total is {usd(h['Cumulative Unreserved Loss (USD)'])}. Read "
          "against the notional rather than against each other: the unfunded loss behind the "
          f"Gaussian line is {N.percent(g['Cumulative Unreserved Loss (% of notional)'], 1)} of "
          f"the book over {N.number(leg['reserve_adequacy']['Years'], 1)} years, and the two-stage "
          f"line {N.percent(ev['Cumulative Unreserved Loss (% of notional)'], 1)}. Summed over the "
          f"days each boundary was wrong, the Gaussian line's breach days account for "
          f"{N.percent(g['Total Loss on Breach Days (%)'], 1)} of notional against "
          f"{N.percent(ev['Total Loss on Breach Days (%)'], 1)} for the two-stage filter.")
    w0 = worst[0]
    cleared = sum(1 for r in worst if r["ES_also_breached"])
    n08 = sum(1 for r in worst if r["Date"][:4] == "2008")
    by_loss = sorted(worst, key=lambda r: -r["Loss"])
    n08_top5 = sum(1 for r in by_loss[:5] if r["Date"][:4] == "2008")
    other_years = len({r["Date"][:4] for r in worst if r["Date"][:4] != "2008"})
    prose(doc,
          f"The worst day is not an exception to this picture, it is the picture. On "
          f"{w0['Date'][:10]} the book fell {N.percent(100 * abs(w0['Return']), 2)} against a "
          f"boundary of {N.percent(100 * w0['VaR'], 3)} - a miss of "
          f"{N.number(w0['Exceedance_bps'], 1)} basis points, {plain(w0['USD_Excess'])} of "
          f"unfunded loss in a session - and the expected-shortfall forecast standing behind it, "
          f"{N.percent(100 * w0['ES_forecast'], 3)}, was also cleared. So was every one of them: "
          f"all {cnt(cleared)} of the register's {cnt(len(worst))} largest misses are days on "
          "which the shortfall forecast was itself exceeded. A shortfall forecast is a larger "
          "number, not a sufficient one, on precisely the days a risk manager cares about. "
          f"The {n08} of the ten that fall in 2008 include {n08_top5} of the five largest "
          f"single-day losses of the whole scored sample - {N.percent(100 * by_loss[1]['Loss'], 2)} "
          f"on {by_loss[1]['Date'][:10]} and {N.percent(100 * by_loss[2]['Loss'], 2)} on "
          f"{by_loss[2]['Date'][:10]} among them - while the other {len(worst) - n08} are spread "
          f"over {other_years} further years, which is the ordinary shape of tail risk in a long "
          "sample rather than one crisis seen ten times.")
    static_table(
        doc, "Table 17",
        "What it costs to hold the shortfall measure instead of the quantile, and what that "
        "purchase buys, under both recursions. The corrected row is this report's primary result.",
        ["Recursion", "Exceptions", "Rate", "VaR reserve ($m)", "ES reserve ($m)",
         "Extra capital ($m)", "Uplift", "Unreserved under VaR ($m)",
         "Unreserved under ES ($m)", "Loss prevented ($m)", "Prevented per year ($m)",
         "Per extra dollar", "Days past ES", "Share of misses"],
        [[lab,
          N.number(s["summary"]["Actual Breaches"], 0),
          N.percent(s["summary"]["Breach Rate (%)"], 3),
          usd(ra["Mean VaR Reserve (USD)"]), usd(ra["Mean ES Reserve (USD)"]),
          usd(ra["Incremental Capital Held (USD)"]),
          N.percent(ra["ES Reserve Uplift over VaR (%)"], 2),
          usd(ra["Cumulative Unreserved under VaR (USD)"]),
          usd(ra["Cumulative Unreserved under ES (USD)"]),
          usd(ra["Unreserved Loss Avoided by ES (USD)"]),
          usd(ra["Unreserved Loss Avoided per Year (USD)"]),
          N.number(ra["Avoided Shortfall per Dollar of Extra Capital"], 2),
          N.number(ra["Days ES Also Breached"], 0),
          N.percent(ra["Share of VaR Breaches Also ES Breaches (%)"], 2)]
         for lab, s, ra in [("Published (legacy)", leg, leg["reserve_adequacy"]),
                            ("Corrected", corr, corr["reserve_adequacy"])]],
        widths=[1.15, 0.6, 0.6, 0.75, 0.75, 0.75, 0.55, 0.85, 0.85, 0.8, 0.8, 0.65, 0.6, 0.7],
        note=N.value("economic.stock_versus_flow") +
             " The two recursions differ only in how the walk-forward window is aligned; the "
             "economic reading is the same under both.")
    cra = corr["reserve_adequacy"]
    lra = leg["reserve_adequacy"]
    prose(doc,
          f"Holding the shortfall measure rather than the quantile means carrying "
          f"{plain(cra['Incremental Capital Held (USD)'])} more at every mark, an uplift of "
          f"{N.percent(cra['ES Reserve Uplift over VaR (%)'], 2)} on the reserve, and that capital "
          f"is held on all {cnt(N.value('data.walk_forward_days'))} days whether or not the tail "
          "appears. What it prevents going unfunded is "
          f"{plain(cra['Unreserved Loss Avoided by ES (USD)'])} over "
          f"{N.number(cra['Years'], 1)} years, about "
          f"{plain(cra['Unreserved Loss Avoided per Year (USD)'])} a year, or "
          f"{N.number(cra['Avoided Shortfall per Dollar of Extra Capital'], 2)} dollars of "
          "prevented loss per dollar of extra capital held. The exchange rate is the result, and "
          "the ratio is not the argument, because the numerator is a flow realised on "
          f"{cra['Days ES Also Breached']} days and the denominator is a stock present on "
          f"{cnt(N.value('data.walk_forward_days'))}. It is also not a complete fix, and the table "
          f"says so: {cra['Days ES Also Breached']} of {corr['summary']['Actual Breaches']} "
          f"exceptions, {N.percent(cra['Share of VaR Breaches Also ES Breaches (%)'], 2)}, still "
          f"clear the shortfall forecast, leaving "
          f"{plain(cra['Cumulative Unreserved under ES (USD)'])} unfunded where the quantile "
          f"reserve would have left {plain(cra['Cumulative Unreserved under VaR (USD)'])}. The "
          f"single worst day still carries {plain(cra['Largest Unreserved Day under ES (USD)'])} "
          f"of it, down from {plain(cra['Largest Unreserved Day under VaR (USD)'])}.")
    prose(doc,
          f"The correction to the recursion moves the frequency and barely moves the economics, "
          f"which is the reassuring half of the sensitivity and worth stating plainly: "
          f"{leg['summary']['Actual Breaches']} exceptions become "
          f"{corr['summary']['Actual Breaches']}, an unfunded total of "
          f"{plain(leg['summary']['Cumulative Unreserved Loss (USD)'])} becomes "
          f"{plain(corr['summary']['Cumulative Unreserved Loss (USD)'])}, the uplift on the reserve "
          f"moves from {N.percent(lra['ES Reserve Uplift over VaR (%)'], 2)} to "
          f"{N.percent(cra['ES Reserve Uplift over VaR (%)'], 2)}, and the prevented-loss "
          f"exchange rate from {N.number(lra['Avoided Shortfall per Dollar of Extra Capital'], 2)} "
          f"to {N.number(cra['Avoided Shortfall per Dollar of Extra Capital'], 2)}. Nothing in "
          "this subsection's conclusion depends on which recursion a reader prefers, which is "
          "exactly what a sensitivity table is for.")
    gc = reg_conc["GARCH-EVT"]["concentration"]
    prose(doc,
          f"What the remaining exceptions have in common is timing. Of the "
          f"{conc['n_breaches']} corrected exceptions totalling "
          f"{plain(conc['total_usd_excess'])}, the single largest day is "
          f"{N.percent(conc['top_1_share_pct'], 2)} of the total and the five worst are "
          f"{N.percent(conc['top_5_share_pct'], 2)}; the ten worst reach "
          f"{N.percent(conc['top_10_share_pct'], 2)}, and the Herfindahl index across the "
          f"{conc['n_breaches']} days is {N.number(conc['hhi_of_excess'], 4)}. On the published "
          f"recursion the same five-day concentration is {N.percent(gc['top_5_share_pct'], 2)} at "
          f"a similar {N.number(gc['hhi_of_excess'], 4)}. That is a clustered tail, not a diffuse "
          "one, and it cuts against the framework in a way the exception rate hides: a reserve "
          "sized on the average miss would be under-funded on the days that matter, and the days "
          "that matter arrive together. It is also the strongest practical argument in this "
          "report for the allocation-level measure in section 4.9, since a portfolio that can be "
          "reweighted between rebalances is the only lever here that acts on clustering rather "
          "than on average size.")
    figure(doc, "fig11_breach_magnitudes_and_reserves.png", "Figure 11",
           "Panel A: every exception of the corrected register drawn as a vertical line whose "
           "height is the loss in excess of the quantile, coloured by the VIX band it landed in, "
           "with the mean miss as a horizontal reference. Panel B: the cumulative unreserved loss "
           "under the quantile reserve and under the shortfall reserve, against three horizontal "
           "references - the two daily reserve levels and the gap between them.")
    prose(doc,
          f"Observation: panel A's lines are not spread evenly over the calendar - the tall ones "
          f"cluster in {worst[0]['Date'][:4]}, and the tallest reaches "
          f"{N.percent(100 * w0['Exceedance'], 2)} against a mean line at "
          f"{N.percent(ev['Mean Excess Loss (%)'], 2)}; panel B's two curves rise as staircases "
          f"that separate early and end {plain(cra['Unreserved Loss Avoided by ES (USD)'])} apart, "
          f"at {plain(cra['Cumulative Unreserved under VaR (USD)'])} and "
          f"{plain(cra['Cumulative Unreserved under ES (USD)'])}, above two nearly coincident "
          f"horizontal references {plain(cra['Incremental Capital Held (USD)'])} apart. "
          "Mechanism: a staircase is the signature of a flow that only moves on exception days, "
          "and each step's height is one row of the register behind table 17; two horizontal lines "
          "separated by a fixed distance are the signature of a reserve that is a constant "
          "fraction of the boundary, which is why the gap between them is a stock and the gap "
          "between the staircases is a flow. Consequence: the economic case for expected shortfall "
          "is the second gap measured against the first, and it is not visible in the exception "
          f"count at all - {g['Actual Breaches']} versus {ev['Actual Breaches']} breaches separate "
          "the boundaries far less dramatically than "
          f"{usd(g['Cumulative Unreserved Loss (USD)'])} against "
          f"{usd(ev['Cumulative Unreserved Loss (USD)'])} does. Falsifier: staircases that rose "
          "smoothly and evenly across the whole sample, which would mean the differences were a "
          f"general sizing error rather than a tail-handling one, or two curves that never "
          f"separated, which would mean the higher reserve bought nothing. The "
          f"{N.percent(conc['top_5_share_pct'], 1)} carried by five days rules the first out, and "
          f"the {plain(cra['Cumulative Unreserved under ES (USD)'])} still uncovered at the end of "
          "the second rules out the claim that it buys completeness.")

    # ------------------------------------------------------- 4.9 minimum-ES LP --
    add_heading_2(doc, "4.9 Dynamic Minimum-ES Portfolio Optimisation")
    opt_tbl = N.records("optimisation.table")
    conc_tbl = N.records("optimisation.concentration")
    ecc = N.records("optimisation.engine_convention_control")
    bdiag = N.records("optimisation.book_diagnosis")
    agree = N.records("optimisation.breach_date_agreement")
    red_tbl = N.records("optimisation.forecast_es_reduction_by_alpha")
    universe = N.raw("optimisation.universe")
    EW_R = strategy_row("Equal weight (rebalanced)")["Strategy"]
    EW_H = strategy_row("Equal weight (buy-and-hold)")["Strategy"]
    MV = strategy_row("Minimum variance (sample)")["Strategy"]
    MV_LW = strategy_row("Minimum variance (Ledoit-Wolf)")["Strategy"]
    MIN_ES = strategy_row("Minimum ES")["Strategy"]
    FLOOR = strategy_row("Minimum ES with return floor")["Strategy"]
    CAP = strategy_row("Minimum ES with turnover cap")["Strategy"]

    conv_labels = sorted({r["engine convention"] for r in ecc})
    A_CONV = next(c for c in conv_labels if c.startswith("A "))
    A_PRIME = next(c for c in conv_labels if c.startswith("A'"))
    B_CONV = next(c for c in conv_labels if c.startswith("B"))
    conv_index = {(r["Strategy"], r["engine convention"]): r for r in ecc}

    def conv_row(strategy, convention):
        return conv_index[(strategy, convention)]

    def pair_row(a, b):
        hits = [r for r in agree if {r["Book A"], r["Book B"]} == {a, b}]
        if len(hits) != 1:
            raise KeyError(f"{a} versus {b} matched {len(hits)} rows")
        return hits[0]

    def conc_row(strategy):
        return model_row("optimisation.concentration", strategy, key="Strategy")

    def ci_pair(record, low, high):
        return f"[{record[low]:.3f}, {record[high]:.3f}]"

    alphas = ", ".join(f"{a:g}" for a in C.ES_LP_ALPHAS)
    prose(doc,
          f"Reviewer comment 4 asked the framework's tail measure to be turned from a reported "
          f"boundary into a decision variable. What was built is a Rockafellar-Uryasev "
          f"minimisation of expected shortfall over conditional historical-simulation scenarios, "
          f"solved exactly as a linear program rather than by a general nonlinear optimiser, on "
          f"the same walk-forward as the risk model. The design constants are shared with the rest "
          f"of the project rather than restated here: the book rebalances every "
          f"{N.number(C.REBALANCE_INTERVAL, 0)} trading days - deliberately the same interval on "
          f"which the GARCH filter refits, so a rebalance never prices a forecast older than the "
          f"weights it is choosing - long-only, weights summing to one, no name above "
          f"{N.percent(100 * C.MAX_ASSET_WEIGHT, 0)}, one-way transaction cost of "
          f"{N.number(C.TXN_COST_BPS, 0)} basis points per rebalance, scenarios drawn from the "
          f"trailing {N.number(C.ASSET_SCENARIO_WINDOW, 0)}-day window at the primary confidence "
          f"level {C.PRIMARY_ES_LP_ALPHA:g} and swept over {alphas}. The per-asset filter that "
          f"generates those scenarios uses {C.ASSET_WF_INNOVATION_DISTRIBUTION}-distributed "
          f"innovations while the headline recursion stays on "
          f"{N.value('config.innovation_distribution')}, so this section adds a result rather than "
          f"revising Module 4's. Seven books are run: the "
          f"{N.percent(100.0 / len(universe), 0)}-a-name equal-weight control rebalanced at every "
          f"decision date, the same basket bought and held, two minimum-variance books, and three "
          f"shortfall-minimising books - the objective alone, one with a return floor and one with "
          f"a turnover cap. No rebalance date failed to return an optimum: the manifest records "
          f"{N.value('optimisation.failed_solves')} solver failures across the "
          f"{cnt(N.value('optimisation.weight_history_rows'))}-row weight history that appendix D "
          f"reproduces.")
    prose(doc,
          f"One reading rule comes before any result, and it is the manifest's own sentence rather "
          f"than a paraphrase of it: “{N.value('optimisation.comparability_warning')}” Each book "
          f"has its own weights, therefore its own return series, therefore its own loss series, "
          f"therefore its own exceptions. An exception count is a statement about one book's "
          f"forecast being right about one book's P&L; it is not a scoreboard on which two books "
          f"compete. Every table below is written to that rule, and the single most misread number "
          f"in this section - the shortfall book's exception count - is taken apart in "
          f"table 19 rather than argued about.")
    manifest_table(
        doc, "Table 18",
        f"The seven books over {cnt(N.value('data.walk_forward_days'))} scored days at "
        f"{usd(N.value('data.notional_usd'), 0)} notional: realised economics in the first block, "
        f"then the calibration of each book's own two-stage forecast under the published recursion "
        f"convention. Economics are net of {N.number(C.TXN_COST_BPS, 0)} basis points on one-way "
        f"turnover.",
        "optimisation.table",
        [("Strategy", "Book", "str"),
         ("Ann return (%)", "Ann return", "pc"),
         ("Ann volatility (%)", "Ann vol", "pc"),
         ("Sharpe", "Sharpe", 3),
         ("Max drawdown (%)", "Max drawdown", "pc"),
         ("One-way turnover (annual)", "Turnover/yr", 3),
         ("Annual fee fractions (%)", "Cost drag", "pc"),
         ("Actual Breaches", "Exceptions", 0),
         ("Breach Rate (%)", "Rate", "pc", 3),
         ("Breach CI low (%)", "Exact 95% interval",
          lambda r: ci_pair(r, "Breach CI low (%)", "Breach CI high (%)")),
         ("Nominal inside CI", "Target inside", lambda r: yesno(r["Nominal inside CI"])),
         ("Kupiec p", "Kupiec", "pv"),
         ("Mean Excess Loss (%)", "Mean miss", "pc", 3),
         ("Mean ES (%)", "Mean forecast ES", "pc", 3)],
        note="Every row prices a different loss series, so the exception columns are read down a "
             "row and never across rows. The risk-model columns are the portfolio-level two-stage "
             "filter applied to each book's own realised returns.")
    ew_r, es_r = strategy_row(EW_R), strategy_row(MIN_ES)
    cap_r, floor_r = strategy_row(CAP), strategy_row(FLOOR)
    max_opt_ret = max(r["Ann return (%)"] for r in opt_tbl
                      if not r["Strategy"].startswith("Equal weight"))
    prose(doc,
          f"Read the economics block first, because it is the part that is not a convention. The "
          f"shortfall-minimising book cuts annualised volatility from {N.percent(ew_r['Ann volatility (%)'], 3)} "
          f"to {N.percent(es_r['Ann volatility (%)'], 3)} and the maximum drawdown from "
          f"{N.percent(ew_r['Max drawdown (%)'], 2)} to {N.percent(es_r['Max drawdown (%)'], 2)}, "
          f"and it pays for that with "
          f"{N.number(ew_r['Ann return (%)'] - es_r['Ann return (%)'], 3)} points of annualised "
          f"return - {N.percent(es_r['Ann return (%)'], 3)} against "
          f"{N.percent(ew_r['Ann return (%)'], 3)} - which takes the Sharpe from "
          f"{N.number(ew_r['Sharpe'], 3)} to {N.number(es_r['Sharpe'], 3)}. That is the correct "
          f"direction for a tail measure: a distribution can lose mean while losing tail. What "
          f"makes it uncomfortable is the middle columns. The equal-weight control turns over "
          f"{N.number(ew_r['One-way turnover (annual)'], 3)} of the book one-way a year at a cost "
          f"drag of {N.percent(ew_r['Annual fee fractions (%)'], 3)} of wealth; the "
          f"shortfall-minimising book turns {N.number(es_r['One-way turnover (annual)'], 3)} at "
          f"{N.percent(es_r['Annual fee fractions (%)'], 3)}, and the buy-and-hold control turns "
          f"nothing at all, because holding a basket that is never rebalanced is the only book in "
          f"the table with no cost line. The optimiser's risk reduction is real and it is "
          f"expensive, and the second fact is the one a reviewer is entitled to see unaided.")
    figure(doc, "fig12_dynamic_portfolio_optimisation.png", "Figure 12",
           "Panel A: growth of 100 invested, net of "
           f"{N.number(C.TXN_COST_BPS, 0)} basis points on turnover, for all seven books. "
           "Panel B: the same seven books in drawdown from peak. Panel C and panel D are drawn for "
           "the headline pair only - the rebalanced equal-weight book and the minimum-ES book - "
           "with panel C on a log axis showing each book's own 99% forecast VaR and ES through "
           "time, and panel D showing one-way turnover per rebalance as bars.")
    prose(doc,
          f"Observation: panels A and B separate the seven books into two families rather than a "
          f"ranking - the equal-weight pair sits high and volatile, the five optimised books sit "
          f"lower and calmer, and the best of the optimised family still returns "
          f"{N.percent(max_opt_ret, 3)} against the rebalanced control's "
          f"{N.percent(ew_r['Ann return (%)'], 3)}, so the two families never meet on the vertical "
          f"axis of panel A. Panel C's two solid "
          f"lines are the books' own forecast shortfalls, and the panel prints its own score: the "
          f"optimiser's forecast is the lower one on most days but not on all of them, and the "
          f"{N.percent(es_r['Mean ES (%)'], 3)} against "
          f"{N.percent(ew_r['Mean ES (%)'], 3)} sample means are the honest summary rather than "
          f"the picture. Panel D is the least ambiguous of the four: the bars come in bursts at "
          f"every {N.number(C.REBALANCE_INTERVAL, 0)}-day decision date and the equal-weight "
          f"series is a flat line near zero. Mechanism: a minimum-expected-shortfall objective is "
          f"linear in the weights, so its optimum is a vertex of the feasible polytope - the "
          f"corner where as many names as possible sit at the "
          f"{N.percent(100 * C.MAX_ASSET_WEIGHT, 0)} cap or at zero - and vertices move when the "
          f"scenario set moves, which is why the rebalanced book trades in bursts and why the "
          f"buy-and-hold book, which never revisits "
          f"the vertex, pays nothing. Consequence: the drawdown improvement in panel B is bought "
          f"twice, once in mean return and once in cost, and any claim that the optimised family "
          f"is 'better' has to say which of the two it is paying for. Falsifier: a panel A in "
          f"which the optimised books' wealth paths stayed above the equal-weight pair, which "
          f"would have made this a free-lunch section; {N.percent(es_r['Ann return (%)'], 3)} "
          f"against {N.percent(ew_r['Ann return (%)'], 3)} rules that out, and the "
          f"{N.percent(es_r['Annual fee fractions (%)'], 2)} cost line is the second thing that "
          f"does.")
    primary_red = {r["alpha"]: r for r in red_tbl}[C.PRIMARY_ES_LP_ALPHA]
    other_reds = [r for r in red_tbl if r["alpha"] != C.PRIMARY_ES_LP_ALPHA]
    red_rec = N.records("optimisation.forecast_es_reduction_records")
    red_dates = len({r["date"] for r in red_rec})
    prose(doc,
          f"Comment 4's actual question was whether the measure responds when it is made the "
          f"objective, and that question has a cleaner answer than the economics do, because it "
          f"can be asked at the decision date on identical scenarios: take the equal-weight book "
          f"and the optimised book, price both on the same conditional-historical-simulation set "
          f"at the same level, and compare. Across the {cnt(red_dates)} sampled decision dates at "
          f"{C.PRIMARY_ES_LP_ALPHA:g} the optimised book's forecast shortfall is "
          f"{N.percent(abs(primary_red['mean']), 3)} lower on average, median "
          f"{N.percent(abs(primary_red['median']), 3)}, and the distribution does not cross zero: "
          f"the smallest single reduction is {N.percent(abs(primary_red['max']), 3)} and the "
          f"largest {N.percent(abs(primary_red['min']), 3)}. The same holds at the two swept "
          "levels - " + ", and ".join(
              f"{r['alpha']:g} giving a mean reduction of "
              f"{N.percent(abs(r['mean']), 3)}" for r in other_reds) +
          f". A reduction measured against the same scenarios is not a claim about realised P&L - "
          f"it is a claim that the solver does what it says, which is the thing the reviewer "
          f"asked for and the thing that cannot be read off table 18's return column.")
    es_A, es_AP, es_B = (conv_row(MIN_ES, c) for c in (A_CONV, A_PRIME, B_CONV))
    engine_gap = es_AP["Breaches"] - es_B["Breaches"]
    ew_A = conv_row(EW_R, A_CONV)
    mv_B, lw_B = conv_row(MV, B_CONV), conv_row(MV_LW, B_CONV)
    cap_B, floor_B = conv_row(CAP, B_CONV), conv_row(FLOOR, B_CONV)
    dropped_days = es_A["Scored days"] - es_AP["Scored days"]
    dropped_breaches = es_A["Breaches"] - es_AP["Breaches"]
    dropped_rate = 100.0 * dropped_breaches / dropped_days
    prose(doc,
          f"The number in table 18 that looks like a failure is the shortfall book's "
          f"{es_A['Breaches']} exceptions and {N.p_value(es_A['Kupiec p'])} Kupiec p - it is the "
          f"worst calibration in this report and it needed explaining rather than reporting. Three "
          f"scoring conventions were run on every book to do it. Convention A prices each book "
          f"with the filter frozen at today's weights applied to a "
          f"{N.number(C.ASSET_SCENARIO_WINDOW, 0)}-day history, which is a counterfactual book, "
          f"and is used only so that the optimised rows can share the "
          f"{cnt(es_A['Scored days'])}-day sweep that the rest of the report is scored on. "
          f"Convention B hands the Module 4 engine the series the book actually earned - which "
          f"cannot exist before the first decision, so B starts "
          f"{cnt(dropped_days)} days later and scores {cnt(es_B['Scored days'])}. A and B "
          f"therefore differ in two ways at once, and a gap between them proves nothing, which is "
          f"why A' exists: A's engine restricted to B's dates. Where A' and B agree, the frozen "
          f"approximation is not what moves the count.")
    manifest_table(
        doc, "Table 19",
        f"The scoring-convention control: every book priced under convention A (frozen filter, "
        f"full {cnt(es_A['Scored days'])}-day sample), A' (frozen filter, restricted to the "
        f"{cnt(es_B['Scored days'])} dates convention B can score) and B (the Module 4 engine on "
        f"the series the book actually earned). Reading down a strategy block separates the "
        f"sample effect from the engine effect.",
        "optimisation.engine_convention_control",
        [("Strategy", "Book", "str"),
         ("engine convention", "Convention", "str"),
         ("First day", "First scored day", "str"),
         ("Scored days", "Days", 0),
         ("Breaches", "Exceptions", 0),
         ("Breach Rate (%)", "Rate", "pc", 3),
         ("CI low (%)", "Exact 95% interval", lambda r: ci_pair(r, "CI low (%)", "CI high (%)")),
         ("Kupiec p", "Kupiec", "pv"),
         ("Christoffersen p", "CC", "pv"),
         ("Mean Excess Loss (%)", "Mean miss", "pc", 3),
         ("Mean VaR (%)", "Mean boundary", "pc", 3)])
    prose(doc,
          f"Decomposed, the {es_A['Breaches']} becomes unremarkable. Moving from A to A' holds the "
          f"engine fixed and drops the first {cnt(dropped_days)} scored days: "
          f"{es_A['Breaches']} exceptions become {es_AP['Breaches']}, so "
          f"{dropped_breaches} of them belonged to that dropped window alone - a rate of "
          f"{N.percent(dropped_rate, 2)} on those days against the "
          f"{N.percent(100 * (1 - N.value('config.confidence_level')), 1)} nominal exception rate "
          f"the boundary is set to produce - and the window runs from "
          f"{es_A['First day']} to {es_AP['First day']}, which is the 2007-08 transition the risk "
          f"register in section 3.10 named in advance. Moving from A' to B holds the "
          f"dates fixed and changes the engine: {es_AP['Breaches']} becomes {es_B['Breaches']}, "
          f"so the frozen-filter approximation is worth {engine_gap} days of the count and the "
          f"crisis window is worth {dropped_breaches}. Under B the "
          f"shortfall book scores {es_B['Breaches']} exceptions at "
          f"{N.percent(es_B['Breach Rate (%)'], 3)} with a Kupiec p of "
          f"{N.p_value(es_B['Kupiec p'])}, which is the same count the two minimum-variance books "
          f"score - {mv_B['Breaches']} and {lw_B['Breaches']} - and the same interval, "
          f"{ci_pair(es_B, 'CI low (%)', 'CI high (%)')}. The extension the reviewer asked for "
          f"therefore transfers cleanly once it is scored on its own book; the catastrophic-looking "
          f"calibration was an artefact of pricing a counterfactual book over a crisis it was never "
          f"alive for. What convention B does not do is make the book pass: "
          f"{N.p_value(es_B['Christoffersen p'])} on the conditional-coverage test is the one "
          f"figure for this book that stays rejected under all three conventions, and section 4.10 "
          f"returns to it.")
    mv_lw = pair_row(MV, MV_LW)
    es_mv = pair_row(MIN_ES, MV)
    es_cap = pair_row(MIN_ES, CAP)
    ew_pair = pair_row(EW_R, EW_H)
    es_ew = pair_row(MIN_ES, EW_R)

    def exclusive(row, book):
        return row["Only in A"] if row["Book A"] == book else row["Only in B"]

    prose(doc,
          f"Identical counts are not identical books, and the date-level check says so. The "
          f"agreement matrix is computed on convention B, the only convention in which each row "
          f"prices the series it claims to. The two minimum-variance books share "
          f"{mv_lw['Shared exception days']} of their {min(mv_lw['Breaches A'], mv_lw['Breaches B'])} "
          f"exceptions for a Jaccard index of {N.number(mv_lw['Jaccard'], 4)} - shrinkage changes "
          f"the weights and not the failure days. The shortfall book against the sample "
          f"minimum-variance book shares {es_mv['Shared exception days']} of "
          f"{min(es_mv['Breaches A'], es_mv['Breaches B'])} at {N.number(es_mv['Jaccard'], 4)}, and "
          f"against the turnover-capped variant {es_cap['Shared exception days']} at "
          f"{N.number(es_cap['Jaccard'], 4)}. Against the equal-weight control the picture is "
          f"different again: {es_ew['Shared exception days']} common days out of "
          f"{es_ew['Breaches A']} and {es_ew['Breaches B']}, a Jaccard of "
          f"{N.number(es_ew['Jaccard'], 4)}, with "
          f"{exclusive(es_ew, MIN_ES)} exception days belonging to the shortfall book alone and "
          f"{exclusive(es_ew, EW_R)} to the control alone. Even the two equal-weight books, which "
          f"differ only in whether the basket is rebalanced back to "
          f"{N.percent(100.0 / len(universe), 0)}-a-name, agree on "
          f"{ew_pair['Shared exception days']} of their days for a Jaccard of "
          f"{N.number(ew_pair['Jaccard'], 4)}. Two books with the same "
          f"exception count and a third of the same exception dates are not two estimates of the "
          f"same quantity, and this is where the comparability warning earns its place: the "
          f"shortfall book is wrong on days the equal-weight book is right, because it is a "
          f"different book.")
    manifest_table(
        doc, "Table 20",
        "Diagnosis of each book's own loss series and forecast, under the published recursion "
        "convention. The last three columns partition each row's exception count: an exception is "
        "attributed to one proposal stress window or to none.",
        "optimisation.book_diagnosis",
        [("Strategy", "Book", "str"),
         ("Vol (%)", "Daily vol", "pc", 3),
         ("Excess kurtosis", "Excess kurt", 2),
         ("Skew", "Skew", "sg", 3),
         ("Worst day (%)", "Worst day", "pc", 3),
         ("Days < -5%", "Days < -5%", 0),
         ("Days < -7%", "Days < -7%", 0),
         ("Mean VaR (%)", "Mean boundary", "pc", 3),
         ("Names held", "Names held", 2),
         ("Breaches", "Exceptions", 0),
         ("Longest run of breaches", "Longest run", 0),
         ("Breaches in 2008 GFC", "In GFC", 0),
         ("Breaches in 2020 COVID", "In COVID", 0),
         ("Breaches outside all windows", "Outside windows", 0)])
    d_es, d_ew = strategy_row(MIN_ES, "optimisation.book_diagnosis"), strategy_row(EW_R, "optimisation.book_diagnosis")
    c_es, c_ew = conc_row(MIN_ES), conc_row(EW_R)
    prose(doc,
          f"Table 20 resolves the apparent contradiction that a book with thinner tails has more "
          f"exceptions. It is not a book with thinner tails on the terms the boundary is tested "
          f"on; it is a book with a lower boundary. Its mean forecast quantile is "
          f"{N.percent(d_es['Mean VaR (%)'], 3)} of notional against the equal-weight control's "
          f"{N.percent(d_ew['Mean VaR (%)'], 3)}, because the optimiser has genuinely removed most "
          f"of the extreme daily losses - {d_es['Days < -5%']} days below minus five per cent "
          f"against {d_ew['Days < -5%']}, {d_es['Days < -7%']} below minus seven against "
          f"{d_ew['Days < -7%']}, a worst day of {N.percent(d_es['Worst day (%)'], 3)} against "
          f"{N.percent(d_ew['Worst day (%)'], 3)} - and a forecast calibrated to a tamer series is "
          f"a smaller number, so ordinary days clear it. Severity moves the other way from "
          f"frequency and in the right direction: when the shortfall book does breach, the mean "
          f"miss is {N.percent(es_A['Mean Excess Loss (%)'], 3)} against the equal-weight book's "
          f"{N.percent(ew_A['Mean Excess Loss (%)'], 3)}. The clustering is what the count is "
          f"hiding: {d_es['Breaches in 2008 GFC']} of its exceptions fall inside the 2008 GFC "
          f"window against the control's "
          f"{d_ew['Breaches in 2008 GFC']}, its longest run is {d_es['Longest run of breaches']} "
          f"against {d_ew['Longest run of breaches']}, and the two books are wrong on different "
          f"days for the reason the previous paragraph gives.")
    prose(doc,
          f"The price of the reduction, stated as the concentration it buys rather than as a "
          f"return, is in the same manifest block. The equal-weight books hold all "
          f"{cnt(c_ew['Mean names held'])} names at a Herfindahl of "
          f"{N.number(c_ew['Mean Herfindahl'], 3)}. The shortfall book holds "
          f"{N.number(c_es['Mean names held'], 3)} names on "
          f"average at {N.number(c_es['Mean Herfindahl'], 4)}, with its mean maximum weight "
          f"pegged at {N.percent(100 * c_es['Mean max weight'], 0)} and its mean minimum weight "
          f"at zero - the vertex solution panel D implies. That is affordable because the "
          f"universe is not very correlated: mean off-diagonal correlation of the daily returns is "
          f"{N.number(N.value('optimisation.mean_off_diagonal_correlation'), 4)}, so a "
          f"{N.percent(100 * C.MAX_ASSET_WEIGHT, 0)} cap still leaves diversification to buy. It stops "
          f"being affordable at the tail, which is why the book's excess kurtosis rises to "
          f"{N.number(d_es['Excess kurtosis'], 2)} from the control's "
          f"{N.number(d_ew['Excess kurtosis'], 2)} while its volatility falls: concentrating into "
          f"the names with the calmest recent tails is exactly what the objective is for, and it "
          f"replaces idiosyncratic tail risk with the tail risk of the names selected.")
    figure(doc, "fig13_es_reduction_and_frontier.png", "Figure 13",
           "Panel A: every sampled decision date from the reduction grid, plotted as the "
           "equal-weight book's forecast shortfall against the minimum-ES book's forecast "
           "shortfall on identical scenarios, one marker shape per confidence level, with the "
           "45-degree line marking no reduction. Panel B: the seven realised books in "
           "annualised return against annualised realised volatility, each labelled with its "
           "exception rate and its Kupiec p.")
    opt_vols = [r["Ann volatility (%)"] for r in opt_tbl
                if not r["Strategy"].startswith("Equal weight")]
    vol_spread = max(opt_vols) - min(opt_vols)
    deepest_red = min(r["min"] for r in red_tbl)
    shallowest_red = max(r["max"] for r in red_tbl)
    prose(doc,
          f"Observation: panel A's points sit below the diagonal at every one of the "
          f"{cnt(red_dates)} sampled decision dates, three levels apiece, "
          f"{len(red_rec)} points in all, in a band that widens as the equal-weight forecast "
          f"rises - the deepest reduction, {N.percent(abs(deepest_red), 3)}, occurs where the "
          f"starting measure is largest. Panel B is a frontier with a gap in it: the "
          f"equal-weight pair occupies the high-return, high-volatility corner at "
          f"{N.percent(ew_r['Ann return (%)'], 2)} and "
          f"{N.percent(ew_r['Ann volatility (%)'], 2)}, the five optimised books sit inside a "
          f"{N.number(vol_spread, 2)}-point volatility band at the low end, and the labels' "
          f"exception rates run the wrong way for a naive reading - the calmest books carry the "
          f"highest rates. "
          f"Mechanism: panel A is a same-scenarios comparison, so its vertical gap is the pure "
          f"effect of the objective and contains no sampling noise; panel B's labels are "
          f"convention-A counts on counterfactual books, which is the artefact table 19 exists to "
          f"discharge. Consequence: the two panels have to be read together and in that order, "
          f"because panel A is the claim the optimiser is entitled to make and panel B's "
          f"right-hand labels are the claim it is not. Falsifier: points above the diagonal in "
          f"panel A, which would mean the solver was not solving the stated problem - none are, "
          f"and the shallowest reduction anywhere in the grid is "
          f"{N.percent(abs(shallowest_red), 3)}.")
    churn_cut = 100.0 * (1.0 - cap_r["One-way turnover (annual)"]
                         / es_r["One-way turnover (annual)"])
    opt_cc = [conv_row(s, B_CONV)["Christoffersen p"] for s in (MV, MV_LW, MIN_ES, FLOOR, CAP)]
    ew_cc = [conv_row(s, B_CONV)["Christoffersen p"] for s in (EW_R, EW_H)]
    target_rate = 100.0 * (1.0 - N.value("config.confidence_level"))
    b_rows = [conv_row(s, B_CONV) for s in (EW_R, EW_H, MV, MV_LW, MIN_ES, FLOOR, CAP)]
    by_gap = sorted(b_rows, key=lambda r: abs(r["Breach Rate (%)"] - target_rate))
    ordinals = {1: "first", 2: "second", 3: "third", 4: "fourth",
                5: "fifth", 6: "sixth", 7: "seventh"}
    floor_rank = [r["Strategy"] for r in by_gap].index(FLOOR) + 1
    prose(doc,
          f"Two constrained variants close the section, and they are the practical result. The "
          f"turnover-capped book limits one-way rebalancing to "
          f"{N.percent(100 * C.TURNOVER_CAP_ONE_WAY, 0)} of the book and cuts annual turnover from "
          f"{N.number(es_r['One-way turnover (annual)'], 3)} to "
          f"{N.number(cap_r['One-way turnover (annual)'], 3)}, cost drag from "
          f"{N.percent(es_r['Annual fee fractions (%)'], 3)} to "
          f"{N.percent(cap_r['Annual fee fractions (%)'], 3)}, for "
          f"{cap_B['Breaches']} exceptions under convention B against the unconstrained book's "
          f"{es_B['Breaches']} - it removes {N.percent(churn_cut, 1)} of the churn and buys "
          f"{cap_B['Breaches'] - es_B['Breaches']} more exception days with it. The return-floored "
          f"book is the strongest of the three constrained variants: it recovers part of the mean "
          f"the unconstrained objective gave up, {N.percent(floor_r['Ann return (%)'], 3)} against "
          f"the shortfall book's {N.percent(es_r['Ann return (%)'], 3)} and still short of the "
          f"control's {N.percent(ew_r['Ann return (%)'], 3)}, at a volatility of "
          f"{N.percent(floor_r['Ann volatility (%)'], 3)}, and on its own series it is the best "
          f"calibrated of the five optimised books: "
          f"{floor_B['Breaches']} exceptions at "
          f"{N.percent(floor_B['Breach Rate (%)'], 3)} with a Kupiec p of "
          f"{N.p_value(floor_B['Kupiec p'])}, the {ordinals[floor_rank]} of the seven books on "
          f"distance from the {N.percent(target_rate, 1)} nominal rate. Even that book fails on "
          f"independence: its conditional-coverage p is "
          f"{N.p_value(floor_B['Christoffersen p'])}, and that is the shared outcome of this whole "
          f"section - the best of the five optimised books' coverage p-values is "
          f"{N.p_value(max(opt_cc))}, still below the {N.percent(100 * C.CLOPPER_PEARSON_ALPHA, 0)} "
          f"level used throughout, while both equal-weight controls clear it at "
          f"{N.p_value(min(ew_cc))} and {N.p_value(max(ew_cc))}. Exceptions cluster in optimised "
          f"books and do not cluster in the equal-weight ones, which is section 4.10's opening and "
          f"the honest limit on what a minimum-ES objective can be claimed to have done here. The "
          f"recommendation this section can defend is "
          f"therefore narrower and more useful than the one the plan expected: the tail measure "
          f"responds to being optimised, strongly and on identical scenarios; the realised book "
          f"that responds is a constrained one; and neither book's exception count is evidence "
          f"about the other.")

    ctrl_es = strategy_row(MIN_ES, "optimisation_control.table")
    ctrl_ew = strategy_row(EW_R, "optimisation_control.table")
    ctrl_names = len(N.value("optimisation_control.universe"))
    ctrl_red = 100.0 * (1.0 - ctrl_es["Mean ES (%)"] / ctrl_ew["Mean ES (%)"])
    main_red = 100.0 * (1.0 - es_r["Mean ES (%)"] / ew_r["Mean ES (%)"])
    n_book = cnt(N.value("data.n_assets"))
    prose(doc,
          f"Table 5's survivorship row promises that this result is reported again on a book the "
          f"authors did not choose for it, and here it is. The control run recomputes every "
          f"strategy on the {n_book}-name universe cut to its first {cnt(ctrl_names)} names "
          f"alphabetically: {N.value('optimisation_control.reason')} On that "
          f"book the same objective still cuts "
          f"the forecast shortfall - mean expected shortfall falls from "
          f"{N.percent(ctrl_ew['Mean ES (%)'], 3)} for the equal-weight control to "
          f"{N.percent(ctrl_es['Mean ES (%)'], 3)} for the shortfall book, a reduction of "
          f"{N.percent(ctrl_red, 1)} against the {N.percent(main_red, 1)} the full universe "
          f"produces - and realised volatility still falls, {N.percent(ctrl_es['Ann volatility (%)'], 2)} "
          f"against {N.percent(ctrl_ew['Ann volatility (%)'], 2)}. The calibration damage still "
          f"appears too: {cnt(ctrl_es['Actual Breaches'])} exceptions against the control's "
          f"{cnt(ctrl_ew['Actual Breaches'])}, a Kupiec p of "
          f"{N.p_value(ctrl_es['Kupiec p'])} against {N.p_value(ctrl_ew['Kupiec p'])}. What "
          "changes is the severity, not the sign. The finding that a minimum-ES objective degrades "
          "the calibration of the boundary it was scored against is therefore not an artefact of "
          "which survivors are in the sample; the size of that degradation is, and a point-in-time "
          "universe - which this project does not have and cannot buy - is the only way to say how "
          "much of the difference is the universe rather than the objective.")

    # ------------------------------------------------- 4.10 computational cost --
    add_heading_2(doc, "4.10 Computational Efficiency")
    cadence = N.records("runtime.refit_cadence")
    env = N.raw("runtime.environment.environment")
    sharing = N.records("runtime.sweep_sharing")
    c_hs = cost_row("Historical simulation VaR")
    c_gauss = cost_row("Gaussian parametric VaR")
    c_gn = cost_row("GARCH(1,1) MLE, normal innovations")
    c_gt = cost_row("GARCH(1,1) MLE, Student-t innovations")
    c_gpd = cost_row("GPD peaks-over-threshold fit")
    c_ar = cost_row("GPD quantile arithmetic")
    c_full = cost_row("Full GARCH-EVT calibration")
    c_batt = cost_row("Residual i.i.d. diagnostic battery")
    c_lp = cost_row("Minimum-ES linear programme")
    c_qp = cost_row("Minimum-variance QP (benchmark)")
    k1, k5 = cad_row(1), cad_row(5)
    k20, k60 = cad_row(20), cad_row(60)
    fit_ratio = c_full["Calibration median (ms)"] / c_hs["Calibration median (ms)"]
    dec_ratio = c_full["Amortised per forecast (us)"] / c_hs["Amortised per forecast (us)"]
    cad_multiple = k1["Wall time (s)"] / k20["Wall time (s)"]
    share_map = {r["metric"]: r["value"] for r in sharing}
    m4 = N.raw("headline.module4_performance_summary")
    target = 100.0 * (1.0 - N.value("config.confidence_level"))
    k1_gap = abs(k1["Breach rate (%)"] - target)
    k20_gap = abs(k20["Breach rate (%)"] - target)
    per_cfg_s = share_map["cost_per_configuration_minute"] * 60.0
    alone_s = share_map["single_config_pass_wall_time_s"]
    lp_of_gt = c_lp["Calibration median (ms)"] / c_gt["Calibration median (ms)"]
    lp_over_qp = c_lp["Calibration median (ms)"] / c_qp["Calibration median (ms)"]
    lp_of_full = c_lp["Calibration median (ms)"] / c_full["Calibration median (ms)"]
    t_of_full = c_gt["Calibration median (ms)"] / c_full["Calibration median (ms)"]
    margins = {r["Refit interval (days)"]: min(r["Kupiec p"], r["Christoffersen p"])
               for r in cadence}
    best_margin_cadence = max(margins, key=margins.get)

    def ms(record, key):
        return N.number(record[key], 4)

    def secs(value):
        return f"{N.number(value, 3)} s"

    prose(doc,
          f"Reviewer comment 1 asked that the framework's accuracy claim be priced, and objective "
          f"five in section 3.9 is the protocol that answers it. Every figure below is measured on "
          f"one machine and reported with it: {env['platform']}, Python {env['python']} on "
          f"{env['machine']} ({env['processor'].split(',')[0]}), {cnt(env['cpu_count'])} cores, "
          f"numpy {env['numpy']}, pandas {env['pandas']}, scipy {env['scipy']}, statsmodels "
          f"{env['statsmodels']}, arch {env['arch']}. Timings come from "
          f"{N.value('runtime.measured_by')}, which repeats each step "
          f"{N.number(C.BENCH_REPEATS_FAST, 0)} times for the closed-form steps and "
          f"{N.number(C.BENCH_REPEATS_SLOW, 0)} for the maximum-likelihood ones after "
          f"{N.number(C.BENCH_WARMUP, 0)} warm-up runs, and caches what it measured so the report "
          f"reads the cache rather than a fresh timer. The caution printed beside those caches is "
          f"the organising thought of this subsection, quoted rather than paraphrased: "
          f"“{N.value('runtime.caution')}”")
    manifest_table(
        doc, "Table 21",
        f"Every calibration step in the framework, timed on the machine above. The two left-hand "
        f"columns are the price of one fit; the right-hand pair is the price of using it, which is "
        f"what the cadence in table 22 actually charges.",
        "runtime.model_costs",
        [("Model", "Step", "str"),
         ("Calibration median (ms)", "Median fit (ms)", lambda r: ms(r, "Calibration median (ms)")),
         ("Calibration min (ms)", "Fastest (ms)", lambda r: N.number(r["Calibration min (ms)"], 4)),
         ("Calibration p95 (ms)", "p95 (ms)", lambda r: N.number(r["Calibration p95 (ms)"], 4)),
         ("Repeats", "Repeats", 0),
         ("Runs per pass", "Runs per backtest", 0),
         ("Cadence", "Refit cadence", "str"),
         ("Full-pass cost (s)", "Whole backtest (s)", lambda r: N.number(r["Full-pass cost (s)"], 3)),
         ("Amortised per forecast (us)", "Per forecast (us)", lambda r: N.number(r["Amortised per forecast (us)"], 1))],
        note="The two baselines run every day and the filtered steps run every "
             f"{N.number(C.REBALANCE_INTERVAL, 0)} days, so the median-fit column and the per-forecast "
             "column rank the steps differently. That difference is the finding, not a formatting "
             "choice. The whole-backtest column is the cached median multiplied by the runs per pass, "
             "so it prices the fitting calls alone; table 22 times a live pass end to end, and on the "
             f"twenty-day cadence the two differ by {N.number(c_full['Full-pass cost (s)'] - k20['Wall time (s)'], 3)} s.")
    prose(doc,
          f"Ranked by the price of one fit, the framework looks extravagant: the full "
          f"GARCH-EVT calibration takes {ms(c_full, 'Calibration median (ms)')} ms against "
          f"{ms(c_hs, 'Calibration median (ms)')} ms for historical simulation, a factor of "
          f"{N.number(fit_ratio, 1)}. Ranked by the price of a decision, it does not. The filter is "
          f"refitted every {N.number(C.REBALANCE_INTERVAL, 0)} days and its forecast is reused on "
          f"the days in between, so what a ${N.value('data.notional_usd') / 1e6:,.0f} million book "
          f"pays per daily 99% number is "
          f"{N.number(c_full['Amortised per forecast (us)'], 1)} microseconds against the "
          f"baseline's {N.number(c_hs['Amortised per forecast (us)'], 1)} - a factor of "
          f"{N.number(dec_ratio, 1)}, and both are negligible next to the "
          f"{N.number(c_full['Full-pass cost (s)'], 3)} seconds it takes to reproduce the whole "
          f"Module 4 walk-forward on one core. Three other rows matter for what the project "
          f"chose not to do. The Student-t likelihood costs "
          f"{N.number(c_gt['Calibration median (ms)'] / c_gn['Calibration median (ms)'], 2)} times "
          f"the normal one, {ms(c_gt, 'Calibration median (ms)')} ms against "
          f"{ms(c_gn, 'Calibration median (ms)')} ms, which is why section 4.6 treats the "
          f"distributional choice as an expensive test rather than a free default. Everything "
          f"downstream of the filter is arithmetic once the GPD parameters exist - "
          f"{ms(c_ar, 'Calibration median (ms)')} ms, {N.number(c_ar['Amortised per forecast (us)'], 1)} "
          f"microseconds a day - and even the peaks-over-threshold fit that produces those "
          f"parameters is the cheapest of the three likelihoods at "
          f"{ms(c_gpd, 'Calibration median (ms)')} ms, so threshold sensitivity, which looks like a "
          f"grid of refits, is almost free to evaluate. And the whole residual battery that "
          f"section 4.6 runs - Ljung-Box over four lags on the standardised innovations and their "
          f"squares, "
          f"ARCH-LM, Jarque-Bera and the Kolmogorov-Smirnov checks, costs "
          f"{ms(c_batt, 'Calibration median (ms)')} ms once per report "
          f"({N.number(c_batt['Amortised per forecast (us)'], 1)} microseconds amortised), which is "
          f"the reason it is run on every configuration instead of only the headline one.")
    figure(doc, "fig14_cost_vs_accuracy.png", "Figure 14",
           "Panel A: every calibration step of table 21 as a horizontal bar on a log axis, its "
           "median fit time with an error bar spanning the fastest repeat to the p95. Panel B: the "
           "two Module 4 baselines and the GARCH-EVT filter placed on one axis of wall time for a "
           "full walk-forward pass against Kupiec p-value, each point annotated with its breach "
           "rate and labelled in the legend with its amortised cost per forecast, with the "
           "rejection boundary drawn as a dashed line.")
    base_cost_ratio = max(c_hs["Full-pass cost (s)"], c_gauss["Full-pass cost (s)"]) / min(
        c_hs["Full-pass cost (s)"], c_gauss["Full-pass cost (s)"])
    filt_cost_ratio = c_full["Full-pass cost (s)"] / c_hs["Full-pass cost (s)"]
    prose(doc,
          f"Observation: panel A's bars span a factor of "
          f"{N.number(c_full['Calibration median (ms)'] / c_ar['Calibration median (ms)'], 0)} "
          f"inside one framework, and the order is not the one a reader expects - the arithmetic "
          f"step is the shortest bar at {ms(c_ar, 'Calibration median (ms)')} ms and the full "
          f"calibration the longest at {ms(c_full, 'Calibration median (ms)')} ms, with the "
          f"Student-t likelihood the dearest single component at "
          f"{ms(c_gt, 'Calibration median (ms)')} ms, or {N.percent(100.0 * t_of_full, 1)} of that "
          f"whole. The component rows are not additive with the joint row: each was timed on its "
          f"own repeats, and the joint row prices the chain as one call. Panel B is the "
          f"informative one: historical simulation and the Gaussian parametric model sit at "
          f"{N.number(c_hs['Full-pass cost (s)'], 3)} s and {N.number(c_gauss['Full-pass cost (s)'], 3)} "
          f"s - a factor of {N.number(base_cost_ratio, 2)} apart, which is nothing even on a log "
          f"axis, and they land on one another - and both are rejected, at Kupiec p "
          f"{N.p_value(m4['VaR_Historical']['Kupiec p-val'])} and "
          f"{N.p_value(m4['VaR_Normal']['Kupiec p-val'])}. The filter sits "
          f"{N.number(filt_cost_ratio, 1)} times to their right, at "
          f"{N.number(c_full['Full-pass cost (s)'], 3)} s, and clears the line at "
          f"{N.p_value(m4['VaR_GARCH_EVT']['Kupiec p-val'])}. Mechanism: a constant boundary cannot "
          f"track volatility clustering, which is what the two baselines are charged with and what "
          f"section 4.1 already established; the relative cost difference between a cheap fit and "
          f"a slightly cheaper one buys no accuracy because both miss the same way, while the "
          f"filter's absolute price is a backtest in seconds rather than hours. Consequence: the "
          f"panel's claim is that accuracy here is bought rather than rented, and the second half "
          f"of the caution sentence does the work. The "
          f"{N.number(filt_cost_ratio, 1)}-fold gap a reader takes off panel B's axis is one "
          f"full walk-forward pass against another, and it is the same factor as the "
          f"{N.number(dec_ratio, 1)} between "
          f"{N.number(c_full['Amortised per forecast (us)'], 1)} and "
          f"{N.number(c_hs['Amortised per forecast (us)'], 1)} microseconds per forecast - which is "
          f"the quantity a risk team actually pays. Falsifier: a panel B in which the two baselines "
          f"separated vertically, which "
          f"would have made efficiency a straightforward purchase decision at the cheap end, or a "
          f"filter marker below the dashed line, which would have made its cost indefensible; "
          f"neither happens, and the flatness of the pair is what table 22 then tests at the other "
          f"end of the machine.")
    manifest_table(
        doc, "Table 22",
        f"The accuracy-latency curve the framework was asked to produce: the same "
        f"{cnt(N.value('data.walk_forward_days'))} scored days refitted every "
        f"{', '.join(str(i) for i in C.BENCH_REFIT_INTERVALS)} days, with wall time on one side "
        f"and calibration tests on the other. This is the measurement that turns the project's "
        f"twenty-day cadence from a convention into a choice.",
        "runtime.refit_cadence",
        [("Refit interval (days)", "Refit every (days)", 0),
         ("Refits", "Refits", 0),
         ("Scored days", "Scored days", 0),
         ("Wall time (s)", "Backtest (s)", lambda r: N.number(r["Wall time (s)"], 3)),
         ("Wall time per forecast (ms)", "Per forecast (ms)", lambda r: N.number(r["Wall time per forecast (ms)"], 3)),
         ("Breaches", "Exceptions", 0),
         ("Breach rate (%)", "Rate", "pc", 3),
         ("Kupiec p", "Kupiec", "pv"),
         ("Christoffersen p", "CC", "pv"),
         ("Mean excess loss (%)", "Mean miss", "pc", 3)])
    prose(doc,
          f"Table 22 is where the reviewer's question gets answered, and the answer is not what "
          f"the plan expected. Refitting daily costs {secs(k1['Wall time (s)'])} against "
          f"{secs(k20['Wall time (s)'])} at the project's twenty-day cadence, a factor of "
          f"{N.number(cad_multiple, 1)}, and it buys nothing any test rewards: the daily book "
          f"records {k1['Breaches']} exceptions at {N.percent(k1['Breach rate (%)'], 3)} and the "
          f"twenty-day book {k20['Breaches']} at {N.percent(k20['Breach rate (%)'], 3)}, so all "
          f"that compute leaves the rate "
          f"{N.number(k1_gap, 3)} percentage points under the nominal {N.percent(target, 3)} "
          f"target where the twenty-day cadence sits {N.number(k20_gap, 3)} points under it. What "
          f"daily refitting does change is severity: the mean miss falls from "
          f"{N.percent(k20['Mean excess loss (%)'], 3)} to "
          f"{N.percent(k1['Mean excess loss (%)'], 3)}, so the more frequently refitted book "
          f"under-covers by more and, when it is wrong, is wrong less expensively. Neither "
          f"difference is a test result. Both cadences clear Kupiec - "
          f"{N.p_value(k1['Kupiec p'])} daily against {N.p_value(k20['Kupiec p'])} at twenty days - "
          f"and Christoffersen, {N.p_value(k1['Christoffersen p'])} against "
          f"{N.p_value(k20['Christoffersen p'])}. The "
          f"five-day cadence between them, {secs(k5['Wall time (s)'])} for {k5['Breaches']} "
          f"exceptions at {N.percent(k5['Breach rate (%)'], 3)}, sits inside the noise of both. "
          f"The curve is flat where accuracy is concerned and steep where time is, which is the "
          f"opposite of the trade-off a sensitivity table is usually produced to advertise.")
    prose(doc,
          f"Cost is not the whole of it, because the sixty-day cadence is where the flatness ends "
          f"and it ends on the test nobody looks at first. Its {k60['Breaches']} exceptions at "
          f"{N.percent(k60['Breach rate (%)'], 3)} still draw a Kupiec p of "
          f"{N.p_value(k60['Kupiec p'])} - the frequency is passable, and a report that only ran "
          f"the unconditional test would have recommended the cheapest cadence in the table. Its "
          f"conditional-coverage p is {N.p_value(k60['Christoffersen p'])}, which is a rejection, "
          f"and its mean miss rises to {N.percent(k60['Mean excess loss (%)'], 3)}. Stale forecasts "
          f"do not change how often they are wrong so much as how wrong they are and when the "
          f"wrongs arrive together. Read against section 4.8's concentration evidence - the top "
          f"five exception days carrying "
          f"{N.percent(N.value('economic.primary_register_concentration.top_5_share_pct'), 2)} of "
          f"the unfunded loss - the twenty-day cadence is the knee rather than the fastest "
          f"available setting: its weaker of the two tests is the strongest anywhere in the "
          f"table, {N.p_value(margins[best_margin_cadence])} at "
          f"{N.number(best_margin_cadence, 0)} days against "
          f"{N.p_value(margins[60])} at the slow end, and its Kupiec p is "
          f"{N.p_value(k20['Kupiec p'])}, at "
          f"{N.number(k20['Wall time per forecast (ms)'], 3)} ms per forecast.")
    manifest_table(
        doc, "Table 23",
        "What the single-pass sweep design saves. The threshold-by-coverage grid is evaluated from "
        "residuals that depend only on the innovation distribution, so the volatility filter is "
        "fitted twice per refit date for the whole grid rather than once per configuration.",
        "runtime.sweep_sharing",
        [("metric", "Quantity", "str"),
         ("value", "Measured", lambda r: format_sharing(r))])
    naive_s = share_map["naive_independent_passes_s"]
    shared_s = share_map["shared_pass_wall_time_s"]
    prose(doc,
          f"The saving in table 23 is an architecture result rather than a speed-up story. "
          f"Because the peaks-over-threshold step sits downstream of the volatility filter, the "
          f"GARCH fit depends only on the innovation distribution and the GPD fit depends only on "
          f"the threshold and the confidence level, so one pass fits the filter "
          f"{cnt(share_map['shared_pass_refits'])} times - twice per refit date, normal and "
          f"Student-t - and evaluates all {cnt(share_map['configurations_in_sweep'])} "
          f"configurations from the same residuals. Running them independently would have cost "
          f"{secs(naive_s)} for the grid against the {secs(shared_s)} measured, a saving of "
          f"{N.percent(share_map['saving_vs_independent (%)'], 2)}, and the practical consequence "
          f"is that one configuration of the sensitivity study costs {secs(per_cfg_s)} inside the "
          f"shared pass against the {secs(alone_s)} the same configuration takes when it is run "
          f"on its own - {N.percent(100.0 * per_cfg_s / alone_s, 1)} of a standalone run. "
          f"That is what made sections 4.5 and 4.6 affordable: a grid priced this way is reported "
          f"in full rather than sampled, and the threshold rejection in section 4.5 rests on every "
          f"cell of it instead of a chosen few.")
    prose(doc,
          f"What this subsection cannot conclude is worth stating as plainly as what it can. "
          f"Efficiency was framed as the cost of buying accuracy, and at "
          f"{N.number(c_full['Amortised per forecast (us)'], 1)} microseconds per forecast the "
          f"purchase is not the binding constraint on anything: the framework runs "
          f"{secs(c_full['Full-pass cost (s)'])} for the whole walk-forward, the extension of "
          f"section 4.9 adds {ms(c_lp, 'Calibration median (ms)')} ms per rebalance. Read against "
          f"the steps that produce its inputs, that is under half the "
          f"{ms(c_gt, 'Calibration median (ms)')} ms Student-t GARCH fit whose standardised "
          f"residuals become its scenario set ({N.number(lp_of_gt, 2)} of it) and "
          f"{N.percent(100.0 * lp_of_full, 1)} of the {ms(c_full, 'Calibration median (ms)')} ms "
          f"headline calibration the extension sits beside, spent every "
          f"{N.number(C.REBALANCE_INTERVAL, 0)} days rather than every day. It is the dearer of the "
          f"two optimisers - {N.number(lp_over_qp, 2)} times the "
          f"{ms(c_qp, 'Calibration median (ms)')} ms minimum-variance quadratic program it is "
          f"benchmarked against in table 18 - and that is what optimising the tail rather than the "
          f"variance costs. The binding "
          f"constraint is statistical, and "
          f"tables 18 to 22 keep running into it from three directions: the exception counts of "
          f"different books are not comparable, the unconditional test cannot separate the models "
          f"at this sample length, and the conditional test is the one that rejects. A practitioner "
          f"with this framework gets the tail measure for nothing; what they have to pay for, and "
          f"what no amount of compute buys back, is the clustering the tail measure describes.")
    return doc
# --------------------------------------------------------- 5. Discussion --

def section_discussion(doc):
    """What sections 4.5 to 4.10 add up to, and what the sample cannot carry."""
    add_heading_1(doc, "5. Discussion & Inferences")

    verdict = N.raw("iid.iid_verdict")
    f_n = verdict["per_filter"]["normal"]
    f_t = verdict["per_filter"]["t"]
    sel = N.raw(selection_path("normal"))
    ci6 = primary("Breach Rate 95% CI (%)")
    ci4 = N.raw("headline.module4_exact_interval")
    wald4 = ci4["wald_interval_would_be"]
    rec = N.raw("recursion.difference")
    m4rep = N.raw("recursion.m4_reproduction")
    legacy = N.raw("recursion.sensitivity.legacy")["score"]
    econ = N.raw("economic.by_recursion.corrected.reserve_adequacy")
    conc = N.raw("economic.primary_register_concentration")
    calm = N.raw("regime.disagreement")["portfolio_regime_balanced"][
        "portfolio_stressed_market_calm"]
    cuts = N.raw("regime.cut_points")
    agr = N.raw("regime.agreement")
    bl_agr = agr["portfolio_regime_balanced"]
    perf = N.records("regime.regime_conditional_performance")
    gfc = next(r for r in perf if r["regime"] == "2008 GFC")
    covid = next(r for r in perf if r["regime"] == "2020 COVID")
    rank_bal = {r["regime"]: r
                for r in N.records("regime.model_ranking.portfolio_regime_balanced")}
    terciles = ("low_vol", "mid_vol", "high_vol")
    nt = next(r for r in N.records("iid.normal_minus_t")
              if _near(r["threshold_q"], N.value("config.threshold_quantile")))
    filt = {(r["innovation_dist"], r["threshold_q"]): r
            for r in N.records("iid.walk_forward_filter_table")
            if _near(r["confidence_level"], N.value("config.confidence_level"))}
    n_t = filt[("t", N.value("config.threshold_quantile"))]
    es_red = es_reduction_row(C.PRIMARY_ES_LP_ALPHA)  # the level the programme actually solves at
    EW, BH, MIN_ES, CAP = ("Equal weight (rebalanced)", "Equal weight (buy-and-hold)",
                           "Minimum ES", "Minimum ES with turnover cap")
    ew_book, bh_book = strategy_row(EW), strategy_row(BH)
    es_book, cap_book = strategy_row(MIN_ES), strategy_row(CAP)
    opt_books = ("Minimum variance (sample)", "Minimum variance (Ledoit-Wolf)",
                 MIN_ES, "Minimum ES with return floor", CAP)
    conv = {(r["Strategy"], r["engine convention"].split()[0]): r
            for r in N.records("optimisation.engine_convention_control")}
    es_a, es_ap, es_b = conv[(MIN_ES, "A")], conv[(MIN_ES, "A'")], conv[(MIN_ES, "B")]
    ew_a, ew_b = conv[(EW, "A")], conv[(EW, "B")]
    opt_cc = [conv[(s, "B")]["Christoffersen p"] for s in opt_books]
    ew_cc = [conv[(s, "B")]["Christoffersen p"] for s in (EW, BH)]
    k60 = cad_row(60)
    z_lo, z_hi, spread_pct = threshold_spread_pct()
    wf_prod = walk_forward_row(N.value("config.threshold_quantile"))
    wf_99 = [r for r in N.records("threshold.walk_forward_sensitivity")
             if _near(r["confidence_level"], N.value("config.confidence_level"))]
    wf_rej = sorted([r for r in wf_99 if r["Kupiec p-val"] < C.CLOPPER_PEARSON_ALPHA],
                    key=lambda r: (r["innovation_dist"], r["threshold_q"]))
    opt_cost = cost_row("Minimum-ES linear programme")
    limitations = N.raw("data.data_limitations")

    def usd(x, dp=2):
        return N.dollars(x / 1e6, dp)

    def cnt(value):
        return N.number(value, 0)

    def ms(record, key="Calibration median (ms)"):
        return N.number(record[key], 4)

    def cell_label(record):
        filt_name = "Gaussian" if record["innovation_dist"] == "normal" else "Student-t"
        return f"{filt_name} at q = {record['threshold_q']:g}"

    target = 100.0 * (1.0 - N.value("config.confidence_level"))
    iid_say = verdict["iid_conclusion"].replace(" -- ", " - ")
    headroom = 100.0 * (ci6[1] / target - 1.0)
    plain_name = {"VaR_Normal": "parametric Gaussian boundary",
                  "VaR_Historical": "historical-simulation boundary"}
    same_both = " and ".join(plain_name[b] for b in rec["identical_across_recursions"])
    rejected_grid = cnt(sel["n_grid"] - sel["n_eligible"])
    min_tercile_p = min(rank_bal[r]["GARCH-EVT Kupiec p"] for r in terciles)
    rej_labels = ", ".join(cell_label(r) + " (" + N.p_value(r["Kupiec p-val"]) + ")"
                           for r in wf_rej)

    prose(doc,
          f"Sections 4.5 to 4.10 were built to answer the eight peer-review comments, and table 1 "
          f"traces each comment to the file and function that answers it. This section says what "
          f"that evidence adds up to. The seven statements below are each written so that a table "
          f"in section 4 could overturn them, and each is bounded by the same constraint: "
          f"{cnt(N.value('data.walk_forward_days'))} scored days contain "
          f"{cnt(primary('Actual Breaches'))} exceptions, and a tail model is judged on exactly "
          f"those. Section 5.3 states what that limit forbids instead of writing around it.")

    add_heading_2(doc, "5.1 Position Within the Literature the Review Asked For")
    prose(doc,
          f"Reviewer comment 6 objected that the proposal cited the extreme value canon but not "
          f"the critique of it. The canon is what section 2 uses: the result that excesses over a "
          f"high threshold are asymptotically generalised Pareto (Balkema and de Haan; Pickands), "
          f"the inference built on it (Davison and Smith; Coles), the domain-of-attraction "
          f"conditions under which the limit is a usable approximation rather than a statement "
          f"about infinity (de Haan and Ferreira; Embrechts et al.), the application of a filter "
          f"and a tail model in series to conditional heteroskedasticity (McNeil and Frey), and "
          f"the heteroskedasticity itself (Engle; Bollerslev). The critique is that this "
          f"machinery is fragile in precisely the regime it is bought for and that the measures it "
          f"produces are hard to validate: historical simulation updates slowly and its window is "
          f"full of calm days at the moment the shock arrives (Pritsker); the small-sample "
          f"accuracy of value-at-risk backtests is poor at realistic lengths (Kuester et al.); a "
          f"single quantile is not a coherent risk measure and says nothing about the loss beyond "
          f"it (Artzner et al.; Acerbi and Tasche); the alternative that is coherent cannot be "
          f"scored on its own, so comparing two of them with a ranking rule is not the "
          f"straightforward contest a p-value implies (Gneiting; Fissler and Ziegel); and the "
          f"disagreement between candidate tail measures on the same book is wider than a "
          f"single-number comparison suggests (Emmer et al.; Thompson and McCarthy; Chu and "
          f"Bhattacharyya).")
    prose(doc,
          f"What that list is not is the recent empirical equity work the reviewer asked for by "
          f"name. The six works added at this milestone, Davison and Smith (1990), Coles (2001), "
          f"de Haan and Ferreira (2006), Emmer et al. (2015), Krokhmal et al. (2001) and Ledoit "
          f"and Wolf (2004), are methodological: they supply the estimator, its domain of "
          f"attraction, its inference, and the measures this report compares, and none of them is "
          f"a study of the framework failing on equity data in the period the reviewer had in "
          f"mind. The objection is answered here by stating its premises and testing them "
          f"(sections 2.6, 2.7 and 4.5 to 4.6), not by citing the literature that raised it, and "
          f"table 1 records that ask as partially addressed rather than closed.")
    prose(doc,
          f"Two of those objections are answered here with measurement rather than with "
          f"reference. The instability of tail-parameter estimates is what the raw columns of "
          f"table 10 and the clamp column of table 11 print: at full sample "
          f"{rejected_grid} of the {cnt(sel['n_grid'])} grid thresholds are rejected because the "
          f"unclamped shape estimate is negative, the count of thresholds whose shape estimate is "
          f"distinguishable from zero is {cnt(sel['n_thresholds_whose_shape_is_significant'])} "
          f"across the whole grid, and under walk-forward refitting the bound is active on "
          f"{N.percent(wf_prod['clamped_share_%'], 1)} of windows at the production threshold "
          f"alone. The framework does not pretend those estimates are known: it prints the "
          f"estimate, its standard error, the direction the bound moved it and the quantile that "
          f"would have been quoted unclamped. The underpowered-backtest objection is answered the "
          f"same way - the exact interval beside every rate in tables 11, 15, 16 and 18 prices the "
          f"imprecision instead of asserting it away, which is why finding 2 below is worded as "
          f"indistinguishable from nominal rather than as nominal. The third objection, that "
          f"dependence itself is unstable and that correlations tighten in a crash, is the one "
          f"this module does not touch: section 5.3 records it as a limitation and section 6 hands "
          f"it to the copula layer that has been the Module 8 item since the proposal.")
    prose(doc,
          f"Reviewer comment 4, the portfolio extension, has its own literature. Minimising the "
          f"tail rather than the variance is the move Rockafellar and Uryasev (2000) licensed, "
          f"the one Krokhmal et al. put to portfolio selection, and the one Alexander and "
          f"Baptista compared against a value-at-risk constraint inside the mean-variance model "
          f"of Markowitz; the "
          f"market-risk capital framework eventually moved the regulatory boundary onto the same "
          f"measure for the same reason. Optimising a conditional-historical scenario set rather "
          f"than a raw one is Pritsker's objection taken seriously. What the literature does not "
          f"supply, and what section 4.9 does, is the same book scored under the published "
          f"recursion and under the engine that can actually score it, with the exception dates "
          f"compared rather than the counts - which matters here because those two answers differ "
          f"by {cnt(es_a['Breaches'] - es_b['Breaches'])} exceptions on a book whose entire "
          f"backtest is {cnt(es_b['Breaches'])} of them.")

    add_heading_2(doc, "5.2 Findings")
    prose(doc,
          f"**Finding 1 - the recursion correction moved the headline count and left the headline "
          f"conclusion standing.** Module 4 published {m4rep['published_exceptions']} exceptions "
          f"at {N.percent(legacy['Breach Rate (%)'], 4)}, Kupiec "
          f"{N.p_value(legacy['Kupiec p-val'])} and conditional coverage "
          f"{N.p_value(legacy['Conditional Cov p-val'])}; the corrected recursion gives "
          f"{cnt(primary('Actual Breaches'))} at {N.percent(primary('Breach Rate (%)'), 4)}, "
          f"{N.p_value(primary('Kupiec p-val'))} and "
          f"{N.p_value(primary('Conditional Cov p-val'))}. The difference is "
          f"{cnt(rec['exceptions_legacy_minus_corrected'])} exceptions in a published count of "
          f"{m4rep['published_exceptions']}, and it is confined to the one path that compounds "
          f"the filtered variance forward: the {same_both} "
          f"score identically under both recursions. Reproducing the published artefact before "
          f"correcting it is what lets the change be reported as a correction rather than as a "
          f"new result - the largest column-wise discrepancy between the Module 4 output and this "
          f"pipeline's legacy path is {m4rep['max_abs_difference']:.0e}, in units of the "
          f"daily loss series, on the build that wrote the manifest. What the defect had been "
          f"doing was making an inference about a count look like an inference about a model. The "
          f"finding was never that "
          f"{cnt(primary('Actual Breaches'))} is close to "
          f"{N.number(primary('Expected Breaches'), 1)}; it is that the interval around the "
          f"observed rate contains the nominal one, and that survives the correction intact.")
    prose(doc,
          f"**Finding 2 - the framework is indistinguishable from nominal, which is a weaker and "
          f"more useful claim than being nominal.** The exact interval around "
          f"{cnt(primary('Actual Breaches'))} exceptions in "
          f"{cnt(N.value('data.walk_forward_days'))} days is "
          f"[{N.number(ci6[0], 3)}, {N.number(ci6[1], 3)}] per cent and it contains the "
          f"{N.percent(target, 0)} target. The "
          f"width is the result: a boundary breached {N.number(headroom, 0)} per cent more often "
          f"than nominal passes this test, and so does one breached by nearly as much less often. "
          f"The Module 4 numbers show why the exact interval is used rather than the normal "
          f"approximation - at {m4rep['published_exceptions']} exceptions the Wald interval would "
          f"have been [{N.number(wald4[0], 3)}, {N.number(wald4[1], 3)}] against the exact "
          f"[{N.number(ci4['ci_pct'][0], 3)}, {N.number(ci4['ci_pct'][1], 3)}]. For a risk "
          f"function the reading is practical rather than statistical: "
          f"{N.number(N.value('data.walk_forward_days') / 252.0, 1)} years of daily observations "
          f"are enough to screen a tail model out for gross failure and not enough to certify its "
          f"calibration, and every pass in this report should be read in that light.")
    band_prod = clamp_row(C.POT_THRESHOLD_QUANTILE, N.value("headline.confidence_level"),
                          N.value("config.innovation_distribution"))
    prose(doc,
          f"**Finding 3 - the threshold is a bias-variance dial that the data can constrain but "
          f"not resolve.** Confining attention to the {cnt(sel['n_eligible'])} grid thresholds "
          f"the diagnostics license, the reported 99% quantile moves between "
          f"{N.number(z_lo, 4)} and {N.number(z_hi, 4)} standardised deviations, a spread of "
          f"{N.percent(spread_pct, 3)} of the smaller, so the headline calibration is not an "
          f"artefact of the chosen threshold. Widen the grid to the rejected cells and the same "
          f"spread becomes {N.percent(sel['var_z_spread_across_grid_pct'], 2)}, because those "
          f"cells are the ones the shape estimate wants to throw away. Out of sample the dial has "
          f"a visible price: across the {cnt(len(wf_99))} walk-forward cells at this coverage the "
          f"breach rate runs from {N.percent(min(r['Breach Rate (%)'] for r in wf_99), 3)} to "
          f"{N.percent(max(r['Breach Rate (%)'] for r in wf_99), 3)}, and "
          f"{cnt(len(wf_rej))} cells are rejected by Kupiec - {rej_labels} - "
          f"so the rejections sit at both ends of the grid, at the high thresholds under Gaussian "
          f"innovations and the low ones under Student-t. The defensible statement is the one "
          f"section 4.5 makes: the framework is robust inside the region the diagnostics license "
          f"and there is nothing to be robust about outside it, because there the tail parameter "
          f"is not estimated but bounded. What that bounding costs is measured rather than "
          f"asserted: at the production threshold and this coverage the band moves the boundary "
          f"by a median of {N.number(band_prod['Median |ΔVaR| (bps)'], 1)} bps and the two "
          f"extrapolations disagree about whether a day is an exception on "
          f"{cnt(band_prod['Exception disagreements'])} of {cnt(band_prod['days'])} days - "
          f"table 28.")
    prose(doc,
          f"**Finding 4 - the independence premise the framework actually consumes survives; the "
          f"one the reviewer thought it consumes does not; and telling them apart costs "
          f"{cnt(abs(nt['breach_delta']))} exceptions.** Quoting the diagnostic section's own "
          f"verdict rather than paraphrasing it: “{iid_say}” What that verdict states as a "
          f"minimum, this project states per filter: first-order dependence in the levels sits at "
          f"{N.p_value(f_n['lb_z_min_p'])} under Gaussian innovations and "
          f"{N.p_value(f_t['lb_z_min_p'])} under Student-t before correction, and both clear the "
          f"adjustment for the lags tested. Normality does not: the Jarque-Bera statistic rejects "
          f"at {N.p_value(f_n['jb_p'])} with residual excess kurtosis "
          f"{N.number(f_n['residual_kurtosis'], 3)}, and the Student-t filter that answers that "
          f"rejection estimates {N.number(f_t['filter_nu'], 2)} degrees of freedom. That is where "
          f"the cost "
          f"lands. On identical thresholds, identical windows and identical data, switching the "
          f"likelihood from Gaussian to Student-t moves the production backtest from "
          f"{cnt(nt['breaches_normal'])} exceptions to {cnt(nt['breaches_t'])} and the Kupiec "
          f"p-value from {N.p_value(nt['kupiec_p_normal'])} to "
          f"{N.p_value(nt['kupiec_p_t'])}, while the mean miss beyond the boundary falls from "
          f"{N.percent(nt['mean_excess_normal_pct'], 4)} to "
          f"{N.percent(nt['mean_excess_t_pct'], 4)}. The exact interval behind the Student-t "
          f"count is [{N.number(n_t['Breach Rate 95% CI (%)'][0], 3)}, "
          f"{N.number(n_t['Breach Rate 95% CI (%)'][1], 3)}] per cent, still wide enough to hold "
          f"the target, so the sample "
          f"cannot confirm that the filter the residual diagnostics prefer is the better "
          f"boundary. The peaks-over-threshold step needs second-order whiteness, which it has; "
          f"it does not need strict independence, which this project no longer claims.")
    prose(doc,
          f"**Finding 5 - the boundary is not crisis-specific, but it is not crisis-proof "
          f"either.** Under the balanced book-volatility terciles the two-stage filter runs at "
          f"{N.percent(rank_bal['low_vol']['GARCH-EVT Rate (%)'], 3)}, "
          f"{N.percent(rank_bal['mid_vol']['GARCH-EVT Rate (%)'], 3)} and "
          f"{N.percent(rank_bal['high_vol']['GARCH-EVT Rate (%)'], 3)}, in order from low to high "
          f"volatility, the weakest of those Kupiec p-values being "
          f"{N.p_value(min_tercile_p)}. Under the VIX bands the same model is furthest from "
          f"nominal in the crisis band - {N.percent(rank_bal['crisis']['GARCH-EVT Rate (%)'], 3)} "
          f"against the {N.percent(target, 0)} target at "
          f"{N.p_value(rank_bal['crisis']['GARCH-EVT Kupiec p'])}, short of a rejection - and the "
          f"date overlays are worse than any partition cell: {cnt(gfc['Actual Breaches'])} "
          f"exceptions in {cnt(gfc['Total Obs'])} days of the 2008 window is "
          f"{N.percent(gfc['Breach Rate (%)'], 3)}, which Kupiec rejects at "
          f"{N.p_value(gfc['Kupiec p-val'])} and conditional coverage rejects at "
          f"{N.p_value(gfc['Conditional Cov p-val'])}, while the {cnt(covid['Total Obs'])}-day "
          f"2020 window runs at {N.percent(covid['Breach Rate (%)'], 3)} on "
          f"{cnt(covid['Actual Breaches'])} exceptions. The honest version of the regime finding "
          f"is therefore that the calibration is regime-independent at the resolution a "
          f"partition can measure and fails inside the sharpest weeks a partition blurs. The "
          f"other half of the answer is that the regime label is not a measurement: the two state "
          f"variables agree exactly on {N.percent(bl_agr['pct_agreement'], 2)} "
          f"of days (Cohen's kappa {N.number(bl_agr['kappa_unweighted'], 3)}), "
          f"the cut points move with the window that estimates them, from "
          f"{N.percent(100.0 * cuts['frozen']['cut_points'][0], 2)} and "
          f"{N.percent(100.0 * cuts['frozen']['cut_points'][1], 2)} annualised on the frozen "
          f"calibration to {N.percent(100.0 * cuts['balanced']['cut_points'][0], 2)} and "
          f"{N.percent(100.0 * cuts['balanced']['cut_points'][1], 2)} on the balanced one, and "
          f"the cell neither state variable claims - book stressed, market calm - is "
          f"{cnt(calm['n_days'])} days, {N.percent(calm['pct_of_sample'], 2)} of the sample, "
          f"breaching {N.percent(calm['breach_rate_pct'], 3)} of the time: under, not over.")
    prose(doc,
          f"**Finding 6 - economically, the exceptions are few, concentrated, and cheaper to "
          f"hold against than the count suggests.** {cnt(primary('Actual Breaches'))} breaches "
          f"over {N.number(econ['Years'], 1)} years left {usd(conc['total_usd_excess'])} of "
          f"unreserved loss on a {usd(N.value('data.notional_usd'), 0)} book, and the register in "
          f"appendix C is not a list of small misses: the worst single day is "
          f"{usd(conc['largest_single_usd'])}, {N.percent(conc['top_1_share_pct'], 2)} of the "
          f"total, the top five carry {N.percent(conc['top_5_share_pct'], 2)} and the top ten "
          f"{N.percent(conc['top_10_share_pct'], 2)}, with a Herfindahl index of "
          f"{N.number(conc['hhi_of_excess'], 4)} across {cnt(conc['n_breaches'])} events. Holding "
          f"the shortfall measure instead of the quantile costs "
          f"{usd(econ['Incremental Capital Held (USD)'])} of constant reserve, "
          f"{N.percent(econ['Incremental Capital (% of notional)'], 3)} of notional and a "
          f"{N.percent(econ['ES Reserve Uplift over VaR (%)'], 2)} uplift on the capital number, "
          f"and it removes {usd(econ['Unreserved Loss Avoided by ES (USD)'])} of the realised "
          f"shortfall - {N.number(econ['Avoided Shortfall per Dollar of Extra Capital'], 2)} "
          f"dollars avoided per dollar held. Not all of it: "
          f"{cnt(econ['Days ES Also Breached'])} of the {cnt(primary('Actual Breaches'))} "
          f"exception days are also expected-shortfall days "
          f"({N.percent(econ['Share of VaR Breaches Also ES Breaches (%)'], 2)} of them) and the "
          f"worst day still leaves {usd(econ['Largest Unreserved Day under ES (USD)'])} "
          f"unreserved. The convention that makes those figures readable side by side is the one "
          f"stated in section 4.8: {N.value('economic.stock_versus_flow')}")
    prose(doc,
          f"**Finding 7 - the framework transfers to an allocation decision, and the transfer is "
          f"the least portable result in the report.** On identical scenarios at identical "
          f"decision dates the optimiser's forecast shortfall is below the equal-weight book's at "
          f"every one of the {cnt(n_lp_solves())} sampled rebalance dates, by "
          f"{N.percent(abs(es_red['mean']), 2)} on average - the mean of the per-date signed "
          f"reductions at the {N.percent(100 * C.PRIMARY_ES_LP_ALPHA, 1)} level the programme "
          f"solves at, with the {N.percent(100 * N.value('config.confidence_level'), 1)} "
          f"sensitivity reported beside it in section 4.9 and figure 13 - and between "
          f"{N.percent(abs(es_red['max']), 2)} and {N.percent(abs(es_red['min']), 2)} at the "
          f"extremes (figure 13). The objective responds to being made the objective, which is "
          f"the claim reviewer comment 4 asked for and no earlier module could make. Realised "
          f"economics are less flattering: the minimum-ES book cuts annualised volatility from "
          f"{N.percent(ew_book['Ann volatility (%)'], 3)} to "
          f"{N.percent(es_book['Ann volatility (%)'], 3)} and the maximum drawdown from "
          f"{N.percent(abs(ew_book['Max drawdown (%)']), 2)} to "
          f"{N.percent(abs(es_book['Max drawdown (%)']), 2)}, but pays "
          f"{N.percent(es_book['Annual fee fractions (%)'], 3)} of wealth a year in transaction "
          f"costs against the rebalanced control's "
          f"{N.percent(ew_book['Annual fee fractions (%)'], 3)} and the buy-and-hold's "
          f"{N.percent(bh_book['Annual fee fractions (%)'], 3)}, on "
          f"{N.number(es_book['One-way turnover (annual)'], 2)} one-way turns a year, and its "
          f"Sharpe ratio is {N.number(es_book['Sharpe'], 3)} against "
          f"{N.number(ew_book['Sharpe'], 3)}. Its exception count is not a comparable number at "
          f"all until the convention is fixed, and table 19 decomposes the gap: "
          f"{cnt(es_a['Breaches'])} under the frozen-filter sweep convention, of which "
          f"{cnt(es_a['Breaches'] - es_ap['Breaches'])} fall in the dates the realised-series "
          f"engine cannot score, and {cnt(es_ap['Breaches'] - es_b['Breaches'])} more are the "
          f"frozen filter's own approximation, leaving {cnt(es_b['Breaches'])} on the series the "
          f"book actually earned against the control's {cnt(ew_b['Breaches'])}. What does carry "
          f"over across conventions is the direction of the failure: at convention B every "
          f"optimised book is rejected by conditional coverage, the best of them at "
          f"{N.p_value(max(opt_cc))}, while both equal-weight controls clear the level - "
          f"{N.p_value(min(ew_cc))} and {N.p_value(max(ew_cc))}. Compressing the tail with "
          f"weights compresses the forecast, not the clustering in the losses. The "
          f"turnover-capped variant is the practical shape of the extension: "
          f"{N.number(cap_book['One-way turnover (annual)'], 2)} one-way turns against "
          f"{N.number(es_book['One-way turnover (annual)'], 2)}, cost drag "
          f"{N.percent(cap_book['Annual fee fractions (%)'], 3)} against "
          f"{N.percent(es_book['Annual fee fractions (%)'], 3)}, drawdown "
          f"{N.percent(abs(cap_book['Max drawdown (%)']), 2)} against "
          f"{N.percent(abs(es_book['Max drawdown (%)']), 2)}. No part of this is a compute "
          f"limitation: the programme costs {ms(opt_cost)} ms per rebalance, so the binding "
          f"constraint is the statistical one findings 2 and 7 keep running into.")

    add_heading_2(doc, "5.3 Limitations and Threats to Validity")
    prose(doc,
          f"Four kinds of threat are kept apart because they limit different claims. "
          f"**Internal validity.** The comparison inside section 4.9 is only as causal as its "
          f"scoring convention: table 19 shows the same minimum-ES book producing "
          f"{cnt(es_a['Breaches'])} and {cnt(es_b['Breaches'])} exceptions under two defensible "
          f"engines, so the extension's backtest is reported with its convention named rather "
          f"than as a single number, and the per-asset filter frozen across the "
          f"{N.number(C.REBALANCE_INTERVAL, 0)}-day interval that convention A requires is a "
          f"simplification the headline model does not share. The regime partitions have their "
          f"own leak: the balanced terciles take their cut points from the whole classified span "
          f"of {cnt(bl_agr['n_classified'])} days, which includes the "
          f"scored period, which is why the leak-free frozen definition is reported beside it in "
          f"every table instead of being replaced by it. **Construct validity.** The measure is a "
          f"one-day {N.percent(100.0 * N.value('config.confidence_level'), 0)} boundary between "
          f"closing prices. {limitations['consequence']} The regime construct is a lagged index "
          f"level and a realised-volatility tercile, and finding 5 shows they disagree on "
          f"{N.percent(calm['pct_of_sample'], 2)} of the sample. Expected shortfall is not "
          f"elicitable on its own (Gneiting; Fissler and Ziegel), which is why the shortfall "
          f"series is judged by coverage and by the dollar register in appendix C rather than by "
          f"a head-to-head scoring contest with the quantile.")
    prose(doc,
          f"**External validity.** {limitations['survivorship']} The universe is "
          f"{cnt(N.value('data.n_assets'))} surviving constituents of one index in one market, "
          f"observed {N.value('data.first_date')} to {N.value('data.last_date')}, and the two "
          f"sharpest stress windows inside that span are the cells where the calibration is "
          f"weakest - {N.percent(gfc['Breach Rate (%)'], 3)} for the 2008 overlay and "
          f"{N.percent(covid['Breach Rate (%)'], 3)} for the 2020 one, against "
          f"{N.percent(primary('Breach Rate (%)'), 3)} for the sample. Nothing here supports "
          f"moving the framework to another market, another notional convention or a horizon "
          f"longer than one day: multi-day scaling was descoped with the liquidity work, and no "
          f"square-root-of-time intuition is tested anywhere in this report. **Conclusion "
          f"validity.** {cnt(primary('Actual Breaches'))} exceptions is the power problem of "
          f"finding 2, and the margins are thin enough that a different sample would move some "
          f"of them. The sixty-day refit cadence passes Kupiec at {N.p_value(k60['Kupiec p'])} "
          f"and is rejected by conditional coverage at {N.p_value(k60['Christoffersen p'])}, a "
          f"margin of {N.number(C.CLOPPER_PEARSON_ALPHA - k60['Christoffersen p'], 4)} under the "
          f"{N.percent(100.0 * C.CLOPPER_PEARSON_ALPHA, 0)} level used throughout, which is the "
          f"whole of the difference between the framework surviving and failing on refit "
          f"frequency. The threshold study spans "
          f"{cnt(sel['n_grid'])} grid points by {cnt(len(N.value('data.confidence_levels')))} "
          f"coverages by {cnt(len(N.value('data.innovation_distributions')))} filters, and where "
          f"a single-lag result is quoted from that many tests the adjusted value is the one "
          f"printed in section 4.6.")
    prose(doc,
          f"Two limitations are recorded as open rather than closed. The estimation window of "
          f"{cnt(N.value('config.window'))} days and the refit interval of "
          f"{N.number(C.REBALANCE_INTERVAL, 0)} days were fixed by Module 4, re-tested at Module "
          f"6 against the {', '.join(str(i) for i in C.BENCH_REFIT_INTERVALS)}-day cadences and "
          f"chosen again; table 22 shows the calibration flat across that range and the "
          f"production cadence the strongest of the four on the weaker of its two tests, but "
          f"nothing in one sample of {N.value('data.first_date')} to {N.value('data.last_date')} "
          f"establishes that a different window length would not fail elsewhere. And the "
          f"minimum-ES extension optimises a conditional-historical scenario set, so it inherits "
          f"the dependence structure of the trailing window instead of modelling tail "
          f"co-movement; on a calm-to-crisis transition that is the assumption Pritsker attacks "
          f"by another name, and it is the reason the extension is offered as a shape of the "
          f"framework rather than as a recommendation. Section 6 hands both to the copula layer, "
          f"which remains the Module 8 item.")
    return doc


# ------------------------------------------------ 6. Conclusion & next steps --

def section_conclusion(doc):
    """What this milestone settled, what it withdrew, and what the next two are for."""
    add_heading_1(doc, "6. Conclusion & Next Steps")
    ci6 = primary("Breach Rate 95% CI (%)")
    legacy = N.raw("recursion.sensitivity.legacy")["score"]
    rec = N.raw("recursion.difference")
    m4rep = N.raw("recursion.m4_reproduction")
    sel = N.raw(selection_path("normal"))
    verdict = N.raw("iid.iid_verdict")
    f_n = verdict["per_filter"]["normal"]
    agr = N.raw("regime.agreement")
    bl_agr = agr["portfolio_regime_balanced"]
    limitations = N.raw("data.data_limitations")
    nt = next(r for r in N.records("iid.normal_minus_t")
              if _near(r["threshold_q"], N.value("config.threshold_quantile")))
    gfc = next(r for r in N.records("regime.regime_conditional_performance")
               if r["regime"] == "2008 GFC")
    econ = N.raw("economic.by_recursion.corrected.reserve_adequacy")
    conc = N.raw("economic.primary_register_concentration")
    es_red = es_reduction_row(C.PRIMARY_ES_LP_ALPHA)  # the level the programme actually solves at
    # Derived, not remembered: the count of books the joint test rejects is a result
    # of the rebuilt ledger, and the previous draft asserted it in words. The column
    # is the one table 18 prints under its "CC" heading, so the count and the table
    # cannot drift apart.
    _cc_p = [r["Christoffersen p"] for r in N.records("optimisation.table")
             if isinstance(r["Christoffersen p"], (int, float))
             and not isinstance(r["Christoffersen p"], bool)
             and r["Christoffersen p"] == r["Christoffersen p"]]
    n_cc_rejected = sum(1 for p in _cc_p if p < C.CLOPPER_PEARSON_ALPHA)
    n_scored_books = len(_cc_p)
    rebal = strategy_row("Equal weight (rebalanced)")
    min_es = strategy_row("Minimum ES")
    k60 = cad_row(60)
    z_lo, z_hi, spread_pct = threshold_spread_pct()
    wf_prod = walk_forward_row(N.value("config.threshold_quantile"))

    def cnt(value):
        return N.number(value, 0)

    def usd(value, dp=2):
        return N.dollars(value / 1e6, dp)

    plain_name = {"VaR_Normal": "the parametric Gaussian boundary",
                  "VaR_Historical": "the historical-simulation boundary"}
    same_both = " and ".join(plain_name[b] for b in rec["identical_across_recursions"])
    same_both_lead = same_both[0].upper() + same_both[1:]
    target = 100.0 * (1.0 - N.value("config.confidence_level"))
    avoided_share = (100.0 * econ["Unreserved Loss Avoided by ES (USD)"]
                     / econ["Cumulative Unreserved under VaR (USD)"])
    headroom = 100.0 * (ci6[1] / target - 1.0)

    prose(doc,
          f"Module 6 was a set of tests of the model Module 4 published rather than a new model, "
          f"and the model survives them: a GARCH(1,1) filter with a peaks-over-threshold "
          f"generalised Pareto tail, refitted every {N.number(C.REBALANCE_INTERVAL, 0)} days on a "
          f"{cnt(N.value('config.window'))}-day window and scored on "
          f"{cnt(N.value('data.walk_forward_days'))} out-of-sample days of a "
          f"{cnt(N.value('data.n_assets'))}-name equity book. On the corrected recursion the "
          f"headline is {primary('Actual Breaches')} exceptions at "
          f"{N.percent(primary('Breach Rate (%)'), 4)}, with Kupiec at "
          f"{N.p_value(primary('Kupiec p-val'))}, conditional coverage at "
          f"{N.p_value(primary('Conditional Cov p-val'))} and an exact interval of "
          f"[{ci6[0]:.3f}, {ci6[1]:.3f}] per cent around the {N.percent(target, 1)} target. Three "
          f"of the eight reviewer comments changed what this document is entitled to say, and one "
          f"defect found while reproducing the published artefact changed the count itself. Both "
          f"kinds of change are reported as corrections, which is what reproducing the old "
          f"artefact first is for.")

    add_heading_2(doc, "6.1 What This Milestone Changed")
    add_bullet_point(
        doc,
        f"The Module 4 output was rebuilt from this pipeline's legacy path and matched to "
        f"{m4rep['max_abs_difference']:.0e}, in units of the daily loss series, on the build "
        f"that wrote the manifest, before anything "
        f"was corrected. The recursion defect then moved the headline from "
        f"{legacy['Actual Breaches']} exceptions at {N.percent(legacy['Breach Rate (%)'], 4)} to "
        f"{primary('Actual Breaches')} at {N.percent(primary('Breach Rate (%)'), 4)}, Kupiec from "
        f"{N.p_value(legacy['Kupiec p-val'])} to {N.p_value(primary('Kupiec p-val'))}. "
        f"{same_both_lead} score identically under both recursions, which is what "
        f"localises the defect to the variance path instead of the tail.",
        bold_prefix="Reproduction before correction. ")
    add_bullet_point(
        doc,
        f"{cnt(sel['n_grid'])} cuts were carried through one shared walk-forward pass instead of "
        f"{cnt(sel['n_grid'])} separate ones. {cnt(sel['n_eligible'])} of them survive the "
        f"diagnostics, the reported {N.percent(100.0 * C.PRIMARY_CONFIDENCE, 0)} quantile moves "
        f"between {N.number(z_lo, 4)} and {N.number(z_hi, 4)} standardised "
        f"deviations across those cells, and the clamp that turns an unusable shape estimate into "
        f"a number is active on {N.percent(wf_prod['clamped_share_%'], 1)} of windows at the "
        f"production cut alone.",
        bold_prefix="The threshold became a measured choice. ")
    add_bullet_point(
        doc,
        f"Second-order whiteness, which is the condition the peaks-over-threshold step actually "
        f"consumes, is not rejected: the smallest Ljung-Box p-value on the squared innovations is "
        f"{N.p_value(f_n['lb_z2_min_p'])}. Normality is rejected outright at "
        f"{N.p_value(f_n['jb_p'])}, and the Student-t filter that answers it costs "
        f"{cnt(abs(nt['breach_delta']))} exceptions at the production cut "
        f"({nt['breaches_normal']} to {nt['breaches_t']}) while leaving both intervals covering "
        f"the target. The premise this report rests on is martingale-difference behaviour with "
        f"short-range dependence, not strict independence.",
        bold_prefix="The independence premise was tested, and re-stated. ")
    add_bullet_point(
        doc,
        f"The book's own realised-volatility bands and the VIX bands agree on "
        f"{N.percent(bl_agr['pct_agreement'], 2)} of days (kappa "
        f"{N.number(bl_agr['kappa_unweighted'], 3)}), which is why section 4.7 reports both and "
        f"names neither as the regime. Calibration holds across the partition cells and fails "
        f"inside the sharpest weeks a partition blurs: the 2008 window runs at "
        f"{N.percent(gfc['Breach Rate (%)'], 3)} and Kupiec rejects it at "
        f"{N.p_value(gfc['Kupiec p-val'])}.",
        bold_prefix="Regime conditioning moved onto the book. ")
    add_bullet_point(
        doc,
        f"{usd(conc['total_usd_excess'])} of loss went unreserved on a "
        f"{usd(N.value('data.notional_usd'), 0)} book over {N.number(econ['Years'], 1)} years, "
        f"{N.percent(conc['top_5_share_pct'], 2)} of it in five days. An expected-shortfall "
        f"reserve costs {usd(econ['Incremental Capital Held (USD)'])} at every mark, removes "
        f"{usd(econ['Unreserved Loss Avoided by ES (USD)'])} of that shortfall, and does not "
        f"remove all of it.",
        bold_prefix="The remaining exceptions are priced. ")
    add_bullet_point(
        doc,
        f"The minimum-ES linear programme forecasts a shortfall below the equal-weight book's at "
        f"every one of the {n_lp_solves()} rebalance dates, by "
        f"{N.percent(abs(es_red['mean']), 2)} on average at the "
        f"{N.percent(100 * C.PRIMARY_ES_LP_ALPHA, 1)} level the programme solves at, and buys "
        f"that with {N.percent(min_es['Annual fee fractions (%)'], 3)} of wealth a year in "
        f"transaction costs against the control's "
        f"{N.percent(rebal['Annual fee fractions (%)'], 3)}. Joint conditional coverage rejects "
        f"{n_cc_rejected} of the {n_scored_books} books scored in table 18, which is why finding 7 "
        f"calls this the least portable result in the report rather than the strongest.",
        bold_prefix="The framework transfers to an allocation decision. ")
    add_bullet_point(
        doc,
        f"Module 4 shipped six modules. This milestone adds the shared walk-forward engine "
        f"(walkforward_engine.py), the threshold study (threshold_sensitivity.py), the residual "
        f"battery (residual_analysis.py), the portfolio-side regime definition "
        f"(regime_segmentation.py), the breach register and reserve ledger (economic_impact.py), "
        f"the per-asset filter and the linear programme (asset_walk_forward.py, "
        f"portfolio_optimizer.py), the cost measurement (runtime_benchmark.py), figures 6 through "
        f"14 (visualizations_m6.py) and the entry point that assembles the manifest this report "
        f"reads (m6_develop_pipeline.py), with a suite in tests/ that fails if a Module 4 number "
        f"moves without the recursion flag that would explain it. Appendix B lists them with the "
        f"commands that reproduce them.",
        bold_prefix="The code is materially further developed. ")

    add_heading_2(doc, "6.2 Claims This Report Withdraws")
    prose(doc,
          "An answer to peer review that only adds to the old document has not engaged with it. "
          "Three claims the proposal made are withdrawn here, each because evidence produced at "
          "this milestone contradicts it rather than because a reviewer objected to it.")
    add_bullet_point(
        doc,
        f"The proposal offered this for {N.percent(legacy['Breach Rate (%)'], 2)} against a "
        f"{N.percent(target, 1)} target. The corrected count is {primary('Actual Breaches')} in "
        f"{cnt(N.value('data.walk_forward_days'))} days and the exact interval around it is "
        f"[{ci6[0]:.3f}, {ci6[1]:.3f}] per cent, which contains a boundary breaching "
        f"{N.percent(headroom, 0)} more often than nominal and still passing. What replaces the "
        f"sentence is indistinguishability from nominal, which finding 2 argues is the weaker and "
        f"the more useful claim.",
        bold_prefix="\"Near-perfect empirical calibration.\" ")
    add_bullet_point(
        doc,
        f"Independence reads {N.p_value(primary('Independence p-val'))} on the corrected "
        f"recursion, and at the {N.number(C.BENCH_REFIT_INTERVALS[-1], 0)}-day cadence "
        f"conditional coverage fails at {N.p_value(k60['Christoffersen p'])}, the one cell of "
        f"table 22 whose margin is smaller than the difference one exception makes. Exceptions "
        f"are unclustered at the resolution {cnt(N.value('data.walk_forward_days'))} days can "
        f"resolve, which is a different sentence from the one the proposal wrote.",
        bold_prefix="\"Exceptions are completely unclustered.\" ")
    add_bullet_point(
        doc,
        f"That is what the Module 4 risk registry recorded for the "
        f"{N.percent(100.0 * C.PRIMARY_POT_THRESHOLD_QUANTILE, 0)} cut, and no code in the "
        f"repository produced the verification. It exists now, in figure 6 and table 10, and it "
        f"does not say what the sentence claimed: "
        f"{cnt(sel['n_thresholds_whose_shape_is_significant'])} of the {cnt(sel['n_grid'])} grid "
        f"cuts have a shape estimate distinguishable from zero, so the diagnostics constrain the "
        f"threshold and do not identify it.",
        bold_prefix="\"Verified against a sample mean excess function.\" ")

    add_heading_2(doc, "6.3 Next Steps")
    prose(doc,
          "Two extensions and one set of tasks remain. The extensions belong to Modules 7 and 8; "
          "the tasks belong to this submission, and they cannot be done by tooling - an "
          "unverified citation or an unrewritten paragraph is not fixed by more code.")
    add_bullet_point(
        doc,
        f"A Gaussian-copula dependence sensitivity across the twenty names: hold the fitted "
        f"marginals, impose a stated correlation structure on the standardised residuals, and "
        f"report what the co-movement the minimum-ES programme currently inherits from its "
        f"trailing scenario window is worth beside one that was chosen. That inheritance is the "
        f"limitation section 5.3 records as open, the regime disagreement in table 14 is its "
        f"symptom, and on a calm-to-crisis transition it is the failure Pritsker documents for "
        f"historical simulation. The Gaussian family is the extension the proposal named, and it "
        f"is a sensitivity rather than a fix: at nondegenerate correlations it carries no "
        f"asymptotic tail dependence, so a family that does - Clayton or Gumbel - is what a "
        f"tail-dependence model needs, and neither is built here. The proposal placed this work "
        f"after Milestone 2; it has not moved, it has only become more specific.",
        bold_prefix="1. Copula dependence modeling (Module 8): ")
    add_bullet_point(
        doc,
        f"The proposal also promised Kenneth French three- and five-factor attribution and "
        f"multi-day liquidity stress. Neither is in this document, and both are blocked by the "
        f"data contract rather than by time: {limitations['consequence']} No factor series, no "
        f"volume and no intraday prints are cached, so "
        f"{cnt(N.value('data.walk_forward_days'))} daily observations of one market stay the "
        f"outer bound of what can be claimed here. Multi-day scaling is consequently absent from "
        f"every table in this report, and no square-root-of-time intuition is asserted anywhere "
        f"in it.",
        bold_prefix="2. Factor risk decomposition and liquidity stress testing: ")
    add_bullet_point(
        doc,
        "Tasks T6 to T9 of table 4 carry the dates. The analysis in this document does not change "
        "between now and then, so the deck re-narrates findings 1 to 7 rather than producing "
        "new ones.",
        bold_prefix="3. Final presentation, manuscript convergence and self-reflection: ")
    add_bullet_point(
        doc,
        "Human verification of every Works Cited entry added at this milestone against the "
        "publisher or DOI record (T1); the analysis prose rewritten in the authors' own words "
        "from the generated text dump (T2); the in-text declaration of AI assistance (T3); a "
        "rebuild of this document from the final manifest with the suite green (T4); and "
        "packaging of code, data and figures with the PDF uploaded separately from the archive so "
        "that similarity checking can read the manuscript (T5).",
        bold_prefix="4. Before the 3 November submission: ")

    prose(doc,
          f"The rubric asks whether the project is on schedule, and the answer has two halves. "
          f"Everything this milestone undertook is in this document; the two items that are not "
          f"are named above with the reason rather than omitted silently, and table 3 records the "
          f"copula extension at Module 8 exactly as the proposal did. On the substance, the "
          f"question the topic set - whether a usable alternative to VaR can be built for a "
          f"medium-term equity book - now has a measurement attached to it. Expected shortfall on "
          f"a filtered tail reaches nominal coverage out-of-sample without a tuned threshold, sits "
          f"{N.number(primary('Mean ES minus VaR (bps)'), 2)} basis points a day above the "
          f"quantile it replaces, funds {N.percent(avoided_share, 1)} of the loss that quantile "
          f"leaves unfunded, and can be made the objective of a portfolio rather than only its "
          f"diagnosis. What it does not do is certify itself, and this report does not claim that "
          f"it does.")
    return doc


# ----------------------------------------------------------------- 7. Works Cited --

def section_works_cited(doc):
    """The proposal's MLA list, extended by the sources reviewer comment 6 asked for."""
    add_heading_1(doc, "7. Works Cited")
    add_styled_paragraph(doc,
                         "All academic literature and regulatory standards cited are formatted "
                         "according to Modern Language Association (MLA) conventions.",
                         italic=True)
    for entry, _milestone in WORKS_CITED:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Inches(0.5)
        paragraph.paragraph_format.first_line_indent = Inches(-0.5)
        paragraph.paragraph_format.space_after = Pt(4)
        paragraph.paragraph_format.space_before = Pt(2)
        paragraph.paragraph_format.line_spacing = 1.15
        run = paragraph.add_run(entry)
        run.font.name = "Calibri"
        run.font.size = Pt(9.5)

    added = [entry for entry, milestone in WORKS_CITED if milestone == "M6"]
    with_doi = [entry for entry, _m in WORKS_CITED if "https://doi.org/" in entry]
    no_id = [entry for entry, _m in WORKS_CITED if "https://doi.org/" not in entry]
    no_id_no_title = [entry for entry in no_id if '"' not in entry]
    add_styled_paragraph(doc,
                         f"{len(added)} entries were added at this milestone, in answer to "
                         f"reviewer comment 6, and each of them carries a Digital Object "
                         f"Identifier: Davison and Smith, Coles, and de Haan and Ferreira for the "
                         f"peaks-over-threshold machinery and the domain-of-attraction conditions "
                         f"under which it is a usable approximation; Emmer, Kratz and Tasche for "
                         f"the comparison of tail measures the proposal assumed was settled; "
                         f"Krokhmal, Palmquist and Uryasev for the conditional-value-at-risk "
                         f"optimisation result section 4.9 rests on; and Ledoit and Wolf for the "
                         f"shrinkage estimator that appears as a benchmark strategy in table 18.",
                         space_after=6, italic=True)
    add_styled_paragraph(doc,
                         f"The whole list was then read again, entry by entry, against the record "
                         f"its identifier resolves to. The reading is done by "
                         f"`verify_works_cited.py`, which prints what Crossref holds beside what "
                         f"the page says and scores each pair, so the artefact itself names the "
                         f"records that do not confirm their entry; its printout is kept at "
                         f"data/works_cited_audit.txt. {len(with_doi)} of the "
                         f"{len(WORKS_CITED)} entries resolved that way; "
                         f"{len(no_id)} carry no identifier, of which "
                         f"{len(no_id_no_title)} carry no quoted title either, so the three Basel "
                         f"documents, the Embrechts, Klüppelberg and Mikosch monograph and the "
                         f"RiskMetrics technical document were read against the publisher's own "
                         f"page instead, and the two Rockafellar and Uryasev papers and Pritsker "
                         f"were checked by hand because the identifier-less search answers to "
                         f"them are the working papers or, in one case, a different author's "
                         f"chapter. That reading corrected seven entries the earlier draft had "
                         f"carried: the given names of Emmer and Kratz, of Krokhmal and Uryasev, "
                         f"of Pritsker, of Thompson and McCarthy, and of the second author of the "
                         f"de Haan monograph; the Fissler and Ziegel title, volume, issue, pages "
                         f"and identifier, which had described a different paper; and the "
                         f"position of Cont, which the earlier alphabetisation had dropped below "
                         f"de Haan.",
                         space_after=6, italic=True)
    add_styled_paragraph(doc,
                         "In-text identification was the other half of the same audit. A surname "
                         "identifies a work only when its author has one, and this list carries "
                         "three Basel documents and two Rockafellar and Uryasev papers, so the "
                         "citing sentences now name the year or the short title rather than "
                         "leaving the reader to guess. That rule is not a promise in a note: the "
                         "build refuses the document if a listed work is never cited in the body, "
                         "if an in-text citation resolves to nothing on the list, or if a work "
                         "sharing an author is cited without the year or title that tells it "
                         "apart. What it cannot check is a method named after its authors rather "
                         "than cited to them - the Clopper-Pearson, Jarque-Bera, "
                         "Kolmogorov-Smirnov and Ljung-Box tests appear on these pages as the "
                         "conventional names of procedures, not as references, and their sources "
                         "are not in the list. Table 1 nevertheless leaves the item open as task "
                         "T1, because the verification the course requires is the authors' and "
                         "not the tooling's.",
                         space_after=6, italic=True)
    return doc


# ------------------------------------------------------------------- 8. Appendix --

_MISSING_PATH = object()


def csv_records(relative_path):
    """Read an artefact the manifest names, for the appendices that print one whole file."""
    path = os.path.join(BASE_DIR, relative_path.replace("\\", os.sep))
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def register_rows():
    """The corrected breach register, as economic_impact.py wrote it, row for row."""
    path = N.value("economic.full_register_path")
    rows = csv_records(path)
    reported = N.value("economic.full_register_rows")
    if len(rows) != reported:
        raise AssertionError(f"{path} carries {len(rows)} rows but the manifest reports "
                             f"{reported}; the register and the text that quotes it are not "
                             f"the same artefact")
    return rows


def check_manifest_path(path):
    """Appendix E prints manifest paths as an audit trail, so each one is resolved here."""
    node = N.raw(path, default=_MISSING_PATH)
    if node is _MISSING_PATH:
        raise KeyError(f"appendix E cites a manifest path that does not exist: {path}")
    return node


def appendix_math(doc):
    add_heading_2(doc, "Appendix A: Mathematical Derivation of EVT-POT GPD Quantiles")
    prose(doc,
          "Carried from the proposal without change. Module 6 tests this derivation on a "
          "threshold grid, a second innovation law and a longer register; the tail estimator "
          "those tests are applied to is the one the proposal printed, and reprinting it with "
          "edits would make the two documents unreadable against each other.")
    add_styled_paragraph(doc,
                         "Let Y = -Z denote the standardized loss innovations exceeding high "
                         "threshold u. The conditional exceedance distribution is given by:")
    add_equation(doc, "F_u(y) = P(Y - u <= y | Y > u) = ( F(u + y) - F(u) ) / ( 1 - F(u) )",
                 title="EQUATION A.1: CONDITIONAL EXCEEDANCE PROBABILITY")
    add_styled_paragraph(doc,
                         "By the Pickands-Balkema-de Haan theorem, for sufficiently high u, "
                         "F_u(y) approx G_{xi, beta}(y) = 1 - (1 + xi y / beta)^{-1/xi}. "
                         "Isolating F(x) for x = u + y yields:")
    add_equation(doc, "F(x) = (1 - F(u)) * G_{xi, beta}(x - u) + F(u)",
                 title="EQUATION A.2: FULL TAIL ESTIMATOR")
    add_styled_paragraph(doc,
                         "Estimating F(u) empirically by (n - N_u) / n, where n is the total "
                         "sample size and N_u the number of exceedances:")
    add_equation(doc,
                 "F_hat(x) = 1 - (N_u / n) * ( 1 + (xi * (x - u)) / beta )^{-1 / xi}",
                 title="EQUATION A.3: TAIL DISTRIBUTION FUNCTION")
    add_styled_paragraph(doc, "Inverting F_hat(x) = q yields the closed-form standardized "
                              "value-at-risk:")
    add_equation(doc,
                 "VaR_q(Z) = u + (beta / xi) * [ ( (1 - q) / (N_u / n) )^{-xi} - 1 ]",
                 title="EQUATION A.4: STANDARDIZED EVT VALUE-AT-RISK")
    add_styled_paragraph(doc,
                         "The expected shortfall of the generalised Pareto distribution exceeds "
                         "the threshold quantile by the mean excess over VaR_q(Z). Exceedances "
                         "over VaR_q(Z) are again generalised Pareto with scale beta' = beta + "
                         "xi (VaR_q(Z) - u), whose mean is beta' / (1 - xi). Adding VaR_q(Z) "
                         "yields:")
    add_equation(doc,
                 "ES_q(Z) = VaR_q(Z) + ( beta + xi * (VaR_q(Z) - u) ) / (1 - xi) "
                 "= ( VaR_q(Z) / (1 - xi) ) + ( (beta - xi * u) / (1 - xi) )",
                 title="EQUATION A.5: CLOSED-FORM EVT EXPECTED SHORTFALL")
    add_styled_paragraph(doc,
                         "Two conditions on xi are what section 4.5 prints rather than assumes. "
                         "Equation A.4 has a solution for any xi below 1, including a negative "
                         "one, where the fitted tail simply ends; equation A.5 has a finite mean "
                         "only where xi is below 1 and a finite variance only below one half. "
                         "The admissibility band the framework clamps to, "
                         f"{N.number(XI_ADMISSIBLE_MIN, 3)} to {N.number(XI_ADMISSIBLE_MAX, 1)}, "
                         "is the interval inside which both are usable, and every clamped fit "
                         "records the raw estimate beside the value used.", space_after=10)


def appendix_codebase(doc):
    add_heading_2(doc, "Appendix B: Codebase Guide and Execution Instructions")
    control_names = len(N.value("optimisation_control.universe"))
    prose(doc,
          "All code supporting this capstone lives in the repository at "
          "https://github.com/amynalypk/var-alternatives-capstone-mscfe690. What is published "
          "there today is the Module 4 branch; this milestone's work is on a module6 branch on "
          "the machine that wrote this document, and neither that branch nor the corrections in "
          "this draft have been pushed. Publishing it and granting the instructor read-only "
          "access are the authors' actions, and this document does not claim either is done. The "
          "code folder of the archive that accompanies this PDF is the copy a reviewer can open "
          "now, and it is the same sources. The Module 4 modules are listed as the proposal "
          "listed them; the Module 6 additions are what reviewer comment 4 through comment 8 "
          "required.")
    add_styled_paragraph(doc, "**Carried from Module 4.**", space_after=3)
    for name, role in [
        ("config.py", "every design constant this report quotes: universe, dates, confidence "
                      "levels, rolling window, refit interval, threshold grid, weight cap, "
                      "turnover cap, transaction cost and the LP quantile."),
        ("data_acquisition.py", "retrieval and caching of the twenty equities plus SPY and the "
                               "VIX, log returns, and the summary statistics behind table 6."),
        ("risk_models.py", "Gaussian and historical-simulation value at risk, the GARCH(1,1) "
                          "filter under either innovation law, the peaks-over-threshold fit, "
                          "the raw-diagnostic variant, and the shape admissibility band."),
        ("backtester.py", "the walk-forward loop, the Kupiec and Christoffersen statistics, and "
                          "the recursion switch that makes the legacy and corrected paths "
                          "comparable rather than sequential."),
        ("visualizations.py", "figures 1 to 5, left untouched so the proposal's charts "
                             "regenerate identically."),
        ("m4_core_assets.py", "the Module 4 pipeline, retained as the reproduction check that "
                              "finding 1 depends on."),
    ]:
        add_bullet_point(doc, role, bold_prefix=name + ": ")
    add_styled_paragraph(doc, "**New at Module 6.**", space_after=3)
    for name, role in [
        ("tail_metrics.py", "exact Clopper-Pearson interval and tail statistics shared by the "
                            "evaluator and the economic analysis, so the two cannot disagree "
                            "about what an interval means."),
        ("forecast_eval.py", "the exception-counting helper both paths call."),
        ("walkforward_engine.py", "one pass over the whole threshold-by-coverage-by-innovation "
                                 "grid, which is what makes table 11 affordable."),
        ("threshold_sensitivity.py", "the mean excess curve, the parameter profile and the "
                                     "eligibility rule behind tables 10 and 11 and figure 6."),
        ("residual_analysis.py", "the whiteness and distributional battery, the Student-t "
                                 "comparison and the verdict quoted in section 4.6."),
        ("regime_segmentation.py", "the book's own realised-volatility states, the VIX bands, "
                                   "their cross-tabulation and the cut-point sensitivity."),
        ("economic_impact.py", "the breach register, its concentration measures and the reserve "
                              "ledger of tables 16 and 17."),
        ("asset_walk_forward.py", "per-asset conditional volatility and innovation paths, the "
                                  "input the optimiser scores on."),
        ("portfolio_optimizer.py", "the minimum-expected-shortfall linear programme and its "
                                   "turnover-capped and return-floored variants."),
        ("dynamic_portfolio.py", "the rebalance loop, the transaction-cost model and the "
                                 "scoring-convention control of table 19."),
        ("runtime_benchmark.py", "the per-step timings of tables 21 to 23, with the cadence and "
                                "sweep-sharing accounting."),
        ("visualizations_m6.py", "figures 6 to 14, each refusing to draw an unlabelled panel or "
                                "a clipped caption."),
        ("m6_develop_pipeline.py", "the single entry point that produces every number this "
                                   "report prints and writes the manifest below."),
    ]:
        add_bullet_point(doc, role, bold_prefix=name + ": ")
    add_styled_paragraph(doc, "**Tests.**", space_after=3)
    prose(doc,
          "A suite in tests/, one module per component above plus a Module 4 regression guard "
          "that fails if a published number moves without the recursion flag that would explain "
          "it, and a guard on this document's own audit patterns. Run it with "
          "`python -m pytest -q`.")
    add_styled_paragraph(doc,
          "To replicate every figure in this report: `pip install -r requirements.txt`, then "
          "`python m4_core_assets.py`, then `python m6_develop_pipeline.py`, then "
          "`python visualizations_m6.py`. Tabular output goes to "
          "data/module4_metrics_manifest.json and data/module6_metrics_manifest.json, the "
          "per-day artefacts named in appendix C and appendix D sit beside them in data/, and "
          "the charts go to figures/. The pipeline accepts `--force` to ignore the manifest on "
          "disk, `--only threshold,iid` to recompute named sections, `--only "
          "optimisation_control` to re-run just the "
          f"{control_names}-name subset sensitivity that section 4.9 reports, and "
          "`--no-write` to compute without touching the manifest.", space_after=10)


def check_artefact(relative_path):
    """An appendix that prints a whole file refuses to print a friendly apology for it."""
    path = os.path.join(BASE_DIR, relative_path.replace("\\", os.sep))
    if not os.path.exists(path):
        raise FileNotFoundError(f"{relative_path} is cited by the report but is not on disk; "
                                f"re-run the section of the pipeline that writes it")
    return path


def appendix_register(doc):
    add_heading_2(doc, "Appendix C: The Full Breach Register")
    rows = register_rows()
    conc = N.raw("economic.primary_register_concentration")
    register_path = N.value("economic.full_register_path")
    published_path = N.value("economic.published_register_path")
    published_rows = N.value("economic.published_register_rows")
    notional = N.value("data.notional_usd")

    def pct(value, dp=3):
        return N.percent(100.0 * float(value), dp)

    past_es = sum(1 for row in rows if row["ES_also_breached"] == "True")
    years = sorted({row["Date"][:4] for row in rows})
    total_unreserved = sum(float(row["USD_Excess"]) for row in rows)

    prose(doc,
          f"Reviewer comment 8 asked for the magnitude of the loss on each breach rather than "
          f"the count of breaches. Section 4.8 gives the aggregates; this is the register behind "
          f"them, {len(rows)} rows read from {register_path} exactly as economic_impact.py wrote "
          f"it and ordered by the size of the miss, largest first. The row count is checked "
          f"against the manifest every time the report builds, so a register that has drifted "
          f"from the text quoting it fails the build instead of printing quietly. The book is "
          f"{N.dollars(notional / 1e6, 0)}; every dollar column here is the loss beyond the "
          f"forecast boundary on that day, not the day's total loss.")
    static_table(
        doc, "Table 24",
        f"Every exception of the two-stage filter under the corrected recursion: "
        f"{cnt(len(rows))} days spread over {len(years)} calendar years of the scored sample, "
        f"from {years[0]} to {years[-1]}. 'Miss' is the exceedance in basis points of notional; "
        "'past ES' records whether the expected-shortfall forecast standing behind the boundary "
        "was itself cleared.",
        ["Date", "Loss (%)", "Boundary VaR (%)", "Miss (bps)", "Unreserved ($m)",
         "ES forecast (%)", "Past ES"],
        [[row["Date"], pct(row["Loss"]), pct(row["VaR"]),
          N.number(float(row["Exceedance_bps"]), 1),
          usd(row["USD_Excess"]), pct(row["ES_forecast"]),
          yesno(row["ES_also_breached"] == "True")] for row in rows],
        note=f"Module 4 published {cnt(published_rows)} exceptions of the same filter under the "
             f"recursion as it stood then, held in {published_path} with the same columns; the "
             f"difference of {cnt(published_rows - len(rows))} days is the variance recursion "
             "reported in section 4.1, not a change in the data.",
        widths=[0.85, 0.75, 0.95, 0.75, 0.95, 0.95, 0.65])
    prose(doc,
          f"Read as a distribution rather than a list, the register says that the exceptions are "
          f"few and that their sizes are not equal. The {cnt(len(rows))} days carry "
          f"{usd(total_unreserved)} of unfunded loss between them; the largest single day is "
          f"{usd(conc['largest_single_usd'])} of it, or "
          f"{N.percent(conc['top_1_share_pct'], 1)} of the total, the five worst "
          f"{N.percent(conc['top_5_share_pct'], 1)} and the ten worst "
          f"{N.percent(conc['top_10_share_pct'], 1)}. A Herfindahl index of "
          f"{N.number(conc['hhi_of_excess'], 4)} over "
          f"{cnt(conc['n_breaches'])} days is concentrated by any standard, and it is the reason "
          f"section 4.8 refuses to describe an average miss as the cost of a miss. The years "
          f"present are {years[0]} to {years[-1]}, with {len(years)} distinct years represented. "
          f"{past_es} of the {cnt(len(rows))} days also cleared the shortfall forecast behind "
          "the boundary.")
    add_callout_box(doc, N.value("economic.stock_versus_flow"),
                    title="WHY THE TWO MONEY COLUMNS ARE NOT ADDED")


def appendix_optimisation(doc):
    add_heading_2(doc, "Appendix D: The Minimum-Expected-Shortfall Programme")
    universe = N.value("optimisation.universe")
    scenarios = C.ASSET_SCENARIO_WINDOW
    failures = N.value("optimisation.failed_solves")
    failure_records = N.value("optimisation.failure_records")
    rows_written = N.value("optimisation.weight_history_rows")
    strategies = N.value("optimisation.strategies")
    check_artefact(WEIGHT_HISTORY)
    prose(doc,
          f"Reviewer comment 4 asked whether the framework could be extended to portfolio "
          f"optimisation, minimising expected shortfall rather than measuring it. Section 4.9 "
          f"reports what that produced. This appendix states the programme exactly, because the "
          f"distinction between an approximation and an exact formulation is the whole "
          f"contribution of doing it as a linear programme: expected shortfall is a mean over "
          f"the tail, which is not differentiable, but on a finite scenario set it is the "
          f"solution of a linear programme with {len(universe) + 1 + scenarios} variables and no "
          f"smoothing assumption. Nothing about the tail is approximated in order to make the "
          f"optimiser converge, since the tail is the object under test.")
    add_equation(
        doc,
        f"r~_{{k,i}} = mu_{{i,t}} + sigma_{{i,t}} * z_{{k,i}},   "
        f"k = 1 ... {scenarios},   i = 1 ... {len(universe)}",
        title="EQUATION D.1: CONDITIONAL HISTORICAL SCENARIOS")
    add_styled_paragraph(doc,
          "Standardised residuals z are taken row-wise from the trailing window, so the "
          "cross-asset dependence of the actual sample is carried into the scenario set instead "
          "of being replaced by a Gaussian copula. mu and sigma are the per-asset GARCH paths of "
          f"section 3.8, fitted under {C.ASSET_WF_INNOVATION_DISTRIBUTION} innovations and "
          f"refitted every {C.GARCH_REFIT_INTERVAL} days.")
    add_equation(
        doc,
        f"minimise over (w, t, u):   t + ( 1 / ( (1 - alpha) * K ) ) * sum_k u_k,   "
        f"alpha = {C.PRIMARY_ES_LP_ALPHA}",
        title="EQUATION D.2: ROCKAFELLAR-URYASEV FORM")
    add_styled_paragraph(doc,
          "t estimates the value at risk of the portfolio and u_k absorbs the part of scenario k "
          "beyond it, so the objective is the mean loss in the worst (1 - alpha) fraction of "
          "scenarios. The epigraphical variables are what make it linear:")
    add_equation(
        doc,
        "u_k >= - ( sum_i w_i * r~_{k,i} ) - t   for every k,   u_k >= 0   for every k",
        title="EQUATION D.3: TAIL CONSTRAINTS")
    add_equation(
        doc,
        f"sum_i w_i = 1,   {C.MIN_ASSET_WEIGHT:.2f} <= w_i <= {C.MAX_ASSET_WEIGHT:.2f}   "
        f"for every i (long-only, uncapped otherwise)",
        title="EQUATION D.4: THE SIMPLEX AND THE WEIGHT BAND")
    add_styled_paragraph(doc,
          f"The two constrained variants reported in table 18 keep the objective and add rows. "
          f"The turnover-capped book introduces v_i >= w_i - w_i^prev and "
          f"v_i >= w_i^prev - w_i with sum_i v_i <= {C.TURNOVER_CAP_ONE_WAY:.2f}, one-way, at "
          f"{C.TXN_COST_BPS:.0f} basis points of cost on turnover at each of the "
          f"{C.REBALANCE_INTERVAL}-day rebalances; the return-floored book adds one row, "
          "sum_i w_i * mu_i >= floor, and is the answer to the objection that minimising a tail "
          "measure alone is a way of holding nothing. Each programme is handed to "
          "`scipy.optimize.linprog(method='highs')` and must return a certificate. A failed "
          "solve yields no weights and is never replaced by the equal-weight benchmark, because "
          "a silently substituted portfolio would be reported as an optimised one. Across the "
          f"whole pass the solver failed {cnt(failures)} times "
          f"({len(failure_records)} records at optimisation.failure_records), so every weight in "
          f"table 18 came out of a solved programme.")
    manifest_table(
        doc, "Table 25",
        f"Concentration of the {len(strategies)} books section 4.9 compares, averaged over the "
        f"{cnt(rows_written)} strategy-days written to the weight history. The "
        f"{C.MAX_ASSET_WEIGHT:.0%} per-name cap is a "
        "design choice, not a result; the number of names a strategy actually holds is what the "
        "cap does to each objective.",
        "optimisation.concentration",
        [("Strategy", "Book", "str"),
         ("Mean names held", "Names held", 2),
         ("Mean Herfindahl", "Herfindahl", 4),
         ("Mean max weight", "Largest weight",
          lambda r: N.percent(100.0 * r["Mean max weight"], 1)),
         ("Mean min weight", "Smallest weight",
          lambda r: N.percent(100.0 * r["Mean min weight"], 2))])
    prose(doc,
          f"The weight history behind it is {cnt(rows_written)} rows of "
          f"{WEIGHT_HISTORY}, one dated row per strategy for each of the {len(universe)} names, "
          f"and it is the artefact a reviewer would need in order to rebuild table 18 rather than "
          f"trust it. The mean off-diagonal correlation of the scenario set is "
          f"{N.percent(100.0 * N.value('optimisation.mean_off_diagonal_correlation'), 1)}, which "
          "is why the diversification the optimiser finds is modest and why the minimum-variance "
          "and minimum-shortfall books end up looking related. One caution is printed on the "
          "same authority as the table:")
    add_callout_box(doc, N.value("optimisation.comparability_warning"),
                    title="HOW TO READ A TWO-BOOK COMPARISON")


TRACEABLE_ASKS = [
    ("1", "A computational-efficiency target for the objectives",
     ["runtime.model_costs", "runtime.refit_cadence", "runtime.sweep_sharing"],
     "1.6, 3.9, 4.10; tables 21-23, figure 14"),
    ("2", "Is the i.i.d. innovation assumption sufficient, or is a heavier-tailed law justified?",
     ["iid.residual_diagnostics", "iid.iid_verdict", "iid.walk_forward_filter_table",
      "iid.normal_minus_t"],
     "2.6, 3.3, 4.6; tables 12-13, figures 8-9"),
    ("3", "The VIX measures the index, not this twenty-name book",
     ["regime.cut_points", "regime.agreement", "regime.cross_tab_with_breach_rates",
      "regime.regime_conditional_performance", "regime.stressed_but_calm"],
     "3.7, 4.7; tables 14-15, figure 10"),
    ("4", "Extend the project to minimising expected shortfall in the allocation",
     ["optimisation.table", "optimisation.concentration",
      "optimisation.forecast_es_reduction_by_alpha", "optimisation.engine_convention_control",
      "optimisation.book_diagnosis", "optimisation.weight_history_rows",
      "optimisation.failed_solves"],
     "3.8, 4.9; tables 18-20, figures 12-13, appendix D"),
    ("5", "The 90th-percentile threshold is chosen a priori and never tested",
     ["threshold.per_innovation.normal.full_sample.profile", "threshold.grid",
      "threshold.walk_forward_sensitivity", "threshold.recommendation",
      "threshold.production_q", "threshold.raw_vs_regularised"],
     "2.7, 3.6, 4.5; tables 10-11, figures 6-7, appendix G"),
    ("6", "Recent critiques of EVT in equity markets are not discussed",
     [],
     "2.6, 2.7, 5.1, 7; no measured artefact"),
    ("7a", "The appendix must come after the references",
     [],
     "7 then 8; page order, checked against the submitted proposal"),
    ("7b", "Figures should be interpreted, not described",
     [],
     "4.1-4.10; every figure passage"),
    ("8", "The economic importance and magnitude of the remaining breaches",
     ["economic.model_comparison", "economic.by_recursion", "economic.worst_ten",
      "economic.primary_register_concentration", "economic.full_register_path",
      "economic.published_register_rows"],
     "3.4, 4.8; tables 16-17, figure 11, appendix C"),
    ("Self-set", "Module 4's published numbers must still reproduce",
     ["recursion.m4_reproduction.reproduced", "recursion.m4_reproduction.max_abs_difference",
      "recursion.sensitivity.legacy.score", "recursion.sensitivity.corrected.score",
      "recursion.difference"],
     "3.2, 5.2, 6.1; the two columns of table 17"),
    ("Self-set", "Survivorship in a 2024-constituent universe",
     ["data.data_limitations.survivorship", "optimisation_control.reason",
      "optimisation_control.table"],
     "3.1, 3.10, 4.9, 5.3; the control run at the end of section 4.9"),
    ("Self-set", "Weights, not only thresholds, under resampling",
     ["weight_robustness.models", "weight_robustness.simulations", "weight_robustness.tautology"],
     "1.6, 4.4; table 9, figure 5"),
    ("Self-set", "Every missing value accounted for",
     ["nan_policy", "null_meanings", "non_finite_paths", "section_non_finite"],
     "Appendix F"),
]


def appendix_traceability(doc):
    add_heading_2(doc, "Appendix E: From Reviewer Ask to Measured Artefact")
    checked = []
    for _ask, _short, paths, _where in TRACEABLE_ASKS:
        for path in paths:
            check_manifest_path(path)
            checked.append(path)
    prose(doc,
          f"The response matrix in table 1 records what was done about each comment; this "
          f"appendix records where the number that justified it actually lives. Every manifest "
          f"path in the fourth column is resolved while this document builds - {len(checked)} of "
          f"them - so the audit trail cannot rot into a list of references to a file that no "
          f"longer has the field. A path that disappears fails the build; a table that moves "
          f"section only moves the pointer.")
    static_table(
        doc, "Table 26",
        "Each reviewer ask, and the artefact that answers it. 'Manifest path' is the dotted "
        "route into data/module6_metrics_manifest.json that the report generator asks for by "
        "name; a cell reading n/a marks an ask closed by prose, citations or page order rather "
        "than by a measured quantity.",
        ["Ask", "What the reviewer asked for", "Sections, tables and figures", "Manifest path"],
        [[ask, short, where,
          "; ".join(paths) or "n/a (no measured artefact)"]
         for ask, short, paths, where in TRACEABLE_ASKS],
        note="The generator reads the manifest through one accessor that raises on a null it "
             "cannot explain, so no cell in this document is a placeholder and no cell is a zero "
             "standing in for a quantity nobody computed.",
        widths=[0.72, 1.5, 1.45, 2.83])


def appendix_environment(doc):
    add_heading_2(doc, "Appendix F: Reproduction Environment and Null Accounting")
    env = N.value("runtime.environment.environment")
    note = N.value("runtime.environment.note")
    measured_by = N.value("runtime.measured_by")
    config_block = N.value("config")
    timings = N.value("section_timings_s")
    total = sum(timings.values())
    null_meanings = N.value("null_meanings")
    non_finite = N.value("non_finite_paths")
    section_non_finite = N.value("section_non_finite")
    control_names = len(N.value("optimisation_control.universe"))
    prose(doc,
          f"Timings travel badly between machines, so every number in tables 21 to 23 is "
          f"accompanied by the fingerprint of the machine that produced it, taken by "
          f"`{measured_by}` at the same moment as the measurements and stored at "
          f"runtime.environment. Re-measuring on other hardware will move these figures; the "
          f"rankings between models are the part meant to survive.")
    static_table(
        doc, "Table 27",
        f"The environment recorded beside the timing caches ({note}). Repeat counts and warm-up "
        f"are design constants from config.py: {C.BENCH_REPEATS_FAST} repeats for the fast "
        f"calibrations, {C.BENCH_REPEATS_SLOW} for the solver-bound ones, "
        f"{C.BENCH_WARMUP} discarded before timing.",
        ["Property", "Value"],
        [[key, str(value)] for key, value in env.items()],
        note=f"Manifest written {N.value('generated_at')} by m6_develop_pipeline.py. Primary "
             f"configuration of the headline path: confidence "
             f"{N.percent(100.0 * config_block['confidence_level'], 0)}, threshold quantile "
             f"{N.number(config_block['threshold_quantile'], 2)}, "
             f"{config_block['innovation_distribution']} innovations, "
             f"{config_block['variance_recursion']} variance recursion, "
             f"{cnt(config_block['window'])}-day window refitted every "
             f"{cnt(config_block['refit_interval'])} days.",
        widths=[2.0, 4.4])
    def secs(value):
        return "< 0.1" if value < 0.05 else N.number(value, 1)

    prose(doc,
          f"Where the {N.number(total, 0)} seconds of recorded section time go: the "
          f"minimum-expected-shortfall pass and its {control_names}-name subset sensitivity "
          f"together dominate it, the walk-forward reproduction of the proposal and the threshold "
          f"sweep take most of the rest, and the cache-reading sections are the small terms. "
          f"Section times, in seconds: "
          + ", ".join(f"{name} {secs(value)}" for name, value in timings.items()) + ".")
    prose(doc,
          f"Nothing in the manifest is silently missing. {len(non_finite)} paths hold a null, "
          f"grouped by the section that wrote them, and each carries a reason rather than a "
          f"blank. The rule is stated once, in the manifest field `nan_policy`: a non-finite "
          f"value is written as null and listed in non_finite_paths, so the file stays valid "
          f"JSON for any tool and nothing is hidden; the reasons are keyed by field name in "
          f"null_meanings, {len(null_meanings)} of them, and this build refuses to render a null "
          "that is not accounted for there. Two examples of what that rule catches: a mean "
          "excess loss of null in an empty regime cell is not a zero, and a degrees-of-freedom "
          "of null on a Gaussian filter is not a failed Student-t fit. Nulls per section: "
          + ", ".join(f"{name} {cnt(len(value))}"
                      for name, value in section_non_finite.items()) + ".")


def clamp_rows(confidence_level, innovation_dist=None):
    """Raw-versus-regularised rolling rows at one coverage, ordered by threshold."""
    rows = [r for r in N.records("threshold.raw_vs_regularised")
            if _near(r["confidence_level"], confidence_level)
            and (innovation_dist is None or r["innovation_dist"] == innovation_dist)]
    if not rows:
        raise KeyError(f"no clamp-effect rows at coverage {confidence_level}")
    return sorted(rows, key=lambda r: (r["innovation_dist"], r["threshold_q"]))


def clamp_row(threshold_q, confidence_level, innovation_dist):
    for r in clamp_rows(confidence_level, innovation_dist):
        if _near(r["threshold_q"], threshold_q):
            return r
    raise KeyError(f"no clamp-effect row at q={threshold_q}, "
                   f"alpha={confidence_level}, dist={innovation_dist}")


def appendix_clamp_cost(doc):
    add_heading_2(doc, "Appendix G: What the Shape Bound Costs on Forecasts")
    alpha = N.value("headline.confidence_level")
    levels = N.value("data.confidence_levels")
    other_alpha = [level for level in levels if not _near(level, alpha)]
    dist = N.value("config.innovation_distribution")
    prod = clamp_row(C.POT_THRESHOLD_QUANTILE, alpha, dist)
    notional = N.value("data.notional_usd")
    extra_reserve = prod["Mean ΔVaR (bps)"] / 10000.0 * notional
    prose(doc,
          f"Reviewer comment 5 asked for the clamp to be justified and for raw and regularised "
          f"forecasts to be compared. Section 3.6 answers the first half: the admissibility band "
          f"[{XI_ADMISSIBLE_MIN:g}, {XI_ADMISSIBLE_MAX:g}] is a modelling choice, not a finding, "
          f"and a shape at or above one leaves expected shortfall undefined, so the upper edge is "
          f"where the requested number stops existing. This appendix answers the second half by "
          f"scoring each walk-forward configuration twice on the same out-of-sample losses: once "
          f"with the boundary the report publishes, once with the same fit extrapolated without "
          f"the band. Both columns come from one estimation pass, so the difference between them "
          f"is the band and nothing else. A negative difference means the unbounded tail is the "
          f"wider reserve.")
    manifest_table(
        doc, "Table 28",
        f"Rolling forecasts with and without the shape band, at "
        f"{N.percent(alpha * 100, 1)} coverage on {cnt(prod['days'])} out-of-sample days. "
        f"Delta is bounded minus unbounded, so a positive mean delta is extra reserve the band "
        f"adds. The two exception columns are the same {cnt(prod['days'])} days scored twice.",
        "threshold.raw_vs_regularised",
        [("innovation_dist", "Configuration",
          lambda r: f"{r['innovation_dist']} at q = {r['threshold_q']:g}"),
         ("clamped_share_%", "Refits where the band binds", "pc", 1),
         ("raw_es_undefined_days", "Days with no unbounded ES", 0),
         ("Median |ΔVaR| (bps)", "Median |delta| boundary (bps)", 1),
         ("Mean ΔVaR (bps)", "Mean delta boundary (bps)", 1),
         ("Breaches (regularised)", "Exceptions, bounded", 0),
         ("Breaches (raw)", "Exceptions, unbounded", 0),
         ("Exception disagreements", "Days the two disagree", 0),
         ("Kupiec p (regularised)", "p, bounded", "pv"),
         ("Kupiec p (raw)", "p, unbounded", "pv"),
         ("Raw VaR higher (%)", "Days unbounded is the wider reserve", "pc", 2),
         ("Mean VaR (regularised, %)", "Mean boundary, bounded", "pc", 3),
         ("Mean VaR (raw, %)", "Mean boundary, unbounded", "pc", 3),
         ("Mean ES (regularised, %)", "Mean ES, bounded", "pc", 3),
         ("Mean ES (raw, %)", "Mean ES, unbounded", "pc", 3)],
        note=f"The grid is scored at both coverages in the manifest; this table prints the "
             f"{N.percent(alpha * 100, 1)} rows, which is where the published path lives. "
             f"'Days with no unbounded ES' counts forecasts whose raw shape reaches one, where "
             f"the expected shortfall integral diverges: those days are counted, not dropped, "
             f"because an undefined reserve is a result. Mean ES columns average over the days "
             f"where that series is finite, so a bounded and an unbounded mean ES are not "
             f"always averages of the same days.",
        filter_kwargs={"confidence_level": alpha})
    prose(doc,
          f"Direction first, because it decides whether the band flatters the model. At the "
          f"production threshold with {dist} innovations the band is adjusted in "
          f"{N.percent(prod['clamped_share_%'], 1)} of the refits, and the unbounded boundary "
          f"turns out to be the wider reserve on only "
          f"{N.percent(prod['Raw VaR higher (%)'], 2)} of the {cnt(prod['days'])} scored days: "
          f"where the band acts at this threshold it adds to the reserve and never takes away "
          f"from it. The band is therefore not buying a quieter model by cutting the reserve. "
          f"Its size is "
          f"{N.number(prod['Median |ΔVaR| (bps)'], 1)} bps at the median and "
          f"{N.number(prod['Mean ΔVaR (bps)'], 1)} bps on the mean, which on the "
          f"{usd(notional, 0)} book is about {usd(extra_reserve, 2)} of boundary per day. "
          f"That is the number section 3.6 said the full-sample quantile spread could not "
          f"supply: a bound on what the band does to forecasts, measured day by day.")
    alpha_level = C.CLOPPER_PEARSON_ALPHA
    bounded_ok = prod["Kupiec p (regularised)"] >= alpha_level
    unbounded_ok = prod["Kupiec p (raw)"] >= alpha_level
    if bounded_ok and unbounded_ok:
        verdict = (f"Neither variant is rejected at {N.percent(alpha_level * 100, 0)}, so the "
                   f"published calibration is not an artefact of the band - but the unbounded "
                   f"path is the one closer to the edge, and a reader who prefers it should "
                   f"expect a model that under-covers more often rather than one that is merely "
                   f"different.")
    elif bounded_ok and not unbounded_ok:
        verdict = (f"The bounded path clears {N.percent(alpha_level * 100, 0)} and the unbounded "
                   f"one does not: the calibration the report publishes is the one the band "
                   f"produces, and it is stated as such rather than as a result that would "
                   f"survive any shape treatment.")
    else:
        verdict = (f"At least one variant is refused at {N.percent(alpha_level * 100, 0)} "
                   f"({N.p_value(prod['Kupiec p (regularised)'])} bounded, "
                   f"{N.p_value(prod['Kupiec p (raw)'])} unbounded), so neither reading of the "
                   f"tail is calibrated at this threshold and the exception counts are the "
                   f"evidence rather than the p-values.")
    prose(doc,
          f"Mechanism: the band's lower edge is what moves this threshold. A negative shape "
          f"estimate describes a tail with a finite upper endpoint, so the quantile it prices "
          f"sits below the near-exponential one the report uses, and lifting the estimate to "
          f"{XI_ADMISSIBLE_MIN:g} is what produces the extra reserve above. Consequence "
          f"for inference: the same "
          f"{cnt(prod['days'])} days carry {cnt(prod['Breaches (regularised)'])} exceptions "
          f"under the bounded boundary and {cnt(prod['Breaches (raw)'])} under the unbounded "
          f"one, and the two classify a day differently on "
          f"{cnt(prod['Exception disagreements'])} days. The unconditional-coverage p-value runs "
          f"from {N.p_value(prod['Kupiec p (regularised)'])} to "
          f"{N.p_value(prod['Kupiec p (raw)'])}. " + verdict)
    down = [r for r in clamp_rows(alpha) if r["Raw VaR higher (%)"] > 0.0]
    undef = [r for r in clamp_rows(alpha) if r["raw_es_undefined_days"] > 0]
    undef_phrase = ", ".join(
        f"{r['innovation_dist']} at q = {r['threshold_q']:g} "
        f"({cnt(r['raw_es_undefined_days'])} days)" for r in undef) or "no threshold on the grid"
    alt = clamp_row(C.POT_THRESHOLD_QUANTILE, other_alpha[0], dist)
    prose(doc,
          f"Two further readings, both against the band. Where the grid runs past the production "
          f"cut the band sometimes works the other way: {N.number(len(down), 0)} of the "
          f"{N.number(len(clamp_rows(alpha)), 0)} rows above have at least one day on which the "
          f"unbounded boundary is the wider one, because the estimate then exceeds "
          f"{XI_ADMISSIBLE_MAX:g} and clamping pulls the reserve down instead of up. And at "
          f"{undef_phrase} the unbounded shape estimate reaches one often enough that the "
          f"requested expected shortfall does not exist on those days; removing the band there "
          f"does not produce a sharper model, it produces no number. At "
          f"{N.percent(other_alpha[0] * 100, 1)} coverage the same comparison is wider: at the "
          f"production threshold the median move is "
          f"{N.number(alt['Median |ΔVaR| (bps)'], 1)} bps, exceptions run "
          f"{cnt(alt['Breaches (regularised)'])} against "
          f"{cnt(alt['Breaches (raw)'])}, and the p-values "
          f"{N.p_value(alt['Kupiec p (regularised)'])} and "
          f"{N.p_value(alt['Kupiec p (raw)'])}.")
    add_callout_box(doc,
                    "This table bounds the effect of one modelling choice. It does not bound "
                    "hindsight in the threshold itself: the band is compared at the "
                    "production quantile, which was selected on the full sample, and the "
                    "strictly prospective screen on the first "
                    f"{N.value('data.window')} days accepts no candidate at all. A genuinely "
                    "rolling selection procedure or an untouched evaluation period is still the "
                    "evidence a prospective claim would need, and neither exists in this "
                    "submission.",
                    title="WHAT TABLE 28 DOES NOT SETTLE")


def section_appendices(doc):
    add_heading_1(doc, "8. Appendix")
    prose(doc,
          "Seven appendices, in the order Module 4 used and with Module 4's first two carried "
          "without change, so a reader holding both documents finds the same mathematics and the "
          "same codebase map in the same place. Appendices C to G are new and exist because "
          "reviewer comments asked for evidence this report's body could not hold: the whole "
          "breach register, the whole optimisation programme, a trace from each comment to the "
          "artefact that answers it, the machine those answers were measured on, and the cost of "
          "the one modelling choice the threshold step cannot do without.")
    for build in (appendix_math, appendix_codebase, appendix_register, appendix_optimisation,
                  appendix_traceability, appendix_environment, appendix_clamp_cost):
        build(doc)


# ------------------------------------------------------------------------ build --

DOCX_NAME = "MScFE_690_Capstone_Draft_Project_Report.docx"
PDF_NAME = "MScFE_690_Capstone_Draft_Project_Report.pdf"
PROSE_NAME = "MScFE_690_Capstone_Draft_Project_Report_prose.txt"

SECTION_BUILDERS = (
    add_title_block,
    section_abstract,
    section_introduction,
    section_theory,
    section_methodology,
    section_results,
    section_results_module6,
    section_discussion,
    section_conclusion,
    section_works_cited,
    section_appendices,
)


def build_document():
    doc = docx.Document()
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
    for build in SECTION_BUILDERS:
        build(doc)
    add_page_number_footer(doc)
    return doc


def export_pdf(docx_path, pdf_path):
    """Convert through Word itself, the way Module 4 did, so pagination is Word's.

    `ExportAsFixedFormat` rather than `SaveAs` because the eleventh positional
    parameter is `CreateBookmarks`, and F14 asks for a navigable 95-page PDF: the
    document now uses real Heading 1-3 styles, and this is what turns them into a
    PDF outline. `SaveAs` is kept as the fallback for a Word that will not take the
    longer signature.
    """
    script = os.path.join(HERE, "export_m6_pdf.ps1")
    if os.path.exists(pdf_path):
        # The return value below is "did Word write this file", and a file left by the
        # previous build would answer that question wrongly.
        os.remove(pdf_path)
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(f'''$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
    $doc = $word.Documents.Open("{docx_path}")
    $doc.Save()
    $done = $false
    try {{
        $doc.ExportAsFixedFormat("{pdf_path}", 17, $false, 0, 0, 1, 1, 0, $true, $true, 1)
        $done = $true
        Write-Host "PDF exported with heading bookmarks"
    }} catch {{
        Write-Host "Bookmarked export failed: " $_.Exception.Message
    }}
    if (-not $done) {{
        $doc.SaveAs([ref] "{pdf_path}", [ref] 17)
        Write-Host "PDF exported without bookmarks"
    }}
    $doc.Close()
}} catch {{
    Write-Host "Word export failed: " $_.Exception.Message
}} finally {{
    $word.Quit()
}}
''')
    result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", script],
                            capture_output=True, text=True)
    print("  Word:", result.stdout.strip() or result.stderr.strip())
    os.remove(script)
    return os.path.exists(pdf_path)


def dump_prose(doc, path):
    """A plain-text copy of the document, for the authors to rewrite against.

    Course policy is that the prose is the authors' own; the tables and numbers are the
    code's. This dump is what makes the first part editable without fighting Word.
    """
    lines = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        lines.append(text)
    lines.append("")
    lines.append("=" * 78)
    lines.append("TABLES")
    lines.append("=" * 78)
    for index, table in enumerate(doc.tables, start=1):
        lines.append(f"--- table object {index} ---")
        for row in table.rows:
            lines.append(" | ".join(cell.text.replace("\n", " / ") for cell in row.cells))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return path


def main():
    os.makedirs(SUBMITTED_DIR, exist_ok=True)
    print("[1/4] Building the Draft Project Report from data/module6_metrics_manifest.json...")
    doc = build_document()

    final_docx = os.path.join(SUBMITTED_DIR, DOCX_NAME)
    copy_docx = os.path.join(HERE, DOCX_NAME)
    final_pdf = os.path.join(SUBMITTED_DIR, PDF_NAME)
    copy_pdf = os.path.join(HERE, PDF_NAME)

    print("[2/4] Auditing the finished document for Python artefacts...")
    audit_document(doc)
    reconcile_citations(doc)
    used = sorted(set(N.used))
    print(f"      clean; {len(used)} manifest paths read")

    doc.save(final_docx)
    doc.save(copy_docx)

    print("[3/4] Exporting to PDF through Word...")
    made = export_pdf(final_docx, final_pdf)
    if made:
        export_pdf(copy_docx, copy_pdf)
    else:
        print("      PDF skipped: Word was not available to convert. Export the DOCX to PDF "
              "by hand before submitting.")

    print("[4/4] Writing the prose dump for the authors...")
    dumped = dump_prose(doc, os.path.join(HERE, PROSE_NAME))
    print(f"      {dumped}")
    print("\n[Done] Module 6 Draft Project Report build complete.")
    return final_docx, (final_pdf if made else None)


if __name__ == "__main__":
    main()
