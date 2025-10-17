import argparse
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from codeclash.analysis.viz.utils import MODEL_TO_DISPLAY_NAME


class GroundingValidationPlotter:
    """Create a triple plot showing grounding, validation, and testing/analysis metrics."""

    # Styling parameters
    title_fontsize = 16
    title_pad = 10
    legend_fontsize = 14
    label_fontsize = 14
    ytick_label_fontsize = 14
    xtick_label_fontsize = 12
    in_bar_number_fontsize = 12
    in_bar_number_fontweight = "bold"
    total_number_fontsize = 12
    total_number_fontweight = "bold"

    # Spacing parameters
    bar_height = 0.8  # Height of each bar (higher = less space between bars)
    figure_height_per_model = 0.8  # Figure height scaling factor per model

    # Color parameters - each as list of (color, alpha) tuples
    # Plot 1: Grounding (logs, insights)
    grounding_colors = [
        ("steelblue", 1.0),  # Analysis of previous round
        ("steelblue", 0.5),  # Other analysis/tests
    ]

    # Plot 2: Hallucination (logs/analysis, docs/tests/other, no source)
    hallucination_colors = [
        ("#8B0000", 0.8),  # Dark red
        ("#DC143C", 0.8),  # Crimson
        ("#FF6B6B", 0.8),  # Light red
    ]

    # Plot 3: Validation (both, unit only, sim only)
    validation_colors = [
        ("forestgreen", 1.0),  # Sim. + unittests
        ("forestgreen", 0.6),  # Unittests only
        ("forestgreen", 0.3),  # Simulations only
    ]

    def __init__(self, df: pd.DataFrame):
        self.df = df

        # Aggregate hallucination columns by claim
        h_cols = [col for col in self.df.columns if col.startswith("h_")]
        claim_cols = defaultdict(list)

        for col in h_cols:
            parts = col.split("__")
            if len(parts) >= 2:
                claim = "__".join(parts[:-1])  # Everything before the last '__'
                claim_cols[claim].append(col)

        for claim, cols in claim_cols.items():
            self.df[claim] = self.df[cols].sum(axis=1)

        # Add hallucination category column
        self.df["hal_cat1"] = self.df.apply(self._get_l_reason_breakdown, axis=1)

        # Sort models alphabetically by display name
        models = [m for m in df["model_name"].unique() if isinstance(m, str)]
        model_display_pairs = [(m, MODEL_TO_DISPLAY_NAME.get(m, m)) for m in models]
        model_display_pairs.sort(key=lambda x: x[1].lower())
        self.models = [m for m, _ in model_display_pairs]
        self.display_names = [d for _, d in model_display_pairs]
        self.n_models = len(self.models)

        # Create figure with 3 subplots sharing y-axis
        fig_height = self.n_models * self.figure_height_per_model
        self.fig, self.axes = plt.subplots(1, 3, figsize=(13, fig_height), sharey=True)
        self.y_positions = np.arange(self.n_models)

    def _get_l_reason_breakdown(self, row) -> str:
        """Categorize loss reason hallucinations."""
        c0 = ["h_loss_reason__log", "h_loss_reason__execution_output.analysis"]
        if any([row[c] > 0 for c in c0]):
            return "logs/analysis"
        elif row["h_loss_reason__none"] > 0:
            if row["h_loss_reason"] > row["h_loss_reason__none"]:
                # There's other cols that are also > 0
                return "docs/tests/other"
            return "no source"
        return ""

    def _add_stacked_bar_labels(self, ax, stacked_values: list[list[float]], min_value_to_show: float = 5.0):
        """Add percentage labels inside stacked bars.

        Args:
            ax: The matplotlib axis
            stacked_values: List of lists, where each inner list contains values for one stack segment
            min_value_to_show: Minimum value to display a label for
        """
        left = np.zeros(self.n_models)

        for segment_idx, values in enumerate(stacked_values):
            for i, val in enumerate(values):
                if val >= min_value_to_show:
                    x_pos = left[i] + val / 2
                    # Determine text color based on segment index or value
                    text_color = "white" if segment_idx < len(stacked_values) - 1 else "black"
                    ax.text(
                        x_pos,
                        self.y_positions[i],
                        f"{val:.0f}%",
                        fontsize=self.in_bar_number_fontsize,
                        fontweight=self.in_bar_number_fontweight,
                        ha="center",
                        va="center",
                        color=text_color,
                    )
            left = left + np.array(values)

    def _add_total_bar_labels(self, ax, totals: list[float], x_offset: float = 1):
        """Add total value labels at the end of bars.

        Args:
            ax: The matplotlib axis
            totals: List of total values for each bar
            x_offset: Horizontal offset from the end of the bar
        """
        for i, total in enumerate(totals):
            if total > 0:
                ax.text(
                    total + x_offset,
                    self.y_positions[i],
                    f"{total:.0f}%",
                    fontsize=self.total_number_fontsize,
                    fontweight=self.total_number_fontweight,
                    ha="left",
                    va="center",
                )

    def plot_grounding_analysis(self):
        """Plot: Are edits grounded in analysis?"""
        ax = self.axes[0]

        # Create temporary columns
        df_temp = self.df.copy()
        df_temp["edits_motivated_by_insight_not_logs"] = df_temp["edits_motivated_by_insights"] & (
            ~df_temp["edits_motivated_by_logs"]
        )

        # Calculate percentages
        motivated_by_logs = []
        motivated_by_insights_not_logs = []

        for model in self.models:
            model_df = df_temp[df_temp["model_name"] == model]
            total = len(model_df)

            logs_pct = (model_df["edits_motivated_by_logs"].sum() / total * 100) if total > 0 else 0
            insights_not_logs_pct = (
                model_df["edits_motivated_by_insight_not_logs"].sum() / total * 100 if total > 0 else 0
            )

            motivated_by_logs.append(logs_pct)
            motivated_by_insights_not_logs.append(insights_not_logs_pct)

        # Plot stacked bars
        color_logs, alpha_logs = self.grounding_colors[0]
        color_insights, alpha_insights = self.grounding_colors[1]

        ax.barh(
            self.y_positions,
            motivated_by_logs,
            self.bar_height,
            label="Analysis of prev. round",
            alpha=alpha_logs,
            color=color_logs,
        )
        ax.barh(
            self.y_positions,
            motivated_by_insights_not_logs,
            self.bar_height,
            left=motivated_by_logs,
            label="Other analysis/tests",
            alpha=alpha_insights,
            color=color_insights,
        )

        # Add labels
        self._add_stacked_bar_labels(ax, [motivated_by_logs, motivated_by_insights_not_logs], min_value_to_show=12.0)
        totals = [logs + insights for logs, insights in zip(motivated_by_logs, motivated_by_insights_not_logs)]
        self._add_total_bar_labels(ax, totals)

        ax.set_title(
            "(a) Groundedness of edits",
            fontsize=self.title_fontsize,
            fontweight="bold",
            pad=self.title_pad,
        )
        ax.legend(loc="upper right", bbox_to_anchor=(1.2, 1), fontsize=self.legend_fontsize, frameon=False)
        ax.set_yticks(self.y_positions)
        ax.set_yticklabels(self.display_names, fontsize=self.ytick_label_fontsize)
        ax.set_xlabel("Percentage of rounds", fontsize=self.label_fontsize)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", labelsize=self.xtick_label_fontsize)
        ax.xaxis.set_minor_locator(plt.MultipleLocator(5))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    def plot_validation_feedback(self):
        """Plot: Are edits validated based on execution feedback?"""
        ax = self.axes[2]

        # Create temporary columns
        df_temp = self.df.copy()
        df_temp["edits_tested_sim_and_unit"] = (
            df_temp["edits_tested_with_simulations"] & df_temp["edits_validated_with_unittests"]
        )
        df_temp["edits_tested_sim_only"] = df_temp["edits_tested_with_simulations"] & (
            ~df_temp["edits_validated_with_unittests"]
        )
        df_temp["edits_tested_unit_only"] = df_temp["edits_validated_with_unittests"] & (
            ~df_temp["edits_tested_with_simulations"]
        )

        # Calculate percentages
        tested_both = []
        tested_sim_only = []
        tested_unit_only = []

        for model in self.models:
            model_df = df_temp[df_temp["model_name"] == model]
            total = len(model_df)

            both_pct = (model_df["edits_tested_sim_and_unit"].sum() / total * 100) if total > 0 else 0
            sim_pct = (model_df["edits_tested_sim_only"].sum() / total * 100) if total > 0 else 0
            unit_pct = (model_df["edits_tested_unit_only"].sum() / total * 100) if total > 0 else 0

            tested_both.append(both_pct)
            tested_sim_only.append(sim_pct)
            tested_unit_only.append(unit_pct)

        # Plot stacked bars
        color_both, alpha_both = self.validation_colors[0]
        color_unit, alpha_unit = self.validation_colors[1]
        color_sim, alpha_sim = self.validation_colors[2]

        ax.barh(
            self.y_positions,
            tested_both,
            self.bar_height,
            label="Sim. + unittests",
            alpha=alpha_both,
            color=color_both,
        )
        ax.barh(
            self.y_positions,
            tested_unit_only,
            self.bar_height,
            left=tested_both,
            label="Unittests only",
            alpha=alpha_unit,
            color=color_unit,
        )
        ax.barh(
            self.y_positions,
            tested_sim_only,
            self.bar_height,
            left=np.array(tested_both) + np.array(tested_unit_only),
            label="Simulations only",
            alpha=alpha_sim,
            color=color_sim,
        )

        # Add labels
        self._add_stacked_bar_labels(ax, [tested_both, tested_unit_only, tested_sim_only])
        totals = [both + sim + unit for both, sim, unit in zip(tested_both, tested_sim_only, tested_unit_only)]
        self._add_total_bar_labels(ax, totals)

        ax.set_title(
            "(c) Validation of edits",
            fontsize=self.title_fontsize,
            fontweight="bold",
            pad=self.title_pad,
        )
        ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1), fontsize=self.legend_fontsize, frameon=False)
        ax.set_xlabel("Percentage of rounds", fontsize=self.label_fontsize)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", labelsize=self.xtick_label_fontsize)
        ax.xaxis.set_minor_locator(plt.MultipleLocator(5))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    def plot_hallucination_categories(self):
        """Plot: Hallucinated/Unproven Loss Causality Claims."""
        ax = self.axes[1]

        category_order = ["logs/analysis", "docs/tests/other", "no source"]

        # Collect data for each model
        model_data = []
        for model in self.models:
            model_df = self.df[self.df["model_name"] == model]
            total_rounds = len(model_df)
            category_values = []

            for category in category_order:
                count = (model_df["hal_cat1"] == category).sum()
                pct = (count / total_rounds * 100) if total_rounds > 0 else 0
                category_values.append(pct)

            model_data.append(category_values)

        # Plot stacked bars
        left = np.zeros(self.n_models)

        for cat_idx, category in enumerate(category_order):
            values = [model_data[model_idx][cat_idx] for model_idx in range(self.n_models)]
            color, alpha = self.hallucination_colors[cat_idx]

            ax.barh(
                self.y_positions,
                values,
                self.bar_height,
                left=left,
                label=category,
                alpha=alpha,
                color=color,
            )
            left = left + np.array(values)

        # Add labels
        stacked_values = [
            [model_data[model_idx][cat_idx] for model_idx in range(self.n_models)]
            for cat_idx in range(len(category_order))
        ]
        self._add_stacked_bar_labels(ax, stacked_values, min_value_to_show=3.0)
        totals = [sum(model_data[i]) for i in range(self.n_models)]
        self._add_total_bar_labels(ax, totals)

        ax.set_title(
            "(b) Hallucinated Loss Causality",
            fontsize=self.title_fontsize,
            fontweight="bold",
            pad=self.title_pad,
        )
        ax.legend(
            loc="center right",
            bbox_to_anchor=(1.15, 0.55),
            fontsize=self.legend_fontsize,
            frameon=False,
            title="Hallucinated claims based on",
            title_fontsize=12,
        )
        ax.set_xlabel("Percentage of rounds", fontsize=self.label_fontsize)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", labelsize=self.xtick_label_fontsize)
        ax.xaxis.set_minor_locator(plt.MultipleLocator(5))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    def create_plot(self):
        """Create all three plots."""
        self.plot_grounding_analysis()
        self.plot_hallucination_categories()
        self.plot_validation_feedback()
        self.fig.tight_layout()

    def save(self, output_path: Path):
        """Save figure to PDF."""
        self.fig.savefig(output_path, bbox_inches="tight", dpi=300)
        print(f"Saved plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Create grounding and validation triple plot")
    parser.add_argument("datafile", type=str, help="Path to the parquet data file")
    parser.add_argument(
        "-o", "--output", type=str, default="grounding_validation_plot.pdf", help="Output PDF file path"
    )
    args = parser.parse_args()

    # Load data
    df = pd.read_parquet(args.datafile)

    # Process model name and filter
    df["model_name"] = df["model_name"].str.split("/").str[1]
    df = df.query("model_name != opponent_model_name").copy()

    # Create and save plot
    plotter = GroundingValidationPlotter(df)
    plotter.create_plot()
    plotter.save(Path(args.output))


if __name__ == "__main__":
    main()
