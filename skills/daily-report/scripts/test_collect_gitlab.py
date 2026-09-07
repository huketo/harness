import unittest
from unittest.mock import patch

import collect_gitlab as collector


class NullableCommitTitleTests(unittest.TestCase):
    def test_null_titles_preserve_branch_and_commit_evidence(self):
        for commit_from in (None, "0" * 40, "previous"):
            with self.subTest(commit_from=commit_from):
                event = {
                    "project_id": 1,
                    "action_name": "pushed to",
                    "target_type": "Project",
                    "created_at": "2026-09-05T10:00:00Z",
                    "author": {},
                    "push_data": {
                        "commit_to": "abcdef1234567890",
                        "commit_from": commit_from,
                        "commit_title": None,
                        "ref": "feat/182-example",
                    },
                }
                issues = [collector.normalize_assigned_issue({"iid": 182, "project_id": 1})]
                comparison = {"commits": [
                    {"short_id": "abcdef12", "title": None},
                    {"short_id": "12345678", "title": "Implement #182"},
                ]}
                with (
                    patch.object(collector, "fetch_events", return_value=[event]),
                    patch.object(collector, "lookup_project", return_value={"id": 1}),
                    patch.object(collector, "fetch_assigned_issues", return_value=issues),
                    patch.object(collector, "glab", return_value=comparison),
                ):
                    result = collector.collect("unused.local", "2026-09-05")
                self.assertEqual(result["event_count"], 1)
                self.assertTrue(result["assigned_issues"][0]["touched_today"])
                expected = ["branch feat/182-example"]
                if commit_from == "previous":
                    expected.append("commit 12345678 Implement #182")
                self.assertEqual(result["assigned_issues"][0]["evidence"], expected)
                commits = result["projects"][0]["pushes"][0]["commits"]
                self.assertEqual(commits[0], {"short_id": "abcdef12", "title": ""})


if __name__ == "__main__":
    unittest.main()
