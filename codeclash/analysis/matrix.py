import argparse
import json
import time
import uuid
from pathlib import Path
from queue import Queue
from threading import Lock, Thread

from codeclash.agents.dummy_agent import Dummy
from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_WORK
from codeclash.games import get_game
from codeclash.tournaments.utils.git_utils import filter_git_diff
from codeclash.utils.atomic_write import atomic_write
from codeclash.utils.log import add_root_file_handler, get_logger

# todo: add visualization code
# todo: Should start from initial commit set in metadata rather than last commit


class PvPMatrixEvaluator:
    def __init__(self, pvp_output_dir: Path, n_repetitions: int = 3, max_workers: int = 4):
        self.pvp_output_dir = Path(pvp_output_dir)
        self.n_repetitions = n_repetitions
        self.max_workers = max_workers
        self.metadata = json.loads((self.pvp_output_dir / "metadata.json").read_text())

        assert len(self.players) == 2, f"Expected exactly 2 players, got {len(self.players)}"

        # Set up logging with thread safety
        self.logger = get_logger("MatrixEvaluator", log_path=self.pvp_output_dir / "matrix_eval.log", emoji="📊")
        add_root_file_handler(self.pvp_output_dir / "matrix_everything.log")

        # Thread safety for progress saving
        self._save_lock = Lock()

        # Initialize metadata similar to tournament class
        self._metadata = {
            "name": "MatrixEvaluator",
            "pvp_output_dir": str(self.pvp_output_dir),
            "p1_name": self.players[0],
            "p2_name": self.players[1],
            "rounds": self.rounds,
            "n_repetitions": n_repetitions,
            "max_workers": max_workers,
            "created_timestamp": int(time.time()),
            "matrices": {},
        }

        # Load existing progress if available
        self._load_existing_progress()

        # Initialize game pool and agent pools
        self._initialize_game_pool()
        self._initialize_agent_pools()

        self.logger.info(f"Initialized matrix evaluator for {self.players[0]} vs {self.players[1]}")
        self.logger.info(f"Will evaluate {self.rounds + 1} rounds with {n_repetitions} repetitions each")
        self.logger.info(f"Using {max_workers} parallel workers")

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

    def _save(self):
        """Save metadata to matrix.json."""
        with self._save_lock:
            atomic_write(self.output_file, json.dumps(self._metadata, indent=2))

    def _load_existing_progress(self):
        """Load existing progress from matrix.json if it exists."""
        if not self.output_file.exists():
            return
        existing_data = json.loads(self.output_file.read_text())
        if "matrices" in existing_data:
            self._metadata["matrices"] = existing_data["matrices"]

    def _initialize_game_pool(self):
        """Initialize a pool of game objects for parallel execution."""
        self.game_pool = []
        for i in range(self.max_workers):
            tournament_id = f"MatrixEval.{self.metadata['name']}.{time.strftime('%y%m%d%H%M%S')}.worker{i}"
            config = self.config.copy()
            config["game"]["sims_per_round"] = self.n_repetitions

            game = get_game(
                config,
                tournament_id=tournament_id,
                local_output_dir=self.pvp_output_dir / "matrix_eval" / f"worker_{i}",
                keep_containers=False,
            )
            self.game_pool.append(game)

        self.logger.info(f"Initialized {len(self.game_pool)} game workers")

    def _initialize_agent_pools(self):
        """Pre-initialize agents for all rounds for each player."""
        self.agent_pools = {}

        for player_name in self.players:
            self.agent_pools[player_name] = {}
            for round_num in range(self.rounds + 1):
                # Pre-load the diff for this round
                patch = self._get_round_diff(player_name, round_num)
                if patch is not None:
                    # Create agent for this round and player
                    agent = self._create_dummy_agent(player_name, f"_r{round_num}")
                    agent.reset_and_apply_patch(filter_git_diff(patch))
                    self.agent_pools[player_name][round_num] = agent
                    self.logger.debug(f"Pre-initialized agent for {player_name} round {round_num}")
                else:
                    self.logger.warning(f"Missing changes file for {player_name} round {round_num}")

        self.logger.info(f"Pre-initialized agents for {len(self.players)} players across {self.rounds + 1} rounds")

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

        game = self.game_pool[0]
        environment = game.get_environment(f"{game.game_id}.{original_config['name']}")
        game_context = GameContext(
            id=game.game_id,
            log_env=game.log_env,
            log_local=game.log_local,
            name=game.name,
            player_id=original_config["name"],
            prompts=game.config["prompts"],
            round=0,
            rounds=self.rounds,
            working_dir=str(DIR_WORK),
        )

        return Dummy(original_config, environment, game_context)

    def _evaluate_matrix_cell_parallel(
        self, game_worker, player1_name: str, player2_name: str, i: int, j: int, matrix_id: str
    ) -> tuple[int, int, dict | None]:
        """Evaluate a single matrix cell using pre-initialized agents. Returns (i, j, result)."""
        # Return existing result if already completed
        try:
            existing_result = self.matrices[matrix_id][str(i)][str(j)]
            if existing_result:
                self.logger.debug(f"Skipping {player1_name} round {i} vs {player2_name} round {j} - already completed")
                return (i, j, existing_result)
        except KeyError:
            pass

        # Check if agents are available for these rounds
        if i not in self.agent_pools[player1_name]:
            self.logger.warning(
                f"Skipping {player1_name} round {i} vs {player2_name} round {j} - missing agent for {player1_name} round {i}"
            )
            return (i, j, None)
        if j not in self.agent_pools[player2_name]:
            self.logger.warning(
                f"Skipping {player1_name} round {i} vs {player2_name} round {j} - missing agent for {player2_name} round {j}"
            )
            return (i, j, None)

        # Get pre-initialized agents
        agent1 = self.agent_pools[player1_name][i]
        agent2 = self.agent_pools[player2_name][j]

        self.logger.info(f"Evaluating {player1_name} round {i} vs {player2_name} round {j}")

        round_id = str(uuid.uuid4().hex)
        stats = game_worker.run_round([agent1, agent2], round_id, copy_logs=False)
        result = stats.to_dict()
        self.logger.debug(f"Result: {result}")

        with self._save_lock:
            self.matrices[matrix_id][str(i)][str(j)] = result
            self._save()

        return (i, j, result)

    def _worker_thread(self, worker_id: int, task_queue: Queue):
        """Worker thread that processes tasks using a specific game worker."""
        game_worker = self.game_pool[worker_id]
        self.logger.debug(f"Worker {worker_id} started")

        while True:
            try:
                task = task_queue.get(timeout=1)  # Short timeout to allow clean exit
            except:
                # Queue is empty and no more tasks coming
                break

            try:
                self._evaluate_matrix_cell_parallel(game_worker, **task)
            except Exception as e:
                self.logger.error(f"Worker {worker_id} failed on task {task}: {e}")
            finally:
                task_queue.task_done()

        self.logger.debug(f"Worker {worker_id} stopped")

    def _evaluate_matrix(self, player1_name: str, player2_name: str):
        """Evaluate a matrix between two players using manual thread management."""
        symmetric = player1_name == player2_name
        matrix_id = f"{player1_name}_vs_{player2_name}"
        self.logger.info(f"Evaluating {matrix_id} matrix: {player1_name} vs {player2_name}")

        # Initialize matrix structure
        self.matrices.setdefault(matrix_id, {})
        for i in range(self.rounds + 1):
            self.matrices[matrix_id].setdefault(str(i), {})

        # Create task queue and populate it directly
        task_queue = Queue()
        task_count = 0

        for i in range(self.rounds + 1):
            j_range = range(i) if symmetric else range(self.rounds + 1)
            for j in j_range:
                # Skip if already completed
                try:
                    if self.matrices[matrix_id][str(i)][str(j)]:
                        continue
                except KeyError:
                    pass
                task_queue.put(
                    {"player1_name": player1_name, "player2_name": player2_name, "i": i, "j": j, "matrix_id": matrix_id}
                )
                task_count += 1

        if task_count == 0:
            self.logger.info(f"All matrix cells for {matrix_id} already completed")
            return

        self.logger.info(f"Executing {task_count} matrix cells using {self.max_workers} dedicated workers")

        # Start worker threads - each bound to a specific game worker
        self.logger.debug("Starting worker threads")
        workers = []
        for worker_id in range(self.max_workers):
            worker = Thread(target=self._worker_thread, args=(worker_id, task_queue))
            worker.start()
            workers.append(worker)

        self.logger.debug("Waiting for tasks to complete")
        task_queue.join()
        self.logger.debug("Workers finished")
        for worker in workers:
            worker.join()

        self.logger.info(f"Completed matrix evaluation for {matrix_id}")

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
        self._save()
        self.logger.info(f"Matrix evaluation results saved to {self.output_file}")

        # Clean up all game workers
        for i, game in enumerate(self.game_pool):
            try:
                game.end(cleanup=True)
                self.logger.debug(f"Cleaned up game worker {i}")
            except Exception as e:
                self.logger.warning(f"Error cleaning up game worker {i}: {e}")

        self.logger.info("All game workers cleaned up")


def main(pvp_output_dir: Path, n_repetitions: int = 3, max_workers: int = 4):
    """Main function to evaluate PvP tournament matrices."""
    evaluator = PvPMatrixEvaluator(pvp_output_dir, n_repetitions, max_workers)
    return evaluator.evaluate_all_matrices()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate PvP tournament matrices")
    parser.add_argument("pvp_output_dir", type=Path, help="Path to PvP tournament output directory")
    parser.add_argument(
        "--repetitions", "-r", type=int, default=3, help="Number of repetitions per matrix cell (default: 3)"
    )
    parser.add_argument("--max-workers", "-w", type=int, default=4, help="Number of parallel game workers (default: 4)")

    args = parser.parse_args()
    main(args.pvp_output_dir, args.repetitions, args.max_workers)
