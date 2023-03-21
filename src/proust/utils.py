import os
from typing import Any, Dict

import json

def api_response(body: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'body': json.dumps(body),
        'headers': {
            'Content-Type': 'application/json'
        }
    }


def find_resource_modules(source_folder: str) -> list:
    # Look through folder structure and create a list of resource modules found.
    # Expects a folder structure like this:
    #   resources/
    #       [resource_name]/
    #           [resource_name].py which exposes a resource object named [resource_name]
    resources = []
    resources_dir = os.path.join(source_folder, 'resources')
    # Loop over folders in resources_dir and import the resource modules
    for resource_name in os.listdir(resources_dir):
        # Ignore files, only look at folders
        if not os.path.isdir(os.path.join(resources_dir, resource_name)):
            continue
        # Skip special folders
        if resource_name.startswith('.') or resource_name.startswith('__'):
            continue
        resources.append({
            'name': resource_name,
            'module_path': f'api.resources.{resource_name}.{resource_name}',
            'fromlist': [resource_name],
        })
    return resources
