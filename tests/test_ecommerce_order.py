"""
Auto-generated tests from: ECサイト - 注文管理
Spec ID: SPEC-ECOMMERCE-ORDER-V5
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


def cart_total(state: dict, entity: dict) -> Any:
    """カート合計金額"""
    # Formula: sum(product.price * cart_item.quantity where cart_item.cart_id == cart.id)
    # Parse error: Invalid aggregation: sum
    return entity.get('amount', 0)


def order_total(state: dict, entity: dict) -> Any:
    """注文合計金額"""
    # Formula: sum(order_item.unit_price * order_item.quantity where order_item.order_id == order.id)
    # Parse error: Invalid aggregation: sum
    return entity.get('amount', 0)


def cart_item_count(state: dict, entity: dict) -> Any:
    """カート内の商品数"""
    # Formula: sum(cart_item.quantity where cart_item.cart_id == cart.id)
    return sum(item.get('quantity', 0) for item in state.get('cart_item', []) if (item.get('cart_id') == cart.get('id')))


def available_stock(state: dict, entity: dict) -> Any:
    """利用可能在庫数"""
    # Formula: product.stock
    return entity.get('stock')


def add_to_cart(state: dict, input_data: dict) -> dict:
    """カートに商品を追加"""

    cart = state.get('cart', {})
    if isinstance(cart, list): cart = cart[0] if cart else {}
    cart_item = state.get('cart_item', {})
    if isinstance(cart_item, list): cart_item = cart_item[0] if cart_item else {}
    order = state.get('order', {})
    if isinstance(order, list): order = order[0] if order else {}
    order_item = state.get('order_item', {})
    if isinstance(order_item, list): order_item = order_item[0] if order_item else {}
    product = state.get('product', {})
    if isinstance(product, list): product = product[0] if product else {}

    # ビジネスルールチェック
    if (product.get('stock') < input_data.get('quantity')):
        raise BusinessError("OUT_OF_STOCK", "在庫が不足しています")

    # 前提条件チェック
    if not ((cart.get('status') == 'active')):
        raise BusinessError("PRECONDITION_FAILED", "注文済みカートには追加できない")

    # 状態更新
    new_cart_item = {'id': f'CART_ITEM-{len(state.get("cart_item", [])) + 1:03d}', **input_data}
    if 'cart_item' not in state: state['cart_item'] = []
    state['cart_item'].append(new_cart_item)

    return {'success': True}


def place_order(state: dict, input_data: dict) -> dict:
    """注文を確定"""

    cart = state.get('cart', {})
    if isinstance(cart, list): cart = cart[0] if cart else {}
    cart_item = state.get('cart_item', {})
    if isinstance(cart_item, list): cart_item = cart_item[0] if cart_item else {}
    order = state.get('order', {})
    if isinstance(order, list): order = order[0] if order else {}
    order_item = state.get('order_item', {})
    if isinstance(order_item, list): order_item = order_item[0] if order_item else {}
    product = state.get('product', {})
    if isinstance(product, list): product = product[0] if product else {}

    # ビジネスルールチェック
    # Parse error for 'any(product.stock < cart_item.quantity for cart_item in cart.items)': Expected RPAREN, got IDENT at pos 39

    # 前提条件チェック
    if not ((cart.get('status') == 'active')):
        raise BusinessError("PRECONDITION_FAILED", "既に注文済みのカート")
    if not ((cart_item_count(state, cart) > 0)):
        raise BusinessError("PRECONDITION_FAILED", "カートが空です")

    # 状態更新
    new_order = {'id': f'ORDER-{len(state.get("order", [])) + 1:03d}', **input_data}
    new_order['status'] = 'confirmed'
    if 'order' not in state: state['order'] = []
    state['order'].append(new_order)
    # Parse error for 'decrease product.stock by cart_item.quantity': Unexpected token after expression: product at pos 9
    cart['status'] = 'ordered'

    return {'success': True}


def cancel_order(state: dict, input_data: dict) -> dict:
    """注文をキャンセル"""

    cart = state.get('cart', {})
    if isinstance(cart, list): cart = cart[0] if cart else {}
    cart_item = state.get('cart_item', {})
    if isinstance(cart_item, list): cart_item = cart_item[0] if cart_item else {}
    order = state.get('order', {})
    if isinstance(order, list): order = order[0] if order else {}
    order_item = state.get('order_item', {})
    if isinstance(order_item, list): order_item = order_item[0] if order_item else {}
    product = state.get('product', {})
    if isinstance(product, list): product = product[0] if product else {}

    # ビジネスルールチェック
    if (order.get('status') == 'shipped'):
        raise BusinessError("ALREADY_SHIPPED", "発送済みの注文はキャンセルできません")

    # 前提条件チェック
    if not ((order.get('status') == 'confirmed')):
        raise BusinessError("PRECONDITION_FAILED", "確定済み注文のみキャンセル可能")

    # 状態更新
    order['status'] = 'cancelled'
    # Parse error for 'increase product.stock by order_item.quantity': Unexpected token after expression: product at pos 9

    return {'success': True}


def ship_order(state: dict, input_data: dict) -> dict:
    """注文を発送"""

    cart = state.get('cart', {})
    if isinstance(cart, list): cart = cart[0] if cart else {}
    cart_item = state.get('cart_item', {})
    if isinstance(cart_item, list): cart_item = cart_item[0] if cart_item else {}
    order = state.get('order', {})
    if isinstance(order, list): order = order[0] if order else {}
    order_item = state.get('order_item', {})
    if isinstance(order_item, list): order_item = order_item[0] if order_item else {}
    product = state.get('product', {})
    if isinstance(product, list): product = product[0] if product else {}

    # 前提条件チェック
    if not ((order.get('status') == 'confirmed')):
        raise BusinessError("PRECONDITION_FAILED", "確定済み注文のみ発送可能")

    # 状態更新
    order['status'] = 'shipped'

    return {'success': True}


# ==================================================
# Test Functions (generated from scenarios)
# ==================================================

def test_at_001_______________():
    """在庫がある商品をカートに追加
    
    Verifies: COND-001-1
    """

    # Given: 初期状態
    state = {}
    state['product'] = {"id": "PROD-001", "name": "Tシャツ", "price": 2000, "stock": 10}
    state['cart'] = {"id": "CART-001", "user_id": "USER-001", "status": "active"}
    state['cart_item'] = []

    # When: アクション実行
    input_data = {"cart_id": "CART-001", "product_id": "PROD-001", "quantity": 2}
    result = add_to_cart(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (cart_item_count(state, state['cart']) == 2)


def test_at_002_________():
    """在庫超過でエラー
    
    Verifies: COND-001-2
    """

    # Given: 初期状態
    state = {}
    state['product'] = {"id": "PROD-001", "name": "Tシャツ", "price": 2000, "stock": 5}
    state['cart'] = {"id": "CART-001", "user_id": "USER-001", "status": "active"}
    state['cart_item'] = []

    # When: アクション実行
    input_data = {"cart_id": "CART-001", "product_id": "PROD-001", "quantity": 10}

    # Then: エラー OUT_OF_STOCK が発生すること
    try:
        result = add_to_cart(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "OUT_OF_STOCK"


def test_at_003___________():
    """注文確定で在庫が減少
    
    Verifies: COND-002-1, COND-002-2
    """

    # Given: 初期状態
    state = {}
    state['product'] = {"id": "PROD-001", "name": "Tシャツ", "price": 2000, "stock": 10}
    state['cart'] = {"id": "CART-001", "user_id": "USER-001", "status": "active"}
    state['cart_item'] = [{"id": "CI-001", "cart_id": "CART-001", "product_id": "PROD-001", "quantity": 3}]
    state['order'] = []

    # When: アクション実行
    input_data = {"cart_id": "CART-001"}
    result = place_order(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['product'].get('stock') == 7)
    assert (state['order'].get('status') == 'confirmed')


def test_at_004______________():
    """注文キャンセルで在庫が戻る
    
    Verifies: COND-003-1, COND-003-2
    """

    # Given: 初期状態
    state = {}
    state['product'] = {"id": "PROD-001", "name": "Tシャツ", "price": 2000, "stock": 7}
    state['order'] = {"id": "ORD-001", "user_id": "USER-001", "status": "confirmed", "total_amount": 6000}
    state['order_item'] = [{"id": "OI-001", "order_id": "ORD-001", "product_id": "PROD-001", "quantity": 3, "unit_price": 2000}]

    # When: アクション実行
    input_data = {"order_id": "ORD-001"}
    result = cancel_order(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['product'].get('stock') == 10)
    assert (state['order'].get('status') == 'cancelled')


def test_at_005_______________():
    """発送済み注文はキャンセル不可
    
    Verifies: COND-003-3
    """

    # Given: 初期状態
    state = {}
    state['product'] = {"id": "PROD-001", "name": "Tシャツ", "price": 2000, "stock": 7}
    state['order'] = {"id": "ORD-001", "user_id": "USER-001", "status": "shipped", "total_amount": 6000}
    state['order_item'] = [{"id": "OI-001", "order_id": "ORD-001", "product_id": "PROD-001", "quantity": 3, "unit_price": 2000}]

    # When: アクション実行
    input_data = {"order_id": "ORD-001"}

    # Then: エラー ALREADY_SHIPPED が発生すること
    try:
        result = cancel_order(state, input_data)
        assert False, 'Expected error was not raised'
    except BusinessError as e:
        assert e.code == "ALREADY_SHIPPED"


def test_at_006______():
    """注文を発送
    
    Verifies: COND-004-1
    """

    # Given: 初期状態
    state = {}
    state['order'] = {"id": "ORD-001", "user_id": "USER-001", "status": "confirmed", "total_amount": 6000}
    state['order_item'] = []

    # When: アクション実行
    input_data = {"order_id": "ORD-001"}
    result = ship_order(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (state['order'].get('status') == 'shipped')


def test_at_007__________():
    """注文合計金額の計算
    
    Verifies: COND-005-1
    """

    # Given: 初期状態
    state = {}
    state['order'] = {"id": "ORD-001", "user_id": "USER-001", "status": "confirmed", "total_amount": 0}
    state['order_item'] = [{"id": "OI-001", "order_id": "ORD-001", "product_id": "PROD-001", "quantity": 2, "unit_price": 2000}, {"id": "OI-002", "order_id": "ORD-001", "product_id": "PROD-002", "quantity": 1, "unit_price": 5000}]

    # When: アクション実行
    input_data = {"cart_id": "CART-001"}
    result = place_order(state, input_data)

    # Then: 期待結果
    assert result['success'] is True
    assert (order_total(state, state['order']) == 9000)



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
