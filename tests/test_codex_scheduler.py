import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import codex_scheduler as scheduler


class SchedulerTests(unittest.TestCase):
    def test_parse_time(self):
        self.assertEqual(scheduler.parse_time("08:05"), (8, 5))
        with self.assertRaises(Exception):
            scheduler.parse_time("8:5")

    def test_load_save_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            scheduler.save_config({"time": "12:34", "prompt": "你好"}, path)
            loaded = scheduler.load_config(path)
            self.assertEqual(loaded["time"], "12:34")
            self.assertEqual(loaded["prompt"], "你好")
            self.assertEqual(loaded["new_chat_shortcut"], "cmd+option+n")

    def test_launch_agent_is_valid_plist(self):
        config = dict(scheduler.DEFAULT_CONFIG, time="07:09", date="2026-12-01")
        payload = scheduler.launch_agent(config, "/usr/bin/python3")
        raw = plistlib.dumps(payload)
        decoded = plistlib.loads(raw)
        self.assertEqual(decoded["StartCalendarInterval"], {"Year": 2026, "Month": 12, "Day": 1, "Hour": 7, "Minute": 9})
        self.assertEqual(decoded["ProgramArguments"][-1], "run")

    def test_apple_script_uses_arguments_for_prompt(self):
        config = dict(scheduler.DEFAULT_CONFIG, prompt='say "hello"', app="ChatGPT")
        script = scheduler.apple_script(config)
        self.assertIn("set promptText to item 2 of argv", script)
        self.assertNotIn('say "hello"', script)
        self.assertIn('keystroke "n" using {command down, option down}', script)

    def test_shortcut_without_modifiers_is_valid(self):
        config = dict(scheduler.DEFAULT_CONFIG, new_chat_shortcut="n")
        script = scheduler.apple_script(config)
        self.assertIn('keystroke "n"\n', script)

    def test_deep_link_encodes_prompt_and_workspace(self):
        config = dict(scheduler.DEFAULT_CONFIG, prompt="hello world", workspace_path="/tmp/demo folder")
        self.assertEqual(
            scheduler.codex_deep_link(config),
            "codex://new?prompt=hello%20world&path=%2Ftmp%2Fdemo%20folder",
        )

    def test_prefilled_submit_script_only_sends_return(self):
        script = scheduler.submit_prefilled_script(dict(scheduler.DEFAULT_CONFIG))
        self.assertIn("key code 36", script)
        self.assertNotIn("keystroke promptText", script)

    def test_next_run_text_is_human_readable(self):
        value = scheduler.next_run_text(dict(scheduler.DEFAULT_CONFIG, time="07:00"))
        self.assertRegex(value, r"\d{4}-\d{2}-\d{2} 07:00")

    def test_dry_run_does_not_call_processes(self):
        with patch("codex_scheduler.subprocess.run") as run:
            result = scheduler.run_once(dict(scheduler.DEFAULT_CONFIG), dry_run=True)
        self.assertEqual(result, 0)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
