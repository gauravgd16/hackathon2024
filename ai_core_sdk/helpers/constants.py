import os
from enum import Enum

AI_CORE_PREFIX = 'AICORE'
AUTH_ENDPOINT_SUFFIX = '/oauth/token'
DEFAULT_HOME_PATH = os.path.join(os.path.expanduser('~'), '.aicore')
HOME_PATH_ENV_VAR = f'{AI_CORE_PREFIX}_HOME'
VCAP_AICORE_SERVICE_NAME = 'aicore'
VCAP_SERVICES_ENV_VAR = 'VCAP_SERVICES'
X509_FILE_NAME_PREFIX = 'aicoresdk_x509_'


class Timeouts(Enum):
    READ_TIMEOUT = 60
    CONNECT_TIMEOUT = 60
    NUM_REQUEST_RETRIES = 3