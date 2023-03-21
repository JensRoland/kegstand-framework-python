import json
import logging
import urllib.parse

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

    def get(self, path: str = '', **kwargs):
        return self._method_decorator('GET', path, **kwargs)

    def post(self, path: str = '', **kwargs):
        return self._method_decorator('POST', path, **kwargs)

    def put(self, path: str = '', **kwargs):
        return self._method_decorator('PUT', path, **kwargs)

    def delete(self, path: str = '', **kwargs):
        return self._method_decorator('DELETE', path, **kwargs)

    # Path contains the path to the resource method, relative to the resource's route
    # and may include dynamic segments (e.g. `/:id`).
    def _method_decorator(self, method: str, path: str, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(params, event, context):
                if event['httpMethod'] != method:
                    return api_response({'error': f'Method not allowed for route {self.route}'}, 405)

                try:
                    data = json.loads(event['body']) if event['body'] else {}
                except json.JSONDecodeError:
                    return api_response({'error': 'Invalid JSON data provided'}, 400)

                try:
                    # If the arg "auth" is set to True, then we require authorization
                    if kwargs.get('auth', False):
                        if 'authorizer' not in event['requestContext']:
                            return api_response({'error': 'Unauthorized'}, 401)

                        # Call the function with the authorized user properties
                        response = self._call_func_with_arguments(
                            method,
                            func,
                            params,
                            data=data,
                            auth=event['requestContext']['authorizer']['claims']
                        )
                    else:
                        # Call the function with the correct arguments
                        response = self._call_func_with_arguments(method, func, params, data=data)

                except ApiError as e:
                    return e.to_api_response()

                return api_response(response)

            self.methods.append({
                'path': path,
                'full_path': self.route + path,
                'method': method,
                'handler': wrapper
            })

            return wrapper
        
        return decorator


    def _call_func_with_arguments(self, method, func, params, **kwargs):
        # Calls different function signatures depending on different method types
        # and whether or not auth is present:
        #   - func(params)
        #   - func(params, data)
        #   - func(params, authorized_user_properties)
        #   - func(params, data, authorized_user_properties)
        #
        # May raise ApiError
        args = [params]
        if method in ['POST', 'PUT', 'PATCH']:
            args.append(kwargs.get('data'))

        # Add authorized user properties if they were passed in
        authorized_user_properties = kwargs.get('auth', None)
        if authorized_user_properties is not None:
            args.append(authorized_user_properties)

        return func(*args)


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
        # Remove trailing slash if present (/hello/world/ -> /hello/world)
        if route.endswith('/'):
            route = route[:-1]
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
                path_params[method_segments[i][1:]] = urllib.parse.unquote(segments[i])
                continue

            # If the segment doesn't match, the routes don't match
            if segments[i] != method_segments[i]:
                return None

        # If we've made it this far, the routes match
        return path_params
        

class ApiError(Exception):
    def __init__(self, message, status_code=400):
        Exception.__init__(self)
        self.message = message
        self.status_code = status_code

    def to_dict(self):
        rv = dict()
        rv['message'] = self.message
        return rv

    def to_api_response(self):
        return api_response(self.to_dict(), self.status_code)
