from app.views.auth import auth_api
from app.views.organization import organization_api
from app.views.person import person_api
from app.views.task import task_api

def initialize_views(api):
    api.add_namespace(auth_api)
    api.add_namespace(organization_api)
    api.add_namespace(person_api)
    api.add_namespace(task_api)
