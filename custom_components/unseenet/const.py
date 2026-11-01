"""Constants for the Unseenet integration."""

DOMAIN = "unseenet"

# The stats interface of a node or a council replica on Home Assistant's add-on
# network (a node's ONNTP port is 1119; its stats are one port up).
DEFAULT_PORT = 1120
SCAN_INTERVAL_SECONDS = 30

KIND_NODE = "node"
KIND_REPLICA = "replica"

CONF_KIND = "kind"
CONF_TOKEN = "token"
