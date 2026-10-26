from __future__ import annotations

import json, sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from .core import CandidateProfile, Opportunity

SCHEMA_VERSION = 2

class OpportunityStore:
    def __init__(self, path: str | Path = "jobradar.db") -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=10); self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL"); self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.connection; self.connection.commit()
        except Exception:
            self.connection.rollback(); raise

    def _migrate(self) -> None:
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS opportunities (
                fingerprint TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL,
                location TEXT NOT NULL, description TEXT NOT NULL, url TEXT NOT NULL,
                source TEXT NOT NULL, salary_min INTEGER NOT NULL DEFAULT 0,
                remote INTEGER NOT NULL DEFAULT 0, tags TEXT NOT NULL DEFAULT '[]',
                match_score INTEGER NOT NULL DEFAULT 0, risk_score INTEGER NOT NULL DEFAULT 0,
                reasons TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'New',
                discovered_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '')""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(opportunities)")}
            for name in ("discovered_at", "updated_at"):
                if name not in columns: db.execute(f"ALTER TABLE opportunities ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
                fingerprint TEXT, action TEXT NOT NULL, details TEXT NOT NULL DEFAULT '{}')""")
            db.execute("""CREATE TABLE IF NOT EXISTS application_drafts (
                fingerprint TEXT PRIMARY KEY, cover_letter TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
                FOREIGN KEY(fingerprint) REFERENCES opportunities(fingerprint) ON DELETE CASCADE)""")
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    def upsert(self, job: Opportunity) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as db:
            db.execute("""INSERT INTO opportunities
                (fingerprint,title,company,location,description,url,source,salary_min,remote,tags,match_score,risk_score,reasons,status,discovered_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET
                description=excluded.description,url=excluded.url,source=excluded.source,
                salary_min=excluded.salary_min,remote=excluded.remote,tags=excluded.tags,
                match_score=excluded.match_score,risk_score=excluded.risk_score,
                reasons=excluded.reasons,updated_at=excluded.updated_at""",
                (job.fingerprint,job.title,job.company,job.location,job.description,job.url,job.source,
                 job.salary_min,int(job.remote),json.dumps(job.tags),job.match_score,job.risk_score,
                 json.dumps(job.reasons),job.status,now,now))

    def all(self, status: str | None = None) -> list[Opportunity]:
        sql="SELECT * FROM opportunities"; values: tuple[str,...]=()
        if status: sql += " WHERE status=?"; values=(status,)
        rows=self.connection.execute(sql+" ORDER BY match_score DESC, risk_score ASC", values).fetchall()
        return [Opportunity(r["title"],r["company"],r["location"],r["description"],r["url"],r["source"],
            r["salary_min"],bool(r["remote"]),json.loads(r["tags"]),r["match_score"],r["risk_score"],
            json.loads(r["reasons"]),r["status"]) for r in rows]

    def set_status(self, fingerprint: str, status: str) -> None:
        allowed={"New","Saved","Ready","Applied","Interview","Offer","Rejected","Archived"}
        if status not in allowed: raise ValueError(f"Unsupported status: {status}")
        now=datetime.now(timezone.utc).isoformat()
        with self.transaction() as db:
            db.execute("UPDATE opportunities SET status=?,updated_at=? WHERE fingerprint=?",(status,now,fingerprint))
            db.execute("INSERT INTO audit_log (occurred_at,fingerprint,action,details) VALUES (?,?,?,?)",
                       (now,fingerprint,"status_changed",json.dumps({"status":status})))

    def save_profile(self, profile: CandidateProfile) -> None:
        if errors:=profile.validate(): raise ValueError("; ".join(errors))
        payload=json.dumps({"skills":profile.skills,"desired_titles":profile.desired_titles,
            "countries":profile.countries,"min_salary":profile.min_salary,
            "remote_only":profile.remote_only,"blocked_terms":profile.blocked_terms})
        with self.transaction() as db: db.execute("INSERT OR REPLACE INTO settings VALUES ('candidate_profile',?)",(payload,))

    def load_profile(self, fallback: CandidateProfile) -> CandidateProfile:
        row=self.connection.execute("SELECT value FROM settings WHERE key='candidate_profile'").fetchone()
        if not row: return fallback
        d=json.loads(row[0]); return CandidateProfile(tuple(d["skills"]),tuple(d["desired_titles"]),
            tuple(d.get("countries",["Worldwide"])),int(d.get("min_salary",0)),
            bool(d.get("remote_only",True)),tuple(d.get("blocked_terms",[])))

    def has_profile(self)->bool:
        return self.connection.execute("SELECT 1 FROM settings WHERE key='candidate_profile'").fetchone() is not None

    def set_setting(self,key:str,value:object)->None:
        if not key or len(key)>80: raise ValueError("Invalid setting key")
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)",(key,json.dumps(value)))

    def get_setting(self,key:str,default:object=None)->object:
        row=self.connection.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        if not row:return default
        try:return json.loads(row[0])
        except json.JSONDecodeError:return default

    def audit(self, limit:int=100)->list[dict[str,object]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]

    def save_draft(self,fingerprint:str,cover_letter:str,notes:str="")->None:
        if not cover_letter.strip(): raise ValueError("Cover letter cannot be empty")
        now=datetime.now(timezone.utc).isoformat()
        with self.transaction() as db:
            db.execute("""INSERT INTO application_drafts VALUES (?,?,?,?)
                ON CONFLICT(fingerprint) DO UPDATE SET cover_letter=excluded.cover_letter,
                notes=excluded.notes,updated_at=excluded.updated_at""",(fingerprint,cover_letter.strip(),notes.strip(),now))
            db.execute("INSERT INTO audit_log (occurred_at,fingerprint,action,details) VALUES (?,?,?,?)",
                (now,fingerprint,"draft_saved",json.dumps({"characters":len(cover_letter.strip())})))

    def load_draft(self,fingerprint:str)->dict[str,str]|None:
        row=self.connection.execute("SELECT cover_letter,notes,updated_at FROM application_drafts WHERE fingerprint=?",(fingerprint,)).fetchone()
        return dict(row) if row else None

    def close(self)->None: self.connection.close()
