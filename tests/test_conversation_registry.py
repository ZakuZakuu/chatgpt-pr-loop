import json,subprocess,sys,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).parents[1]/"scripts"/"conversation_registry.py"
class RegistryTests(unittest.TestCase):
    def invoke(self,p,*a): return subprocess.run([sys.executable,str(SCRIPT),"--state",str(p),*a],check=True,capture_output=True,text=True)
    def test_binding_and_handoff_lineage(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"registry.json"; old="https://chatgpt.com/c/old"; new="https://chatgpt.com/c/new"
            self.invoke(p,"bind","--url",old,"--workspace-name","smoke","--summary","v2")
            self.invoke(p,"work","--workspace-name","smoke","--pr","17","--head","a"*40,"--phase","AWAITING_REVIEW","--tests","PASS","--ci","PASS","--next-action","review")
            self.invoke(p,"handoff","--result","FAILED"); v=json.loads(self.invoke(p,"status").stdout)["registry"]; self.assertEqual(v["active"]["url"],old); self.assertEqual(v["active"]["generation"],"G01")
            self.invoke(p,"handoff","--result","SUCCESS","--url",new); v=json.loads(self.invoke(p,"status").stdout)["registry"]; self.assertEqual(v["active"]["url"],new); self.assertEqual(v["active"]["generation"],"G02"); self.assertEqual(v["previous"][0]["url"],old)
    def test_default_names_include_summary_and_pr_updates_keep_generation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"registry.json"
            self.invoke(p,"bind","--url","https://chatgpt.com/c/old","--workspace-name","smoke","--summary","PR loop migration")
            v=json.loads(self.invoke(p,"status").stdout)["registry"]
            self.assertEqual(v["active"]["logicalName"],"smoke · G01 · PR loop migration")
            self.invoke(p,"work","--workspace-name","smoke","--pr","17","--head","a"*40,"--phase","MERGE_READY","--tests","PASS","--ci","NOT_REQUIRED","--next-action","next")
            self.invoke(p,"work","--workspace-name","smoke","--pr","18","--head","b"*40,"--phase","IMPLEMENTING","--tests","UNKNOWN","--ci","UNKNOWN","--next-action","implement")
            self.invoke(p,"handoff","--result","SUCCESS","--url","https://chatgpt.com/c/new","--summary","Search quality")
            v=json.loads(self.invoke(p,"status").stdout)["registry"]
            self.assertEqual(v["active"]["generation"],"G02")
            self.assertEqual(v["active"]["logicalName"],"smoke · G02 · Search quality")
            self.assertEqual(v["previous"][0]["generation"],"G01")

if __name__=="__main__": unittest.main()
