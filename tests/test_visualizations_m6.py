"""Tests for the figure module's build-time refusals.

The rubric grades axes, labels and scales, and a caption that matplotlib clips away
is invisible to the grader but invisible to the author too -- the file saves, looks
finished, and is missing the claim it was added to make. Two of those happened while
writing fig6-fig14, so the checks are now code that runs on every save. These tests
pin the checks themselves, because a guard nobody has seen fire is a comment.

Everything here draws into a temporary directory, so a test run cannot overwrite a
figure the report references.
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest
from matplotlib.transforms import Bbox

import visualizations_m6 as viz


@pytest.fixture()
def out_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(viz, "FIGURES_DIR", str(tmp_path))
    return tmp_path


def _close_all():
    import matplotlib.pyplot as plt
    plt.close("all")


class TestLabelGuard:
    """A titled panel without both axis labels does not leave the module."""

    def test_a_titled_panel_missing_an_x_label_is_refused(self, out_dir):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.set_title("(A) Some panel")
        ax.set_ylabel("y")
        with pytest.raises(ValueError, match="no x label"):
            viz._finish(fig, "refused.png", "suptitle")
        _close_all()

    def test_a_titled_panel_missing_a_y_label_is_refused(self, out_dir):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.set_title("(A) Some panel")
        ax.set_xlabel("x")
        with pytest.raises(ValueError, match="no y label"):
            viz._finish(fig, "refused.png", "suptitle")
        _close_all()

    def test_a_refused_figure_writes_no_file(self, out_dir):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.set_title("(A) Some panel")
        with pytest.raises(ValueError):
            viz._finish(fig, "refused.png", "suptitle")
        assert list(out_dir.glob("*.png")) == []
        _close_all()

    def test_a_fully_labelled_panel_saves(self, out_dir):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.set_title("(A) Some panel")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        path = viz._finish(fig, "accepted.png", "suptitle")
        assert path.endswith("accepted.png")
        assert (out_dir / "accepted.png").stat().st_size > 10_000


class TestClippedCaptionGuard:
    """A caption that falls outside its axes is a build error, not a review comment."""

    def test_a_caption_beyond_the_axis_limits_is_refused(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.set_xlim(0, 1.3)
        ax.annotate("nu = 8: Gaussian tails already adequate", (1.45, 0.5))
        with pytest.raises(ValueError, match="clipped away"):
            viz._assert_annotations_visible(fig, "fig9.png")
        _close_all()

    def test_a_caption_inside_the_limits_passes(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.annotate("inside", (0.5, 0.5))
        viz._assert_annotations_visible(fig, "fig9.png")
        _close_all()

    def test_a_deliberately_external_caption_opts_out(self):
        """Every staggered tick label asks for this, so opting out must be honoured."""
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.set_xlim(0, 1.0)
        ax.annotate("below the axis", (0.5, -0.4), annotation_clip=False)
        viz._assert_annotations_visible(fig, "fig7.png")
        _close_all()

    def test_finish_runs_the_caption_check(self, out_dir):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.set_xlim(0, 1.0)
        ax.set_title("(A) Panel")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.annotate("off to the right", (1.6, 0.5))
        with pytest.raises(ValueError, match="off to the right"):
            viz._finish(fig, "refused.png", "suptitle")
        _close_all()


class TestStaggeredTicks:
    """0.975 and 0.98 sit 2.8% of the axis apart and print on top of each other."""

    PRODUCTION_GRID = [0.80, 0.85, 0.90, 0.95, 0.975, 0.98]

    def _staggered_axis(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6.4, 3.2))
        ax.plot(self.PRODUCTION_GRID, [1, 2, 3, 4, 5, 6])
        ax.set_xlim(0.78, 1.0)
        ax.set_xlabel("POT threshold as a quantile")
        viz._stagger_xlabels(ax, self.PRODUCTION_GRID)
        fig.canvas.draw()
        return fig, ax

    def test_the_default_labels_are_cleared_so_nothing_prints_twice(self):
        fig, ax = self._staggered_axis()
        assert [t.get_text() for t in ax.get_xticklabels()] == [""] * len(ax.get_xticks())
        _close_all()

    def test_every_label_of_the_grid_is_placed(self):
        fig, ax = self._staggered_axis()
        texts = sorted(t.get_text() for t in ax.texts)
        assert texts == sorted(f"{q:g}" for q in self.PRODUCTION_GRID)
        _close_all()

    def test_no_two_labels_overlap(self):
        fig, ax = self._staggered_axis()
        boxes = [t.get_window_extent() for t in ax.texts]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                shared = Bbox.intersection(a, b)
                assert shared is None or shared.width <= 0 or shared.height <= 0, \
                    f"{ax.texts[i].get_text()} and {ax.texts[i + 1].get_text()} collide"
        _close_all()

    def test_the_close_pair_is_the_one_that_needed_a_second_row(self):
        fig, ax = self._staggered_axis()
        base = min(t.get_window_extent().y0 for t in ax.texts)
        rows = {t.get_text(): round(float(t.get_window_extent().y0 - base))
                for t in ax.texts}
        assert rows["0.975"] != rows["0.98"], "the adjacent pair should be split"
        assert len(set(rows.values())) == 2, "one bump, no cascade down four rows"
        _close_all()


class TestBreachMagnitudeFigure:
    """fig11's reserve panel must reproduce the manifest or say why it cannot."""

    NOTIONAL = 100_000_000.0

    @pytest.fixture()
    def pieces(self):
        index = pd.bdate_range("2010-01-04", periods=8)
        rng = np.random.default_rng(3)
        var = rng.uniform(0.018, 0.026, len(index))
        es = var * 1.4
        loss = var + rng.uniform(0.0, 0.02, len(index))
        register = pd.DataFrame({
            "Return": -loss, "Loss": loss, "VaR": var,
            "Exceedance": loss - var, "ES_forecast": es}, index=index)
        adequacy = {
            "Cumulative Unreserved under VaR (USD)":
                float(np.maximum(register["Loss"] - register["VaR"], 0.0).sum())
                * self.NOTIONAL,
            "Cumulative Unreserved under ES (USD)":
                float(np.maximum(register["Loss"] - register["ES_forecast"], 0.0).sum())
                * self.NOTIONAL,
            "Mean VaR Reserve (USD)": float(var.mean()) * self.NOTIONAL,
            "Mean ES Reserve (USD)": float(es.mean()) * self.NOTIONAL,
            "Incremental Capital Held (USD)": float((es - var).mean()) * self.NOTIONAL,
            "Incremental Capital (% of notional)":
                float((es - var).mean()) * 100.0,
        }
        vix = pd.Series(np.linspace(12.0, 34.0, len(index)), index=index, name="VIX")
        return register, adequacy, vix

    def test_consecutive_values_draw_and_save(self, out_dir, pieces):
        register, adequacy, vix = pieces
        path = viz.plot_breach_magnitudes(register, adequacy, vix,
                                          notional=self.NOTIONAL)
        assert (out_dir / "fig11_breach_magnitudes_and_reserves.png").exists()
        assert path.endswith(".png")

    def test_a_zero_cumulative_is_refused_not_skipped(self, out_dir, pieces):
        """The exact artefact of the sign defect: negating the difference clips every
        shortfall to zero, and a truthy-test guard would wave a zero through."""
        register, adequacy, vix = pieces
        adequacy["Cumulative Unreserved under VaR (USD)"] = 0.0
        with pytest.raises(AssertionError, match="fig11 cumulative VaR"):
            viz.plot_breach_magnitudes(register, adequacy, vix, notional=self.NOTIONAL)

    def test_a_mismatched_es_cumulative_is_refused(self, out_dir, pieces):
        register, adequacy, vix = pieces
        adequacy["Cumulative Unreserved under ES (USD)"] += 2_000_000.0
        with pytest.raises(AssertionError, match="fig11 cumulative ES"):
            viz.plot_breach_magnitudes(register, adequacy, vix, notional=self.NOTIONAL)

    def test_a_missing_entry_is_tolerated(self, out_dir, pieces):
        """None is the manifest's encoding of 'this model has no ES forecast',
        which is a real answer and must not fail the build."""
        register, adequacy, vix = pieces
        adequacy["Cumulative Unreserved under ES (USD)"] = None
        viz.plot_breach_magnitudes(register, adequacy, vix, notional=self.NOTIONAL)

    def test_a_date_passed_where_a_fraction_was_meant_is_caught(self, out_dir, pieces):
        """Panel B's captions sit at an axes fraction on one axis and a date on the
        other; mixing the two is how one of them went invisible."""
        register, adequacy, vix = pieces
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot(register.index, register["Loss"])
        ax.annotate("reserve held daily", (0.02, float(register["Loss"].max())))
        with pytest.raises(ValueError, match="clipped away"):
            viz._assert_annotations_visible(fig, "fig11.png")
        _close_all()


@pytest.mark.slow
class TestWholeSet:
    """The nine production figures, through the same entry point the report build uses."""

    MANIFEST = "data/module6_metrics_manifest.json"

    def test_all_nine_figures_survive_the_guards(self, out_dir):
        import os
        if not os.path.exists(self.MANIFEST):
            pytest.skip("manifest not built")
        written = viz.generate_module6_figures()
        assert len(written) == 9
        assert sorted(p.name for p in out_dir.glob("*.png")) == sorted(
            os.path.basename(path) for path in written)
        for path in written:
            assert (out_dir / os.path.basename(path)).stat().st_size > 100_000
