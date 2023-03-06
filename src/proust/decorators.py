from functools import wraps
from typing import Any, Dict

import json

"""
This code provides the following decorators:

1. api_route, which can be used to decorate a function that defines an API endpoint.

The api_route decorator checks the HTTP method of the incoming request against the
list of allowed methods, deserializes the request body as JSON, calls the decorated
function with the deserialized body data, and returns the response as an API Gateway-
compatible response object.
"""

def api_route(route: str, methods: list):
    def decorator(func):
        @wraps(func)
        def wrapper(event, context):
            if event['httpMethod'] not in methods:
                return api_response({'error': f'Method not allowed for route {route}'}, 405)

            try:
                data = json.loads(event['body']) if event['body'] else {}
            except json.JSONDecodeError:
                return api_response({'error': 'Invalid JSON data provided'}, 400)

            response = func(data)

            return api_response(response)

        return wrapper

    return decorator


def api_response(body: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'body': json.dumps(body),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
