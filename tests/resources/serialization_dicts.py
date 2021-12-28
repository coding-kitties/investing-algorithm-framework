order_serialization_dict = {
    'id',
    'order_reference',
    'initial_price',
    'identifier',
    'position_id',
    'amount',
    'amount_trading_symbol',
    'trading_symbol',
    'executed_at',
    'status',
    'target_symbol',
    'order_type',
    'order_side'
}

position_serialization_dict = {
    'symbol', 'amount', 'id', 'orders', 'identifier'
}

portfolio_serialization_dict = {
    'trading_symbol',
    'updated_at',
    'allocated',
    'realized',
    'unallocated_percentage',
    'created_at',
    'delta',
    'unallocated',
    'id',
    'identifier',
    'allocated_percentage',
    'market',
    'positions',
    'orders',
    "performance"
}
