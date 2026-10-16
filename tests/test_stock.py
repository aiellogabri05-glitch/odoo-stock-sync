from app.stock import StockLevel, find_low_stock, is_low_stock


def level(on_hand: float, reorder_point: int = 10, sku: str = "SKU") -> StockLevel:
    return StockLevel(sku=sku, name="Test product", on_hand=on_hand, reorder_point=reorder_point)


def test_below_reorder_point_is_low():
    assert is_low_stock(level(on_hand=9, reorder_point=10))


def test_exactly_at_reorder_point_is_low():
    assert is_low_stock(level(on_hand=10, reorder_point=10))


def test_above_reorder_point_is_not_low():
    assert not is_low_stock(level(on_hand=11, reorder_point=10))


def test_zero_stock_is_low_even_with_zero_threshold():
    assert is_low_stock(level(on_hand=0, reorder_point=0))


def test_negative_on_hand_from_odoo_is_low():
    # Odoo can show negative quantities when deliveries are booked before receipts.
    assert is_low_stock(level(on_hand=-3, reorder_point=5))


def test_find_low_stock_keeps_input_order_and_filters():
    levels = [
        level(on_hand=50, reorder_point=10, sku="A"),
        level(on_hand=4, reorder_point=10, sku="B"),
        level(on_hand=10, reorder_point=10, sku="C"),
        level(on_hand=100, reorder_point=10, sku="D"),
    ]
    assert [item.sku for item in find_low_stock(levels)] == ["B", "C"]


def test_find_low_stock_empty_input():
    assert find_low_stock([]) == []
