import json

from kegstand.decorators import ApiError, ApiResource, Auth, claim


def test_api_resource_initialization():
    resource = ApiResource("/test")
    assert resource.prefix == "/test"
    assert resource.methods == []
    assert resource.method_defaults == {}


def test_api_resource_with_defaults():
    defaults = {"auth": Auth()}
    resource = ApiResource("/test", method_defaults=defaults)
    assert resource.method_defaults == defaults


def test_route_decorators():
    resource = ApiResource("/test")

    @resource.get("/get")
    def get_handler():
        pass

    @resource.post("/post")
    def post_handler():
        pass

    @resource.put("/put")
    def put_handler():
        pass

    @resource.delete("/delete")
    def delete_handler():
        pass

    assert len(resource.methods) == 4

    methods = {m["method"]: m for m in resource.methods}
    assert "GET" in methods
    assert "POST" in methods
    assert "PUT" in methods
    assert "DELETE" in methods

    assert methods["GET"]["route"] == "/get"
    assert methods["POST"]["route"] == "/post"
    assert methods["PUT"]["route"] == "/put"
    assert methods["DELETE"]["route"] == "/delete"


def test_route_matching():
    resource = ApiResource("/api")

    @resource.get("/users/:id")
    def get_user():
        pass

    method, params = resource.get_matching_route("GET", "/api/users/123")
    assert method is not None
    assert params == {"id": "123"}

    # Test non-matching route
    method, params = resource.get_matching_route("GET", "/api/posts/123")
    assert method is None
    assert params is None


def test_route_matching_with_multiple_params():
    resource = ApiResource("/api")

    @resource.get("/users/:user_id/posts/:post_id")
    def get_user_post():
        pass

    method, params = resource.get_matching_route("GET", "/api/users/123/posts/456")
    assert method is not None
    assert params == {"user_id": "123", "post_id": "456"}


def test_route_matching_with_encoded_params():
    resource = ApiResource("/api")

    @resource.get("/users/:name")
    def get_user_by_name():
        pass

    method, params = resource.get_matching_route("GET", "/api/users/John%20Doe")
    assert method is not None
    assert params == {"name": "John Doe"}


def test_auth_basic():
    auth = Auth()
    event = {"requestContext": {"authorizer": {"claims": {"role": "admin"}}}}

    # Test with no conditions
    assert auth.evaluate(event) is True

    # Test with missing authorizer
    assert auth.evaluate({"requestContext": {}}) is True


def test_auth_claim_eq():
    auth = claim("role").eq("admin")

    # Test matching claim
    event = {"requestContext": {"authorizer": {"claims": {"role": "admin"}}}}
    assert auth.evaluate(event) is True

    # Test non-matching claim
    event = {"requestContext": {"authorizer": {"claims": {"role": "user"}}}}
    assert auth.evaluate(event) is False


def test_auth_claim_contains():
    auth = claim("groups").contains("admins")

    # Test matching claim
    event = {"requestContext": {"authorizer": {"claims": {"groups": ["users", "admins"]}}}}
    assert auth.evaluate(event) is True

    # Test non-matching claim
    event = {"requestContext": {"authorizer": {"claims": {"groups": ["users"]}}}}
    assert auth.evaluate(event) is False


def test_auth_claim_comparison():
    auth = claim("age").gte(18)

    # Test valid age
    event = {"requestContext": {"authorizer": {"claims": {"age": 21}}}}
    assert auth.evaluate(event) is True

    # Test invalid age
    event = {"requestContext": {"authorizer": {"claims": {"age": 16}}}}
    assert auth.evaluate(event) is False


def test_auth_claim_collection():
    auth = claim("role").in_collection(["admin", "moderator"])

    # Test role in collection
    event = {"requestContext": {"authorizer": {"claims": {"role": "admin"}}}}
    assert auth.evaluate(event) is True

    # Test role not in collection
    event = {"requestContext": {"authorizer": {"claims": {"role": "user"}}}}
    assert auth.evaluate(event) is False


def test_api_error():
    error = ApiError("Invalid input", 400)

    # Test error to dict
    error_dict = error.to_dict()
    assert error_dict == {"error": "Invalid input"}

    # Test error to API response
    response = error.to_api_response()
    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Invalid input"}


def test_route_handler_with_claims():
    resource = ApiResource("/api")

    @resource.get("/protected")
    def protected_route(claims):
        return {"user": claims["sub"]}

    # Create event with claims
    event = {
        "httpMethod": "GET",
        "path": "/api/protected",
        "body": None,
        "requestContext": {"authorizer": {"claims": {"sub": "user123"}}},
    }

    # Get the route and execute handler
    method, params = resource.get_matching_route("GET", "/api/protected")
    assert method is not None

    response = method["handler"](params, event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"user": "user123"}


def test_route_handler_with_query_params():
    resource = ApiResource("/api")

    @resource.get("/search")
    def search(query):
        return {"query": query}

    # Create event with query parameters
    event = {
        "httpMethod": "GET",
        "path": "/api/search",
        "body": None,
        "queryStringParameters": {"q": "test", "page": "1"},
        "requestContext": {},
    }

    # Get the route and execute handler
    method, params = resource.get_matching_route("GET", "/api/search")
    assert method is not None

    response = method["handler"](params, event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"query": {"q": "test", "page": "1"}}
