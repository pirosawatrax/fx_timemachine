import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from fxtm import __version__
from fxtm.cli import main
from fxtm.store import default_data_dir


class DataDirTests(unittest.TestCase):
    def test_env_override_wins(self):
        with mock.patch.dict(os.environ, {"FXTM_DATA_DIR": "/tmp/custom"}):
            self.assertEqual(default_data_dir(), Path("/tmp/custom"))

    def test_platform_defaults(self):
        env = {k: v for k, v in os.environ.items() if k not in ("FXTM_DATA_DIR", "XDG_DATA_HOME", "LOCALAPPDATA")}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(sys, "platform", "linux"):
                self.assertEqual(default_data_dir(), Path.home() / ".local" / "share" / "fxtm")
            with mock.patch.object(sys, "platform", "darwin"):
                self.assertEqual(default_data_dir(), Path.home() / "Library" / "Application Support" / "fxtm")
            with mock.patch.object(sys, "platform", "win32"):
                self.assertEqual(default_data_dir(), Path.home() / "AppData" / "Local" / "fxtm")
        with mock.patch.dict(os.environ, {**env, "XDG_DATA_HOME": "/xdg"}, clear=True):
            with mock.patch.object(sys, "platform", "linux"):
                self.assertEqual(default_data_dir(), Path("/xdg/fxtm"))


class CliTests(unittest.TestCase):
    def test_version(self):
        with self.assertRaises(SystemExit) as ctx, mock.patch("sys.stdout") as out:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(__version__, "".join(c.args[0] for c in out.write.call_args_list))

    def test_bad_input_is_a_clean_error(self):
        self.assertEqual(main(["candles", "EUR/USD", "not-a-date"]), 1)


if __name__ == "__main__":
    unittest.main()
