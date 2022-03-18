from datetime import datetime

from sqlalchemy.orm import relationship

from investing_algorithm_framework.core.models import db
from investing_algorithm_framework.core.models.model_extension import \
    SQLAlchemyModelExtension


class AssetPrice:

    def __init__(self, symbol, price, datetime):
        self.symbol = symbol
        self.price = price
        self.datetime = datetime

    def get_symbol(self):
        return self.symbol

    def get_price(self):

        if self.price is None:
            return 0

        return self.price

    def get_datetime(self):

        if self.datetime is None:
            return datetime.utcnow()

        return self.datetime

    def repr(self, **fields) -> str:
        """
        Helper for __repr__
        """

        field_strings = []
        at_least_one_attached_attribute = False

        for key, field in fields.items():
            field_strings.append(f'{key}={field!r}')
            at_least_one_attached_attribute = True

        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"

        return f"<{self.__class__.__name__} {id(self)}>"

    def __repr__(self):
        return self.repr(
            symbol=self.get_symbol(),
            price=self.price,
            datetime=self.datetime
        )


class SQLLiteAssetPrice(AssetPrice, db.Model, SQLAlchemyModelExtension):

    __tablename__ = "asset_prices"

    id = db.Column(db.Integer, primary_key=True)
    target_symbol = db.Column(db.String, nullable=False)
    trading_symbol = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)

    # Relationships
    asset_price_history_id = db.Column(
        db.Integer, db.ForeignKey('asset_price_histories.id')
    )
    asset_price_history = relationship(
        "SQLLiteAssetPriceHistory", back_populates="prices"
    )

    def get_target_symbol(self):
        return self.target_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_price(self):
        return self.price

    def get_datetime(self):
        return self.datetime

    def __repr__(self):
        return self.repr(
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            price=self.price,
            datetime=self.datetime
        )
