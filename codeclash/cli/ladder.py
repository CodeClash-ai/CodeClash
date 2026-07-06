"""`codeclash ladder` subcommands: build a ladder (make) and climb it (run)."""

import copy
import getpass
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
import yaml

from codeclash import CONFIG_DIR
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.log import get_logger
from codeclash.utils.yaml_utils import resolve_includes

logger = get_logger("ladder")


def _resolve_ladder_rules(ladder_rules: dict, rounds: int) -> tuple[float, int]:
    """Validate the optional ``ladder_rules`` block and return ``(min_round_win_fraction, win_last_k)``.

    Defaults reproduce the historical behavior: win a strict majority of rounds
    (``min_round_win_fraction=0.5``) AND win the final round (``win_last_k=1``).
    """
    min_round_win_fraction = ladder_rules.get("min_round_win_fraction", 0.5)
    win_last_k = ladder_rules.get("win_last_k", 1)

    # win_last_k: number of trailing rounds the player must win (1 == just the final round).
    if isinstance(win_last_k, bool) or not isinstance(win_last_k, int):
        typer.echo(f"ladder_rules.win_last_k must be an integer, got {win_last_k!r}.")
        raise typer.Exit(1)
    if win_last_k < 1:
        typer.echo(
            f"ladder_rules.win_last_k must be >= 1, got {win_last_k}. Use 1 to require winning only the final round."
        )
        raise typer.Exit(1)
    if win_last_k > rounds:
        typer.echo(f"ladder_rules.win_last_k ({win_last_k}) cannot exceed tournament.rounds ({rounds}).")
        raise typer.Exit(1)

    # min_round_win_fraction: player must win strictly more than this fraction of rounds.
    if isinstance(min_round_win_fraction, bool) or not isinstance(min_round_win_fraction, (int, float)):
        typer.echo(f"ladder_rules.min_round_win_fraction must be a number, got {min_round_win_fraction!r}.")
        raise typer.Exit(1)
    if not 0 <= min_round_win_fraction < 1:
        typer.echo(
            f"ladder_rules.min_round_win_fraction must be in [0, 1), got {min_round_win_fraction}. "
            "0.5 requires a strict majority; 0 drops the majority requirement."
        )
        raise typer.Exit(1)

    return float(min_round_win_fraction), win_last_k


ladder_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",  # enables the [dim] markup used in the Examples blocks
    context_settings={"help_option_names": ["-h", "--help"]},
)


@ladder_app.command("make")
def make(
    config_path: Path = typer.Argument(..., help="Path to the ladder (round-robin) config file."),
    workers: int = typer.Option(
        1, "--workers", "-w", help="Pairwise tournaments to run concurrently (each pair is independent)."
    ),
):
    """Build a ladder: run PvP tournaments across all pairs of players (for ranking).

    [dim]• codeclash ladder make configs/ablations/ladder/make_battlesnake.yaml[/dim]
    """
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)

    players = config["players"]
    num_players = len(players)

    # Build one fully independent (deep-copied) config per pair up front so concurrent runs
    # never share or mutate the same player/config dicts.
    jobs: list[tuple[dict, Path]] = []
    for i in range(num_players):
        for j in range(i + 1, num_players):
            player1 = copy.deepcopy(players[i])
            player1["name"] = player1["branch_init"]
            player2 = copy.deepcopy(players[j])
            player2["name"] = player2["branch_init"]
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


@ladder_app.command("run")
def run(
    config_path: Path = typer.Argument(..., help="Path to the ladder config (with `player` + `ladder`)."),
    cleanup: bool = typer.Option(False, "--cleanup", "-c", help="Clean up the game environment after running."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Output directory (default: logs/<user>)."),
    suffix: str = typer.Option("", "--suffix", "-s", help="Suffix for the output folder name (no leading dot)."),
    keep_containers: bool = typer.Option(
        False, "--keep-containers", "-k", help="Do not remove containers after games/agent finish."
    ),
):
    """Send a model up a ranked ladder, rung by rung, until it loses.

    [dim]• codeclash ladder run path/to/ladder_config.yaml -c  # clean up after each rung[/dim]
    """
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)
    ladder, player, rounds, sims = (
        config["ladder"],
        config["player"],
        config["tournament"]["rounds"],
        config["game"]["sims_per_round"],
    )
    min_round_win_fraction, win_last_k = _resolve_ladder_rules(config.get("ladder_rules", {}), rounds)
    timestamp = time.strftime("%y%m%d%H%M%S")
    del config["player"]
    del config["ladder"]
    config.pop("ladder_rules", None)

    print(
        f"Ladder advancement rule: win > {min_round_win_fraction:.0%} of {rounds} rounds "
        f"and win the last {win_last_k} round(s)."
    )
    ladder_folder = f"LadderTournament.{config['game']['name']}.r{rounds}.s{sims}.{timestamp}"
    player["branch"] = ladder_folder
    parent_dir = LOCAL_LOG_DIR / getpass.getuser() / ladder_folder

    for idx, opponent in enumerate(ladder):
        opponent_rank = len(ladder) - idx
        opponent["name"] = opponent["branch_init"].replace("human/", "").replace("/", "_")
        if "branch_init" in player and idx > 0:
            # After first opponent, remove branch_init so that player continues from previous tournament's codebase
            del player["branch_init"]
        c = {
            **config,
            "players": [
                player,
                opponent,
            ],
        }

        players = [p["name"] for p in c["players"]]
        p_num = len(players)
        p_list = ".".join(players)
        suffix_part = f".{suffix}" if suffix else ""
        folder_name = f"PvpTournament.{c['game']['name']}.r{rounds}.s{sims}.p{p_num}.{p_list}{suffix_part}"

        tournament_dir = parent_dir / folder_name if output_dir is None else output_dir / folder_name
        tournament = PvpTournament(
            c,
            output_dir=tournament_dir,
            cleanup=cleanup,
            keep_containers=keep_containers,
        )
        tournament.run()

        # Get results
        metadata_path = tournament_dir / "metadata.json"
        with open(metadata_path) as f:
            metadata = yaml.safe_load(f)
        round_winners = [r["winner"] for r in metadata["round_stats"].values()]

        # Advancement rule (configurable via `ladder_rules`): win strictly more than
        # `min_round_win_fraction` of rounds AND win the last `win_last_k` rounds.
        player_wins = sum(1 for w in round_winners if w == player["name"])
        won_majority = player_wins > len(round_winners) * min_round_win_fraction
        won_last_k = all(w == player["name"] for w in round_winners[-win_last_k:])

        if not won_majority or not won_last_k:
            # Player failed the advancement rule; the ladder challenge ends here.
            print("=" * 10)
            print(
                f"{player['name']} did not clear {opponent['name']} "
                f"(rank {opponent_rank}/{len(ladder)}): won {player_wins}/{len(round_winners)} rounds "
                f"(needed > {min_round_win_fraction:.0%}), last {win_last_k} round(s) won: {won_last_k}.\n"
                "Ladder challenge ends."
            )
            print("=" * 10)
            break

        print("=" * 10)
        print(
            f"{player['name']} successfully beat {opponent['name']} (rank {opponent_rank}/{len(ladder)}) "
            f"in {player_wins}/{len(round_winners)} rounds.\n"
            "Ladder challenge continuing"
        )
        print("=" * 10)

    print(f"Ladder tournament complete. Logs saved to {parent_dir}")
    print(f"Final opponent faced: {opponent['name']} (rank {opponent_rank}/{len(ladder)} in ladder)")
