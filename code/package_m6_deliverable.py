"""Assemble the Module 6 submission archive.

The archive is a snapshot, not a copy of the working tree: it carries the code the
report describes, the per-day artefacts the report names, the fourteen figures it
contains, and the tests that hold both in place - and no run logs, no caches and no
editors' debris, because a reviewer cannot grade a file that was never part of the
argument.

Run it after the report builds cleanly:

    python "Module 6 Develop/package_m6_deliverable.py"

It stages the snapshot in a temporary directory and copies only the completed ZIP
beside this script. Existing code/, tests/, data/, figures/ and submitted/ folders
are never modified. The report build sources are included, but the manuscript PDF
is submitted separately.
"""

import json
import os
import re
import shutil
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SNAPSHOT_DIRS = ("code", "tests", "data", "figures")
ZIP_NAME = "MScFE_690_Capstone_Module6_Deliverables.zip"

# Everything the report's argument rests on, by name rather than by wildcard, so a
# stray artefact cannot join the submission just because it landed in data/ first.
DATA_FILES = [
    "module4_metrics_manifest.json",
    "module6_metrics_manifest.json",
    "sp500_market_data_2005_2024.csv",
    "backtest_results_500w.csv",
    "m4_baseline_backtest.csv",
    "m4_breach_register_garch_evt.csv",
    "m6_breach_register_garch_evt.csv",
    "m6_investable_backtest.csv",
    "m6_optimisation_paths.csv",
    "m6_optimisation_weight_history.csv",
    "m6_multi_config_walkforward.csv",
    "m6_multi_config_walkforward_legacy.csv",
    # Each sweep cache travels with the fingerprint that authorises reading it.
    # Without the sidecar a reviewer's run treats a shipped cache as unverified
    # and recomputes it, which needs the price history all over again.
    "m6_multi_config_walkforward.csv.meta.json",
    "m6_multi_config_walkforward_legacy.csv.meta.json",
    "m6_runtime_environment.json",
    "m6_runtime_model_costs.csv",
    "m6_runtime_refit_cadence.csv",
    "m6_runtime_sweep_sharing.csv",
    # The report's Works Cited note points a reviewer at this printout, so the
    # archive has to carry the file it names rather than only the claim about it.
    "works_cited_audit.txt",
]
# The per-asset walk-forward store is what makes section 4.9 reproducible without
# re-estimating two hundred and twenty-seven refits per name.
ASSET_STORE_DIR = "asset_wf"
DOCS = ["README.md", "CONTRIBUTORS.md", "requirements.txt", "pyproject.toml"]
# Keep the complete build chain together under code/. Its parent is the archive
# root, so the existing report builders can find data/ and figures/ unchanged.
LOCAL_SCRIPTS = [
    "m6_numbers.py",
    "build_m6_deliverable.py",
    "generate_m6_final_docx.py",
    "package_m6_deliverable.py",
    # The report describes how its bibliography was audited, and ships the auditor.
    "verify_works_cited.py",
]
# The archive must contain the file each of these manifest routes points at, or the
# report cites an artefact the reviewer cannot open.
CITED_PATH_ROUTES = [
    "economic.full_register_path",
    "economic.published_register_path",
    "recursion.m4_reproduction.baseline_artefact",
    "optimisation.forecast_es_reduction_path",
]
WEIGHT_HISTORY = "data/m6_optimisation_weight_history.csv"


def route(manifest, dotted):
    node = manifest
    for part in dotted.split("."):
        node = node[part]
    return node


def collect():
    """Return the {(archive_name, absolute_source_path)} list for the whole submission."""
    entries = []

    # Repository modules are authoritative, never the old Module 6 snapshot.
    # In an extracted ZIP, this script and the analysis modules live in code/.
    code_dir = HERE if os.path.basename(HERE) == "code" else ROOT
    scripts = {name: os.path.join(code_dir, name)
               for name in os.listdir(code_dir) if name.endswith(".py")}
    scripts.update({name: os.path.join(HERE, name) for name in LOCAL_SCRIPTS})
    entries.extend((f"code/{name}", path) for name, path in sorted(scripts.items()))
    # These are required inputs, including the pytest configuration. A missing
    # file must fail validation rather than silently produce a partial package.
    entries.extend((name, os.path.join(ROOT, name)) for name in DOCS)

    tests_dir = os.path.join(ROOT, "tests")
    for name in sorted(f for f in os.listdir(tests_dir) if f.endswith(".py")):
        entries.append((f"tests/{name}", os.path.join(tests_dir, name)))

    for name in DATA_FILES:
        entries.append((f"data/{name}", os.path.join(ROOT, "data", name)))
    store = os.path.join(ROOT, "data", ASSET_STORE_DIR)
    for name in sorted(f for f in os.listdir(store) if f.endswith(".csv")):
        entries.append((f"data/{ASSET_STORE_DIR}/{name}", os.path.join(store, name)))

    figures = os.path.join(ROOT, "figures")
    for name in sorted(f for f in os.listdir(figures) if f.endswith(".png")):
        entries.append((f"figures/{name}", os.path.join(figures, name)))

    missing = [arc for arc, src in entries if not os.path.exists(src)]
    if missing:
        raise FileNotFoundError("the submission is incomplete: " + ", ".join(missing))

    archive_names = {arc for arc, _ in entries}
    manifest = os.path.join(ROOT, "data", "module6_metrics_manifest.json")
    with open(manifest, encoding="utf-8") as handle:
        data = json.load(handle)

    # The report cites figures by number and files by manifest route. Both are
    # checked against what is actually in the archive, because a citation the
    # reviewer cannot open is a finding against the submission, not against the paper.
    drawn = {int(m.group(1)) for m in
             (re.match(r"fig(\d+)_", os.path.basename(p)) for _, p in entries
              if _.startswith("figures/")) if m}
    cited = set()
    for pointer in route(data, "report_table_pointers"):
        if not pointer.lower().startswith("figure"):
            continue
        for token in re.findall(r"\d+(?:\s*-\s*\d+)?", pointer):
            low, _, high = token.partition("-")
            cited.update(range(int(low), int(high or low) + 1))
    if cited - drawn:
        raise FileNotFoundError(f"figures cited but not drawn: {sorted(cited - drawn)}")

    for path in ([route(data, r).replace("\\", "/") for r in CITED_PATH_ROUTES]
                 + [WEIGHT_HISTORY]):
        if path not in archive_names:
            raise FileNotFoundError(f"{path} is cited by the report but not packaged")
    return entries


def build(entries):
    """Stage in TEMP and publish only the complete ZIP, not working-tree folders."""
    zip_path = os.path.join(HERE, ZIP_NAME)
    with tempfile.TemporaryDirectory(prefix="m6-deliverable-") as staging:
        staged = []
        for archive_name, source in entries:
            destination = os.path.join(staging, archive_name)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy2(source, destination)
            staged.append((archive_name, destination))

        staged_zip = os.path.join(staging, ZIP_NAME)
        with zipfile.ZipFile(staged_zip, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for archive_name, staged_path in staged:
                archive.write(staged_path, archive_name)
        # No snapshot folder is deleted or synchronized. The only persistent
        # output is this named ZIP; submitted artifacts are managed separately.
        shutil.copy2(staged_zip, zip_path)
    return zip_path


def main():
    entries = collect()
    zip_path = build(entries)
    raw = sum(os.path.getsize(src) for src in {src for _, src in entries})
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        compressed = sum(i.compress_size for i in archive.infolist())
    size = os.path.getsize(zip_path)
    print(f"{len(entries)} artefacts staged, {len(names)} entries in {ZIP_NAME}")
    print(f"  uncompressed {raw / 1e6:.1f} MB -> archive {size / 1e6:.1f} MB")
    print(f"  {zip_path}")
    for folder in SNAPSHOT_DIRS:
        count = sum(name.startswith(folder + "/") for name in names)
        print(f"  {folder}/  {count} files")
    return zip_path


if __name__ == "__main__":
    main()
