#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal, TypeAlias, get_args

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize
from tqdm import tqdm

from codeclash.analysis.metrics.elo import get_scores
from codeclash.analysis.significance import calculate_p_value
from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE
from codeclash.utils.log import get_logger

logger = get_logger("elo2")

# Bradley-Terry to Elo conversion constants
ELO_SLOPE = 400
ELO_BASE = 1200


SCORING_TYPES: TypeAlias = Literal[
    "per_round_tertiary", "per_round_float", "per_round_tertiary_p_value", "per_tournament_boolean_drop_draws"
]

ALL_GAMES_NORMALIZATION_SCHEMES: TypeAlias = Literal["none", "by_game_model_pair", "by_game"]


class ScoreMatrixBuilder:
    def __init__(
        self,
        *,
        all_games_normalization_scheme: ALL_GAMES_NORMALIZATION_SCHEMES = "none",
        score_type: SCORING_TYPES = "per_round_tertiary",
    ):
        """This class builds a win matrix from a log directory, it doesn't fit anything yet.
        It also adds a "ALL" game to the win matrix, which is the sum of all games.
        There are different choices for normalize the "ALL" game, which is controlled by the all_normalization_scheme parameter.

        The possible values are:
        - "none": No normalization, just sum up raw scores
        - "by_game_model_pair": Normalize each matchup by its total: wij/(wij+wji)/total_games  (NOTE: can't calculate uncertainties for this)
        - "by_game": Normalize by total games in each game  (NOTE: can't calculate uncertainties for this)

        The `score_type` parameter controls how the score is calculated for each round. The possible values are:
        - "per_round_tertiary": Returns 0.0, 0.5, or 1.0 for the score of each player for each round,
            depending on the "winner" field in the stats dictionary.
        - "per_round_float": The "float" score type returns the scores based on performance over sims
        - "per_round_tertiary_p_value": The "tertiary_p_value" score type returns 0.0, 0.5, or 1.0 for the score of each player,
            similar to the "tertiary" score type, but if the p-value is greater than 0.05, it concludes
            a draw.
        - "per_tournament_boolean_drop_draws": The "boolean_drop_draws" score type returns 0.0 or 1.0 for the score of each player,
            depending on the "winner" field in the stats dictionary. This is the only score type that gives proper uncertainties for the win matrix.
        """
        self.win_matrix: dict[str, dict[tuple[str, str], list[float]]] = defaultdict(
            lambda: defaultdict(lambda: [0.0, 0.0])
        )
        """game name -> (player1, player2) -> [wins, losses]"""
        self.all_normalization_scheme = all_games_normalization_scheme
        self.score_type = score_type
        self._samples: dict[str, dict[tuple[str, str], list[tuple[float, float]]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def _get_unique_model_name(self, model: str) -> str:
        return model.rpartition("/")[2]

    def _get_sorted_pair(self, p1: str, p2: str) -> tuple[str, str]:
        return tuple(sorted([p1, p2]))

    def _get_round_score(self, stats: dict, player_names: list[str], game_name: str) -> tuple[float, float]:
        """Calculate score for a round.

        Returns (p1_score, p2_score) where each is 0.0, 0.5, or 1.0.
        """
        if self.score_type == "float":
            scores = get_scores(stats)
            if len(stats["scores"]) == 1 and stats["scores"][RESULT_TIE] > 0:
                return (0.5, 0.5)
            # print(stats)
            return (scores[player_names[0]], scores[player_names[1]])
        elif self.score_type in ["per_round_tertiary", "per_tournament_boolean_drop_draws"]:
            if stats["winner"] == RESULT_TIE:
                if self.score_type == "per_tournament_boolean_drop_draws":
                    return (0.0, 0.0)
                return (0.5, 0.5)
            if stats["winner"] == player_names[0]:
                return (1.0, 0.0)
            elif stats["winner"] == player_names[1]:
                return (0.0, 1.0)
            raise ValueError(f"Expected winner to be one of {player_names}, got {stats['winner']}")
        elif self.score_type == "per_round_tertiary_p_value":
            player2score = stats["scores"]
            assert len(player_names) == 2

            # Handle special case that one or more had an invalid submit
            valid_submits = sum(
                [x["valid_submit"] for x in stats["player_stats"].values() if x.get("valid_submit") is not None]
            )
            if valid_submits == 0:
                return (0.5, 0.5)
            if valid_submits == 1:
                if stats["winner"] == RESULT_TIE:
                    return (0.5, 0.5)
                if stats["winner"] == player_names[0]:
                    return (1.0, 0.0)
                else:
                    return (0.0, 1.0)

            # if len(player2score) != 2:
            #     raise ValueError(f"Expected 2 players, got {len(player2score)}: {player2score}")

            p1_name, p2_name = player_names
            if p1_name not in player2score or p2_name not in player2score:
                raise ValueError(f"Expected {p1_name} and {p2_name} in {player2score}")

            # For HuskyBench and RoboCode, don't use significance testing
            if game_name not in ["HuskyBench", "RoboCode"]:
                p_value = calculate_p_value(player2score)
                if p_value > 0.05:
                    return (0.5, 0.5)

            # Determine winner
            if player2score[p1_name] > player2score[p2_name]:
                return (1.0, 0.0)
            elif player2score[p2_name] > player2score[p1_name]:
                return (0.0, 1.0)
            return (0.5, 0.5)
        raise ValueError(f"Invalid round score type: {self.score_type}")

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

        # Aggregate scores for each round
        p1_round_score = 0
        p2_round_score = 0
        for idx, stats in metadata["round_stats"].items():
            if idx == "0":
                continue

            _p1_score, _p2_score = self._get_round_score(stats, player_names, game_name)
            p1_round_score += _p1_score
            p2_round_score += _p2_score

        # If we're scoring per tournament, we need to convert the round scores to a tournament score
        p1_score = p1_round_score
        p2_score = p2_round_score
        if self.score_type == "per_tournament_boolean_drop_draws":
            if p1_round_score == p2_round_score:
                p1_score, p2_score = 0.0, 0.0
            if p1_round_score > p2_round_score:
                p1_score, p2_score = 1.0, 0.0
            else:
                p1_score, p2_score = 0.0, 1.0

        # Convert to unique names and sorted pair when updating matrix
        unique_names = [self._get_unique_model_name(m) for m in models]
        sorted_pair = self._get_sorted_pair(unique_names[0], unique_names[1])

        if unique_names[0] == sorted_pair[0]:
            self.win_matrix[game_name][sorted_pair][0] += p1_score
            self.win_matrix[game_name][sorted_pair][1] += p2_score
            self._samples[game_name][sorted_pair].append((p1_score, p2_score))
        else:
            self.win_matrix[game_name][sorted_pair][0] += p2_score
            self.win_matrix[game_name][sorted_pair][1] += p1_score
            self._samples[game_name][sorted_pair].append((p2_score, p1_score))

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
                total_games = sum(w1 + w2 for w1, w2 in matchups.values())
                if total_games > 0:
                    for pair, (w1, w2) in matchups.items():
                        total_pair = w1 + w2
                        if total_pair > 0:
                            combined[pair][0] += w1 / total_pair / total_games
                            combined[pair][1] += w2 / total_pair / total_games

        elif self.all_normalization_scheme == "by_game":
            # Normalize by total games in each game
            for matchups in self.win_matrix.values():
                total_games = sum(w1 + w2 for w1, w2 in matchups.values())
                if total_games > 0:
                    for pair, (w1, w2) in matchups.items():
                        combined[pair][0] += w1 / total_games
                        combined[pair][1] += w2 / total_games

        self.win_matrix["ALL"] = {k: [v[0], v[1]] for k, v in combined.items()}

    def get_nonparametric_bootstrap(
        self, *, rng: np.random.Generator | None = None
    ) -> dict[str, dict[tuple[str, str], list[float]]]:
        """Return a bootstrap-resampled win matrix with the same format as win_matrix.

        Sampling is done with replacement over per-tournament contributions for each (game, pair).
        """
        if self.all_normalization_scheme != "none":
            raise NotImplementedError("get_nonparametric_bootstrap supports all_normalization_scheme='none' only")
        if rng is None:
            rng = np.random.default_rng()

        boot_matrix: dict[str, dict[tuple[str, str], list[float]]] = defaultdict(
            lambda: defaultdict(lambda: [0.0, 0.0])
        )

        for game_name, matchups in self._samples.items():
            for pair, samples in matchups.items():
                n = len(samples)
                if n == 0:
                    continue
                indices = rng.integers(0, n, size=n)
                w1 = 0.0
                w2 = 0.0
                for idx in indices:
                    s1, s2 = samples[int(idx)]
                    w1 += s1
                    w2 += s2
                boot_matrix[game_name][pair] = [w1, w2]

        # Build combined 'ALL' game by summing, same as other games
        combined: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
        for matchups in boot_matrix.values():
            for pair, (w1, w2) in matchups.items():
                combined[pair][0] += w1
                combined[pair][1] += w2

        boot_matrix["ALL"] = {k: [v[0], v[1]] for k, v in combined.items()}
        return boot_matrix

    def print_matrix(self) -> None:
        for game, matchups in sorted(self.win_matrix.items()):
            print(f"\n{game}:")
            for (p1, p2), (w1, w2) in sorted(matchups.items()):
                if game == "ALL":
                    print(f"  {p1} vs {p2}: {w1:.3f}-{w2:.3f}")
                else:
                    print(f"  {p1} vs {p2}: {w1:.0f}-{w2:.0f}")


class BradleyTerryFitter:
    def __init__(
        self,
        win_matrix: dict[str, dict[tuple[str, str], list[float]]],
        *,
        regularization: float = 0.01,
        compute_uncertainties: bool = True,
    ):
        self.win_matrix = win_matrix
        self.regularization = regularization
        self.compute_uncertainties = compute_uncertainties
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
        assert len(wins) == len(pairs)
        ll = 0.0
        for k, (i, j) in enumerate(pairs):
            diff = strengths[i] - strengths[j]
            w_ij, w_ji = wins[k]
            ll += w_ij * np.log(self._sigmoid(diff) + 1e-10)
            ll += w_ji * np.log(self._sigmoid(-diff) + 1e-10)
        # Add L2 regularization: -λΣ_i s_i^2 becomes +λΣ_i s_i^2 in the objective
        regularization_term = self.regularization * np.sum(strengths**2)
        return -ll + regularization_term

    def _hessian(self, strengths: np.ndarray, pairs: list[tuple[int, int]], wins: np.ndarray) -> np.ndarray:
        n = strengths.shape[0]
        H = np.zeros((n, n))
        for k, (i, j) in enumerate(pairs):
            diff = strengths[i] - strengths[j]
            p = self._sigmoid(diff)
            w_ij, w_ji = wins[k]
            w = (w_ij + w_ji) * p * (1 - p)
            if w == 0:
                continue
            H[i, i] += w
            H[j, j] += w
            H[i, j] -= w
            H[j, i] -= w
        # L2 regularization Hessian
        H += 2 * self.regularization * np.eye(n)
        return H

    def _constrained_covariance(self, H: np.ndarray) -> np.ndarray:
        n = H.shape[0]
        if n == 1:
            return np.array([[1.0 / H[0, 0]]])
        # Basis Z for subspace sum(s)=0: columns e_k - e_n, k=0..n-2
        Z = np.zeros((n, n - 1))
        for k in range(n - 1):
            Z[k, k] = 1.0
            Z[n - 1, k] = -1.0
        Hr = Z.T @ H @ Z
        Hr_inv = np.linalg.pinv(Hr)
        return Z @ Hr_inv @ Z.T

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

        # HUMAN COMMENT, DO NOT ERASE
        # Constraint: sum of strengths = 0
        # This is because the win probabilities only depend on differences,
        # so we could add a constant A to all strengths without changing the win probabilities.
        # Therefore we need to make a normalization choice here.
        # There are different choices for the normalization, and they DO change the Elo ratings
        # by adding a constant to all strengths.
        # However, Elo ratings also are only meaningful up to an additive constant, so it doesn't
        # matter which we choose.
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

        strengths = result.x
        out = {
            "players": players,
            "strengths": strengths,
            "log_likelihood": -result.fun,
        }
        if self.compute_uncertainties:
            H = self._hessian(strengths, pairs, wins)
            cov = self._constrained_covariance(H)
            scale = ELO_SLOPE / np.log(10)
            elo_std = scale * np.sqrt(np.clip(np.diag(cov), 0.0, np.inf))
            out["covariance"] = cov
            out["elo_std"] = elo_std
        return out

    def fit_all(self) -> None:
        """Fit Bradley-Terry model for all games."""
        for game_name, matchups in self.win_matrix.items():
            logger.info(f"Fitting Bradley-Terry model for {game_name}")
            self.results[game_name] = self._fit_game(game_name, matchups)

    def print_results(self) -> None:
        """Print fitted strengths and Elo ratings."""
        print(f"Regularization λ = {self.regularization}")
        print(f"Elo conversion: R = {ELO_BASE} + ({ELO_SLOPE}/ln(10)) * s")
        for game_name, result in sorted(self.results.items()):
            print(f"\n{game_name}:")
            print(f"Log-likelihood: {result['log_likelihood']:.2f}")
            has_sigma = "elo_std" in result
            if has_sigma:
                print(f"\n{'Player':<30s} {'BT Strength':>12s} {'Elo':>8s} {'±1σ':>8s}")
                print("-" * 62)
            else:
                print(f"\n{'Player':<30s} {'BT Strength':>12s} {'Elo':>8s}")
                print("-" * 52)

            # Sort by strength descending
            indices = np.argsort(result["strengths"])[::-1]
            for idx in indices:
                player = result["players"][idx]
                strength = result["strengths"][idx]
                elo = self.bt_to_elo(strength)
                sigma = result.get("elo_std")
                if sigma is not None:
                    s = sigma[idx]
                    print(f"  {player:<30s} {strength:12.3f} {elo:8.0f} {s:8.0f}")
                else:
                    print(f"  {player:<30s} {strength:12.3f} {elo:8.0f}")


class BradleyTerryFitterPlots:
    def __init__(self, fitter: BradleyTerryFitter):
        self.fitter = fitter

    def create_elo_plots(self, output_dir: Path) -> None:
        """Create combined horizontal bar chart showing Elo ratings for all games.

        All games share the same y-axis ordered by the "ALL" game Elo ratings.

        Args:
            output_dir: Directory to save PDF plots
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get player ordering from "ALL" game
        if "ALL" not in self.fitter.results:
            logger.warning("No 'ALL' game found in results, skipping Elo plots")
            return

        all_result = self.fitter.results["ALL"]
        all_players = all_result["players"]
        all_strengths = all_result["strengths"]
        all_elos = np.array([self.fitter.bt_to_elo(s) for s in all_strengths])

        # Sort by ALL game Elo descending
        all_indices = np.argsort(all_elos)[::-1]
        player_order = [all_players[i] for i in all_indices]

        # Create mapping from player to y-position
        player_to_pos = {p: i for i, p in enumerate(player_order)}

        # Create subplots for each game
        games = sorted(self.fitter.results.keys())
        n_games = len(games)

        fig, axes = plt.subplots(1, n_games, figsize=(5 * n_games, max(8, len(player_order) * 0.5)), sharey=True)
        if n_games == 1:
            axes = [axes]

        for ax, game_name in zip(axes, games):
            result = self.fitter.results[game_name]
            players = result["players"]
            strengths = result["strengths"]
            sigma = result.get("elo_std")

            # Convert to Elo ratings
            elos = {p: self.fitter.bt_to_elo(s) for p, s in zip(players, strengths)}

            # Create arrays aligned with player_order
            y_positions = []
            elo_values = []
            sigma_values = []
            for player in player_order:
                if player in elos:
                    y_positions.append(player_to_pos[player])
                    elo_values.append(elos[player])
                    if sigma is not None:
                        # Map player's index in this game's ordering to σ
                        idx = players.index(player)
                        sigma_values.append(float(sigma[idx]))
                    else:
                        sigma_values.append(0.0)

            # Create horizontal bar chart
            ax.barh(y_positions, elo_values, color="steelblue", edgecolor="black", linewidth=0.5)
            # Add horizontal error indicators (±1σ) at the end of bars
            if any(v > 0 for v in sigma_values):
                ax.errorbar(
                    elo_values,
                    y_positions,
                    xerr=sigma_values,
                    fmt="none",
                    ecolor="black",
                    elinewidth=1.0,
                    capsize=0,
                    zorder=3,
                )

            ax.set_xlabel("Elo Rating", fontsize=11, fontweight="bold")
            ax.set_title(game_name, fontsize=14, fontweight="bold")
            ax.grid(True, axis="x", alpha=0.3)

            # Add value labels inside bars near x=0, include ±1σ when available
            has_sigma = any(v > 0 for v in sigma_values)
            for pos, elo, sig in zip(y_positions, elo_values, sigma_values):
                label = f"{elo:.0f}"
                if has_sigma and sig > 0:
                    label = f"{elo:.0f} ± {sig:.0f}"
                ax.text(20, pos, label, va="center", ha="left", fontsize=13, fontweight="bold", color="white")

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

        for game_name, result in self.fitter.results.items():
            players = result["players"]
            strengths = result["strengths"]
            n_players = len(players)

            # Rebuild pairs and wins for this game
            player_to_idx = {p: i for i, p in enumerate(players)}
            matchups = self.fitter.win_matrix[game_name]
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
                    neg_ll = self.fitter._negative_log_likelihood(test_strengths, pairs, wins)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build win matrix and fit Bradley-Terry model")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR)
    parser.add_argument("--print-matrix", action="store_true", help="Print win matrix")
    parser.add_argument(
        "-s",
        "--score-type",
        choices=get_args(SCORING_TYPES),
        default="per_tournament_boolean_drop_draws",
        help="See ScoreMatrixBuilder for possible values",
    )
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
        choices=get_args(ALL_GAMES_NORMALIZATION_SCHEMES),
        default="none",
        help="See ScoreMatrixBuilder for possible values",
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

    builder = ScoreMatrixBuilder(
        all_games_normalization_scheme=args.all_normalization_scheme, score_type=args.score_type
    )
    builder.build(args.log_dir)

    if args.print_matrix:
        builder.print_matrix()

    compute_uncertainties = (
        args.score_type == "per_tournament_boolean_drop_draws" and args.all_normalization_scheme == "none"
    )
    fitter = BradleyTerryFitter(
        builder.win_matrix,
        regularization=args.regularization,
        compute_uncertainties=compute_uncertainties,
    )
    fitter.fit_all()
    fitter.print_results()

    if args.validation_plots or args.elo_plot:
        plotter = BradleyTerryFitterPlots(fitter)
        if args.validation_plots:
            plotter.create_validation_plots(args.validation_dir)
        if args.elo_plot:
            plotter.create_elo_plots(args.elo_plot_dir)
