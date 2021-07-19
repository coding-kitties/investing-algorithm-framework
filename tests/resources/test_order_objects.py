from investing_algorithm_framework import db
from investing_algorithm_framework.core.portfolio_managers import \
    PortfolioManager


class TestOrderAndPositionsObjectsMixin:
    TICKERS = [
        'BTC',
        'ETH',
        'BNB',
        'ADA',
        'XRP',
    ]

    def create_test_objects(self, portfolio_manager: PortfolioManager):
        # Create buy orders
        for ticker in self.TICKERS:
            order = portfolio_manager.create_buy_order(
                symbol=ticker,
                amount=4,
                price=9
            )
            order.save(db)
            portfolio_manager.add_buy_order(order)

            order = portfolio_manager.create_buy_order(
                symbol=ticker,
                amount=5,
                price=9.76
            )
            order.save(db)
            portfolio_manager.add_buy_order(order)

        # Create sell orders
        for ticker in self.TICKERS:
            order = portfolio_manager.create_sell_order(
                symbol=ticker,
                amount=2,
                price=10
            )

            order.save(db)
            portfolio_manager.add_sell_order(order)

            order = portfolio_manager.create_sell_order(
                symbol=ticker,
                amount=3,
                price=11
            )

            order.save(db)
            portfolio_manager.add_sell_order(order)

        db.session.commit()

    @staticmethod
    def create_buy_orders(amount, tickers, portfolio_manager):

        for ticker in tickers:
            order = portfolio_manager.create_buy_order(
                amount=amount,
                symbol=ticker,
                price=5
            )
            order.save(db)
            portfolio_manager.add_buy_order(order)

        db.session.commit()

    @staticmethod
    def create_sell_orders(amount, tickers, portfolio_manager):

        for ticker in tickers:
            order = portfolio_manager.create_sell_order(
                amount=amount,
                symbol=ticker,
                price=5
            )
            order.save(db)
            portfolio_manager.add_sell_order(order)

        db.session.commit()
