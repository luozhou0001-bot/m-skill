import tempfile
from pathlib import Path
import unittest

from mskill.policy import PolicyError, load_policy


class PolicyTests(unittest.TestCase):
    def write_policy(self, root: Path, text: str) -> None:
        (root / "mskill.toml").write_text(text, encoding="utf-8")

    def test_defaults_when_file_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = load_policy(Path(tmp))
            self.assertEqual(policy.fail_on, ("blocker",))
            self.assertFalse(policy.require_complete)
            self.assertEqual(policy.source, "defaults")

    def test_strict_policy_and_duplicate_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(
                root,
                '[policy]\nfail_on = ["major", "blocker", "major"]\nrequire_complete = true\n',
            )
            policy = load_policy(root)
            self.assertEqual(policy.fail_on, ("blocker", "major"))
            self.assertTrue(policy.require_complete)
            self.assertEqual(policy.source, "mskill.toml")

    def test_empty_fail_on_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(root, '[policy]\nfail_on = []\n')
            policy = load_policy(root)
            self.assertEqual(policy.fail_on, ())

    def test_invalid_severity_is_controlled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(root, '[policy]\nfail_on = ["critical"]\n')
            with self.assertRaisesRegex(PolicyError, "invalid policy.fail_on severity"):
                load_policy(root)

    def test_unknown_policy_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(root, '[policy]\nfail_on = ["blocker"]\nsurprise = true\n')
            with self.assertRaisesRegex(PolicyError, "unknown policy key"):
                load_policy(root)

    def test_unknown_top_level_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(root, 'surprise = true\n')
            with self.assertRaisesRegex(PolicyError, "unknown top-level key"):
                load_policy(root)

    def test_malformed_toml_is_controlled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(root, '[policy\nfail_on = ["blocker"]\n')
            with self.assertRaisesRegex(PolicyError, "invalid TOML"):
                load_policy(root)

    def test_require_complete_must_be_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(root, '[policy]\nrequire_complete = "yes"\n')
            with self.assertRaisesRegex(PolicyError, "must be a boolean"):
                load_policy(root)


if __name__ == "__main__":
    unittest.main()
