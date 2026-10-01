import json
import logging
import os
import shutil
import subprocess
import sys

import c4d


def find_executable(executable, path=None):
    """
    Locate an executable on PATH (or a custom path string).
    Replaces distutils.spawn.find_executable, which is removed in Python 3.12+.
    """
    return shutil.which(executable, path=path)


def get_deadlinecommand():
    """
    Finds the Deadline Command executable as it is installed on your machine by searching in the following order:
    * The DEADLINE_PATH environment variable
    * The PATH environment variable
    * The file /Users/Shared/Thinkbox/DEADLINE_PATH
    """

    for env in ("DEADLINE_PATH", "PATH"):
        try:
            env_value = os.environ[env]
        except KeyError:
            # if the error is a key error it means that DEADLINE_PATH is not set.
            # however Deadline command may be in the PATH or on OSX it could be in the file /Users/Shared/Thinkbox/DEADLINE_PATH
            continue

        exe = find_executable("deadlinecommand", env_value)
        if exe:
            return exe

    # On OSX, we look for the DEADLINE_PATH file if the environment variable does not exist.
    if os.path.exists("/Users/Shared/Thinkbox/DEADLINE_PATH"):
        with open("/Users/Shared/Thinkbox/DEADLINE_PATH") as dl_file:
            deadline_bin = dl_file.read().strip()
        exe = find_executable("deadlinecommand", deadline_bin)
        if exe:
            return exe

    raise Exception("Deadline could not be found.  Please ensure that Deadline is installed.")


def call_deadlinecommand(arguments, format_output_as_json=False):
    """
    Calls DeadlineCommand with a given list of arguments.
    If json_output is true the output is returned as a json dictionary.
    Otherwise the raw string is output is returned.
    """
    command = [get_deadlinecommand()]
    if format_output_as_json:
        # JSON formatting option must come directly after the Deadline Command executable in the argument list.
        command.append('-prettyJSON')
    command.extend(arguments)

    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = proc.communicate()

    if format_output_as_json:
        json_out = json.loads(output)
        if json_out["ok"]:
            return json_out["result"]
        else:
            raise Exception(json_out["result"])
    else:
        if proc.returncode:
            raise Exception(output)
        return output


def GetC4DSubmissionDir():
    json_out = call_deadlinecommand(["-GetRepositoryPath", "submission/Cinema4D/Main"], format_output_as_json=True )
    return json_out.replace( "\\", "/" )


def install_slack_options(submitter):
    """Extend the repository dialog while keeping this a single-file install."""
    base = submitter.SubmitC4DToDeadlineDialog
    if getattr(base, "_slack_options_installed", False):
        return

    class SlackSubmissionDialog(base):
        _slack_options_installed = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.slack_choice_id = self.GetNextID()
            self.slack_text_id = self.GetNextID()
            self.slack_history = []
            self.slack_settings_path = os.path.join(
                self.DeadlineSettings, "c4d_slack_mentions.json")
            try:
                with open(self.slack_settings_path, encoding="utf-8") as stream:
                    history = json.load(stream)
                if isinstance(history, list):
                    self.slack_history = list(dict.fromkeys(
                        value.strip() for value in history
                        if isinstance(value, str) and value.strip()
                        and not any(ord(char) < 32 for char in value)))[:20]
            except (OSError, ValueError):
                pass

        def AddTextBoxGroup(self, control_id, label):
            super().AddTextBoxGroup(control_id, label)
            # Insert inside the existing Job Description group.
            if control_id == self.dialogIDs["DepartmentBoxID"]:
                self.AddComboBoxGroup(self.slack_choice_id, "Slack notification")
                self.AddChild(self.slack_choice_id, 0, "None")
                self.AddChild(self.slack_choice_id, 1, "Custom...")
                for index, mention in enumerate(self.slack_history, 2):
                    self.AddChild(self.slack_choice_id, index, mention)
                super().AddTextBoxGroup(self.slack_text_id, "Slack @ person")

        def InitValues(self):
            result = super().InitValues()
            # Deliberately opt in for each submission dialog.
            self.SetLong(self.slack_choice_id, 0)
            self.SetString(self.slack_text_id, "")
            self.Enable(self.slack_text_id, False)
            return result

        def Command(self, control_id, message):
            if control_id == self.slack_choice_id:
                choice = self.GetLong(self.slack_choice_id)
                mention = ""
                if 2 <= choice < len(self.slack_history) + 2:
                    mention = self.slack_history[choice - 2]
                self.SetString(self.slack_text_id, mention)
                self.Enable(self.slack_text_id, choice != 0)
                return True
            if control_id == self.dialogIDs["SubmitButtonID"]:
                try:
                    self.slack_mention()
                except ValueError as error:
                    c4d.gui.MessageDialog(str(error))
                    return True
            return super().Command(control_id, message)

        def slack_mention(self):
            if self.GetLong(self.slack_choice_id) == 0:
                return ""
            raw = self.GetString(self.slack_text_id)
            if any(ord(char) < 32 for char in raw):
                raise ValueError("Enter the Slack person on a single line.")
            mention = raw.strip()
            if not mention:
                raise ValueError("Enter a Slack person, or choose None.")
            return mention

        def writeInfoFile(self, filename, fileContents):
            # Job files carry Plugin; plugin-info files do not.
            mention = self.slack_mention() if "Plugin" in fileContents else ""
            if mention:
                fileContents = dict(fileContents)
                fileContents["OverrideTaskExtraInfoNames"] = "True"
                fileContents["TaskExtraInfoName0"] = mention
            result = super().writeInfoFile(filename, fileContents)
            if mention:
                history = [mention] + [value for value in self.slack_history
                                       if value != mention]
                try:
                    os.makedirs(self.DeadlineSettings, exist_ok=True)
                    with open(self.slack_settings_path, "w", encoding="utf-8") as stream:
                        json.dump(history[:20], stream, ensure_ascii=False, indent=2)
                except OSError as error:
                    logging.warning("Could not save Slack mention history: %s", error)
            return result

    submitter.SubmitC4DToDeadlineDialog = SlackSubmissionDialog


def main():
    # Get the repository path
    try:
        submissionDir = GetC4DSubmissionDir()
    except Exception as e:
        print("Error:Failed to pull Deadline Integrated submitter: %s" % e)
        raise
    
    if submissionDir not in sys.path:
        print( 'Appending "%s" to system path to import SubmitC4DToDeadline module' % submissionDir )
        sys.path.append( submissionDir )
    else:
        print( '"%s" is already in the system path' % submissionDir )
    
    try:
        import SubmitC4DToDeadline
    except ImportError as e:
        print("Error: Failed to import Deadline: %s" % e)
        raise
    
    install_slack_options(SubmitC4DToDeadline)
    SubmitC4DToDeadline.main( submissionDir )


if __name__=='__main__':
    main()
