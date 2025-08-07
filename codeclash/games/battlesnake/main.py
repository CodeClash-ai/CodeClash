import subprocess
import time
from typing import Any

from codeclash.constants import LOGS_DIR
from codeclash.games.abstract import CodeGame


class BattleSnakeGame(CodeGame):
    name: str = "BattleSnake"
    url_gh: str = "git@github.com:emagedoc/BattleSnake.git"

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
        self.game_server = self.get_codebase()
        for cmd in [
            "cd game; go build -o battlesnake ./cli/battlesnake/main.go",
            "pip install -r requirements.txt",
        ]:
            subprocess.run(
                cmd,
                shell=True,
                cwd=self.game_server,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _cleanup_ports(self, ports: list[int]):
        """Clean up any existing processes on the specified ports"""
        for port in ports:
            try:
                result = subprocess.run(
                    f"lsof -ti :{port} | xargs -r kill", shell=True, capture_output=True
                )
                if result.returncode == 0:
                    self.logger.info(f"🧹 Cleaned up port {port}")
            except Exception as e:
                self.logger.warning(f"Error cleaning port {port}: {e}")
        time.sleep(0.5)

    def run_round(self, agents: list[Any]):
        super().run_round(agents)
        self.logger.info(f"▶️ Running {self.name} round {self.round}...")

        cmd = self.run_cmd_round
        server_processes, ports = [], []

        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background and keep track of the process
            process = subprocess.Popen(
                f"PORT={port} python main.py", shell=True, cwd=agent.codebase
            )
            server_processes.append(process)
            cmd += f" --url http://0.0.0.0:{port} -n {agent.name}"
            ports.append(port)

        time.sleep(1)

        cmd += f" -o {self.round_log_path}"
        subprocess.run(f"touch {self.round_log_path}", shell=True)
        self.logger.info(f"Running command: {cmd}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.game_server / "game",
                capture_output=True,
                text=True,
            )
            with open(self.round_log_path, "a") as log_file:
                log_file.write(result.stdout)
                if result.stderr:
                    log_file.write(result.stderr)
        finally:
            # Shut down all server processes
            self.logger.info("🛑 Shutting down player servers...")
            for process in server_processes:
                try:
                    process.terminate()
                except:
                    pass
            # Give processes time to die after cleanup
            time.sleep(1.5)
            self._cleanup_ports(ports)
            self.logger.info("✅ All player servers shut down")
        self.logger.info(f"✅ Completed {self.name} round {self.round}")

        # Copy round log to agents' codebases
        for agent in agents:
            copy_path = agent.codebase / LOGS_DIR / self.round_log_path.name
            copy_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.round_log_path, "rb") as src_file:
                with open(copy_path, "wb") as dest_file:
                    dest_file.write(src_file.read())
