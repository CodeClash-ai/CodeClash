"""Toggle a running container's internet access via iptables in its network namespace.

Ported from RevEngBench (reveng/utils/environment_internet_control.py), Linux-only path.
Used to disable internet DURING the agent's editing turn (so it can't look up solutions),
while leaving it on for setup (git fetch of the starting codebase) and the post-round push.
Loopback is always kept up, so localhost gameplay (bot servers on 0.0.0.0:PORT) is unaffected.
DNS is left reachable so container tools fail fast instead of hanging on resolution.

Host-side (nsenter + sudo iptables) so an in-container root agent cannot undo it. Composes with
Player._isolate_git — internet-off stops re-fetching, git-strip hides the already-cloned branches.
"""

import os
import subprocess
import threading

from minisweagent.environments.docker import DockerEnvironment

from codeclash.utils.log import get_logger

logger = get_logger(__name__)

_dns_lock = threading.Lock()
_container_dns: dict[str, set[str]] = {}


def _docker_pid(env: DockerEnvironment) -> str:
    return subprocess.run(
        [env.config.executable, "inspect", "--format", "{{.State.Pid}}", env.container_id],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _iptables(env: DockerEnvironment, rule_args: list[str]) -> None:
    """Run one iptables command in the container's net namespace (sudo nsenter on Linux)."""
    pid = _docker_pid(env)
    prefix = [] if os.getuid() == 0 else ["sudo", "-n"]
    subprocess.run([*prefix, "nsenter", "-t", pid, "-n", "iptables", *rule_args], check=True)


def _dns_servers(env: DockerEnvironment) -> set[str]:
    r = env.execute({"command": "grep '^nameserver' /etc/resolv.conf | awk '{print $2}'"})
    return {ip.strip() for ip in r["output"].splitlines() if ip.strip()}


def turn_off_internet(env: DockerEnvironment) -> None:
    """Drop all inbound/outbound traffic except loopback and DNS."""
    dns = _dns_servers(env)
    with _dns_lock:
        _container_dns[env.container_id] = dns
    for chain in ("OUTPUT", "INPUT"):
        _iptables(env, ["-I", chain, "-j", "DROP"])
    _iptables(env, ["-I", "OUTPUT", "-o", "lo", "-j", "ACCEPT"])
    _iptables(env, ["-I", "INPUT", "-i", "lo", "-j", "ACCEPT"])
    for ip in sorted(dns):
        _iptables(env, ["-I", "OUTPUT", "-d", ip, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
        _iptables(env, ["-I", "OUTPUT", "-d", ip, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])
        _iptables(env, ["-I", "INPUT", "-s", ip, "-p", "udp", "--sport", "53", "-j", "ACCEPT"])
        _iptables(env, ["-I", "INPUT", "-s", ip, "-p", "tcp", "--sport", "53", "-j", "ACCEPT"])
    logger.info("Internet disabled for container %s (loopback+DNS kept)", env.container_id[:12])


def turn_on_internet(env: DockerEnvironment) -> None:
    """Remove the drop rules inserted by turn_off_internet (restores full connectivity)."""
    with _dns_lock:
        dns = _container_dns.pop(env.container_id, set())
    for ip in sorted(dns):
        _iptables(env, ["-D", "OUTPUT", "-d", ip, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
        _iptables(env, ["-D", "OUTPUT", "-d", ip, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])
        _iptables(env, ["-D", "INPUT", "-s", ip, "-p", "udp", "--sport", "53", "-j", "ACCEPT"])
        _iptables(env, ["-D", "INPUT", "-s", ip, "-p", "tcp", "--sport", "53", "-j", "ACCEPT"])
    _iptables(env, ["-D", "OUTPUT", "-o", "lo", "-j", "ACCEPT"])
    _iptables(env, ["-D", "INPUT", "-i", "lo", "-j", "ACCEPT"])
    for chain in ("OUTPUT", "INPUT"):
        _iptables(env, ["-D", chain, "-j", "DROP"])
    logger.info("Internet restored for container %s", env.container_id[:12])
