import os

from sqlalchemy import create_engine

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, MarketCredential, Algorithm
from investing_algorithm_framework.infrastructure.database.sql_alchemy \
    import _apply_forward_only_migrations
from tests.resources import TestBase


class Test(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="USDT"
        )
    ]
    external_balances = {
        "USDT": 1000
    }
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="",
            secret_key=""
        )
    ]

    # def setUp(self) -> None:
    #     self.resource_dir = os.path.abspath(
    #         os.path.join(
    #             os.path.join(
    #                 os.path.join(
    #                     os.path.join(
    #                         os.path.realpath(__file__),
    #                         os.pardir
    #                     ),
    #                     os.pardir
    #                 ),
    #                 os.pardir
    #             ),
    #             "resources"
    #         )
    #     )
    #     self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
    #     self.app.add_portfolio_configuration(
    #         PortfolioConfiguration(
    #             market="BITVAVO",
    #             trading_symbol="USDT"
    #         )
    #     )
    #     self.app.container.market_service.override(
    #         MarketServiceStub(self.app.container.market_credential_service())
    #     )
    #     algorithm = Algorithm()
    #     self.app.add_algorithm(algorithm)
    #     self.app.add_market_credential(
    #         MarketCredential(
    #             market="BITVAVO",
    #             api_key="api_key",
    #             secret_key="secret_key"
    #         )
    #     )
    #     self.app.initialize()

    # def tearDown(self):
    #     return super().tearDown()

    def test_store_position_amount(self):
        self.portfolio_service = self.app.container.portfolio_service()
        portfolio = self.portfolio_service.find({"market": "BITVAVO"})
        self.position_repository = self.app.container.position_repository()
        self.position_repository.create(
            {
                "symbol": "ADA",
                "amount": 2004.5303357979318,
                "portfolio_id": portfolio.id,
            }
        )
        position = self.position_repository.find(
            {"symbol": "ADA", "portfolio": portfolio.id}
        )
        self.assertEqual(position.amount, 2004.5303357979318)
        self.assertEqual(position.get_amount(), 2004.5303357979318)

    def test_position_update(self):
        self.portfolio_service = self.app.container.portfolio_service()
        portfolio = self.portfolio_service.find({"market": "BITVAVO"})
        self.position_repository = self.app.container.position_repository()
        self.position_repository.create(
            {
                "symbol": "ADA",
                "amount": 2004.5303357979318,
                "portfolio_id": portfolio.id,
            }
        )
        position = self.position_repository.find(
            {"symbol": "ADA", "portfolio": portfolio.id}
        )
        self.assertEqual(position.amount, 2004.5303357979318)
        self.assertEqual(position.get_amount(), 2004.5303357979318)
        position = self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() + 1000.0
            }
        )
        self.assertEqual(position.amount, 3004.5303357979318)
        self.assertEqual(position.get_amount(), 3004.5303357979318)

    def test_position_legs_round_trip(self):
        portfolio = self.app.container.portfolio_service().find({
            "market": "BITVAVO"
        })
        repository = self.app.container.position_repository()
        repository.create({
            "symbol": "ETH",
            "portfolio_id": portfolio.id,
            "long_amount": 5,
            "short_amount": 3,
            "long_cost": 500,
            "short_cost": 330,
        })

        position = repository.find({
            "symbol": "ETH", "portfolio": portfolio.id
        })

        self.assertEqual(2, position.amount)
        self.assertEqual(8, position.gross_amount)
        self.assertEqual(170, position.net_cost)
        self.assertEqual(830, position.gross_cost)

    def test_migration_backfills_legacy_long_and_short_rows(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE positions ("
                "id INTEGER PRIMARY KEY, amount VARCHAR, cost VARCHAR)"
            )
            connection.exec_driver_sql(
                "INSERT INTO positions (amount, cost) VALUES "
                "('2.5', '250.25'), ('-3.5', '420.75')"
            )
            connection.exec_driver_sql(
                "CREATE TABLE position_snapshots ("
                "id INTEGER PRIMARY KEY, amount VARCHAR, cost VARCHAR)"
            )
            connection.exec_driver_sql(
                "INSERT INTO position_snapshots (amount, cost) "
                "VALUES ('-1.25', '125.5')"
            )

        _apply_forward_only_migrations(engine)

        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT amount, cost, long_amount, short_amount, "
                "long_cost, short_cost FROM positions ORDER BY id"
            ).all()

        self.assertEqual(
            ('2.5', '250.25', '2.5', '0', '250.25', '0'), rows[0]
        )
        self.assertEqual(
            ('-3.5', '420.75', '0', '3.5', '0', '420.75'), rows[1]
        )
        with engine.connect() as connection:
            snapshot = connection.exec_driver_sql(
                "SELECT long_amount, short_amount, long_cost, short_cost "
                "FROM position_snapshots"
            ).one()
        self.assertEqual(('0', '1.25', '0', '125.5'), snapshot)
