from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import AutoMinorLocator

from codeclash.analysis.viz.utils import FONT_BOLD, MODEL_TO_DISPLAY_NAME

# Load data
df = pd.read_parquet(Path(__file__).parent / "aggregated_results.parquet")

# Map model names early to merge models that map to the same display name
df["model_name"] = df["model_name"].map(lambda x: MODEL_TO_DISPLAY_NAME.get(x, x) if isinstance(x, str) else x)

# Define action category mappings
action_category_mapping = {
    "Navigate/search": ["search", "navigate"],
    "Read source": ["read.source.new", "read.source.old"],
    "Read docs/logs": ["read.docs.new", "read.docs.old", "read.logs.new", "read.logs.old"],
    "Modify main": ["write.source.main.create", "write.source.main.modify_old", "write.source.main.modify_new"],
    "Write docs": ["write.docs.create", "write.docs.modify_new", "write.docs.modify_old"],
    "Write analysis/tests": [
        "write.source.analysis.create",
        "write.source.tests.create",
        "write.source.analysis.modify_new",
        "write.source.tests.modify_new",
        "write.source.analysis.modify_old",
        "write.source.tests.modify_old",
    ],
    "Execute unittests": ["execute.unittest.in_mem", "execute.unittest.new", "execute.unittest.old"],
    "Execute analysis": ["execute.analysis.new", "execute.analysis.old", "execute.analysis.in_mem"],
    "Execute game": [
        "execute.game.setup.new",
        "execute.game.setup.old",
        "execute.game.new",
        "execute.game.old",
        "execute.game.setup.in_mem",
        "execute.game.in_mem",
    ],
}

action_category_mapping2 = {
    "Read": action_category_mapping["Navigate/search"]
    + action_category_mapping["Read source"]
    + action_category_mapping["Read docs/logs"],
    "Modify main": action_category_mapping["Modify main"],
    "Unittests": action_category_mapping["Execute unittests"]
    + [
        "write.source.tests.create",
        "write.source.tests.modify_new",
        "write.source.tests.modify_old",
    ],
    "Analysis": action_category_mapping["Execute analysis"]
    + [
        "write.source.analysis.create",
        "write.source.analysis.modify_new",
        "write.source.analysis.modify_old",
    ],
    "Simulations": action_category_mapping["Execute game"]
    + [
        "execute.game.setup.new",
        "execute.game.setup.old",
        "execute.game.new",
        "execute.game.old",
        "execute.game.setup.in_mem",
        "execute.game.in_mem",
    ],
}

prefix = "c_"
models = sorted([m for m in df["model_name"].unique() if isinstance(m, str)], reverse=True)

# Get all mapped actions for MISC calculation
all_mapped_actions = set()
for actions in action_category_mapping2.values():
    all_mapped_actions.update(actions)

# Collect data for each model
category_order = list(action_category_mapping2.keys()) + ["MISC"]
early_data = []
late_data = []

for model in models:
    # Early rounds (≤7)
    early_model_df = df[(df["model_name"] == model) & (df["round_number"] <= 7)]
    early_category_values = []

    for category in category_order[:-1]:
        total = 0
        for action in action_category_mapping2[category]:
            col = f"{prefix}{action}"
            if col in df.columns:
                total += early_model_df[col].mean()
        early_category_values.append(total)

    # Get MISC value
    misc_total = 0
    for col in df.columns:
        if col.startswith(prefix):
            action = col.removeprefix(prefix)
            if action not in all_mapped_actions:
                misc_total += early_model_df[col].mean()
    early_category_values.append(misc_total)
    early_data.append(early_category_values)

    # Late rounds (≥8)
    late_model_df = df[(df["model_name"] == model) & (df["round_number"] >= 8)]
    late_category_values = []

    for category in category_order[:-1]:
        total = 0
        for action in action_category_mapping2[category]:
            col = f"{prefix}{action}"
            if col in df.columns:
                total += late_model_df[col].mean()
        late_category_values.append(total)

    # Get MISC value
    misc_total = 0
    for col in df.columns:
        if col.startswith(prefix):
            action = col.removeprefix(prefix)
            if action not in all_mapped_actions:
                misc_total += late_model_df[col].mean()
    late_category_values.append(misc_total)
    late_data.append(late_category_values)

# Create horizontal stacked bar chart
fig, ax = plt.subplots(figsize=(12, 8))

# Create y positions: two bars per model (touching), with gaps between models
gap = 0.3
y_positions = []
model_positions = []
for i, model in enumerate(models):
    base = i * (2 + gap)
    y_positions.extend([base, base + 1])
    model_positions.append(base + 0.5)

# Define colors for each category
colors = plt.cm.tab10(range(len(category_order)))

# Plot late rounds (bottom bar) and early rounds (top bar) for each model
all_data = []
for early, late in zip(early_data, late_data):
    all_data.extend([late, early])

# Starting position for each stack
left = [0] * len(y_positions)

for cat_idx, category in enumerate(category_order):
    values = [all_data[pos_idx][cat_idx] for pos_idx in range(len(y_positions))]
    ax.barh(y_positions, values, left=left, label=category, alpha=0.8, color=colors[cat_idx], height=1.0)

    # Add value labels for significant values
    for i, (y_pos, val) in enumerate(zip(y_positions, values)):
        x_pos = left[i] + val / 2
        if val >= 1.0:
            ax.text(
                x_pos,
                y_pos,
                f"{val:.1f}",
                fontsize=11,
                ha="center",
                va="center",
                color="white",
                fontweight="bold",
                fontproperties=FONT_BOLD,
            )
        elif val >= 0.5:
            ax.text(
                x_pos,
                y_pos,
                f"{val:.1f}",
                fontsize=10,
                ha="center",
                va="center",
                color="white",
                fontweight="bold",
                fontproperties=FONT_BOLD,
            )

    left = [left[i] + values[i] for i in range(len(y_positions))]

# Add total bar length numbers at the end of each bar
for y_pos, total in zip(y_positions, left):
    ax.text(
        total + 0.5,
        y_pos,
        f"{total:.1f}",
        fontsize=12,
        ha="left",
        va="center",
        color="black",
        fontweight="bold",
        fontproperties=FONT_BOLD,
    )

# Add round labels on the left side of the plot
for i, (y_late, y_early) in enumerate(zip(y_positions[::2], y_positions[1::2])):
    ax.text(-0.2, y_late, "round ≥8", fontsize=11, ha="right", va="center", color="gray", fontproperties=FONT_BOLD)
    ax.text(-0.2, y_early, "round ≤7", fontsize=11, ha="right", va="center", color="gray", fontproperties=FONT_BOLD)

legend_font = FONT_BOLD.copy()
legend_font.set_size(15)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.05), frameon=False, prop=legend_font, ncol=6)
ax.set_yticks(model_positions)
ax.set_yticklabels(models, fontsize=14, fontproperties=FONT_BOLD)
ax.set_xlabel("Mean Action Count", fontsize=15, fontproperties=FONT_BOLD)

# Add minor ticks to x-axis
ax.xaxis.set_minor_locator(AutoMinorLocator())
ax.tick_params(axis="x", which="minor", length=3)
ax.tick_params(axis="x", which="major", length=6)

# Remove top and right spines
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(True)

# Set tick label fonts
for label in ax.get_xticklabels():
    label.set_fontproperties(FONT_BOLD)
    label.set_fontsize(14)
for label in ax.get_yticklabels():
    label.set_fontproperties(FONT_BOLD)

plt.tight_layout()

# Save to PDF
output_path = Path(__file__).parent / "action_categories_by_model.pdf"
plt.savefig(output_path, format="pdf", bbox_inches="tight")
print(f"Plot saved to {output_path}")
