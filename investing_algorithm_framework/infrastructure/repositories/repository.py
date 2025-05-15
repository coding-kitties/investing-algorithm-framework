import logging
from abc import ABC, abstractmethod
from typing import Callable

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import MultiDict

from investing_algorithm_framework.domain import OperationalException, \
    DEFAULT_PAGE_VALUE, DEFAULT_PER_PAGE_VALUE
from investing_algorithm_framework.infrastructure.database import Session

logger = logging.getLogger("investing_algorithm_framework")


class Repository(ABC):
    base_class: Callable
    DEFAULT_NOT_FOUND_MESSAGE = "The requested resource was not found"
    DEFAULT_PER_PAGE = DEFAULT_PER_PAGE_VALUE
    DEFAULT_PAGE = DEFAULT_PAGE_VALUE

    def create(self, data, save=True):
        created_object = self.base_class(**data)

        if save:
            with Session() as db:
                try:
                    db.add(created_object)
                    db.commit()
                    return self.get(created_object.id)
                except SQLAlchemyError as e:
                    logger.error(e)
                    db.rollback()
                    raise OperationalException("Error creating object")

        return created_object

    def update(self, object_id, data):

        with Session() as db:
            try:
                update_object = self.get(object_id)
                update_object.update(data)
                db.add(update_object)
                db.commit()
                return self.get(object_id)
            except SQLAlchemyError as e:
                logger.error(e)
                db.rollback()
                raise OperationalException("Error updating object")

    def update_all(self, query_params, data):

        with Session() as db:
            try:
                selection = self.get_all(query_params)

                for item in selection:
                    try:
                        item.update(db, data)
                    except SQLAlchemyError as e:
                        logger.error(e)
                        db.rollback()

                db.commit()

            except SQLAlchemyError as e:
                logger.error(e)
                db.rollback()
                raise OperationalException("Error updating object")

    def delete(self, object_id):

        with Session() as db:
            try:
                delete_object = self.get(object_id)
                db.delete(delete_object)
                db.commit()
                return delete_object
            except SQLAlchemyError as e:
                logger.error(e)
                db.rollback()
                raise OperationalException("Error deleting object")

    def delete_all(self, query_params):

        with Session() as db:
            if query_params is None:
                raise OperationalException("No parameters are required")

            try:
                query_set = db.query(self.base_class)
                query_set = self.apply_query_params(
                    db, query_set, query_params
                )

                for item in query_set.all():
                    item.delete(db)
                    db.commit()

            except SQLAlchemyError as e:
                logger.error(e)
                db.rollback()
                raise OperationalException("Error deleting all objects")

    def get_all(self, query_params=None):
        query_params = MultiDict(query_params)

        with Session() as db:
            try:
                query_set = db.query(self.base_class)
                query_set = self.apply_query_params(
                    db, query_set, query_params
                )
                return query_set.all()
            except SQLAlchemyError as e:
                logger.error(e)
                raise OperationalException("Error getting all objects")

    def get(self, object_id):

        with Session() as db:
            match = db.query(self.base_class).filter_by(id=object_id) \
                .first()

            if not match:
                raise OperationalException(
                    self.DEFAULT_NOT_FOUND_MESSAGE
                )

            return match

    @abstractmethod
    def _apply_query_params(self, db, query, query_params):
        raise NotImplementedError()

    def apply_query_params(self, db, query, query_params):

        if query_params is not None:
            query_params = MultiDict(query_params)
            query = self._apply_query_params(db, query, query_params)

        return query

    def exists(self, query_params):
        with Session() as db:
            try:
                query = db.query(self.base_class)
                query = self.apply_query_params(db, query, query_params)
                return query.first() is not None
            except SQLAlchemyError as e:
                logger.error(e)
                raise OperationalException("Error checking if object exists")

    def find(self, query_params):

        if query_params is None or len(query_params) == 0:
            raise OperationalException("Find requires query parameters")

        with Session() as db:
            try:
                query = db.query(self.base_class)
                query = self.apply_query_params(db, query, query_params)
                result = query.first()

                if result is None:
                    raise OperationalException(self.DEFAULT_NOT_FOUND_MESSAGE)

                return result
            except SQLAlchemyError as e:
                logger.error(e)
                raise OperationalException(self.DEFAULT_NOT_FOUND_MESSAGE)

    def count(self, query_params=None):

        with Session() as db:
            try:
                query = db.query(self.base_class)
                query = self.apply_query_params(db, query, query_params)
                return query.count()
            except SQLAlchemyError as e:
                logger.error(e)
                raise OperationalException("Error counting objects")

    def normalize_query_param(self, value):
        """
        Given a non-flattened query parameter value,
        and if the value is a list only containing 1 item,
        then the value is flattened.

        :param value: a value from a query parameter
        :return: a normalized query parameter value
        """
        return value if len(value) > 1 else value[0]

    def is_query_param_present(self, key, params, throw_exception=False):
        query_params = self.normalize_query(params)

        if key not in query_params:

            if not throw_exception:
                return False

            raise OperationalException(f"{key} is not specified")
        else:
            return True

    def normalize_query(self, params):
        """
        Converts query parameters from only containing one value for
        each parameter, to include parameters with multiple values as lists.

        :param params: a flask query parameters data structure
        :return: a dict of normalized query parameters
        """
        if isinstance(params, MultiDict):
            params = params.to_dict(flat=False)

        return {k: self.normalize_query_param(v) for k, v in params.items()}

    def get_query_param(self, key, params, default=None, many=False):
        boolean_array = ["true", "false"]

        if params is None or key not in params:
            return default

        params = self.normalize_query(params)
        selection = params.get(key, default)

        if not isinstance(selection, list):

            if selection is None:
                selection = []
            else:
                selection = [selection]

        new_selection = []

        for index, selected in enumerate(selection):

            if isinstance(selected, str) and selected.lower() in boolean_array:
                new_selection.append(selected.lower() == "true")
            else:
                new_selection.append(selected)

        if not many:

            if len(new_selection) == 0:
                return None

            return new_selection[0]

        return new_selection

    def save(self, object_to_save):
        """
        Save an object to the database with SQLAlchemy.

        Args:
            object_to_save: instance of the object to save.

        Returns:
            Object: The saved object.
        """
        with Session() as db:
            try:
                db.add(object_to_save)
                db.commit()
                return self.get(object_to_save.id)
            except SQLAlchemyError as e:
                logger.error(e)
                db.rollback()
                raise OperationalException("Error saving object")

    def save_objects(self, objects):

        with Session() as db:
            try:
                for object in objects:
                    db.add(object)
                db.commit()
                return objects
            except SQLAlchemyError as e:
                logger.error(e)
                db.rollback()
                raise OperationalException("Error saving objects")
