import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from codeclash.constants import RESULT_TIE


@dataclass
class PlayerGameProfile:
    player_id: str
    game_id: str
    wins: int = 0
    count: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.count if self.count > 0 else 0.0


def main(log_dir: Path):
    player_profiles = {}
    for game_log_folder in log_dir.iterdir():
        if game_log_folder.is_dir():
            print(f"Processing game log folder: {game_log_folder}")

        game_id = game_log_folder.name.split(".")[1]
        player_ids = [x.name for x in (game_log_folder / "players").iterdir() if x.is_dir()]
        num_rounds = len(list((game_log_folder / "rounds").iterdir()))

        for player in player_ids:
            if f"{game_id}.{player}" in player_profiles:
                player_profiles[f"{game_id}.{player}"].count += num_rounds
            else:
                player_profiles[f"{game_id}.{player}"] = PlayerGameProfile(
                    player_id=player, game_id=game_id, count=num_rounds
                )

        for round_folder in (game_log_folder / "rounds").iterdir():
            round_results = json.load(open(round_folder / "results.json"))
            winner = round_results.get("winner")
            if winner != RESULT_TIE:
                player_profiles[f"{game_id}.{winner}"].wins += 1

    print("Player profiles:")
    for profile in player_profiles.values():
        print(
            f" - {profile.player_id} (Game: {profile.game_id}) - Win Rate: {profile.win_rate:.2%} ({profile.wins}/{profile.count})"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_dir", type=Path, help="Path to `logs/<user>` folder containing game logs")
    args = parser.parse_args()
    main(args.log_dir)
