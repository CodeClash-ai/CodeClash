import json
import random
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code, create_file_in_container


class ChessArena(CodeArena):
    name: str = "Chess"
    description: str = """Chess is a strategic board game where you improve a chess engine (Kojiro) to compete against other engines.
Your engine is written in C++ and uses the UCI (Universal Chess Interface) protocol.
You can modify the evaluation function, search algorithms, move ordering, and other aspects of the engine to improve its strength.
The engine source code is located in the `src/` directory, and you compile it using `make native`.
IMPORTANT: Do not modify the executable name in the Makefile (keep `EXE = kojiro`). The executable must be named `kojiro`."""
    submission: str = "src/"
    default_args: dict = {
        "time_control": "1+0.01",  
    }

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        
        # Get time control from config
        time_control = self.game_config.get("args", self.default_args).get("time_control", self.default_args["time_control"])
        
        # Build base Fastchess command
        self.run_cmd_base = f"fastchess -each tc={time_control}"
        
        # Store time control for reference
        self.time_control = time_control
        
        self.logger.debug(f"Initialized ChessArena with time control: {time_control}")

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        """
        Validate that agent's Kojiro codebase compiles successfully.
        """
        # Check that src/ directory exists
        ls_result = agent.environment.execute("ls")
        if "src" not in ls_result["output"]:
            return False, "There should be a `src/` directory in the workspace"

        # Compile the engine 
        self.logger.debug(f"Compiling Kojiro for agent {agent.name}")
        compile_result = agent.environment.execute(
            "cd src && make native",
            timeout=120,  # 2 minute timeout for compilation
        )

        if compile_result["returncode"] != 0:
            error_output = compile_result.get("output", "Unknown compilation error")
            # Truncate very long error messages
            if len(error_output) > 1000:
                error_output = error_output[:1000] + "\n... (truncated)"
            return False, f"Compilation failed:\n{error_output}"

        # Verify executable was created
        kojiro_check = agent.environment.execute("ls src/kojiro")
        if kojiro_check["returncode"] != 0 or "kojiro" not in kojiro_check["output"]:
            return False, "Compilation succeeded but executable 'kojiro' not found in src/"

        self.logger.info(f"Agent {agent.name} passed validation: Kojiro compiles successfully")
        return True, None

    def _compile_engines_in_game_container(self, agents: list[Player]) -> dict[str, str]:
        """
        Recompile each agent's engine in the game container and return engine paths.
        
        Returns:
            dict mapping agent name to engine executable path (only successfully compiled agents)
        """
        engine_paths = {}
        failed_agents = []
        
        for agent in agents:
            src_dir = f"/{agent.name}/src"
            self.logger.debug(f"Compiling Kojiro for {agent.name} in game container")
            
            compile_result = self.environment.execute(
                f"cd {src_dir} && make native",
                timeout=120,  # 2 minute timeout for compilation
            )
            
            if compile_result["returncode"] != 0:
                error_output = compile_result.get("output", "Unknown compilation error")
                if len(error_output) > 1000:
                    error_output = error_output[:1000] + "\n... (truncated)"
                self.logger.warning(f"Failed to compile {agent.name} in game container, skipping:\n{error_output}")
                failed_agents.append(agent.name)
                continue
            
            # Verify executable exists (executable name is fixed as 'kojiro' per Makefile and prompt constraints)
            engine_path = f"{src_dir}/kojiro"
            check_result = self.environment.execute(f"test -f {engine_path} && echo 'exists'")
            if "exists" not in check_result["output"]:
                self.logger.warning(
                    f"Compilation succeeded but executable 'kojiro' not found at {engine_path} for {agent.name}, skipping"
                )
                failed_agents.append(agent.name)
                continue
            
            engine_paths[agent.name] = engine_path
            self.logger.debug(f"Successfully compiled {agent.name}, engine at {engine_path}")
        
        if failed_agents:
            self.logger.warning(f"Failed to compile {len(failed_agents)} agent(s): {failed_agents}")
        
        return engine_paths
    
    def _build_match_pairings(self, agents: list[Player]) -> list[tuple[Player, Player]]:
        """
        Build match pairings for sims_per_round simulations.
        
        Strategy: Round-robin style - pair agents and repeat as needed.
        For each simulation, randomly select two different agents.
        
        Returns:
            List of (agent1, agent2) tuples
        """
        sims = self.game_config["sims_per_round"]
        pairings = []
        
        # Generate pairings: for each simulation, pick two random agents
        for _ in range(sims):
            agent1, agent2 = random.sample(agents, 2)
            pairings.append((agent1, agent2))
        
        return pairings
    
    def _run_single_match(self, agent1: Player, agent2: Player, engine1_path: str, engine2_path: str, idx: int):
        """
        Run a single Fastchess match between two engines.
        
        Args:
            agent1: First agent
            agent2: Second agent
            engine1_path: Path to first engine executable in game container
            engine2_path: Path to second engine executable in game container
            idx: Simulation index for output file naming
        """

        output_file = self.log_env / f"match_{idx}.pgn"
        
        # Ensure log directory exists
        self.environment.execute(f"mkdir -p {self.log_env}")
        
        cmd = (
            f"{self.run_cmd_base} "
            f"-engine cmd={engine1_path} name={agent1.name} "
            f"-engine cmd={engine2_path} name={agent2.name} "
            f"-rounds 1 "
            f"-pgnout file={str(output_file)}"
        )
        
        self.logger.debug(f"Running match {idx}: {agent1.name} vs {agent2.name}")
        self.logger.debug(f"Fastchess command: {cmd}")
        self.logger.debug(f"Output file path: {output_file}")
        
        try:
            response = self.environment.execute(cmd, timeout=300)  # 5 minute timeout per match
            if response["returncode"] != 0:
                error_output = response.get('output', '')[:1000]
                self.logger.warning(
                    f"Match {idx} ({agent1.name} vs {agent2.name}) failed with exit code {response['returncode']}:\n{error_output}"
                )
            else:
                # Verify PGN file was created
                check_result = self.environment.execute(f"test -f {str(output_file)} && echo 'exists'")
                if "exists" not in check_result["output"]:
                    self.logger.warning(f"Match {idx} completed but PGN file not found at {output_file}")
                    # Debug: list files in log directory
                    ls_result = self.environment.execute(f"ls -la {self.log_env}")
                    self.logger.debug(f"Files in {self.log_env}: {ls_result.get('output', '')[:500]}")
                else:
                    self.logger.debug(f"Match {idx} PGN file verified at {output_file}")
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Match {idx} ({agent1.name} vs {agent2.name}) timed out after 5 minutes")
    
    def execute_round(self, agents: list[Player]):
        """
        Execute competition phase - run Fastchess matches between agents.
        """
        assert len(agents) >= 2, "Chess requires at least two players"
        
        # Recompile engines in game container
        self.logger.info("Recompiling engines in game container...")
        engine_paths = self._compile_engines_in_game_container(agents)
        
        if len(engine_paths) < 2:
            self.logger.warning(f"Only {len(engine_paths)} agent(s) compiled successfully, need at least 2. Skipping round.")
            return
        
        # Build match pairings using only successfully compiled agents
        compiled_agents = [agent for agent in agents if agent.name in engine_paths]
        self.logger.info(f"Building match pairings for {self.game_config['sims_per_round']} simulations...")
        pairings = self._build_match_pairings(compiled_agents)
        
        # Store pairings to file for retrieval in get_results()
        pairings_file = self.log_env / "pairings.json"
        pairings_data = [
            {"match_idx": idx, "agent1": agent1.name, "agent2": agent2.name}
            for idx, (agent1, agent2) in enumerate(pairings)
        ]
        # Write to container's log directory
        pairings_json = json.dumps(pairings_data, indent=2)
        create_file_in_container(
            container=self.environment,
            content=pairings_json,
            dest_path=str(pairings_file),
        )
        self.logger.debug(f"Stored pairings to {pairings_file}")
        
        # Run matches in parallel
        self.logger.info(f"Running {len(pairings)} matches in parallel...")
        with ThreadPoolExecutor(max_workers=min(20, len(pairings))) as executor:
            futures = [
                executor.submit(
                    self._run_single_match,
                    agent1,
                    agent2,
                    engine_paths[agent1.name],
                    engine_paths[agent2.name],
                    idx,
                )
                for idx, (agent1, agent2) in enumerate(pairings)
            ]
            
            # Collect results with progress bar
            for future in tqdm(as_completed(futures), total=len(futures), desc="Chess matches"):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Match execution failed: {e}", exc_info=True)
        
        self.logger.info("All matches completed")

    def _parse_all_games_in_pgn(self, pgn_content: str) -> list[tuple[str | None, str, str]]:
        """
        Parse all games from a PGN file.
        
        Args:
            pgn_content: Content of the PGN file (may contain multiple games)
        
        Returns:
            List of (result, white_agent, black_agent) tuples
            result is agent name if that agent won, RESULT_TIE for draws, or None if incomplete
        """
        games = []
        
        # Split PGN into individual games (games are separated by blank lines)
        # Look for [Event ...] tags which mark the start of each game
        game_blocks = re.split(r'(?=\[Event\s+")', pgn_content)
        
        for game_block in game_blocks:
            game_block = game_block.strip()
            if not game_block:
                continue
            
            # Skip if this block doesn't look like a game (no [White] or [Black] tags)
            if '[White' not in game_block or '[Black' not in game_block:
                continue
            
            # Extract White and Black agent names
            white_match = re.search(r'\[White\s+"([^"]+)"\]', game_block)
            black_match = re.search(r'\[Black\s+"([^"]+)"\]', game_block)
            result_match = re.search(r'\[Result\s+"([^"]+)"\]', game_block)
            
            if not white_match or not black_match:
                continue  # Skip incomplete game headers
            
            white_agent = white_match.group(1)
            black_agent = black_match.group(1)
            
            if not result_match:
                games.append((None, white_agent, black_agent))
                continue
            
            result = result_match.group(1)
            
            # Parse result: "1-0" = White wins, "0-1" = Black wins, "1/2-1/2" = draw, "*" = incomplete
            if result == "1-0":
                games.append((white_agent, white_agent, black_agent))
            elif result == "0-1":
                games.append((black_agent, white_agent, black_agent))
            elif result == "1/2-1/2":
                games.append((RESULT_TIE, white_agent, black_agent))
            elif result == "*":
                games.append((None, white_agent, black_agent))
            else:
                self.logger.warning(f"Unknown result format: {result}")
                games.append((None, white_agent, black_agent))
        
        return games
    
    def _aggregate_match_result(self, game_results: list[tuple[str | None, str, str]], agent1_name: str, agent2_name: str) -> str | None:
        """
        Aggregate results from multiple games into a single match result.
        
        Args:
            game_results: List of (result, white_agent, black_agent) tuples from _parse_all_games_in_pgn
            agent1_name: Name of first agent (for reference)
            agent2_name: Name of second agent (for reference)
        
        Returns:
            Match winner (agent name), RESULT_TIE for draw, or None if match incomplete
        """
        if not game_results:
            return None
        
        if len(game_results) == 1:
            self.logger.warning(f"Match has only 1 game, expected 2. Using single game result.")
            return game_results[0][0]
        
        if len(game_results) > 2:
            self.logger.warning(f"Match has {len(game_results)} games, expected 2. Using first 2 games.")
            game_results = game_results[:2]
        
        # Count wins for each agent
        agent1_wins = 0
        agent2_wins = 0
        draws = 0
        incomplete = 0
        
        for result, white_agent, black_agent in game_results:
            if result is None:
                incomplete += 1
            elif result == RESULT_TIE:
                draws += 1
            elif result == agent1_name:
                agent1_wins += 1
            elif result == agent2_name:
                agent2_wins += 1
            else:
                # Result is for an agent not in this match (shouldn't happen, but handle gracefully)
                self.logger.warning(f"Unexpected result agent '{result}' in match between {agent1_name} and {agent2_name}")
        
        # If both games incomplete, match is incomplete
        if incomplete == 2:
            return None
        
        # If one game incomplete, use the other game's result
        if incomplete == 1:
            for result, _, _ in game_results:
                if result is not None:
                    return result
            return None
        
        # Determine match winner based on wins
        if agent1_wins > agent2_wins:
            return agent1_name
        elif agent2_wins > agent1_wins:
            return agent2_name
        else:
            # Equal wins (could be 1-1, 0-0 with draws, etc.) = match draw
            return RESULT_TIE
    
    def _load_pairings(self, round_num: int) -> dict[int, tuple[str, str]]:
        """
        Load match pairings from stored JSON file.
        
        Returns:
            Dict mapping match_idx to (agent1_name, agent2_name) tuple
        """
        pairings_file = self.log_round(round_num) / "pairings.json"
        
        try:
            with open(pairings_file) as f:
                pairings_data = json.load(f)
            
            pairings = {
                item["match_idx"]: (item["agent1"], item["agent2"])
                for item in pairings_data
            }
            return pairings
        except FileNotFoundError:
            self.logger.error(f"Pairings file not found: {pairings_file}")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse pairings file: {e}")
            return {}
    
    def _read_all_match_results(self, round_num: int, agents: list[Player]) -> list[tuple[str | None, str, str]]:
        """
        Read all match result files and parse them.
        
        Returns:
            List of (winner, agent1_name, agent2_name) tuples
            winner is None if match failed or incomplete
        """
        match_results = []
        
        # Load pairings from stored file
        pairings = self._load_pairings(round_num)
        if not pairings:
            self.logger.warning("No pairings found, cannot parse match results")
            return []
        
        # Build set of valid agent names for validation
        valid_agent_names = {agent.name for agent in agents}
        
        sims = self.game_config["sims_per_round"]
        
        for idx in range(sims):
            # Get agent names from stored pairings
            if idx not in pairings:
                self.logger.warning(f"Match {idx} pairing not found in pairings file, skipping")
                continue
            
            agent1_name, agent2_name = pairings[idx]
            
            # Validate agent names exist in agents list
            if agent1_name not in valid_agent_names or agent2_name not in valid_agent_names:
                self.logger.warning(
                    f"Match {idx}: Invalid agent names ({agent1_name}, {agent2_name}) not in agents list, skipping"
                )
                continue
            
            pgn_file = self.log_round(round_num) / f"match_{idx}.pgn"
            
            self.logger.debug(f"Looking for PGN file at: {pgn_file}")
            
            try:
                if not pgn_file.exists():
                    self.logger.warning(f"PGN file does not exist: {pgn_file}")
                    # List files in the directory for debugging
                    if self.log_round(round_num).exists():
                        files = list(self.log_round(round_num).iterdir())
                        self.logger.debug(f"Files in {self.log_round(round_num)}: {[f.name for f in files]}")
                    else:
                        self.logger.warning(f"Round directory does not exist: {self.log_round(round_num)}")
                    continue
                
                with open(pgn_file) as f:
                    pgn_content = f.read()
                
                # Parse all games from PGN file
                game_results = self._parse_all_games_in_pgn(pgn_content)
                
                # Aggregate game results into match result
                winner = self._aggregate_match_result(game_results, agent1_name, agent2_name)
                match_results.append((winner, agent1_name, agent2_name))
                
            except FileNotFoundError:
                self.logger.warning(f"Match {idx} result file not found, skipping")
                continue
            except Exception as e:
                self.logger.warning(f"Error parsing match {idx} result: {e}")
                continue
        
        return match_results
    
    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        """
        Parse Fastchess results and determine winners.
        """
        # Debug: Check if round directory exists
        round_dir = self.log_round(round_num)
        self.logger.debug(f"get_results: Looking for round directory at {round_dir}")
        if round_dir.exists():
            files = list(round_dir.iterdir())
            self.logger.debug(f"get_results: Files in round directory: {[f.name for f in files]}")
        else:
            self.logger.warning(f"get_results: Round directory does not exist: {round_dir}")
        
        # Read and parse all match results
        match_results = self._read_all_match_results(round_num, agents)
        
        # Count wins per agent
        scores = defaultdict(int)
        valid_matches = 0
        for winner, agent1_name, agent2_name in match_results:
            if winner is None:
                # Incomplete or failed match - skip it
                continue
            elif winner == RESULT_TIE:
                # Draws count as 0 points for both, but still a valid match
                valid_matches += 1
                continue
            else:
                # Winner exists - give 1 point
                scores[winner] += 1
                valid_matches += 1
        
        # Determine overall winner
        if valid_matches == 0:
            self.logger.warning("No valid match results found (all matches failed or incomplete)")
            stats.winner = RESULT_TIE
            stats.scores = {agent.name: 0 for agent in agents}
        elif not scores:
            # All valid matches were draws
            self.logger.info(f"All {valid_matches} matches were draws")
            stats.winner = RESULT_TIE
            stats.scores = {agent.name: 0 for agent in agents}
        else:
            # Find agent(s) with maximum score
            max_score = max(scores.values())
            winners = [name for name, score in scores.items() if score == max_score]
            
            if len(winners) > 1:
                stats.winner = RESULT_TIE
            else:
                stats.winner = winners[0]
            
            # Update stats object
            stats.scores = dict(scores)
            
            # Ensure all agents have scores (even if 0)
            for agent in agents:
                stats.scores[agent.name] = scores.get(agent.name, 0)
                stats.player_stats[agent.name].score = scores.get(agent.name, 0)
        
        self.logger.info(f"Round {round_num} results: winner={stats.winner}, scores={stats.scores}")

