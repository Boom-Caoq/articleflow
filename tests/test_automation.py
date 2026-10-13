import asyncio
import pytest
from app import automation, core, navigation

@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DATA', tmp_path)
    core.init()
    navigation.init()
    automation.init()
    monkeypatch.setattr(automation.time, 'time', lambda: 10000.0)

def row():
    return next(x for x in automation.listing() if x['kind']=='navigation')

def test_interval_change_replaces_old_future_plan(local):
    with core.db() as c:
        c.execute("UPDATE automations SET enabled=1,interval_minutes=1440,next_run=90000,last_run=100,status='completed',progress=100 WHERE kind='navigation'")
    automation.configure('navigation', True, 10, {'topic':'AI','limit':1})
    assert row()['next_run']==10600
    assert row()['progress']==0
    automation.configure('navigation', True, 10, {'topic':'AI video','limit':2})
    assert row()['next_run']==10600

def test_manual_run_while_disabled_and_duplicate_click(local):
    task_id=asyncio.run(automation.run_now('navigation'))
    assert task_id and not row()['enabled']
    assert row()['status']=='running'
    with pytest.raises(ValueError, match='已有任务'):
        asyncio.run(automation.run_now('navigation'))
    with core.db() as c:
        assert c.execute('SELECT count(*) FROM nav_tasks').fetchone()[0]==1
        c.execute("UPDATE nav_tasks SET status='completed',stage='done',logs='[]' WHERE id=?",(task_id,))
    asyncio.run(automation.tick())
    assert row()['status']=='completed'
    assert row()['next_run'] is None

def test_completion_schedules_once_and_returns_logs(local):
    automation.configure('navigation', True, 10, {'topic':'AI','limit':1})
    asyncio.run(automation.tick())
    task_id=row()['last_task_id']
    navigation.log(task_id, 'progress message')
    with core.db() as c:c.execute("UPDATE nav_tasks SET status='completed' WHERE id=?",(task_id,))
    asyncio.run(automation.tick())
    assert row()['next_run']==10600
    assert row()['logs'][-1]['message']=='progress message'
    asyncio.run(automation.tick())
    assert row()['last_task_id']==task_id
    assert row()['next_run']==10600

def test_startup_repairs_outdated_plan(local):
    with core.db() as c:c.execute("UPDATE automations SET enabled=1,interval_minutes=10,last_run=100,next_run=90000 WHERE kind='navigation'")
    automation.init()
    assert row()['next_run']==10600

def test_missing_task_does_not_stall_scheduler(local):
    with core.db() as c:c.execute("UPDATE automations SET enabled=1,status='running',last_task_id=999 WHERE kind='navigation'")
    asyncio.run(automation.tick())
    assert row()['last_task_id']!=999
    assert row()['status']=='running'
