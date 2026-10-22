"""Exercise Docker publish argv without SDK installation or Docker execution."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest import mock


def load_helper():
    # Only the unavailable SDK import is substituted; the publish wrapper is real.
    cua = types.ModuleType("cua")
    cua.Image = object
    cua.Sandbox = object
    runtime = types.ModuleType("cua_sandbox.runtime")
    runtime.docker = types.SimpleNamespace(subprocess=subprocess)
    with mock.patch.dict(sys.modules, {"cua": cua, "cua_sandbox": types.ModuleType("cua_sandbox"),
                                       "cua_sandbox.runtime": runtime}):
        loader = importlib.machinery.SourceFileLoader("cua_helper_test", str(Path(__file__).with_name("cua-sandbox")))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
    return module


class PublishBoundaryTest(unittest.TestCase):
    def test_known_separate_port_mapping_is_loopback_only(self):
        helper = load_helper()
        with mock.patch.object(helper.subprocess, "run") as run:
            helper.LoopbackPublish.run(["docker", "run", "-p", "8080:80", "-p", "9000:90/tcp", "image"])
        self.assertEqual(run.call_args.args[0], ["docker", "run", "-p", "127.0.0.1:8080:80", "-p", "127.0.0.1:9000:90/tcp", "image"])

    def test_other_publish_forms_fail_before_docker(self):
        helper = load_helper()
        for arguments in (["--publish", "8080:80"], ["--publish=8080:80"], ["-p8080:80"],
                          ["-p", "0.0.0.0:8080:80"], ["-p", "80"], ["-p"], ["-P"],
                          ["--publish-all"], ["-dP"], ["--publish-all=true"]):
            with self.subTest(arguments=arguments), mock.patch.object(helper.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    helper.LoopbackPublish.run(["docker", "run", *arguments, "image"])
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
