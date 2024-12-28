class BaseModel:

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

    def update(self, data):

        for attr, value in data.items():

            if value is not None:
                setattr(self, attr, value)

    @staticmethod
    def from_dict(data):
        instance = BaseModel()
        instance.update(data)
        return instance
