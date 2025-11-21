from common.repositories.base import BaseRepository
from common.models.task import Task


class TaskRepository(BaseRepository):
    MODEL = Task

    def get_tasks_by_person_id_ordered(self, person_id: str):
        query = """
            SELECT *
            FROM task
            WHERE person_id = %s AND active = true
            ORDER BY changed_on DESC;
        """
        params = (person_id,)

        with self.adapter:
            results = self.adapter.execute_query(query, params)
            tasks = []
            for row in results:
                task = self.MODEL()
                for key, value in row.items():
                    setattr(task, key, value)
                tasks.append(task)
            return tasks

