import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from PySide6.QtWidgets import QApplication
from jobradar.app import DraftDialog, GuideDialog, JobRadar, ProfileDialog, SourceSettingsDialog


def app():
    return QApplication.instance() or QApplication([])


def test_main_window_loads_and_filters(tmp_path):
    app(); window=JobRadar(tmp_path/"ui.db")
    assert window.list.count()==5
    window._filter("OpenCV")
    assert window.list.count()>=1
    window.close()


def test_profile_dialog_validates_required_fields(tmp_path):
    app(); window=JobRadar(tmp_path/"profile.db"); dialog=ProfileDialog(window.profile,window)
    dialog.skills.clear(); dialog.titles.clear(); dialog._validate()
    assert "at least one skill" in dialog.error.text()
    dialog.close(); window.close()


def test_status_change_is_audited(tmp_path):
    app(); window=JobRadar(tmp_path/"audit.db"); job=window.jobs[0]
    window._set_status(job,"Ready")
    assert window.store.audit()[0]["action"]=="status_changed"
    window.close()

def test_draft_dialog_generates_role_specific_content(tmp_path):
    app(); window=JobRadar(tmp_path/"draft-ui.db"); job=window.jobs[0]
    dialog=DraftDialog(job,window.profile,parent=window)
    assert job.title in dialog.cover.toPlainText()
    assert job.company in dialog.cover.toPlainText()
    dialog.close(); window.close()

def test_source_settings_require_one_enabled_source(tmp_path):
    app(); window=JobRadar(tmp_path/"sources.db"); dialog=SourceSettingsDialog(window.source_settings,window)
    dialog.remotive.setChecked(False); dialog.remoteok.setChecked(False)
    assert dialog.settings()["enabled"]==[]
    dialog.close(); window.close()

def test_guide_explains_three_step_workflow(tmp_path):
    app(); window=JobRadar(tmp_path/"guide.db"); guide=GuideDialog(window)
    text=" ".join(label.text() for label in guide.findChildren(type(window).mro()[1]) if hasattr(label,"text"))
    assert guide.windowTitle()=="How JobRadar works"
    guide.close(); window.close()
