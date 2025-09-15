"""
In single player mode, the agent runs always against its previous version.
"""

import copy
import json

from codeclash.agents import get_agent
from codeclash.agents.dummy_agent import Dummy
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_WORK, FILE_RESULTS
from codeclash.games import get_game
from codeclash.games.game import CodeGame
from codeclash.tournaments.tournament import AbstractTournament
from codeclash.tournaments.utils.git_utils import filter_git_diff
from codeclash.utils.environment import copy_to_container


class SinglePlayerTraining(AbstractTournament):
    def __init__(self, config: dict, *, cleanup: bool = False):
        super().__init__(config, name="SinglePlayerTraining")
        self.cleanup_on_end = cleanup
        self.game: CodeGame = get_game(
            self.config,
            tournament_id=self.tournament_id,
            local_output_dir=self.local_output_dir,
        )
        self.agent: Player = self.get_agent(self.config["player"], round=1)
        mirror_agent_config = copy.deepcopy(self.config["player"])
        mirror_agent_config["name"] = "mirror"
        self.mirror_agent: Player = self.get_agent(mirror_agent_config, round=0)

    @property
    def rounds(self) -> int:
        return self.config["tournament"]["rounds"]

    def get_metadata(self) -> dict:
        return {
            **super().get_metadata(),
            "game": self.game.get_metadata(),
            "agents": [self.agent.get_metadata(), self.mirror_agent.get_metadata()],
        }

    def get_game_context(self, agent_config: dict, *, round: int) -> GameContext:
        """Create a game context for an agent."""
        return GameContext(
            id=self.game.game_id,
            log_env=self.game.log_env,
            log_local=self.game.log_local,
            name=self.game.name,
            player_id=agent_config["name"],
            prompts=self.config["prompts"],
            round=round,
            rounds=self.rounds,
            working_dir=str(DIR_WORK),
        )

    def get_agent(self, agent_config: dict, round: int) -> Player:
        """Create an agent with environment and game context."""
        environment = self.game.get_environment(f"{self.game.game_id}.{agent_config['name']}")
        game_context = self.get_game_context(agent_config, round=round)
        return get_agent(agent_config, game_context, environment)

    def get_dummy_agent(self, player_config: dict) -> Player:
        """Create a dummy agent that does nothing."""
        return Dummy(
            player_config,
            environment=self.game.get_environment(f"{self.game.game_id}.dummy"),
            game_context=self.get_game_context(player_config, round=0),
        )

    def run(self):
        """Main execution function that runs all rounds."""
        try:
            for round_num in range(1, self.rounds + 1):
                self.run_training_round(round_num)
            if self.config["tournament"]["evaluate_matrix"]:
                self.evaluate()
        finally:
            self.end()

    def run_training_round(self, round_num: int) -> None:
        """Execute a single training round, i.e., run the game, then run the agent."""
        # Run the game round and get results
        stats = self.game.run_round([self.agent, self.mirror_agent], round_num)
        self.logger.info(stats)

        # Write log to file
        results_file = self.game.log_local / "rounds" / str(round_num) / FILE_RESULTS
        results_file.write_text(json.dumps(stats.to_dict(), indent=2))

        # Copy log to main agent environment only
        self.logger.info(f"Copying round {round_num} log(s) to {self.agent.name}'s container...")
        copy_to_container(
            self.agent.environment,
            self.game.log_local / "rounds" / str(round_num),
            f"logs/rounds/{round_num}/",
        )

        self.run_main_agent(round_num)
        mirror_agent_state = round_num - 1 if round_num > 1 else 0
        self.set_mirror_state_to_round(mirror_agent_state)

        self._save()

        self.logger.info("Round completed.")

    def run_main_agent(self, round_num: int):
        """Run the main agent for the current round."""
        self.agent.pre_run_hook(new_round=round_num)
        self.agent.run()
        self.agent.post_run_hook(round=round_num)

    def set_mirror_state_to_round(self, round_num: int):
        """Update mirror agent's codebase with the main agent's changes."""
        full_diff = self.agent.get_metadata()["diff"][round_num]
        full_diff = filter_git_diff(full_diff)
        self.mirror_agent.reset_and_apply_patch(full_diff)

    def _save(self) -> None:
        (self.local_output_dir / "metadata.json").write_text(json.dumps(self.get_metadata(), indent=2))

    def end(self):
        """Clean up game resources."""
        self._save()
        self.game.end(self.cleanup_on_end)

    def evaluate(self, n_repetitions: int = 3) -> None:
        """Evaluate the agent's performance by
        calculating the matrix of every round against each other.
        """
        p1_config = self.config["player"].copy()
        p1_config["name"] = "p1"
        p1 = self.get_dummy_agent(p1_config)

        p2_config = self.config["player"].copy()
        p2_config["name"] = "p2"
        p2 = self.get_dummy_agent(p2_config)
        matrix = {
            p1_round: {p2_round: [] for p2_round in range(0, self.rounds + 1)} for p1_round in range(0, self.rounds + 1)
        }
        for p1_round in range(0, self.rounds + 1):
            for p2_round in range(0, self.rounds + 1):
                self.logger.info(f"Evaluating agent at round {p1_round} against agent at round {p2_round}")
                p1_patch = self.agent.get_metadata()["diff"][p1_round] if p1_round > 0 else ""
                p2_patch = self.agent.get_metadata()["diff"][p2_round] if p2_round > 0 else ""
                p1.reset_and_apply_patch(p1_patch)
                p2.reset_and_apply_patch(p2_patch)
                for i_repetition in range(n_repetitions):
                    stats = self.game.run_round([p1, p2], round_num=int(f"{p1_round}{p2_round}{i_repetition}"))
                    self.logger.info(f"Round {p1_round} vs {p2_round} repetition {i_repetition} winner: {stats.winner}")
                    matrix[p1_round][p2_round].append(stats.winner)
        self.logger.info(f"Evaluation matrix: {matrix}")
        self._metadata.setdefault("evaluation", {})["matrix"] = matrix
