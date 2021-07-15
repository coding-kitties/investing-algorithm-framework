import os
from investing_algorithm_framework import TimeUnit
from investing_algorithm_framework.app import App
from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.configuration.settings import DevConfig
from investing_algorithm_framework import Order

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = App(resources_directory=BASE_DIR, config=DevConfig)


@app.algorithm.schedule(time_unit=TimeUnit.SECONDS, interval=20)
def analyze(algorithm: AlgorithmContext):
    print("analyze function")
    print(Order.query.all())


@app.algorithm.schedule(worker_id="one", time_unit=TimeUnit.SECONDS, interval=10)
def moving_average_btc_usdt_analyzer(algorithm: AlgorithmContext):
    print("moving_average_btc_usdt_analyzer function")


if __name__ == "__main__":
    app.start()


# class Calculation:
#
#     @abstractmethod
#     def calculate(self):
#         raise NotImplementedError()
#
# class ComplexCalculation(Calculation):
#
#     @abstractmethod
#     def calculate_a(self):
#         raise NotImplementedError()
#
#     @abstractmethod
#     def calculate_b(self):
#         raise NotImplementedError()
#
#     def calculate(self):
#         self.calculate_a()
#         self.calculate_b()
#
#
# class UseCaseAComplexCalculation(ComplexCalculation):
#
#     def calculate_a(self):
#         return 120
#
#     def calculate_b(self):
#         return 10
#
#
# class UseCaseBComplexCalculation(ComplexCalculation):
#
#     def calculate_a(self):
#         return 1204242
#
#     def calculate_b(self):
#         return 10424224
#
#
# class StrategyA:
#
#     def calculate(self):
#         return 200593
#
#
# class StrategyB:
#
#     def calculate(self):
#         return 100420
#
#
# class StrategyCalculation(Calculation):
#     strategy = None
#
#     def calculate(self):
#         return self.strategy.calculate()
#
#
#
#
#
# class OrderExecutor:
#
#     executor = None
#
#     def execute(self):
#         return self.executor.execute()
#
#     def process_return(self):
#         return self.executor.process_return()
#
#
# class Eend(ABC):
#
#     @abstractmethod
#     def kwak(self):
#         raise NotImplementedError()
#
#
# class Meerkoet(Eend):
#
#     def kwak(self):
#         print("geoaogejpjgejgejpo")
#
#
# class NepEend:
#
#     def kwak(self):
#         print("kwakagkakegkekg")
#
#
# def laat_eend_kwakken(eend):
#     eend.kwak()
#
#
# if __name__ == "__main__":
#     meerkoet = Meerkoet()
#     nep_eend = NepEend()
#
#     laat_eend_kwakken(meerkoet)
#     laat_eend_kwakken(nep_eend)
#
# # class OrderExecutorStrategy(ABC):
# #
# #     @abstractmethod
# #     def execute(self):
# #         raise NotImplementedError()
# #
# #     @abstractmethod
# #     def process_return(self):
# #         raise NotImplementedError()
# #
# #
# # class BinanceOrderExecutor():
# #
# #     def execute(self):
# #         print("Binance execution")
# #
# #     def process_return(self):
# #         print("Binance processing")
# #
# #
# # class KrakenOrderExecutor:
# #
# #     def execute(self):
# #         print("Binance execution")
# #
# #     def process_return(self):
# #         print("Binance processing")
# #
# #
# # if __name__ == "__main__":
# #     executor = OrderExecutor()
# #     executor.executor = BinanceOrderExecutor()
# #     executor.execute()
#
