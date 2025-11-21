from common.repositories.factory import RepositoryFactory, RepoType
from common.models.task import Task


class TaskService:

    def __init__(self, config):
        self.config = config
        self.repository_factory = RepositoryFactory(config)
        self.task_repo = self.repository_factory.get_repository(RepoType.TASK)

    def save_task(self, task: Task):
        task = self.task_repo.save(task)
        return task

    def get_task_by_id(self, entity_id: str):
        task = self.task_repo.get_one({"entity_id": entity_id})
        return task

    def get_tasks_by_person_id(self, person_id: str):
        tasks = self.task_repo.get_tasks_by_person_id_ordered(person_id)
        return tasks

    def delete_task(self, task: Task):
        task.active = False
        task = self.task_repo.save(task)
        return task

