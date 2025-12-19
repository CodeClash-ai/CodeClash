"""
PvP training mode where multiple agents compete against each other.
"""

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codeclash.agents import get_agent
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.arenas import get_arena
from codeclash.arenas.arena import CodeArena
from codeclash.constants import DIR_LOGS, DIR_WORK, FILE_RESULTS, OPPONENT_CODEBASES_DIR_NAME
from codeclash.tournaments.tournament import AbstractTournament
from codeclash.utils.atomic_write import atomic_write
from codeclash.utils.aws import is_running_in_aws_batch, s3_log_sync
from codeclash.utils.environment import copy_between_containers, copy_to_container


class PvpTournament(AbstractTournament):
    def __init__(
        self,
        config: dict,
        *,
        output_dir: Path,
        cleanup: bool = False,
        push: bool = False,
        keep_containers: bool = False,
    ):
        metadata_file = output_dir / "metadata.json"
        if metadata_file.exists():
            raise FileExistsError(f"Metadata file already exists: {metadata_file}")

        super().__init__(config, name="PvpTournament", output_dir=output_dir)
        self.cleanup_on_end = cleanup
        self.game: CodeArena = get_arena(
            self.config,
            tournament_id=self.tournament_id,
            local_output_dir=self.local_output_dir,
            keep_containers=keep_containers,
        )
        self.agents: list[Player] = []
        for agent_conf in self.config["players"]:
            self.agents.append(self.get_agent(agent_conf, self.config["prompts"], push=push))

    @property
    def metadata_file(self) -> Path:
        return self.local_output_dir / "metadata.json"

    @property
    def rounds(self) -> int:
        return self.config["tournament"]["rounds"]

    @property
    def transparent(self) -> bool:
        return self.config["tournament"].get("transparent", False)

    def get_metadata(self) -> dict:
        # will be saved in end()
        return {
            **super().get_metadata(),
            "game": self.game.get_metadata(),
            "agents": [agent.get_metadata() for agent in self.agents],
        }

    def get_agent(self, agent_config: dict, prompts: dict, push: bool) -> Player:
        """Create an agent with environment and game context."""
        environment = self.game.get_environment(f"{self.game.game_id}.{agent_config['name']}")

        game_context = GameContext(
            id=self.game.game_id,
            log_env=self.game.log_env,
            log_local=self.game.log_local,
            name=self.game.name,
            player_id=agent_config["name"],
            prompts=prompts,
            round=1,
            rounds=self.rounds,
            working_dir=str(DIR_WORK),
        )

        return get_agent(agent_config, game_context, environment, push=push)

    def run(self) -> None:
        """Main execution function that runs all rounds."""
        try:
            self.run_competition_phase(0)  # Initial round with identical codebases
            for round_num in range(1, self.rounds + 1):
                self.run_edit_phase(round_num)
                self.run_competition_phase(round_num)
            # Need to separately compress the last round, because
            # in run_edit_phase we always only compress the previous round
            self._compress_round_folder(self.rounds)
        finally:
            self.end()

    def run_competition_phase(self, round_num: int) -> None:
        # Run the game round and get results
        stats = self.game.run_round(self.agents, round_num)
        self.logger.info(stats)

        self._metadata.setdefault("round_stats", {})[round_num] = stats.to_dict()

        # Create directory for round logs
        (self.game.log_local / "rounds" / str(round_num)).mkdir(parents=True, exist_ok=True)

        # Write logs to file
        results_file = self.game.log_local / "rounds" / str(round_num) / FILE_RESULTS
        results_file.write_text(json.dumps(stats.to_dict(), indent=2))

        self._save()

    def run_edit_phase(self, round_num: int) -> None:
        """Execute a single training round."""
        # Copy log to agent environments
        for agent in self.agents:
            self.logger.info(f"Copying round {round_num - 1} log(s) to {agent.name}'s container...")
            copy_to_container(
                agent.environment,
                self.game.log_local / "rounds" / str(round_num - 1),
                DIR_LOGS / "rounds" / str(round_num - 1),
            )
        self._compress_round_folder(round_num - 1)

        if self.transparent:
            # Copy agent's codebase to all other agents
            self.logger.info("Transparent mode enabled: copying codebases between agents...")
            for idx in range(len(self.agents)):
                agent = self.agents[idx]
                opponents = [a for j, a in enumerate(self.agents) if j != idx]
                self.logger.info(f"Copying {agent.name}'s codebase to other agents...")
                for opp in opponents:
                    copy_between_containers(
                        agent.environment,
                        opp.environment,
                        agent.environment.config.cwd,
                        f"/{OPPONENT_CODEBASES_DIR_NAME}/{agent.name}/",
                    )

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.run_agent, agent, round_num) for agent in self.agents]
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    self.logger.critical(f"Agent execution failed: {e}", exc_info=True)
                    raise

        self._save()
        self.logger.info("Round completed.")

    def run_agent(self, agent: Player, round_num: int) -> None:
        """Run a single agent for the current round."""
        agent.pre_run_hook(new_round=round_num)
        agent.run()
        agent.post_run_hook(round=round_num)

    def _save(self) -> None:
        self.local_output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(self.metadata_file, json.dumps(self.get_metadata(), indent=2))
        self.logger.debug(f"Metadata saved to {self.metadata_file}")
        if is_running_in_aws_batch():
            s3_log_sync(self.local_output_dir, logger=self.logger)

    def _compress_round_logs(self) -> None:
        rounds_dir = self.game.log_local / "rounds"
        if not rounds_dir.exists():
            return

        cmd = [
            "tar",
            "-zcf",
            str(self.game.log_local / "rounds.tar.gz"),
            "-C",
            str(self.game.log_local),
            "rounds",
        ]
        self.logger.info(f"Compressing round logs, this might take a while... ({' '.join(cmd)})")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {result.returncode}:\n{result.stderr}")
        # Remove the original round logs
        shutil.rmtree(self.game.log_local / "rounds")
        self.logger.info("Round logs compressed successfully")

    def _compress_round_folder(self, round_num_zero_indexed: int) -> None:
        round_dir = self.game.log_local / "rounds" / str(round_num_zero_indexed)
        if not round_dir.exists():
            return

        archive = self.game.log_local / "rounds" / f"round_{round_num_zero_indexed}.tar.gz"
        cmd = [
            "tar",
            "-zcf",
            str(archive),
            "-C",
            str(round_dir.parent),
            str(round_num_zero_indexed),
        ]
        self.logger.info(
            f"Compressing round {round_num_zero_indexed} logs, this might take a while... ({' '.join(cmd)})"
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {result.returncode}:\n{result.stderr}")
        self.logger.debug("Removing %s", round_dir)
        shutil.rmtree(round_dir)
        self.logger.info(f"Round {round_num_zero_indexed} logs compressed successfully")

    def end(self) -> None:
        """Save output files, clean up game resources and push agents if requested."""
        self._save()
        self.game.end(self.cleanup_on_end)
        self.cleanup_handlers()
