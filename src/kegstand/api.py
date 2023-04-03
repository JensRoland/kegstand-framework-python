import logging

from .utils import (
    api_response,
    find_resource_modules,
)
from . import Logger

logger = Logger()

# Class KegstandApi provides a container for API resources and a method to add
# resources to the API.
class KegstandApi:
    def __init__(self):
        self.resources = []


    def add_resource(self, resource):
        # Resource is a ApiResource object
        self.resources.append(resource)


    def find_and_add_resources(self, source_root: str):
        # Look through folder structure, importing and adding resources to the API.
        # Expects a folder structure like this:
        # api/
        #   resources/
        #       [resource_name]/
        #           any.py which exposes a resource object named `api`
        resource_module_folders = find_resource_modules(source_root)
        for resource_module_folder in resource_module_folders:
            # Import the resource module
            resource_module = __import__(resource_module_folder['module_path'], fromlist=resource_module_folder['fromlist'])
            # Get the resource object from the module and add it to the API
            self.add_resource(getattr(resource_module, 'api'))

        return self.resources


    def export(self):
        # Export the API as a single Lambda-compatible handler function
        def handler(event, context):
            method = None
            for resource in self.resources:
                if event['path'].startswith(resource.route):
                    method, params = resource.get_matching_route(event['httpMethod'], event['path'])
                    if method is not None:
                        break

            # method = next(
            #     (resource.get_matching_route(event['path']) for resource in self.resources), None
            # )

            if method is None:
                return api_response({'error': 'Not found'}, 404)

            # Call the method's handler function
            return method['handler'](params, event, context)

        return handler
