from __future__ import annotations
import csv
from pathlib import Path
from .core import Opportunity

HEADERS=("title","company","location","description","url","source","salary_min","remote","tags","status")

def export_csv(path:str|Path,jobs:list[Opportunity])->None:
    with Path(path).open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=HEADERS); w.writeheader()
        for j in jobs: w.writerow({"title":j.title,"company":j.company,"location":j.location,
            "description":j.description,"url":j.url,"source":j.source,"salary_min":j.salary_min,
            "remote":"yes" if j.remote else "no","tags":", ".join(j.tags),"status":j.status})

def import_csv(path:str|Path)->list[Opportunity]:
    jobs=[]
    with Path(path).open(newline="",encoding="utf-8-sig") as h:
        for r in csv.DictReader(h):
            if not r.get("title") or not r.get("company") or not r.get("url"): continue
            try: salary=int(r.get("salary_min") or 0)
            except ValueError: salary=0
            jobs.append(Opportunity(r["title"].strip(),r["company"].strip(),(r.get("location") or "Unknown").strip(),
                r.get("description") or "",r["url"].strip(),r.get("source") or "CSV import",salary,
                (r.get("remote") or "").lower() in {"yes","true","1"},
                [x.strip() for x in (r.get("tags") or "").split(",") if x.strip()],status=r.get("status") or "New"))
    return jobs
