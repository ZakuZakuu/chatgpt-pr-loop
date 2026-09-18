#!/usr/bin/env python3
"""One active Web ChatGPT conversation per workspace."""
import argparse,json,os,re,tempfile
from datetime import datetime,timezone
from pathlib import Path
URL=re.compile(r"^https://chatgpt\.com/c/[A-Za-z0-9_-]+(?:\?.*)?$")
SHA=re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def url(v):
    if not URL.fullmatch(v.strip()): raise SystemExit("invalid ChatGPT conversation URL")
    return v.strip()
def sha(v):
    if not SHA.fullmatch(v.strip()): raise SystemExit("invalid complete HEAD SHA")
    return v.strip().lower()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True); fd,t=tempfile.mkstemp(prefix="."+p.name+".",dir=p.parent)
    with os.fdopen(fd,"w",encoding="utf-8") as h: json.dump(v,h,indent=2,sort_keys=True); h.write("\n")
    os.replace(t,p)
def load(p):
    if not p.is_file(): raise SystemExit("registry does not exist: "+str(p))
    v=json.loads(p.read_text(encoding="utf-8"))
    if v.get("schema")!=1: raise SystemExit("unsupported registry schema")
    return v
def work(a):
    return {"workspace":a.workspace_name,"pr":int(a.pr) if a.pr else None,
            "headSha":sha(a.head) if a.head else None,"phase":a.phase,
            "tests":a.tests,"ci":a.ci,"nextAction":a.next_action}
def main(a):
    p=Path(a.state).expanduser()
    if a.cmd=="bind":
        if p.exists(): raise SystemExit("registry already exists; use work or handoff")
        t=now(); v={"schema":1,"workspaceName":a.workspace_name,
          "active":{"generation":"G01","url":url(a.url),
          "logicalName":a.logical_name or a.workspace_name+" - G01","summary":a.summary,
          "createdAt":t,"updatedAt":t},"previous":[],"work":work(a),
          "history":[{"at":t,"event":"BOUND_EXISTING_CONVERSATION","generation":"G01"}]}
        save(p,v); print(json.dumps({"ok":True,"registry":v},indent=2,sort_keys=True)); return
    v=load(p)
    if a.cmd=="status":
        print(json.dumps({"ok":True,"registry":v},indent=2,sort_keys=True)); return
    if a.cmd=="work":
        v["work"]=work(a); v["active"]["updatedAt"]=now()
        v["history"].append({"at":now(),"event":"WORK_UPDATED","generation":v["active"]["generation"]})
    elif a.cmd=="handoff":
        if a.result=="FAILED":
            v["history"].append({"at":now(),"event":"HANDOFF_FAILED","generation":v["active"]["generation"]})
            save(p,v); print(json.dumps({"ok":True,"swapped":False,"registry":v},indent=2)); return
        old=v["active"]; g="G"+str(int(old["generation"][1:])+1).zfill(2); t=now(); v["previous"].append(old)
        v["active"]={"generation":g,"url":url(a.url),
          "logicalName":a.logical_name or v["workspaceName"]+" - "+g,
          "summary":a.summary or old.get("summary"),"createdAt":t,"updatedAt":t}
        v["history"].append({"at":t,"event":"HANDOFF_SUCCEEDED","from":old["generation"],"to":g})
    save(p,v); print(json.dumps({"ok":True,"registry":v},indent=2,sort_keys=True))
def parser():
    r=argparse.ArgumentParser(); r.add_argument("--state",required=True); s=r.add_subparsers(dest="cmd",required=True)
    b=s.add_parser("bind"); b.add_argument("--url",required=True); b.add_argument("--workspace-name",required=True)
    b.add_argument("--logical-name"); b.add_argument("--summary",required=True); b.add_argument("--pr"); b.add_argument("--head")
    b.add_argument("--phase",default="IMPLEMENTING"); b.add_argument("--tests",default="UNKNOWN"); b.add_argument("--ci",default="UNKNOWN"); b.add_argument("--next-action")
    s.add_parser("status")
    w=s.add_parser("work"); w.add_argument("--workspace-name",required=True); w.add_argument("--pr"); w.add_argument("--head"); w.add_argument("--phase",required=True); w.add_argument("--tests",required=True); w.add_argument("--ci",required=True); w.add_argument("--next-action",required=True)
    h=s.add_parser("handoff"); h.add_argument("--result",choices=["SUCCESS","FAILED"],required=True); h.add_argument("--url"); h.add_argument("--summary"); h.add_argument("--logical-name")
    return r
if __name__=="__main__":
    a=parser().parse_args()
    if a.cmd=="handoff" and a.result=="SUCCESS" and not a.url: parser().error("--url required")
    main(a)
