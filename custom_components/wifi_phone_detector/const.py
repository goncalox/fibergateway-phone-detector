"""Constants for hostname-based phone presence."""
DOMAIN = "wifi_phone_detector"
NAME = "FiberGateway Phone Detector"
DEFAULT_PORT = 23
DEFAULT_INTERVAL = 45
CONF_INTERVAL = "scan_interval"
CONF_NAMES = "phone_name_keywords"
DEFAULT_NAMES = "iphone, phone, android, pixel, galaxy, oneplus, xiaomi, redmi, poco, huawei, honor, moto, oppo, realme, vivo"
STATIONS_COMMANDS = tuple(f"wireless/show-stationinfo --wifi-index={index}" for index in (0, 1))
LEASES_COMMAND = "/lan/dhcp/show"

CONF_DEPARTURE_DELAY = "departure_delay"
DEFAULT_DEPARTURE_DELAY = 120
EVENT_PHONE_ARRIVED = f"{DOMAIN}_phone_arrived"
