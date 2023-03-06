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
