#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE


@dataclass
class PlayerGameProfile:
    player_id: str
    model_name: str
    game_id: str
    wins: int = 0
    count: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.count if self.count > 0 else 0.0


def main(log_dir: Path):
    # Assuming directory structure is:
    # logs/<user_id>/<game_id>
    # - players/
    # - game.log
    # - metadata.json
    model_profiles = {}
    for game_log_folder in tqdm([x.parent for x in log_dir.rglob("metadata.json")]):
        game_id = game_log_folder.name.split(".")[1]
        player_ids = [x.name for x in (game_log_folder / "players").iterdir() if x.is_dir()]
        metadata = json.load(open(game_log_folder / "metadata.json"))
        try:
            player_to_model = {
                x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]
            }
        except KeyError:
            continue
        num_rounds = len(metadata["round_stats"])

        # Only count each unique model once per game
        unique_models = {player_to_model[player] for player in player_ids}
        for model_name in unique_models:
            k = f"{game_id}.{model_name}"
            if k in model_profiles:
                model_profiles[k].count += num_rounds
            else:
                # Use the first player_id that matches this model_name for display
                player_id = next(pid for pid in player_ids if player_to_model[pid] == model_name)
                model_profiles[k] = PlayerGameProfile(
                    player_id=player_id, model_name=model_name, game_id=game_id, count=num_rounds
                )

        for round, details in metadata["round_stats"].items():
            if round == "0":
                # Skip initial round
                continue
            winner = details["winner"]
            if winner != RESULT_TIE:
                model_profiles[f"{game_id}.{player_to_model[winner]}"].wins += 1

    print("Player profiles:")
    lines = [
        f" - {profile.model_name} (Game: {profile.game_id}) - Win Rate: {profile.win_rate:.2%} ({profile.wins}/{profile.count})"
        for profile in model_profiles.values()
    ]
    print("\n".join(sorted(lines)))

    # Player-specific (game-agnostic) win rates (micro average)
    total_wins = {}
    total_games = {}
    model_names = {}
    for profile in model_profiles.values():
        mid = profile.model_name
        total_wins[mid] = total_wins.get(mid, 0) + profile.wins
        total_games[mid] = total_games.get(mid, 0) + profile.count
        model_names[mid] = profile.model_name

    print("\nPlayer-specific win rates (game-agnostic, micro average):")
    calc_win_rate = lambda w, c: w / c if c > 0 else 0.0
    lines = [
        f" - {model_names[mid]}: Win Rate {calc_win_rate(total_wins[mid], total_games[mid]):.2%} ({total_wins[mid]}/{total_games[mid]})"
        for mid in total_wins
    ]
    print("\n".join(sorted(lines)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--log_dir", type=Path, help="Path to game logs (Default: logs/)", default=LOCAL_LOG_DIR)
    args = parser.parse_args()
    main(args.log_dir)
