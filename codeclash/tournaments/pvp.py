"""
PvP training mode where multiple agents compete against each other.
"""

import json

from codeclash.agents import get_agent
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_WORK
from codeclash.games import get_game
from codeclash.games.game import CodeGame
from codeclash.tournaments.tournament import AbstractTournament
from codeclash.utils.environment import copy_to_container
from codeclash.utils.log import get_logger


class PvpTournament(AbstractTournament):
    def __init__(self, config: dict, *, cleanup: bool = False, push_agent: bool = False):
        super().__init__(config, name="PvpTournament")
        self.cleanup_on_end = cleanup
        self.push_agent = push_agent
        self.game: CodeGame = get_game(
            self.config,
            tournament_id=self.tournament_id,
            local_output_dir=self.local_output_dir,
        )
        self.agents: list[Player] = []
        for agent_conf in self.config["players"]:
            self.agents.append(self.get_agent(agent_conf, self.config["prompts"]))
        self.logger = get_logger(self.game.name)

    @property
    def scoreboard(self) -> list[tuple[int, str]]:
        return self._metadata.setdefault("scoreboard", [])

    @property
    def rounds(self) -> int:
        return self.config["tournament"]["rounds"]

    def get_metadata(self) -> dict:
        # will be saved in end()
        return {
            **super().get_metadata(),
            "scoreboard": self.scoreboard,
            "game": self.game.get_metadata(),
            "agents": [agent.get_metadata() for agent in self.agents],
        }

    def get_agent(self, agent_config: dict, prompts: dict) -> Player:
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

        return get_agent(agent_config, game_context, environment)

    def run(self) -> None:
        """Main execution function that runs all rounds."""
        try:
            for round_num in range(1, self.rounds + 1):
                self.run_training_round(round_num)
        finally:
            self.end()

    def run_training_round(self, round_num: int) -> None:
        """Execute a single training round."""
        # Run the game round and get results
        record = self.game.run_round(self.agents)

        # Handle bookkeeping that was previously in the game
        self.scoreboard.append(record.stats)
        self.logger.info(f"Round {round_num}:\n{record.stats}")

        # Create directory for round logs
        (self.game.log_local / "rounds" / str(round_num)).mkdir(parents=True, exist_ok=True)

        # Write logs to file
        for idx, lo in enumerate(record.data.logs):
            round_log_path = self.game.log_local / "rounds" / str(round_num) / f"sim_{idx}.log"
            round_log_path.write_text(lo)
        results_file = self.game.log_local / "rounds" / str(round_num) / "results.json"
        with open(results_file, "w") as f:
            json.dump(record.stats.model_dump(), fp=f, indent=2)

        # Copy log to agent environments
        for agent in self.agents:
            self.logger.info(f"Copying round {round_num} log(s) to {agent.name}'s container...")
            copy_to_container(
                agent.environment,
                self.game.log_local / "rounds" / str(round_num),
                f"logs/rounds/{round_num}/",
            )

        for agent in self.agents:
            self.run_agent(agent, round_num)

        self.logger.info("Round completed.")

    def run_agent(self, agent: Player, round_num: int) -> None:
        """Run a single agent for the current round."""
        agent.pre_run_hook(new_round=round_num)
        agent.run()
        agent.post_run_hook(round=round_num)

    def end(self) -> None:
        """Save output files, clean up game resources and push agents if requested."""
        with open(self.local_output_dir / "metadata.json", "w") as f:
            json.dump(self.game.get_metadata(), fp=f, indent=2)
        self.game.end(self.cleanup_on_end)
        if self.push_agent:
            for agent in self.agents:
                agent.push()
