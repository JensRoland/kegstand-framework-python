import inspect
import json

from functools import wraps
from urllib.parse import unquote_plus

from .utils import api_response
from . import Logger

logger = Logger()

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
                    if kwargs.get('auth', False):
                        auth_conditions = kwargs.get("auth")
                        if not auth_conditions.evaluate(event):
                            return api_response({'error': 'Unauthorized'}, 401)
                    
                    # If the func has a 'query' parameter, then we have to pass
                    # in the query string parameters from the event
                    query = None
                    if 'query' in inspect.signature(func).parameters:
                        query = event['queryStringParameters'] or {}

                    # If the func has a 'claims' parameter, then we have to pass
                    # in the authorized user properties (claims) from the authorizer
                    claims = None
                    if 'claims' in inspect.signature(func).parameters:
                        if 'authorizer' not in event['requestContext']:
                            return api_response({'error': 'Unauthorized (missing authorizer context)'}, 401)
                        claims = event['requestContext']['authorizer']['claims']

                    # Call the function with the authorized user properties
                    response = self._call_func_with_arguments(
                        method,
                        func,
                        params,
                        query=query,
                        data=data,
                        claims=claims,
                    )

                except ApiError as e:
                    return e.to_api_response()

                return api_response(response, 200)

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
        # and whether or not claims are present:
        #   - func()
        #   - func(params=params)
        #   - func(query=query)
        #   - func(params=params, query=query)
        #   - func(params=params, data=data)
        #   - func(params=params, claims=claims)
        #   - func(params=params, query=query, data=data, claims=claims)
        #   - etc.
        #
        # May raise ApiError
        func_kwargs = {}
        if len(params) > 0:
            func_kwargs["params"] = params
        if method in ['POST', 'PUT', 'PATCH']:
            func_kwargs["data"] = kwargs.get('data', {})

        # Add querystring parameters if a 'query' parameter was passed in
        query = kwargs.get('query', None)
        if query is not None:
            func_kwargs["query"] = query

        # Add authorized user properties (claims) if a 'claims' parameter was passed in
        claims = kwargs.get('claims', None)
        if claims is not None:
            func_kwargs["claims"] = claims

        return func(**func_kwargs)


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
                path_params[method_segments[i][1:]] = unquote_plus(segments[i])
                continue

            # If the segment doesn't match, the routes don't match
            if segments[i] != method_segments[i]:
                return None

        # If we've made it this far, the routes match
        return path_params


class Auth:
    def __init__(self):
        self.conditions = []

    @classmethod
    def require(cls, claim):
        instance = cls()
        return instance._claim(claim)

    def _claim(self, claim):
        self.current_claim = claim
        return self

    def to_be(self, value):
        self.conditions.append(lambda claims: claims.get(self.current_claim) == value)
        return self

    def gt(self, value):
        self.conditions.append(lambda claims: int(claims.get(self.current_claim, 0)) > value)
        return self

    def and_(self, claim):
        return self._claim(claim)

    def evaluate(self, event):
        if 'authorizer' not in event['requestContext']:
            return False
        claims = event['requestContext']['authorizer']['claims']
        for condition in self.conditions:
            if not condition(claims):
                return False
        return True


class ApiError(Exception):
    def __init__(self, error_message, status_code: int = 400):
        Exception.__init__(self)
        self.error_message = error_message
        self.status_code = status_code
        logger.warning(f"API Error (status {status_code}): {error_message}")

    def to_dict(self):
        rv = dict()
        rv['error'] = self.error_message
        return rv

    def to_api_response(self):
        return api_response(self.to_dict(), self.status_code)
