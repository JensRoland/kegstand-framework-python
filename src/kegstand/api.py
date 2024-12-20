import os
from typing import Any

from . import Logger
from .utils import (
    api_response,
    find_resource_modules,
)

logger = Logger()


# Class RestApi provides a container for API resources and a method to add
# resources to the API.
class RestApi:
    def __init__(self, root: str | None = None):
        self.resources: list[dict[str, Any]] = []
        if root is not None:
            source_path = os.path.dirname(os.path.dirname(os.path.abspath(root)))
            logger.info(f"Adding resources from {root} : source_path={source_path}")
            self.find_and_add_resources(source_path)

    def add_resource(self, resource, is_public: bool = False):
        # Resource is a ApiResource object
        self.resources.append(
            {
                "resource": resource,
                "is_public": is_public,
            }
        )

    def find_and_add_resources(self, api_source_root: str):
        # Look through folder structure, importing and adding resources to the API.
        # Expects a folder structure like this:
        # api/
        #   [resource_name].py which exposes a resource object named `api`
        # api/public/
        #   [resource_name].py which exposes a resource object named `api`
        resource_module_folders = find_resource_modules(api_source_root)

        for resource_module_folder in resource_module_folders:
            # Import the resource module
            resource_module = __import__(
                resource_module_folder["module_path"], fromlist=resource_module_folder["fromlist"]
            )
            # Get the resource object from the module and add it to the API
            self.add_resource(resource_module.api, resource_module_folder["is_public"])

        return self.resources

    def export(self):
        # Export the API as a single Lambda-compatible handler function
        def handler(event, context):
            logger.debug(f"event={event}")
            logger.debug(f"context={context}")
            resource_is_public = False
            method = None
            for resource_tuple in self.resources:
                resource = resource_tuple["resource"]
                if event["path"].startswith(resource.prefix):
                    method, params = resource.get_matching_route(event["httpMethod"], event["path"])
                    if method is not None:
                        resource_is_public = resource_tuple["is_public"]
                        break

            if method is None:
                logger.error(f"No matching route found for {event['httpMethod']} {event['path']}")
                return api_response(
                    {"error": f"Not found: {event['httpMethod']} {event['path']}"}, 404
                )

            # Check if the resource is public and if not, check that the user is authenticated
            if not resource_is_public and "authorizer" not in event["requestContext"]:
                logger.error("User is not authenticated")
                return api_response({"error": "User is not authenticated"}, 401)

            # Call the method's handler function
            return method["handler"](params, event, context)

        return handler
