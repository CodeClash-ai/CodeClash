import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from codeclash.constants import FILE_RESULTS, LOCAL_LOG_DIR

K_FACTOR = 32  # ELO constant, changeable


@dataclass
class PlayerEloProfile:
    player_id: str
    game_id: str
    rating: float = 1200.0  # Default starting ELO
    games_played: int = 0


def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def main(log_dir: Path):
    # Assuming directory structure is:
    # logs/<user_id>/<game_id>
    # - players/
    # - rounds/
    # - game.log
    # - metadata.json
    player_profiles = {}
    for user_folder in log_dir.iterdir():
        print(f"Processing games under user `{user_folder.name}`")
        for game_log_folder in tqdm(list(user_folder.iterdir())):
            if not game_log_folder.is_dir():
                continue
            game_id = game_log_folder.name.split(".")[1]
            player_ids = [x.name for x in (game_log_folder / "players").iterdir() if x.is_dir()]
            # Initialize profiles
            for player in player_ids:
                key = f"{game_id}.{player}"
                if key not in player_profiles:
                    player_profiles[key] = PlayerEloProfile(player_id=player, game_id=game_id)

            for round_folder in (game_log_folder / "rounds").iterdir():
                if round_folder.name == "0":
                    # Skip initial round
                    continue
                if not (round_folder / FILE_RESULTS).exists():
                    continue
                round_results = json.load(open(round_folder / FILE_RESULTS))
                winner = round_results.get("winner")
                players = round_results.get("players", player_ids)
                # Only process if there are exactly 2 players
                if len(players) == 2:
                    p1_key = f"{game_id}.{players[0]}"
                    p2_key = f"{game_id}.{players[1]}"
                    p1 = player_profiles[p1_key]
                    p2 = player_profiles[p2_key]
                    p1.games_played += 1
                    p2.games_played += 1
                    # Determine scores
                    if winner == players[0]:
                        s1, s2 = 1, 0
                    elif winner == players[1]:
                        s1, s2 = 0, 1
                    else:
                        s1, s2 = 0.5, 0.5  # Tie
                    # Calculate expected scores
                    e1 = expected_score(p1.rating, p2.rating)
                    e2 = expected_score(p2.rating, p1.rating)
                    # Update ratings
                    p1.rating += K_FACTOR * (s1 - e1)
                    p2.rating += K_FACTOR * (s2 - e2)

    print("Player ELO profiles:")
    for profile in player_profiles.values():
        print(
            f" - {profile.player_id} (Game: {profile.game_id}) - ELO: {profile.rating:.1f} (Games: {profile.games_played})"
        )

    # Weighted average ELO per player across all games
    weighted_elo = {}
    total_games = {}
    for profile in player_profiles.values():
        pid = profile.player_id
        weighted_elo[pid] = weighted_elo.get(pid, 0) + profile.rating * profile.games_played
        total_games[pid] = total_games.get(pid, 0) + profile.games_played

    print("\nWeighted average ELO per player (across all games):")
    for pid in weighted_elo:
        if total_games[pid] > 0:
            avg_elo = weighted_elo[pid] / total_games[pid]
        else:
            avg_elo = 0.0
        print(f" - {pid}: Weighted Avg ELO {avg_elo:.1f} (Total Games: {total_games[pid]})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--log_dir", type=Path, help="Path to game logs (Default: logs/)", default=LOCAL_LOG_DIR)
    args = parser.parse_args()
    main(args.log_dir)
