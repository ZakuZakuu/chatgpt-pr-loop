import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_upstream import (
    BootstrapError,
    node_major,
    normalize_remote,
    render_upstream_skill,
)


class BootstrapUpstreamTests(unittest.TestCase):
    def test_node_major(self):
        self.assertEqual(node_major("v20.18.1"), 20)
        self.assertEqual(node_major("22.0.0"), 22)
        self.assertIsNone(node_major("unknown"))

    def test_remote_normalization(self):
        self.assertEqual(
            normalize_remote("git@github.com:XiaoDuoYa/codex-with-chatgpt.git"),
            normalize_remote("https://github.com/XiaoDuoYa/codex-with-chatgpt"),
        )

    def test_render_upstream_skill_replaces_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp) / "checkout"
            rendered = render_upstream_skill(
                "The codex-with-chatgpt checkout lives at: `<ACTUAL_CHECKOUT_PATH>`\n",
                checkout,
            )
            self.assertIn(str(checkout.resolve()), rendered)
            self.assertNotIn("<ACTUAL_CHECKOUT_PATH>", rendered)

    def test_render_upstream_skill_rejects_missing_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BootstrapError):
                render_upstream_skill("no placeholder", Path(tmp))


if __name__ == "__main__":
    unittest.main()
