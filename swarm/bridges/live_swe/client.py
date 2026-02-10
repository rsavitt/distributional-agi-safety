"""Client for interfacing with mini-swe-agent processes and trajectory files.

Supports two modes:
- **Online**: spawns a mini-swe-agent subprocess and parses its output in real time
- **Offline**: parses existing trajectory JSON files (e.g. from SWE-bench runs)
"""

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from swarm.bridges.live_swe.events import (
    StepEvent,
    TrajectoryEvent,
)

logger = logging.getLogger(__name__)


# --- Regex patterns for detecting tool creation and usage in bash output ---

# Matches heredoc-style file creation: cat <<'EOF' > path.py / cat << EOF > path.py
TOOL_CREATION_HEREDOC = re.compile(
    r"""cat\s+<<\s*['"]?EOF['"]?\s*>\s*(\S+\.py)""",
    re.IGNORECASE,
)

# Matches redirect-style file creation: echo/printf ... > path.py
TOOL_CREATION_REDIRECT = re.compile(
    r"""(?:echo|printf)\s+.*>\s*(\S+\.py)""",
    re.IGNORECASE,
)

# Matches tee-based creation: tee path.py
TOOL_CREATION_TEE = re.compile(
    r"""tee\s+(\S+\.py)""",
    re.IGNORECASE,
)

# Matches python script execution: python path.py [args]
TOOL_USAGE_PYTHON = re.compile(
    r"""python[3]?\s+(\S+\.py)""",
    re.IGNORECASE,
)

# Matches bash/sh script execution: bash path.sh or sh path.sh
TOOL_USAGE_SHELL = re.compile(
    r"""(?:bash|sh)\s+(\S+\.sh)""",
    re.IGNORECASE,
)

# Matches chmod +x and execution: ./path.py or ./path.sh
TOOL_USAGE_DIRECT = re.compile(
    r"""\.\/(\S+\.(?:py|sh))""",
)

# Matches a successful completion message
COMPLETION_PATTERN = re.compile(
    r"""(?:resolved|fixed|completed|done|passing|success)""",
    re.IGNORECASE,
)


@dataclass
class LiveSWEClientConfig:
    """Configuration for the LiveSWE client."""

    mini_cli_path: str = "mini-swe-agent"
    config_path: str = ""
    step_limit: int = 50
    cost_limit_usd: float = 5.0
    timeout_seconds: float = 600.0
    trajectory_dir: str = ""


class LiveSWEClient:
    """Client for running and parsing mini-swe-agent tasks.

    Online mode:
        client = LiveSWEClient(config)
        trajectory = client.run_task("Fix the bug in foo.py", "agent_1")

    Offline mode:
        client = LiveSWEClient(config)
        trajectory = client.parse_trajectory("/path/to/trajectory.json")
    """

    def __init__(self, config: Optional[LiveSWEClientConfig] = None) -> None:
        self.config = config or LiveSWEClientConfig()

    def run_task(self, task: str, agent_id: str = "") -> TrajectoryEvent:
        """Run a task via mini-swe-agent subprocess (online mode).

        Args:
            task: Task description / issue text
            agent_id: Identifier for the agent

        Returns:
            TrajectoryEvent summarizing the run

        Raises:
            FileNotFoundError: If mini-swe-agent CLI is not found
            subprocess.TimeoutExpired: If the run exceeds timeout
        """
        cmd = [self.config.mini_cli_path]
        if self.config.config_path:
            cmd.extend(["--config", self.config.config_path])
        cmd.extend([
            "--step-limit", str(self.config.step_limit),
            "--cost-limit", str(self.config.cost_limit_usd),
            "--task", task,
        ])

        start_time = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
            duration = time.monotonic() - start_time
        except FileNotFoundError:
            logger.error("mini-swe-agent CLI not found at: %s", self.config.mini_cli_path)
            raise
        except subprocess.TimeoutExpired:
            logger.error("mini-swe-agent timed out after %.1fs", self.config.timeout_seconds)
            raise

        # Try to find the trajectory JSON in the output or trajectory dir
        trajectory_data = self._find_trajectory_output(result.stdout, result.stderr)
        if trajectory_data:
            traj = self._parse_trajectory_data(trajectory_data, agent_id)
            traj.duration_seconds = duration
            traj.task = task
            return traj

        # Fallback: parse stdout directly as step output
        steps = self._parse_stdout_steps(result.stdout, agent_id)
        tools_created = []
        for step in steps:
            tools_created.extend(step.tool_creations)

        success = result.returncode == 0 and bool(
            COMPLETION_PATTERN.search(result.stdout)
        )

        return TrajectoryEvent(
            total_steps=len(steps),
            total_cost_usd=0.0,
            tools_created=tools_created,
            success=success,
            duration_seconds=duration,
            steps=steps,
            agent_id=agent_id,
            task=task,
        )

    def parse_trajectory(self, path: str) -> TrajectoryEvent:
        """Parse an existing trajectory JSON file (offline mode).

        Args:
            path: Path to the trajectory JSON file

        Returns:
            TrajectoryEvent summarizing the trajectory

        Raises:
            FileNotFoundError: If the file does not exist
            json.JSONDecodeError: If the file is not valid JSON
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Trajectory file not found: {path}")

        with open(filepath) as f:
            data = json.load(f)

        agent_id = data.get("agent_id", filepath.stem)
        return self._parse_trajectory_data(data, agent_id)

    def _parse_trajectory_data(
        self, data: dict, agent_id: str
    ) -> TrajectoryEvent:
        """Parse trajectory data dict into a TrajectoryEvent."""
        # Handle both flat and nested formats
        messages = data.get("messages", data.get("trajectory", []))
        steps: List[StepEvent] = []

        for i, msg in enumerate(messages):
            step = self._parse_step(msg, i, agent_id)
            if step is not None:
                steps.append(step)

        tools_created = []
        for step in steps:
            tools_created.extend(step.tool_creations)

        # Detect success from the data
        success = data.get("resolved", data.get("success", False))
        if isinstance(success, str):
            success = success.lower() in ("true", "yes", "resolved")

        cost = data.get("cost", data.get("total_cost_usd", 0.0))
        if isinstance(cost, str):
            try:
                cost = float(cost)
            except ValueError:
                cost = 0.0

        return TrajectoryEvent(
            total_steps=len(steps),
            total_cost_usd=cost,
            tools_created=tools_created,
            success=bool(success),
            duration_seconds=data.get("duration_seconds", 0.0),
            steps=steps,
            agent_id=agent_id,
            task=data.get("task", data.get("issue", "")),
        )

    def _parse_step(
        self, message: dict, step_index: int, agent_id: str
    ) -> Optional[StepEvent]:
        """Parse a single message/step from trajectory data.

        Args:
            message: A message dict from the trajectory
            step_index: Index of this step
            agent_id: Agent identifier

        Returns:
            StepEvent or None if the message is not a valid step
        """
        role = message.get("role", "")
        content = message.get("content", "")
        if isinstance(content, list):
            # Handle multi-part content (e.g. tool_use blocks)
            content = " ".join(
                p.get("text", p.get("content", ""))
                for p in content
                if isinstance(p, dict)
            )

        # Extract thought (assistant messages)
        thought = ""
        if role == "assistant":
            thought = content[:500] if content else ""

        # Extract bash command from tool_use blocks or content
        bash_command = ""
        return_code = 0
        output_preview = ""

        # Check for tool_use in message
        tool_calls = message.get("tool_calls", message.get("tool_use", []))
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name", tc.get("function", {}).get("name", ""))
                    if name in ("bash", "execute_bash", "terminal"):
                        args = tc.get("input", tc.get("arguments", {}))
                        if isinstance(args, dict):
                            bash_command = args.get("command", args.get("cmd", ""))
                        elif isinstance(args, str):
                            bash_command = args

        # Check for bash command in content (some formats inline it)
        if not bash_command and role == "assistant":
            bash_match = re.search(r"```bash\n(.*?)```", content, re.DOTALL)
            if bash_match:
                bash_command = bash_match.group(1).strip()

        # Extract return code and output from tool results
        if role in ("tool", "function"):
            output_preview = content[:500] if content else ""
            # Try to extract return code
            rc_match = re.search(r"exit code:?\s*(\d+)", content, re.IGNORECASE)
            if rc_match:
                return_code = int(rc_match.group(1))
            elif "error" in content.lower() or "traceback" in content.lower():
                return_code = 1

        # Skip empty steps
        if not thought and not bash_command and not output_preview:
            return None

        # Detect tool creation and usage from bash command
        tool_creations = self._detect_tool_creations(bash_command)
        tool_usages = self._detect_tool_usages(bash_command)

        return StepEvent(
            step_index=step_index,
            thought=thought,
            bash_command=bash_command,
            return_code=return_code,
            output_preview=output_preview,
            tool_creations=tool_creations,
            tool_usages=tool_usages,
        )

    def _parse_stdout_steps(
        self, stdout: str, agent_id: str
    ) -> List[StepEvent]:
        """Parse steps from raw stdout output."""
        steps: List[StepEvent] = []
        # Split on common step delimiters
        blocks = re.split(r"(?:Step \d+|---+|\*\*\*+)", stdout)
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block:
                continue
            # Try to extract a bash command
            bash_match = re.search(r"\$\s*(.*?)(?:\n|$)", block)
            bash_command = bash_match.group(1) if bash_match else ""

            step = StepEvent(
                step_index=i,
                thought=block[:200],
                bash_command=bash_command,
                tool_creations=self._detect_tool_creations(bash_command),
                tool_usages=self._detect_tool_usages(bash_command),
            )
            steps.append(step)
        return steps

    def _find_trajectory_output(
        self, stdout: str, stderr: str
    ) -> Optional[dict]:
        """Try to extract JSON trajectory from subprocess output.

        When ``trajectory_dir`` is configured, only files that resolve
        inside that directory are read (path-confinement).
        """
        # Look for trajectory file path in output
        path_match = re.search(
            r"trajectory[:\s]+(\S+\.json)", stdout + stderr, re.IGNORECASE
        )
        if path_match:
            traj_path = Path(path_match.group(1)).resolve()

            # Path confinement: if trajectory_dir is set, reject paths
            # that resolve outside it (prevents traversal via subprocess output).
            if self.config.trajectory_dir:
                allowed_dir = Path(self.config.trajectory_dir).resolve()
                if not traj_path.is_relative_to(allowed_dir):
                    logger.warning(
                        "Trajectory path %s is outside configured "
                        "trajectory_dir %s — skipping",
                        traj_path,
                        allowed_dir,
                    )
                    traj_path = None  # type: ignore[assignment]

            if traj_path is not None and traj_path.exists():
                try:
                    with open(traj_path) as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass

        # Try parsing stdout as JSON
        try:
            return json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    @staticmethod
    def _detect_tool_creations(bash_command: str) -> List[str]:
        """Detect file/tool creation patterns in a bash command."""
        if not bash_command:
            return []

        created: List[str] = []
        for pattern in (
            TOOL_CREATION_HEREDOC,
            TOOL_CREATION_REDIRECT,
            TOOL_CREATION_TEE,
        ):
            for match in pattern.finditer(bash_command):
                path = match.group(1)
                if path not in created:
                    created.append(path)
        return created

    @staticmethod
    def _detect_tool_usages(bash_command: str) -> List[str]:
        """Detect tool/script usage patterns in a bash command."""
        if not bash_command:
            return []

        used: List[str] = []
        for pattern in (
            TOOL_USAGE_PYTHON,
            TOOL_USAGE_SHELL,
            TOOL_USAGE_DIRECT,
        ):
            for match in pattern.finditer(bash_command):
                path = match.group(1)
                if path not in used:
                    used.append(path)
        return used
