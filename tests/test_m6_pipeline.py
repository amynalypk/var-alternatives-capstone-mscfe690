"""Tests for the manifest's null policy and the table pointers the report reads.

A NaN in the manifest becomes a JSON null, and the build refuses to ship one that
has no recorded meaning. That refusal is the only thing standing between a silently
missing number and a sentence in the report written around it, so it is tested here
rather than trusted. The second class checks that every Table pointer in the report
resolves inside the artefact that was actually written, which is what a reviewer
follows when they ask where a number came from.
"""

import json
import os
import re

import numpy as np
import pandas as pd
import pytest

from m6_develop_pipeline import (
    NULL_MEANINGS, _explain_nulls, _field_of, _find_non_finite, _scalar,
    section_pointers,
)

MANIFEST = os.path.join("data", "module6_metrics_manifest.json")
needs_manifest = pytest.mark.skipif(not os.path.exists(MANIFEST),
                                   reason="manifest not built")

# A pointer is checkable only if it is nothing but a dotted route into this manifest.
# Anything else - a sentence, another artefact, a path with <innovation> in it - is
# description, and the test counts it as skipped rather than pretending to resolve it.
PLAIN_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*")


class TestNonFiniteSearch:
    def test_a_nan_an_inf_and_a_none_are_all_collected(self):
        tree = {"a": float("nan"), "b": float("inf"), "c": None, "d": 1.0}
        assert sorted(_find_non_finite(tree)) == ["$.a", "$.b", "$.c"]

    def test_the_walk_reaches_inside_lists_of_records(self):
        tree = {"rows": [{"x": 1.0}, {"x": None}]}
        assert _find_non_finite(tree) == ["$.rows[1].x"]

    def test_a_clean_tree_returns_nothing(self):
        assert _find_non_finite({"a": 1.0, "b": [2, 3], "c": "text"}) == []

    def test_the_field_is_the_last_key_with_indices_stripped(self):
        assert _field_of("$.threshold.profile[7].var_z_raw") == "var_z_raw"
        assert _field_of("$.nu") == "nu"
        assert _field_of("$") == "$"


class TestScalarConversion:
    def test_a_nan_survives_unless_the_caller_asks_for_null(self):
        assert np.isnan(_scalar(float("nan")))
        assert _scalar(float("nan"), nan_to_none=True) is None

    def test_numpy_scalars_become_python_ones(self):
        assert _scalar(np.float64(1.5)) == 1.5
        assert isinstance(_scalar(np.int64(3)), int)

    def test_timestamps_become_iso_strings(self):
        assert _scalar(pd.Timestamp("2008-10-10")) == "2008-10-10T00:00:00"

    def test_a_frame_is_converted_without_dropping_a_nan(self):
        frame = pd.DataFrame({"x": [1.0, np.nan]})
        assert _scalar(frame, nan_to_none=True) == [{"index": 0, "x": 1.0},
                                                    {"index": 1, "x": None}]


class TestNullGuard:
    def test_an_unexplained_null_refuses_the_manifest(self):
        manifest = {"non_finite_paths": ["$.section_a.the_shape_estimate"]}
        with pytest.raises(KeyError, match="the_shape_estimate"):
            _explain_nulls(manifest)

    def test_a_known_field_is_recorded_with_its_meaning(self):
        manifest = {"non_finite_paths": ["$.iid.filter.nu", "$.iid.filter[2].nu"]}
        fields = _explain_nulls(manifest)
        assert fields == ["nu"]
        assert manifest["null_meanings"] == {"nu": NULL_MEANINGS["nu"]}

    def test_a_manifest_with_no_nulls_needs_no_meanings(self):
        manifest = {"non_finite_paths": []}
        assert _explain_nulls(manifest) == []
        assert manifest["null_meanings"] == {}

    def test_the_guard_reports_every_offender_at_once(self):
        manifest = {"non_finite_paths": ["$.a.mystery_one", "$.b.mystery_two"]}
        with pytest.raises(KeyError, match="mystery_one, mystery_two"):
            _explain_nulls(manifest)

    @needs_manifest
    def test_the_shipped_manifest_satisfies_the_current_guard(self):
        """Catches a field added to the sections without its meaning being written.

        The second assertion is the stronger one: the list recorded at build time
        must match what the finished tree actually contains, so a null cannot be
        dropped from the accounting by the conversion that turned it into a JSON null.
        """
        with open(MANIFEST) as handle:
            manifest = json.load(handle)
        unexplained = sorted({f for f in map(_field_of, manifest["non_finite_paths"])
                              if f not in NULL_MEANINGS})
        assert unexplained == [], f"nulls with no meaning: {unexplained[:8]}"
        tree = {k: v for k, v in manifest.items()
                if not k.startswith("non_finite") and k != "null_meanings"}
        assert sorted(_find_non_finite(tree)) == sorted(manifest["non_finite_paths"])


class TestTablePointers:
    POINTER_FILE = MANIFEST

    @needs_manifest
    def test_every_plain_pointer_resolves_in_the_manifest(self):
        with open(self.POINTER_FILE) as handle:
            manifest = json.load(handle)
        pointers = section_pointers({})
        skipped, checked = [], 0
        for label, path in pointers.items():
            if not PLAIN_PATH.fullmatch(path):
                skipped.append(label)
                continue
            node = manifest
            for key in path.split("."):
                assert key in node, f"{label} points at a missing key: {path}"
                node = node[key]
            assert node not in ({}, [], None), f"{label} resolves to an empty {path}"
            checked += 1
        assert checked >= 12, "too few pointers were actually checked to mean anything"
        assert len(skipped) >= 4

    def test_no_table_number_is_pointed_at_twice(self):
        pointers = section_pointers({})
        assert len(pointers) == len(set(pointers))


class TestReportAuditPatterns:
    """The build-time refusal that keeps Python artefacts off the page.

    These test the patterns rather than a document because the patterns are the
    rule; a document is just a place they are applied. The narrow one is the
    placeholder check, which has to distinguish `{mean_excess}`, a bug, from
    `r_{t-W+1}`, a subscript in an equation written in the Module 4 style.
    """

    @staticmethod
    def _patterns():
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "Module 6 Develop"))
        from m6_numbers import ARTEFACT_PATTERNS
        return ARTEFACT_PATTERNS

    def _hits(self, text):
        return [why for pattern, why in self._patterns() if pattern.search(text)]

    def test_a_real_placeholder_is_caught(self):
        assert self._hits("the mean was {mean_excess} percent")

    def test_a_formatted_placeholder_is_caught(self):
        assert self._hits("reserve {value:.2f} at every mark")

    def test_a_mathematical_subscript_is_not_a_placeholder(self):
        assert not self._hits("VaR = -Quantile( { r_{t-W+1}, r_t }, 1 - alpha )")

    def test_subscripts_and_superscripts_in_the_module_4_math_style_pass(self):
        for text in ["VaR_{alpha}^{Norm} = -mu + sigma * Phi^{-1}(alpha)",
                     "sigma_t^2 = omega + alpha * epsilon_{t-1}^2 + beta * sigma_{t-1}^2",
                     "VaR_{alpha, t}^{HS} = - Quantile( { r_{t-W+1} }, 1 - alpha )",
                     "G_{xi, beta}(y) = 1 - ( 1 + (xi * y) / beta )^{-1 / xi}"]:
            assert not self._hits(text), f"{text!r} is mathematics, not a bug"

    def test_a_bare_braced_name_in_prose_is_still_caught(self):
        # The subscript exemption keys off the character before the brace, so a
        # placeholder that follows a space is caught even when it looks like a token.
        assert self._hits("applied to the sequence {z_t} for every t")

    def test_a_dict_literal_spanning_spaces_is_not_flagged_as_one_token(self):
        # Braces with a space after the open brace are prose, not a format field.
        assert not self._hits("the set { l in R : P(R <= l) >= 1 - alpha }")

    def test_python_booleans_and_missing_values_are_caught(self):
        assert self._hits("Nominal Inside 95% CI: True")
        assert self._hits("the value is None here")
        assert self._hits("rate came back as nan")
        assert self._hits("object at 0x7f8e90")

    def test_ordinary_prose_survives(self):
        for text in [
            "The Finance Committee met in January.",
            "None of the alternatives matched the observed tail.",  # caught on purpose
            "Each exception clears VaR by 0.80% on average.",
        ]:
            hits = self._hits(text)
            if "None of" in text:
                assert hits, "the checker must stay strict about the word None"
            else:
                assert not hits, f"{text!r} was refused: {hits}"
