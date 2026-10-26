from jobradar import sources


def test_remotive_connector_maps_public_payload(monkeypatch):
    monkeypatch.setattr(sources,"_json",lambda *args,**kwargs:{"jobs":[{
        "title":"Vision Engineer","company_name":"Acme","candidate_required_location":"Worldwide",
        "description":"<p>Python &amp; OpenCV</p>","url":"https://example.com/job","category":"Software","job_type":"full_time"}]})
    jobs=sources.fetch_remotive(1)
    assert jobs[0].company=="Acme" and jobs[0].remote
    assert "<p>" not in jobs[0].description


def test_remoteok_connector_ignores_metadata(monkeypatch):
    monkeypatch.setattr(sources,"_json",lambda *args,**kwargs:[{"legal":"metadata"},{
        "position":"Python Engineer","company":"Acme","description":"Build things",
        "url":"https://example.com/job","tags":["python"]}])
    jobs=sources.fetch_remoteok(1)
    assert len(jobs)==1 and jobs[0].title=="Python Engineer"

def test_disabled_connector_is_not_called(monkeypatch):
    monkeypatch.setattr(sources,"fetch_remoteok",lambda timeout:(_ for _ in ()).throw(AssertionError()))
    monkeypatch.setitem(sources.CONNECTORS,"Remote OK",sources.fetch_remoteok)
    monkeypatch.setitem(sources.CONNECTORS,"Remotive",lambda timeout:[])
    jobs,errors=sources.discover_public_jobs(enabled={"Remotive"})
    assert jobs==[] and errors==[]
