from abc import abstractmethod


class Position:

    @abstractmethod
    def get_symbol(self):
        pass

    @abstractmethod
    def get_orders(self):
        pass

    @abstractmethod
    def get_amount(self):
        pass

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

    def to_string(self):
        return self.repr(
            symbol=self.get_symbol(),
            amount=self.get_amount()
        )

    def __repr__(self):
        return self.to_string()