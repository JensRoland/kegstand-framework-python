import logging

from .utils import api_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Class ProustApi provides a container for API resources and a method to add
# resources to the API.
class ProustApi:
    def __init__(self):
        self.resources = []


    def add_resource(self, resource):
        # Resource is a ApiResource object
        self.resources.append(resource)


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
