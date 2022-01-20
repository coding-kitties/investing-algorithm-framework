class SQLAlchemyModelExtension:

    def update(self, db, data, commit=True, **kwargs):

        for attr, value in data.items():
            setattr(self, attr, value)

        if commit:
            db.session.commit()

    def save(self, db, commit=True):
        db.session.add(self)

        if commit:
            db.session.commit()

    def delete(self, db, commit=True):
        db.session.delete(self)

        if commit:
            db.session.commit()
