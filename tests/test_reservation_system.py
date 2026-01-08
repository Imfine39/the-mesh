"""
Auto-generated tests from: 施設予約システム
Spec ID: SPEC-RESERVATION-V6
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


def stay_duration(state: dict, entity: dict) -> Any:
    """宿泊日数"""
    # Formula (v6): {'date_diff': {'from': 'self.check_in_date', 'to': 'self.check_out_date', 'unit'...
    return date_diff(entity.get('check_in_date'), entity.get('check_out_date'), 'days')


def reservation_total(state: dict, entity: dict) -> Any:
    """予約合計金額"""
    # Formula (v6): {'multiply': ['room.price_per_night', {'call': 'stay_duration', 'args': ['self']...
    return (room.get('price_per_night') * stay_duration(state, entity))


def days_until_checkin(state: dict, entity: dict) -> Any:
    """チェックインまでの日数"""
    # Parse error: expected string or bytes-like object, got 'dict'
    return entity.get('amount', 0)


def cancellation_fee_rate(state: dict, entity: dict) -> Any:
    """キャンセル料率"""
    # Formula (v6): {'case': [{'when': {'ge': [{'call': 'days_until_checkin', 'args': ['self']}, 7]}...
    return (0 if (days_until_checkin(state, entity) >= 7) else (0.3 if (days_until_checkin(state, entity) >= 3) else 1.0))


def create_reservation(state: dict, input_data: dict) -> dict:
    """予約を作成"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # ビジネスルールチェック
    # Parse error for error condition: 'NoneType' object has no attribute 'node_type'

    # 前提条件チェック
    if not ((room.get('status') == 'available')):
        raise BusinessError("PRECONDITION_FAILED", "利用可能な部屋のみ予約できる")

    # 状態更新
    new_reservation = {'id': f'RESERVATION-{len(state.get("reservation", [])) + 1:03d}', **input_data}
    new_reservation['room_id'] = input_data.get('room_id')
    new_reservation['guest_id'] = input_data.get('guest_id')
    new_reservation['check_in_date'] = input_data.get('check_in_date')
    new_reservation['check_out_date'] = input_data.get('check_out_date')
    new_reservation['num_guests'] = input_data.get('num_guests')
    new_reservation['status'] = 'confirmed'
    new_reservation['total_amount'] = 0
    if 'reservation' not in state: state['reservation'] = []
    state['reservation'].append(new_reservation)

    return {'success': True}


def cancel_reservation(state: dict, input_data: dict) -> dict:
    """予約をキャンセル"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # ビジネスルールチェック
    if (reservation.get('status') == 'checked_in'):
        raise BusinessError("ALREADY_CHECKED_IN", "チェックイン後はキャンセルできません")

    # 前提条件チェック
    if not ((reservation.get('status') == 'confirmed')):
        raise BusinessError("PRECONDITION_FAILED", "確定済み予約のみキャンセル可能")

    # 状態更新
    reservation['status'] = 'cancelled'

    return {'success': True}


def check_in(state: dict, input_data: dict) -> dict:
    """チェックイン"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # 前提条件チェック
    if not ((reservation.get('status') == 'confirmed')):
        raise BusinessError("PRECONDITION_FAILED", "確定済み予約のみチェックイン可能")

    # 状態更新
    reservation['status'] = 'checked_in'
    room['status'] = 'occupied'

    return {'success': True}


def check_out(state: dict, input_data: dict) -> dict:
    """チェックアウト"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # 前提条件チェック
    if not ((reservation.get('status') == 'checked_in')):
        raise BusinessError("PRECONDITION_FAILED", "チェックイン中の予約のみチェックアウト可能")

    # 状態更新
    reservation['status'] = 'checked_out'
    room['status'] = 'available'

    return {'success': True}


# ==================================================
# Test Functions (generated from scenarios)
# ==================================================

def test_at_001________():
    """空き部屋を予約
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-001", "room_number": "101", "room_type": "single", "capacity": 1, "price_per_night": 8000, "status": "available"}
    state['guest'] = {"id": "GUEST-001", "name": "田中太郎", "email": "tanaka@example.com"}
    state['reservation'] = []

    # When: アクション実行
    input_data = {"room_id": "ROOM-001", "guest_id": "GUEST-001", "check_in_date": "2024-03-01", "check_out_date": "2024-03-03", "num_guests": 1}
    result = create_reservation(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'confirmed')


def test_at_002____________():
    """予約済み部屋は予約不可
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-001", "room_number": "101", "room_type": "single", "capacity": 1, "price_per_night": 8000, "status": "available"}
    state['guest'] = {"id": "GUEST-001", "name": "田中太郎", "email": "tanaka@example.com"}
    state['reservation'] = [{"id": "RES-001", "room_id": "ROOM-001", "guest_id": "GUEST-001", "check_in_date": "2024-03-01", "check_out_date": "2024-03-03", "num_guests": 1, "status": "confirmed", "total_amount": 16000}]

    # When: アクション実行
    input_data = {"room_id": "ROOM-001", "guest_id": "GUEST-002", "check_in_date": "2024-03-02", "check_out_date": "2024-03-04", "num_guests": 1}

    # Then: エラー ROOM_NOT_AVAILABLE が発生すること
    try:
        result = create_reservation(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "ROOM_NOT_AVAILABLE"


def test_at_003________():
    """予約キャンセル
    """

    # Given: 初期状態
    state = {}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-001", "guest_id": "GUEST-001", "check_in_date": "2024-03-10", "check_out_date": "2024-03-12", "num_guests": 1, "status": "confirmed", "total_amount": 16000}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = cancel_reservation(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'cancelled')


def test_at_004_______():
    """チェックイン
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-001", "room_number": "101", "room_type": "single", "capacity": 1, "price_per_night": 8000, "status": "available"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-001", "guest_id": "GUEST-001", "check_in_date": "2024-03-01", "check_out_date": "2024-03-03", "num_guests": 1, "status": "confirmed", "total_amount": 16000}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = check_in(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'checked_in')
    assert (state['room'].get('status') == 'occupied')


def test_at_005________():
    """チェックアウト
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-001", "room_number": "101", "room_type": "single", "capacity": 1, "price_per_night": 8000, "status": "occupied"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-001", "guest_id": "GUEST-001", "check_in_date": "2024-03-01", "check_out_date": "2024-03-03", "num_guests": 1, "status": "checked_in", "total_amount": 16000}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = check_out(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'checked_out')
    assert (state['room'].get('status') == 'available')


def test_at_006_________________():
    """チェックイン済みはキャンセル不可
    """

    # Given: 初期状態
    state = {}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-001", "guest_id": "GUEST-001", "check_in_date": "2024-03-01", "check_out_date": "2024-03-03", "num_guests": 1, "status": "checked_in", "total_amount": 16000}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}

    # Then: エラー ALREADY_CHECKED_IN が発生すること
    try:
        result = cancel_reservation(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "ALREADY_CHECKED_IN"



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
