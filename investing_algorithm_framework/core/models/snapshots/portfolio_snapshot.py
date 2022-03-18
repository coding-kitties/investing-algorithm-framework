# from abc import abstractmethod
# from datetime import datetime
#
# from sqlalchemy import UniqueConstraint
#
# from investing_algorithm_framework.core.models import db
# from investing_algorithm_framework.core.models.model_extension import \
#     SQLAlchemyModelExtension
#
#
# class PortfolioSnapshot:
#
#     @abstractmethod
#     def get_portfolio_id(self):
#         pass
#
#     @abstractmethod
#     def get_market(self):
#         pass
#
#     @abstractmethod
#     def get_realized(self):
#         pass
#
#     @abstractmethod
#     def get_pending_value(self):
#         pass
#
#     @abstractmethod
#     def get_unallocated(self):
#         pass
#
#     @abstractmethod
#     def get_allocated(self, asset_prices=None):
#         pass
#
#     @abstractmethod
#     def get_total_revenue(self):
#         pass
#
#     @abstractmethod
#     def get_created_at(self):
#         pass
#
#     @abstractmethod
#     def get_withdrawel(self):
#         pass
#
#     @abstractmethod
#     def get_deposit(self):
#         pass
#
#     @abstractmethod
#     def set_inner_snapshot(self, flas):
#         pass
#
#     @abstractmethod
#     def is_inner_snapshot(self):
#         pass
#
#     @abstractmethod
#     def get_positions(self):
#         pass
#
#     @staticmethod
#     @abstractmethod
#     def from_portfolio(portfolio, creation_datetime=None, withdrawel=0, deposit=0):
#         pass
#
#     def get_total_value(self, asset_prices):
#         if self.is_inner_snapshot():
#             return self.get_pending_value() + self.get_unallocated() + self.get_allocated()
#
#         total_value = 0
#
#         total_value += self.get_allocated(asset_prices)
#         total_value += self.get_pending_value()
#         total_value += self.get_unallocated()
#         return total_value
#
#     @property
#     def cashflow(self):
#
#         if self.get_deposit() != 0:
#             return self.get_deposit()
#
#         if self.get_withdrawel() != 0:
#             return -self.get_withdrawel()
#
#         return 0
#
#     def repr(self, **fields) -> str:
#         """
#         Helper for __repr__
#         """
#
#         field_strings = []
#         at_least_one_attached_attribute = False
#
#         for key, field in fields.items():
#             field_strings.append(f'{key}={field!r}')
#             at_least_one_attached_attribute = True
#
#         if at_least_one_attached_attribute:
#             return f"<{self.__class__.__name__}({','.join(field_strings)})>"
#
#         return f"<{self.__class__.__name__} {id(self)}>"
#
#     def __repr__(self):
#         return self.repr(
#             portfolio_id=self.get_portfolio_id(),
#             created_at=self.get_created_at(),
#             market=self.get_market(),
#         )
#
#
# class SQLLitePortfolioSnapshot(
#     PortfolioSnapshot, db.Model, SQLAlchemyModelExtension
# ):
#
#     __tablename__ = "portfolio_snapshots"
#
#     id = db.Column(db.Integer, primary_key=True)
#     portfolio_id = db.Column(db.Integer, nullable=False)
#     market = db.Column(db.String, nullable=False)
#     trading_symbol = db.Column(db.String, nullable=True)
#     realized = db.Column(db.Float, default=0)
#     allocated = db.Column(db.Float, default=0)
#     unallocated = db.Column(db.Float, default=0)
#     total_revenue = db.Column(db.Float, default=0)
#     total_value = db.Column(db.Float, default=0)
#     created_at = db.Column(db.DateTime, default=0)
#     pending_value = db.Column(db.Float, default=0)
#
#     # Cash flow attributes
#     withdrawel = db.Column(db.Float, default=0)
#     deposit = db.Column(db.Float, default=0)
#     _inner_snapshot = db.Column(db.Boolean, default=False)
#
#     # Relationships
#     positions = db.relationship(
#         "SQLLitePositionSnapshot",
#         back_populates="portfolio",
#         lazy="dynamic",
#         cascade="all,delete",
#     )
#
#     __table_args__ = (
#         UniqueConstraint(
#             "portfolio_id",
#             "created_at",
#             name="_portfolio_snapshot_id_created_at_uc"
#         ),
#     )
#
#     @staticmethod
#     def from_portfolio(
#         portfolio, creation_datetime=None, withdrawel=0, deposit=0
#     ):
#         snapshot = SQLLitePortfolioSnapshot()
#         snapshot.portfolio_id = portfolio.get_identifier()
#
#         from investing_algorithm_framework.core.models \
#             import SQLLitePositionSnapshot
#
#         positions = portfolio.get_positions()
#
#         position_snapshots = [
#             SQLLitePositionSnapshot.from_position(position)
#             for position in positions
#         ]
#
#         snapshot.positions = position_snapshots
#         snapshot.market = portfolio.market
#         snapshot.withdrawel = withdrawel
#         snapshot.deposit = deposit
#
#         if snapshot.created_at is None:
#             snapshot.created_at = datetime.utcnow()
#
#         pending_value = 0
#
#         for position in positions:
#             pending_value += position.get_pending_value()
#
#         snapshot.pending_value = pending_value
#
#         total_value = 0
#         total_value += portfolio.get_allocated()
#         total_value += pending_value
#         total_value += snapshot.get_unallocated().get_amount()
#         snapshot.total_value = total_value
#         return snapshot
#
#     @property
#     def cash_flow(self):
#
#         if self.deposit != 0:
#             return self.deposit
#
#         if self.withdrawel != 0:
#             return -self.withdrawel
#
#         return 0
#
#     def is_inner_snapshot(self):
#         return self._inner_snapshot
#
#     def set_inner_snapshot(self, flag):
#         self._inner_snapshot = flag
#
#     def get_portfolio_id(self):
#         return self.portfolio_id
#
#     def get_market(self):
#         return self.market
#
#     def get_pending_value(self):
#         return self.pending_value
#
#     def get_unallocated(self):
#         return self.unallocated
#
#     def get_allocated(self, asset_prices=None):
#
#         if asset_prices is not None:
#             allocated = 0
#
#             for asset_price in asset_prices:
#                 position = self.positions \
#                     .filter_by(symbol=asset_price.target_symbol).first()
#
#                 if position is not None:
#                     allocated += position.amount * asset_price.price
#
#             return allocated
#
#         return self.allocated
#
#     def get_total_revenue(self):
#         return self.total_revenue
#
#     def get_created_at(self):
#         return self.created_at
#
#     def get_withdrawel(self):
#         return self.withdrawel
#
#     def get_deposit(self):
#         return self.deposit
#
#     def get_positions(self):
#         return self.positions
