from unittest.mock import MagicMock, patch

from kegstand.api import RestApi
from kegstand.decorators import ApiResource


def test_rest_api_initialization():
    api = RestApi()
    assert api.resources == []


def test_add_resource():
    api = RestApi()
    resource = ApiResource("/test")

    api.add_resource(resource)
    assert len(api.resources) == 1
    assert api.resources[0]["resource"] == resource
    assert api.resources[0]["is_public"] is False


def test_add_public_resource():
    api = RestApi()
    resource = ApiResource("/test")

    api.add_resource(resource, is_public=True)
    assert len(api.resources) == 1
    assert api.resources[0]["resource"] == resource
    assert api.resources[0]["is_public"] is True


@patch("kegstand.api.find_resource_modules")
def test_find_and_add_resources(mock_find_resources):
    # Mock resource modules
    mock_find_resources.return_value = [
        {"module_path": "api.users", "fromlist": ["users"], "is_public": False},
        {"module_path": "api.public.health", "fromlist": ["health"], "is_public": True},
    ]

    # Create mock modules
    mock_users_api = ApiResource("/users")
    mock_health_api = ApiResource("/health")

    # Mock __import__ to return our mock modules
    def mock_import(name, *args, **kwargs):  # noqa: ARG001
        mock = MagicMock()
        if name == "api.users":
            mock.api = mock_users_api
        elif name == "api.public.health":
            mock.api = mock_health_api
        return mock

    with patch("builtins.__import__", side_effect=mock_import):
        api = RestApi()
        resources = api.find_and_add_resources("/mock/path")

        assert len(resources) == 2
        assert resources[0]["resource"] == mock_users_api
        assert not resources[0]["is_public"]
        assert resources[1]["resource"] == mock_health_api
        assert resources[1]["is_public"]


def test_export_handler():
    api = RestApi()
    resource = ApiResource("/test")

    # Add a test route
    @resource.get("/:id")
    def get_test(params):
        return {"id": params["id"]}

    api.add_resource(resource)

    # Create the handler
    handler = api.export()

    # Test successful request
    event = {
        "httpMethod": "GET",
        "path": "/test/123",
        "body": None,
        "requestContext": {"authorizer": {"claims": {}}},
    }

    response = handler(event, {})
    assert response["statusCode"] == 200
    assert "id" in response["body"]


def test_export_handler_not_found():
    api = RestApi()
    resource = ApiResource("/test")
    api.add_resource(resource)

    handler = api.export()

    # Test non-existent route
    event = {"httpMethod": "GET", "path": "/nonexistent", "body": None, "requestContext": {}}

    response = handler(event, {})
    assert response["statusCode"] == 404


def test_export_handler_unauthorized():
    api = RestApi()
    resource = ApiResource("/test")

    @resource.get("/")
    def get_test():
        return {"message": "success"}

    # Add as non-public resource
    api.add_resource(resource, is_public=False)

    handler = api.export()

    # Test request without authorization
    event = {
        "httpMethod": "GET",
        "path": "/test",
        "body": None,
        "requestContext": {},  # No authorizer
    }

    response = handler(event, {})
    assert response["statusCode"] == 401


def test_export_handler_with_body():
    api = RestApi()
    resource = ApiResource("/test")

    @resource.post("/")
    def post_test(data):
        return {"received": data}

    api.add_resource(resource, is_public=True)
    handler = api.export()

    # Test POST request with body
    event = {
        "httpMethod": "POST",
        "path": "/test",
        "body": '{"key": "value"}',
        "requestContext": {},
    }

    response = handler(event, {})
    assert response["statusCode"] == 200
    assert '"key": "value"' in response["body"]


def test_export_handler_invalid_json():
    api = RestApi()
    resource = ApiResource("/test")

    @resource.post("/")
    def post_test(data):
        return {"received": data}

    api.add_resource(resource, is_public=True)
    handler = api.export()

    # Test POST request with invalid JSON body
    event = {"httpMethod": "POST", "path": "/test", "body": "invalid json", "requestContext": {}}

    response = handler(event, {})
    assert response["statusCode"] == 400
    assert "Invalid JSON" in response["body"]
