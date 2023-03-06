import json
import logging

from functools import wraps

from .utils import api_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ApiResource provides a resource object that provides decorators for get, post, put, and delete
# methods. The resource object also provides a route property that can be used to get the
# resource's route.
class ApiResource:
    def __init__(self, route: str):
        self.route = route
        self.methods = []

    def get(self, path: str = ''):
        return self._method_decorator('GET', path)

    def post(self, path: str = ''):
        return self._method_decorator('POST', path)

    def put(self, path: str = ''):
        return self._method_decorator('PUT', path)

    def delete(self, path: str = ''):
        return self._method_decorator('DELETE', path)

    # Path contains the path to the resource method, relative to the resource's route
    # and may include dynamic segments (e.g. `/:id`).
    def _method_decorator(self, method: str, path: str):
        def decorator(func):
            @wraps(func)
            def wrapper(params, event, context):
                if event['httpMethod'] != method:
                    return api_response({'error': f'Method not allowed for route {self.route}'}, 405)

                try:
                    data = json.loads(event['body']) if event['body'] else {}
                except json.JSONDecodeError:
                    return api_response({'error': 'Invalid JSON data provided'}, 400)

                if method in ['POST', 'PUT', 'PATCH']:
                    response = func(params, data)
                else:
                    response = func(params)

                return api_response(response)

            self.methods.append({
                'path': path,
                'full_path': self.route + path,
                'method': method,
                'handler': wrapper
            })

            return wrapper
        
        return decorator


    def get_matching_route(self, httpMethod: str, route: str):
        for method in self.methods:
            params = self._route_matcher(httpMethod, route, method)
            if params is not None:
                return method, params
        
        return None, None


    def _route_matcher(self, httpMethod, route, method):
        # If the method doesn't match, the routes don't match
        if httpMethod != method['method']:
            return None
        
        # Split the route into segments
        segments = route.split('/')

        # And same for the method's full route
        method_segments = method['full_path'].split('/')

        # If the number of segments doesn't match, the routes don't match
        if len(segments) != len(method_segments):
            return None

        # Loop through the segments and compare them
        path_params = {}
        for i in range(len(segments)):
            # If the segment is a dynamic segment, it matches
            if method_segments[i].startswith(':'):
                path_params[method_segments[i][1:]] = segments[i]
                continue

            # If the segment doesn't match, the routes don't match
            if segments[i] != method_segments[i]:
                return None

        # If we've made it this far, the routes match
        return path_params
        
