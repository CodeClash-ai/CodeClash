#!/usr/bin/env python3
import argparse
import json
import logging
from pathlib import Path

from tqdm import tqdm

from codeclash.analysis.metrics.elo import get_scores
from codeclash.constants import LOCAL_LOG_DIR

logger = logging.getLogger(__name__)


def extract_round_scores(log_dir: Path, output_file: Path) -> None:
    game_tournaments: dict[str, list[dict[str, list[float]]]] = {}

    for metadata_path in tqdm(list(log_dir.rglob("metadata.json"))):
        with open(metadata_path) as f:
            metadata = json.load(f)

        try:
            players = metadata["config"]["players"]
            game_name = metadata["config"]["game"]["name"]
            round_stats = metadata["round_stats"]
        except KeyError:
            logger.warning(f"Skipping {metadata_path} (malformed metadata.json)")
            continue

        if game_name not in game_tournaments:
            game_tournaments[game_name] = []

        tournament_scores: dict[str, list[float]] = {}
        player_to_model = {}
        for player_config in players:
            player_name = player_config["name"]
            model_name = player_config["config"]["model"]["model_name"].strip("@")
            player_to_model[player_name] = model_name

        for round_idx, stats in round_stats.items():
            if round_idx == "0":
                continue

            player2score = get_scores(stats)

            for player_name, score in player2score.items():
                model_name = player_to_model.get(player_name)
                if not model_name:
                    continue

                if model_name not in tournament_scores:
                    tournament_scores[model_name] = []

                tournament_scores[model_name].append(score)

        game_tournaments[game_name].append(tournament_scores)

    output_file.write_text(json.dumps(game_tournaments, indent=2))
    logger.info(f"Wrote round scores to {output_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Extract round scores from tournament logs")
    parser.add_argument(
        "-d",
        "--log_dir",
        type=Path,
        default=LOCAL_LOG_DIR,
        help="Path to game logs (Default: logs/)",
    )
    parser.add_argument(
        "-o",
        "--output_file",
        type=Path,
        default=Path("round_scores.json"),
        help="Output file path (Default: round_scores.json)",
    )
    args = parser.parse_args()

    extract_round_scores(args.log_dir, args.output_file)
