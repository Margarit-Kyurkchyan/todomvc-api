from flask_restx import Namespace, Resource, Model, fields
from flask import request
from app.helpers.response import get_success_response, get_failure_response, parse_request_body, validate_required_fields
from app.helpers.decorators import login_required
from common.app_config import config
from common.services import AuthService, PersonService, OAuthClient

# Create the auth blueprint
auth_api = Namespace('auth', description="Auth related APIs")

# Define request models
signup_model = Model('Signup', {
    'first_name': fields.String(description='First name of the user', required=True),
    'last_name': fields.String(description='Last name of the user', required=True),
    'email_address': fields.String(description='Email address of the user', required=True)
})

login_model = Model('Login', {
    'email': fields.String(description='Email address of the user', required=True),
    'password': fields.String(description='Password of the user', required=True)
})

forgot_password_model = Model('ForgotPassword', {
    'email': fields.String(description='Email address of the user requesting password reset', required=True)
})

reset_password_model = Model('ResetPassword', {
    'password': fields.String(description='New password for the user', required=True)
})

# Register models
auth_api.models[signup_model.name] = signup_model
auth_api.models[login_model.name] = login_model
auth_api.models[forgot_password_model.name] = forgot_password_model
auth_api.models[reset_password_model.name] = reset_password_model


@auth_api.route('/test')
class Test(Resource):
    def get(self):
        login_data = {
            "username": "test",
            "password": "test"
        }
        return get_success_response(**login_data)


@auth_api.route('/signup')
class Signup(Resource):
    @auth_api.expect(signup_model)
    def post(self):
        """
        Register a new user account and send an onboarding email.

        Request Body:
            first_name (str): User's first name.
            last_name (str): User's last name.
            email_address (str): Unique email address for the account; must be a valid email.

        Returns:
            dict: Confirmation message indicating that the sign-up flow started successfully.

        Raises:
            InputValidationError: Raised when a required field is missing or empty.
        """
        parsed_body = parse_request_body(request, ['first_name', 'last_name', 'email_address'])
        validate_required_fields(parsed_body)

        auth_service = AuthService(config)

        auth_service.signup(
            parsed_body['email_address'],
            parsed_body['first_name'],
            parsed_body['last_name']
        )
        return get_success_response(message="User signed up successfully and verification email is sent.")


@auth_api.route('/login')
class Login(Resource):
    @auth_api.expect(login_model)
    def post(self):
        """
        Validate user credentials and issue an access token.

        Request Body:
            email (str): Email address of the registered user.
            password (str): Plain-text password corresponding to the email.

        Returns:
            dict: Success response that contains serialized person data, an access token and its expiry.

        Raises:
            InputValidationError: Raised when the payload is missing required keys or when credentials are invalid.
            APIException: Propagated for service-level failures.
        """
        parsed_body = parse_request_body(request, ['email', 'password'])
        validate_required_fields(parsed_body)

        auth_service = AuthService(config)
        access_token, expiry = auth_service.login_user_by_email_password(
            parsed_body['email'], 
            parsed_body['password']
        )

        person_service = PersonService(config)
        person = person_service.get_person_by_email_address(email_address=parsed_body['email'])

        return get_success_response(person=person.as_dict(), access_token=access_token, expiry=expiry)


@auth_api.route('/forgot_password', doc=dict(description="Send reset password link"))
class ForgotPassword(Resource):
    @auth_api.expect(forgot_password_model)
    def post(self):
        """
        Trigger delivery of a password reset link to a registered email address.

        Request Body:
            email (str): Email address tied to the account that needs a reset link.

        Returns:
            dict: Confirmation that the reset email was queued for delivery.

        Raises:
            InputValidationError: Raised when the email field is missing or blank.
            APIException: Raised when the supplied email is not registered or when dependent services fail.
        """
        parsed_body = parse_request_body(request, ['email'])
        validate_required_fields(parsed_body)

        auth_service = AuthService(config)
        auth_service.trigger_forgot_password_email(parsed_body.get('email'))

        return get_success_response(message="Password reset email sent successfully.")


@auth_api.route(
    '/reset_password/<string:token>/<string:uidb64>',
    doc=dict(description="Update the password using reset password link")
)
class ResetPassword(Resource):
    @auth_api.expect(reset_password_model)
    def post(self, token, uidb64):
        parsed_body = parse_request_body(request, ['password'])
        validate_required_fields(parsed_body)

        auth_service = AuthService(config)
        access_token, expiry, person_obj = auth_service.reset_user_password(token, uidb64, parsed_body.get('password'))
        return get_success_response(
            message="Your password has been updated!", 
            access_token=access_token, 
            expiry=expiry,
            person=person_obj.as_dict()
        )


@auth_api.route('/<string:provider>/exchange')
class OAuthExchange(Resource):
    def post(self, provider):
        """
        Exchange OAuth authorization code for access token and user info
        
        Args:
            provider: OAuth provider (google, microsoft)
        """
        parsed_body = parse_request_body(
            request,
            ['code', 'redirect_uri', 'code_verifier']
        )
        validate_required_fields(parsed_body)

        oauth_client = OAuthClient(config)
        auth_service = AuthService(config)

        try:
            # Token exchange + user info retrieval
            if provider == "google":
                token_response = oauth_client.get_google_token(
                    parsed_body['code'],
                    parsed_body['redirect_uri'],
                    parsed_body['code_verifier']
                )
                user_info = oauth_client.get_google_user_info(token_response['access_token'])

            elif provider == "microsoft":
                token_response = oauth_client.get_microsoft_token(
                    parsed_body['code'],
                    parsed_body['redirect_uri'],
                    parsed_body['code_verifier']
                )
                user_info = oauth_client.get_microsoft_user_info(token_response['access_token'])

            else:
                return get_failure_response(message=f"Unsupported provider: {provider}")

            # Normalize name + email
            if provider == "google":
                email = user_info.get('email')
                name = user_info.get('name', '')

            elif provider == "microsoft":
                email = user_info.get('email')
                name = user_info.get('name', '')

            if not email:
                return get_failure_response(message=f"{provider.capitalize()} user info does not contain email.")

            name_parts = name.split(' ', 1)
            first_name, last_name = name_parts[0], name_parts[1] if len(name_parts) > 1 else ""

            # Login or create user
            access_token, expiry, person = auth_service.login_user_by_oauth(
                email, first_name, last_name,
                provider=provider,
                provider_data=user_info
            )

            return get_success_response(person=person.as_dict(), access_token=access_token, expiry=expiry)

        except Exception as e:
            return get_failure_response(message=f"OAuth authentication failed: {str(e)}")


@auth_api.route('/logout')
class Logout(Resource):
    @login_required()
    def post(self, person):
        """
        Logout user - log the event and return success
        
        Args:
            person: Current authenticated user (injected by login_required decorator)
        """
        try:
            # Log the logout attempt
            if person and hasattr(person, 'first_name') and hasattr(person, 'last_name'):
                print(f"User {person.first_name} {person.last_name} (ID: {person.entity_id}) logged out")
            else:
                print("User logged out (person details not available)")
            
            # Note: Frontend will clear local data and redirect
            # JWT tokens will naturally expire based on their expiry time
            
            return get_success_response(message="Logged out successfully")
            
        except Exception as e:
            # Even if there's an error, return success to not block frontend logout
            print(f"Logout endpoint error (non-blocking): {e}")
            return get_success_response(message="Logged out successfully")
