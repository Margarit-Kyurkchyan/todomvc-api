from flask import Flask, g, Request
from flask_restx import Api
from flask_cors import CORS


from rococo.plugins.pooled_connection import PooledConnectionPlugin
from rococo.models.versioned_model import ModelValidationError

from common.helpers.exceptions import InputValidationError, APIException

from common.app_config import get_config
from common.utils.version import get_service_version, get_project_name
from logger import set_request_exception_signal, logger



# Initialize Flask-Restx
api = Api(
    version=get_service_version(),
    title=get_project_name(),
    description="Welcome to the API documentation of TodoMVC API",
    authorizations={'Bearer': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization'}},
    security='Bearer',
    doc='/api-doc'
)

def create_app():
    config = get_config()

    app = Flask(__name__)
    app.config.from_object(config)

    with app.app_context():
        set_request_exception_signal(app)

    # Register views
    from app.views import initialize_views
    initialize_views(api)

    api.init_app(app)

    # Add simple CORS support
    CORS(app)

    PooledConnectionPlugin(app, database_type="postgres")

    @app.route('/')
    def hello_world():
        return 'Welcome to TodoMVC API.'

    @app.errorhandler(ModelValidationError)
    def handle_model_validation_error(exception):
        # Handle your custom exception here
        from app.helpers.response import get_failure_response
        return get_failure_response(message='\n'.join(exception.errors))

    @app.errorhandler(InputValidationError)
    def handle_input_validation_error(exception):
        # Handle your custom exception here
        from app.helpers.response import get_failure_response
        return get_failure_response(message=str(exception))


    @app.errorhandler(APIException)
    def handle_application_error(exception):
        # Handle your custom exception here
        from app.helpers.response import get_failure_response
        return get_failure_response(message=str(exception))

    return app
