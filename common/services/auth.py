import time

import jwt
from werkzeug.security import check_password_hash

from common.services import (
    PersonService, EmailService, LoginMethodService, OrganizationService,
    PersonOrganizationRoleService
)
from common.models import Person, Email, LoginMethod, Organization, PersonOrganizationRole
from common.models.login_method import LoginMethodType
from common.tasks.send_message import MessageSender
from common.app_logger import logger

from common.helpers.string_utils import urlsafe_base64_encode, force_bytes
from common.helpers.string_utils import force_str, urlsafe_base64_decode
from common.helpers.exceptions import InputValidationError, APIException
from common.helpers.auth import generate_access_token


class AuthService:
    def __init__(self, config):
        self.config = config

        self.EMAIL_TRANSMITTER_QUEUE_NAME = config.QUEUE_NAME_PREFIX + config.EMAIL_SERVICE_PROCESSOR_QUEUE_NAME
        
        self.person_service = PersonService(config)
        self.email_service = EmailService(config)
        self.login_method_service = LoginMethodService(config)
        self.organization_service = OrganizationService(config)
        self.person_organization_role_service = PersonOrganizationRoleService(config)

        self.message_sender = MessageSender()

    def signup(self, email, first_name, last_name):
        login_method = LoginMethod(
            method_type=LoginMethodType.EMAIL_PASSWORD,
            raw_password=self.config.DEFAULT_USER_PASSWORD
        )

        existing_email = self.email_service.get_email_by_email_address(email)
        if existing_email:
            # Check if this email is already registered with OAuth
            existing_login_method = self.login_method_service.get_login_method_by_email_id(existing_email.entity_id)
            
            if existing_login_method and existing_login_method.is_oauth_method:
                provider_name = existing_login_method.oauth_provider_name or "OAuth provider"
                raise InputValidationError(f"This email address is already registered with {provider_name}. Please use the {provider_name} sign-in option instead of creating a new account.")
            else:
                raise InputValidationError("The email address you provided is already registered.")

        person = Person(first_name=first_name, last_name=last_name)

        email = Email(person_id=person.entity_id, email=email)

        login_method.person_id = person.entity_id
        login_method.email_id = email.entity_id

        organization = Organization(
            name=f"{first_name}'s Organization"
        )

        person_organization_role = PersonOrganizationRole(
            person_id=person.entity_id,
            organization_id=organization.entity_id,
            role="admin"
        )

        email = self.email_service.save_email(email)
        person = self.person_service.save_person(person)
        login_method = self.login_method_service.save_login_method(login_method)

        self.organization_service.save_organization(organization)
        self.person_organization_role_service.save_person_organization_role(person_organization_role)
        self.send_welcome_email(login_method, person, email.email)

    def generate_reset_password_token(self, login_method: LoginMethod, email: str):
        person_id, email_id = login_method.person_id, login_method.email_id
        token = jwt.encode(
            {
                'email': email,
                'email_id': email_id,
                'person_id': person_id,
                'exp': time.time() + int(self.config.RESET_TOKEN_EXPIRE),
            },
            login_method.password,
            algorithm='HS256'
        )
        return token

    def prepare_password_reset_url(self, login_method: LoginMethod, email: str):
        token = self.generate_reset_password_token(login_method, email)
        uid = urlsafe_base64_encode(force_bytes(login_method.entity_id))
        password_reset_url = self.config.VUE_APP_URI + "/set-password/" + token + "/" + uid
        return password_reset_url

    def send_welcome_email(self, login_method: LoginMethod, person: Person, email: str):
        if confirmation_link := self.prepare_password_reset_url(login_method, email):
            message = {
                "event": "WELCOME_EMAIL",
                "data": {
                    "confirmation_link": confirmation_link,
                    "recipient_name": f"{person.first_name} {person.last_name}".strip(),
                },
                "to_emails": [email],
            }
            logger.info("confirmation_link")
            logger.info(confirmation_link)
            self.message_sender.send_message(self.EMAIL_TRANSMITTER_QUEUE_NAME, message)

    def login_user_by_email_password(self, email: str, password: str):
        email_obj = self.email_service.get_email_by_email_address(email)

        if not email_obj:
            raise InputValidationError("Email is not registered.")
        
        login_method = self.login_method_service.get_login_method_by_email_id(email_obj.entity_id)
        
        if not login_method:
            raise InputValidationError("Login method not found for this email.")
        
        # Check if this is an OAuth account
        if login_method.is_oauth_method:
            provider_name = login_method.oauth_provider_name or "OAuth provider"
            raise InputValidationError(f"This account was created using {provider_name}. Please use the {provider_name} sign-in option instead of email/password.")
        
        # Check if password is None (shouldn't happen for email/password accounts, but safety check)
        if not login_method.password:
            raise InputValidationError("This account does not have a password set. Please use the appropriate sign-in method.")

        if not check_password_hash(login_method.password, password):
            raise InputValidationError('Incorrect email or password.')

        person = self.person_service.get_person_by_id(login_method.person_id)

        if not person or not email:
            raise InputValidationError("Could not find complete user profile for this link.")

        access_token, expiry = generate_access_token(login_method, person=person, email=email_obj)

        return access_token, expiry

    def login_user_by_oauth(self, email: str, first_name: str, last_name: str, provider: str, provider_data: dict, person_id: str = None):
        """
        Login or create user via OAuth provider
        
        Args:
            email: User's email from OAuth provider
            first_name: User's first name
            last_name: User's last name
            provider: OAuth provider name (google, microsoft)
            provider_data: Raw data from OAuth provider
            person_id: Optional person ID if user already exists
            
        Returns:
            tuple: (access_token, expiry, person)
        """
        # Check if user already exists
        existing_email = self.email_service.get_email_by_email_address(email)
        
        if existing_email:
            # User exists, get their login method and person
            login_method = self.login_method_service.get_login_method_by_email_id(existing_email.entity_id)
            
            # Get person from email's person_id (more reliable)
            person = self.person_service.get_person_by_id(existing_email.person_id)
            
            if not person:
                raise APIException("Person not found for existing email.")
            
            # If no login method exists, create one (this can happen if there was a data inconsistency)
            if not login_method:
                # Create OAuth login method for existing user
                login_method = LoginMethod(
                    method_type=f"oauth-{provider}",
                    raw_password="TempPassword123!"  # Temporary password that will be cleared
                )
                login_method.person_id = person.entity_id
                login_method.email_id = existing_email.entity_id
                login_method.method_data = provider_data
                login_method.password = None  # OAuth users don't need passwords
                
                # Save the new login method
                login_method = self.login_method_service.save_login_method(login_method)
                print(f"Created missing login method for existing user: {email}")
            else:
                # Update existing login method to include OAuth info if needed
                if not login_method.is_oauth_method:
                    login_method.method_type = f"oauth-{provider}"
                    login_method.method_data = provider_data
                    # For OAuth methods, ensure password is None
                    login_method.password = None
                    self.login_method_service.save_login_method(login_method)
            
            # Ensure email is verified for OAuth users
            if not existing_email.is_verified:
                existing_email = self.email_service.verify_email(existing_email)
            
            # Generate access token
            access_token, expiry = generate_access_token(login_method, person=person, email=existing_email)
            return access_token, expiry, person
        else:
            # Create new user
            person = Person(first_name=first_name, last_name=last_name)
            if person_id:
                person.entity_id = person_id
            
            # Create email (verified for OAuth users)
            email_obj = Email(person_id=person.entity_id, email=email, is_verified=True)
            
            # Create OAuth login method - we need to handle this differently since raw_password is required
            # For OAuth users, we'll create with a temporary password then clear it
            temp_login_method = LoginMethod(
                method_type=f"oauth-{provider}",
                raw_password="TempPassword123!"  # Temporary password that will be cleared
            )
            temp_login_method.person_id = person.entity_id
            temp_login_method.email_id = email_obj.entity_id
            temp_login_method.method_data = provider_data
            
            # Clear the password after hashing (since OAuth users don't need passwords)
            temp_login_method.password = None
            
            # Create organization
            organization = Organization(
                name=f"{first_name}'s Organization"
            )
            
            # Create person-organization role
            person_organization_role = PersonOrganizationRole(
                person_id=person.entity_id,
                organization_id=organization.entity_id,
                role="admin"
            )
            
            # Save everything
            email_obj = self.email_service.save_email(email_obj)
            person = self.person_service.save_person(person)
            login_method = self.login_method_service.save_login_method(temp_login_method)
            self.organization_service.save_organization(organization)
            self.person_organization_role_service.save_person_organization_role(person_organization_role)
            
            # Generate access token
            access_token, expiry = generate_access_token(login_method, person=person, email=email_obj)
            return access_token, expiry, person

    @staticmethod
    def parse_reset_password_token(token, login_method: LoginMethod):
        try:
            decoded = jwt.decode(token, login_method.password, algorithms=['HS256'])
            exp_time = decoded['exp']
            if time.time() <= exp_time:
                return decoded
        except jwt.ExpiredSignatureError:
            return

    def trigger_forgot_password_email(self, email: str):
        email_obj = self.email_service.get_email_by_email_address(email)
        if not email_obj:
            raise APIException("Email is not registered.")
        
        person = self.person_service.get_person_by_id(email_obj.person_id)
        if not person:
            raise APIException("Person does not exist.")

        login_method = self.login_method_service.get_login_method_by_email_id(email_obj.entity_id)
        if not login_method:
            raise APIException("Login method does not exist.")

        self.send_password_reset_email(email=email_obj.email, login_method=login_method)

    def send_password_reset_email(self, email: str, login_method: LoginMethod):
        if password_reset_url := self.prepare_password_reset_url(login_method, email):
            message = {
                "event": "RESET_PASSWORD",
                "data": {
                    "reset_password_link": password_reset_url
                },
                "to_emails": [email],
            }
            self.message_sender.send_message(self.EMAIL_TRANSMITTER_QUEUE_NAME, message)

    def reset_user_password(self, token: str, uidb64: str, password: str):
        # Create new login method temporarily to validate and generate hashed password in its `password` field.`
        new_login_method = LoginMethod(
            method_type=LoginMethodType.EMAIL_PASSWORD,
            raw_password=password
        )

        login_method_id = force_str(urlsafe_base64_decode(uidb64))
        login_method = self.login_method_service.get_login_method_by_id(login_method_id)

        if not login_method:
            raise APIException("Invalid password reset URL.")
        
        parsed_token = self.parse_reset_password_token(token, login_method)

        if not parsed_token:
            raise APIException("Invalid reset password token.")
        
        email_obj = self.email_service.get_email_by_id(parsed_token['email_id'])
        if not email_obj:
            raise APIException("Email not found.")
        
        person_obj = self.person_service.get_person_by_id(parsed_token['person_id'])
        if not person_obj:
            raise APIException("Person with email not found.")

        login_method = self.login_method_service.update_password(login_method, new_login_method.password)

        email_obj = self.email_service.verify_email(email_obj)

        access_token, expiry = generate_access_token(login_method, person=person_obj, email=email_obj)

        return access_token, expiry, person_obj