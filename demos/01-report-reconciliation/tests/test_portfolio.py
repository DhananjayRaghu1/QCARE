import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import portfolio
import live_runner
from live_runner import Run
from live_server import LiveServer


@pytest.mark.parametrize('case_id', ['DH-401','DH-501'])
def test_comparison_changes_only_evidence_and_excludes_references(case_id):
    repo=portfolio.inputs(case_id,False); docs=portfolio.inputs(case_id,True)
    assert all(docs[path]==text for path,text in repo.items())
    assert all(path.startswith('business-docs/') for path in docs.keys()-repo.keys())
    assert not any('reference' in path or 'acceptance' in path or 'answer' in path for path in docs)
    assert 'title' not in json.loads(repo['issue.json'])


def test_prepared_export_is_executable_and_seed_fails_acceptance(tmp_path):
    for name,text in portfolio.inputs('DH-401',False).items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    failed=portfolio.acceptance(tmp_path)
    assert not failed['independent_passed']
    assert failed['repository_passed']
    reference=portfolio.reference_export()
    assert reference['checks']['passed'],reference['checks']['output']
    assert reference['csv']=='invoice_id,settlement_date,net_cents\nN-103,2026-09-15,-5000\nN-102,2026-09-30,19400\n'
    assert 'Ran 12 tests' in reference['checks']['output']
    assert 'Ran 2 tests' in reference['checks']['output']


def test_migration_removal_breaks_replay_while_current_code_passes():
    current,removed=portfolio.migration_checks()
    assert current['passed']
    assert not removed['passed']
    assert 'test_replay_v1_reversal' in removed['output']
    assert 'Unsupported format' in removed['output']


@pytest.mark.parametrize('protected_change', [False, True])
def test_feature_run_saves_patch_and_keeps_protected_inputs(monkeypatch,tmp_path,protected_change):
    monkeypatch.setattr(live_runner,'ROOT',tmp_path)
    monkeypatch.setattr(live_runner.agent,'preflight',lambda:{'authenticated':True})
    reference=(portfolio.BASE/'export/reference.py').read_text()
    script='from pathlib import Path\nPath("app/exporter.py").write_text('+repr(reference)+')\n'
    if protected_change: script+='Path("issue.json").unlink()\n'
    script+='print('+repr(json.dumps({'type':'result','result':'Stub implementation completed; this is not a model result.'}))+',flush=True)'
    monkeypatch.setattr(live_runner,'raw_command',lambda *args:[sys.executable,'-c',script])
    run=Run('DH-401','raw_docs',portfolio.PROMPTS['export']);run.execute()
    assert 'app/exporter.py' in run.result['patch']['files']
    assert (tmp_path/'artifacts/live'/run.id/'changes.patch').read_text()==run.result['patch']['diff']
    if protected_change:
        assert run.status=='failed'
        assert run.result['changed_input_files']==['issue.json']
    else:
        assert run.status=='completed',run.result
        assert run.result['implementation_checks']['passed']
    assert (portfolio.BASE/'export/app/exporter.py').read_text()!=reference


def test_patch_capture_rejects_symlink(tmp_path):
    (tmp_path/'app').mkdir();(tmp_path/'tests').mkdir()
    (tmp_path/'app/exporter.py').symlink_to(portfolio.BASE/'export/reference.py')
    with pytest.raises(ValueError):portfolio.capture_patch(tmp_path,{})


def test_patch_does_not_silently_omit_new_helper_modules(tmp_path):
    (tmp_path/'app').mkdir();(tmp_path/'tests').mkdir()
    (tmp_path/'app/exporter.py').write_text('')
    (tmp_path/'app/helper.py').write_text('def hidden_dependency(): pass')
    with pytest.raises(ValueError,match='extra code files'):portfolio.capture_patch(tmp_path,{})


def test_new_routes_three_demos_architecture_sources_and_only_first_ticket():
    server=LiveServer(0);threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    def get(path):
        with urlopen(base+path) as r:return r.read().decode()
    try:
        config=json.loads(get('/api/config'))
        assert [case['id'] for case in config['cases']]==['DH-301']
        assert len(json.loads(get('/api/demos'))['demos'])==3
        for name in ('report','export','migration'):
            assert '<!doctype html>' in get('/demos/'+name)
            architecture=get('/architecture/'+name)
            assert 'Proposed production design' in architecture
            assert 'Confluence' in architecture and 'Jira' in architecture
            assert 'Combine evidence' in architecture
        for id,doc in portfolio.documents().items():
            assert doc['title'] in get('/documents/'+id)
        for case,mode in [('DH-302','raw_repo'),('DH-401','workflow'),('DH-501','workflow')]:
            with pytest.raises(HTTPError) as error:
                urlopen(Request(base+'/api/runs',data=json.dumps({'case_id':case,'mode':mode}).encode(),headers={'X-Demo-Token':config['token']}))
            assert error.value.code==400
        assert not server.runs
    finally:
        server.shutdown();server.server_close()


def test_workflow_diagrams_are_served_locally_under_the_same_policy():
    server=LiveServer(0);threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/vendor/mermaid.min.js') as r:
            assert r.headers['Content-Type'].startswith('text/javascript')
            assert "script-src 'self' 'unsafe-inline';" in r.headers['Content-Security-Policy']
            assert len(r.read())>1_000_000
        with urlopen(base+'/diagrams.js') as r:
            text=r.read().decode()
            assert 'export' in text and 'migration' in text and "securityLevel:'strict'" in text
        for name in ('export','migration'):
            with urlopen(base+'/architecture/'+name) as r:
                page=r.read().decode()
                assert f'data-diagram="{name}"' in page
                assert page.index('/vendor/mermaid.min.js')<page.index('/diagrams.js')
        with urlopen(base+'/demos/export') as r:
            assert 'mermaid' not in r.read().decode()
    finally:
        server.shutdown();server.server_close()
