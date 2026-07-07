"""CC:Ladder tournament orchestration.

Two entry points:
- :func:`build_ladder` — run PvP tournaments across all pairs of players (round-robin) to *build*
  and rank a ladder (``codeclash ladder make``).
- :class:`LadderTournament` — send a single climber up a ranked ladder, rung by rung, until it
  loses (``codeclash ladder run``).

This module owns all ladder business logic; ``codeclash/cli/ladder.py`` is a thin CLI adapter.
Nothing here depends on ``typer``: rule validation raises :class:`ValueError` so the class is usable
outside the CLI, and the CLI translates those into user-facing exits.
"""

import copy
import getpass
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from codeclash.constants import LOCAL_LOG_DIR
from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.log import get_logger

logger = get_logger("ladder")


def _player_slug(branch_init: str) -> str:
    """
    Turn a ``human/<author>/<bot>`` init branch into a bare, filesystem-safe player name:
    strip the ``human/`` prefix and join the rest with ``__`` (e.g. ``human/aleksiy325/snek-two``
    -> ``aleksiy325__snek-two``).
    """
    return branch_init.replace("human/", "").replace("/", "__")


def resolve_ladder_rules(ladder_rules: dict, rounds: int) -> tuple[int, int]:
    """Validate the required ``ladder_rules`` block and return ``(min_round_wins, win_last_k)``.

    Both keys must be specified explicitly in the config (no defaults):
    - ``min_round_wins``: the whole number of *agent* rounds the player must win to advance
      (a ``>=`` threshold). Must be ``1 <= min_round_wins <= rounds``.
    - ``win_last_k``: the player must win the last ``win_last_k`` round(s). ``1`` means just the final
      round; ``0`` disables the trailing-rounds requirement entirely. Must be ``<= min_round_wins``.

    The baseline round 0 (identical, un-edited codebases) is excluded from the count — it reflects
    game variance, not the agent — so wins are counted over the ``rounds`` rounds the agent actually
    edits (rounds 1..``rounds``).

    Raises:
        ValueError: if either key is missing or fails validation.
    """
    if "min_round_wins" not in ladder_rules:
        raise ValueError("ladder_rules.min_round_wins is required; specify it explicitly in the config.")
    if "win_last_k" not in ladder_rules:
        raise ValueError("ladder_rules.win_last_k is required; specify it explicitly in the config.")
    min_round_wins = ladder_rules["min_round_wins"]
    win_last_k = ladder_rules["win_last_k"]

    # min_round_wins: whole number of agent rounds the player must win (round 0 excluded).
    if isinstance(min_round_wins, bool) or not isinstance(min_round_wins, int):
        raise ValueError(f"ladder_rules.min_round_wins must be an integer, got {min_round_wins!r}.")
    if not 1 <= min_round_wins <= rounds:
        raise ValueError(
            f"ladder_rules.min_round_wins must be in [1, {rounds}] (tournament.rounds), got {min_round_wins}."
        )

    # win_last_k: number of trailing rounds the player must win (1 == just the final round, 0 == disabled).
    if isinstance(win_last_k, bool) or not isinstance(win_last_k, int):
        raise ValueError(f"ladder_rules.win_last_k must be an integer, got {win_last_k!r}.")
    if win_last_k < 0:
        raise ValueError(
            f"ladder_rules.win_last_k must be >= 0, got {win_last_k}. "
            "Use 0 to disable the trailing-rounds requirement, or 1 to require winning only the final round."
        )
    if win_last_k > min_round_wins:
        raise ValueError(
            f"ladder_rules.win_last_k ({win_last_k}) cannot exceed ladder_rules.min_round_wins ({min_round_wins})."
        )

    return min_round_wins, win_last_k


def build_ladder(config: dict, workers: int = 1) -> None:
    """Build a ladder: run PvP tournaments across all pairs of players (for ranking).

    Each pair is an independent PvP tournament; win rates over all pairs rank the ladder.
    """
    players = config["players"]
    num_players = len(players)

    # Build one fully independent (deep-copied) config per pair up front so concurrent runs
    # never share or mutate the same player/config dicts.
    jobs: list[tuple[dict, Path]] = []
    for i in range(num_players):
        for j in range(i + 1, num_players):
            player1 = copy.deepcopy(players[i])
            player1["name"] = _player_slug(player1["branch_init"])
            player2 = copy.deepcopy(players[j])
            player2["name"] = _player_slug(player2["branch_init"])
            pvp_config = {**copy.deepcopy(config), "players": [player1, player2]}
            vs = f"PvpTournament.{player1['name']}_vs_{player2['name']}".replace("/", "_")
            output_dir = LOCAL_LOG_DIR / "ladder" / config["game"]["name"] / vs
            jobs.append((pvp_config, output_dir))

    def run_pair(pvp_config: dict, output_dir: Path) -> None:
        try:
            tournament = PvpTournament(pvp_config, output_dir=output_dir)
        except FileExistsError:
            return  # already completed by a previous invocation
        # A single failing pair must not abort the rest of a long round-robin.
        try:
            tournament.run()
        except Exception:
            logger.exception(f"Pair failed, skipping: {output_dir.name}")

    if workers <= 1:
        for pvp_config, output_dir in jobs:
            run_pair(pvp_config, output_dir)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(run_pair, c, d) for c, d in jobs]
            for f in as_completed(futures):
                f.result()


class LadderTournament:
    """Send a single climber up a ranked ladder, rung by rung, until it loses.

    Orchestrates one :class:`PvpTournament` per rung (worst opponent first, strongest last). The
    climber advances while it satisfies the ``ladder_rules`` advancement rule; the first failure
    ends the climb. This composes ``PvpTournament`` rather than subclassing ``AbstractTournament``,
    which assumes a single game/arena.
    """

    def __init__(
        self,
        config: dict,
        *,
        base_dir: Path | None = None,
        output_dir: Path | None = None,
        suffix: str = "",
        cleanup: bool = False,
        keep_containers: bool = False,
    ):
        # Extract ladder-specific keys and strip them from the config that gets handed to each
        # per-rung PvpTournament (which only understands `players`).
        self.config = config
        self.ladder = config["ladder"]
        self.player = config["player"]
        self.rounds = config["tournament"]["rounds"]
        self.sims = config["game"]["sims_per_round"]
        self.min_round_wins, self.win_last_k = resolve_ladder_rules(config.get("ladder_rules", {}), self.rounds)

        del config["player"]
        del config["ladder"]
        config.pop("ladder_rules", None)

        self.suffix = suffix
        self.cleanup = cleanup
        self.keep_containers = keep_containers
        self.output_dir = output_dir

        timestamp = time.strftime("%y%m%d%H%M%S")
        game_name = config["game"]["name"]
        ladder_folder = f"LadderTournament.{game_name}.r{self.rounds}.s{self.sims}.{self.player['name']}.{timestamp}"
        self.player["branch"] = ladder_folder
        base = base_dir if base_dir is not None else LOCAL_LOG_DIR / getpass.getuser()
        self.parent_dir = base / ladder_folder

    def _advancement_rule_str(self) -> str:
        last_k_rule = "disabled" if self.win_last_k == 0 else f"win the last {self.win_last_k} round(s)"
        return (
            f"Ladder advancement rule: win >= {self.min_round_wins} of {self.rounds} agent rounds "
            f"(baseline round 0 excluded) and {last_k_rule}."
        )

    def _rung_dir(self, players: list[str]) -> Path:
        p_num = len(players)
        p_list = ".".join(players)
        suffix_part = f".{self.suffix}" if self.suffix else ""
        folder_name = (
            f"PvpTournament.{self.config['game']['name']}.r{self.rounds}.s{self.sims}.p{p_num}.{p_list}{suffix_part}"
        )
        return self.parent_dir / folder_name if self.output_dir is None else self.output_dir / folder_name

    def _evaluate_advancement(self, round_winners: list[str], player_name: str) -> tuple[int, bool, bool]:
        """Apply the advancement rule to a rung's round winners.

        Returns ``(player_wins, won_last_k, advanced)``.
        """
        player_wins = sum(1 for w in round_winners if w == player_name)
        won_majority = player_wins >= self.min_round_wins
        won_last_k = self.win_last_k == 0 or all(w == player_name for w in round_winners[-self.win_last_k :])
        return player_wins, won_last_k, (won_majority and won_last_k)

    def run(self) -> dict:
        """Run the climb and return the ladder-level summary dict."""
        advancement_rule = self._advancement_rule_str()
        print(advancement_rule)
        logger.info(advancement_rule)

        rungs_cleared = 0
        advanced = False
        opponent: dict = {}
        opponent_rank = 0
        for idx, opponent in enumerate(self.ladder):
            opponent_rank = len(self.ladder) - idx
            opponent["name"] = _player_slug(opponent["branch_init"])
            if "branch_init" in self.player and idx > 0:
                # After first opponent, remove branch_init so the player continues from the
                # previous tournament's codebase.
                del self.player["branch_init"]
            c = {
                **self.config,
                "players": [
                    self.player,
                    opponent,
                ],
            }

            players = [p["name"] for p in c["players"]]
            tournament_dir = self._rung_dir(players)
            tournament = PvpTournament(
                c,
                output_dir=tournament_dir,
                cleanup=self.cleanup,
                keep_containers=self.keep_containers,
            )
            tournament.run()

            # Get results
            metadata_path = tournament_dir / "metadata.json"
            with open(metadata_path) as f:
                metadata = yaml.safe_load(f)
            round_winners = [r["winner"] for k, r in metadata["round_stats"].items() if int(k) != 0]

            # Advancement rule (required via `ladder_rules`): win at least `min_round_wins` of the
            # agent rounds AND win the last `win_last_k` rounds. win_last_k == 0 disables the
            # trailing-rounds requirement.
            player_wins, won_last_k, advanced = self._evaluate_advancement(round_winners, self.player["name"])

            # Record this rung's outcome in its metadata.json (durable gameplay log). The rule itself
            # (min_round_wins, win_last_k) is constant across the run and lives in the ladder summary.
            metadata["ladder_advancement"] = {
                "player_wins": player_wins,
                "won_last_k": won_last_k,
                "cleared": advanced,
            }
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            if not advanced:
                # Player failed the advancement rule; the ladder challenge ends here.
                print("=" * 10)
                print(
                    f"{self.player['name']} did not clear {opponent['name']} "
                    f"(rank {opponent_rank}/{len(self.ladder)}): won {player_wins}/{len(round_winners)} agent rounds "
                    f"(needed >= {self.min_round_wins}), last {self.win_last_k} round(s) won: {won_last_k}.\n"
                    "Ladder challenge ends."
                )
                print("=" * 10)
                break

            rungs_cleared += 1
            print("=" * 10)
            print(
                f"{self.player['name']} successfully beat {opponent['name']} (rank {opponent_rank}/{len(self.ladder)}) "
                f"in {player_wins}/{len(round_winners)} rounds.\n"
                "Ladder challenge continuing"
            )
            print("=" * 10)

        # Persist the overall climb result to a ladder-level metadata.json in the run's parent dir.
        ladder_summary = {
            "player": self.player["name"],
            "game": self.config["game"]["name"],
            "rounds": self.rounds,
            "min_round_wins": self.min_round_wins,
            "win_last_k": self.win_last_k,
            "ladder_size": len(self.ladder),
            "rungs_cleared": rungs_cleared,
            "final_opponent": opponent["name"],
            "final_opponent_rank": opponent_rank,
            "cleared_ladder": rungs_cleared == len(self.ladder),
        }
        self.parent_dir.mkdir(parents=True, exist_ok=True)
        with open(self.parent_dir / "metadata.json", "w") as f:
            json.dump(ladder_summary, f, indent=2)

        print(f"Ladder tournament complete. Logs saved to {self.parent_dir}")
        print(f"Final opponent faced: {opponent['name']} (rank {opponent_rank}/{len(self.ladder)} in ladder)")
        return ladder_summary
