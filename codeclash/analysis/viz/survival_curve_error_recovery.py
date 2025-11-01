#!/usr/bin/env python3
"""
Error Recovery Time Analysis via Survival Curve Visualization

This script analyzes how quickly different AI models recover from command failures
during CodeClash tournaments, visualized as survival curves showing the probability
that recovery takes longer than X steps.

WHAT THE METRIC MEASURES:
- Error Recovery Time = number of steps between a failed command (returncode != 0)
  and the next successful command (returncode == 0)
- Survival Curve = P(recovery takes > X steps) for each X
- Shows what fraction of errors take longer than each recovery time

HOW TO INTERPRET THE SURVIVAL CURVES:
- Y-axis: Probability that recovery takes MORE than X steps
- X-axis: Number of steps to recovery
- Curves that drop quickly (steep) = most errors recovered fast
- Curves that drop slowly (gradual) = more errors take longer to resolve
- Lower curves = faster recovery (better resilience)
- Where curve hits 0 = maximum recovery time observed

STRATEGIC IMPLICATIONS:
Steep drops (most models) indicate:
- Strong immediate error correction abilities
- Familiarity with common failure modes and quick fixes
- Efficient "try the obvious solution first" strategies

Gradual drops would indicate:
- More systematic debugging approaches
- Encountering more complex errors requiring investigation
- Less familiarity with the environment

The survival curve naturally handles the right-skewed distribution and focuses
on the meaningful differences in recovery speed without being distorted by outliers.
"""

import json
import re
from collections import defaultdict

import matplotlib.pyplot as plt
from tqdm.auto import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = ASSETS_DIR / "survival_curve_error_recovery.pdf"
DATA_CACHE = ASSETS_DIR / "survival_curve_error_recovery.json"


def extract_command_results(traj):
    """
    Extract sequence of command execution results from a trajectory.

    Returns a list of tuples: (command_type, returncode) in chronological order.
    This allows us to track the sequence of successes and failures.

    Args:
        traj: Loaded trajectory JSON data

    Returns:
        List of (command_type, returncode) tuples
    """
    results = []
    messages = traj.get("messages", [])

    for i, message in enumerate(messages):
        if message.get("role") == "user" and i > 0:  # Skip first message (initial prompt)
            # Handle both string and list content formats
            content = message.get("content", "")
            if isinstance(content, list) and content:
                text_content = content[0].get("text", "")
            elif isinstance(content, str):
                text_content = content
            else:
                continue

            # Extract return code from this command execution
            returncode_match = re.search(r"<returncode>(\d+)</returncode>", text_content)
            if not returncode_match:
                continue
            returncode = int(returncode_match.group(1))

            # Get the command that was executed (from previous assistant message)
            prev_message = messages[i - 1]
            if prev_message.get("role") == "assistant":
                prev_content = prev_message.get("content", "")
                bash_match = re.search(r"```(bash|sh)\n(.*?)\n```", prev_content, re.DOTALL)
                if bash_match:
                    command = bash_match.group(2).strip()
                    cmd_type = command.split()[0] if command else "unknown"
                    results.append((cmd_type, returncode))

    return results


def calculate_recovery_times(command_results):
    """
    Calculate recovery times for each error in the sequence.

    For each failed command (returncode != 0), count how many steps it takes
    to get to the next successful command (returncode == 0).

    Args:
        command_results: List of (command_type, returncode) tuples

    Returns:
        List of recovery times (integers)
    """
    recovery_times = []

    for i, (_, returncode) in enumerate(command_results):
        if returncode != 0:  # This command failed
            # Look ahead to find the next successful command
            steps_to_recovery = 0
            for j in range(i + 1, len(command_results)):
                steps_to_recovery += 1
                _, next_returncode = command_results[j]
                if next_returncode == 0:  # Found a successful command
                    recovery_times.append(steps_to_recovery)
                    break
            # If we never found a successful command, don't count this failure
            # (model never recovered within this session)

    return recovery_times


def calculate_survival_curve(recovery_times):
    """
    Calculate survival curve data from recovery times.

    Returns the probability that recovery takes MORE than X steps for each X.
    This is more intuitive than CDF for "time to event" data.

    Args:
        recovery_times: List of recovery time integers

    Returns:
        Tuple of (x_values, survival_probabilities)
    """
    if not recovery_times:
        return [], []

    # Get unique recovery times and sort them
    unique_times = sorted(set(recovery_times))
    max_time = max(unique_times)

    # Calculate survival probability for each time point
    x_values = list(range(0, max_time + 1))
    survival_probs = []

    total_errors = len(recovery_times)

    for x in x_values:
        # Count how many recoveries took MORE than x steps
        still_recovering = sum(1 for t in recovery_times if t > x)
        survival_prob = still_recovering / total_errors
        survival_probs.append(survival_prob)

    return x_values, survival_probs


def main():
    """
    Main analysis function that processes all tournament data and generates survival curves.

    Process:
    1. Scan all tournament directories for trajectory files
    2. Extract command execution sequences and calculate recovery times
    3. Group recovery times by model
    4. Generate survival curve visualization comparing models
    """
    if not DATA_CACHE.exists():
        model_to_recovery_times = defaultdict(list)

        # Find all tournament directories by looking for metadata.json files
        tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("metadata.json")]
        for game_log_folder in tqdm(tournaments):
            # Load tournament metadata to get player-to-model mapping
            with open(game_log_folder / "metadata.json") as f:
                metadata = json.load(f)
            try:
                # Extract mapping from player name to model name
                p2m = {
                    x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                    for x in metadata["config"]["players"]
                }
            except KeyError:
                # Skip tournaments with malformed metadata
                continue

            # Process each player's trajectory files
            for name in p2m.keys():
                traj_files = (game_log_folder / "players" / name).rglob("*.traj.json")
                for traj_file in traj_files:
                    try:
                        with open(traj_file) as f:
                            traj = json.load(f)

                        # Extract command results and calculate recovery times
                        command_results = extract_command_results(traj)
                        recovery_times = calculate_recovery_times(command_results)

                        # Add to model's collection (even if empty - shows model had sessions)
                        model_to_recovery_times[p2m[name]].extend(recovery_times)

                    except (json.JSONDecodeError, KeyError, FileNotFoundError):
                        # Skip malformed trajectory files
                        continue

        # Remove models with no data
        model_to_recovery_times = {k: v for k, v in model_to_recovery_times.items() if v}

        # Cache the processed data
        with open(DATA_CACHE, "w") as f:
            json.dump(model_to_recovery_times, f, indent=2)

    with open(DATA_CACHE) as f:
        model_to_recovery_times = json.load(f)

    # Print summary statistics for each model
    print("Error Recovery Time Summary:")
    for model, recovery_times in model_to_recovery_times.items():
        if recovery_times:
            avg_recovery = sum(recovery_times) / len(recovery_times)
            median_recovery = sorted(recovery_times)[len(recovery_times) // 2]
            immediate_recovery_pct = (sum(1 for t in recovery_times if t == 1) / len(recovery_times)) * 100
            print(
                f"- {model}: {len(recovery_times)} recoveries; avg {avg_recovery:.2f} steps; median {median_recovery} steps; {immediate_recovery_pct:.1f}% immediate"
            )
        else:
            print(f"- {model}: No recovery data (no errors or no successful recoveries)")

    if not model_to_recovery_times:
        print("No recovery data found!")
        return

    # Generate survival curves comparing all models
    plt.figure(figsize=(6, 6))

    for _, (model, recovery_times) in enumerate(model_to_recovery_times.items()):
        if recovery_times:  # Only plot if there's data
            x_values, survival_probs = calculate_survival_curve(recovery_times)
            plt.plot(
                x_values,
                survival_probs,
                label=MODEL_TO_DISPLAY_NAME[model],
                linewidth=2.5,
                color=MODEL_TO_COLOR[model],
                marker="o",
                markersize=4,
            )

    plt.xlabel("Recovery Time (Steps)", fontproperties=FONT_BOLD, fontsize=18)
    plt.ylabel("P(Recovery takes > X steps)", fontproperties=FONT_BOLD, fontsize=18)
    # plt.title("Error Recovery Survival Curves by Model\n(Lower curves = faster recovery from command failures)")
    FONT_BOLD.set_size(16)
    plt.legend(loc="upper right", prop=FONT_BOLD)
    plt.grid(True, alpha=0.3)
    plt.xticks([1, 2, 3, 4])
    plt.xlim(left=0, right=4)
    plt.ylim(bottom=0, top=1)

    # Add some useful reference lines
    # plt.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5, label="50% still recovering")
    # plt.axhline(y=0.1, color="gray", linestyle=":", alpha=0.5, label="10% still recovering")

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved survival curve plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
