import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coursekit import paths
from coursekit import terraform as tf


class SyncTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src, self.build = Path(tmp.name) / "src", Path(tmp.name) / "build"
        (self.src / "modules" / "a").mkdir(parents=True)
        (self.src / "main.tf").write_text("# main\n")
        (self.src / "modules" / "a" / "a.tf").write_text("# a\n")

    def sync(self, **kw):
        tf.sync_build_dir(self.src, self.build, **kw)

    def test_mirrors_files_and_drops_stale_ones(self):
        self.sync()
        self.assertEqual((self.build / "modules" / "a" / "a.tf").read_text(), "# a\n")
        (self.build / "course.tfstate").write_text("old")
        (self.build / "plan.json").write_text("old")
        (self.src / "modules" / "a" / "a.tf").unlink()
        self.sync()
        self.assertFalse((self.build / "modules").exists())
        self.assertFalse((self.build / "course.tfstate").exists())
        self.assertFalse((self.build / "plan.json").exists())
        self.assertTrue((self.build / tf.OVERRIDE_NAME).exists())

    def test_keeps_terraform_dir_and_unchanged_files(self):
        self.sync()
        (self.build / ".terraform").mkdir()
        (self.build / ".terraform" / "keep.txt").write_text("x")
        os.utime(self.build / "main.tf", (1, 1))
        (self.src / "modules" / "a" / "a.tf").write_text("# b\n")
        self.sync()
        self.assertTrue((self.build / ".terraform" / "keep.txt").exists())
        self.assertEqual((self.build / "main.tf").stat().st_mtime, 1)
        self.assertEqual((self.build / "modules" / "a" / "a.tf").read_text(), "# b\n")

    def test_state_is_reset_every_time(self):
        state = self.src.parent / "dev.tfstate"
        state.write_text("{}")
        self.sync(states={"": state})
        (self.build / "course.tfstate").write_text("changed by a check")
        self.sync(states={"": state})
        self.assertEqual((self.build / "course.tfstate").read_text(), "{}")


class LinkProvidersTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        top = Path(tmp.name).resolve()
        self.cache, self.build = top / "cache", top / "build"
        self.cwd = self.build / "03c"
        self.cwd.mkdir(parents=True)
        for p in (mock.patch.object(paths, "BUILD", self.build), mock.patch.object(paths, "PLUGIN_CACHE", self.cache)):
            p.start()
            self.addCleanup(p.stop)

        self.pkg = Path("registry.terraform.io/hashicorp/google/8.12.0/windows_amd64")
        (self.cache / self.pkg).mkdir(parents=True)
        (self.cache / self.pkg / "provider.exe").write_text("shared")

    def lock(self, version):
        (self.cwd / ".terraform.lock.hcl").write_text(
            f'provider "registry.terraform.io/hashicorp/google" {{\n  version     = "{version}"\n}}\n')

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows feature")
    def test_links_the_locked_version(self):
        link = self.cwd / ".terraform" / "providers" / self.pkg
        link.mkdir(parents=True)
        (link / "provider.exe").write_text("a copy from an older init")
        self.lock("8.12.0")
        tf.link_providers(self.cwd)
        tf.link_providers(self.cwd)
        self.assertTrue(tf._is_junction(link))
        self.assertEqual((link / "provider.exe").read_text(), "shared")

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows feature")
    def test_unlocked_providers_are_never_linked(self):
        """Terraform may install these, and must not write into the shared cache while doing it."""
        link = self.cwd / ".terraform" / "providers" / self.pkg
        tf.link_providers(self.cwd)
        self.assertFalse(link.exists())
        self.lock("8.12.0")
        tf.link_providers(self.cwd)
        self.lock("8.11.0")
        tf.link_providers(self.cwd)
        self.assertFalse(link.exists())
        self.assertEqual((self.cache / self.pkg / "provider.exe").read_text(), "shared")

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows feature")
    def test_replaces_the_old_whole_folder_link(self):
        import _winapi
        top = self.cwd / ".terraform" / "providers"
        top.parent.mkdir()
        _winapi.CreateJunction(str(self.cache), str(top))
        tf.link_providers(self.cwd)
        self.assertFalse(tf._is_junction(top))
        self.assertEqual((self.cache / self.pkg / "provider.exe").read_text(), "shared")

    def test_only_build_folders_are_linked(self):
        other = self.build.parent / "elsewhere"
        other.mkdir()
        (other / ".terraform.lock.hcl").write_text("")
        tf.link_providers(other)
        self.assertFalse((other / ".terraform").exists())


class EnvTest(unittest.TestCase):
    def test_inherited_settings_are_removed_whatever_their_case(self):
        bad = {"TF_CLI_ARGS_PLAN": "-target=x", "tf_cli_args": "-x", "TF_CLI_CONFIG_FILE": "evil.rc", "TF_VAR_project_id": "real",
               "GOOGLE_APPLICATION_CREDENTIALS": "key.json", "Google_Impersonate_Service_Account": "sa@x", "CLOUDSDK_CONFIG": "c"}
        with mock.patch.dict(os.environ, {**bad, "PATH": os.environ.get("PATH", ""), "HTTPS_PROXY": "http://proxy:3128"}, clear=True):
            e = tf.env()
        for k in bad:
            if k.upper() not in ("TF_CLI_CONFIG_FILE",):
                self.assertNotIn(k, e)
        self.assertEqual(e["TF_CLI_CONFIG_FILE"], str(tf.CLI_CONFIG))
        self.assertEqual(e["GOOGLE_OAUTH_ACCESS_TOKEN"], tf.FAKE_TOKEN)
        self.assertEqual(e["HTTPS_PROXY"], "http://proxy:3128")       # proxies still work for setup

    def test_cli_config_allows_only_course_providers(self):
        text = tf._cli_config().read_text(encoding="utf-8")
        self.assertEqual(text.count('"registry.terraform.io/hashicorp/google", "registry.terraform.io/hashicorp/random"'), 2)
        self.assertNotIn("external", text)

    @unittest.skipUnless(shutil.which("terraform"), "needs terraform")
    def test_other_providers_are_refused(self):
        from coursekit import runner
        build = paths.BUILD / "unit-provider"
        build.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, build, True)
        (build / "main.tf").write_text('data "external" "x" {\n  program = ["whoami"]\n}\n')
        res = tf.run(["init", "-backend=false", "-no-color", "-input=false"], cwd=build)
        self.assertFalse(res.ok)
        self.assertIn('"hashicorp/external" is refused', runner._init_hint(res.output))


if __name__ == "__main__":
    unittest.main()
