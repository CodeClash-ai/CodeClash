import argparse
import json
import re
from collections import Counter
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.constants import LOCAL_LOG_DIR


class ModelProfile:
    def __init__(self, name: str):
        self.name = name
        self.steps = []
        self.failed_commands = 0
        self.failed_command_types = {}
        self.tournaments = []

    @property
    def steps_per_round(self) -> float:
        return sum(self.steps) / len(self.steps) if self.steps else 0.0

    @property
    def steps_total(self) -> int:
        return sum(self.steps)

    @property
    def cmd_failure_rate(self) -> float:
        return self.failed_commands / sum(self.steps) if self.steps else 0.0

    @property
    def rounds_total(self) -> int:
        return len(self.steps)

    @property
    def tournament_count(self) -> Counter:
        return Counter([t.split(".", 2)[1] for t in self.tournaments])

    def __repr__(self):
        return f"""Model: {self.name}
- Steps: {self.steps_total} (Total); {self.steps_per_round:.2f} (Per Round);
- Rounds played: {self.rounds_total}
- Failed cmds: {self.cmd_failure_rate:.2%} ({self.failed_commands}/{self.steps_total})
- Most common failed command types: {Counter(self.failed_command_types).most_common(5)}
- Tournament count: {self.tournament_count.most_common(5)}"""


class TrajectoryAnalyzer:
    def __init__(self, traj_path: str):
        try:
            with open(traj_path) as f:
                self.traj = json.load(f)
                self.messages = self.traj.get("messages", [])
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            self.traj = {}
            self.messages = []

    @property
    def steps(self) -> int:
        return sum([1 for x in self.traj["messages"] if x["role"] == "assistant"])

    @property
    def failure_stats(self) -> dict:
        failed_commands = 0
        failed_command_types = {}
        for i, message in enumerate(self.messages):
            if message["role"] == "user":
                content = message.get("content", "")

                # Handle both list and string content formats
                if isinstance(content, list) and content:
                    text_content = content[0].get("text", "")
                elif isinstance(content, str):
                    text_content = content
                else:
                    continue

                returncode_match = re.search(r"<returncode>(\d+)</returncode>", text_content)

                if i == 0 or not returncode_match:
                    continue
                returncode = int(returncode_match.group(1))

                # Extract bash command from code block
                prev_message = self.messages[i - 1]
                if prev_message["role"] != "assistant":
                    continue
                prev_content = prev_message.get("content", "")
                bash_match = re.search(r"```(bash|sh)\n(.*?)\n```", prev_content, re.DOTALL)
                if not bash_match:
                    continue
                command = bash_match.group(2).strip()
                cmd_type = command.split()[0] if command else "unknown"

                if returncode != 0:
                    failed_commands += 1
                    failed_command_types[cmd_type] = failed_command_types.get(cmd_type, 0) + 1

        return {"failed_commands": failed_commands, "failed_command_types": failed_command_types}


def main(log_dir: str):
    profiles = {}
    tournaments = [x.parent for x in log_dir.rglob("metadata.json")]
    for game_log_folder in tqdm(tournaments):
        with open(game_log_folder / "metadata.json") as f:
            metadata = json.load(f)
        try:
            p2m = {
                x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                for x in metadata["config"]["players"]
            }
        except KeyError:
            continue

        for model in p2m.values():
            if model not in profiles:
                profiles[model] = ModelProfile(name=model)
            profiles[model].tournaments.append(game_log_folder.stem)

        for name in p2m.keys():
            traj_files = (game_log_folder / "players" / name).rglob("*.traj.json")
            for traj_file in traj_files:
                try:
                    analyzer = TrajectoryAnalyzer(traj_file)
                except (json.JSONDecodeError, KeyError, FileNotFoundError):
                    continue
                profiles[p2m[name]].steps.append(analyzer.steps)

                failure_stats = analyzer.failure_stats
                profiles[p2m[name]].failed_commands += failure_stats["failed_commands"]
                for k, v in failure_stats["failed_command_types"].items():
                    profiles[p2m[name]].failed_command_types[k] = profiles[p2m[name]].failed_command_types.get(k, 0) + v

    sep = "=" * 40
    print(f"Models found: {len(profiles)}")
    print(f"Tournaments found: {len(tournaments)}")
    print(sep)
    for profile in profiles.values():
        print(profile)
        print(sep)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get basic statistics about each model")
    parser.add_argument("-d", "--log_dir", type=Path, help="Path to game logs (Default: logs/)", default=LOCAL_LOG_DIR)
    args = parser.parse_args()
    main(**vars(args))
