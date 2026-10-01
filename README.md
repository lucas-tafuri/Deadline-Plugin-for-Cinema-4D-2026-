Replaced distutils with shutil since C4D 2026 uses Python 3.12+

Just copy the file to your /plugins folder

## Slack person on submission

Copy the updated `DeadlineC4DClient.pyp` into your Cinema 4D plugins folder,
replacing the previous copy, then restart Cinema 4D.

Under **General Options → Job Description**, choose **Slack notification → Custom...**
and enter a person in **Slack @ person**. Previously entered people appear in the
dropdown the next time you open the submitter. Choose **None** to omit the metadata;
each new dialog starts with None to avoid accidentally tagging a previous person.

The entered text is trimmed and written to the job submission as:

```ini
OverrideTaskExtraInfoNames=True
TaskExtraInfoName0=<your entered text>
```

This is Deadline's **Task Extra Info 0 Name** setting (a task column name override),
not the job's Extra Info 0 value or an individual task's extra-info value.
See [Deadline's submission documentation](https://docs.thinkboxsoftware.com/products/deadline/10.3/1_User%20Manual/manual/manual-submission.html).
The bot must read this field from the submitted job. No Slack messages are sent by
this plugin, and bot changes or copying this field to downstream FFmpeg jobs are
not included.

Text such as `@artist`, a Slack member ID, or `<@U123456>` is preserved as entered.
The plugin does not look up Slack accounts. Your bot must resolve names or format
member IDs as Slack mentions when sending its message.

Up to 20 recent entries are stored locally in
`<Deadline user home>/settings/c4d_slack_mentions.json`. The extension uses the
repository's existing submitter without changing shared repository files. Metadata
is included on job-info files generated through that submitter (including takes,
exports, and assembly jobs), and never on plugin-info files.

## Verification

Run `python -m unittest discover -v` for isolated checks of metadata writing,
history selection, omission, and invalid input. A live Cinema 4D UI/submission
check still requires Cinema 4D with the updated plugin installed.
