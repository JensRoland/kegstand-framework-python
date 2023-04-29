import os

from .utils import (
    api_response,
    find_resource_modules,
)
from . import Logger

logger = Logger()

# Class RestApi provides a container for API resources and a method to add
# resources to the API.
class RestApi:
    def __init__(self, root: str = None):
        self.resources = []
        if root is not None:
            source_path = os.path.dirname(os.path.abspath(root))
            logger.info(f'Adding resources from {root} : source_path={source_path}')
            self.find_and_add_resources(source_path)


    def add_resource(self, resource):
        # Resource is a ApiResource object
        self.resources.append(resource)


    def find_and_add_resources(self, api_source_root: str):
        # Look through folder structure, importing and adding resources to the API.
        # Expects a folder structure like this:
        # api/
        #   [resource_name].py which exposes a resource object named `api`
        resource_module_folders = find_resource_modules(api_source_root)
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
                if event['path'].startswith(resource.prefix):
                    method, params = resource.get_matching_route(event['httpMethod'], event['path'])
                    if method is not None:
                        break

            if method is None:
                return api_response({'error': 'Not found'}, 404)

            # Call the method's handler function
            return method['handler'](params, event, context)

        return handler
