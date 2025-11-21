import pytest
import jwt
import time
from flask import Flask

from app import create_app
from common.app_config import config
from common.models import Person, Email, LoginMethod
from common.models.login_method import LoginMethodType
from common.services import PersonService, EmailService, LoginMethodService
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


class TestPersonMeGet:
    """
    Test cases for GET /person/me endpoint.
    """
    
    def test_get_person_me_success(self, client, auth_headers, saved_test_data):
        """
        Test successful retrieval of current user's person data.
        """
        response = client.get('/person/me', headers=auth_headers)
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'person' in response_data
        assert response_data['person']['first_name'] == saved_test_data['person'].first_name
        assert response_data['person']['last_name'] == saved_test_data['person'].last_name
    
    def test_get_person_me_missing_auth(self, client):
        """
        Test that GET /person/me returns 401 when authorization header is missing.
        """
        response = client.get('/person/me')
        
        assert response.status_code == 401
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Authorization header not present' in response_data['message']


class TestPersonMePut:
    """
    Test cases for PUT /person/me endpoint.
    """
    
    def test_put_person_me_update_both_names_success(self, client, auth_headers, saved_test_data):
        """
        Test successful update of both first_name and last_name.
        """
        request_data = {
            'first_name': 'UpdatedFirst',
            'last_name': 'UpdatedLast'
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['message'] == 'Name updated successfully.'
        assert response_data['person']['first_name'] == 'UpdatedFirst'
        assert response_data['person']['last_name'] == 'UpdatedLast'
        
        # Verify the update persisted in the database
        person_service = PersonService(config)
        updated_person = person_service.get_person_by_id(saved_test_data['person'].entity_id)
        assert updated_person.first_name == 'UpdatedFirst'
        assert updated_person.last_name == 'UpdatedLast'
    
    def test_put_person_me_update_first_name_only_success(self, client, auth_headers, saved_test_data):
        """
        Test successful update of first_name only.
        """
        original_last_name = saved_test_data['person'].last_name
        request_data = {
            'first_name': 'NewFirstName'
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['person']['first_name'] == 'NewFirstName'
        assert response_data['person']['last_name'] == original_last_name
        
        # Verify the update persisted in the database
        person_service = PersonService(config)
        updated_person = person_service.get_person_by_id(saved_test_data['person'].entity_id)
        assert updated_person.first_name == 'NewFirstName'
        assert updated_person.last_name == original_last_name
    
    def test_put_person_me_update_last_name_only_success(self, client, auth_headers, saved_test_data):
        """
        Test successful update of last_name only.
        """
        original_first_name = saved_test_data['person'].first_name
        request_data = {
            'last_name': 'NewLastName'
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['person']['first_name'] == original_first_name
        assert response_data['person']['last_name'] == 'NewLastName'
        
        # Verify the update persisted in the database
        person_service = PersonService(config)
        updated_person = person_service.get_person_by_id(saved_test_data['person'].entity_id)
        assert updated_person.first_name == original_first_name
        assert updated_person.last_name == 'NewLastName'
    
    def test_put_person_me_missing_auth(self, client):
        """
        Test that PUT /person/me returns 401 when authorization header is missing.
        """
        request_data = {
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        response = client.put(
            '/person/me',
            json=request_data
        )
        
        assert response.status_code == 401
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Authorization header not present' in response_data['message']
    
    def test_put_person_me_empty_request_body(self, client, auth_headers):
        """
        Test that PUT /person/me returns validation error when request body is empty.
        """
        request_data = {}
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "At least one of 'first_name' or 'last_name' must be provided" in response_data['message']
    
    def test_put_person_me_empty_first_name_string(self, client, auth_headers):
        """
        Test that PUT /person/me returns validation error when first_name is an empty string.
        """
        request_data = {
            'first_name': '',
            'last_name': 'ValidLastName'
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'first_name' cannot be empty if provided" in response_data['message']
    
    def test_put_person_me_empty_last_name_string(self, client, auth_headers):
        """
        Test that PUT /person/me returns validation error when last_name is an empty string.
        """
        request_data = {
            'first_name': 'ValidFirstName',
            'last_name': ''
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'last_name' cannot be empty if provided" in response_data['message']
    
    def test_put_person_me_whitespace_only_first_name(self, client, auth_headers):
        """
        Test that PUT /person/me returns validation error when first_name contains only whitespace.
        """
        request_data = {
            'first_name': '   ',
            'last_name': 'ValidLastName'
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'first_name' cannot be empty if provided" in response_data['message']
    
    def test_put_person_me_whitespace_only_last_name(self, client, auth_headers):
        """
        Test that PUT /person/me returns validation error when last_name contains only whitespace.
        """
        request_data = {
            'first_name': 'ValidFirstName',
            'last_name': '   '
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "'last_name' cannot be empty if provided" in response_data['message']
    
    def test_put_person_me_invalid_token(self, client):
        """
        Test that PUT /person/me returns 401 when access token is invalid.
        """
        request_data = {
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        invalid_headers = {
            'Authorization': 'Bearer invalid_token_here',
            'Content-Type': 'application/json'
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=invalid_headers
        )
        
        assert response.status_code == 401
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Access token is invalid' in response_data['message']
    
    def test_put_person_me_strips_whitespace(self, client, auth_headers, saved_test_data):
        """
        Test that PUT /person/me strips leading and trailing whitespace from names.
        """
        request_data = {
            'first_name': '  TrimmedFirst  ',
            'last_name': '  TrimmedLast  '
        }
        
        response = client.put(
            '/person/me',
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['person']['first_name'] == 'TrimmedFirst'
        assert response_data['person']['last_name'] == 'TrimmedLast'
        
        # Verify the trimmed values persisted in the database
        person_service = PersonService(config)
        updated_person = person_service.get_person_by_id(saved_test_data['person'].entity_id)
        assert updated_person.first_name == 'TrimmedFirst'
        assert updated_person.last_name == 'TrimmedLast'

