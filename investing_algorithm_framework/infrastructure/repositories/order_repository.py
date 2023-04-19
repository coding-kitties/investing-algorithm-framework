from .repository import Repository
from investing_algorithm_framework.infrastructure.models import SQLOrder, \
    SQLPosition, SQLPortfolio


class SQLOrderRepository(Repository):
    base_class = SQLOrder

    def _apply_query_params(self, db, query, query_params):
        external_id_query_param = self.get_query_param(
            "external_id", query_params
        )
        portfolio_query_param = self.get_query_param("portfolio_id", query_params)
        side_query_param = query_params.get("side")
        type_query_param = query_params.get("type")
        status_query_param = query_params.get("status")
        price_query_param = query_params.get("price")
        amount_query_param = query_params.get("amount")
        position_query_param = self.get_query_param(
            "position", query_params, many=True
        )
        target_symbol_query_param = query_params.get("symbol")
        trading_symbol_query_param = query_params.get("trading_symbol")

        if portfolio_query_param:
            portfolio = db.query(SQLPortfolio).filter_by(
                identifier=portfolio_query_param
            ).first()

            if portfolio is None:
                return query.filter_by(id=-1)
            
            positions = db.query(SQLPosition).filter_by(
                portfolio_id=portfolio.id
            ).all()
            position_ids = [p.id for p in positions]
            query = query.filter(SQLOrder.position_id.in_(position_ids))
        if external_id_query_param:
            query = query.filter_by(external_id=external_id_query_param)

        if side_query_param:
            query = query.filter(SQLOrder.side == side_query_param)

        if type_query_param:
            query = query.filter(SQLOrder.type == type_query_param)

        if status_query_param:
            query = query.filter(SQLOrder.status == status_query_param)

        if price_query_param:
            query = query.filter(SQLOrder.price == price_query_param)

        if amount_query_param:
            query = query.filter(SQLOrder.amount == amount_query_param)

        if position_query_param:
            query = query.filter(SQLOrder.position_id.in_(position_query_param))

        if target_symbol_query_param:
            query = query.filter(
                SQLOrder.target_symbol == target_symbol_query_param
            )

        if trading_symbol_query_param:
            query = query.filter(
                SQLOrder.trading_symbol == trading_symbol_query_param
            )

        query = query.order_by(SQLOrder.created_at.desc())
        return query
