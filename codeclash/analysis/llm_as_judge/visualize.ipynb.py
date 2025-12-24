# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
#   kernelspec:
#     display_name: swea13
#     language: python
#     name: python3
# ---

# %%

import matplotlib.pyplot as plt
import pandas as pd

# %%
df = pd.read_parquet("aggregated_results.parquet")
df["edits_not_motivated"] = (
    (~df["edits_motivated_by_insights"])
    & (~df["edits_motivated_by_logs"])
    & (~df["edits_motivated_by_old_static_messages"])
)
df["edits_not_motivated_or_validated"] = (
    (~df["edits_motivated_by_insights"])
    & (~df["edits_motivated_by_logs"])
    & (~df["edits_validated_with_unittests"])
    & (~df["edits_tested_with_simulations"])
)
df["improved_win_rate"] = df["next_round_win_rate"] - df["current_round_win_rate"]
df["improved_win_rate_bool"] = (df["next_round_win_rate"] - df["current_round_win_rate"]) >= -0.01
df["lost_to_won"] = (df["current_round_win_rate"] < 0.5) & (df["next_round_win_rate"] > 0.5)
df["won_to_lost"] = (df["current_round_win_rate"] > 0.5) & (df["next_round_win_rate"] < 0.5)
df["model_name"] = df["model_name"].str.split("/").str[1]
df["edits_motivated_by_insight_not_logs"] = (~df["edits_motivated_by_logs"]) & df["edits_motivated_by_insights"]
df["edits_tested_sim_and_unit"] = df["edits_tested_with_simulations"] & df["edits_validated_with_unittests"]
df = df.query("model_name != opponent_model_name").copy()
boolean_result_cols = [
    "edits_motivated_by_logs",
    "edits_motivated_by_insights",
    "edits_motivated_by_old_static_messages",
    "edits_not_motivated",
    # "edits_reverted_based_on_insights",
    "edits_tested_with_simulations",
    "edits_validated_with_unittests",
    "edits_not_motivated_or_validated",
]
df[boolean_result_cols].mean()

# %%
df.columns

# %%

# %%
len(df)

# %%
target_var = "improved_win_rate"
for bc in boolean_result_cols:
    print(bc)
    for model in df["model_name"].unique():
        if not isinstance(model, str):
            continue
        print("...", model, end=" ")
        val = (
            df.query("model_name == @model and edit_category == 'feature'")[[bc, target_var]]
            .corr(method="spearman")
            .to_numpy()[0, 1]
        )
        if abs(val) < 0.05:
            print("small")
        else:
            print(f"{val * 100:.0f}%")

    # print("... all", df[[bc, target_var]].corr(method="spearman").to_numpy()[0, 1])

# %%
(df.groupby("model_name")[boolean_result_cols].mean() * 100).round().astype(int)

# %%
(df.groupby("round_number")[boolean_result_cols].mean() * 100).round().astype(int)

# %%
df.groupby(["model_name", "round_number"])[boolean_result_cols].mean()["edits_tested_with_simulations"]

# %%
fig, ax = plt.subplots(figsize=(12, 6))
import collections

model2var2diff = collections.defaultdict(dict)
for model in df["model_name"].unique():
    for var in boolean_result_cols:
        win_rates_true = df.query(var).query("model_name == @model")["current_round_win_rate"].mean()
        win_rates_false = df.query(f"not {var}").query("model_name == @model")["current_round_win_rate"].mean()
        model2var2diff[model][var] = (win_rates_true, win_rates_false)

# Visualized

# %%
# Line plot of % edits categorized as features vs round number

plt.clf()
fig, ax = plt.subplots(figsize=(12, 6))

# Plot line for each model
for model in df["model_name"].unique():
    if not isinstance(model, str):
        continue
    model_data = (
        df[df["model_name"] == model]
        .groupby("round_number")
        .apply(lambda x: (x["edit_category"] == "fix").mean() * 100)
    )
    ax.plot(model_data.index, model_data.values, marker="o", label=model, linewidth=2, alpha=0.7)

ax.set_xlabel("Round Number", fontsize=12)
ax.set_ylabel("% of Edits Categorized as Features", fontsize=12)
ax.set_title("Feature Edits by Round Number", fontsize=14, fontweight="bold")
ax.legend(loc="best")
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 100)

# plt.tight_layout()
# plt.show()


# %%
# # Visualize win rate differences - one plot per variable, models on x-axis
# import matplotlib.pyplot as plt
# import numpy as np

# models = list(model2var2diff.keys())
# variables = list(model2var2diff[models[0]].keys())

# n_vars = len(variables)
# fig, axes = plt.subplots(n_vars, 1, figsize=(10, 3.5 * n_vars))
# if n_vars == 1:
#     axes = [axes]

# for var_idx, variable in enumerate(variables):
#     # For this variable, get the difference (true - false) for each model
#     model_diffs = []
#     for model in models:
#         win_rate_true, win_rate_false = model2var2diff[model][variable]
#         diff = win_rate_true - win_rate_false
#         model_diffs.append(diff)

#     # Plot bars
#     x_positions = np.arange(len(models))
#     bars = axes[var_idx].bar(x_positions, model_diffs, alpha=0.75, edgecolor='black', linewidth=0.5)

#     # Color by positive/negative
#     for i, (bar, diff) in enumerate(zip(bars, model_diffs)):
#         bar.set_color('green' if diff > 0 else 'red')

#     # Formatting
#     axes[var_idx].axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.7)
#     axes[var_idx].set_xlabel("Model", fontsize=12)
#     axes[var_idx].set_ylabel("Win Rate Diff", fontsize=12)
#     axes[var_idx].set_title(f"{variable}", fontsize=12, fontweight='bold')
#     axes[var_idx].set_xticks(x_positions)
#     axes[var_idx].set_xticklabels(models, rotation=45, ha='right', fontsize=10)
#     axes[var_idx].grid(True, alpha=0.25, axis='y')

# plt.tight_layout()
# plt.show()

# %%
# For every model, I want to create a stacked area chart based on the edit category categorical variable.
import matplotlib.pyplot as plt

# Get unique models
models = df["model_name"].unique()

# Create a figure with subplots for each model
fig, axes = plt.subplots(len(models), 1, figsize=(12, 4 * len(models)))
if len(models) == 1:
    axes = [axes]

for idx, model in enumerate(models):
    if not isinstance(model, str):
        continue
    # Filter data for this model
    model_df = df[df["model_name"] == model]

    # Get category counts by round
    pivot_data = model_df.groupby(["round_number", "edit_category"]).size().unstack(fill_value=0)

    # Calculate percentages
    pivot_pct = pivot_data.div(pivot_data.sum(axis=1), axis=0) * 100

    # Specify order from bottom to top
    category_order = ["feature", "change", "fix", "tweak", "none"]
    # Only include categories that exist in the data
    category_order = [cat for cat in category_order if cat in pivot_pct.columns]
    pivot_pct = pivot_pct[category_order]

    # Create stacked area chart
    axes[idx].stackplot(
        pivot_pct.index, [pivot_pct[col] for col in pivot_pct.columns], labels=pivot_pct.columns, alpha=0.8
    )

    axes[idx].set_xlabel("Round Number")
    axes[idx].set_ylabel("Percentage (%)")
    axes[idx].set_title(f"Edit Category Distribution - {model}")
    axes[idx].legend(loc="upper left", bbox_to_anchor=(1, 1))
    axes[idx].set_ylim(0, 100)
    axes[idx].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# %%
df.query("round_number <= 5").groupby(["model_name"])["edit_category"].value_counts(normalize=True).mul(
    100
).round().astype(int)

# %%
df.query("round_number >=10").groupby(["model_name"])["edit_category"].value_counts(normalize=True).mul(
    100
).round().astype(int)

# %%
(df[df["edit_category"] == "feature"].groupby("model_name").size() / df.groupby("model_name").size()).mul(
    100
).round().astype(int)

# %%

# Stacked bar chart with models on y-axis, split by early (≤7) and late (≥8) rounds
import matplotlib.pyplot as plt
import numpy as np

# emoji_font_path = "/Users/fuchur/Library/Fonts/NotoColorEmoji.ttf"

# Register and use it
# font_manager.fontManager.addfont(emoji_font_path)
# rcParams["font.family"] = "Noto Color Emoji"

# Get unique models
models = [m for m in df["model_name"].unique() if isinstance(m, str)]

# Calculate category percentages for each model, split by round groups
category_order = ["feature", "change", "fix", "tweak", "none"]
early_data = []
late_data = []

# category_to_emoji = {
#     "feature": "+",
#     "change": "±",
#     "fix": "⚠",
#     "tweak": "⚙",
#     "none": "∅"
# }
category_to_short = {"feature": "F", "change": "C", "fix": "F", "tweak": "T", "none": "N"}

for model in models:
    # Early rounds (≤7)
    early_df = df[(df["model_name"] == model) & (df["round_number"] <= 7)]
    early_counts = early_df["edit_category"].value_counts()
    early_total = early_counts.sum()
    early_pct = [(early_counts.get(cat, 0) / early_total * 100) if early_total > 0 else 0 for cat in category_order]
    early_data.append(early_pct)

    # Late rounds (≥8)
    late_df = df[(df["model_name"] == model) & (df["round_number"] >= 8)]
    late_counts = late_df["edit_category"].value_counts()
    late_total = late_counts.sum()
    late_pct = [(late_counts.get(cat, 0) / late_total * 100) if late_total > 0 else 0 for cat in category_order]
    late_data.append(late_pct)

# Create horizontal stacked bar chart
fig, ax = plt.subplots(figsize=(12, 8))

# Create y positions: two bars per model (touching), with gaps between models
gap = 0.3
y_positions = []
model_positions = []
for i in range(len(models)):
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
    # emoji = category_to_emoji.get(category, "")
    short = category_to_short.get(category, "")
    ax.barh(y_positions, values, left=left, label=f"{category}", alpha=0.8, color=colors[cat_idx], height=1.0)

    # Add percentage labels with emojis for values >= 10%
    for i, (y_pos, val) in enumerate(zip(y_positions, values)):
        x_pos = left[i] + val / 2
        if val >= 12:
            ax.text(
                x_pos,
                y_pos,
                f"{category.capitalize()} {val:.0f}%",
                fontsize=12,
                ha="center",
                va="center",
                color="white",
                fontweight="normal",
            )
        elif val >= 5:
            ax.text(
                x_pos,
                y_pos,
                f"{short} {val:.0f}%",
                fontsize=12,
                ha="center",
                va="center",
                color="white",
                fontweight="normal",
            )
        elif val >= 3:
            ax.text(
                x_pos, y_pos, f"{val:.0f}%", fontsize=12, ha="center", va="center", color="white", fontweight="normal"
            )
        elif val >= 1:
            ax.text(
                x_pos, y_pos, f"{val:.0f}", fontsize=10, ha="center", va="center", color="white", fontweight="normal"
            )

    # Update left positions for next category
    left = [left[i] + values[i] for i in range(len(y_positions))]

# Add round labels on the right side of the plot
for y_late, y_early in zip(y_positions[::2], y_positions[1::2]):
    ax.text(-2, y_late, "round ≥8", fontsize=9, ha="right", va="center", color="gray")
    ax.text(-2, y_early, "round ≤7", fontsize=9, ha="right", va="center", color="gray")

ax.set_title("What kinds of edits are performed on the main player file?", fontsize=14, fontweight="normal", pad=20)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.05), fontsize=12, ncol=5, frameon=False, markerscale=1.5)
ax.set_xlim(0, 100)
ax.set_yticks(model_positions)
ax.set_yticklabels(models, fontsize=12)

# Remove frame and x-axis, keep y-axis
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_visible(False)
ax.spines["left"].set_visible(True)
ax.xaxis.set_visible(False)

plt.tight_layout()
plt.show()

# %%
# Bar chart: Are edits grounded in analysis?
import matplotlib.pyplot as plt
import numpy as np

# Configure matplotlib to use a font that supports emojis
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans", "sans-serif"]

# Get unique models
models = [m for m in df["model_name"].unique() if isinstance(m, str)]

# Create new column for edits motivated by insights but not logs
df_temp = df.copy()
df_temp["edits_motivated_by_insight_not_logs"] = df_temp["edits_motivated_by_insights"] & (
    ~df_temp["edits_motivated_by_logs"]
)

# Calculate percentages for each model
motivated_by_logs = []
motivated_by_insights_not_logs = []

for model in models:
    model_df = df_temp[df_temp["model_name"] == model]
    total = len(model_df)

    logs_pct = (model_df["edits_motivated_by_logs"].sum() / total * 100) if total > 0 else 0
    insights_not_logs_pct = (model_df["edits_motivated_by_insight_not_logs"].sum() / total * 100) if total > 0 else 0

    motivated_by_logs.append(logs_pct)
    motivated_by_insights_not_logs.append(insights_not_logs_pct)

# Create horizontal bar chart
fig, ax = plt.subplots()  # figsize=(12, 6))

y_positions = np.arange(len(models))
bar_height = 0.6

# Plot stacked horizontal bars
bars1 = ax.barh(
    y_positions, motivated_by_logs, bar_height, label="Analysis of previous round logs", alpha=1.0, color="steelblue"
)
bars2 = ax.barh(
    y_positions,
    motivated_by_insights_not_logs,
    bar_height,
    left=motivated_by_logs,
    label="Other analysis/tests",
    alpha=0.5,
    color="steelblue",
)

# Add percentage labels
for i, (logs, insights) in enumerate(zip(motivated_by_logs, motivated_by_insights_not_logs)):
    if logs >= 5:
        ax.text(logs / 2, i, f"{logs:.0f}%", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    if insights >= 5:
        ax.text(logs + insights / 2, i, f"{insights:.0f}%", ha="center", va="center", fontsize=12, color="black")

ax.set_title("Are edits grounded in analysis?", fontsize=14, fontweight="normal", pad=20)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.08), fontsize=11, ncol=2, frameon=False)
ax.set_yticks(y_positions)
ax.set_yticklabels(models, fontsize=11)
ax.set_xlabel("Percentage (%)", fontsize=12)
ax.set_xlim(0, 100)

# Remove top and right spines
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.show()


# %%
# Bar chart: Improved test/analysis framework
import matplotlib.pyplot as plt
import numpy as np

# Configure matplotlib to use a font that supports emojis
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans", "sans-serif"]

# Get unique models
models = [m for m in df["model_name"].unique() if isinstance(m, str)]

# Calculate percentages for each model
improved_framework = []

for model in models:
    model_df = df[df["model_name"] == model]
    pct = model_df["improved_test_analysis_framework"].mean() * 100
    improved_framework.append(pct)

# Create horizontal bar chart
fig, ax = plt.subplots()

y_positions = np.arange(len(models))
bar_height = 0.6

# Plot horizontal bars
bars = ax.barh(y_positions, improved_framework, bar_height, alpha=0.8, color="coral")

# Add percentage labels
for i, pct in enumerate(improved_framework):
    if pct >= 5:
        ax.text(pct / 2, i, f"{pct:.0f}%", ha="center", va="center", fontsize=10, fontweight="bold", color="white")

ax.set_title("Was the testing/analysis framework improved in this round?", fontsize=14, fontweight="normal", pad=20)
ax.set_yticks(y_positions)
ax.set_yticklabels(models, fontsize=11)
ax.set_xlabel("Percentage (%)", fontsize=14)
ax.set_xlim(0, 100)

# Remove top and right spines
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.show()


# %%
# Bar chart: Edits motivated by old static messages
import matplotlib.pyplot as plt
import numpy as np

# Configure matplotlib to use a font that supports emojis
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans", "sans-serif"]

# Get unique models
models = [m for m in df["model_name"].unique() if isinstance(m, str)]

# Calculate percentages for each model
motivated_by_static = []

for model in models:
    model_df = df[df["model_name"] == model]
    pct = model_df["edits_motivated_by_old_static_messages"].mean() * 100
    motivated_by_static.append(pct)

# Create horizontal bar chart
fig, ax = plt.subplots()

y_positions = np.arange(len(models))
bar_height = 0.6

# Plot horizontal bars
bars = ax.barh(y_positions, motivated_by_static, bar_height, alpha=0.8, color="orchid")

# Add percentage labels
for i, pct in enumerate(motivated_by_static):
    if pct >= 5:
        ax.text(pct / 2, i, f"{pct:.0f}%", ha="center", va="center", fontsize=10, fontweight="bold", color="white")

ax.set_title("Are edits following a plan from a previous round?", fontsize=14, fontweight="normal", pad=20)
ax.set_yticks(y_positions)
ax.set_yticklabels(models, fontsize=11)
ax.set_xlabel("Percentage (%)", fontsize=14)
ax.set_xlim(0, 100)

# Remove top and right spines
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.show()


# %%
# Bar chart: Are edits validated based on execution feedback?
import matplotlib.pyplot as plt
import numpy as np

# Configure matplotlib to use a font that supports emojis
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans", "sans-serif"]

# Get unique models
models = [m for m in df["model_name"].unique() if isinstance(m, str)]

# Create new column for edits tested with both simulations and unittests
df_temp = df.copy()
df_temp["edits_tested_sim_and_unit"] = (
    df_temp["edits_tested_with_simulations"] & df_temp["edits_validated_with_unittests"]
)
df_temp["edits_tested_sim_only"] = df_temp["edits_tested_with_simulations"] & (
    ~df_temp["edits_validated_with_unittests"]
)
df_temp["edits_tested_unit_only"] = df_temp["edits_validated_with_unittests"] & (
    ~df_temp["edits_tested_with_simulations"]
)

# Calculate percentages for each model
tested_both = []
tested_sim_only = []
tested_unit_only = []

for model in models:
    model_df = df_temp[df_temp["model_name"] == model]
    total = len(model_df)

    both_pct = (model_df["edits_tested_sim_and_unit"].sum() / total * 100) if total > 0 else 0
    sim_pct = (model_df["edits_tested_sim_only"].sum() / total * 100) if total > 0 else 0
    unit_pct = (model_df["edits_tested_unit_only"].sum() / total * 100) if total > 0 else 0

    tested_both.append(both_pct)
    tested_sim_only.append(sim_pct)
    tested_unit_only.append(unit_pct)

# Create horizontal bar chart
fig, ax = plt.subplots()  # figsize=(12, 6))

y_positions = np.arange(len(models))
bar_height = 0.6

# Plot stacked horizontal bars
bars1 = ax.barh(
    y_positions, tested_both, bar_height, label="Both simulations & unittests", alpha=1.0, color="forestgreen"
)
bars2 = ax.barh(
    y_positions, tested_sim_only, bar_height, left=tested_both, label="Simulations only", alpha=0.7, color="forestgreen"
)
bars3 = ax.barh(
    y_positions,
    tested_unit_only,
    bar_height,
    left=np.array(tested_both) + np.array(tested_sim_only),
    label="Unittests only",
    alpha=0.4,
    color="forestgreen",
)

# Add percentage labels
for i, (both, sim, unit) in enumerate(zip(tested_both, tested_sim_only, tested_unit_only)):
    if both >= 5:
        ax.text(both / 2, i, f"{both:.0f}%", ha="center", va="center", fontsize=10, fontweight="bold", color="white")
    if sim >= 5:
        ax.text(
            both + sim / 2, i, f"{sim:.0f}%", ha="center", va="center", fontsize=10, fontweight="bold", color="white"
        )
    if unit >= 5:
        ax.text(both + sim + unit / 2, i, f"{unit:.0f}%", ha="center", va="center", fontsize=10, color="dimgray")

ax.set_title("Are edits validated based on execution feedback?", fontsize=14, fontweight="normal", pad=20)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.08), fontsize=11, ncol=3, frameon=False)
ax.set_yticks(y_positions)
ax.set_yticklabels(models, fontsize=11)
ax.set_xlabel("Percentage (%)", fontsize=12)
ax.set_xlim(0, 100)

# Remove top and right spines
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.show()


# %%

# %%

# %%

# %%

# %%

# %%
