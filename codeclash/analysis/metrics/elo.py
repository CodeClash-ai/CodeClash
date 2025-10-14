#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from codeclash.analysis.viz.utils import MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE
from codeclash.games import ARENAS, DummyGame


@dataclass
class ModelEloProfile:
    model: str
    arena: str
    rating: float
    rounds_played: int = 0


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def calculate_round_weight_linear(round_num: int, total_rounds: int) -> float:
    """Calculate linear weight for a round, with average weight = 1.0 across all rounds

    Args:
        round_num: Current round number (1-indexed. the first round that we show in the viewer
            is 0, but it's not a real round, so not included here)
        total_rounds: Total number of rounds in the game

    Returns:
        Weight value where early rounds have weight ~0.5 and late rounds have weight ~1.5
    """
    assert round_num >= 1
    assert round_num <= total_rounds
    # Linear: weight = 0.5 + (round_num / total_rounds)
    # This gives range [0.5, 1.5] with average = 1.0
    return 0.5 + (round_num / total_rounds)


def calculate_round_weight_exponential(round_num: int, total_rounds: int, alpha: float = 2.0) -> float:
    """Calculate exponential weight for a round, with average weight = 1.0 across all rounds

    Args:
        round_num: Current round number (1-indexed. the first round that we show in the viewer
            is 0, but it's not a real round, so not included here)
        total_rounds: Total number of rounds in the game
        alpha: Exponential factor (default 2.0 for quadratic weighting)

    Returns:
        Weight value with exponential progression favoring later rounds
    """
    assert round_num >= 1
    assert round_num <= total_rounds
    # Raw weight (exponential)
    raw_weight = (round_num / total_rounds) ** alpha

    # Normalization factor so average = 1.0
    # For α=2: average of x² from 0 to 1 is 1/3, so multiply by 3
    norm_factor = alpha + 1  # This makes average = 1.0

    return raw_weight * norm_factor


def get_scores(stats: dict) -> dict[str, float]:
    valid_submits = sum(
        [x["valid_submit"] for x in stats["player_stats"].values() if x.get("valid_submit") is not None]
    )

    ties = stats["scores"].get(RESULT_TIE, 0)
    sims = sum(stats["scores"].values())
    assert sims >= ties

    player2score = {}
    for k, v in stats["player_stats"].items():
        if k != RESULT_TIE:
            if v["score"] is None:
                # Not sure why this happens, but just skip it
                # Kilian: This is probably when we skip a round (might have fixed this, but probably in old logs)
                continue
            if valid_submits == 1:
                # FOR BACKWARDS COMPATIBILITY: If only one player submitted, give them full point
                if v["valid_submit"]:
                    _score = 1.0
                else:
                    _score = 0.0
            elif sims > 0:
                _score = (v["score"] + 0.5 * ties) * 1.0 / sims
            else:
                continue
            player2score[k] = _score
    return player2score


def update_profiles(prof_and_score: list[tuple[ModelEloProfile, float]], k_factor: float) -> None:
    """Update ELO profiles for two players based on their scores

    Args:
        prof_and_score: List of tuples [(ModelEloProfile, score), ...] for two players
        k_factor: Base K-factor for ELO calculation
    """
    p1_prof, p1_score = prof_and_score[0]
    p2_prof, p2_score = prof_and_score[1]

    assert p1_score + p2_score == 1.0, p1_score + p2_score

    expected_p1 = expected_score(p1_prof.rating, p2_prof.rating)

    # Apply round weighting to K-factor
    rating_change = k_factor * (p1_score - expected_p1)

    # Consistency:
    expected_p2 = expected_score(p2_prof.rating, p1_prof.rating)
    check = k_factor * (p2_score - expected_p2)
    assert abs(check + rating_change) < 1e-6, "Weighted ELO rating changes do not sum to zero!"

    p1_prof.rating += rating_change
    p2_prof.rating -= rating_change  # Zero-sum property


class SkipTournamentException(Exception):
    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class ELOCalculator:
    def __init__(self, *, k_factor: float, starting_elo: float, weighting_function: str, alpha: float, unit: str):
        self._k_factor = k_factor
        self._starting_elo = starting_elo
        self._weighting_function = weighting_function
        self._alpha = alpha
        self._unit = unit
        self._player_profiles = {}

    @property
    def player_profiles(self) -> dict[str, ModelEloProfile]:
        return self._player_profiles

    def _analyze_round(self, stats: dict, player2profile: dict, *, total_rounds: int) -> None:
        """Update all profiles based on the results of one round"""
        current_round = stats["round_num"]
        if self._weighting_function == "linear":
            round_weight = calculate_round_weight_linear(current_round, total_rounds)
        elif self._weighting_function == "exponential":
            round_weight = calculate_round_weight_exponential(current_round, total_rounds, self._alpha)
        else:  # none
            round_weight = 1.0

        player2score = get_scores(stats)

        prof_and_score = []
        for player, score in player2score.items():
            prof = player2profile[player]
            prof.rounds_played += 1
            prof_and_score.append((prof, score))

        if len(prof_and_score) != 2:
            raise SkipTournamentException(f"Skipping round {current_round} (wrong number of players)")

        weighted_k_factor = self._k_factor * round_weight
        update_profiles(prof_and_score, weighted_k_factor)

    def _score_per_round(self, metadata: dict, player2profile: dict, total_rounds: int) -> None:
        for idx, stats in metadata["round_stats"].items():
            idx = int(idx)
            if idx == 0:
                # Skip initial round
                continue
            assert idx == stats["round_num"], (idx, stats["round_num"])
            self._analyze_round(stats, player2profile, total_rounds=total_rounds)

    def _score_per_tournament(self, metadata: dict, player2profile: dict, total_rounds: int) -> None:
        # Update score = number of rounds won per tournament (ties count as 0.5 each)
        round_stats = metadata["round_stats"]
        winners = []
        ties = 0
        for k, v in round_stats.items():
            try:
                if int(k) == 0:
                    continue
            except Exception:
                pass
            w = v.get("winner")
            if w == RESULT_TIE:
                ties += 1
            elif w is not None:
                winners.append(w)

        win_counts = Counter(winners)

        # Ensure both players are considered (even if they have zero wins)
        players = list(player2profile.keys())
        for p in players:
            player2profile[p].rounds_played += 1  # Each player played all rounds
        wins_per_player = {p: win_counts.get(p, 0) + 0.5 * ties for p in players}

        wins_total = sum(wins_per_player.values())
        if wins_total == 0:
            raise SkipTournamentException

        prof_and_score = [(player2profile[p], wins_per_player[p] / wins_total) for p in players]

        weighted_k_factor = self._k_factor * (1 / total_rounds) if total_rounds > 0 else self._k_factor
        update_profiles(prof_and_score, weighted_k_factor)

    def _analyze_tournament(self, tournament_log_folder: Path) -> None:
        """Update all profiles based on the results of one tournament"""
        with open(tournament_log_folder / "metadata.json") as f:
            metadata = json.load(f)
        try:
            players = metadata["config"]["players"]
            arena = metadata["config"]["game"]["name"]
        except KeyError:
            raise SkipTournamentException("Skipping (malformed metadata.json)")

        if len(players) != 2:
            # Only process if there are exactly 2 players
            raise SkipTournamentException("Skipping (not 2 players)")

        # Initialize profiles
        player2profile = {}
        for player_config in players:
            player_name = player_config["name"]
            model = player_config["config"]["model"]["model_name"].strip("@")
            key = f"{arena}.{model}"
            if key not in self._player_profiles:
                self._player_profiles[key] = ModelEloProfile(model=model, arena=arena, rating=self._starting_elo)
            player2profile[player_name] = self._player_profiles[key]

        # Determine total rounds for weighting calculation
        if "round_stats" not in metadata:
            raise SkipTournamentException("Skipping (no `round_stats` in metadata)")
        total_rounds = len([k for k in metadata["round_stats"].keys() if k != "0"])

        if self._unit == "round":
            self._score_per_round(metadata, player2profile, total_rounds=total_rounds)
        elif self._unit == "tournament":
            self._score_per_tournament(metadata, player2profile, total_rounds=total_rounds)

    def analyze(self, log_dir: Path) -> None:
        print(f"Calculating weighted ELO ratings from logs in {log_dir} ...")
        print(f"Using K_FACTOR={self._k_factor}, STARTING_ELO={self._starting_elo}")
        print(
            f"Weighting function: {self._weighting_function}"
            + (f" (alpha={self._alpha})" if self._weighting_function == "exponential" else "")
        )
        for game_log_folder in tqdm([x.parent for x in log_dir.rglob("metadata.json")]):
            try:
                self._analyze_tournament(game_log_folder)
            except SkipTournamentException as e:
                print(f"[{game_log_folder.name}] {e.message}")
                continue

    def print_results(self) -> None:
        print("=" * 50)
        print("Player ELO profiles:")
        lines = [
            f" - {profile.model} ({profile.arena}) - ELO: {profile.rating:.0f} (Rounds: {profile.rounds_played})"
            for profile in self._player_profiles.values()
        ]
        print("\n".join(sorted(lines)))

        # ELO per player across all games
        weighted_elo = {}
        total_games = {}
        for profile in self._player_profiles.values():
            mid = profile.model
            weighted_elo[mid] = weighted_elo.get(mid, 0) + profile.rating * profile.rounds_played
            total_games[mid] = total_games.get(mid, 0) + profile.rounds_played

        print("\nELO per player (across all games):")
        calc_avg_elo = lambda total_elo, games: total_elo / games
        model_to_avg_elo = {mid: calc_avg_elo(weighted_elo[mid], total_games[mid]) for mid in weighted_elo}
        lines = sorted(
            [f"{pid}: {model_to_avg_elo[pid]:.1f} (Rounds: {total_games[pid]})" for pid in model_to_avg_elo.keys()],
            key=lambda x: float(x.split(":")[1].split("(")[0]),
            reverse=True,
        )
        for i, line in enumerate(lines, 1):
            print(f"{i}. {line}")

        # Print latex formatted table for results, formatted as
        # Model & ELO & & & \\
        # & BattleCode & BattleSnake & ... \\
        # \midrule
        # Claude 4 Sonnet & ... & & & \\
        # ...
        print("\nLaTeX formatted table:")
        arenas = [x.name for x in ARENAS if x != DummyGame]
        lines = []
        arenas_small = [f"\\scriptsize{{{arena}}}" for arena in arenas]
        line = "& " + " & ".join(arenas_small) + " & \\textbf{All}" + r" \\"
        line = line.replace("HuskyBench", "Poker")
        lines.append(line)
        lines.append(r"\midrule")
        per_model_lines = {}
        arena_rankings = {}

        # Create a mapping of model -> arena -> elo and also arena -> list of (model, elo) for ranking
        for profile in self._player_profiles.values():
            if profile.model not in per_model_lines:
                per_model_lines[profile.model] = {}
            if profile.arena not in arena_rankings:
                arena_rankings[profile.arena] = []
            per_model_lines[profile.model][profile.arena] = int(round(profile.rating, 0))
            arena_rankings[profile.arena].append((profile.model, profile.rating))

        # Sort each arena ranking by ELO descending
        for arena in arena_rankings:
            arena_rankings[arena].sort(key=lambda x: x[1], reverse=True)
            for rank, (model, _) in enumerate(arena_rankings[arena], 1):
                per_model_lines[model][arena] = (
                    f"{per_model_lines[model][arena]}" + f"\\textsuperscript{{\\textcolor{{gray}}{{{rank}}}}}"
                )
                if rank == 1:
                    # Make it bold
                    per_model_lines[model][arena] = f"\\textbf{{{per_model_lines[model][arena]}}}"

        # Now print the table
        overall_ranks = sorted(model_to_avg_elo.items(), key=lambda x: x[1], reverse=True)
        model_rank = {model: rank + 1 for rank, (model, _) in enumerate(overall_ranks)}
        for model, _ in overall_ranks:
            m = model.split("/", 1)[-1]
            rank = f"\\textsuperscript{{\\textcolor{{gray}}{{{model_rank[model]}}}}}"
            overall_elo = f"{model_to_avg_elo[model]:.0f}{rank}"
            if model_rank[model] == 1:
                overall_elo = f"\\textbf{{{overall_elo}}}"
            line = (
                f"\\small{{{MODEL_TO_DISPLAY_NAME[m]}}} & "
                + " & ".join(str(per_model_lines[model].get(arena, "-")) for arena in arenas)
                + " & "
                + overall_elo
                + " \\\\"
            )
            lines.append(line)
        print("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate weighted ELO ratings with configurable weighting functions")
    parser.add_argument("-d", "--log_dir", type=Path, help="Path to game logs (Default: logs/)", default=LOCAL_LOG_DIR)
    parser.add_argument("-k", "--k_factor", type=float, help="K-Factor for ELO calculation (Default: 32)", default=32)
    parser.add_argument(
        "-s", "--starting_elo", type=float, help="Starting ELO for new players (Default: 1200)", default=1200
    )
    parser.add_argument(
        "-w",
        "--weighting_function",
        choices=["none", "linear", "exponential"],
        default="none",
        help="Weighting function for rounds: 'linear' for gradual increase, 'exponential' for accelerating importance (Default: none)",
    )
    parser.add_argument(
        "-a",
        "--alpha",
        type=float,
        default=2.0,
        help="Alpha parameter for exponential weighting (Default: 2.0, ignored for linear weighting)",
    )
    parser.add_argument(
        "-u",
        "--unit",
        choices=["round", "tournament"],
        default="round",
        help="Calculate Elo ratings on a per-round or per-tournament basis (Default: round)",
    )
    args = parser.parse_args()
    calculator = ELOCalculator(
        k_factor=args.k_factor,
        starting_elo=args.starting_elo,
        weighting_function=args.weighting_function,
        alpha=args.alpha,
        unit=args.unit,
    )
    calculator.analyze(args.log_dir)
    calculator.print_results()
