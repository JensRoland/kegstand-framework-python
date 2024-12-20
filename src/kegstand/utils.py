import json
import os
from typing import Any, Dict


def api_response(body: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
        "headers": {"Content-Type": "application/json"},
    }


def find_resource_modules(api_src_dir: str) -> list:
    # Look through folder structure and create a list of resource modules found.
    # Expects a folder structure like this:
    #   api/
    #       [resource_name].py which exposes a resource object named `api`
    #   api/public/
    #       [resource_name].py which exposes a resource object named `api`
    resources = []

    api_folders: list[dict[str, str | bool]] = [
        {"name": "api", "resources_are_public": False},
        {"name": "api/public", "resources_are_public": True},
    ]

    # Loop over folders in api_src_dir and list the resource modules
    for api_folder in api_folders:
        api_folder_full = os.path.join(api_src_dir, str(api_folder["name"]))
        if not os.path.isdir(api_folder_full):
            continue

        for file_descriptor in os.listdir(api_folder_full):
            # Ignore folders, only look at files
            if os.path.isdir(os.path.join(api_folder_full, file_descriptor)):
                continue
            # Skip dotfiles and special files
            if file_descriptor.startswith((".", "__")) or file_descriptor == "lambda.py":
                continue
            resource_name = os.path.splitext(file_descriptor)[0]
            resources.append(
                {
                    "name": resource_name,
                    "module_path": f"{str(api_folder['name']).replace('/', '.')}.{resource_name}",
                    "fromlist": [resource_name],
                    "is_public": api_folder["resources_are_public"],
                }
            )
    return resources
