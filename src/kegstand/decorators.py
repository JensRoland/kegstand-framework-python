import inspect
import json
from functools import wraps
from typing import Any
from urllib.parse import unquote_plus

from . import Logger
from .utils import api_response

logger = Logger()


# ApiResource provides a resource object that provides decorators for get, post, put, and delete
# methods. The resource object also provides a prefix property that can be used to get the
# resource's base prefix.
class ApiResource:
    def __init__(self, prefix: str, method_defaults: dict | None = None):
        self.prefix = prefix
        self.methods: list[dict[str, Any]] = []
        self.method_defaults = method_defaults or {}

    def get(self, route: str = "/", **kwargs):
        return self._method_decorator("GET", route, **{**self.method_defaults, **kwargs})

    def post(self, route: str = "/", **kwargs):
        return self._method_decorator("POST", route, **{**self.method_defaults, **kwargs})

    def put(self, route: str = "/", **kwargs):
        return self._method_decorator("PUT", route, **{**self.method_defaults, **kwargs})

    def delete(self, route: str = "/", **kwargs):
        return self._method_decorator("DELETE", route, **{**self.method_defaults, **kwargs})

    # Route contains the path to the resource method, relative to the resource's prefix
    # and may include dynamic segments (e.g. `/:id`).
    def _method_decorator(self, method: str, route: str, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(params, event, _context):
                if event["httpMethod"] != method:
                    return api_response(
                        {"error": f"Method not allowed for prefix {self.prefix}"}, 405
                    )

                try:
                    data = json.loads(event["body"]) if event["body"] else {}
                except json.JSONDecodeError:
                    return api_response({"error": "Invalid JSON data provided"}, 400)

                try:
                    # Authorization
                    # Defaults to checking for a valid requestContext
                    auth_conditions = kwargs.get("auth", Auth())
                    if not isinstance(auth_conditions, list):
                        auth_conditions = [auth_conditions]

                    # Validate each auth condition
                    for auth_condition in auth_conditions:
                        if not auth_condition.evaluate(event):
                            return api_response({"error": "Unauthorized"}, 401)

                    # If the func has a "claims" argument, then we have to pass
                    # in the authorized user properties (claims) from the authorizer
                    claims = None
                    if "claims" in inspect.signature(func).parameters:
                        if (
                            "authorizer" not in event["requestContext"]
                            or "claims" not in event["requestContext"]["authorizer"]
                        ):
                            return api_response(
                                {"error": "Unauthorized (missing authorizer context)"}, 401
                            )
                        claims = event["requestContext"]["authorizer"]["claims"]

                    # Other injected arguments
                    # If the func has a "query" argument, then we have to pass
                    # in the query string parameters from the event
                    query = None
                    if "query" in inspect.signature(func).parameters:
                        query = event["queryStringParameters"] or {}

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

            # Read auth configuration and add it to the method config object
            auth_conditions = kwargs.get("auth", Auth())
            if not isinstance(auth_conditions, list):
                auth_conditions = [auth_conditions]

            self.methods.append(
                {
                    "route": route,
                    "full_route": self.prefix + route,
                    "method": method,
                    "handler": wrapper,
                    "auth": auth_conditions,
                }
            )

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
        if method in ["POST", "PUT", "PATCH"]:
            func_kwargs["data"] = kwargs.get("data", {})

        # Add querystring parameters if a "query" parameter was passed in
        query = kwargs.get("query")
        if query is not None:
            func_kwargs["query"] = query

        # Add authorized user properties (claims) if a "claims" parameter was passed in
        claims = kwargs.get("claims")
        if claims is not None:
            func_kwargs["claims"] = claims

        return func(**func_kwargs)

    def get_matching_route(self, httpmethod: str, request_uri: str):
        for method in self.methods:
            params = self._route_matcher(httpmethod, request_uri, method)
            if params is not None:
                return method, params

        return None, None

    def _route_matcher(self, httpmethod, request_uri, method):
        # If the method doesn't match, the routes don't match
        if httpmethod != method["method"]:
            return None

        # Split the request_uri into segments
        # Remove trailing slash if present (/hello/world/ -> /hello/world)
        if request_uri.endswith("/"):
            request_uri = request_uri[:-1]
        segments = request_uri.split("/")

        # And same for the method's full route
        method_route = method["full_route"]
        if method_route.endswith("/"):
            method_route = method_route[:-1]
        method_segments = method_route.split("/")

        # If the number of segments doesn't match, the routes don't match
        if len(segments) != len(method_segments):
            return None

        # Loop through the segments and compare them
        route_params = {}
        for i in range(len(segments)):
            # If the segment is a dynamic segment, it matches
            if method_segments[i].startswith(":"):
                route_params[method_segments[i][1:]] = unquote_plus(segments[i])
                continue

            # If the segment doesn't match, the routes don't match
            if segments[i] != method_segments[i]:
                return None

        # If we've made it this far, the routes match
        return route_params


class Auth:
    def __init__(self):
        self.conditions = []

    def _claim(self, claim):
        self.current_claim = claim
        return self

    def eq(self, value, case_sensitive=True):
        if not case_sensitive:
            self.conditions.append(
                lambda claims: claims.get(self.current_claim).lower() == value.lower()
            )
        else:
            self.conditions.append(lambda claims: claims.get(self.current_claim) == value)

        return self

    def contains(self, value, case_sensitive=True):
        if not case_sensitive:
            self.conditions.append(
                lambda claims: value.lower()
                in [
                    claim_list_item.lower()
                    for claim_list_item in claims.get(self.current_claim, [])
                ]
            )
        else:
            self.conditions.append(lambda claims: value in claims.get(self.current_claim, []))
        return self

    def gt(self, value):
        self.conditions.append(lambda claims: claims.get(self.current_claim, None) > value)
        return self

    def gte(self, value):
        self.conditions.append(lambda claims: claims.get(self.current_claim, None) >= value)
        return self

    def lt(self, value):
        self.conditions.append(lambda claims: claims.get(self.current_claim, None) < value)
        return self

    def lte(self, value):
        self.conditions.append(lambda claims: claims.get(self.current_claim, None) <= value)
        return self

    def in_collection(self, collection):
        self.conditions.append(lambda claims: claims.get(self.current_claim, None) in collection)
        return self

    def not_in_collection(self, collection):
        self.conditions.append(
            lambda claims: claims.get(self.current_claim, None) not in collection
        )
        return self

    def evaluate(self, event):
        if len(self.conditions) == 0:
            return True

        if (
            "authorizer" not in event["requestContext"]
            or "claims" not in event["requestContext"]["authorizer"]
        ):
            return False
        claims = event["requestContext"]["authorizer"]["claims"]
        return all(condition(claims) for condition in self.conditions)


def claim(claim_key):
    instance = Auth()
    return instance._claim(claim_key)


class ApiError(Exception):
    def __init__(self, error_message, status_code: int = 400):
        Exception.__init__(self)
        self.error_message = error_message
        self.status_code = status_code
        logger.warning(f"API Error (status {status_code}): {error_message}")

    def to_dict(self):
        return {"error": self.error_message}

    def to_api_response(self):
        return api_response(self.to_dict(), self.status_code)
