"""
PvP training mode where multiple agents compete against each other.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codeclash.agents import get_agent
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_WORK, FILE_RESULTS
from codeclash.games import get_game
from codeclash.games.game import CodeGame
from codeclash.tournaments.tournament import AbstractTournament
from codeclash.utils.environment import copy_to_container


class PvpTournament(AbstractTournament):
    def __init__(self, config: dict, *, cleanup: bool = False, push: bool = False, output_dir: Path | None = None):
        super().__init__(config, name="PvpTournament", output_dir=output_dir)
        self.cleanup_on_end = cleanup
        self.game: CodeGame = get_game(
            self.config,
            tournament_id=self.tournament_id,
            local_output_dir=self.local_output_dir,
        )
        self.agents: list[Player] = []
        for agent_conf in self.config["players"]:
            self.agents.append(self.get_agent(agent_conf, self.config["prompts"], push=push))

    @property
    def rounds(self) -> int:
        return self.config["tournament"]["rounds"]

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
            self.run_competition_phase(0)  # Warm up (doesn't count)
            for round_num in range(1, self.rounds + 1):
                self.run_edit_phase(round_num)
                self.run_competition_phase(round_num)
        finally:
            self.end()

    def run_competition_phase(self, round_num: int) -> None:
        # Run the game round and get results
        stats = self.game.run_round(self.agents, round_num)
        self.logger.info(stats)

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
                f"logs/rounds/{round_num - 1}/",
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
        (self.local_output_dir / "metadata.json").write_text(json.dumps(self.get_metadata(), indent=2))

    def end(self) -> None:
        """Save output files, clean up game resources and push agents if requested."""
        self._save()
        self.game.end(self.cleanup_on_end)
