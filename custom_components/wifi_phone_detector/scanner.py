"""Association and hostname matching shared by both entrypoints."""
from .classifier import classify, parse_name_keywords
from .const import DEFAULT_NAMES
from .models import Detection, Snapshot
from .router import RouterError


class PhoneScanner:
    """Match configured keywords against current Wi-Fi clients."""
    def __init__(self, router, *, name_keywords: str = DEFAULT_NAMES, enabled: bool = True) -> None:
        self.router = router
        self.enabled = enabled
        self.keywords = parse_name_keywords(name_keywords)

    async def async_scan(self) -> Snapshot:
        clients = await self.router.async_fetch()
        # Losing DHCP data must not turn a previously detected phone off.
        if self.enabled and not self.router.dhcp_available:
            raise RouterError("Cannot read device names from router DHCP table")
        return Snapshot(clients, tuple(classify(client, self.keywords) if self.enabled else Detection(client, ())
                                       for client in clients))
