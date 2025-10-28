#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal, TypeAlias, get_args

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import AutoMinorLocator
from scipy.optimize import minimize
from scipy.stats import kendalltau, spearmanr
from tqdm import tqdm

from codeclash.analysis.metrics.elo_broken import get_scores
from codeclash.analysis.significance import calculate_p_value
from codeclash.analysis.viz.utils import FONT_BOLD, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE
from codeclash.utils.log import add_file_handler, get_logger

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
        max_round: int = 15,
        only_specific_round: bool = False,
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

        The `max_round` parameter controls the maximum number of rounds to include in the score calculation (default: 15).
        The `only_specific_round` parameter controls whether to only include the specific round (True) or all rounds up to max_round (False).
        """
        self.win_matrix: dict[str, dict[tuple[str, str], list[float]]] = defaultdict(
            lambda: defaultdict(lambda: [0.0, 0.0])
        )
        """game name -> (player1, player2) -> [wins, losses]"""
        self.all_normalization_scheme = all_games_normalization_scheme
        self.score_type = score_type
        self.max_round = max_round
        self.only_specific_round = only_specific_round
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
        p1_round_scores = []
        p2_round_scores = []
        for idx, stats in metadata["round_stats"].items():
            if idx == "0":
                continue

            round_num = int(idx)
            if self.only_specific_round:
                if round_num != self.max_round:
                    continue
            else:
                if round_num > self.max_round:
                    continue

            _p1_score, _p2_score = self._get_round_score(stats, player_names, game_name)
            p1_round_scores.append(_p1_score)
            p2_round_scores.append(_p2_score)

        # If we're scoring per tournament, we need to convert the round scores to a tournament score
        if self.score_type == "per_tournament_boolean_drop_draws":
            if sum(p1_round_scores) == sum(p2_round_scores):
                # Check for the last round that was not a tie
                logger.debug(f"Tie in tournament {metadata_path}")
                for i in range(len(p1_round_scores) - 1, -1, -1):
                    if p1_round_scores[i] > p2_round_scores[i]:
                        p1_score, p2_score = 1.0, 0.0
                        break
                    if p1_round_scores[i] < p2_round_scores[i]:
                        p1_score, p2_score = 0.0, 1.0
                        break
                else:
                    logger.warning(f"Tie in tournament {metadata_path} could not be broken, skipping tournament.")
                    p1_score, p2_score = 0.0, 0.0
            elif sum(p1_round_scores) > sum(p2_round_scores):
                p1_score, p2_score = 1.0, 0.0
            else:
                p1_score, p2_score = 0.0, 1.0
        else:
            p1_score = sum(p1_round_scores)
            p2_score = sum(p2_round_scores)

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
        if self.score_type != "per_tournament_boolean_drop_draws":
            raise NotImplementedError(
                "get_nonparametric_bootstrap supports score_type='per_tournament_boolean_drop_draws' only"
            )
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
        win_matrix: dict[tuple[str, str], list[float]],
        *,
        regularization: float = 0.01,
        compute_uncertainties: bool = True,
    ):
        """Fit Bradley-Terry model to a win matrix

        Args:
            win_matrix: Dictionary mapping player pairs to win counts
            regularization: L2 regularization strength
            compute_uncertainties: Whether to compute uncertainties
        """
        self.matchups = win_matrix
        self.regularization = regularization
        self.compute_uncertainties = compute_uncertainties
        self.result: dict | None = None
        """{players: list[str], strengths: np.ndarray, log_likelihood: float}"""

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

    def fit(self) -> dict:
        """Fit Bradley-Terry model."""
        players = sorted({p for pair in self.matchups.keys() for p in pair})
        n_players = len(players)
        player_to_idx = {p: i for i, p in enumerate(players)}

        pairs = []
        wins = []
        for (p1, p2), (w1, w2) in self.matchups.items():
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
        self.result = out
        return out

    def get_parametric_bootstrap(self, *, rng: np.random.Generator | None = None) -> dict[tuple[str, str], list[float]]:
        """Return a parametric bootstrap sample based on the fitted Bradley-Terry model.

        Uses the fitted strengths to compute win probabilities P(i beats j) = sigmoid(s_i - s_j),
        then samples new win counts from binomial distributions with those probabilities.
        This is a true parametric bootstrap, unlike a semi-parametric approach that uses empirical win rates.
        """
        if self.result is None:
            raise RuntimeError("Must call fit() before get_parametric_bootstrap()")
        if rng is None:
            rng = np.random.default_rng()

        players = self.result["players"]
        strengths = self.result["strengths"]
        player_to_idx = {p: i for i, p in enumerate(players)}

        boot_matrix: dict[tuple[str, str], list[float]] = {}

        for pair, (w1, w2) in self.matchups.items():
            n = int(w1 + w2)
            if n == 0:
                boot_matrix[pair] = [0.0, 0.0]
                continue

            p1, p2 = pair
            i, j = player_to_idx[p1], player_to_idx[p2]
            diff = strengths[i] - strengths[j]
            p = self._sigmoid(diff)

            w1_new = float(rng.binomial(n, p))
            w2_new = float(n - w1_new)
            boot_matrix[pair] = [w1_new, w2_new]

        return boot_matrix


class BradleyTerryFitterPlots:
    def __init__(self, results: dict[str, dict], win_matrix: dict[str, dict[tuple[str, str], list[float]]]):
        self.results = results
        self.win_matrix = win_matrix

    @staticmethod
    def _save_plot(output_dir: Path, filename_base: str) -> None:
        """Save plot in both PDF and PNG formats."""
        for fmt in ["pdf", "png"]:
            output_path = output_dir / f"{filename_base}.{fmt}"
            plt.savefig(output_path, format=fmt, bbox_inches="tight", dpi=300 if fmt == "png" else None)
            logger.info(f"Saved plot: {output_path}")

    @staticmethod
    def bt_to_elo(strength: float) -> float:
        """Convert Bradley-Terry strength to Elo rating.

        Formula: R_i = R_0 + (β/ln(10)) * s_i
        where β = 400 (ELO_SLOPE), R_0 = 1200 (ELO_BASE)
        """
        return ELO_BASE + (ELO_SLOPE / np.log(10)) * strength

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-x))

    def _negative_log_likelihood(
        self, strengths: np.ndarray, pairs: list, wins: np.ndarray, regularization: float
    ) -> float:
        """Negative log-likelihood for Bradley-Terry model with L2 regularization."""
        assert len(wins) == len(pairs)
        ll = 0.0
        for k, (i, j) in enumerate(pairs):
            diff = strengths[i] - strengths[j]
            w_ij, w_ji = wins[k]
            ll += w_ij * np.log(self._sigmoid(diff) + 1e-10)
            ll += w_ji * np.log(self._sigmoid(-diff) + 1e-10)
        regularization_term = regularization * np.sum(strengths**2)
        return -ll + regularization_term

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

        # Translate to display names
        display_names = [MODEL_TO_DISPLAY_NAME.get(p, p) for p in player_order]

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
            sigma = result.get("elo_std")

            # Convert to Elo ratings
            elos = {p: self.bt_to_elo(s) for p, s in zip(players, strengths)}

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

            ax.set_xlabel("Elo Rating", fontproperties=FONT_BOLD, fontsize=14)
            ax.set_title(game_name, fontproperties=FONT_BOLD, fontsize=16)
            ax.grid(True, axis="x", alpha=0.3)

            # Add value labels inside bars near x=0, include ±1σ when available
            has_sigma = any(v > 0 for v in sigma_values)
            for pos, elo, sig in zip(y_positions, elo_values, sigma_values):
                label = f"{elo:.0f}"
                if has_sigma and sig > 0:
                    label = f"{elo:.0f} ± {sig:.0f}"
                ax.text(20, pos, label, va="center", ha="left", fontproperties=FONT_BOLD, fontsize=14, color="white")

            # Add reference line at ELO_BASE
            ax.axvline(ELO_BASE, color="red", linestyle="--", alpha=0.5, linewidth=1)

        # Set y-axis labels on the first subplot
        axes[0].set_yticks(range(len(player_order)))
        axes[0].set_yticklabels(display_names, fontproperties=FONT_BOLD, fontsize=14)
        axes[0].invert_yaxis()

        plt.tight_layout()
        self._save_plot(output_dir, "all_games_elo")
        plt.close()

    def create_validation_plots(self, output_dir: Path, regularization: float = 0.01) -> None:
        """Create validation plots showing log-likelihood profiles for each player.

        Args:
            output_dir: Directory to save PDF plots
            regularization: L2 regularization strength used in fitting
        """
        output_dir = output_dir / "fit_validation"
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
                    neg_ll = self._negative_log_likelihood(test_strengths, pairs, wins, regularization)
                    neg_lls.append(neg_ll)

                neg_lls = np.array(neg_lls)
                min_neg_ll = neg_lls.min()

                # Plot
                ax.plot(strength_range, neg_lls, "b-", linewidth=2)
                ax.axvline(optimal_strength, color="r", linestyle="--", label="Optimal", linewidth=2)
                ax.axhline(min_neg_ll, color="r", linestyle=":", alpha=0.5, linewidth=1, label="Min NLL")

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

                ax.set_xlabel("BT Strength", fontproperties=FONT_BOLD, fontsize=12)
                ax.set_ylabel("Negative Log-Likelihood", fontproperties=FONT_BOLD, fontsize=12)
                display_name = MODEL_TO_DISPLAY_NAME.get(player, player)
                ax.set_title(display_name, fontproperties=FONT_BOLD, fontsize=14)
                legend = ax.legend(prop=FONT_BOLD, fontsize=10, loc="upper right")
                legend.set_frame_on(False)
                ax.grid(True, alpha=0.3)

            # Hide unused subplots
            for idx in range(n_players, len(axes)):
                axes[idx].set_visible(False)

            plt.tight_layout()
            safe_game_name = game_name.replace("/", "_").replace(" ", "_")
            self._save_plot(output_dir, f"{safe_game_name}_validation")
            plt.close()


class BootStrapRankStability:
    def __init__(
        self,
        builder: ScoreMatrixBuilder,
        *,
        n_bootstrap: int = 1000,
        game: str = "ALL",
        regularization: float = 0.01,
        topks: list[int] | None = None,
        bootstrap_type: Literal["nonparametric", "parametric"] = "nonparametric",
        output_dir: Path | None = None,
    ):
        self.builder = builder
        self.n_bootstrap = n_bootstrap
        self.game = game
        self.regularization = regularization
        self.topks = topks
        self.bootstrap_type = bootstrap_type
        self.output_dir = output_dir

    @staticmethod
    def _save_plot(output_dir: Path, filename_base: str) -> None:
        """Save plot in both PDF and PNG formats."""
        for fmt in ["pdf", "png"]:
            output_path = output_dir / f"{filename_base}.{fmt}"
            plt.savefig(output_path, format=fmt, bbox_inches="tight", dpi=300 if fmt == "png" else None)
            logger.info(f"Saved plot: {output_path}")

    @staticmethod
    def _elos_from_result(result: dict) -> dict[str, float]:
        return {p: BradleyTerryFitter.bt_to_elo(s) for p, s in zip(result["players"], result["strengths"])}

    @staticmethod
    def _ranking_from_elos(elos: dict[str, float]) -> list[str]:
        return [p for p, _ in sorted(elos.items(), key=lambda kv: kv[1], reverse=True)]

    @staticmethod
    def _positions(ranking: list[str]) -> dict[str, int]:
        return {p: i for i, p in enumerate(ranking)}

    @staticmethod
    def _max_footrule(n: int) -> float:
        return (n * n) / 2 if n % 2 == 0 else (n * n - 1) / 2

    def _fit_on_matrix(self, matchups: dict[tuple[str, str], list[float]]) -> dict:
        fitter = BradleyTerryFitter(matchups, regularization=self.regularization, compute_uncertainties=False)
        return fitter.fit()

    def _create_rank_matrix_plot(
        self, players: list[str], rank_samples: dict[str, list[int]], output_dir: Path
    ) -> None:
        """Create a matrix plot showing the percentage of times each model achieves each rank."""
        n = len(players)
        rank_matrix = np.zeros((n, n))

        for model_idx, model in enumerate(players):
            ranks = rank_samples[model]
            for rank in ranks:
                rank_matrix[rank - 1, model_idx] += 1

        rank_matrix = (rank_matrix / self.n_bootstrap) * 100

        # Translate player names to display names
        display_names = [MODEL_TO_DISPLAY_NAME.get(p, p) for p in players]

        fig, ax = plt.subplots(figsize=(6, 6))
        im = ax.imshow(rank_matrix, cmap="YlOrRd", aspect="auto", vmin=0, vmax=100)

        ax.set_xticks(range(n))
        ax.set_xticklabels(display_names, rotation=45, ha="right", fontproperties=FONT_BOLD, fontsize=10)
        ax.set_yticks(range(n))
        ax.set_yticklabels([f"Rank {i + 1}" for i in range(n)], fontproperties=FONT_BOLD, fontsize=10)
        ax.yaxis.set_minor_locator(AutoMinorLocator())

        ax.set_xlabel("Model", fontproperties=FONT_BOLD, fontsize=12)
        ax.set_ylabel("Rank", fontproperties=FONT_BOLD, fontsize=12)
        ax.set_title(
            f"Rank Distribution ({self.bootstrap_type} bootstrap, {self.n_bootstrap} samples)",
            fontproperties=FONT_BOLD,
            fontsize=14,
        )

        for i in range(n):
            for j in range(n):
                value = rank_matrix[i, j]
                if value > 0:
                    text_color = "white" if value > 50 else "black"
                    ax.text(
                        j,
                        i,
                        f"{value:.1f}%",
                        ha="center",
                        va="center",
                        color=text_color,
                        fontproperties=FONT_BOLD,
                        fontsize=12,
                    )

        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label("Percentage (%)", fontproperties=FONT_BOLD, fontsize=14)

        plt.tight_layout()
        self._save_plot(output_dir, f"{self.game}_rank_matrix_{self.bootstrap_type}")
        plt.close()

    def _create_elo_violin_plot(
        self, players: list[str], elo_samples: dict[str, list[float]], baseline_elos: dict[str, float], output_dir: Path
    ) -> None:
        """Create a violin plot showing the distribution of Elo scores for each model."""
        elo_data = [elo_samples[p] for p in players]

        # Translate player names to display names
        display_names = [MODEL_TO_DISPLAY_NAME.get(p, p) for p in players]

        fig, ax = plt.subplots(figsize=(6, 6))

        parts = ax.violinplot(elo_data, positions=range(len(players)), showmeans=False, showmedians=False, widths=0.7)

        for pc in parts["bodies"]:
            pc.set_facecolor("steelblue")
            pc.set_alpha(0.7)
            pc.set_edgecolor("black")
            pc.set_linewidth(1)

        for partname in ("cbars", "cmins", "cmaxes"):
            if partname in parts:
                parts[partname].set_edgecolor("black")
                parts[partname].set_linewidth(1)

        baseline_vals = [baseline_elos[p] for p in players]
        ax.scatter(
            range(len(players)),
            baseline_vals,
            color="red",
            s=100,
            zorder=3,
            marker="D",
            label="Baseline Elo",
            edgecolors="black",
            linewidths=1,
        )

        ax.set_xticks(range(len(players)))
        ax.set_xticklabels(display_names, rotation=45, ha="right", fontproperties=FONT_BOLD, fontsize=12)
        ax.set_ylabel("Elo Rating", fontproperties=FONT_BOLD, fontsize=14)
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.set_title(
            f"Elo Distribution ({self.bootstrap_type} bootstrap, {self.n_bootstrap} samples)",
            fontproperties=FONT_BOLD,
            fontsize=16,
        )
        ax.grid(True, axis="y", alpha=0.3)
        legend = ax.legend(prop=FONT_BOLD, fontsize=12)
        legend.set_frame_on(False)

        plt.tight_layout()
        self._save_plot(output_dir, f"{self.game}_elo_violin_{self.bootstrap_type}")
        plt.close()

    def run(self) -> None:
        game = self.game
        assert game in self.builder.win_matrix, f"Game '{game}' not found in win matrix"

        baseline_res = self._fit_on_matrix(self.builder.win_matrix[game])
        baseline_elos = self._elos_from_result(baseline_res)
        baseline_ranking = self._ranking_from_elos(baseline_elos)
        players = baseline_ranking
        n = len(players)
        topks = list(range(1, n + 1)) if self.topks is None else [k for k in self.topks if k <= n]

        rank_samples: dict[str, list[int]] = {p: [] for p in players}
        elo_samples: dict[str, list[float]] = {p: [] for p in players}
        tau_vals: list[float] = []
        rho_vals: list[float] = []
        footrule_vals: list[float] = []
        topk_overlap: dict[int, list[float]] = {k: [] for k in topks}
        top1_match = 0
        pair_agree = 0
        total_pairs = n * (n - 1) // 2

        base_pos = self._positions(baseline_ranking)

        rng = np.random.default_rng(42)
        baseline_fitter = BradleyTerryFitter(
            self.builder.win_matrix[game], regularization=self.regularization, compute_uncertainties=False
        )
        for _ in tqdm(range(self.n_bootstrap), desc="Bootstrap samples"):
            if self.bootstrap_type == "nonparametric":
                boot = self.builder.get_nonparametric_bootstrap(rng=rng)
                res = self._fit_on_matrix(boot[game])
            else:
                baseline_fitter.fit()
                boot_matrix = baseline_fitter.get_parametric_bootstrap(rng=rng)
                res = self._fit_on_matrix(boot_matrix)
            elos = self._elos_from_result(res)
            ranking = self._ranking_from_elos(elos)
            pos = self._positions(ranking)

            for p in players:
                rank_samples[p].append(pos[p] + 1)
                elo_samples[p].append(elos[p])

            base_rank_arr = np.array([base_pos[p] + 1 for p in players])
            boot_rank_arr = np.array([pos[p] + 1 for p in players])
            tau = kendalltau(base_rank_arr, boot_rank_arr, variant="b").correlation
            rho = spearmanr(base_rank_arr, boot_rank_arr).correlation
            tau_vals.append(float(tau) if tau is not None else float("nan"))
            rho_vals.append(float(rho) if rho is not None else float("nan"))

            foot = float(np.abs(base_rank_arr - boot_rank_arr).sum())
            footrule_vals.append(foot / self._max_footrule(n))

            for k in topks:
                base_set = set(baseline_ranking[:k])
                boot_set = set(ranking[:k])
                inter = len(base_set & boot_set)
                topk_overlap[k].append(inter / k)

            if ranking and baseline_ranking and ranking[0] == baseline_ranking[0]:
                top1_match += 1

            agree = 0
            for i in range(n):
                for j in range(i + 1, n):
                    pi, pj = players[i], players[j]
                    agree += int((base_pos[pi] < base_pos[pj]) == (pos[pi] < pos[pj]))
            pair_agree += agree

        mean_tau = float(np.nanmean(np.array(tau_vals))) if tau_vals else float("nan")
        mean_rho = float(np.nanmean(np.array(rho_vals))) if rho_vals else float("nan")
        mean_foot = float(np.nanmean(np.array(footrule_vals))) if footrule_vals else float("nan")
        top1_consistency = top1_match / self.n_bootstrap if self.n_bootstrap > 0 else float("nan")
        pairwise_agreement = (pair_agree / (self.n_bootstrap * total_pairs)) if total_pairs > 0 else float("nan")

        logger.info("\nRank stability (bootstrap)")
        logger.info(f"Game: {game}")
        logger.info(f"Bootstraps: {self.n_bootstrap}")
        logger.info(f"Bootstrap type: {self.bootstrap_type}")
        logger.info("")
        logger.info(f"{'Metric':<28} {'Value':>10}")
        logger.info("-" * 40)
        logger.info(f"{'Kendall tau (avg)':<28} {mean_tau:>10.3f}")
        logger.info(f"{'Spearman rho (avg)':<28} {mean_rho:>10.3f}")
        logger.info(f"{'Footrule (avg, norm)':<28} {mean_foot:>10.3f}")
        logger.info(f"{'Top-1 consistency':<28} {top1_consistency:>10.3f}")
        logger.info(f"{'Pairwise order agree':<28} {pairwise_agreement:>10.3f}")
        for k in topks:
            logger.info(f"{f'Top-{k} overlap (avg)':<28} {float(np.mean(topk_overlap[k])):>10.3f}")

        header = f"\n{'Model':<30} {'BaseElo':>8} {'StdElo':>8} {'MeanRank':>9} {'StdRank':>8} " + " ".join(
            [f"P@{k:>2}" for k in topks]
        )
        logger.info(header)
        separator = "-" * max(40, len(header))
        logger.info(separator)
        for p in players:
            ranks = np.array(rank_samples[p], dtype=float)
            elos_arr = np.array(elo_samples[p], dtype=float)
            base_elo = baseline_elos[p]
            mean_r = float(np.mean(ranks))
            std_r = float(np.std(ranks, ddof=0))
            std_elo = float(np.std(elos_arr, ddof=0))
            probs = []
            for k in topks:
                probs.append(np.mean(ranks <= k))
            player_line = f"{p:<30} {base_elo:8.0f} {std_elo:8.0f} {mean_r:9.2f} {std_r:8.2f} " + " ".join(
                [f"{float(pr):>5.2f}" for pr in probs]
            )
            logger.info(player_line)

        if self.output_dir is not None:
            bootstrap_dir = self.output_dir / "bootstrap"
            bootstrap_dir.mkdir(parents=True, exist_ok=True)
            self._create_rank_matrix_plot(players, rank_samples, bootstrap_dir)
            self._create_elo_violin_plot(players, elo_samples, baseline_elos, bootstrap_dir)


class EloVsMaxRounds:
    def __init__(
        self,
        *,
        log_dir: Path,
        max_rounds: int = 15,
        all_games_normalization_scheme: ALL_GAMES_NORMALIZATION_SCHEMES = "none",
        score_type: SCORING_TYPES = "per_round_tertiary",
        regularization: float = 0.01,
        output_dir: Path | None = None,
        games: list[str] | None = None,
    ):
        self.log_dir = log_dir
        self.max_rounds = max_rounds
        self.all_games_normalization_scheme = all_games_normalization_scheme
        self.score_type = score_type
        self.regularization = regularization
        self.output_dir = output_dir
        self.games = games

    @staticmethod
    def _save_plot(output_dir: Path, filename_base: str) -> None:
        """Save plot in both PDF and PNG formats."""
        for fmt in ["pdf", "png"]:
            output_path = output_dir / f"{filename_base}.{fmt}"
            plt.savefig(output_path, format=fmt, bbox_inches="tight", dpi=300 if fmt == "png" else None)
            logger.info(f"Saved plot: {output_path}")

    def run(self) -> None:
        """Calculate Elo for max rounds from 1 to max_rounds and plot the results."""
        logger.info(f"Calculating Elo for max rounds 1 to {self.max_rounds}")

        # Dictionary to store results: {max_round: {game_name: {player: elo}}}
        results_by_max_round: dict[int, dict[str, dict[str, float]]] = {}

        for max_round in tqdm(range(1, self.max_rounds + 1), desc="Processing max rounds"):
            builder = ScoreMatrixBuilder(
                all_games_normalization_scheme=self.all_games_normalization_scheme,
                score_type=self.score_type,
                max_round=max_round,
            )
            builder.build(self.log_dir)

            results_by_max_round[max_round] = {}

            for game_name, matchups in builder.win_matrix.items():
                if self.games is not None and game_name not in self.games:
                    continue

                fitter = BradleyTerryFitter(matchups, regularization=self.regularization, compute_uncertainties=False)
                result = fitter.fit()

                results_by_max_round[max_round][game_name] = {
                    p: BradleyTerryFitter.bt_to_elo(s) for p, s in zip(result["players"], result["strengths"])
                }

        self._plot_results(results_by_max_round)

    def _plot_results(self, results_by_max_round: dict[int, dict[str, dict[str, float]]]) -> None:
        """Create line plots showing Elo vs max rounds for each game."""
        if self.output_dir is None:
            logger.warning("No output directory specified, skipping plots")
            return

        output_dir = self.output_dir / "elo_vs_max_rounds"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all games
        all_games = set()
        for game_results in results_by_max_round.values():
            all_games.update(game_results.keys())

        for game_name in sorted(all_games):
            # Collect all players that appear in this game
            all_players = set()
            for round_results in results_by_max_round.values():
                if game_name in round_results:
                    all_players.update(round_results[game_name].keys())

            players = sorted(all_players)

            # Create plot
            fig, ax = plt.subplots(figsize=(12, 8))

            for player in players:
                max_rounds_list = []
                elos_list = []

                for max_round in sorted(results_by_max_round.keys()):
                    if game_name in results_by_max_round[max_round]:
                        if player in results_by_max_round[max_round][game_name]:
                            max_rounds_list.append(max_round)
                            elos_list.append(results_by_max_round[max_round][game_name][player])

                if max_rounds_list:
                    display_name = MODEL_TO_DISPLAY_NAME.get(player, player)
                    ax.plot(max_rounds_list, elos_list, marker="o", label=display_name, linewidth=2, markersize=6)

            ax.set_xlabel("Max Round", fontproperties=FONT_BOLD, fontsize=14)
            ax.set_ylabel("Elo Rating", fontproperties=FONT_BOLD, fontsize=14)
            ax.set_title(f"Elo vs Max Rounds: {game_name}", fontproperties=FONT_BOLD, fontsize=16)
            ax.grid(True, alpha=0.3)
            ax.yaxis.set_minor_locator(AutoMinorLocator())

            # Add reference line at ELO_BASE
            ax.axhline(ELO_BASE, color="red", linestyle="--", alpha=0.5, linewidth=1, label=f"Base Elo ({ELO_BASE})")

            legend = ax.legend(prop=FONT_BOLD, fontsize=12, loc="best")
            legend.set_frame_on(False)

            plt.tight_layout()
            safe_game_name = game_name.replace("/", "_").replace(" ", "_")
            self._save_plot(output_dir, f"{safe_game_name}_elo_vs_max_rounds")
            plt.close()


class EloOnlyAtRound:
    def __init__(
        self,
        *,
        log_dir: Path,
        max_rounds: int = 15,
        all_games_normalization_scheme: ALL_GAMES_NORMALIZATION_SCHEMES = "none",
        score_type: SCORING_TYPES = "per_round_tertiary",
        regularization: float = 0.01,
        output_dir: Path | None = None,
        games: list[str] | None = None,
    ):
        self.log_dir = log_dir
        self.max_rounds = max_rounds
        self.all_games_normalization_scheme = all_games_normalization_scheme
        self.score_type = score_type
        self.regularization = regularization
        self.output_dir = output_dir
        self.games = games

    @staticmethod
    def _save_plot(output_dir: Path, filename_base: str) -> None:
        """Save plot in both PDF and PNG formats."""
        for fmt in ["pdf", "png"]:
            output_path = output_dir / f"{filename_base}.{fmt}"
            plt.savefig(output_path, format=fmt, bbox_inches="tight", dpi=300 if fmt == "png" else None)
            logger.info(f"Saved plot: {output_path}")

    def run(self) -> None:
        """Calculate Elo for only specific rounds from 1 to max_rounds and plot the results."""
        logger.info(f"Calculating Elo for only specific rounds 1 to {self.max_rounds}")

        # Dictionary to store results: {round: {game_name: {player: elo}}}
        results_by_round: dict[int, dict[str, dict[str, float]]] = {}

        for round_num in tqdm(range(1, self.max_rounds + 1), desc="Processing specific rounds"):
            builder = ScoreMatrixBuilder(
                all_games_normalization_scheme=self.all_games_normalization_scheme,
                score_type=self.score_type,
                max_round=round_num,
                only_specific_round=True,
            )
            builder.build(self.log_dir)

            results_by_round[round_num] = {}

            for game_name, matchups in builder.win_matrix.items():
                if self.games is not None and game_name not in self.games:
                    continue

                fitter = BradleyTerryFitter(matchups, regularization=self.regularization, compute_uncertainties=False)
                result = fitter.fit()

                results_by_round[round_num][game_name] = {
                    p: BradleyTerryFitter.bt_to_elo(s) for p, s in zip(result["players"], result["strengths"])
                }

        self._plot_results(results_by_round)

    def _plot_results(self, results_by_round: dict[int, dict[str, dict[str, float]]]) -> None:
        """Create line plots showing Elo vs round for each game."""
        if self.output_dir is None:
            logger.warning("No output directory specified, skipping plots")
            return

        output_dir = self.output_dir / "elos_only_at_round"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all games
        all_games = set()
        for game_results in results_by_round.values():
            all_games.update(game_results.keys())

        for game_name in sorted(all_games):
            # Collect all players that appear in this game
            all_players = set()
            for round_results in results_by_round.values():
                if game_name in round_results:
                    all_players.update(round_results[game_name].keys())

            players = sorted(all_players)

            # Create plot
            fig, ax = plt.subplots(figsize=(12, 8))

            for player in players:
                rounds_list = []
                elos_list = []

                for round_num in sorted(results_by_round.keys()):
                    if game_name in results_by_round[round_num]:
                        if player in results_by_round[round_num][game_name]:
                            rounds_list.append(round_num)
                            elos_list.append(results_by_round[round_num][game_name][player])

                if rounds_list:
                    display_name = MODEL_TO_DISPLAY_NAME.get(player, player)
                    ax.plot(rounds_list, elos_list, marker="o", label=display_name, linewidth=2, markersize=6)

            ax.set_xlabel("Round", fontproperties=FONT_BOLD, fontsize=14)
            ax.set_ylabel("Elo Rating", fontproperties=FONT_BOLD, fontsize=14)
            ax.set_title(f"Elo at Specific Round: {game_name}", fontproperties=FONT_BOLD, fontsize=16)
            ax.grid(True, alpha=0.3)
            ax.yaxis.set_minor_locator(AutoMinorLocator())

            # Add reference line at ELO_BASE
            ax.axhline(ELO_BASE, color="red", linestyle="--", alpha=0.5, linewidth=1, label=f"Base Elo ({ELO_BASE})")

            legend = ax.legend(prop=FONT_BOLD, fontsize=12, loc="best")
            legend.set_frame_on(False)

            plt.tight_layout()
            safe_game_name = game_name.replace("/", "_").replace(" ", "_")
            self._save_plot(output_dir, f"{safe_game_name}_elo_only_at_round")
            plt.close()


def print_results(results: dict[str, dict]) -> None:
    """Print fitted strengths and Elo ratings for all games.

    Args:
        results: Dictionary mapping game name to fit results
    """
    for game_name in sorted(results.keys()):
        result = results[game_name]
        logger.info(f"\n{game_name}:")
        logger.info(f"Log-likelihood: {result['log_likelihood']:.2f}")
        has_sigma = "elo_std" in result
        if has_sigma:
            logger.info(f"\n{'Player':<30s} {'BT Strength':>12s} {'Elo':>8s} {'±1σ':>8s}")
            logger.info("-" * 62)
        else:
            logger.info(f"\n{'Player':<30s} {'BT Strength':>12s} {'Elo':>8s}")
            logger.info("-" * 52)

        # Sort by strength descending
        indices = np.argsort(result["strengths"])[::-1]
        for idx in indices:
            player = result["players"][idx]
            strength = result["strengths"][idx]
            elo = BradleyTerryFitter.bt_to_elo(strength)
            sigma = result.get("elo_std")
            if sigma is not None:
                s = sigma[idx]
                logger.info(f"  {player:<30s} {strength:12.3f} {elo:8.0f} {s:8.0f}")
            else:
                logger.info(f"  {player:<30s} {strength:12.3f} {elo:8.0f}")


def write_latex_table(results: dict[str, dict], output_dir: Path) -> None:
    """Write LaTeX table with ELO results to file.

    Args:
        results: Dictionary mapping game name to fit results
        output_dir: Directory to save the LaTeX file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "main_results.tex"

    single_arena_games = ["BattleSnake", "CoreWar", "Halite", "HuskyBench", "RoboCode", "RobotRumble"]
    games_in_table = [g for g in single_arena_games if g in results]

    if "ALL" not in results:
        logger.warning("No 'ALL' game found in results, skipping LaTeX table generation")
        return

    all_result = results["ALL"]
    all_players = all_result["players"]
    all_strengths = all_result["strengths"]
    all_elos = {p: BradleyTerryFitter.bt_to_elo(s) for p, s in zip(all_players, all_strengths)}
    sorted_players = sorted(all_elos.items(), key=lambda x: x[1], reverse=True)

    lines = []
    lines.append("% LaTeX commands for formatting ELO results")
    lines.append(r"\newcommand{\eloSingleArenaResult}[1]{% #1=formatted number")
    lines.append(r"  \begin{tikzpicture}[baseline=(text.base)]")
    lines.append(r"    \pgfmathsetmacro{\barwidth}{#1 * 0.0007}")
    lines.append(r"    \fill[black!15] (0, -0.15) rectangle (\barwidth, 0.25);")
    lines.append(r"    \node[anchor=west,text=black,font=\footnotesize] (text) at (-0.05, 0.05) {#1};")
    lines.append(r"  \end{tikzpicture}%")
    lines.append(r"}")
    lines.append(r"\newcommand{\eloMainResult}[1]{% #1=raw number")
    lines.append(r"  \begin{tikzpicture}[baseline=(text.base)]")
    lines.append(r"    \pgfmathsetmacro{\barwidth}{#1 * 0.001}")
    lines.append(r"    \fill[chart!35] (0, -0.15) rectangle (\barwidth, 0.25);")
    lines.append(r"    \node[anchor=west,font=\bfseries] (text) at (0, 0.05) {#1};")
    lines.append(r"  \end{tikzpicture}%")
    lines.append(r"}")
    lines.append("")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\setlength{\tabcolsep}{3pt}")
    lines.append(r"\renewcommand{\arraystretch}{0.9}")
    lines.append(r"\begin{tabular}{l|" + "l" * len(games_in_table) + "|l}")
    lines.append(r"\toprule")

    display_names = [g.replace("HuskyBench", "Poker") for g in games_in_table]
    header_parts = [""] + [rf"\scriptsize{{{g}}}" for g in display_names] + [r"\multicolumn{1}{c}{\textbf{All}}"]
    lines.append(" & ".join(header_parts) + r" \\")
    lines.append(r"\midrule")

    for player, all_elo in sorted_players:
        display_name = MODEL_TO_DISPLAY_NAME.get(player, player)
        row_parts = [display_name.replace("_", r"\_")]

        for game_name in games_in_table:
            if game_name in results:
                game_result = results[game_name]
                if player in game_result["players"]:
                    idx = game_result["players"].index(player)
                    strength = game_result["strengths"][idx]
                    elo = BradleyTerryFitter.bt_to_elo(strength)
                    row_parts.append(rf"\eloSingleArenaResult{{{int(elo)}}}")
                else:
                    row_parts.append("--")
            else:
                row_parts.append("--")

        row_parts.append(rf"\eloMainResult{{{int(all_elo)}}}")
        lines.append(" & ".join(row_parts) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    output_file.write_text("\n".join(lines) + "\n")
    logger.info(f"Saved LaTeX table: {output_file}")


def write_website_results(results: dict[str, dict], output_dir: Path) -> None:
    """Write results in JSON format for website consumption.

    Creates a leaderboard JSON with rankings per arena and overall.
    Format:
    {
        "ArenaName": [
            {"rank": 1, "model": "model_name", "elo": 1500},
            ...
        ],
        "Overall": [...]
    }
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "leaderboard.json"

    leaderboard = {}

    for game_name, game_result in results.items():
        players = game_result["players"]
        strengths = game_result["strengths"]

        # Convert Bradley-Terry strengths to Elo ratings
        elos = {p: BradleyTerryFitter.bt_to_elo(s) for p, s in zip(players, strengths)}

        # Sort by Elo (descending)
        sorted_players = sorted(elos.items(), key=lambda x: x[1], reverse=True)

        # Create leaderboard entries
        leaderboard[game_name] = [
            {"rank": rank + 1, "model": MODEL_TO_DISPLAY_NAME.get(player, player), "elo": round(elo, 1)}
            for rank, (player, elo) in enumerate(sorted_players)
        ]

    # Write to file
    with open(output_file, "w") as f:
        json.dump(leaderboard, f, indent=2)

    logger.info(f"Saved leaderboard JSON: {output_file}")


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
        "--output-dir",
        type=Path,
        default=Path("elo2_plots"),
        help="Directory to save plots (default: elo2_plots)",
    )
    args = parser.parse_args()

    builder = ScoreMatrixBuilder(
        all_games_normalization_scheme=args.all_normalization_scheme, score_type=args.score_type
    )
    builder.build(args.log_dir)

    if args.print_matrix:
        builder.print_matrix()

    uncertainties_supported = (
        args.score_type == "per_tournament_boolean_drop_draws" and args.all_normalization_scheme == "none"
    )

    # Fit Bradley-Terry model for each game
    results = {}
    for game_name, matchups in builder.win_matrix.items():
        logger.info(f"Fitting Bradley-Terry model for {game_name}")
        fitter = BradleyTerryFitter(
            matchups,
            regularization=args.regularization,
            compute_uncertainties=uncertainties_supported,
        )
        results[game_name] = fitter.fit()

    # Add file handler to logger to save all output
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        add_file_handler(logger, args.output_dir / "elo_results.log")

    # Print ELO results
    logger.info(f"\nRegularization λ = {args.regularization}")
    logger.info(f"Elo conversion: R = {ELO_BASE} + ({ELO_SLOPE}/ln(10)) * s")

    print_results(results)

    plotter = BradleyTerryFitterPlots(results, builder.win_matrix)
    plotter.create_validation_plots(args.output_dir, regularization=args.regularization)
    plotter.create_elo_plots(args.output_dir)
    write_latex_table(results, args.output_dir)
    write_website_results(results, args.output_dir)

    if uncertainties_supported:
        for bootstrap_type in ["nonparametric", "parametric"]:
            BootStrapRankStability(
                builder,
                n_bootstrap=1000,
                game="ALL",
                regularization=args.regularization,
                topks=None,
                bootstrap_type=bootstrap_type,
                output_dir=args.output_dir,
            ).run()

    logger.info("Running EloVsMaxRounds analysis")
    EloVsMaxRounds(
        log_dir=args.log_dir,
        max_rounds=15,
        all_games_normalization_scheme=args.all_normalization_scheme,
        score_type=args.score_type,
        regularization=args.regularization,
        output_dir=args.output_dir,
    ).run()

    logger.info("Running EloOnlyAtRound analysis")
    EloOnlyAtRound(
        log_dir=args.log_dir,
        max_rounds=15,
        all_games_normalization_scheme=args.all_normalization_scheme,
        score_type=args.score_type,
        regularization=args.regularization,
        output_dir=args.output_dir,
    ).run()
