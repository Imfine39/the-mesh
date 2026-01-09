"""
Auto-generated tests from: タスク管理システム
Spec ID: SPEC-TASK-MANAGEMENT-V6
Version: v6.0
"""

import pytest
from typing import Dict, Any, List
from datetime import date, datetime, timedelta

# Date helpers
def today() -> str:
    return date.today().isoformat()

def now() -> str:
    return datetime.now().isoformat()

def date_diff(d1: str, d2: str, unit: str = 'days') -> int:
    """Calculate difference between two dates"""
    from datetime import datetime
    dt1 = datetime.fromisoformat(d1)
    dt2 = datetime.fromisoformat(d2)
    delta = dt2 - dt1
    if unit == 'days':
        return delta.days
    elif unit == 'hours':
        return int(delta.total_seconds() / 3600)
    return delta.days

def overlaps(start1: str, end1: str, start2: str, end2: str) -> bool:
    """Check if two date ranges overlap"""
    return start1 < end2 and start2 < end1

def add_days(d: str, days: int) -> str:
    """Add days to a date"""
    from datetime import datetime, timedelta
    dt = datetime.fromisoformat(d)
    return (dt + timedelta(days=days)).date().isoformat()


# ==================================================
# Helper Functions (generated from spec)
# ==================================================

class BusinessError(Exception):
    """ビジネスルール違反エラー"""
    def __init__(self, code: str, message: str = ''):
        self.code = code
        self.message = message
        super().__init__(f'{code}: {message}')


def project_progress(state: dict, entity: dict) -> Any:
    """プロジェクト進捗率（完了タスク数/全タスク数）"""
    # Parse error: 'NoneType' object has no attribute 'node_type'
    return entity.get('amount', 0)


def task_count(state: dict, entity: dict) -> Any:
    """プロジェクト内のタスク数"""
    # Parse error: 'NoneType' object has no attribute 'node_type'
    return entity.get('amount', 0)


def completed_task_count(state: dict, entity: dict) -> Any:
    """完了タスク数"""
    # Parse error: 'NoneType' object has no attribute 'node_type'
    return entity.get('amount', 0)


def total_estimated_hours(state: dict, entity: dict) -> Any:
    """プロジェクト見積もり工数合計"""
    # Formula (v6): {'sum': {'expr': 'item.estimated_hours', 'from': 'task as item', 'where': 'item....
    return sum(item.get('estimated_hours', 0) for item in state.get('task', []) if item.get('project_id') == entity.get('id'))


def total_actual_hours(state: dict, entity: dict) -> Any:
    """プロジェクト実績工数合計"""
    # Formula (v6): {'sum': {'expr': 'item.actual_hours', 'from': 'task as item', 'where': 'item.pro...
    return sum(item.get('actual_hours', 0) for item in state.get('task', []) if item.get('project_id') == entity.get('id'))


def create_task(state: dict, input_data: dict) -> dict:
    """タスクを作成"""

    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    user = state.get('user', {})
    if isinstance(user, list): user = user[0] if user else {}

    # 前提条件チェック
    if not ((project.get('status') == 'active')):
        raise BusinessError("PRECONDITION_FAILED", "アクティブなプロジェクトのみタスク追加可能")

    # 状態更新
    new_task = {'id': f'TASK-{len(state.get("task", [])) + 1:03d}', **input_data}
    new_task['project_id'] = input_data.get('project_id')
    new_task['title'] = input_data.get('title')
    new_task['description'] = input_data.get('description')
    new_task['assignee_id'] = input_data.get('assignee_id')
    new_task['status'] = 'todo'
    new_task['priority'] = input_data.get('priority')
    new_task['estimated_hours'] = input_data.get('estimated_hours')
    new_task['actual_hours'] = 0
    new_task['due_date'] = input_data.get('due_date')
    if 'task' not in state: state['task'] = []
    state['task'].append(new_task)

    return {'success': True}


def start_task(state: dict, input_data: dict) -> dict:
    """タスクを開始"""

    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    user = state.get('user', {})
    if isinstance(user, list): user = user[0] if user else {}

    # 前提条件チェック
    if not ((task.get('status') == 'todo')):
        raise BusinessError("PRECONDITION_FAILED", "未着手タスクのみ開始可能")

    # 状態更新
    task['status'] = 'in_progress'

    return {'success': True}


def complete_task(state: dict, input_data: dict) -> dict:
    """タスクを完了"""

    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    user = state.get('user', {})
    if isinstance(user, list): user = user[0] if user else {}

    # 前提条件チェック
    if not ((task.get('status') in ['in_progress', 'review'])):
        raise BusinessError("PRECONDITION_FAILED", "進行中またはレビュー中のタスクのみ完了可能")

    # 状態更新
    task['status'] = 'done'
    task['actual_hours'] = input_data.get('actual_hours')

    return {'success': True}


def cancel_task(state: dict, input_data: dict) -> dict:
    """タスクをキャンセル"""

    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    user = state.get('user', {})
    if isinstance(user, list): user = user[0] if user else {}

    # 前提条件チェック
    if not ((task.get('status') in ['todo', 'in_progress'])):
        raise BusinessError("PRECONDITION_FAILED", "未完了タスクのみキャンセル可能")

    # 状態更新
    task['status'] = 'cancelled'

    return {'success': True}


def complete_project(state: dict, input_data: dict) -> dict:
    """プロジェクトを完了"""

    project = state.get('project', {})
    if isinstance(project, list): project = project[0] if project else {}
    task = state.get('task', {})
    if isinstance(task, list): task = task[0] if task else {}
    user = state.get('user', {})
    if isinstance(user, list): user = user[0] if user else {}

    # ビジネスルールチェック
    # Parse error for error condition: 'NoneType' object has no attribute 'node_type'

    # 前提条件チェック
    if not ((project.get('status') == 'active')):
        raise BusinessError("PRECONDITION_FAILED", "アクティブなプロジェクトのみ完了可能")

    # 状態更新
    project['status'] = 'completed'

    return {'success': True}


# ==================================================
# Test Functions (generated from scenarios)
# ==================================================

def test_at_001_______():
    """タスクを作成
    """

    # Given: 初期状態
    state = {}
    state['project'] = {"id": "PROJ-001", "name": "新機能開発", "status": "active", "start_date": "2024-01-01", "due_date": "2024-03-31"}
    state['user'] = {"id": "USER-001", "name": "山田太郎", "email": "yamada@example.com", "role": "developer"}
    state['task'] = []

    # When: アクション実行
    input_data = {"project_id": "PROJ-001", "title": "ログイン機能", "description": "ログイン画面を実装", "assignee_id": "USER-001", "priority": "high", "estimated_hours": 8, "due_date": "2024-01-15"}
    result = create_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('status') == 'todo')


def test_at_002_______():
    """タスクを開始
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PROJ-001", "title": "ログイン機能", "description": "", "assignee_id": "USER-001", "status": "todo", "priority": "high", "estimated_hours": 8, "actual_hours": 0, "due_date": "2024-01-15"}

    # When: アクション実行
    input_data = {"task_id": "TASK-001"}
    result = start_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('status') == 'in_progress')


def test_at_003_______():
    """タスクを完了
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PROJ-001", "title": "ログイン機能", "description": "", "assignee_id": "USER-001", "status": "in_progress", "priority": "high", "estimated_hours": 8, "actual_hours": 0, "due_date": "2024-01-15"}

    # When: アクション実行
    input_data = {"task_id": "TASK-001", "actual_hours": 10}
    result = complete_task(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['task'].get('status') == 'done')
    assert (state['task'].get('actual_hours') == 10)


def test_at_004___________():
    """完了タスクは開始不可
    """

    # Given: 初期状態
    state = {}
    state['task'] = {"id": "TASK-001", "project_id": "PROJ-001", "title": "ログイン機能", "description": "", "assignee_id": "USER-001", "status": "done", "priority": "high", "estimated_hours": 8, "actual_hours": 10, "due_date": "2024-01-15"}

    # When: アクション実行
    input_data = {"task_id": "TASK-001"}

    # Then: エラー PRE_CONDITION_FAILED が発生すること
    try:
        result = start_task(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "PRE_CONDITION_FAILED"


def test_at_005_________():
    """プロジェクト完了
    """

    # Given: 初期状態
    state = {}
    state['project'] = {"id": "PROJ-001", "name": "新機能開発", "status": "active", "start_date": "2024-01-01", "due_date": "2024-03-31"}
    state['task'] = [{"id": "TASK-001", "project_id": "PROJ-001", "title": "タスク1", "description": "", "assignee_id": "USER-001", "status": "done", "priority": "high", "estimated_hours": 8, "actual_hours": 10, "due_date": "2024-01-15"}]

    # When: アクション実行
    input_data = {"project_id": "PROJ-001"}
    result = complete_project(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['project'].get('status') == 'completed')


def test_at_006_____________________():
    """未完了タスクがあるとプロジェクト完了不可
    """

    # Given: 初期状態
    state = {}
    state['project'] = {"id": "PROJ-001", "name": "新機能開発", "status": "active", "start_date": "2024-01-01", "due_date": "2024-03-31"}
    state['task'] = [{"id": "TASK-001", "project_id": "PROJ-001", "title": "タスク1", "description": "", "assignee_id": "USER-001", "status": "in_progress", "priority": "high", "estimated_hours": 8, "actual_hours": 0, "due_date": "2024-01-15"}]

    # When: アクション実行
    input_data = {"project_id": "PROJ-001"}

    # Then: エラー INCOMPLETE_TASKS が発生すること
    try:
        result = complete_project(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "INCOMPLETE_TASKS"



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
