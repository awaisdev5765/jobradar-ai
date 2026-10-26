from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QStandardPaths, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from .core import CandidateProfile, Opportunity, score_opportunity
from .interchange import export_csv, import_csv
from .sample_data import sample_opportunities
from .sources import discover_public_jobs
from .storage import OpportunityStore


class Metric(QFrame):
    def __init__(self, value: str, label: str) -> None:
        super().__init__(); self.setObjectName("metric")
        box = QVBoxLayout(self); box.setContentsMargins(18, 14, 18, 14); box.setSpacing(2)
        number = QLabel(value); number.setObjectName("metricValue")
        caption = QLabel(label.upper()); caption.setObjectName("eyebrow")
        box.addWidget(number); box.addWidget(caption)


class ProfileDialog(QDialog):
    def __init__(self, profile: CandidateProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.setWindowTitle("My opportunity profile"); self.setMinimumWidth(520)
        root=QVBoxLayout(self); intro=QLabel("JobRadar uses these preferences locally to rank opportunities.")
        intro.setObjectName("muted"); intro.setWordWrap(True); root.addWidget(intro)
        form=QFormLayout(); form.setSpacing(12)
        self.skills=QLineEdit(", ".join(profile.skills)); self.skills.setAccessibleName("Skills")
        self.titles=QLineEdit(", ".join(profile.desired_titles)); self.titles.setAccessibleName("Target roles")
        self.countries=QLineEdit(", ".join(profile.countries)); self.countries.setAccessibleName("Eligible locations")
        self.salary=QSpinBox(); self.salary.setRange(0,1_000_000); self.salary.setSingleStep(1000); self.salary.setValue(profile.min_salary); self.salary.setPrefix("£ ")
        self.remote=QCheckBox("Show remote opportunities only"); self.remote.setChecked(profile.remote_only)
        self.blocked=QLineEdit(", ".join(profile.blocked_terms)); self.blocked.setAccessibleName("Blocked terms")
        form.addRow("Skills",self.skills); form.addRow("Target roles",self.titles); form.addRow("Eligible locations",self.countries)
        form.addRow("Minimum annual salary",self.salary); form.addRow("",self.remote); form.addRow("Blocked terms",self.blocked); root.addLayout(form)
        self.error=QLabel(); self.error.setObjectName("error"); self.error.setWordWrap(True); root.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Save)
        buttons.rejected.connect(self.reject); buttons.accepted.connect(self._validate); root.addWidget(buttons)

    @staticmethod
    def _values(field: QLineEdit) -> tuple[str,...]: return tuple(x.strip() for x in field.text().split(",") if x.strip())
    def profile(self)->CandidateProfile:
        return CandidateProfile(self._values(self.skills),self._values(self.titles),self._values(self.countries) or ("Worldwide",),
            self.salary.value(),self.remote.isChecked(),self._values(self.blocked))
    def _validate(self)->None:
        errors=self.profile().validate()
        if errors: self.error.setText("Please fix: "+" · ".join(errors)); return
        self.accept()


class SourceSettingsDialog(QDialog):
    def __init__(self,settings:dict[str,object],parent:QWidget|None=None)->None:
        super().__init__(parent); self.setWindowTitle("Discovery sources"); self.setMinimumWidth(480)
        layout=QVBoxLayout(self); intro=QLabel("Choose public feeds and how often JobRadar checks them while the app is open."); intro.setObjectName("muted"); intro.setWordWrap(True); layout.addWidget(intro)
        self.remotive=QCheckBox("Remotive · global remote roles"); self.remoteok=QCheckBox("Remote OK · technology and remote roles")
        enabled=set(settings.get("enabled",["Remotive","Remote OK"])); self.remotive.setChecked("Remotive" in enabled); self.remoteok.setChecked("Remote OK" in enabled)
        layout.addWidget(self.remotive); layout.addWidget(self.remoteok)
        form=QFormLayout(); self.interval=QComboBox(); self.interval.addItem("Manual only",0); self.interval.addItem("Every 30 minutes",30); self.interval.addItem("Every hour",60); self.interval.addItem("Every 3 hours",180)
        value=int(settings.get("interval_minutes",0)); index=max(0,self.interval.findData(value)); self.interval.setCurrentIndex(index); form.addRow("Automatic discovery",self.interval); layout.addLayout(form)
        note=QLabel("JobRadar sends no profile or résumé data to these feeds."); note.setObjectName("safety"); note.setWordWrap(True); layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Save); buttons.rejected.connect(self.reject); buttons.accepted.connect(self._validate); layout.addWidget(buttons)
    def _validate(self)->None:
        if not self.remotive.isChecked() and not self.remoteok.isChecked(): QMessageBox.warning(self,"Choose a source","Enable at least one discovery source."); return
        self.accept()
    def settings(self)->dict[str,object]:
        enabled=[]
        if self.remotive.isChecked():enabled.append("Remotive")
        if self.remoteok.isChecked():enabled.append("Remote OK")
        return {"enabled":enabled,"interval_minutes":int(self.interval.currentData())}


class GuideDialog(QDialog):
    def __init__(self,parent:QWidget|None=None,first_run:bool=False)->None:
        super().__init__(parent); self.setWindowTitle("Welcome to JobRadar AI" if first_run else "How JobRadar works"); self.setMinimumWidth(620)
        layout=QVBoxLayout(self); eyebrow=QLabel("A SAFER WAY TO FIND GLOBAL WORK"); eyebrow.setObjectName("eyebrow"); layout.addWidget(eyebrow)
        title=QLabel("From scattered listings to a focused application queue."); title.setObjectName("detailTitle"); title.setWordWrap(True); layout.addWidget(title)
        intro=QLabel("JobRadar collects public opportunities, explains why each role matches, and helps you prepare an application. You always decide what gets submitted."); intro.setObjectName("body"); intro.setWordWrap(True); layout.addWidget(intro)
        for number,heading,copy in (
            ("01","Set your preferences","Add target roles, skills, eligible locations and a salary target."),
            ("02","Discover and compare","Run discovery. Review the match evidence and risk signals—never just a mystery score."),
            ("03","Review before applying","Edit the generated draft, open the original listing, submit externally, then record the result.")):
            card=QFrame(); card.setObjectName("guideStep"); row=QHBoxLayout(card); num=QLabel(number); num.setObjectName("stepNumber"); text=QVBoxLayout(); h=QLabel(heading); h.setObjectName("stepTitle"); c=QLabel(copy); c.setObjectName("muted"); c.setWordWrap(True); text.addWidget(h); text.addWidget(c); row.addWidget(num); row.addLayout(text,1); layout.addWidget(card)
        safety=QLabel("JobRadar never accepts offers, signs contracts or sends applications without your explicit action."); safety.setObjectName("safety"); safety.setWordWrap(True); layout.addWidget(safety)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.accept); layout.addWidget(buttons)


class AuditDialog(QDialog):
    def __init__(self, records:list[dict[str,object]],parent:QWidget|None=None)->None:
        super().__init__(parent); self.setWindowTitle("Application activity"); self.resize(760,420)
        layout=QVBoxLayout(self); info=QLabel("A local record of every workflow status change."); info.setObjectName("muted"); layout.addWidget(info)
        table=QTableWidget(len(records),3); table.setHorizontalHeaderLabels(["Time","Action","Details"]); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row,record in enumerate(records):
            table.setItem(row,0,QTableWidgetItem(str(record["occurred_at"])[:19].replace("T"," ")))
            table.setItem(row,1,QTableWidgetItem(str(record["action"]).replace("_"," ").title()))
            table.setItem(row,2,QTableWidgetItem(str(record["details"])))
        table.horizontalHeader().setStretchLastSection(True); layout.addWidget(table)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(self.reject); layout.addWidget(close)


class DraftDialog(QDialog):
    approved=Signal(str,str)
    def __init__(self,job:Opportunity,profile:CandidateProfile,existing:dict[str,str]|None=None,parent:QWidget|None=None)->None:
        super().__init__(parent); self.job=job; self.setWindowTitle("Prepare application"); self.resize(700,620)
        layout=QVBoxLayout(self); title=QLabel(job.title); title.setObjectName("detailTitle"); layout.addWidget(title)
        meta=QLabel(f"{job.company} · {job.location}"); meta.setObjectName("muted"); layout.addWidget(meta)
        notice=QLabel("Review every word before using this draft. JobRadar will never submit or accept an offer without your explicit action.")
        notice.setObjectName("safety"); notice.setWordWrap(True); layout.addWidget(notice)
        skills=", ".join(s for s in profile.skills if s.lower() in f"{job.title} {job.description} {' '.join(job.tags)}".lower()) or ", ".join(profile.skills[:3])
        default=(f"Dear {job.company} hiring team,\n\nI am applying for the {job.title} position. "
            f"My experience with {skills} aligns with the role, and I am particularly interested in contributing to the work described in your listing.\n\n"
            "I would welcome the opportunity to discuss how my experience can support your team. Thank you for your consideration.\n\nKind regards")
        self.cover=QTextEdit(existing["cover_letter"] if existing else default); self.cover.setAccessibleName("Cover letter draft"); layout.addWidget(QLabel("Cover letter")); layout.addWidget(self.cover,1)
        self.notes=QTextEdit(existing["notes"] if existing else ""); self.notes.setMaximumHeight(90); self.notes.setPlaceholderText("Private notes, questions, or required documents…"); self.notes.setAccessibleName("Private application notes")
        layout.addWidget(QLabel("Private notes")); layout.addWidget(self.notes)
        actions=QHBoxLayout(); save=QPushButton("Save draft"); apply=QPushButton("Approve as applied"); apply.setObjectName("primary"); cancel=QPushButton("Cancel")
        save.clicked.connect(self._save); apply.clicked.connect(self._approve); cancel.clicked.connect(self.reject)
        actions.addWidget(cancel); actions.addStretch(); actions.addWidget(save); actions.addWidget(apply); layout.addLayout(actions)
    def _save(self)->None:
        if not self.cover.toPlainText().strip(): QMessageBox.warning(self,"Draft required","Write or generate a cover letter before saving."); return
        self.approved.emit(self.cover.toPlainText(),self.notes.toPlainText()); self.accept()
    def _approve(self)->None:
        if QMessageBox.question(self,"Confirm application record","Confirm that you reviewed this draft and submitted the application externally?")==QMessageBox.StandardButton.Yes:
            self.setProperty("markApplied",True); self._save()


class JobRadar(QMainWindow):
    discovery_complete = Signal(object, object)

    def __init__(self, store_path: str | Path | None = None) -> None:
        super().__init__(); self.setWindowTitle("JobRadar AI"); self.resize(1380, 860)
        if store_path is None:
            data_root=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)); data_root.mkdir(parents=True,exist_ok=True)
            store_path=data_root/"jobradar.db"
        self.store = OpportunityStore(store_path); self.needs_onboarding=not self.store.has_profile()
        default_profile = CandidateProfile(
            skills=("Python", "OpenCV", "FastAPI", "AI", "ONNX"),
            desired_titles=("Python", "Computer Vision", "AI"), min_salary=45000,
            blocked_terms=("unpaid", "commission only"),
        ); self.profile=self.store.load_profile(default_profile)
        if not self.store.all():
            for job in sample_opportunities(): self.store.upsert(score_opportunity(job, self.profile))
        self.source_settings=dict(self.store.get_setting("source_settings",{"enabled":["Remotive","Remote OK"],"interval_minutes":0}))
        self.jobs = self.store.all(); self.filtered = self.jobs
        self._build(); self._render_list(); self.discovery_complete.connect(self._finish_discovery)
        self.discovery_timer=QTimer(self); self.discovery_timer.timeout.connect(self._discover); self._configure_timer()
        if self.needs_onboarding: QTimer.singleShot(0,self._onboard)

    def _build(self) -> None:
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        nav = QFrame(); nav.setObjectName("nav"); nav.setFixedWidth(220)
        nv = QVBoxLayout(nav); nv.setContentsMargins(20, 22, 20, 20); nv.setSpacing(8)
        brand=QHBoxLayout(); icon=QLabel(); icon.setObjectName("brandIcon"); icon.setPixmap(QPixmap(str(Path(__file__).parent.parent/"assets"/"app-icon.png")).scaled(42,42,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        logo = QLabel("JobRadar\nAI"); logo.setObjectName("logo"); brand.addWidget(icon); brand.addWidget(logo); brand.addStretch(); nv.addLayout(brand)
        nv.addSpacing(26); section=QLabel("OPPORTUNITIES"); section.setObjectName("navLabel"); nv.addWidget(section)
        self.nav_group=QButtonGroup(self); self.nav_group.setExclusive(True)
        for text in ("Opportunity inbox", "Ready to apply"):
            b = QPushButton(text); b.setObjectName("navButton"); b.setCheckable(True)
            self.nav_group.addButton(b)
            if text == "Opportunity inbox": b.setChecked(True)
            if text == "Ready to apply": b.clicked.connect(lambda: self._show_status("Ready"))
            else: b.clicked.connect(lambda: self._show_status(None))
            nv.addWidget(b)
        nv.addSpacing(20); settings_label=QLabel("SETUP & CONTROL"); settings_label.setObjectName("navLabel"); nv.addWidget(settings_label)
        for text,handler in (("Profile & matching",self._edit_profile),("Sources & schedule",self._edit_sources),("Activity history",self._show_audit),("How JobRadar works",self._show_guide)):
            b=QPushButton(text); b.setObjectName("navButton"); b.clicked.connect(handler); nv.addWidget(b)
        nv.addStretch()
        privacy = QLabel("LOCAL WORKSPACE\nYour profile stays on this device"); privacy.setObjectName("privacy"); privacy.setWordWrap(True); nv.addWidget(privacy)
        outer.addWidget(nav)

        page = QWidget(); page.setObjectName("page"); layout = QVBoxLayout(page); layout.setContentsMargins(32, 26, 32, 28); layout.setSpacing(16)
        top = QHBoxLayout(); title = QVBoxLayout(); eyebrow = QLabel("GLOBAL OPPORTUNITY INTELLIGENCE"); eyebrow.setObjectName("eyebrow")
        heading = QLabel("Your best opportunities, ranked."); heading.setObjectName("heading")
        title.addWidget(eyebrow); title.addWidget(heading); top.addLayout(title); top.addStretch()
        self.scan = QPushButton("Find opportunities"); self.scan.setObjectName("primary"); self.scan.setToolTip("Check enabled public sources for new roles"); self.scan.clicked.connect(self._discover); top.addWidget(self.scan); layout.addLayout(top)

        journey=QFrame(); journey.setObjectName("journey"); jr=QHBoxLayout(journey); jr.setContentsMargins(18,12,18,12)
        for number,label in (("1","Profile ready"),("2","Discover roles"),("3","Review before applying")):
            n=QLabel(number); n.setObjectName("journeyNumber"); t=QLabel(label); t.setObjectName("journeyText"); jr.addWidget(n); jr.addWidget(t); jr.addSpacing(18)
        jr.addStretch(); help_btn=QPushButton("How it works"); help_btn.clicked.connect(self._show_guide); jr.addWidget(help_btn); layout.addWidget(journey)
        metrics = QHBoxLayout(); metrics.setSpacing(12)
        self.found = Metric(str(len(self.jobs)), "Discovered"); self.strong = Metric(str(sum(j.match_score >= 70 for j in self.jobs)), "Strong matches")
        self.queue = Metric(str(sum(j.status == "Ready" for j in self.jobs)), "Ready for review")
        for m in (self.found, self.strong, self.queue): metrics.addWidget(m)
        layout.addLayout(metrics)

        content = QHBoxLayout(); content.setSpacing(16)
        left = QFrame(); left.setObjectName("panel"); lv = QVBoxLayout(left); lv.setContentsMargins(16, 16, 16, 14); lv.setSpacing(10)
        list_head=QHBoxLayout(); label=QLabel("OPPORTUNITIES"); label.setObjectName("eyebrow"); list_head.addWidget(label); list_head.addStretch()
        self.status_filter=QComboBox(); self.status_filter.setAccessibleName("Filter by application status"); self.status_filter.addItems(["All statuses","New","Saved","Ready","Applied","Interview","Offer","Rejected","Archived"]); self.status_filter.currentTextChanged.connect(lambda value:self._show_status(None if value=="All statuses" else value)); list_head.addWidget(self.status_filter); lv.addLayout(list_head)
        search = QLineEdit(); search.setPlaceholderText("Search roles, skills or companies"); search.setClearButtonEnabled(True); search.textChanged.connect(self._filter); lv.addWidget(search)
        self.list = QListWidget(); self.list.currentRowChanged.connect(self._select); lv.addWidget(self.list); content.addWidget(left, 5)
        data_actions=QHBoxLayout(); imp=QPushButton("Import jobs"); exp=QPushButton("Export results"); imp.clicked.connect(self._import_csv); exp.clicked.connect(self._export_csv); data_actions.addWidget(imp); data_actions.addWidget(exp); data_actions.addStretch(); lv.addLayout(data_actions)
        self.detail = QFrame(); self.detail.setObjectName("detail"); self.dv = QVBoxLayout(self.detail); self.dv.setContentsMargins(26, 24, 26, 24); self.dv.setSpacing(12)
        content.addWidget(self.detail, 4); layout.addLayout(content, 1); outer.addWidget(page, 1)
        self._clear_detail(True)
        css = Path(__file__).with_name("style.qss").read_text(); self.setStyleSheet(css)

    def _render_list(self) -> None:
        self.list.clear()
        for job in self.filtered:
            item = QListWidgetItem(f"{job.match_score}% match  ·  {job.status}\n{job.title}\n{job.company}  ·  {job.location}")
            item.setData(Qt.ItemDataRole.UserRole, job.fingerprint); item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint().__class__(0, 86)))
            self.list.addItem(item)
        if self.list.count(): self.list.setCurrentRow(0)

    def _clear_detail(self, placeholder: bool = False) -> None:
        while self.dv.count():
            child = self.dv.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        if placeholder:
            empty = QLabel("Select an opportunity to inspect its match evidence and prepare an application."); empty.setObjectName("emptyState"); empty.setWordWrap(True); empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.dv.addStretch(); self.dv.addWidget(empty); self.dv.addStretch()

    def _select(self, row: int) -> None:
        if row < 0 or row >= len(self.filtered): return
        job = self.filtered[row]; self._clear_detail(False)
        badge = QLabel(f"{job.match_score}% MATCH   ·   RISK {job.risk_score}%"); badge.setObjectName("badge")
        title = QLabel(job.title); title.setObjectName("detailTitle"); title.setWordWrap(True)
        meta = QLabel(f"{job.company}  ·  {job.location}  ·  {job.source}"); meta.setObjectName("muted")
        summary = QLabel(job.description); summary.setWordWrap(True); summary.setObjectName("body")
        reasons = QLabel("WHY IT MATCHES\n" + "\n".join(f"• {reason}" for reason in job.reasons)); reasons.setObjectName("reason"); reasons.setWordWrap(True)
        safety = QLabel("Human approval required before any application is submitted. JobRadar never accepts contracts or offers automatically."); safety.setObjectName("safety"); safety.setWordWrap(True)
        actions = QHBoxLayout(); open_btn = QPushButton("Open listing"); open_btn.setEnabled(job.safe_url); open_btn.clicked.connect(lambda: webbrowser.open(job.url))
        status=QComboBox(); status.addItems(["New","Saved","Ready","Applied","Interview","Offer","Rejected","Archived"]); status.setCurrentText(job.status); status.currentTextChanged.connect(lambda value:self._set_status(job,value))
        ready = QPushButton("Review application draft"); ready.setObjectName("primary"); ready.clicked.connect(lambda: self._prepare_application(job))
        actions.addWidget(status); actions.addWidget(open_btn); actions.addWidget(ready)
        for widget in (badge, title, meta, summary, reasons, safety): self.dv.addWidget(widget)
        self.dv.addStretch(); self.dv.addLayout(actions)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip(); self.filtered = [j for j in self.jobs if needle in f"{j.title} {j.company} {j.location} {' '.join(j.tags)}".lower()]
        self._render_list()

    def _mark_ready(self, job: Opportunity) -> None:
        self._set_status(job,"Ready")

    def _prepare_application(self,job:Opportunity)->None:
        dialog=DraftDialog(job,self.profile,self.store.load_draft(job.fingerprint),self)
        def save(cover:str,notes:str)->None:
            self.store.save_draft(job.fingerprint,cover,notes)
            self._set_status(job,"Applied" if dialog.property("markApplied") else "Ready")
        dialog.approved.connect(save); dialog.exec()

    def _set_status(self,job:Opportunity,status:str)->None:
        if job.status==status:return
        job.status=status; self.store.set_status(job.fingerprint,status); self._refresh_metrics(); self._render_list()

    def _refresh_metrics(self)->None:
        self.found.findChild(QLabel,"metricValue").setText(str(len(self.jobs)))
        self.strong.findChild(QLabel,"metricValue").setText(str(sum(j.match_score>=70 for j in self.jobs)))
        self.queue.findChild(QLabel,"metricValue").setText(str(sum(j.status=="Ready" for j in self.jobs)))

    def _show_status(self,status:str|None)->None:
        self.filtered=self.store.all(status); self._render_list()

    def _edit_profile(self)->None:
        dialog=ProfileDialog(self.profile,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        self.profile=dialog.profile(); self.store.save_profile(self.profile)
        for job in self.jobs:self.store.upsert(score_opportunity(job,self.profile))
        self.jobs=self.store.all(); self.filtered=self.jobs; self._render_list(); self._refresh_metrics()

    def _onboard(self)->None:
        GuideDialog(self,True).exec()
        dialog=ProfileDialog(self.profile,self); dialog.setWindowTitle("Welcome to JobRadar AI")
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.profile=dialog.profile(); self.store.save_profile(self.profile); self.needs_onboarding=False

    def _edit_sources(self)->None:
        dialog=SourceSettingsDialog(self.source_settings,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        self.source_settings=dialog.settings(); self.store.set_setting("source_settings",self.source_settings); self._configure_timer()

    def _configure_timer(self)->None:
        minutes=int(self.source_settings.get("interval_minutes",0)); self.discovery_timer.stop()
        if minutes>0:self.discovery_timer.start(minutes*60*1000)

    def _show_audit(self)->None: AuditDialog(self.store.audit(),self).exec()
    def _show_guide(self)->None: GuideDialog(self).exec()
    def _show_safety(self)->None:
        QMessageBox.information(self,"Responsible automation","JobRadar automates discovery, scoring and preparation.\n\nApplications require your approval. Offers and contracts are never accepted automatically. Listings with unsafe links or scam language are risk-labelled.")

    def _import_csv(self)->None:
        path,_=QFileDialog.getOpenFileName(self,"Import opportunities","","CSV files (*.csv)")
        if not path:return
        try:
            jobs=import_csv(path)
            for job in jobs:self.store.upsert(score_opportunity(job,self.profile))
            self.jobs=self.store.all(); self.filtered=self.jobs; self._render_list(); self._refresh_metrics()
            QMessageBox.information(self,"Import complete",f"Imported {len(jobs)} valid opportunities.")
        except (OSError,ValueError) as exc: QMessageBox.critical(self,"Import failed",str(exc))

    def _export_csv(self)->None:
        path,_=QFileDialog.getSaveFileName(self,"Export opportunities","jobradar-opportunities.csv","CSV files (*.csv)")
        if not path:return
        try: export_csv(path,self.jobs); QMessageBox.information(self,"Export complete",f"Saved {len(self.jobs)} opportunities.")
        except OSError as exc: QMessageBox.critical(self,"Export failed",str(exc))

    def _discover(self) -> None:
        import threading
        self.scan.setEnabled(False); self.scan.setText("Discovering…")
        threading.Thread(target=self._discovery_worker, daemon=True).start()

    def _discovery_worker(self) -> None:
        jobs, errors = discover_public_jobs(enabled=set(self.source_settings.get("enabled",[])))
        self.discovery_complete.emit(jobs, errors)

    def _finish_discovery(self, jobs: list[Opportunity], errors: list[str]) -> None:
        for job in jobs: self.store.upsert(score_opportunity(job, self.profile))
        self.jobs = self.store.all(); self.filtered = self.jobs; self._render_list()
        self._refresh_metrics()
        self.scan.setEnabled(True)
        self.scan.setText(f"Find opportunities · {len(jobs)} new" if jobs else "Retry discovery")
        if errors: self.scan.setToolTip("Some sources were unavailable: " + "; ".join(errors))

    def closeEvent(self,event)->None:  # noqa: N802
        self.store.close(); event.accept()


def main() -> int:
    app = QApplication(sys.argv); app.setApplicationName("JobRadar AI")
    icon_path=Path(__file__).parent.parent/"assets"/"app-icon.png"
    if icon_path.exists(): app.setWindowIcon(QIcon(str(icon_path)))
    window = JobRadar(); window.show(); return app.exec()
