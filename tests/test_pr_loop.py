import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from scripts import pr_loop
class PrLoopTests(unittest.TestCase):
    def setUp(self):
        self.s=pr_loop.new_state(type("A",(),{"pr":"17","head":"a"*40,"workspace":".","workspace_name":"smoke","ref":"feature","url":None})())
    def test_same_head_preserves_evidence(self):
        pr_loop.set_tests(self.s,"PASS","tests","green"); pr_loop.request_review_state(self.s,"PASS","green"); pr_loop.apply_review(self.s,"a"*40,"DONE")
        before=copy.deepcopy((self.s["review"],self.s["tests"],self.s["ci"])); self.assertFalse(pr_loop.apply_head(self.s,"a"*40)); self.assertEqual(before,(self.s["review"],self.s["tests"],self.s["ci"]))
    def test_changed_head_invalidates(self):
        pr_loop.set_tests(self.s,"PASS","tests","green"); pr_loop.request_review_state(self.s,"PASS","green"); pr_loop.apply_review(self.s,"a"*40,"DONE")
        self.assertTrue(pr_loop.apply_head(self.s,"b"*40)); self.assertIsNone(self.s["review"]); self.assertIsNone(self.s["tests"]["headSha"]); self.assertIsNone(self.s["ci"]["headSha"])
    def test_gate_requires_current_head(self):
        pr_loop.set_tests(self.s,"PASS","tests","green"); pr_loop.request_review_state(self.s,"PASS","green"); pr_loop.apply_review(self.s,"a"*40,"DONE"); pr_loop.set_ci(self.s,"PASS","green")
        self.assertTrue(pr_loop.run_gate(self.s)[0]); self.s["phase"]="REVIEWED"; self.s["tests"]["headSha"]="b"*40; ok,reasons=pr_loop.run_gate(self.s); self.assertFalse(ok); self.assertIn("tests are not PASS for current HEAD",reasons)
    def test_stale_and_wrong_phase(self):
        with self.assertRaises(ValueError): pr_loop.apply_review(self.s,"b"*40,"DONE")
        with self.assertRaises(ValueError): pr_loop.apply_review(self.s,"a"*40,"DONE")
if __name__=="__main__": unittest.main()
