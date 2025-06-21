class RepositoryService:

    def __init__(self, repository):
        self.repository = repository

    def create(self, data):
        return self.repository.create(data)

    def get(self, object_id):
        return self.repository.get(object_id)

    def get_all(self, query_params=None):
        return self.repository.get_all(query_params)

    def update(self, object_id, data):
        return self.repository.update(object_id, data)

    def update_all(self, query_params, data):
        return self.repository.update_all(query_params, data)

    def delete(self, object_id):
        return self.repository.delete(object_id)

    def delete_all(self, query_params):
        return self.repository.delete_all(query_params)

    def find(self, query_params):
        return self.repository.find(query_params)

    def count(self, query_params=None):
        return self.repository.count(query_params)

    def exists(self, query_params):
        return self.repository.exists(query_params)

    def save(self, object):
        return self.repository.save(object)
