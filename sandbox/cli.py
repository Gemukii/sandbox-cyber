"""Controlled wrapper around Docker Sandboxes.

The wrapper deliberately never passes a host workspace to ``sbx create``.
Files cross the microVM boundary only through explicit import/export commands.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


STATE_DIR = ".sas"
STATE_FILE = "sandbox.json"
DEFAULT_NAME = "secure-agent-sandbox"
DEFAULT_AGENT = "shell"
GUEST_IMPORT_DIR = "/sas/incoming"
GUEST_EXPORT_DIR = "/sas/outgoing"


def run_sbx(*args: str, interactive: bool = False) -> int:
    """Run an sbx command and return its exit status."""
    del interactive  # Kept for callers to document interactive commands.
    return subprocess.run(["sbx", *args], check=False).returncode


def sbx_output(*args: str) -> str:
    """Run sbx and return stdout, raising a useful error on failure."""
    completed = subprocess.run(
        ["sbx", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or "Docker Sandbox command failed"
        raise RuntimeError(message)
    return completed.stdout.strip()


def state_path() -> Path:
    return Path.cwd() / STATE_DIR / STATE_FILE


def save_state(name: str, agent: str) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": name, "agent": agent}, indent=2) + "\n",
        encoding="utf-8",
    )


def load_state() -> dict[str, str]:
    path = state_path()
    if not path.exists():
        raise RuntimeError("No sandbox exists. Run 'sas create' first.")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        name = state["name"]
        agent = state["agent"]
        if not isinstance(name, str) or not isinstance(agent, str):
            raise TypeError
        return {"name": name, "agent": agent}
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid sandbox state in {path}") from error


def sandbox_name() -> str:
    return load_state()["name"]


def create(agent: str, name: str) -> int:
    try:
        existing = load_state()
    except RuntimeError:
        existing = None

    if existing:
        print(f"Sandbox state already exists: {existing['name']}")
        return 0

    # Do not append a host path. Omitting it is what makes this sandbox
    # mountless according to Docker Sandboxes (sbx >= 0.42).
    if run_sbx("create", "--name", name, agent) != 0:
        return 1
    save_state(name, agent)
    print(f"Sandbox created: {name} (mountless)")
    return 0


def shell() -> int:
    return run_sbx("run", "--name", sandbox_name())


def execute(command: list[str]) -> int:
    if not command:
        raise RuntimeError("sas exec requires a command")
    return run_sbx("exec", sandbox_name(), "--", *command)


def import_file(source: str, guest_name: str | None) -> int:
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise RuntimeError(f"Import source is not a file: {source_path}")
    target = guest_name or source_path.name
    if Path(target).name != target:
        raise RuntimeError("The guest filename must not contain a directory")
    if run_sbx(
        "exec",
        sandbox_name(),
        "--",
        "mkdir",
        "-p",
        GUEST_IMPORT_DIR,
    ) != 0:
        return 1
    return run_sbx(
        "cp",
        str(source_path),
        f"{sandbox_name()}:{GUEST_IMPORT_DIR}/{target}",
    )


def export_file(guest_path: str, destination: str) -> int:
    if not guest_path.startswith(GUEST_EXPORT_DIR + "/"):
        raise RuntimeError(
            f"Only files below {GUEST_EXPORT_DIR} may be exported"
        )
    destination_path = Path(destination).resolve()
    if destination_path.exists() and destination_path.is_dir():
        target = destination_path / Path(guest_path).name
    else:
        target = destination_path
    target.parent.mkdir(parents=True, exist_ok=True)
    return run_sbx("cp", f"{sandbox_name()}:{guest_path}", str(target))


def status() -> int:
    print(sbx_output("ls"))
    return 0


def destroy() -> int:
    name = sandbox_name()
    result = run_sbx("rm", name)
    if result == 0:
        state_path().unlink(missing_ok=True)
    return result


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(prog="sas")
    commands = command_parser.add_subparsers(dest="command", required=True)

    create_parser = commands.add_parser(
        "create",
        help="Create a mountless Docker Sandbox with no host workspace",
    )
    create_parser.add_argument("--name", default=DEFAULT_NAME)
    create_parser.add_argument("--agent", default=DEFAULT_AGENT)
    commands.add_parser("shell", help="Open the sandbox shell")
    exec_parser = commands.add_parser("exec", help="Run a command in the sandbox")
    exec_parser.add_argument("command_args", nargs=argparse.REMAINDER)

    import_parser = commands.add_parser(
        "import",
        help="Copy one explicitly selected file into the sandbox",
    )
    import_parser.add_argument("source")
    import_parser.add_argument("--name", dest="guest_name")

    export_parser = commands.add_parser(
        "export",
        help=f"Copy one file from {GUEST_EXPORT_DIR} to the host",
    )
    export_parser.add_argument("guest_path")
    export_parser.add_argument("destination")
    commands.add_parser("status", help="List Docker Sandboxes")
    commands.add_parser("destroy", help="Remove the sandbox and its state")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "create":
            return create(arguments.agent, arguments.name)
        if arguments.command == "shell":
            return shell()
        if arguments.command == "exec":
            return execute(arguments.command_args)
        if arguments.command == "import":
            return import_file(arguments.source, arguments.guest_name)
        if arguments.command == "export":
            return export_file(arguments.guest_path, arguments.destination)
        if arguments.command == "status":
            return status()
        return destroy()
    except FileNotFoundError:
        print(
            "Docker Sandboxes CLI 'sbx' was not found. "
            "Install/update Docker Desktop and the sbx CLI.",
            file=sys.stderr,
        )
        return 127
    except RuntimeError as error:
        print(f"sas: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
