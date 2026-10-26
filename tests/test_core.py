from jobradar.core import CandidateProfile, Opportunity, deduplicate, score_opportunity
from jobradar.interchange import export_csv, import_csv
from jobradar.storage import OpportunityStore


PROFILE = CandidateProfile(("Python", "OpenCV"), ("Python", "Computer Vision"), min_salary=40000)


def test_strong_relevant_remote_job_scores_high():
    job = Opportunity("Python Computer Vision Engineer", "Acme", "Remote", "Python and OpenCV", "https://example.com/job", "feed", 50000, True)
    assert score_opportunity(job, PROFILE).match_score >= 90


def test_scam_language_reduces_score_and_increases_risk():
    job = Opportunity("Python Engineer", "Acme", "Remote", "Pay a registration fee via gift card", "u", "feed", 50000, True)
    result = score_opportunity(job, PROFILE)
    assert result.risk_score >= 70
    assert result.match_score < 70


def test_fingerprint_deduplicates_same_role():
    jobs = [Opportunity("Python Engineer", "Acme", "Remote", "A", "1", "a"), Opportunity("Python Engineer", "Acme", "Remote", "B", "2", "b")]
    assert len(deduplicate(jobs)) == 1

def test_non_https_link_adds_risk():
    job=Opportunity("Python Engineer","Acme","Remote","Python","http://example.com","feed",remote=True)
    assert score_opportunity(job,PROFILE).risk_score==35

def test_profile_validation():
    assert CandidateProfile((),(),min_salary=-1).validate()==[
        "Add at least one skill","Add at least one target role","Minimum salary cannot be negative"]

def test_store_persists_profile_status_and_audit(tmp_path):
    store=OpportunityStore(tmp_path/"test.db"); store.save_profile(PROFILE)
    assert store.load_profile(CandidateProfile(("x",),("x",)))==PROFILE
    job=score_opportunity(Opportunity("Python Engineer","Acme","Remote","Python","https://example.com","feed",remote=True),PROFILE)
    store.upsert(job); store.set_status(job.fingerprint,"Ready")
    assert store.all()[0].status=="Ready"; assert store.audit()[0]["action"]=="status_changed"

def test_csv_round_trip(tmp_path):
    path=tmp_path/"jobs.csv"; job=Opportunity("Python Engineer","Acme","Remote","Python","https://example.com","feed",50000,True,["Python"])
    export_csv(path,[job]); loaded=import_csv(path)
    assert loaded[0].title==job.title and loaded[0].remote is True

def test_application_draft_is_persisted_and_audited(tmp_path):
    store=OpportunityStore(tmp_path/"draft.db")
    job=score_opportunity(Opportunity("Python Engineer","Acme","Remote","Python","https://example.com","feed",remote=True),PROFILE)
    store.upsert(job); store.save_draft(job.fingerprint,"A carefully reviewed letter","private note")
    assert store.load_draft(job.fingerprint)["notes"]=="private note"
    assert store.audit()[0]["action"]=="draft_saved"

def test_generic_settings_are_json_persisted(tmp_path):
    store=OpportunityStore(tmp_path/"settings.db"); value={"enabled":["Remotive"],"interval_minutes":60}
    store.set_setting("source_settings",value)
    assert store.get_setting("source_settings")==value
