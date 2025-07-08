from investing_algorithm_framework import CCXTOHLCVMarketDataSource

from .strategy_v1 import CrossOverStrategyV1



def configure_strategy(
    time_unit,
    interval,
    assets,
    time_frame,
    fast,
    slow,
    trend,
    stop_loss_percentage,
    stop_loss_sell_size,
    take_profit_percentage,
    take_profit_sell_size
):
    data_providers = []

    for asset in assets:
        data_providers.append(
            CCXTOHLCVMarketDataSource(
                identifier=f"{asset}-ohlcv-{time_frame.value}",
                market="bitvavo",
                symbol=asset,
                time_frame=time_frame,
                window_size=200
            )
        )

    strategy = CrossOverStrategyV1(
        time_unit=time_unit,
        interval=interval,
        symbol_pairs=assets,
        market_data_sources=data_providers,
        fast=fast,
        slow=slow,
        trend=trend,
        stop_loss_percentage=stop_loss_percentage,
        stop_loss_sell_size=stop_loss_sell_size,
        take_profit_percentage=take_profit_percentage,
        take_profit_sell_size=take_profit_sell_size
    )
    return strategy


__all__ = [
    "CrossOverStrategyV1",
]
