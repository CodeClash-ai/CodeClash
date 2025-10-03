#!/usr/bin/env python3
"""
Command Diversity Analysis via CDF Visualization

This script analyzes the diversity of bash commands used by different AI models
during CodeClash tournaments, visualized as a Cumulative Distribution Function (CDF).

WHAT THE METRIC MEASURES:
- Command Diversity = Shannon entropy of command types used in each session
- Higher entropy (2.5-3.5) = model uses many different command types
- Lower entropy (1.5-2.5) = model tends to stick to fewer command types

HOW TO INTERPRET THE CDF:
- X-axis: Shannon entropy values (diversity score)
- Y-axis: Cumulative probability (fraction of sessions at or below that diversity)
- Curves shifted RIGHT = more diverse command usage
- Curves shifted LEFT = more focused/repetitive command usage
- Steep curves = consistent behavior, gradual curves = variable behavior

STRATEGIC IMPLICATIONS:
High diversity could indicate:
- Better exploration of the codebase and problem space
- More thorough debugging and analysis approaches
- Adaptability to different types of challenges
- OR potentially inefficient trial-and-error behavior

Low diversity could indicate:
- Efficient, focused strategies with proven command patterns
- Expertise with a smaller set of reliable tools
- Consistent methodology across different problems
- OR potentially limited problem-solving approaches or tool awareness

The "best" diversity level depends on the task complexity and whether exploration
or exploitation is more valuable in the given context.
"""

import json
import math
from collections import Counter

from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = "cdf_command_diversity.png"


def shannon_entropy(command_list):
    """
    Calculate Shannon entropy for a list of commands.

    Shannon entropy measures the "surprise" or information content in the distribution.
    - Higher entropy = more uniform distribution across command types (more diverse)
    - Lower entropy = some commands are much more frequent (more focused)
    - Max entropy = log2(unique_commands) when all commands equally frequent

    Args:
        command_list: List of command strings (e.g., ['ls', 'cat', 'ls', 'grep'])

    Returns:
        Float entropy value (0 = single command type, higher = more diverse)
    """
    if not command_list:
        return 0.0

    # Count frequency of each command type
    counter = Counter(command_list)
    total = len(command_list)
    entropy = 0.0

    # Calculate Shannon entropy: -Σ(p * log2(p)) where p is probability of each command
    for count in counter.values():
        prob = count / total
        entropy -= prob * math.log2(prob)

    return entropy


def extract_commands_from_trajectory(traj):
    """
    Extract all bash commands from a trajectory file.

    Parses assistant messages to find bash code blocks and extracts the first word
    of each command as the "command type" (e.g., 'cat', 'ls', 'python', etc.).

    Args:
        traj: Loaded trajectory JSON data

    Returns:
        List of command type strings used in this session
    """
    commands = []
    messages = traj.get("messages", [])

    # Look through all assistant responses for bash commands
    for message in messages:
        if message.get("role") == "assistant":
            content = message.get("content", "")

            # Extract bash command from ```bash code blocks using regex
            import re

            bash_match = re.search(r"```(bash|sh)\n(.*?)\n```", content, re.DOTALL)
            if bash_match:
                command = bash_match.group(2).strip()
                # Get first word as command type (e.g., "cat file.txt" -> "cat")
                cmd_type = command.split()[0] if command else "unknown"
                commands.append(cmd_type)

    return commands


def main():
    """
    Main analysis function that processes all tournament data and generates the CDF plot.

    Process:
    1. Scan all tournament directories for trajectory files
    2. Extract commands from each trajectory and calculate diversity
    3. Group diversity scores by model
    4. Generate CDF visualization comparing models
    """
    model_to_diversity = {}

    # Find all tournament directories by looking for game.log files
    tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("game.log")]
    for game_log_folder in tqdm(tournaments):
        # Load tournament metadata to get player-to-model mapping
        with open(game_log_folder / "metadata.json") as f:
            metadata = json.load(f)
        try:
            # Extract mapping from player name to model name
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}
            # Initialize diversity list for each model we encounter
            for model in p2m.values():
                if model not in model_to_diversity:
                    model_to_diversity[model] = []
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

                    # Extract commands and calculate diversity for this session
                    commands = extract_commands_from_trajectory(traj)
                    if commands:  # Only calculate entropy if there are commands
                        diversity = shannon_entropy(commands)
                        model_to_diversity[p2m[name]].append(diversity)
                except (json.JSONDecodeError, KeyError):
                    # Skip malformed trajectory files
                    continue

    # Remove models with no valid data
    model_to_diversity = {k: v for k, v in model_to_diversity.items() if v}

    # Print summary statistics for each model
    print("Command Diversity Summary:")
    for model, diversities in model_to_diversity.items():
        avg_diversity = sum(diversities) / len(diversities)
        max_diversity = max(diversities)
        print(
            f"- {model}: {len(diversities)} sessions; avg diversity {avg_diversity:.3f}; max diversity {max_diversity:.3f}"
        )

    # Generate CDF plot comparing all models
    plt.figure(figsize=(12, 8))
    colors = plt.cm.tab10(range(len(model_to_diversity)))

    for i, (model, diversities) in enumerate(model_to_diversity.items()):
        # Sort diversity values and create cumulative probability values
        sorted_diversities = sorted(diversities)
        yvals = [i / len(sorted_diversities) for i in range(len(sorted_diversities))]
        # Plot as step function (standard for CDFs)
        plt.step(sorted_diversities, yvals, label=model, where="post", color=colors[i])

    plt.xlabel("Command Diversity (Shannon Entropy)")
    plt.ylabel("Cumulative Probability")
    plt.title("CDF of Command Diversity by Model\n(Higher entropy = more diverse command usage)")
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")  # Legend outside plot area
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved CDF plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
