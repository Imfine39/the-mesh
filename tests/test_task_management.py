"""
Auto-generated tests from: タスク管理システム
Spec ID: SPEC-TASK-MGMT-V5
Version: v5.0
"""

import pytest
from typing import Dict, Any, List
from datetime import date, datetime

# Date helper
def today() -> str:
    return date.today().isoformat()


# ==================================================
# Helper Functions (generated from spec)
# ==================================================

class BusinessError(Exception):
    """ビジネスルール違反エラー"""
    def __init__(self, code: str, message: str = ''):
        self.code = code
        self.message = message
        super().__init__(f'{code}: {message}')


def total_tasks(state: dict, entity: dict) -> Any:
    """プロジェクトの全タスク数"""
    # Formula: count(task where task.project_id == project.id)
    return len([item for item in state.get('task', []) if (item.get('project_id') == project.get('id'))])


def done_tasks(state: dict, entity: dict) -> Any:
    """プロジェクトの完了タスク数"""
    # Formula: count(task where task.project_id == project.id and task.status == 'done')
    return len([item for item in state.get('task', []) if ((item.get('project_id') == project.get('id')) and (item.get('status') == 'done'))])


def progress_rate(state: dict, entity: dict) -> Any:
    """プロジェクト進捗率（%）"""
    # Formula: (done_tasks(project) / total_tasks(project)) * 100
    try:
        return ((done_tasks(state, entity) / total_tasks(state, entity)) * 100)
    except ZeroDivisionError:
        return 0


def actual_hours(state: dict, entity: dict) -> Any:
    """タスクの実績時間"""
    # Formula: sum(time_entry.hours where time_entry.task_id == task.id)
    return sum(item.get('hours', 0) for item in state.get('time_entry', []) if (item.get('task_id') == task.get('id')))


def remaining_hours(state: dict, entity: dict) -> Any:
    """タスクの残り時間"""
    # Formula: task.estimated_hours - actual_hours(task)
    return (entity.get('estimated_hours') - actual_hours(state, entity))


def create_task(state: dict, input_data: dict) -> dict:
    """タスクを作成"""

    member = state.get('member', {})
    if isinstance(member, list): member = member[0] if member else {}
    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    time_entry = state.get('time_entry', {})
    if isinstance(time_entry, list): time_entry = time_entry[0] if time_entry else {}

    # 前提条件チェック
    if not ((project.get('status') == 'active')):
        raise BusinessError("PRECONDITION_FAILED", "アクティブなプロジェクトにのみタスクを追加可能")

    # 状態更新
    new_task = {'id': f'TASK-{len(state.get("task", [])) + 1:03d}', **input_data}
    new_task['status'] = 'todo'
    if 'task' not in state: state['task'] = []
    state['task'].append(new_task)

    return {'success': True}


def assign_task(state: dict, input_data: dict) -> dict:
    """タスクに担当者をアサイン"""

    member = state.get('member', {})
    if isinstance(member, list): member = member[0] if member else {}
    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    time_entry = state.get('time_entry', {})
    if isinstance(time_entry, list): time_entry = time_entry[0] if time_entry else {}

    # 前提条件チェック
    if not ((task.get('status') != 'done')):
        raise BusinessError("PRECONDITION_FAILED", "完了タスクにはアサインできない")

    # 状態更新
    task['assignee_id'] = input_data.get('assignee_id')

    return {'success': True}


def start_task(state: dict, input_data: dict) -> dict:
    """タスクを開始"""

    member = state.get('member', {})
    if isinstance(member, list): member = member[0] if member else {}
    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    time_entry = state.get('time_entry', {})
    if isinstance(time_entry, list): time_entry = time_entry[0] if time_entry else {}

    # ビジネスルールチェック
    if (task.get('assignee_id') is None):
        raise BusinessError("NOT_ASSIGNED", "担当者が未設定です")

    # 前提条件チェック
    if not ((task.get('status') == 'todo')):
        raise BusinessError("PRECONDITION_FAILED", "未着手タスクのみ開始可能")
    if not ((task.get('assignee_id') is not None)):
        raise BusinessError("PRECONDITION_FAILED", "担当者がアサインされていないと開始できない")

    # 状態更新
    task['status'] = 'in_progress'

    return {'success': True}


def complete_task(state: dict, input_data: dict) -> dict:
    """タスクを完了"""

    member = state.get('member', {})
    if isinstance(member, list): member = member[0] if member else {}
    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    time_entry = state.get('time_entry', {})
    if isinstance(time_entry, list): time_entry = time_entry[0] if time_entry else {}

    # 前提条件チェック
    if not ((task.get('status') == 'in_progress')):
        raise BusinessError("PRECONDITION_FAILED", "進行中タスクのみ完了可能")

    # 状態更新
    (task.get('status') == 'done')

    return {'success': True}


def reopen_task(state: dict, input_data: dict) -> dict:
    """タスクを再オープン"""

    member = state.get('member', {})
    if isinstance(member, list): member = member[0] if member else {}
    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    time_entry = state.get('time_entry', {})
    if isinstance(time_entry, list): time_entry = time_entry[0] if time_entry else {}

    # 前提条件チェック
    if not ((task.get('status') == 'done')):
        raise BusinessError("PRECONDITION_FAILED", "完了タスクのみ再オープン可能")

    # 状態更新
    task['status'] = 'todo'

    return {'success': True}


def log_time(state: dict, input_data: dict) -> dict:
    """作業時間を記録"""

    member = state.get('member', {})
    if isinstance(member, list): member = member[0] if member else {}
    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    time_entry = state.get('time_entry', {})
    if isinstance(time_entry, list): time_entry = time_entry[0] if time_entry else {}

    # 前提条件チェック
    if not ((input_data.get('hours') > 0)):
        raise BusinessError("PRECONDITION_FAILED", "記録時間は正の値")

    # 状態更新
    new_time_entry = {'id': f'TIME_ENTRY-{len(state.get("time_entry", [])) + 1:03d}', **input_data}
    if 'time_entry' not in state: state['time_entry'] = []
    state['time_entry'].append(new_time_entry)

    return {'success': True}


# ==================================================
# Test Functions (generated from scenarios)
# ==================================================

def test_at_001______________():
    """プロジェクトにタスクを追加
    
    Verifies: COND-001-1
    """

    # Given: 初期状態
    state = {}
    state['project'] = {"id": "PRJ-001", "name": "Webサイトリニューアル", "status": "active"}
    state['task'] = []

    # When: アクション実行
    input_data = {"project_id": "PRJ-001", "title": "デザイン作成", "priority": "high"}
    result = create_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (total_tasks(state, state['project']) == 1)


def test_at_002_____________():
    """タスクに担当者をアサイン
    
    Verifies: COND-001-2
    """

    # Given: 初期状態
    state = {}
    state['member'] = {"id": "MEM-001", "name": "田中太郎", "email": "tanaka@example.com", "role": "developer"}
    state['task'] = {"id": "TASK-001", "project_id": "PRJ-001", "title": "デザイン作成", "status": "todo", "priority": "high", "assignee_id": None}

    # When: アクション実行
    input_data = {"task_id": "TASK-001", "assignee_id": "MEM-001"}
    result = assign_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('assignee_id') == 'MEM-001')


def test_at_003_______():
    """タスクを開始
    
    Verifies: COND-002-1
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PRJ-001", "title": "デザイン作成", "status": "todo", "priority": "high", "assignee_id": "MEM-001"}

    # When: アクション実行
    input_data = {"task_id": "TASK-001"}
    result = start_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('status') == 'in_progress')


def test_at_004_______():
    """タスクを完了
    
    Verifies: COND-002-2
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PRJ-001", "title": "デザイン作成", "status": "in_progress", "priority": "high", "assignee_id": "MEM-001"}

    # When: アクション実行
    input_data = {"task_id": "TASK-001"}
    result = complete_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('status') == 'done')


def test_at_005____________():
    """完了タスクを再オープン
    
    Verifies: COND-002-3
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PRJ-001", "title": "デザイン作成", "status": "done", "priority": "high", "assignee_id": "MEM-001"}

    # When: アクション実行
    input_data = {"task_id": "TASK-001"}
    result = reopen_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('status') == 'todo')


def test_at_006_____________():
    """プロジェクト進捗率の計算
    
    Verifies: COND-003-1
    """

    # Given: 初期状態
    state = {}
    state['project'] = {"id": "PRJ-001", "name": "Webサイトリニューアル", "status": "active"}
    state['task'] = [{"id": "TASK-001", "project_id": "PRJ-001", "title": "タスク1", "status": "done", "priority": "medium", "assignee_id": "MEM-001"}, {"id": "TASK-002", "project_id": "PRJ-001", "title": "タスク2", "status": "done", "priority": "medium", "assignee_id": "MEM-001"}, {"id": "TASK-003", "project_id": "PRJ-001", "title": "タスク3", "status": "in_progress", "priority": "medium", "assignee_id": "MEM-001"}, {"id": "TASK-004", "project_id": "PRJ-001", "title": "タスク4", "status": "todo", "priority": "medium", "assignee_id": None}]

    # When: アクション実行
    input_data = {"task_id": "TASK-003"}
    result = complete_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (progress_rate(state, state['project']) == 75)


def test_at_007___________():
    """タスクに優先度を設定
    
    Verifies: COND-004-1
    """

    # Given: 初期状態
    state = {}
    state['project'] = {"id": "PRJ-001", "name": "Webサイトリニューアル", "status": "active"}
    state['task'] = []

    # When: アクション実行
    input_data = {"project_id": "PRJ-001", "title": "緊急バグ修正", "priority": "high"}
    result = create_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('priority') == 'high')


def test_at_008__________():
    """タスクに期限を設定
    
    Verifies: COND-005-1
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PRJ-001", "title": "デザイン作成", "status": "todo", "priority": "high", "assignee_id": "MEM-001", "due_date": "2024-12-31"}

    # When: アクション実行
    input_data = {"task_id": "TASK-001"}
    result = start_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('due_date') == '2024-12-31')


def test_at_009___________():
    """担当者未設定でエラー
    
    Verifies: COND-002-1
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PRJ-001", "title": "デザイン作成", "status": "todo", "priority": "high", "assignee_id": None}

    # When: アクション実行
    input_data = {"task_id": "TASK-001"}

    # Then: エラー NOT_ASSIGNED が発生すること
    try:
        result = start_task(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "NOT_ASSIGNED"


def test_at_010________():
    """作業時間を記録
    
    Verifies: COND-006-1
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PRJ-001", "title": "デザイン作成", "status": "in_progress", "priority": "high", "assignee_id": "MEM-001", "estimated_hours": 8}
    state['time_entry'] = []

    # When: アクション実行
    input_data = {"task_id": "TASK-001", "hours": 2}
    result = log_time(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (actual_hours(state, state['task']) == 2)
    assert (remaining_hours(state, state['task']) == 6)



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
