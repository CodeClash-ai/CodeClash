from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import AutoMinorLocator

from codeclash.analysis.viz.utils import FONT_BOLD, MODEL_TO_DISPLAY_NAME


def main():
    # Load data
    df = pd.read_parquet(Path(__file__).parent / "aggregated_results.parquet")
    df["model_name"] = df["model_name"].str.split("/").str[1]
    df = df.query("model_name != opponent_model_name").copy()

    # Get unique models
    models = sorted(
        [m for m in df["model_name"].unique() if isinstance(m, str)], key=lambda m: MODEL_TO_DISPLAY_NAME.get(m, m)
    )

    # Calculate number of rows needed (2 columns)
    n_cols = 2
    n_rows = (len(models) + n_cols - 1) // n_cols

    # Create figure with subplots
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 3.5 * n_rows))
    axes = axes.flatten() if n_rows > 1 else [axes] if n_cols == 1 else axes

    # Category order and colors
    category_order = ["feature", "change", "fix", "tweak", "none"]
    colors = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E"]

    # Plot for each model
    for idx, model in enumerate(models):
        ax = axes[idx]

        # Filter data for this model
        model_df = df[df["model_name"] == model]

        # Get category counts by round
        pivot_data = model_df.groupby(["round_number", "edit_category"]).size().unstack(fill_value=0)

        # Calculate percentages
        pivot_pct = pivot_data.div(pivot_data.sum(axis=1), axis=0) * 100

        # Only include categories that exist in the data
        available_categories = [cat for cat in category_order if cat in pivot_pct.columns]
        pivot_pct = pivot_pct[available_categories]

        # Get corresponding colors for available categories
        category_colors = [colors[category_order.index(cat)] for cat in available_categories]

        # Create stacked area chart
        stackplot_kwargs = {"colors": category_colors, "alpha": 0.85}
        if idx == 0:
            stackplot_kwargs["labels"] = pivot_pct.columns

        ax.stackplot(pivot_pct.index, [pivot_pct[col] for col in pivot_pct.columns], **stackplot_kwargs)

        # Add markers to show data points more clearly
        # Calculate cumulative values for plotting markers at boundaries
        cumsum = pivot_pct.cumsum(axis=1)
        for i, col in enumerate(pivot_pct.columns):
            y_values = cumsum[col]
            ax.plot(
                pivot_pct.index,
                y_values,
                marker="o",
                markersize=4,
                markerfacecolor="white",
                markeredgecolor=category_colors[i],
                markeredgewidth=1.5,
                linestyle="",
                zorder=10,
            )

        # Get display name
        display_name = MODEL_TO_DISPLAY_NAME.get(model, model)

        # Styling
        ax.set_xlabel("Round Number", fontproperties=FONT_BOLD, fontsize=14)
        ax.set_ylabel("Percentage (%)", fontproperties=FONT_BOLD, fontsize=14)
        ax.set_title(display_name, fontproperties=FONT_BOLD, fontsize=16, pad=10)
        ax.set_xlim(1, 15)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)

        # Add minor ticks to y-axis
        ax.yaxis.set_minor_locator(AutoMinorLocator())

        # Make tick labels bold
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(FONT_BOLD)
            label.set_fontsize(12)

        # Remove spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    # Hide unused subplots
    for idx in range(len(models), len(axes)):
        axes[idx].set_visible(False)

    # Create legend at the top with 5 columns
    handles, labels = axes[0].get_legend_handles_labels()
    # Reverse to match the stacking order (bottom to top)
    handles = handles[::-1]
    labels = [label.capitalize() for label in labels[::-1]]

    legend_font = FONT_BOLD.copy()
    legend_font.set_size(15)

    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=5, frameon=False, prop=legend_font)

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)

    # Save
    output_path = Path(__file__).parent / "edit_type_stacked.pdf"
    plt.savefig(output_path, bbox_inches="tight", dpi=300)
    print(f"Saved to {output_path}")
    plt.close()


if __name__ == "__main__":
    main()
