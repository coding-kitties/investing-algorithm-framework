from datetime import datetime as dt, timedelta as td
from investing_algorithm_framework.core.models import db, TimeFrame, \
    TimeInterval
from investing_algorithm_framework.core.models.model_extension \
    import ModelExtension


class AssetPriceHistory(db.Model, ModelExtension):
    __tablename__ = "asset_price_histories"

    id = db.Column(db.Integer, primary_key=True)
    target_symbol = db.Column(db.String, nullable=False)
    trading_symbol = db.Column(db.String, nullable=False)
    market = db.Column(db.String, nullable=False)
    time_frame = db.Column(db.String, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)

    # Relationships
    prices = db.relationship(
        "AssetPrice",
        back_populates="asset_price_history",
        lazy="dynamic",
        cascade="all,delete",
    )

    def __init__(self, market, target_symbol, trading_symbol, time_frame):
        self.market = market
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.time_frame = TimeFrame.from_value(time_frame).value

    @staticmethod
    def of(market: str, target_symbol: str, trading_symbol: str, time_frame):
        asset_price_history = AssetPriceHistory.query.filter_by(
            market=market,
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            time_frame=TimeFrame.from_value(time_frame).value
        ).first()

        if not asset_price_history:
            asset_price_history = AssetPriceHistory(
                market=market,
                target_symbol=target_symbol,
                trading_symbol=trading_symbol,
                time_frame=TimeFrame.from_value(time_frame).value
            )
            asset_price_history.get_prices()
            asset_price_history.save(db)

        return asset_price_history

    def get_prices(self):
        time_frame = TimeFrame.from_value(self.time_frame)

        # Get the latest price point
        if TimeInterval.CURRENT.equals(time_frame.time_interval):
            prices = self._get_prices_current()

        # Get the latest minute prices
        elif TimeInterval.MINUTES_ONE.equals(time_frame.time_interval):
            prices = self._get_prices_one_minute()

        # Get the latest 15 minute prices
        elif TimeInterval.MINUTES_FIFTEEN.equals(time_frame.time_interval):
            prices = self._get_prices_fifteen_minutes()

        # Get the latest hourly prices
        elif TimeInterval.HOURS_ONE.equals(time_frame.time_interval):
            prices = self._get_prices_one_hour()

        # Get the latest four hour prices
        elif TimeInterval.HOURS_FOUR.equals(time_frame.time_interval):
            prices = self._get_prices_four_hour()

        # Get the latest daily prices
        elif TimeInterval.DAYS_ONE.equals(time_frame.time_interval):
            prices = self._get_prices_one_day()

        return prices.all()

    def _get_prices_current(self):
        from investing_algorithm_framework import current_app as app

        if self.updated_at is None \
                or self.updated_at < dt.utcnow() - td(seconds=5) \
                or not self.prices:
            self.remove_prices()

            market_service = app.algorithm.get_market_service(self.market)

            asset_prices = market_service.get_price(
                self.target_symbol,
                self.trading_symbol,
            )

            self.updated_at = dt.utcnow()
            self.prices = asset_prices
        return self.prices

    def _get_prices_one_minute(self):
        from investing_algorithm_framework import current_app as app
        market_service = app.algorithm.get_market_service(self.market)

        if self.updated_at is None\
                or self.updated_at < dt.utcnow() - td(minutes=1) \
                or not self.prices:
            self.remove_prices()

            asset_prices = market_service.get_prices(
                self.target_symbol,
                self.trading_symbol,
                TimeInterval.MINUTES_ONE,
            )

            self.updated_at = dt.utcnow()
            self.prices = asset_prices
        return self.prices

    def _get_prices_fifteen_minutes(self):
        from investing_algorithm_framework import current_app as app
        market_service = app.algorithm.get_market_service(self.market)

        if self.updated_at is None \
                or self.updated_at < dt.utcnow() - td(minutes=15) \
                or not self.prices:
            self.remove_prices()

            asset_prices = market_service.get_prices(
                self.target_symbol,
                self.trading_symbol,
                TimeInterval.MINUTES_FIFTEEN,
            )

            self.updated_at = dt.utcnow()
            self.prices = asset_prices
        return self.prices

    def _get_prices_one_hour(self):
        from investing_algorithm_framework import current_app as app
        market_service = app.algorithm.get_market_service(self.market)

        if self.updated_at is None \
                or self.updated_at < dt.utcnow() - td(hours=1) \
                or not self.prices:
            self.remove_prices()

            asset_prices = market_service.get_prices(
                self.target_symbol,
                self.trading_symbol,
                TimeInterval.HOURS_ONE,
            )
            self.updated_at = dt.utcnow()
            self.prices = asset_prices
        return self.prices

    def _get_prices_four_hour(self):
        from investing_algorithm_framework import current_app as app
        market_service = app.algorithm.get_market_service(self.market)

        if self.updated_at is None \
                or self.updated_at < dt.utcnow() - td(hours=4) \
                or not self.prices:
            self.remove_prices()

            asset_prices = market_service.get_prices(
                self.target_symbol,
                self.trading_symbol,
                TimeInterval.HOURS_FOUR
            )
            self.updated_at = dt.utcnow()
            self.prices = asset_prices
        return self.prices

    def _get_prices_one_day(self):
        from investing_algorithm_framework import current_app as app
        market_service = app.algorithm.get_market_service(self.market)

        if self.updated_at is None \
                or self.updated_at < dt.utcnow() - td(days=1) \
                or not self.prices:
            self.remove_prices()

            asset_prices = market_service.get_prices(
                self.target_symbol,
                self.trading_symbol,
                TimeInterval.DAYS_ONE
            )
            self.updated_at = dt.utcnow()
            self.prices = asset_prices

        return self.prices

    def _get_prices_one_week(self):
        from investing_algorithm_framework import current_app as app
        market_service = app.algorithm.get_market_service(self.market)

        if self.updated_at is None \
                or self.updated_at < dt.utcnow() - td(weeks=1) \
                or not self.prices:
            self.remove_prices()

            asset_prices = market_service.get_prices(
                self.target_symbol,
                self.trading_symbol,
                TimeInterval.WEEKS_ONE,
            )
            self.updated_at = dt.utcnow()
            self.prices = asset_prices

        return self.prices

    def remove_prices(self):
        from investing_algorithm_framework.core.models.snapshots import \
            AssetPrice

        db.session.query(AssetPrice).filter(
            AssetPrice.asset_price_history_id == self.id
        ).delete()
