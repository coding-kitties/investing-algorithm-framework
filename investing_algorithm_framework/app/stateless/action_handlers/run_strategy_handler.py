from investing_algorithm_framework.app.stateless.action_handlers\
    .action_handler_strategy import ActionHandlerStrategy
from investing_algorithm_framework.core.models import Portfolio
from investing_algorithm_framework.core.models.data_provider import Ticker, \
    OrderBook


class RunStrategyHandler(ActionHandlerStrategy):

    def handle_event(self, payload, algorithm_context):
        strategy_identifier = payload.get("identifier", None)
        portfolio = Portfolio.from_dict(payload.get("portfolio", None))
        ticker = Ticker.from_dict(payload.get("ticker", None))
        order_book = OrderBook.from_dict(payload.get("oder_book", None))

        strategy = algorithm_context.get_strategy(strategy_identifier)
        strategy.run(
            portfolio=portfolio,
            ticker=ticker,
            order_book=order_book,
            algorithm_context=algorithm_context
        )
