from aws_lambda_powertools import Logger
from .decorators import (
    ApiResource as Resource,
    ApiError
)
from .api import ProustApi as Api
