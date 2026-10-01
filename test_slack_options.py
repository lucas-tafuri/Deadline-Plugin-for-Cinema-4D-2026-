"""Run without Cinema 4D: python -m unittest discover -v."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


loader = importlib.machinery.SourceFileLoader(
    "deadline_client", str(Path(__file__).with_name("DeadlineC4DClient.pyp")))
spec = importlib.util.spec_from_loader(loader.name, loader)
client = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"c4d": types.SimpleNamespace()}):
    loader.exec_module(client)


class SlackOptionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = self.temp.name

        class Dialog:
            def __init__(self):
                self.DeadlineSettings = settings
                self.dialogIDs = {"DepartmentBoxID": 1, "SubmitButtonID": 2}
                self.next_id = 2
                self.values = {}
                self.children = {}

            def GetNextID(self):
                self.next_id += 1
                return self.next_id

            def AddTextBoxGroup(self, *args): pass
            def AddComboBoxGroup(self, *args): pass
            def Enable(self, *args): pass
            def InitValues(self): return True
            def Command(self, *args): return "base command"
            def SetLong(self, key, value): self.values[key] = value
            def SetString(self, key, value): self.values[key] = value
            def GetLong(self, key): return self.values[key]
            def GetString(self, key): return self.values[key]
            def AddChild(self, key, index, text): self.children[index] = text

            def writeInfoFile(self, filename, contents):
                Path(filename).write_text("".join(
                    f"{key}={value}\n" for key, value in contents.items()), encoding="utf-8")

        self.submitter = types.SimpleNamespace(SubmitC4DToDeadlineDialog=Dialog)
        client.install_slack_options(self.submitter)
        self.dialog = self.new_dialog()

    def new_dialog(self):
        dialog = self.submitter.SubmitC4DToDeadlineDialog()
        dialog.AddTextBoxGroup(1, "Department")
        dialog.InitValues()
        return dialog

    def select(self, mention):
        self.dialog.SetLong(self.dialog.slack_choice_id, 1)
        self.dialog.Command(self.dialog.slack_choice_id, None)
        self.dialog.SetString(self.dialog.slack_text_id, mention)

    def test_job_metadata_and_plugin_file_separation(self):
        self.select(" <@U123456> ")
        original = {"Plugin": "Cinema4DBatch", "Name": "Test"}
        job = Path(self.temp.name, "job.job")
        plugin = Path(self.temp.name, "plugin.job")
        self.dialog.writeInfoFile(job, original)
        self.dialog.writeInfoFile(plugin, {"SceneFile": "scene.c4d"})
        self.assertIn("TaskExtraInfoName0=<@U123456>\n", job.read_text())
        self.assertIn("OverrideTaskExtraInfoNames=True\n", job.read_text())
        self.assertNotIn("TaskExtraInfo", plugin.read_text())
        self.assertEqual(original, {"Plugin": "Cinema4DBatch", "Name": "Test"})

    def test_history_dropdown_and_none(self):
        self.select("@artist")
        job = Path(self.temp.name, "job.job")
        self.dialog.writeInfoFile(job, {"Plugin": "Cinema4D"})
        self.dialog = self.new_dialog()
        self.assertEqual(self.dialog.children[2], "@artist")
        self.assertEqual(self.dialog.slack_mention(), "")
        self.dialog.SetLong(self.dialog.slack_choice_id, 2)
        self.dialog.Command(self.dialog.slack_choice_id, None)
        self.assertEqual(self.dialog.slack_mention(), "@artist")
        self.dialog.SetLong(self.dialog.slack_choice_id, 0)
        self.dialog.Command(self.dialog.slack_choice_id, None)
        self.dialog.writeInfoFile(job, {"Plugin": "Cinema4D"})
        self.assertNotIn("TaskExtraInfo", job.read_text())

    def test_rejects_blank_and_job_file_injection_before_writing(self):
        job = Path(self.temp.name, "job.job")
        for value in (" ", "@artist\nPool=other", "@artist\r", "@artist\0"):
            self.select(value)
            with self.assertRaises(ValueError):
                self.dialog.writeInfoFile(job, {"Plugin": "Cinema4D"})
            self.assertFalse(job.exists())

    def test_bad_history_and_repeated_install(self):
        Path(self.dialog.slack_settings_path).write_text('{broken')
        self.assertEqual(self.new_dialog().slack_history, [])
        Path(self.dialog.slack_settings_path).write_text(json.dumps([None, "@artist", "@artist"]))
        self.assertEqual(self.new_dialog().slack_history, ["@artist"])
        installed = self.submitter.SubmitC4DToDeadlineDialog
        client.install_slack_options(self.submitter)
        self.assertIs(installed, self.submitter.SubmitC4DToDeadlineDialog)


if __name__ == "__main__":
    unittest.main()
