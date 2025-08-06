import subprocess
from pathlib import Path

from codeclash.games.abstract import CodeGame
from codeclash.games.utils import clone


class BattlesnakeGame(CodeGame):
    name: str = "Battlesnake"

    url_server: str = "git@github.com:emagedoc/Battlesnake.git"
    url_starter: str = "git@github.com:emagedoc/Battlesnake-starter.git"
    build_server: str = "go build -o battlesnake ./cli/battlesnake/main.go"
    run_cmd_player: str = "python main.py"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./battlesnake play"
        for arg, val in config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def setup(self):
        self.logger.info(f"🐍 Setting up {self.name} game environment...")
        self.server_path = clone(self.url_server)
        self.artifacts.append(self.server_path)
        subprocess.run(self.build_server, shell=True, cwd=self.server_path)
        self.logger.info(f"✅ Cloned and built {self.name} local client")

    def setup_codebase(self, dest: str) -> Path:
        dest = clone(self.url_starter, dest)
        self.artifacts.append(dest)
        return dest

    def run_round(self, agents: list[any]) -> Path:
        super().run_round(agents)
        self.logger.info(f"▶️ Running {self.name} round {self.round}...")
        cmd = self.run_cmd_round
        server_processes = []

        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background and keep track of the process
            process = subprocess.Popen(
                f"PORT={port} {self.run_cmd_player}", shell=True, cwd=agent.codebase
            )
            server_processes.append(process)
            cmd += f" --url http://0.0.0.0:{port} -n {agent.name}"

        # Give servers a moment to start up
        import time

        time.sleep(1)

        cmd += f" -o {self.round_log_path}"
        subprocess.run(f"touch {self.round_log_path}", shell=True)
        self.logger.info(f"Running command: {cmd}")

        try:
            result = subprocess.run(
                cmd, shell=True, cwd=self.server_path, capture_output=True, text=True
            )
            with open(self.round_log_path, "a") as log_file:
                log_file.write(result.stdout)
                if result.stderr:
                    log_file.write(result.stderr)
        finally:
            # Shut down all server processes
            self.logger.info("🛑 Shutting down player servers...")
            for process in server_processes:
                if process.poll() is None:  # Process is still running
                    process.terminate()
                    try:
                        process.wait(
                            timeout=5
                        )  # Wait up to 5 seconds for graceful shutdown
                    except subprocess.TimeoutExpired:
                        process.kill()  # Force kill if it doesn't shut down gracefully
            self.logger.info("✅ All player servers shut down")
        self.logger.info(f"✅ Completed {self.name} round {self.round}")

        return self.round_log_path
