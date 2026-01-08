"""
Auto-generated tests from: 施設予約システム
Spec ID: SPEC-RESERVATION-V5
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


def nights(state: dict, entity: dict) -> Any:
    """宿泊日数"""
    # Formula: date_diff(reservation.check_out_date, reservation.check_in_date)
    return date_diff(state, reservation)


def room_charge(state: dict, entity: dict) -> Any:
    """宿泊料金"""
    # Formula: room.price_per_night * nights(reservation)
    return (entity.get('price_per_night') * nights(state, reservation))


def is_room_available(state: dict, entity: dict) -> Any:
    """部屋が指定期間に空いているか"""
    # Formula: not exists(reservation where reservation.room_id == room.id and reservation.status in ['confirmed', 'checked_in'] and overlaps(reservation.check_in_date, reservation.check_out_date, input.check_in_date, input.check_out_date))
    # Parse error: Expected RPAREN, got IDENT at pos 83
    return entity.get('amount', 0)


def occupancy_rate(state: dict, entity: dict) -> Any:
    """稼働率（%）"""
    # Formula: (count(room where room.status == 'occupied') / count(room)) * 100
    return ((len([item for item in state.get('room', []) if (entity.get('status') == 'occupied')]) / count(state, entity)) * 100)


def cancel_fee_rate(state: dict, entity: dict) -> Any:
    """キャンセル料率"""
    # Formula: case when days_until_checkin >= 7 then 0 when days_until_checkin >= 3 then 0.3 when days_until_checkin >= 1 then 0.5 else 1.0 end
    # Parse error: Unexpected token after expression: when at pos 5
    return entity.get('amount', 0)


def make_reservation(state: dict, input_data: dict) -> dict:
    """予約を作成"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    payment = state.get('payment', {})
    if isinstance(payment, list): payment = payment[0] if payment else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # ビジネスルールチェック
    if (not is_room_available(state, room)):
        raise BusinessError("ROOM_NOT_AVAILABLE", "指定期間は予約済みです")
    if (input_data.get('num_guests') > room.get('capacity')):
        raise BusinessError("CAPACITY_EXCEEDED", "定員を超えています")

    # 前提条件チェック
    if not ((input_data.get('check_in_date') < input_data.get('check_out_date'))):
        raise BusinessError("PRECONDITION_FAILED", "チェックアウト日はチェックイン日より後")
    if not ((input_data.get('num_guests') <= room.get('capacity'))):
        raise BusinessError("PRECONDITION_FAILED", "定員オーバー")

    # 状態更新
    new_reservation = {'id': f'RESERVATION-{len(state.get("reservation", [])) + 1:03d}', **input_data}
    new_reservation['status'] = 'confirmed'
    if 'reservation' not in state: state['reservation'] = []
    state['reservation'].append(new_reservation)
    reservation['total_amount'] = room_charge(state, reservation)

    return {'success': True}


def cancel_reservation(state: dict, input_data: dict) -> dict:
    """予約をキャンセル"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    payment = state.get('payment', {})
    if isinstance(payment, list): payment = payment[0] if payment else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # ビジネスルールチェック
    if (reservation.get('status') == 'checked_in'):
        raise BusinessError("ALREADY_CHECKED_IN", "チェックイン済みの予約はキャンセルできません")

    # 前提条件チェック
    if not ((reservation.get('status') == 'confirmed')):
        raise BusinessError("PRECONDITION_FAILED", "確定済み予約のみキャンセル可能")

    # 状態更新
    reservation['status'] = 'cancelled'
    reservation['cancel_fee'] = (total_amount * cancel_fee_rate)

    return {'success': True}


def check_in(state: dict, input_data: dict) -> dict:
    """チェックイン処理"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    payment = state.get('payment', {})
    if isinstance(payment, list): payment = payment[0] if payment else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # ビジネスルールチェック
    if (today() < reservation.get('check_in_date')):
        raise BusinessError("TOO_EARLY", "チェックイン日より前です")

    # 前提条件チェック
    if not ((reservation.get('status') == 'confirmed')):
        raise BusinessError("PRECONDITION_FAILED", "確定済み予約のみチェックイン可能")
    if not ((today() >= reservation.get('check_in_date'))):
        raise BusinessError("PRECONDITION_FAILED", "チェックイン日以降のみ")

    # 状態更新
    reservation['status'] = 'checked_in'
    (room.get('status') == 'occupied')

    return {'success': True}


def check_out(state: dict, input_data: dict) -> dict:
    """チェックアウト処理"""

    guest = state.get('guest', {})
    if isinstance(guest, list): guest = guest[0] if guest else {}
    payment = state.get('payment', {})
    if isinstance(payment, list): payment = payment[0] if payment else {}
    reservation = state.get('reservation', {})
    if isinstance(reservation, list): reservation = reservation[0] if reservation else {}
    room = state.get('room', {})
    if isinstance(room, list): room = room[0] if room else {}

    # 前提条件チェック
    if not ((reservation.get('status') == 'checked_in')):
        raise BusinessError("PRECONDITION_FAILED", "チェックイン済み予約のみチェックアウト可能")

    # 状態更新
    reservation['status'] = 'checked_out'
    room['status'] = 'available'
    new_payment = {'id': f'PAYMENT-{len(state.get("payment", [])) + 1:03d}', **input_data}
    new_payment['amount'] = reservation.get('total_amount')
    if 'payment' not in state: state['payment'] = []
    state['payment'].append(new_payment)

    return {'success': True}


# ==================================================
# Test Functions (generated from scenarios)
# ==================================================

def test_at_001________():
    """空き部屋を予約
    
    Verifies: COND-001-1
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "available"}
    state['guest'] = {"id": "GUEST-001", "name": "山田太郎", "email": "yamada@example.com", "phone": "090-1234-5678"}
    state['reservation'] = []

    # When: アクション実行
    input_data = {"room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "num_guests": 2}
    result = make_reservation(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'confirmed')
    assert (state['reservation'].get('total_amount') == 30000)


def test_at_002____________():
    """予約済み期間は予約不可
    
    Verifies: COND-001-2
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "available"}
    state['guest'] = {"id": "GUEST-001", "name": "山田太郎", "email": "yamada@example.com", "phone": "090-1234-5678"}
    state['reservation'] = [{"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-002", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "status": "confirmed", "total_amount": 30000}]

    # When: アクション実行
    input_data = {"room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-21", "check_out_date": "2024-12-23", "num_guests": 2}

    # Then: エラー ROOM_NOT_AVAILABLE が発生すること
    try:
        result = make_reservation(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "ROOM_NOT_AVAILABLE"


def test_at_003_________():
    """予約をキャンセル
    
    Verifies: COND-002-1
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "available"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "status": "confirmed", "total_amount": 30000, "cancel_fee": 0}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = cancel_reservation(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'cancelled')


def test_at_004__________():
    """キャンセル料が発生
    
    Verifies: COND-002-2
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "available"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "status": "confirmed", "total_amount": 30000, "cancel_fee": 0}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = cancel_reservation(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('cancel_fee') >= 0)


def test_at_005________________():
    """チェックイン後はキャンセル不可
    
    Verifies: COND-002-3
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "occupied"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "status": "checked_in", "total_amount": 30000, "cancel_fee": 0}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}

    # Then: エラー ALREADY_CHECKED_IN が発生すること
    try:
        result = cancel_reservation(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "ALREADY_CHECKED_IN"


def test_at_006_________():
    """チェックイン処理
    
    Verifies: COND-003-1
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "available"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "status": "confirmed", "total_amount": 30000}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = check_in(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'checked_in')
    assert (state['room'].get('status') == 'occupied')


def test_at_007_______________():
    """チェックイン日より前はエラー
    
    Verifies: COND-003-2
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "available"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-25", "check_out_date": "2024-12-27", "status": "confirmed", "total_amount": 30000}

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}

    # Then: エラー TOO_EARLY が発生すること
    try:
        result = check_in(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "TOO_EARLY"


def test_at_008__________():
    """チェックアウト処理
    
    Verifies: COND-004-1
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "occupied"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "status": "checked_in", "total_amount": 30000}
    state['payment'] = []

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = check_out(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['reservation'].get('status') == 'checked_out')
    assert (state['room'].get('status') == 'available')


def test_at_009______________():
    """チェックアウト時に請求作成
    
    Verifies: COND-004-2
    """

    # Given: 初期状態
    state = {}
    state['room'] = {"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "occupied"}
    state['reservation'] = {"id": "RES-001", "room_id": "ROOM-101", "guest_id": "GUEST-001", "check_in_date": "2024-12-20", "check_out_date": "2024-12-22", "status": "checked_in", "total_amount": 30000}
    state['payment'] = []

    # When: アクション実行
    input_data = {"reservation_id": "RES-001"}
    result = check_out(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['payment'].get('amount') == 30000)


def test_at_010_______():
    """稼働率の計算
    
    Verifies: COND-005-1
    """

    # Given: 初期状態
    state = {}
    state['room'] = [{"id": "ROOM-101", "room_number": "101", "room_type": "double", "capacity": 2, "price_per_night": 15000, "status": "occupied"}, {"id": "ROOM-102", "room_number": "102", "room_type": "single", "capacity": 1, "price_per_night": 10000, "status": "occupied"}, {"id": "ROOM-103", "room_number": "103", "room_type": "twin", "capacity": 2, "price_per_night": 18000, "status": "available"}, {"id": "ROOM-104", "room_number": "104", "room_type": "suite", "capacity": 4, "price_per_night": 50000, "status": "available"}]

    # When: アクション実行
    input_data = {"reservation_id": "RES-003"}
    result = check_in(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (occupancy_rate == 50)



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
