import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sandbox import cli


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cwd = patch("pathlib.Path.cwd", return_value=Path(self.temp_dir.name))
        self.cwd.start()

    def tearDown(self) -> None:
        self.cwd.stop()
        self.temp_dir.cleanup()

    @patch("sandbox.cli.run_sbx", return_value=0)
    def test_create_is_mountless(self, run_sbx: object) -> None:
        self.assertEqual(cli.create("shell", "test-sandbox"), 0)
        run_sbx.assert_called_once_with(
            "create", "--name", "test-sandbox", "shell"
        )
        state = json.loads((Path(self.temp_dir.name) / ".sas" / "sandbox.json").read_text())
        self.assertEqual(state["name"], "test-sandbox")

    @patch("sandbox.cli.run_sbx", return_value=0)
    def test_import_requires_explicit_file_transfer(self, run_sbx: object) -> None:
        cli.save_state("test-sandbox", "shell")
        source = Path(self.temp_dir.name) / "sample.bin"
        source.write_bytes(b"sample")

        self.assertEqual(cli.import_file(str(source), None), 0)
        self.assertEqual(
            [call.args for call in run_sbx.call_args_list],
            [
                ("exec", "test-sandbox", "--", "mkdir", "-p", "/sas/incoming"),
                (
                    "cp",
                    str(source.resolve()),
                    "test-sandbox:/sas/incoming/sample.bin",
                ),
            ],
        )

    def test_export_rejects_paths_outside_export_directory(self) -> None:
        cli.save_state("test-sandbox", "shell")
        with self.assertRaisesRegex(RuntimeError, "Only files below"):
            cli.export_file("/etc/passwd", str(Path(self.temp_dir.name) / "out"))

    @patch("sandbox.cli.run_sbx", return_value=0)
    def test_exec_does_not_use_docker_engine_directly(self, run_sbx: object) -> None:
        cli.save_state("test-sandbox", "shell")
        self.assertEqual(cli.execute(["python", "--version"]), 0)
        run_sbx.assert_called_once_with(
            "exec", "test-sandbox", "--", "python", "--version"
        )


if __name__ == "__main__":
    unittest.main()
