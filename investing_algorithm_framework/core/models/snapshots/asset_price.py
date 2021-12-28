from sqlalchemy.orm import relationship

from investing_algorithm_framework.core.models.model_extension import \
    ModelExtension
from investing_algorithm_framework.core.models import db


class AssetPrice(db.Model, ModelExtension):
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
        "AssetPriceHistory", back_populates="prices"
    )

    def __init__(self, target_symbol, trading_symbol, price, datetime):
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.price = price
        self.datetime = datetime

    def __repr__(self):
        return self.repr(
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            price=self.price,
            datetime=self.datetime
        )
