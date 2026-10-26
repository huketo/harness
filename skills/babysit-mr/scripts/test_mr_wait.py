import contextlib
import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "mr-wait"
loader = importlib.machinery.SourceFileLoader("mr_wait", str(SCRIPT))
spec = importlib.util.spec_from_loader("mr_wait", loader)
mr_wait = importlib.util.module_from_spec(spec)
sys.modules["mr_wait"] = mr_wait
loader.exec_module(mr_wait)

HOST = "gitlab.example.com"
PROJECT = "group/sub/proj"
API = "projects/group%2Fsub%2Fproj"
MR = f"{API}/merge_requests/5"
HEAD = "a" * 40
BASE = "b" * 40
MR_URL = f"https://{HOST}/{PROJECT}/-/merge_requests/5"
PIPELINE_URL = f"https://{HOST}/{PROJECT}/-/pipelines/77"


class FakeCli:
    """Stands in for gh, glab, and git. Unknown calls fail like a 404."""

    def __init__(self):
        self.routes = {}
        self.calls = []
        self.envs = []

    def glab(self, path, data):
        self.routes[("glab", HOST, path)] = (0, json.dumps(data), "")

    def set(self, key, stdout, returncode=0, stderr=""):
        self.routes[key] = (returncode, stdout, stderr)

    @staticmethod
    def key(argv):
        if argv[0] == "glab":
            return ("glab", argv[argv.index("--hostname") + 1], argv[-1])
        if argv[0] == "git":
            return ("git",)
        if argv[1:3] == ["api", "graphql"]:
            return ("gh", "graphql")
        return tuple(argv)

    def __call__(self, argv, env=None):
        self.calls.append(list(argv))
        self.envs.append(env)
        returncode, stdout, stderr = self.routes.get(self.key(argv), (1, "", "HTTP 404: Not Found (fake)"))
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


def merge_request(**overrides):
    data = {
        "iid": 5,
        "state": "opened",
        "sha": HEAD,
        "draft": False,
        "detailed_merge_status": "mergeable",
        "has_conflicts": False,
        "head_pipeline": {"id": 77, "status": "success", "sha": HEAD, "web_url": PIPELINE_URL},
        "blocking_discussions_resolved": True,
        "author": {"username": "author"},
        "reviewers": [{"username": "rev"}],
        "target_branch": "main",
        "diff_refs": {"base_sha": BASE},
        "web_url": MR_URL,
    }
    data.update(overrides)
    return data


def note(note_id, user, body, **fields):
    return {"id": note_id, "body": body, "author": {"username": user}, "system": False,
            "resolvable": False, "resolved": False, **fields}


def diff_position(path, line):
    return {"new_path": path, "new_line": line, "old_path": path, "old_line": None}


class Harness(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fake = FakeCli()
        for target, value in (
            ("STATE_DIR", Path(tmp.name)),
            ("run_cli", self.fake),
            ("TOKEN_HOSTS", set()),
        ):
            patcher = patch.object(mr_wait, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        sleep = patch.object(mr_wait.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def call(self, fn, *args):
        """Run fn, returning (stdout lines, exit code or None)."""
        out = io.StringIO()
        code = None
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                fn(*args)
            except SystemExit as stop:
                code = stop.code
        return out.getvalue().splitlines(), code

    def gitlab(self, mr=None, discussions=(), approvals=None, branch=BASE):
        self.fake.glab(MR, mr or merge_request())
        self.fake.glab("user", {"username": "viewer"})
        self.fake.glab(f"{MR}/discussions?per_page=100&page=1", list(discussions))
        self.fake.glab(f"{MR}/approvals", approvals or {
            "approved": True, "approvals_required": 1, "approvals_left": 0,
            "approved_by": [{"user": {"username": "rev"}}],
        })
        self.fake.glab(f"{API}/repository/branches/main", {"commit": {"id": branch}})
        self.fake.glab(f"{API}/repository/compare?from={HEAD}&to={branch}", {"commits": []})

    def watcher(self, until="ready"):
        return mr_wait.GitLabWatcher(mr_wait.Target("gitlab", HOST, PROJECT, 5), until, 20)

    def poll(self, watcher):
        """One poll as the run loop does it: settle only when the poll did not exit."""
        lines, code = self.call(watcher.poll)
        if code is None:
            self.call(watcher.settle)
        return lines, code


class TargetParsingTests(Harness):
    def test_github_url(self):
        self.fake.set(("gh", "pr", "view", "3", "-R", "o/r", "--json", "number"), '{"number": 3}')
        target = mr_wait.parse_target("https://github.com/o/r/pull/3/files", None)
        self.assertEqual(target, mr_wait.Target("github", "github.com", "o/r", 3))

    def test_gitlab_nested_group_url_with_query(self):
        self.fake.glab(f"{API}/merge_requests/12", {"iid": 12})
        raw = f"https://{HOST}/{PROJECT}/-/merge_requests/12/diffs?commit_id=abc#note_1"
        target = mr_wait.parse_target(raw, None)
        self.assertEqual(target, mr_wait.Target("gitlab", HOST, PROJECT, 12))

    def test_bang_number_uses_ssh_origin_on_custom_port(self):
        self.fake.set(("git",), f"ssh://git@{HOST}:2222/{PROJECT}.git\n")
        self.fake.glab(f"{API}/merge_requests/12", {"iid": 12})
        target = mr_wait.parse_target("!12", None)
        self.assertEqual(target, mr_wait.Target("gitlab", HOST, PROJECT, 12))
        self.assertIn(["glab", "api", "--hostname", HOST, f"{API}/merge_requests/12"], self.fake.calls)

    def test_env_tokens_reach_only_vouched_hosts(self):
        self.fake.glab(f"{API}/merge_requests/12", {"iid": 12})
        evil = "evil.example.net"
        self.fake.routes[("glab", evil, f"{API}/merge_requests/12")] = (0, "{}", "")
        with patch.dict(mr_wait.os.environ, {"GITLAB_TOKEN": "secret"}):
            mr_wait.parse_target(f"https://{evil}/{PROJECT}/-/merge_requests/12", None)
            self.assertNotIn("GITLAB_TOKEN", self.fake.envs[-1])
            self.fake.set(("git",), f"git@{HOST}:{PROJECT}.git\n")
            mr_wait.parse_target(f"https://{HOST}/{PROJECT}/-/merge_requests/12", None)
            self.assertIsNone(self.fake.envs[-1])
            mr_wait.parse_target(f"https://{evil}/{PROJECT}/-/merge_requests/12", None, evil)
            self.assertIsNone(self.fake.envs[-1])

    def test_scp_remote(self):
        self.assertEqual(mr_wait.parse_remote(f"git@{HOST}:{PROJECT}.git"), (HOST, PROJECT))

    def test_bad_input_exits_2(self):
        for raw in ("abc", "0", "", "https://example.com/o/r/issues/3"):
            with self.subTest(raw=raw):
                lines, code = self.call(mr_wait.parse_target, raw, "o/r")
                self.assertEqual(code, 2)
                self.assertTrue(lines and lines[0].startswith("mr-wait: "))

    def test_unknown_merge_request_exits_2(self):
        _, code = self.call(mr_wait.parse_target, f"https://{HOST}/{PROJECT}/-/merge_requests/99", None)
        self.assertEqual(code, 2)


class LockTests(Harness):
    def test_second_watcher_exits_2(self):
        target = mr_wait.Target("gitlab", HOST, PROJECT, 5)
        first = mr_wait.lock(target)
        self.addCleanup(first.close)
        lines, code = self.call(mr_wait.lock, target)
        self.assertEqual(code, 2)
        self.assertIn(f"already watches {PROJECT}!5", lines[0])


class GitLabTests(Harness):
    def test_baseline_then_new_discussion(self):
        old = {"id": "d1", "individual_note": True, "notes": [note(101, "rev", "old comment")]}
        self.gitlab(mr=merge_request(head_pipeline=None), discussions=[old])
        watcher = self.watcher(until="any-change")
        self.assertEqual(self.poll(watcher), ([], None))

        thread = {"id": "d2", "individual_note": False, "notes": [
            note(102, "rev", "Please <b>fix</b> this", resolvable=True,
                 position=diff_position("src/a.py", 12)),
            note(103, "author", "done", resolvable=True),
            note(104, "rev", "thanks", resolvable=True),
        ]}
        system = {"id": "d3", "individual_note": True, "notes": [note(105, "rev", "added 1 commit", system=True)]}
        self.gitlab(mr=merge_request(head_pipeline=None), discussions=[old, thread, system])
        lines, code = self.poll(watcher)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            f"!5 new thread from rev on src/a.py:12: Please fix this {MR_URL}#note_102",
            f"!5 thread reply from rev on src/a.py:12: thanks {MR_URL}#note_104",
        ])

    def test_restarted_watcher_does_not_repeat_events(self):
        comment = {"id": "d1", "individual_note": True, "notes": [note(101, "rev", "hi")]}
        self.gitlab(mr=merge_request(head_pipeline=None))
        self.poll(self.watcher(until="any-change"))
        self.gitlab(mr=merge_request(head_pipeline=None), discussions=[comment])
        self.assertEqual(self.poll(self.watcher(until="any-change"))[0], [f"!5 comment from rev: hi {MR_URL}#note_101"])
        self.assertEqual(self.poll(self.watcher(until="any-change")), ([], None))

    def test_review_bot_notes_are_ordinary_events(self):
        self.gitlab(mr=merge_request(head_pipeline=None))
        watcher = self.watcher(until="any-change")
        self.poll(watcher)
        discussions = [
            {"id": "d1", "individual_note": True, "notes": [
                note(201, "review-bot", "## Review finished\n3 findings")]},
            {"id": "d2", "individual_note": False, "notes": [
                note(202, "review-bot", "Null check missing", resolvable=True,
                     position=diff_position("src/b.py", 4))]},
        ]
        self.gitlab(mr=merge_request(head_pipeline=None), discussions=discussions)
        lines, code = self.poll(watcher)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            f"!5 comment from review-bot: ## Review finished 3 findings {MR_URL}#note_201",
            f"!5 new thread from review-bot on src/b.py:4: Null check missing {MR_URL}#note_202",
        ])

    def test_merged_results_pipeline_counts_as_head(self):
        merged = {"id": 78, "status": "success", "sha": "f" * 40, "ref": "refs/merge-requests/5/merge",
                  "web_url": PIPELINE_URL}
        self.gitlab(mr=merge_request(head_pipeline=merged))
        self.fake.glab(f"{API}/repository/commits/{'f' * 40}", {"parent_ids": ["b" * 40, HEAD]})
        watcher = self.watcher(until="green")
        self.assertEqual(self.poll(watcher), ([], None))
        lines, code = self.poll(watcher)
        self.assertEqual(code, 0)
        self.assertTrue(lines[0].startswith("!5 green on aaaaaaa: pipeline success"), lines)

    def test_merged_results_pipeline_for_an_older_head_does_not_count(self):
        stale = {"id": 78, "status": "success", "sha": "e" * 40, "ref": "refs/merge-requests/5/merge",
                 "web_url": PIPELINE_URL}
        self.gitlab(mr=merge_request(head_pipeline=stale))
        self.fake.glab(f"{API}/repository/commits/{'e' * 40}", {"parent_ids": ["b" * 40, "c" * 40]})
        watcher = self.watcher(until="green")
        self.assertEqual(self.poll(watcher), ([], None))
        self.assertEqual(self.poll(watcher), ([], None))

    def test_pipeline_failure_exits_1_with_job_names(self):
        failed = {"id": 77, "status": "failed", "sha": HEAD, "web_url": PIPELINE_URL}
        self.gitlab(mr=merge_request(head_pipeline=failed))
        self.fake.glab(f"{API}/pipelines/77/jobs?per_page=100&page=1", [
            {"name": "test", "status": "failed"},
            {"name": "lint", "status": "failed"},
            {"name": "flaky", "status": "failed", "allow_failure": True},
            {"name": "build", "status": "success"},
        ])
        lines, code = self.poll(self.watcher(until="green"))
        self.assertEqual(code, 1)
        self.assertEqual(lines, [f"!5 pipeline failed on aaaaaaa: lint, test {PIPELINE_URL}"])

    def test_ready_exits_0_after_a_stable_green_pipeline(self):
        self.gitlab()
        watcher = self.watcher()
        self.assertEqual(self.poll(watcher), ([], None))
        lines, code = self.poll(watcher)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            "!5 ready on aaaaaaa: pipeline success; approvals 1/1; 0 unresolved discussions; "
            "merge status mergeable; 0 commits behind main"
        ])

    def test_ready_waits_for_approval(self):
        unapproved = {"approved": False, "approvals_required": 1, "approvals_left": 1, "approved_by": []}
        running = {"id": 77, "status": "running", "sha": HEAD, "web_url": PIPELINE_URL}
        self.gitlab(mr=merge_request(head_pipeline=running, detailed_merge_status="ci_still_running"),
                    approvals=unapproved)
        watcher = self.watcher()
        self.poll(watcher)
        self.gitlab(mr=merge_request(detailed_merge_status="not_approved"), approvals=unapproved)
        self.assertEqual(self.poll(watcher), ([], None))
        lines, code = self.poll(watcher)
        self.assertIsNone(code)
        self.assertEqual(lines, [
            "!5 pipeline finished on aaaaaaa: pipeline success; approvals 0/1; 0 unresolved discussions; "
            "merge status not_approved"
        ])
        self.gitlab()
        lines, code = self.poll(watcher)
        self.assertEqual(code, 0)
        self.assertEqual(lines[0], "!5 approval given by rev")

    def test_ready_blocked_by_unresolved_discussions_exits_1(self):
        thread = {"id": "d1", "individual_note": False, "notes": [
            note(301, "rev", "why?", resolvable=True, position=diff_position("src/a.py", 2))]}
        self.gitlab(
            mr=merge_request(blocking_discussions_resolved=False, detailed_merge_status="discussions_not_resolved"),
            discussions=[thread],
        )
        watcher = self.watcher()
        self.poll(watcher)
        lines, code = self.poll(watcher)
        self.assertEqual(code, 1)
        self.assertEqual(lines, [f"!5 blocked by 1 unresolved discussions on aaaaaaa: {MR_URL}#note_301"])

    def test_need_rebase_exits_1(self):
        self.gitlab(mr=merge_request(detailed_merge_status="need_rebase"))
        watcher = self.watcher()
        self.poll(watcher)
        lines, code = self.poll(watcher)
        self.assertEqual(code, 1)
        self.assertEqual(lines, ["!5 merge status is need_rebase: rebase the branch onto main before merging"])

    def test_conflict_exits_1(self):
        self.gitlab(mr=merge_request(has_conflicts=True, detailed_merge_status="conflict"))
        lines, code = self.poll(self.watcher())
        self.assertEqual(code, 1)
        self.assertEqual(lines, ["!5 merge status is conflict: the branch conflicts with main, rebase it"])

    def test_merged_exits_0(self):
        self.gitlab(mr=merge_request(state="merged"))
        self.assertEqual(self.poll(self.watcher()), ([f"!5 merged: {MR_URL}"], 0))

    def test_no_pipeline_on_head_for_15_minutes_exits_1(self):
        stale = {"id": 70, "status": "success", "sha": "c" * 40, "web_url": PIPELINE_URL}
        self.gitlab(mr=merge_request(head_pipeline=stale))
        watcher = self.watcher(until="green")
        with patch.object(mr_wait.time, "monotonic", return_value=1000.0):
            self.assertEqual(self.poll(watcher), ([], None))
        with patch.object(mr_wait.time, "monotonic", return_value=1000.0 + 15 * 60):
            self.assertEqual(self.poll(watcher), (["!5 no pipeline on aaaaaaa after 15m"], 1))

    def test_target_branch_moved_over_mr_files(self):
        running = {"id": 77, "status": "running", "sha": HEAD, "web_url": PIPELINE_URL}
        self.gitlab(mr=merge_request(head_pipeline=running))
        watcher = self.watcher(until="any-change")
        self.poll(watcher)
        moved = "c" * 40
        self.gitlab(mr=merge_request(head_pipeline=running), branch=moved)
        self.fake.glab(f"{API}/repository/compare?from={BASE}&to={moved}",
                       {"diffs": [{"new_path": "src/a.py", "old_path": "src/a.py"}, {"new_path": "README.md"}]})
        self.fake.glab(f"{MR}/diffs?per_page=100&page=1", [{"new_path": "src/a.py", "old_path": "src/a.py"}])
        lines, code = self.poll(watcher)
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["!5 main moved to ccccccc and touches files in this MR: src/a.py"])


class GitHubTests(Harness):
    def test_green_through_fake_gh(self):
        repo, head = "o/r", "d" * 40
        self.fake.set(("gh", "api", f"repos/{repo}/rules/branches/main", "--jq",
                       '.[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context'),
                      "ci\n")
        self.fake.set(("gh", "graphql"), json.dumps({"data": {
            "viewer": {"login": "viewer"},
            "repository": {"pullRequest": {
                "url": f"https://github.com/{repo}/pull/7", "state": "OPEN", "headRefOid": head,
                "baseRefName": "main", "mergeStateStatus": "CLEAN", "author": {"login": "author"},
                "baseRef": {"target": {"oid": BASE}},
                "comments": {"nodes": []}, "reviews": {"nodes": []}, "reviewThreads": {"nodes": []},
            }},
        }}))
        self.fake.set(("gh", "pr", "checks", "7", "-R", repo, "--json", "name,bucket,link,description"),
                      json.dumps([{"name": "ci", "bucket": "pass", "link": "https://ci/1", "description": ""}]))
        self.fake.set(("gh", "api", f"repos/{repo}/compare/{BASE}...{head}", "--jq", ".behind_by"), "0\n")
        watcher = mr_wait.GitHubWatcher(mr_wait.Target("github", "github.com", repo, 7), "green", 20)
        self.assertEqual(self.poll(watcher), ([], None))
        lines, code = self.poll(watcher)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            "#7 green on ddddddd: 1 pass; required 1/1 green; no Greptile or Macroscope yet; "
            "0 unresolved threads; merge state CLEAN; 0 commits behind main"
        ])


class CliTests(unittest.TestCase):
    def test_help_exits_0(self):
        proc = subprocess.run(["python3", str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("usage: mr-wait", proc.stdout)


if __name__ == "__main__":
    unittest.main()
