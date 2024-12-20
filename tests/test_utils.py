import json
import os
import tempfile

from kegstand.utils import api_response, find_resource_modules


def test_api_response_default_status():
    body = {"message": "success"}
    response = api_response(body)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == body
    assert response["headers"]["Content-Type"] == "application/json"


def test_api_response_custom_status():
    body = {"error": "not found"}
    response = api_response(body, status_code=404)

    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == body
    assert response["headers"]["Content-Type"] == "application/json"


def test_find_resource_modules():
    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create api directory
        api_dir = os.path.join(temp_dir, "api")
        os.makedirs(api_dir)

        # Create api/public directory
        public_dir = os.path.join(api_dir, "public")
        os.makedirs(public_dir)

        # Create test files
        test_files = {
            os.path.join(api_dir, "users.py"): False,
            os.path.join(api_dir, "posts.py"): False,
            os.path.join(public_dir, "health.py"): True,
        }

        # Create the test files
        for file_path, _ in test_files.items():
            with open(file_path, "w") as f:
                f.write("# Test resource file")

        # Add some files that should be ignored
        with open(os.path.join(api_dir, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(api_dir, ".hidden.py"), "w") as f:
            f.write("")
        with open(os.path.join(api_dir, "lambda.py"), "w") as f:
            f.write("")

        # Test the function
        resources = find_resource_modules(temp_dir)

        # Verify results
        assert len(resources) == 3

        # Check each resource
        for resource in resources:
            assert "name" in resource
            assert "module_path" in resource
            assert "fromlist" in resource
            assert "is_public" in resource

            # Verify the module path format
            if resource["is_public"]:
                assert resource["module_path"].startswith("api.public.")
            else:
                assert resource["module_path"].startswith("api.")
                assert "public" not in resource["module_path"]

            # Verify the name matches the file name
            assert resource["name"] in ["users", "posts", "health"]

            # Verify public/private status
            if resource["name"] == "health":
                assert resource["is_public"] is True
            else:
                assert resource["is_public"] is False


def test_find_resource_modules_empty_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        resources = find_resource_modules(temp_dir)
        assert resources == []


def test_find_resource_modules_no_api_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create an empty directory without api folder
        resources = find_resource_modules(temp_dir)
        assert resources == []
