import argparse
import json
import time
import uuid
from pathlib import Path

from codeclash.agents.dummy_agent import Dummy
from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_WORK
from codeclash.games import get_game
from codeclash.tournaments.utils.git_utils import filter_git_diff
from codeclash.utils.log import add_file_handler, get_logger

# todo: add visualization code
# todo: Should start from initial commit set in metadata rather than last commit


class PvPMatrixEvaluator:
    def __init__(self, pvp_output_dir: Path, n_repetitions: int = 3):
        self.pvp_output_dir = Path(pvp_output_dir)
        self.n_repetitions = n_repetitions
        self.metadata = json.loads((self.pvp_output_dir / "metadata.json").read_text())

        assert len(self.players) == 2, f"Expected exactly 2 players, got {len(self.players)}"

        # Set up logging
        self.logger = get_logger("MatrixEvaluator", log_path=self.pvp_output_dir / "matrix_eval.log", emoji="📊")
        add_file_handler(get_logger("."), self.pvp_output_dir / "matrix_eval.log")

        # Initialize metadata similar to tournament class
        self._metadata = {
            "name": "MatrixEvaluator",
            "pvp_output_dir": str(self.pvp_output_dir),
            "p1_name": self.players[0],
            "p2_name": self.players[1],
            "rounds": self.rounds,
            "n_repetitions": n_repetitions,
            "created_timestamp": int(time.time()),
            "matrices": {},
        }

        # Load existing progress if available
        self._load_existing_progress()

        # Create game instance for evaluation
        tournament_id = f"MatrixEval.{self.metadata['name']}.{time.strftime('%y%m%d%H%M%S')}"

        self.config["game"]["sims_per_round"] = n_repetitions

        self.game = get_game(
            self.config,
            tournament_id=tournament_id,
            local_output_dir=self.pvp_output_dir / "matrix_eval",
            keep_containers=False,
        )

        self.logger.info(f"Initialized matrix evaluator for {self.players[0]} vs {self.players[1]}")
        self.logger.info(f"Will evaluate {self.rounds + 1} rounds with {n_repetitions} repetitions each")

    # Quick access properties
    # -----------------------

    @property
    def config(self) -> dict:
        """Game configuration from PvP metadata."""
        return self.metadata["config"]

    @property
    def rounds(self) -> int:
        """Number of rounds actually evaluated, determined from round_stats in metadata."""
        return len(self.metadata["round_stats"])

    @property
    def players(self) -> list[str]:
        """List of player names from metadata."""
        return [agent["name"] for agent in self.metadata["agents"]]

    @property
    def output_file(self) -> Path:
        """Path to the matrix.json output file."""
        return self.pvp_output_dir / "matrix.json"

    @property
    def matrices(self) -> dict:
        """Direct access to the matrices in metadata."""
        return self._metadata["matrices"]

    # -----------------------

    def _load_existing_progress(self):
        """Load existing progress from matrix.json if it exists."""
        if not self.output_file.exists():
            return
        existing_data = json.loads(self.output_file.read_text())
        if "matrices" in existing_data:
            self._metadata["matrices"] = existing_data["matrices"]

    def _save_progress(self):
        """Save current progress to matrix.json."""
        self.output_file.write_text(json.dumps(self._metadata, indent=2))
        self.logger.debug("Progress saved to matrix.json")

    def _get_round_diff(self, player_name: str, round_num: int) -> str | None:
        """Read diff data from changes_r{round}.json file. Returns None if file doesn't exist."""
        if round_num == 0:
            return ""
        changes_file = self.pvp_output_dir / "players" / player_name / f"changes_r{round_num}.json"
        try:
            changes_data = json.loads(changes_file.read_text())
            return changes_data.get("full_diff", "")
        except FileNotFoundError:
            return None

    def _create_dummy_agent(self, player_name: str, agent_suffix: str = "") -> Dummy:
        """Create a dummy agent for matrix evaluation."""
        # Find the original player config
        original_config = None
        for player_config in self.config["players"]:
            if player_config["name"] == player_name:
                original_config = player_config.copy()
                break

        if original_config is None:
            raise ValueError(f"Player {player_name} not found in config")

        # Create unique name for this agent instance
        original_config["name"] = f"{player_name}{agent_suffix}"

        environment = self.game.get_environment(f"{self.game.game_id}.{original_config['name']}")
        game_context = GameContext(
            id=self.game.game_id,
            log_env=self.game.log_env,
            log_local=self.game.log_local,
            name=self.game.name,
            player_id=original_config["name"],
            prompts=self.config["prompts"],
            round=0,
            rounds=self.rounds,
            working_dir=str(DIR_WORK),
        )

        return Dummy(original_config, environment, game_context)

    def _evaluate_matrix_cell(
        self, agent1: Dummy, agent2: Dummy, player1_name: str, player2_name: str, i: int, j: int, matrix_id: str
    ) -> dict | None:
        """Evaluate a single matrix cell and return the stats object. Returns None if cell should be skipped."""
        # Return existing result if already completed
        try:
            existing_result = self.matrices[matrix_id][str(i)][str(j)]
        except KeyError:
            existing_result = None
        if existing_result:
            self.logger.debug(f"Skipping {player1_name} round {i} vs {player2_name} round {j} - already completed")
            return existing_result

        patch1 = self._get_round_diff(player1_name, i)
        patch2 = self._get_round_diff(player2_name, j)

        # Skip if any required changes file is missing
        if patch1 is None:
            self.logger.warning(
                f"Skipping {player1_name} round {i} vs {player2_name} round {j} - missing changes file for {player1_name} round {i}"
            )
            return None
        if patch2 is None:
            self.logger.warning(
                f"Skipping {player1_name} round {i} vs {player2_name} round {j} - missing changes file for {player2_name} round {j}"
            )
            return None

        agent1.reset_and_apply_patch(filter_git_diff(patch1))
        agent2.reset_and_apply_patch(filter_git_diff(patch2))

        self.logger.info(f"Evaluating {player1_name} round {i} vs {player2_name} round {j}")

        round_id = str(uuid.uuid4().hex)
        stats = self.game.run_round([agent1, agent2], round_id)
        self.logger.debug(f"Result: {stats.to_dict()}")

        return stats.to_dict()

    def _evaluate_matrix(self, player1_name: str, player2_name: str):
        """Generic method to evaluate a matrix between two players (or same player)."""
        symmetric = player1_name == player2_name
        matrix_id = f"{player1_name}_vs_{player2_name}"
        self.logger.info(f"Evaluating {matrix_id} matrix: {player1_name} vs {player2_name}")

        agent1 = self._create_dummy_agent(player1_name, "_1" if player1_name == player2_name else "")
        agent2 = self._create_dummy_agent(player2_name, "_2" if player1_name == player2_name else "")

        self.matrices.setdefault(matrix_id, {})
        for i in range(self.rounds + 1):
            self.matrices[matrix_id].setdefault(str(i), {})
            j_range = range(i + 1) if symmetric else range(self.rounds + 1)
            for j in j_range:
                result = self._evaluate_matrix_cell(agent1, agent2, player1_name, player2_name, i, j, matrix_id)
                if result is not None:
                    self.matrices[matrix_id][str(i)][str(j)] = result
                self._save_progress()

    def evaluate_all_matrices(self) -> dict:
        """Evaluate vs matrix between the two players."""
        self.logger.info("Starting matrix evaluation")
        self._evaluate_matrix(self.players[0], self.players[0])
        self._evaluate_matrix(self.players[1], self.players[1])
        self._metadata["evaluation_completed_timestamp"] = int(time.time())
        self.end()
        return self.matrices

    def end(self):
        """Save metadata and clean up resources."""
        self.output_file.write_text(json.dumps(self._metadata, indent=2))
        self.logger.info(f"Matrix evaluation results saved to {self.output_file}")
        self.game.end(cleanup=True)


def main(pvp_output_dir: Path, n_repetitions: int = 3):
    """Main function to evaluate PvP tournament matrices."""
    evaluator = PvPMatrixEvaluator(pvp_output_dir, n_repetitions)
    return evaluator.evaluate_all_matrices()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate PvP tournament matrices")
    parser.add_argument("pvp_output_dir", type=Path, help="Path to PvP tournament output directory")
    parser.add_argument(
        "--repetitions", "-r", type=int, default=3, help="Number of repetitions per matrix cell (default: 3)"
    )

    args = parser.parse_args()
    main(args.pvp_output_dir, args.repetitions)
