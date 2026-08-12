"""
WireguardAPI class - talks to the Wireguard panel at localhost:8085
"""
import json
import logging
import aiohttp
import uuid
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

WG_PANEL_URL = "http://140.233.177.223:8085"


class WireguardAPI:
    def __init__(self, panel_url=None):
        self.panel_url = (panel_url or WG_PANEL_URL).rstrip("/")
        self.session: aiohttp.ClientSession | None = None
        from urllib.parse import urlparse
        parsed = urlparse(self.panel_url)
        self._panel_host = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            self._panel_host += f":{parsed.port}"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True)
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _normalize_short_link(self, link: str) -> str:
        """Replace localhost/127.0.0.1 in short links with the real panel host."""
        if not link:
            return link
        from urllib.parse import urlparse, urlunparse
        p = urlparse(link)
        if p.hostname in ("127.0.0.1", "localhost"):
            return urlunparse(p._replace(netloc=self._panel_host.split("://")[1]))
        return link

    async def _get(self, path: str, params: dict = None) -> dict | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15))
            body = await resp.text()
            if resp.status == 200:
                return json.loads(body)
            logger.error(f"WG GET {resp.status}: {url} -> {body[:200]}")
        except Exception as e:
            logger.error(f"WG GET error: {e}")
        return None

    async def _get_raw(self, path: str, params: dict = None) -> bytes | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15))
            if resp.status == 200:
                return await resp.read()
            logger.error(f"WG GET_RAW {resp.status}: {url}")
        except Exception as e:
            logger.error(f"WG GET_RAW error: {e}")
        return None

    async def _post(self, path: str, data: dict = None) -> dict | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.post(url, json=data or {}, timeout=aiohttp.ClientTimeout(total=15))
            body = await resp.text()
            if resp.status == 200:
                return json.loads(body)
            logger.error(f"WG POST {resp.status}: {url} -> {body[:200]}")
        except Exception as e:
            logger.error(f"WG POST error: {e}")
        return None

    async def health_check(self) -> bool:
        result = await self._get("/api/health")
        return result is not None and result.get("status") == "running"

    async def get_interfaces(self) -> list[str]:
        result = await self._get("/api/wireguard-interfaces")
        if result and "interfaces" in result:
            return result["interfaces"]
        return []

    async def get_available_ips(self, config_file: str = "wg0.conf") -> list[str]:
        """Get available IPs from the Wireguard panel.
        The panel extracts the private IP from the config file itself."""
        result = await self._get("/api/available-ips", params={"config": config_file})
        if result and "availableIps" in result:
            return result["availableIps"]
        return []

    async def create_peer(
        self,
        peer_name: str,
        data_limit_gb: float = 0,
        expiry_days: int = 0,
        config_file: str = "wg0.conf",
        dns: str = "1.1.1.1, 1.0.0.1",
        peer_ip: str = None,
        first_usage: bool = False,
        persistent_keepalive: int = 25,
        mtu: int = 1280,
    ) -> dict | None:
        """Create a new Wireguard peer and return the config link."""
        if not peer_ip:
            available = await self.get_available_ips(config_file)
            if not available:
                logger.error("No available IPs for Wireguard peer")
                return None
            peer_ip = available[0]

        if data_limit_gb > 0:
            if data_limit_gb >= 1:
                data_limit = f"{data_limit_gb:.0f}GiB"
            else:
                data_limit = f"{int(data_limit_gb * 1024)}MiB"
        else:
            data_limit = "100MiB"

        payload = {
            "peerName": peer_name,
            "peerIp": peer_ip,
            "dataLimit": data_limit,
            "configFile": config_file,
            "dns": dns,
            "expiryDays": max(expiry_days, 1),
            "expiryMonths": 0,
            "expiryHours": 0,
            "expiryMinutes": 0,
            "firstUsage": first_usage,
            "persistentKeepalive": persistent_keepalive,
            "mtu": mtu,
        }

        result = await self._post("/api/create-peer", payload)
        if result and "message" in result and "error" not in result:
            logger.info(f"Wireguard peer '{peer_name}' created at {peer_ip}: {result}")
            return {
                "peer_name": peer_name,
                "peer_ip": peer_ip,
                "short_link": self._normalize_short_link(result.get("short_link", "")),
                "message": result.get("message", ""),
            }
        logger.error(f"Wireguard peer creation failed: {result}")
        return None

    async def get_peer_details(self, peer_name: str, config_file: str = "wg0.conf") -> dict | None:
        result = await self._get("/api/obt-peer-botdetails", params={
            "peer_name": peer_name,
            "config_file": config_file,
        })
        if result and "peer_name" in result:
            return result
        return None

    async def get_client_traffic(self, email: str) -> dict | None:
        """Get traffic info for a peer by peer_name (email)."""
        details = await self.get_peer_details(email)
        if not details:
            return None
        
        total_bytes = details.get("data_limit", 0)
        used_bytes = details.get("data_used", 0)
        expiry_time = details.get("expiry_time", 0)
        
        if total_bytes and total_bytes > 0:
            remaining_bytes = max(0, total_bytes - used_bytes)
        else:
            remaining_bytes = 0
        
        return {
            "total_bytes": total_bytes,
            "total_gb": round(total_bytes / (1024 * 1024 * 1024), 2) if total_bytes > 0 else 0,
            "up_bytes": 0,
            "down_bytes": used_bytes,
            "used_bytes": used_bytes,
            "used_gb": round(used_bytes / (1024 * 1024 * 1024), 2),
            "remaining_bytes": remaining_bytes,
            "remaining_gb": round(remaining_bytes / (1024 * 1024 * 1024), 2) if total_bytes > 0 else 0,
            "expiry_time": expiry_time,
        }

    async def get_peer_link(self, peer_name: str, config_file: str = "wg0.conf") -> str | None:
        result = await self._get("/api/get-peer-link", params={
            "peerName": peer_name,
            "config": config_file,
        })
        if result and "short_link" in result:
            return self._normalize_short_link(result["short_link"])
        return None

    async def download_config(self, peer_name: str, config_file: str = "wg0.conf") -> str | None:
        """Download the raw .conf file content for a peer."""
        data = await self._get_raw("/api/download-peer-config", params={
            "peerName": peer_name,
            "config": config_file,
        })
        if data:
            return data.decode("utf-8", errors="replace")
        return None

    async def download_qr(self, peer_name: str, config_file: str = "wg0.conf") -> bytes | None:
        """Download the QR code image (PNG bytes) for a peer."""
        return await self._get_raw("/api/download-peer-qr", params={
            "peerName": peer_name,
            "config": config_file,
        })

    async def delete_peer(self, peer_name: str, config_file: str = "wg0.conf") -> bool:
        result = await self._post("/api/delete-peer", {
            "peerName": peer_name,
            "configFile": config_file,
        })
        return result is not None and result.get("success", False)

    async def reset_traffic(self, peer_name: str, config_file: str = "wg0.conf") -> bool:
        result = await self._post("/api/reset-traffic", {
            "peerName": peer_name,
            "config": config_file,
        })
        return result is not None and result.get("success", False)

    async def block_peer(self, peer_name: str, config_file: str = "wg0.conf") -> bool:
        result = await self._post("/api/block-peer", {
            "peerName": peer_name,
            "config": config_file,
        })
        return result is not None and result.get("success", False)

    async def unblock_peer(self, peer_name: str, config_file: str = "wg0.conf") -> bool:
        result = await self._post("/api/unblock-peer", {
            "peerName": peer_name,
            "config": config_file,
        })
        return result is not None and result.get("success", False)

    async def get_peers_by_interface(self, interface: str = "wg0.conf") -> list[dict]:
        result = await self._get("/api/peers-by-interface", params={"interface": interface})
        if result and "peers" in result:
            return result["peers"]
        return []


wireguard_api = WireguardAPI()
