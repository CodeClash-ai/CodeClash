#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize
from tqdm import tqdm

from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE
from codeclash.utils.log import get_logger

logger = get_logger("elo2")

# Bradley-Terry to Elo conversion constants
ELO_SLOPE = 400
ELO_BASE = 1200


class ScoreMatrixBuilder:
    def __init__(self, *, all_normalization_scheme: Literal["none", "by_game_model_pair", "by_game"] = "none"):
        self.win_matrix: dict[str, dict[tuple[str, str], list[float]]] = defaultdict(
            lambda: defaultdict(lambda: [0.0, 0.0])
        )
        self.all_normalization_scheme = all_normalization_scheme
        """game name -> (player1, player2) -> [wins, losses]"""

    def _get_unique_model_name(self, model: str) -> str:
        return model.rpartition("/")[2]

    def _get_sorted_pair(self, p1: str, p2: str) -> tuple[str, str]:
        return tuple(sorted([p1, p2]))

    def _get_score(self, stats: dict, player_names: list[str], game_name: str) -> tuple[float, float]:
        """Calculate score for a round.

        Returns (p1_score, p2_score) where each is 0.0, 0.5, or 1.0.
        """
        if stats["winner"] == RESULT_TIE:
            return (0.5, 0.5)
        if stats["winner"] == player_names[0]:
            return (1.0, 0.0)
        elif stats["winner"] == player_names[1]:
            return (0.0, 1.0)
        raise ValueError(f"Expected winner to be one of {player_names}, got {stats['winner']}")
        # player2score = stats["scores"]
        # assert len(player_names) == 2

        # Handle special case that one or more had an invalid submit
        # valid_submits = sum(
        #     [x["valid_submit"] for x in stats["player_stats"].values() if x.get("valid_submit") is not None]
        # )
        # if valid_submits == 2:
        #     return (0, 0)
        # if valid_submits == 1:
        #     if stats["winner"] == "Tie":
        #         return (0, 0)
        #     if stats["winner"] == player_names[0]:
        #         return (1, 0)
        #     else:
        #         return (0, 1)

        # print(stats)
        # print(player2score)

        # if len(player2score) != 2:
        #     raise ValueError(f"Expected 2 players, got {len(player2score)}: {player2score}")

        # p1_name, p2_name = player_names
        # if p1_name not in player2score or p2_name not in player2score:
        #     raise ValueError(f"Expected {p1_name} and {p2_name} in {player2score}")

        # # For HuskyBench and RoboCode, don't use significance testing
        # if game_name not in ["HuskyBench", "RoboCode"]:
        #     p_value = calculate_p_value(player2score)
        #     if p_value > 0.05:
        #         return (0, 0)

        # # Determine winner
        # if player2score[p1_name] > player2score[p2_name]:
        #     return (1, 0)
        # elif player2score[p2_name] > player2score[p1_name]:
        #     return (0, 1)
        # raise ValueError(f"Shouldn't get here, p value should have been > 0.05: {player2score}, {p_value}")

    def _process_tournament(self, metadata_path: Path) -> None:
        metadata = json.loads(metadata_path.read_text())

        try:
            players = metadata["config"]["players"]
            game_name = metadata["config"]["game"]["name"]
        except KeyError:
            return

        if len(players) != 2:
            return

        player_names = [p["name"] for p in players]
        models = [p["config"]["model"]["model_name"].strip("@") for p in players]

        # Process each round
        for idx, stats in metadata["round_stats"].items():
            if idx == "0":
                continue

            p1_score, p2_score = self._get_score(stats, player_names, game_name)

            # Convert to unique names and sorted pair when updating matrix
            unique_names = [self._get_unique_model_name(m) for m in models]
            sorted_pair = self._get_sorted_pair(unique_names[0], unique_names[1])

            if unique_names[0] == sorted_pair[0]:
                self.win_matrix[game_name][sorted_pair][0] += p1_score
                self.win_matrix[game_name][sorted_pair][1] += p2_score
            else:
                self.win_matrix[game_name][sorted_pair][0] += p2_score
                self.win_matrix[game_name][sorted_pair][1] += p1_score

    def build(self, log_dir: Path) -> None:
        for metadata_path in tqdm(list(log_dir.rglob("metadata.json"))):
            try:
                self._process_tournament(metadata_path)
            except Exception as e:
                logger.error(f"Error processing {metadata_path}: {e}", exc_info=True)
                continue

        self._build_combined_matrix()

    def _build_combined_matrix(self) -> None:
        """Build combined 'ALL' matrix with normalized scores from all games."""
        combined: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])

        if self.all_normalization_scheme == "none":
            # No normalization: just sum up raw scores
            for matchups in self.win_matrix.values():
                for pair, (w1, w2) in matchups.items():
                    combined[pair][0] += w1
                    combined[pair][1] += w2

        elif self.all_normalization_scheme == "by_game_model_pair":
            # Normalize each matchup by its total: wij/(wij+wji)
            for matchups in self.win_matrix.values():
                for pair, (w1, w2) in matchups.items():
                    total_pair = w1 + w2
                    if total_pair > 0:
                        combined[pair][0] += w1 / total_pair
                        combined[pair][1] += w2 / total_pair

        elif self.all_normalization_scheme == "by_game":
            # Normalize by total games in each game
            for matchups in self.win_matrix.values():
                total_games = sum(w1 + w2 for w1, w2 in matchups.values())
                if total_games > 0:
                    for pair, (w1, w2) in matchups.items():
                        combined[pair][0] += w1 / total_games
                        combined[pair][1] += w2 / total_games

        self.win_matrix["ALL"] = {k: [v[0], v[1]] for k, v in combined.items()}

    def print_matrix(self) -> None:
        for game, matchups in sorted(self.win_matrix.items()):
            print(f"\n{game}:")
            for (p1, p2), (w1, w2) in sorted(matchups.items()):
                if game == "ALL":
                    print(f"  {p1} vs {p2}: {w1:.3f}-{w2:.3f}")
                else:
                    print(f"  {p1} vs {p2}: {w1:.0f}-{w2:.0f}")


class BradleyTerryFitter:
    def __init__(self, win_matrix: dict[str, dict[tuple[str, str], list[float]]], *, regularization: float = 0.01):
        self.win_matrix = win_matrix
        self.regularization = regularization
        self.results: dict[str, dict] = {}
        """game name -> {players: list[str], strengths: np.ndarray, log_likelihood: float}"""

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-x))

    @staticmethod
    def bt_to_elo(strength: float) -> float:
        """Convert Bradley-Terry strength to Elo rating.

        Formula: R_i = R_0 + (β/ln(10)) * s_i
        where β = 400 (ELO_SLOPE), R_0 = 1200 (ELO_BASE)
        """
        return ELO_BASE + (ELO_SLOPE / np.log(10)) * strength

    def _negative_log_likelihood(self, strengths: np.ndarray, pairs: list, wins: np.ndarray) -> float:
        """Negative log-likelihood for Bradley-Terry model with L2 regularization.

        Args:
            strengths: Array of player strengths (length n_players)
            pairs: List of (i, j) player index pairs
            wins: Array of shape (n_pairs, 2) where wins[k] = [w_ij, w_ji]

        Returns:
            -log(likelihood) + λ * Σ_i s_i^2 (MAP estimate with Gaussian prior)
        """
        ll = 0.0
        for k, (i, j) in enumerate(pairs):
            diff = strengths[i] - strengths[j]
            w_ij, w_ji = wins[k]
            ll += w_ij * np.log(self._sigmoid(diff) + 1e-10)
            ll += w_ji * np.log(self._sigmoid(-diff) + 1e-10)
        # Add L2 regularization: -λΣ_i s_i^2 becomes +λΣ_i s_i^2 in the objective
        regularization_term = self.regularization * np.sum(strengths**2)
        return -ll + regularization_term

    def _fit_game(self, game_name: str, matchups: dict[tuple[str, str], list[float]]) -> dict:
        """Fit Bradley-Terry model for a single game."""
        players = sorted({p for pair in matchups.keys() for p in pair})
        n_players = len(players)
        player_to_idx = {p: i for i, p in enumerate(players)}

        pairs = []
        wins = []
        for (p1, p2), (w1, w2) in matchups.items():
            i, j = player_to_idx[p1], player_to_idx[p2]
            pairs.append((i, j))
            wins.append([w1, w2])
        wins = np.array(wins)

        # Initial guess: all strengths = 0
        s0 = np.zeros(n_players)

        # Constraint: sum of strengths = 0
        constraints = {"type": "eq", "fun": lambda s: np.sum(s)}

        result = minimize(
            self._negative_log_likelihood,
            s0,
            args=(pairs, wins),
            method="SLSQP",
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 1000},
        )

        if not result.success:
            logger.warning(f"Optimization failed for {game_name}: {result.message}")

        return {"players": players, "strengths": result.x, "log_likelihood": -result.fun}

    def fit_all(self) -> None:
        """Fit Bradley-Terry model for all games."""
        for game_name, matchups in self.win_matrix.items():
            logger.info(f"Fitting Bradley-Terry model for {game_name}")
            self.results[game_name] = self._fit_game(game_name, matchups)

    def create_elo_plots(self, output_dir: Path) -> None:
        """Create combined horizontal bar chart showing Elo ratings for all games.

        All games share the same y-axis ordered by the "ALL" game Elo ratings.

        Args:
            output_dir: Directory to save PDF plots
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get player ordering from "ALL" game
        if "ALL" not in self.results:
            logger.warning("No 'ALL' game found in results, skipping Elo plots")
            return

        all_result = self.results["ALL"]
        all_players = all_result["players"]
        all_strengths = all_result["strengths"]
        all_elos = np.array([self.bt_to_elo(s) for s in all_strengths])

        # Sort by ALL game Elo descending
        all_indices = np.argsort(all_elos)[::-1]
        player_order = [all_players[i] for i in all_indices]

        # Create mapping from player to y-position
        player_to_pos = {p: i for i, p in enumerate(player_order)}

        # Create subplots for each game
        games = sorted(self.results.keys())
        n_games = len(games)

        fig, axes = plt.subplots(1, n_games, figsize=(5 * n_games, max(8, len(player_order) * 0.5)), sharey=True)
        if n_games == 1:
            axes = [axes]

        for ax, game_name in zip(axes, games):
            result = self.results[game_name]
            players = result["players"]
            strengths = result["strengths"]

            # Convert to Elo ratings
            elos = {p: self.bt_to_elo(s) for p, s in zip(players, strengths)}

            # Create arrays aligned with player_order
            y_positions = []
            elo_values = []
            for player in player_order:
                if player in elos:
                    y_positions.append(player_to_pos[player])
                    elo_values.append(elos[player])

            # Create horizontal bar chart
            ax.barh(y_positions, elo_values, color="steelblue", edgecolor="black", linewidth=0.5)

            ax.set_xlabel("Elo Rating", fontsize=11, fontweight="bold")
            ax.set_title(game_name, fontsize=12, fontweight="bold")
            ax.grid(True, axis="x", alpha=0.3)

            # Add value labels inside bars near x=0
            for pos, elo in zip(y_positions, elo_values):
                ax.text(10, pos, f"{elo:.0f}", va="center", ha="left", fontsize=11, fontweight="bold", color="white")

            # Add reference line at ELO_BASE
            ax.axvline(ELO_BASE, color="red", linestyle="--", alpha=0.5, linewidth=1)

        # Set y-axis labels on the first subplot
        axes[0].set_yticks(range(len(player_order)))
        axes[0].set_yticklabels(player_order, fontsize=13)
        axes[0].invert_yaxis()

        plt.tight_layout()
        output_path = output_dir / "all_games_elo.pdf"
        plt.savefig(output_path, format="pdf", bbox_inches="tight")
        plt.close()
        logger.info(f"Saved combined Elo plot: {output_path}")

    def create_validation_plots(self, output_dir: Path) -> None:
        """Create validation plots showing log-likelihood profiles for each player.

        Args:
            output_dir: Directory to save PDF plots
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        for game_name, result in self.results.items():
            players = result["players"]
            strengths = result["strengths"]
            n_players = len(players)

            # Rebuild pairs and wins for this game
            player_to_idx = {p: i for i, p in enumerate(players)}
            matchups = self.win_matrix[game_name]
            pairs = []
            wins = []
            for (p1, p2), (w1, w2) in matchups.items():
                i, j = player_to_idx[p1], player_to_idx[p2]
                pairs.append((i, j))
                wins.append([w1, w2])
            wins = np.array(wins)

            # Create a plot for each player
            n_cols = min(3, n_players)
            n_rows = (n_players + n_cols - 1) // n_cols
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
            if n_players == 1:
                axes = np.array([axes])
            axes = axes.flatten()

            for idx, player in enumerate(players):
                ax = axes[idx]
                optimal_strength = strengths[idx]

                # Vary this player's strength around the optimal value
                strength_range = np.linspace(optimal_strength - 2, optimal_strength + 2, 100)
                neg_lls = []

                for s in strength_range:
                    test_strengths = strengths.copy()
                    test_strengths[idx] = s
                    # Re-normalize to maintain sum=0 constraint
                    test_strengths -= test_strengths.mean()
                    neg_ll = self._negative_log_likelihood(test_strengths, pairs, wins)
                    neg_lls.append(neg_ll)

                neg_lls = np.array(neg_lls)
                min_neg_ll = neg_lls.min()

                # Plot
                ax.plot(strength_range, neg_lls, "b-", linewidth=2)
                ax.axvline(optimal_strength, color="r", linestyle="--", label="Optimal", linewidth=2)
                ax.axhline(min_neg_ll, color="r", linestyle=":", alpha=0.5, linewidth=1)

                # Add text annotation with minimum NLL and optimal strength
                text_str = f"Min NLL: {min_neg_ll:.2f}\nBT Strength: {optimal_strength:.3f}"
                ax.text(
                    0.02,
                    0.98,
                    text_str,
                    transform=ax.transAxes,
                    verticalalignment="top",
                    fontsize=9,
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
                )

                ax.set_xlabel("BT Strength", fontsize=10)
                ax.set_ylabel("Negative Log-Likelihood", fontsize=10)
                ax.set_title(f"{player}", fontsize=11, fontweight="bold")
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)

            # Hide unused subplots
            for idx in range(n_players, len(axes)):
                axes[idx].set_visible(False)

            plt.tight_layout()
            safe_game_name = game_name.replace("/", "_").replace(" ", "_")
            output_path = output_dir / f"{safe_game_name}_validation.pdf"
            plt.savefig(output_path, format="pdf", bbox_inches="tight")
            plt.close()
            logger.info(f"Saved validation plot: {output_path}")

    def print_results(self, *, all_normalization_scheme: str = "none") -> None:
        """Print fitted strengths and Elo ratings."""
        print(f"Regularization λ = {self.regularization}")
        print(f"ALL game normalization: {all_normalization_scheme}")
        print(f"Elo conversion: R = {ELO_BASE} + ({ELO_SLOPE}/ln(10)) * s")
        for game_name, result in sorted(self.results.items()):
            print(f"\n{game_name}:")
            print(f"Log-likelihood: {result['log_likelihood']:.2f}")
            print(f"\n{'Player':<30s} {'BT Strength':>12s} {'Elo':>8s}")
            print("-" * 52)

            # Sort by strength descending
            indices = np.argsort(result["strengths"])[::-1]
            for idx in indices:
                player = result["players"][idx]
                strength = result["strengths"][idx]
                elo = self.bt_to_elo(strength)
                print(f"  {player:<30s} {strength:12.3f} {elo:8.0f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build win matrix and fit Bradley-Terry model")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR)
    parser.add_argument("--print-matrix", action="store_true", help="Print win matrix")
    parser.add_argument(
        "-l",
        "--lambda",
        dest="regularization",
        type=float,
        default=0.01,
        help="L2 regularization strength (default: 0.01)",
    )
    parser.add_argument(
        "--ars",
        dest="all_normalization_scheme",
        choices=["none", "by_game_model_pair", "by_game"],
        default="none",
        help="ALL game normalization scheme: 'none' (no normalization), 'by_game_model_pair' (normalize by pair total), 'by_game' (normalize by game total) (default: none)",
    )
    parser.add_argument(
        "--validation-plots", action="store_true", help="Create validation plots showing likelihood profiles"
    )
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=Path("elo2_validation_plots"),
        help="Directory to save validation plots (default: elo2_validation_plots)",
    )
    parser.add_argument("--elo-plot", action="store_true", help="Create horizontal bar charts showing Elo ratings")
    parser.add_argument(
        "--elo-plot-dir",
        type=Path,
        default=Path("elo2_plots"),
        help="Directory to save Elo plots (default: elo2_plots)",
    )
    args = parser.parse_args()

    builder = ScoreMatrixBuilder(all_normalization_scheme=args.all_normalization_scheme)
    builder.build(args.log_dir)

    if args.print_matrix:
        builder.print_matrix()

    fitter = BradleyTerryFitter(builder.win_matrix, regularization=args.regularization)
    fitter.fit_all()
    fitter.print_results(all_normalization_scheme=args.all_normalization_scheme)

    if args.validation_plots:
        fitter.create_validation_plots(args.validation_dir)

    if args.elo_plot:
        fitter.create_elo_plots(args.elo_plot_dir)
