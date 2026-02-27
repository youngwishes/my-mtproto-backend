import os

VDS_MAX_USERS_COUNT = int(os.getenv("VDS_MAX_USERS_COUNT", 30))
VDS_REQUEST_TIMEOUT = int(os.getenv("VDS_REQUEST_TIMEOUT", 5))
