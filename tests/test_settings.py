"""settings.py 的单元测试(不依赖 systemd/图形环境)。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from doubao_input import settings as settings_mod
from doubao_input.settings import Settings, load_settings, save_settings


class SettingsFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_is_not_silent(self) -> None:
        self.assertFalse(load_settings().silent_start)

    def test_roundtrip(self) -> None:
        self.assertTrue(save_settings(Settings(silent_start=True)))
        self.assertTrue(load_settings().silent_start)

        data = json.loads(settings_mod.get_settings_path().read_text(encoding="utf-8"))
        self.assertEqual(data, {"silent_start": True})

    def test_corrupt_file_falls_back_to_default(self) -> None:
        settings_mod.get_settings_path().write_text("{not json", encoding="utf-8")
        self.assertFalse(load_settings().silent_start)


class AutostartTest(unittest.TestCase):
    def _ok(self, stdout: str = "") -> mock.Mock:
        return mock.Mock(returncode=0, stdout=stdout, stderr="")

    @mock.patch.object(settings_mod, "_run_systemctl")
    def test_is_enabled_parses_systemctl(self, run) -> None:
        run.return_value = self._ok("enabled\n")
        self.assertTrue(settings_mod.is_autostart_enabled())

        run.return_value = self._ok("masked\n")
        self.assertFalse(settings_mod.is_autostart_enabled())

    @mock.patch.object(settings_mod, "_run_systemctl")
    def test_disable_masks_unit(self, run) -> None:
        run.return_value = self._ok()
        self.assertTrue(settings_mod.set_autostart(False))
        self.assertEqual(run.call_args_list[0].args, ("mask", "doubao-input.service"))

    @mock.patch.object(settings_mod, "_run_systemctl")
    def test_enable_unmasks_then_enables(self, run) -> None:
        run.return_value = self._ok()
        self.assertTrue(settings_mod.set_autostart(True))
        calls = [c.args for c in run.call_args_list]
        self.assertEqual(calls[0], ("unmask", "doubao-input.service"))
        self.assertEqual(calls[1], ("enable", "doubao-input.service"))

    @mock.patch.object(settings_mod, "_run_systemctl")
    def test_failure_returns_false(self, run) -> None:
        run.return_value = mock.Mock(returncode=1, stdout="", stderr="boom")
        self.assertFalse(settings_mod.set_autostart(False))


if __name__ == "__main__":
    unittest.main()
