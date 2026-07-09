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
import shutil
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

    Round 0 (before any edits against this opponent) is excluded — identical codebases at the first
    rung, the agent's carried-over codebase at later rungs — so only rounds 1..``rounds`` count.

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


def resolve_fast_forward(ladder_rules: dict) -> tuple[bool, float]:
    """Validate the optional ``ladder_rules.fast_forward`` sub-block and return
    ``(enabled, min_sim_win_rate)``.

    Fast-forward lets a climber *skip playing* a rung whose carried-over codebase already dominates:
    if the climber wins at least ``min_sim_win_rate`` of the rung's round-0 simulations (ties count
    as non-wins), the rung is cleared without spending edit rounds. Absent or ``enabled: false`` ->
    ``(False, 0.0)`` = today's full-play behavior.
    """
    ff = ladder_rules.get("fast_forward")
    if ff is None:
        return False, 0.0
    if "enabled" not in ff:
        raise ValueError("ladder_rules.fast_forward.enabled is required when a fast_forward block is present.")
    enabled = ff["enabled"]
    if not isinstance(enabled, bool):
        raise ValueError(f"ladder_rules.fast_forward.enabled must be a bool, got {enabled!r}.")
    if not enabled:
        return False, 0.0
    if "min_sim_win_rate" not in ff:
        raise ValueError("ladder_rules.fast_forward.min_sim_win_rate is required when fast_forward is enabled.")
    rate = ff["min_sim_win_rate"]
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise ValueError(f"ladder_rules.fast_forward.min_sim_win_rate must be a number, got {rate!r}.")
    if not 0.5 < rate <= 1.0:
        raise ValueError(f"ladder_rules.fast_forward.min_sim_win_rate must be in (0.5, 1.0], got {rate}.")
    return True, float(rate)


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
        resume_from: Path | None = None,
    ):
        # Extract ladder-specific keys and strip them from the config that gets handed to each
        # per-rung PvpTournament (which only understands `players`).
        self.config = config
        self.ladder = config["ladder"]
        self.player = config["player"]
        self.rounds = config["tournament"]["rounds"]
        self.sims = config["game"]["sims_per_round"]
        self.min_round_wins, self.win_last_k = resolve_ladder_rules(config.get("ladder_rules", {}), self.rounds)
        self.ff_enabled, self.ff_min_win_rate = resolve_fast_forward(config.get("ladder_rules", {}))

        del config["player"]
        del config["ladder"]
        config.pop("ladder_rules", None)

        self.suffix = suffix
        self.cleanup = cleanup
        self.keep_containers = keep_containers
        self.output_dir = output_dir
        self._resuming = resume_from is not None
        self._start_idx = 0

        base = base_dir if base_dir is not None else LOCAL_LOG_DIR / getpass.getuser()

        if not self._resuming:
            timestamp = time.strftime("%y%m%d%H%M%S")
            game_name = config["game"]["name"]
            ladder_folder = (
                f"LadderTournament.{game_name}.r{self.rounds}.s{self.sims}.{self.player['name']}.{timestamp}"
            )
            self.player["branch"] = ladder_folder
            self.parent_dir = base / ladder_folder
        else:
            # Continue the interrupted run IN PLACE: reuse its log dir and its push branch (the dir
            # name IS the branch name). The top-level metadata.json is written only after the climb
            # loop finishes (win or lose), so its presence means there is nothing to resume.
            self.parent_dir = resume_from
            self.player["branch"] = resume_from.name
            if not self.player.get("push"):
                raise ValueError(
                    "--resume requires push: True — the pushed branch and round tags are the codebase store."
                )
            if (resume_from / "metadata.json").exists():
                raise ValueError(
                    f"{resume_from.name} already finished (top-level metadata.json present); nothing to resume."
                )
            self._start_idx, resume_tag = self._scan_resume(resume_from)
            if resume_tag is not None:
                self.player["branch_init"] = resume_tag
            # The first resumed rung force-resets the branch to `resume_tag`, discarding any partial
            # rounds the interrupted rung pushed; later rungs then fast-forward normally.
            self.player["force_push"] = True
            msg = (
                f"Resuming {resume_from.name}: {self._start_idx} rung(s) already cleared; "
                f"seeding codebase from {resume_tag or self.player.get('branch_init')}."
            )
            print(msg)
            logger.info(msg)

    def _advancement_rule_str(self) -> str:
        last_k_rule = "disabled" if self.win_last_k == 0 else f"win the last {self.win_last_k} round(s)"
        return (
            f"Ladder advancement rule: win >= {self.min_round_wins} of {self.rounds} agent rounds "
            f"(baseline round 0 excluded) and {last_k_rule}."
        )

    def _rung_folder_name(self, players: list[str]) -> str:
        p_num = len(players)
        p_list = ".".join(players)
        suffix_part = f".{self.suffix}" if self.suffix else ""
        return f"PvpTournament.{self.config['game']['name']}.r{self.rounds}.s{self.sims}.p{p_num}.{p_list}{suffix_part}"

    def _rung_dir(self, players: list[str]) -> Path:
        folder_name = self._rung_folder_name(players)
        return self.parent_dir / folder_name if self.output_dir is None else self.output_dir / folder_name

    def _climber_final_tag(self, rung_metadata: dict) -> str:
        """The climber's git tag for the last round of a (cleared) rung — the codebase to carry over."""
        for agent in rung_metadata.get("agents", []):
            if agent.get("name") == self.player["name"]:
                tags = agent.get("round_tags") or {}
                if not tags:
                    raise ValueError("A cleared rung has no round tags to resume from (was push enabled?).")
                return tags[max(tags, key=lambda k: int(k))]
        raise ValueError(f"Climber {self.player['name']!r} not found in the resumed rung's metadata.")

    def _scan_resume(self, resume_dir: Path) -> tuple[int, str | None]:
        """Inspect an interrupted run and return ``(start_idx, resume_tag)``: the first rung not yet
        cleared, and the climber's codebase tag at the end of the last cleared rung (``None`` if the
        run never cleared a rung). Reads only artifacts a normal run already writes — per-rung
        ``metadata.json`` (``ladder_advancement.cleared``) and the pushed ``round_tags``.
        """
        if not resume_dir.exists():
            raise ValueError(f"--resume directory does not exist: {resume_dir}")
        resume_tag: str | None = None
        for idx, opponent in enumerate(self.ladder):
            players = [self.player["name"], _player_slug(opponent["branch_init"])]
            meta_path = resume_dir / self._rung_folder_name(players) / "metadata.json"
            if not meta_path.exists():
                if idx == 0 and not any(resume_dir.glob("PvpTournament.*")):
                    return 0, None  # nothing was completed → equivalent to a fresh run
                if idx == 0:
                    raise ValueError(f"--resume dir has no rung matching this config: {resume_dir}")
                return idx, resume_tag  # reached the interrupted rung
            meta = json.loads(meta_path.read_text())
            advancement = meta.get("ladder_advancement")
            if advancement is None:
                return idx, resume_tag  # rung ran but never finished → resume here
            if not advancement.get("cleared"):
                raise ValueError(f"Run already ended: climber lost at rung {idx + 1}. Nothing to resume.")
            # A fast-forwarded rung made no code changes (no round tags), so it isn't a new carry-over
            # point — keep the tag from the last *played* rung.
            if not advancement.get("fast_forwarded"):
                resume_tag = self._climber_final_tag(meta)
        raise ValueError("Run already cleared the entire ladder. Nothing to resume.")

    def _fast_forward_probe(self, rung_config: dict, rung_dir: Path) -> float:
        """Run round 0 only in a throwaway probe dir and return the climber's share of the round-0
        simulations (ties count as non-wins). Used to decide whether to skip playing the rung."""
        probe_config = copy.deepcopy(rung_config)
        probe_config["tournament"] = {**probe_config["tournament"], "rounds": 0}
        probe_dir = rung_dir.parent / f".ff-probe.{rung_dir.name}"
        if probe_dir.exists():
            shutil.rmtree(probe_dir)
        try:
            probe = PvpTournament(
                probe_config, output_dir=probe_dir, cleanup=self.cleanup, keep_containers=self.keep_containers
            )
            probe.run()
            meta = json.loads((probe_dir / "metadata.json").read_text())
            round_stats = meta.get("round_stats", {})
            r0 = round_stats.get("0") or round_stats.get(0) or {}
            wins = (r0.get("scores") or {}).get(self.player["name"], 0)
            return wins / self.sims if self.sims else 0.0
        finally:
            if probe_dir.exists():
                shutil.rmtree(probe_dir)

    def _record_fast_forward(self, rung_dir: Path, win_rate: float) -> None:
        """Write a minimal rung metadata.json marking it cleared-by-fast-forward (no rounds played),
        so resume and the ladder summary can account for it like any other cleared rung."""
        rung_dir.mkdir(parents=True, exist_ok=True)
        meta = {"ladder_advancement": {"cleared": True, "fast_forwarded": True, "round0_win_rate": round(win_rate, 4)}}
        (rung_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

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

        advanced = False
        fast_forwarded = 0
        opponent: dict = {}
        opponent_rank = 0
        rung = 0
        total = len(self.ladder)
        for idx, opponent in enumerate(self.ladder):
            if idx < self._start_idx:
                continue  # already cleared in the run we're resuming
            # `rung` counts the climb from the bottom (1 = weakest opponent faced first, `total` =
            # strongest); `opponent_rank` is the opponent's Elo standing (1 = strongest overall).
            rung = idx + 1
            opponent_rank = total - idx
            opponent["name"] = _player_slug(opponent["branch_init"])
            # Prefix the climber's commit/tag messages with rung context (a prefix carrying its own
            # trailing separator; see Player._round_message).
            self.player["commit_label"] = f"Rung {rung}/{total} ({opponent['name']}, elo #{opponent_rank}) — "
            if idx > self._start_idx:
                # After the first executed rung, drop branch_init so the player continues from the
                # previous rung's pushed codebase (carry-over).
                self.player.pop("branch_init", None)
            c = {
                **self.config,
                "players": [
                    self.player,
                    opponent,
                ],
            }

            players = [p["name"] for p in c["players"]]
            tournament_dir = self._rung_dir(players)
            # When resuming in place, the interrupted rung left a partial dir; clear it so
            # PvpTournament (which refuses a pre-existing metadata.json) can re-run it fresh.
            if self._resuming and idx == self._start_idx and tournament_dir.exists():
                shutil.rmtree(tournament_dir)

            # Fast-forward gate: if enabled and the carried-over bot already wins round 0 by a large
            # enough margin, clear this rung without playing the edit rounds (see resolve_fast_forward).
            if self.ff_enabled:
                ff_rate = self._fast_forward_probe(c, tournament_dir)
                if ff_rate >= self.ff_min_win_rate:
                    self._record_fast_forward(tournament_dir, ff_rate)
                    advanced = True
                    fast_forwarded += 1
                    print("=" * 10)
                    print(
                        f"{self.player['name']} fast-forwarded rung {rung}/{total} ({opponent['name']}, "
                        f"elo #{opponent_rank}) — won {ff_rate:.0%} of round-0 sims "
                        f"(>= {self.ff_min_win_rate:.0%}).\nLadder challenge continuing"
                    )
                    print("=" * 10)
                    continue

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
                    f"(rung {rung}/{total}, elo #{opponent_rank}): won {player_wins}/{len(round_winners)} agent rounds "
                    f"(needed >= {self.min_round_wins}), last {self.win_last_k} round(s) won: {won_last_k}.\n"
                    "Ladder challenge ends."
                )
                print("=" * 10)
                break

            print("=" * 10)
            print(
                f"{self.player['name']} successfully beat {opponent['name']} (rung {rung}/{total}, elo #{opponent_rank}) "
                f"in {player_wins}/{len(round_winners)} rounds.\n"
                "Ladder challenge continuing"
            )
            print("=" * 10)

        # Persist the overall climb result to a ladder-level metadata.json in the run's parent dir.
        rungs_cleared = rung if advanced else max(rung - 1, 0)
        ladder_summary = {
            "player": self.player["name"],
            "game": self.config["game"]["name"],
            "rounds": self.rounds,
            "min_round_wins": self.min_round_wins,
            "win_last_k": self.win_last_k,
            "ladder_size": len(self.ladder),
            "rungs_cleared": rungs_cleared,
            "rungs_fast_forwarded": fast_forwarded,
            "final_opponent": opponent["name"],
            "final_opponent_rank": opponent_rank,
            "cleared_ladder": rungs_cleared == len(self.ladder),
        }
        self.parent_dir.mkdir(parents=True, exist_ok=True)
        with open(self.parent_dir / "metadata.json", "w") as f:
            json.dump(ladder_summary, f, indent=2)

        print(f"Ladder tournament complete. Logs saved to {self.parent_dir}")
        print(f"Final opponent faced: {opponent['name']} (rung {rung}/{total}, elo #{opponent_rank})")
        return ladder_summary
