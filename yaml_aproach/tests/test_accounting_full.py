"""
Auto-generated tests from: 会計システム - 消込管理
Spec ID: SPEC-ACCOUNTING-V6-FULL
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


def remaining(state: dict, entity: dict) -> Any:
    """請求の残額"""
    # Formula (v6): {'subtract': ['self.amount', {'sum': {'expr': 'item.amount', 'from': 'allocation...
    return (entity.get('amount') - sum(item.get('amount', 0) for item in state.get('allocation', []) if ((item.get('invoice_id') == entity.get('id')) and (item.get('status') == 'active'))))


def total_allocated(state: dict, entity: dict) -> Any:
    """入金の消込済み合計額"""
    # Formula (v6): {'sum': {'expr': 'item.amount', 'from': 'allocation as item', 'where': {'and': [...
    return sum(item.get('amount', 0) for item in state.get('allocation', []) if ((item.get('payment_id') == entity.get('id')) and (item.get('status') == 'active')))


def payment_remaining(state: dict, entity: dict) -> Any:
    """入金の未消込残額"""
    # Formula (v6): {'subtract': ['self.amount', {'call': 'total_allocated', 'args': ['self']}]}...
    return (entity.get('amount') - total_allocated(state, entity))


def allocate_payment(state: dict, input_data: dict) -> dict:
    """消込実行"""

    allocation = state.get('allocation', {})
    if isinstance(allocation, list): allocation = allocation[0] if allocation else {}
    customer = state.get('customer', {})
    if isinstance(customer, list): customer = customer[0] if customer else {}
    invoice = state.get('invoice', {})
    if isinstance(invoice, list): invoice = invoice[0] if invoice else {}
    payment = state.get('payment', {})
    if isinstance(payment, list): payment = payment[0] if payment else {}

    # ビジネスルールチェック
    if (remaining(state, invoice) < input_data.get('amount')):
        raise BusinessError("OVER_ALLOCATION", "残額を超える消込はできない")
    if (invoice.get('customer_id') != payment.get('customer_id')):
        raise BusinessError("CUSTOMER_MISMATCH", "請求と入金の顧客が一致しない")

    # 前提条件チェック
    if not ((invoice.get('status') == 'open')):
        raise BusinessError("PRECONDITION_FAILED", "クローズ済み請求には消込できない")
    if not ((payment_remaining(state, payment) >= input_data.get('amount'))):
        raise BusinessError("PRECONDITION_FAILED", "入金の未消込残額が不足")

    # 状態更新
    new_allocation = {'id': f'ALLOCATION-{len(state.get("allocation", [])) + 1:03d}', **input_data}
    new_allocation['invoice_id'] = input_data.get('invoice_id')
    new_allocation['payment_id'] = input_data.get('payment_id')
    new_allocation['amount'] = input_data.get('amount')
    new_allocation['status'] = 'active'
    if 'allocation' not in state: state['allocation'] = []
    state['allocation'].append(new_allocation)
    if (remaining(state, invoice) == 0):
        invoice['status'] = 'closed'

    return {'success': True}


def cancel_allocation(state: dict, input_data: dict) -> dict:
    """消込取り消し"""

    allocation = state.get('allocation', {})
    if isinstance(allocation, list): allocation = allocation[0] if allocation else {}
    customer = state.get('customer', {})
    if isinstance(customer, list): customer = customer[0] if customer else {}
    invoice = state.get('invoice', {})
    if isinstance(invoice, list): invoice = invoice[0] if invoice else {}
    payment = state.get('payment', {})
    if isinstance(payment, list): payment = payment[0] if payment else {}

    # 前提条件チェック
    if not ((allocation.get('status') == 'active')):
        raise BusinessError("PRECONDITION_FAILED", "既に取り消し済みの消込は取り消せない")

    # 状態更新
    allocation['status'] = 'cancelled'
    if (invoice.get('status') == 'closed'):
        invoice['status'] = 'open'

    return {'success': True}


# ==================================================
# Test Functions (generated from scenarios)
# ==================================================

def test_at_001_____________():
    """部分消込で残額が減少する
    
    Verifies: COND-001-1, COND-001-2
    """

    # Given: 初期状態
    state = {}
    state['customer'] = {"id": "CUST-001", "name": "株式会社テスト"}
    state['invoice'] = {"id": "INV-001", "customer_id": "CUST-001", "amount": 100000, "status": "open"}
    state['payment'] = {"id": "PAY-001", "customer_id": "CUST-001", "amount": 80000}
    state['allocation'] = []

    # When: アクション実行
    input_data = {"invoice_id": "INV-001", "payment_id": "PAY-001", "amount": 80000}
    result = allocate_payment(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (remaining(state, state['invoice']) == 20000)
    assert (state['invoice'].get('status') == 'open')


def test_at_002____________():
    """全額消込で自動クローズ
    
    Verifies: COND-002-1
    """

    # Given: 初期状態
    state = {}
    state['customer'] = {"id": "CUST-001", "name": "株式会社テスト"}
    state['invoice'] = {"id": "INV-001", "customer_id": "CUST-001", "amount": 100000, "status": "open"}
    state['payment'] = {"id": "PAY-001", "customer_id": "CUST-001", "amount": 100000}
    state['allocation'] = []

    # When: アクション実行
    input_data = {"invoice_id": "INV-001", "payment_id": "PAY-001", "amount": 100000}
    result = allocate_payment(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (remaining(state, state['invoice']) == 0)
    assert (state['invoice'].get('status') == 'closed')


def test_at_003_________():
    """残額超過でエラー
    
    Verifies: COND-003-1
    """

    # Given: 初期状態
    state = {}
    state['customer'] = {"id": "CUST-001", "name": "株式会社テスト"}
    state['invoice'] = {"id": "INV-001", "customer_id": "CUST-001", "amount": 100000, "status": "open"}
    state['payment'] = {"id": "PAY-001", "customer_id": "CUST-001", "amount": 150000}
    state['allocation'] = []

    # When: アクション実行
    input_data = {"invoice_id": "INV-001", "payment_id": "PAY-001", "amount": 120000}

    # Then: エラー OVER_ALLOCATION が発生すること
    try:
        result = allocate_payment(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "OVER_ALLOCATION"


def test_at_004__________():
    """顧客不一致でエラー
    
    Verifies: COND-004-1
    """

    # Given: 初期状態
    state = {}
    state['customer'] = {"id": "CUST-001", "name": "株式会社A"}
    state['invoice'] = {"id": "INV-001", "customer_id": "CUST-001", "amount": 100000, "status": "open"}
    state['payment'] = {"id": "PAY-001", "customer_id": "CUST-002", "amount": 100000}
    state['allocation'] = []

    # When: アクション実行
    input_data = {"invoice_id": "INV-001", "payment_id": "PAY-001", "amount": 100000}

    # Then: エラー CUSTOMER_MISMATCH が発生すること
    try:
        result = allocate_payment(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "CUSTOMER_MISMATCH"


def test_at_005_____________():
    """消込取り消しで残額が復活
    
    Verifies: COND-005-1
    """

    # Given: 初期状態
    state = {}
    state['customer'] = {"id": "CUST-001", "name": "株式会社テスト"}
    state['invoice'] = {"id": "INV-001", "customer_id": "CUST-001", "amount": 100000, "status": "closed"}
    state['payment'] = {"id": "PAY-001", "customer_id": "CUST-001", "amount": 100000}
    state['allocation'] = [{"id": "ALLOC-001", "invoice_id": "INV-001", "payment_id": "PAY-001", "amount": 100000, "status": "active"}]

    # When: アクション実行
    input_data = {"allocation_id": "ALLOC-001"}
    result = cancel_allocation(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (remaining(state, state['invoice']) == 100000)
    assert (state['invoice'].get('status') == 'open')



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
