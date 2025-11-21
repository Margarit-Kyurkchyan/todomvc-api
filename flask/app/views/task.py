from flask_restx import Namespace, Resource, Model, fields
from flask import request
from app.helpers.response import get_success_response, parse_request_body, validate_required_fields
from app.helpers.decorators import login_required
from common.app_config import config
from common.services import TaskService
from common.models.task import Task
from common.helpers.exceptions import InputValidationError

# Create the task blueprint
task_api = Namespace('tasks', description="Task-related APIs")

# Define the request model for creating a task
create_task_model = Model('CreateTask', {
    'title': fields.String(description='Title of the task', required=True)
})

# Define the request model for updating a task
update_task_model = Model('UpdateTask', {
    'title': fields.String(description='Title of the task', required=False),
    'completed': fields.Boolean(description='Completion status of the task', required=False)
})

task_api.models[create_task_model.name] = create_task_model
task_api.models[update_task_model.name] = update_task_model


@task_api.route('')
class Tasks(Resource):
    """
    Endpoints for managing tasks.
    """
    
    @login_required()
    def get(self, person):
        """
        Get all tasks for the current authenticated user.
        
        Returns a list of all tasks belonging to the authenticated user.
        
        Returns:
            dict: Success response with list of tasks
        """
        task_service = TaskService(config)
        tasks = task_service.get_tasks_by_person_id(person.entity_id)
        
        tasks_list = [task.as_dict() for task in tasks] if tasks else []
        
        return get_success_response(tasks=tasks_list)

    @task_api.expect(create_task_model)
    @login_required()
    def post(self, person):
        """
        Create a new task for the current authenticated user.
        
        Creates a new task with the provided title. The task will be
        associated with the authenticated user and marked as incomplete by default.
        
        Args:
            title (str): Title of the task (required)
        
        Returns:
            dict: Success response with created task data and confirmation message
        
        Raises:
            InputValidationError: If title is not provided or is empty
        """
        parsed_body = parse_request_body(request, ["title"], default_value=None)
        validate_required_fields(parsed_body)
        
        title = parsed_body.get("title")
        
        if not title or not str(title).strip():
            raise InputValidationError("'title' cannot be empty.")
        
        task_service = TaskService(config)
        
        new_task = Task(
            person_id=person.entity_id,
            title=title.strip(),
            completed=False
        )
        
        saved_task = task_service.save_task(new_task)
        
        return get_success_response(message="Task created successfully.", task=saved_task.as_dict())


@task_api.route('/<string:task_id>')
class TaskById(Resource):
    """
    Endpoints for managing a specific task by ID.
    """
    
    @task_api.expect(update_task_model)
    @login_required()
    def put(self, task_id, person):
        """
        Update an existing task.
        
        Allows updating the title and/or completion status of a task.
        The task must belong to the authenticated user.
        
        Args:
            task_id (str): ID of the task to update
            title (str, optional): New title for the task
            completed (bool, optional): New completion status for the task
        
        Returns:
            dict: Success response with updated task data and confirmation message
        
        Raises:
            InputValidationError: If task is not found, doesn't belong to user, or if provided title is empty
        """
        parsed_body = parse_request_body(request, ["title", "completed"], default_value=None)
        
        title = parsed_body.get("title")
        completed = parsed_body.get("completed")
        
        if title is None and completed is None:
            raise InputValidationError("At least one of 'title' or 'completed' must be provided.")
        
        if title is not None and (not title or not str(title).strip()):
            raise InputValidationError("'title' cannot be empty if provided.")
        
        task_service = TaskService(config)
        
        existing_task = task_service.get_task_by_id(task_id)
        
        if not existing_task:
            raise InputValidationError("Task not found.")
        
        if existing_task.person_id != person.entity_id:
            raise InputValidationError("You do not have permission to update this task.")
        
        if title is not None:
            existing_task.title = title.strip()
        
        if completed is not None:
            existing_task.completed = bool(completed)
        
        task_service.save_task(existing_task)
        
        updated_task = task_service.get_task_by_id(task_id)
        
        return get_success_response(message="Task updated successfully.", task=updated_task.as_dict())

    @login_required()
    def delete(self, task_id, person):
        """
        Delete an existing task.
        
        Soft deletes a task by setting its active status to False.
        The task must belong to the authenticated user.
        
        Args:
            task_id (str): ID of the task to delete
        
        Returns:
            dict: Success response with confirmation message
        
        Raises:
            InputValidationError: If task is not found or doesn't belong to user
        """
        task_service = TaskService(config)
        
        existing_task = task_service.get_task_by_id(task_id)
        
        if not existing_task:
            raise InputValidationError("Task not found.")
        
        if existing_task.person_id != person.entity_id:
            raise InputValidationError("You do not have permission to delete this task.")
        
        task_service.delete_task(existing_task)
        
        return get_success_response(message="Task deleted successfully.")

