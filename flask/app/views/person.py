from flask_restx import Namespace, Resource, Model, fields
from flask import request
from app.helpers.response import get_success_response, parse_request_body
from app.helpers.decorators import login_required
from common.app_config import config
from common.services import PersonService
from common.helpers.exceptions import InputValidationError

# Create the organization blueprint
person_api = Namespace('person', description="Person-related APIs")

# Define the request model for updating person
update_person_model = Model('UpdatePerson', {
    'first_name': fields.String(description='First name of the person', required=False),
    'last_name': fields.String(description='Last name of the person', required=False)
})

person_api.models[update_person_model.name] = update_person_model


@person_api.route('/me')
class Me(Resource):
    """
    Endpoints for managing the current authenticated user's person information.
    """
    
    @login_required()
    def get(self, person):
        """
        Get the current authenticated user's person information.
        
        Returns the person data from the database for the authenticated user,
        including first_name and last_name.
        
        Returns:
            dict: Success response with person data
        """
        person_service = PersonService(config)
        
        # Fetch the actual person from the database, not from token
        db_person = person_service.get_person_by_id(person.entity_id)
        
        if not db_person:
            raise InputValidationError("Person not found.")
        
        return get_success_response(person=db_person)

    @person_api.expect(update_person_model)
    @login_required()
    def put(self, person):
        """
        Update the current authenticated user's name.
        
        Allows updating first_name and/or last_name. At least one field must be provided.
        Both fields are optional, but if provided, they cannot be empty or whitespace-only.
        Leading and trailing whitespace will be automatically trimmed.
        
        Args:
            first_name (str, optional): New first name for the user
            last_name (str, optional): New last name for the user
        
        Returns:
            dict: Success response with updated person data and confirmation message
        
        Raises:
            InputValidationError: If no fields are provided, or if provided fields are empty
        """
        parsed_body = parse_request_body(request, ["first_name", "last_name"], default_value=None)
        
        first_name = parsed_body.get("first_name")
        last_name = parsed_body.get("last_name")
        
        if not first_name and not last_name:
            raise InputValidationError("At least one of 'first_name' or 'last_name' must be provided.")
        
        if first_name is not None and (not first_name or not str(first_name).strip()):
            raise InputValidationError("'first_name' cannot be empty if provided.")
        
        if last_name is not None and (not last_name or not str(last_name).strip()):
            raise InputValidationError("'last_name' cannot be empty if provided.")
        
        person_service = PersonService(config)
        
        # Fetch the actual person from the database using the entity_id from the token
        db_person = person_service.get_person_by_id(person.entity_id)
        
        if not db_person:
            raise InputValidationError("Person not found.")
        
        if first_name is not None:
            db_person.first_name = first_name.strip()
        
        if last_name is not None:
            db_person.last_name = last_name.strip()
        
        person_service.save_person(db_person)
        
        # Fetch the person again from database to ensure we return the latest saved version
        saved_person = person_service.get_person_by_id(person.entity_id)

        return get_success_response(message="Name updated successfully.", person=saved_person)
