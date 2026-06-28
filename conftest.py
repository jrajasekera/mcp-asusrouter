import os

# Allow importing server.py (RouterSettings validates ROUTER_* at import time)
# without real credentials. list_tools / pure helpers never connect.
os.environ.setdefault("ROUTER_HOSTNAME", "test.local")
os.environ.setdefault("ROUTER_PASSWORD", "testpass")
