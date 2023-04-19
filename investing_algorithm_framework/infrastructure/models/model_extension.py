class SQLAlchemyModelExtension:

    def update(self, data):

        for attr, value in data.items():
            setattr(self, attr, value)
