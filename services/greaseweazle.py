from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import subprocess


LogCallback = Callable[[str], None]


@dataclass
class CommandResult:
    command: list[str]
    return_code: int


def build_write_command(
    image_path: Path,
    fmt: str,
    verify: bool,
    extra_flags: str,
) -> list[str]:
    command = ["gw", "write"]
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
) -> list[str]:
    command = ["gw", "read"]

    lowered = output_type.lower()
    if lowered == "img" and fmt.strip():
        command.extend(["--format", fmt.strip()])

    command.extend(_split_extra_flags(extra_flags))
    command.append(str(output_path))
    return command


def run_command(command: list[str], log_callback: LogCallback) -> CommandResult:
    log_callback(f"$ {' '.join(command)}")

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        log_callback(line.rstrip())

    return_code = process.wait()
    log_callback(f"[exit code: {return_code}]")
    return CommandResult(command=command, return_code=return_code)


def _split_extra_flags(extra_flags: str) -> list[str]:
    return [flag for flag in extra_flags.split() if flag]
