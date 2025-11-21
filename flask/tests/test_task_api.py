import pytest
from flask import Flask

from app import create_app
from common.app_config import config
from common.models import Person, Email, LoginMethod, Task
from common.models.login_method import LoginMethodType
from common.services import PersonService, EmailService, LoginMethodService, TaskService
from common.helpers.auth import generate_access_token


@pytest.fixture(scope='session')
def app():
    """
    Create and configure a test Flask application instance.
    Using session scope to avoid Flask-RESTX API registration conflicts.
    """
    test_app = create_app()
    test_app.config['TESTING'] = True
    test_app.config['WTF_CSRF_ENABLED'] = False
    return test_app


@pytest.fixture(scope='function')
def client(app):
    """
    Create a test client for the Flask application.
    """
    return app.test_client()


@pytest.fixture
def test_person():
    """
    Create a test person for use in tests.
    """
    person = Person(
        first_name="Test",
        last_name="User"
    )
    return person


@pytest.fixture
def test_email(test_person):
    """
    Create a test email associated with the test person.
    """
    email = Email(
        person_id=test_person.entity_id,
        email="testuser@example.com",
        is_verified=True
    )
    return email


@pytest.fixture
def test_login_method(test_person, test_email):
    """
    Create a test login method associated with the test person and email.
    """
    login_method = LoginMethod(
        method_type=LoginMethodType.EMAIL_PASSWORD,
        raw_password="TestPassword123!"
    )
    login_method.person_id = test_person.entity_id
    login_method.email_id = test_email.entity_id
    return login_method


@pytest.fixture
def saved_test_data(test_person, test_email, test_login_method):
    """
    Save test person, email, and login method to the database and return them.
    This fixture ensures test data is persisted for use in API tests.
    """
    person_service = PersonService(config)
    email_service = EmailService(config)
    login_method_service = LoginMethodService(config)
    
    saved_person = person_service.save_person(test_person)
    saved_email = email_service.save_email(test_email)
    test_login_method.email_id = saved_email.entity_id
    saved_login_method = login_method_service.save_login_method(test_login_method)
    
    return {
        'person': saved_person,
        'email': saved_email,
        'login_method': saved_login_method
    }


@pytest.fixture
def auth_token(saved_test_data):
    """
    Generate a valid JWT access token for the test user.
    """
    login_method = saved_test_data['login_method']
    person = saved_test_data['person']
    email = saved_test_data['email']
    
    token, expiry = generate_access_token(login_method, person=person, email=email)
    return token


@pytest.fixture
def auth_headers(auth_token):
    """
    Create authorization headers with a valid access token.
    """
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def test_task(saved_test_data):
    """
    Create a test task associated with the test person.
    """
    task = Task(
        person_id=saved_test_data['person'].entity_id,
        title="Test Task",
        completed=False
    )
    return task


@pytest.fixture
def saved_test_task(test_task):
    """
    Save test task to the database and return it.
    """
    task_service = TaskService(config)
    saved_task = task_service.save_task(test_task)
    return saved_task


@pytest.fixture
def another_test_person():
    """
    Create another test person for testing unauthorized access.
    """
    person = Person(
        first_name="Another",
        last_name="User"
    )
    return person


@pytest.fixture
def another_test_email(another_test_person):
    """
    Create a test email associated with another test person.
    """
    email = Email(
        person_id=another_test_person.entity_id,
        email="anotheruser@example.com",
        is_verified=True
    )
    return email


@pytest.fixture
def another_test_login_method(another_test_person, another_test_email):
    """
    Create a test login method associated with another test person and email.
    """
    login_method = LoginMethod(
        method_type=LoginMethodType.EMAIL_PASSWORD,
        raw_password="AnotherPassword123!"
    )
    login_method.person_id = another_test_person.entity_id
    login_method.email_id = another_test_email.entity_id
    return login_method


@pytest.fixture
def saved_another_test_data(another_test_person, another_test_email, another_test_login_method):
    """
    Save another test person, email, and login method to the database.
    """
    person_service = PersonService(config)
    email_service = EmailService(config)
    login_method_service = LoginMethodService(config)
    
    saved_person = person_service.save_person(another_test_person)
    saved_email = email_service.save_email(another_test_email)
    another_test_login_method.email_id = saved_email.entity_id
    saved_login_method = login_method_service.save_login_method(another_test_login_method)
    
    return {
        'person': saved_person,
        'email': saved_email,
        'login_method': saved_login_method
    }


@pytest.fixture
def another_auth_token(saved_another_test_data):
    """
    Generate a valid JWT access token for another test user.
    """
    login_method = saved_another_test_data['login_method']
    person = saved_another_test_data['person']
    email = saved_another_test_data['email']
    
    token, expiry = generate_access_token(login_method, person=person, email=email)
    return token


@pytest.fixture
def another_auth_headers(another_auth_token):
    """
    Create authorization headers with another user's access token.
    """
    return {
        'Authorization': f'Bearer {another_auth_token}',
        'Content-Type': 'application/json'
    }


class TestTaskListGet:
    """
    Test cases for GET /tasks endpoint.
    """
    
    def test_get_tasks_success(self, client, auth_headers, saved_test_data, saved_test_task):
        """
        Test successful retrieval of all tasks for authenticated user.
        """
        response = client.get('/tasks', headers=auth_headers)
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'tasks' in response_data
        assert isinstance(response_data['tasks'], list)
        assert len(response_data['tasks']) >= 1
        
        task_found = False
        for task in response_data['tasks']:
            if task['entity_id'] == saved_test_task.entity_id:
                task_found = True
                assert task['title'] == saved_test_task.title
                assert task['completed'] == saved_test_task.completed
                assert task['person_id'] == saved_test_data['person'].entity_id
                break
        
        assert task_found is True
    
    def test_get_tasks_empty_list(self, client, auth_headers, saved_test_data):
        """
        Test that GET /tasks returns empty list when user has no tasks.
        """
        response = client.get('/tasks', headers=auth_headers)
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'tasks' in response_data
        assert isinstance(response_data['tasks'], list)
    
    def test_get_tasks_missing_auth(self, client):
        """
        Test that GET /tasks returns 401 when authorization header is missing.
        """
        response = client.get('/tasks')
        
        assert response.status_code == 401
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Authorization header not present' in response_data['message']
    
    def test_get_tasks_only_returns_user_tasks(self, client, auth_headers, another_auth_headers, saved_test_data, saved_another_test_data):
        """
        Test that GET /tasks only returns tasks belonging to the authenticated user.
        """
        task_service = TaskService(config)
        
        task_for_user1 = Task(
            person_id=saved_test_data['person'].entity_id,
            title="User 1 Task",
            completed=False
        )
        saved_task1 = task_service.save_task(task_for_user1)
        
        task_for_user2 = Task(
            person_id=saved_another_test_data['person'].entity_id,
            title="User 2 Task",
            completed=False
        )
        saved_task2 = task_service.save_task(task_for_user2)
        
        response_user1 = client.get('/tasks', headers=auth_headers)
        response_user2 = client.get('/tasks', headers=another_auth_headers)
        
        assert response_user1.status_code == 200
        assert response_user2.status_code == 200
        
        user1_data = response_user1.get_json()
        user2_data = response_user2.get_json()
        
        user1_task_ids = [task['entity_id'] for task in user1_data['tasks']]
        user2_task_ids = [task['entity_id'] for task in user2_data['tasks']]
        
        assert saved_task1.entity_id in user1_task_ids
        assert saved_task2.entity_id not in user1_task_ids
        
        assert saved_task2.entity_id in user2_task_ids
        assert saved_task1.entity_id not in user2_task_ids


class TestTaskCreatePost:
    """
    Test cases for POST /tasks endpoint.
    """
    
    def test_post_tasks_create_success(self, client, auth_headers, saved_test_data):
        """
        Test successful creation of a new task.
        """
        request_data = {
            'title': 'New Test Task'
        }
        
        response = client.post(
            '/tasks',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['message'] == 'Task created successfully.'
        assert 'task' in response_data
        assert response_data['task']['title'] == 'New Test Task'
        assert response_data['task']['completed'] is False
        assert response_data['task']['person_id'] == saved_test_data['person'].entity_id
        
        task_service = TaskService(config)
        created_task = task_service.get_task_by_id(response_data['task']['entity_id'])
        assert created_task is not None
        assert created_task.title == 'New Test Task'
        assert created_task.completed is False
    
    def test_post_tasks_missing_title(self, client, auth_headers):
        """
        Test that POST /tasks returns validation error when title is missing.
        """
        request_data = {}
        
        response = client.post(
            '/tasks',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'title' in response_data['message'].lower() or 'required' in response_data['message'].lower()
    
    def test_post_tasks_empty_title(self, client, auth_headers):
        """
        Test that POST /tasks returns validation error when title is empty.
        """
        request_data = {
            'title': ''
        }
        
        response = client.post(
            '/tasks',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'title' is required and cannot be empty" in response_data['message']
    
    def test_post_tasks_whitespace_only_title(self, client, auth_headers):
        """
        Test that POST /tasks returns validation error when title contains only whitespace.
        """
        request_data = {
            'title': '   '
        }
        
        response = client.post(
            '/tasks',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'title' is required and cannot be empty" in response_data['message']
    
    def test_post_tasks_strips_whitespace(self, client, auth_headers, saved_test_data):
        """
        Test that POST /tasks strips leading and trailing whitespace from title.
        """
        request_data = {
            'title': '  Trimmed Task Title  '
        }
        
        response = client.post(
            '/tasks',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['task']['title'] == 'Trimmed Task Title'
        
        task_service = TaskService(config)
        created_task = task_service.get_task_by_id(response_data['task']['entity_id'])
        assert created_task.title == 'Trimmed Task Title'
    
    def test_post_tasks_missing_auth(self, client):
        """
        Test that POST /tasks returns 401 when authorization header is missing.
        """
        request_data = {
            'title': 'Test Task'
        }
        
        response = client.post(
            '/tasks',
            json=request_data
        )
        
        assert response.status_code == 401
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Authorization header not present' in response_data['message']


class TestTaskUpdatePut:
    """
    Test cases for PUT /tasks/<task_id> endpoint.
    """
    
    def test_put_tasks_update_title_success(self, client, auth_headers, saved_test_task):
        """
        Test successful update of task title.
        """
        request_data = {
            'title': 'Updated Task Title'
        }
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['message'] == 'Task updated successfully.'
        assert response_data['task']['title'] == 'Updated Task Title'
        assert response_data['task']['completed'] == saved_test_task.completed
        
        task_service = TaskService(config)
        updated_task = task_service.get_task_by_id(saved_test_task.entity_id)
        assert updated_task.title == 'Updated Task Title'
    
    def test_put_tasks_update_completed_success(self, client, auth_headers, saved_test_task):
        """
        Test successful update of task completed status.
        """
        request_data = {
            'completed': True
        }
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['task']['completed'] is True
        assert response_data['task']['title'] == saved_test_task.title
        
        task_service = TaskService(config)
        updated_task = task_service.get_task_by_id(saved_test_task.entity_id)
        assert updated_task.completed is True
    
    def test_put_tasks_update_both_success(self, client, auth_headers, saved_test_task):
        """
        Test successful update of both title and completed status.
        """
        request_data = {
            'title': 'Updated Title and Status',
            'completed': True
        }
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['task']['title'] == 'Updated Title and Status'
        assert response_data['task']['completed'] is True
        
        task_service = TaskService(config)
        updated_task = task_service.get_task_by_id(saved_test_task.entity_id)
        assert updated_task.title == 'Updated Title and Status'
        assert updated_task.completed is True
    
    def test_put_tasks_empty_request_body(self, client, auth_headers, saved_test_task):
        """
        Test that PUT /tasks/<id> returns validation error when request body is empty.
        """
        request_data = {}
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "At least one of 'title' or 'completed' must be provided" in response_data['message']
    
    def test_put_tasks_empty_title(self, client, auth_headers, saved_test_task):
        """
        Test that PUT /tasks/<id> returns validation error when title is empty.
        """
        request_data = {
            'title': ''
        }
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'title' cannot be empty if provided" in response_data['message']
    
    def test_put_tasks_whitespace_only_title(self, client, auth_headers, saved_test_task):
        """
        Test that PUT /tasks/<id> returns validation error when title contains only whitespace.
        """
        request_data = {
            'title': '   '
        }
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'title' cannot be empty if provided" in response_data['message']
    
    def test_put_tasks_strips_whitespace(self, client, auth_headers, saved_test_task):
        """
        Test that PUT /tasks/<id> strips leading and trailing whitespace from title.
        """
        request_data = {
            'title': '  Trimmed Title  '
        }
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['task']['title'] == 'Trimmed Title'
        
        task_service = TaskService(config)
        updated_task = task_service.get_task_by_id(saved_test_task.entity_id)
        assert updated_task.title == 'Trimmed Title'
    
    def test_put_tasks_task_not_found(self, client, auth_headers):
        """
        Test that PUT /tasks/<id> returns error when task does not exist.
        """
        request_data = {
            'title': 'Updated Title'
        }
        
        fake_task_id = '00000000000000000000000000000000'
        response = client.put(
            f'/tasks/{fake_task_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Task not found' in response_data['message']
    
    def test_put_tasks_unauthorized_access(self, client, auth_headers, another_auth_headers, saved_test_data, saved_another_test_data):
        """
        Test that PUT /tasks/<id> returns error when user tries to update another user's task.
        """
        task_service = TaskService(config)
        
        task_for_user1 = Task(
            person_id=saved_test_data['person'].entity_id,
            title="User 1 Task",
            completed=False
        )
        saved_task = task_service.save_task(task_for_user1)
        
        request_data = {
            'title': 'Unauthorized Update Attempt'
        }
        
        response = client.put(
            f'/tasks/{saved_task.entity_id}',
            json=request_data,
            headers=another_auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'permission' in response_data['message'].lower() or 'not have permission' in response_data['message']
    
    def test_put_tasks_missing_auth(self, client, saved_test_task):
        """
        Test that PUT /tasks/<id> returns 401 when authorization header is missing.
        """
        request_data = {
            'title': 'Updated Title'
        }
        
        response = client.put(
            f'/tasks/{saved_test_task.entity_id}',
            json=request_data
        )
        
        assert response.status_code == 401
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Authorization header not present' in response_data['message']
    
    def test_put_tasks_completed_false(self, client, auth_headers, saved_test_data):
        """
        Test that PUT /tasks/<id> can set completed to False.
        """
        task_service = TaskService(config)
        
        completed_task = Task(
            person_id=saved_test_data['person'].entity_id,
            title="Completed Task",
            completed=True
        )
        saved_completed_task = task_service.save_task(completed_task)
        
        request_data = {
            'completed': False
        }
        
        response = client.put(
            f'/tasks/{saved_completed_task.entity_id}',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['task']['completed'] is False
        
        task_service = TaskService(config)
        updated_task = task_service.get_task_by_id(saved_completed_task.entity_id)
        assert updated_task.completed is False


class TestTaskDelete:
    """
    Test cases for DELETE /tasks/<task_id> endpoint.
    """
    
    def test_delete_tasks_success(self, client, auth_headers, saved_test_task):
        """
        Test successful deletion of a task.
        """
        task_id = saved_test_task.entity_id
        
        response = client.delete(
            f'/tasks/{task_id}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['message'] == 'Task deleted successfully.'
        
        task_service = TaskService(config)
        deleted_task = task_service.get_task_by_id(task_id)
        assert deleted_task is None
        
        tasks_list = task_service.get_tasks_by_person_id(saved_test_task.person_id)
        task_ids = [task.entity_id for task in tasks_list]
        assert task_id not in task_ids
    
    def test_delete_tasks_task_not_found(self, client, auth_headers):
        """
        Test that DELETE /tasks/<id> returns error when task does not exist.
        """
        fake_task_id = '00000000000000000000000000000000'
        response = client.delete(
            f'/tasks/{fake_task_id}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Task not found' in response_data['message']
    
    def test_delete_tasks_unauthorized_access(self, client, auth_headers, another_auth_headers, saved_test_data, saved_another_test_data):
        """
        Test that DELETE /tasks/<id> returns error when user tries to delete another user's task.
        """
        task_service = TaskService(config)
        
        task_for_user1 = Task(
            person_id=saved_test_data['person'].entity_id,
            title="User 1 Task",
            completed=False
        )
        saved_task = task_service.save_task(task_for_user1)
        
        response = client.delete(
            f'/tasks/{saved_task.entity_id}',
            headers=another_auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'permission' in response_data['message'].lower() or 'not have permission' in response_data['message']
        
        task_service = TaskService(config)
        task_still_exists = task_service.get_task_by_id(saved_task.entity_id)
        assert task_still_exists is not None
        assert task_still_exists.active is True
    
    def test_delete_tasks_missing_auth(self, client, saved_test_task):
        """
        Test that DELETE /tasks/<id> returns 401 when authorization header is missing.
        """
        response = client.delete(
            f'/tasks/{saved_test_task.entity_id}'
        )
        
        assert response.status_code == 401
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Authorization header not present' in response_data['message']
    
    def test_delete_tasks_removed_from_list(self, client, auth_headers, saved_test_data):
        """
        Test that deleted tasks are not returned in the task list.
        """
        task_service = TaskService(config)
        
        task_to_delete = Task(
            person_id=saved_test_data['person'].entity_id,
            title="Task to Delete",
            completed=False
        )
        saved_task = task_service.save_task(task_to_delete)
        
        task_to_keep = Task(
            person_id=saved_test_data['person'].entity_id,
            title="Task to Keep",
            completed=False
        )
        saved_task_to_keep = task_service.save_task(task_to_keep)
        
        response_before = client.get('/tasks', headers=auth_headers)
        tasks_before = response_before.get_json()['tasks']
        task_ids_before = [task['entity_id'] for task in tasks_before]
        assert saved_task.entity_id in task_ids_before
        assert saved_task_to_keep.entity_id in task_ids_before
        
        delete_response = client.delete(
            f'/tasks/{saved_task.entity_id}',
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        
        response_after = client.get('/tasks', headers=auth_headers)
        tasks_after = response_after.get_json()['tasks']
        task_ids_after = [task['entity_id'] for task in tasks_after]
        assert saved_task.entity_id not in task_ids_after
        assert saved_task_to_keep.entity_id in task_ids_after

