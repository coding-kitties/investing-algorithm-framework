from investing_algorithm_framework.core.exceptions import OperationalException


class Strategy:
    id = None

    def on_raw_data(self, data):
        raise OperationalException("Not implemented")

    def on_order_book(self, data):
        raise OperationalException("Not implemented")

    def on_tick(self, data):
        raise OperationalException("Not implemented")

    def on_quote(self, data):
        raise OperationalException("Not implemented")

    def get_id(self) -> str:
        assert getattr(self, 'id', None) is not None, (
            "{} should either include a id attribute, or override the "
            "`get_id()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'id')
