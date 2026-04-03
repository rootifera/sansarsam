from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import shutil
import subprocess
import sys


LogCallback = Callable[[str], None]


@dataclass
class CommandResult:
    command: list[str]
    return_code: int
    cancelled: bool = False
    output_lines: list[str] | None = None


def detect_gw_executable() -> str:
    candidates: list[str] = []

    preferred_names = ["gw"]
    if sys.platform.startswith("win"):
        preferred_names.insert(0, "gw.exe")

    for name in preferred_names:
        resolved = shutil.which(name)
        if resolved:
            return resolved

    app_dir = Path(sys.argv[0]).resolve().parent
    search_dirs = [Path.cwd(), app_dir]

    env_path = os.environ.get("GREASEWEAZLE_PATH", "").strip()
    if env_path:
        search_dirs.append(Path(env_path).expanduser())

    candidate_filenames = ["gw"]
    if sys.platform.startswith("win"):
        candidate_filenames = ["gw.exe", "gw"]

    seen: set[Path] = set()
    for directory in search_dirs:
        try:
            resolved_dir = directory.expanduser().resolve()
        except OSError:
            continue
        if resolved_dir in seen or not resolved_dir.exists() or not resolved_dir.is_dir():
            continue
        seen.add(resolved_dir)

        for filename in candidate_filenames:
            candidate = resolved_dir / filename
            if candidate.is_file():
                return str(candidate)

    return "gw.exe" if sys.platform.startswith("win") else "gw"


def build_write_command(
    image_path: Path,
    fmt: str,
    verify: bool,
    extra_flags: str,
    gw_executable: str = "gw",
) -> list[str]:
    command = [gw_executable, "write"]
    if fmt.strip():
        command.extend(["--format", fmt.strip()])
    if not verify:
        command.append("--no-verify")
    command.extend(_split_extra_flags(extra_flags))
    command.append(str(image_path))
    return command


def build_read_command(
    output_path: Path,
    output_type: str,
    fmt: str,
    extra_flags: str,
    gw_executable: str = "gw",
) -> list[str]:
    command = [gw_executable, "read"]

    lowered = output_type.lower()
    if lowered == "img" and fmt.strip():
        command.extend(["--format", fmt.strip()])

    command.extend(_split_extra_flags(extra_flags))
    command.append(str(output_path))
    return command


def run_command(
    command: list[str],
    log_callback: LogCallback,
    on_process_started: Callable[[subprocess.Popen[str]], None] | None = None,
) -> CommandResult:
    log_callback(f"$ {' '.join(command)}")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        message = f"[error] Command not found: {command[0]}"
        log_callback(message)
        return CommandResult(command=command, return_code=127, output_lines=[message])

    if on_process_started is not None:
        on_process_started(process)

    assert process.stdout is not None
    output_lines: list[str] = []
    for line in process.stdout:
        stripped = line.rstrip()
        output_lines.append(stripped)
        log_callback(stripped)

    return_code = process.wait()
    log_callback(f"[exit code: {return_code}]")
    return CommandResult(command=command, return_code=return_code, output_lines=output_lines)


def _split_extra_flags(extra_flags: str) -> list[str]:
    return [flag for flag in extra_flags.split() if flag]
