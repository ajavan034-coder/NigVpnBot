import uuid
import json
import re
import logging
import aiohttp
from urllib.parse import urlencode
from datetime import datetime, timedelta
import web_db

logger = logging.getLogger(__name__)


class PanelAPI:
    def __init__(self):
        self.panel_url = ""
        self.panel_user = ""
        self.panel_pass = ""
        self.sub_link_template = ""
        self.inbound_ids = []
        self.base_path = ""
        self.session: aiohttp.ClientSession | None = None
        self.csrf_token: str = ""
        try:
            self.reload_config()
        except Exception:
            pass

    def reload_config(self):
        self.panel_url = (web_db.get_setting("panel_url") or "").rstrip("/")
        self.panel_user = web_db.get_setting("panel_user") or ""
        self.panel_pass = web_db.get_setting("panel_pass") or ""
        self.sub_link_template = web_db.get_setting("sub_link_template") or ""
        raw = web_db.get_setting("inbound_id") or ""
        self.inbound_ids = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        self.base_path = ""
        self._extract_base_path()

    def _extract_base_path(self):
        match = re.search(r"https?://[^/]+(/.+)", self.panel_url)
        if match:
            self.base_path = match.group(1).rstrip("/")
        else:
            self.base_path = ""

    @property
    def base_url(self):
        return self.panel_url

    @property
    def api_url(self):
        return f"{self.panel_url}{self.base_path}/panel/api"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True)
            )
        return self.session

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-Token": self.csrf_token,
        }

    def _json_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-Token": self.csrf_token,
        }

    async def login(self) -> bool:
        session = await self._get_session()
        try:
            await session.get(
                self.panel_url,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=10),
            )

            async with session.get(
                f"{self.panel_url}/csrf-token",
                headers={"X-Requested-With": "XMLHttpRequest"},
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.csrf_token = data.get("obj", "")

            async with session.post(
                f"{self.panel_url}/login",
                data=urlencode({"username": self.panel_user, "password": self.panel_pass}),
                headers=self._headers(),
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        return True
        except Exception as e:
            logger.error(f"Panel login error: {e}")
        return False

    async def _get(self, path: str) -> dict | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.get(url, headers=self._json_headers(), ssl=False, timeout=aiohttp.ClientTimeout(total=15))
            if resp.status == 200:
                data = await resp.json()
                await resp.release()
                return data
            await resp.release()
            if resp.status in (401, 403):
                if await self.login():
                    resp2 = await session.get(url, headers=self._json_headers(), ssl=False, timeout=aiohttp.ClientTimeout(total=15))
                    data2 = await resp2.json()
                    await resp2.release()
                    if resp2.status == 200:
                        return data2
        except Exception as e:
            logger.error(f"Panel GET error: {e}")
        return None

    async def _post(self, path: str, data: dict | None = None, use_json: bool = True) -> dict | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            kwargs = {"ssl": False, "timeout": aiohttp.ClientTimeout(total=15)}
            if use_json:
                kwargs["json"] = data or {}
                kwargs["headers"] = self._json_headers()
            else:
                kwargs["data"] = urlencode(data or {})
                kwargs["headers"] = self._headers()

            resp = await session.post(url, **kwargs)
            body = await resp.text()
            if resp.status == 200:
                await resp.release()
                return json.loads(body)
            elif resp.status in (401, 403):
                await resp.release()
                if await self.login():
                    if use_json:
                        kwargs["headers"] = self._json_headers()
                    else:
                        kwargs["headers"] = self._headers()
                    resp2 = await session.post(url, **kwargs)
                    body2 = await resp2.text()
                    if resp2.status == 200:
                        await resp2.release()
                        return json.loads(body2)
                    else:
                        logger.error(f"Panel POST retry {resp2.status}: {body2[:200]}")
                    await resp2.release()
                else:
                    logger.error("Panel login failed during retry")
            else:
                logger.error(f"Panel POST {resp.status}: {url} -> {body[:200]}")
            await resp.release()
        except Exception as e:
            logger.error(f"Panel POST error: {e}")
        return None

    async def get_inbounds(self) -> list:
        data = await self._get("/panel/api/inbounds/list")
        if data and data.get("success"):
            return data.get("obj", [])
        return []

    async def get_inbound(self, inbound_id: int) -> dict | None:
        data = await self._get(f"/panel/api/inbounds/get/{inbound_id}")
        if data and data.get("success"):
            return data.get("obj")
        return None

    async def get_vless_inbound_id(self) -> int | None:
        inbounds = await self.get_inbounds()
        for inbound in inbounds:
            if inbound.get("protocol") == "vless" and inbound.get("enable"):
                return inbound.get("id")
        return None

    async def add_client(self, inbound_ids: list[int], email: str, total_gb: float = 0, days: int = 0) -> dict | None:
        user_uuid = str(uuid.uuid4())
        sub_id = uuid.uuid4().hex[:16]

        total_bytes = int(total_gb * 1024 * 1024 * 1024) if total_gb > 0 else 0
        expiry_time = 0
        if days > 0:
            expiry_time = int((datetime.utcnow() + timedelta(days=days)).timestamp() * 1000)

        success_count = 0
        for inbound_id in inbound_ids:
            client_payload = {
                "client": {
                    "email": email,
                    "subId": sub_id,
                    "id": user_uuid,
                    "password": "",
                    "auth": "",
                    "flow": "",
                    "security": "auto",
                    "totalGB": total_bytes,
                    "expiryTime": expiry_time,
                    "reset": 0,
                    "limitIp": 0,
                    "tgId": 0,
                    "group": "",
                    "comment": "",
                    "enable": True,
                },
                "inboundIds": [inbound_id],
            }

            logger.info(f"Adding client '{email}' to inbound {inbound_id}...")
            result = await self._post("/panel/api/clients/add", client_payload)
            logger.info(f"Result: {result}")
            if result and result.get("success"):
                success_count += 1
            else:
                logger.error(f"Failed to add client to inbound {inbound_id}: {result}")

        if success_count > 0:
            return {"uuid": user_uuid, "sub_id": sub_id, "email": email}
        return None

    def get_sub_link(self, email: str, sub_id: str) -> str:
        if self.sub_link_template:
            return self.sub_link_template.replace("{sub_id}", sub_id).replace("{id}", sub_id)
        import re
        match = re.search(r"https?://([^:/]+)", self.panel_url)
        host = match.group(1) if match else "localhost"
        return f"https://{host}:2096/sub/{sub_id}"

    async def create_config(self, email: str, days: int = 30, total_gb: int = 0, inbound_ids: list[int] | None = None) -> dict | None:
        if inbound_ids is None:
            inbound_ids = self.inbound_ids if self.inbound_ids else []
        if not inbound_ids:
            vid = await self.get_vless_inbound_id()
            if vid is not None:
                inbound_ids = [vid]

        if not inbound_ids:
            logger.error("No inbounds configured")
            return None

        result = await self.add_client(inbound_ids, email, total_gb=total_gb, days=days)
        if result:
            sub_link = self.get_sub_link(email, result["sub_id"])
            expire_date = (datetime.utcnow() + timedelta(days=days)).isoformat()
            return {
                "uuid": result["uuid"],
                "email": result["email"],
                "sub_link": sub_link,
                "expire_date": expire_date,
            }

        logger.error("Failed to add client to panel")
        return None

    async def create_test_config(self, email: str, total_mb: int = 102400) -> dict | None:
        inbound_ids = self.inbound_ids if self.inbound_ids else []
        if not inbound_ids:
            vid = await self.get_vless_inbound_id()
            if vid is not None:
                inbound_ids = [vid]

        if not inbound_ids:
            logger.error("No inbounds configured")
            return None

        total_gb = total_mb / 1024
        result = await self.add_client(inbound_ids, email, total_gb=total_gb, days=1)
        if result:
            sub_link = self.get_sub_link(email, result["sub_id"])
            expire_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
            return {
                "uuid": result["uuid"],
                "email": result["email"],
                "sub_link": sub_link,
                "expire_date": expire_date,
            }

        logger.error("Failed to add test client to panel")
        return None

    async def get_client_configs(self, email: str) -> list:
        inbounds = await self.get_inbounds()
        configs = []
        target_inbound_ids = set(self.inbound_ids) if self.inbound_ids else None
        for inbound in inbounds:
            inbound_id = inbound.get("id")
            if target_inbound_ids and inbound_id not in target_inbound_ids:
                continue
            clients = inbound.get("settings", {}).get("clients", [])
            stream = inbound.get("streamSettings", {})
            external_proxies = stream.get("externalProxy", [])

            for client in clients:
                if client.get("email") == email:
                    uuid = client.get("id", "")
                    tag = inbound.get("tag", "")
                    protocol = inbound.get("protocol", "")
                    net = stream.get("network", "tcp")
                    security = stream.get("security", "none")
                    sni = ""
                    ws_host = ""
                    path = "/"

                    if security == "tls":
                        tls_settings = stream.get("tlsSettings", {})
                        sni_list = tls_settings.get("serverName", [])
                        if sni_list:
                            sni = sni_list[0] if isinstance(sni_list, list) else sni_list
                    elif security == "reality":
                        reality = stream.get("realitySettings", {})
                        sni = reality.get("serverNames", [""])[0] if reality.get("serverNames") else ""

                    if net == "ws":
                        ws = stream.get("wsSettings", {})
                        ws_host = ws.get("host", "") or ws.get("headers", {}).get("Host", "")
                        path = ws.get("path", "/")
                    elif net == "grpc":
                        grpc = stream.get("grpcSettings", {})
                        path = grpc.get("serviceName", "/")

                    total_gb = client.get("totalGB", 0)
                    gb_display = f"{total_gb / (1024*1024*1024):.2f}GB" if total_gb > 0 else "Unlimited"
                    tag_text = f"{tag}@{email}-{gb_display}"

                    # Build server list: external proxies + default host
                    server_list = []
                    for proxy in external_proxies:
                        server_list.append({
                            "host": proxy.get("dest", ""),
                            "port": proxy.get("port", 80),
                        })
                    # Add default host if no proxies or as fallback
                    if not server_list:
                        if ws_host:
                            server_list.append({"host": ws_host, "port": 80})
                        elif self.sub_link_template:
                            import re
                            match = re.search(r"https?://([^:/]+)", self.sub_link_template)
                            port_match = re.search(r":(\d+)", self.sub_link_template)
                            host = match.group(1) if match else "localhost"
                            port = int(port_match.group(1)) if port_match else 443
                            server_list.append({"host": host, "port": port})

                    for server in server_list:
                        server_host = server["host"]
                        server_port = server["port"]

                        # Build query params
                        params = f"encryption=none"
                        params += f"&security={security}"
                        if sni:
                            params += f"&sni={sni}"
                        params += f"&type={net}"
                        if net == "ws":
                            if ws_host:
                                params += f"&host={ws_host}"
                            if path:
                                params += f"&path={path}"
                        elif net == "grpc":
                            if path:
                                params += f"&serviceName={path}"

                        params += f"#{tag_text}"

                        config_link = f"{protocol}://{uuid}@{server_host}:{server_port}?{params}"

                        configs.append({
                            "inbound_id": inbound["id"],
                            "tag": tag,
                            "protocol": protocol,
                            "email": email,
                            "config_link": config_link,
                        })
        return configs

    async def get_client_traffic(self, email: str) -> dict | None:
        data = await self._get("/panel/api/inbounds/get/1")
        if not data or not data.get("success"):
            return None
        obj = data.get("obj", {})

        # Traffic data lives in clientStats, not in settings.clients
        client_stats = obj.get("clientStats", [])
        traffic = None
        for stat in client_stats:
            if stat.get("email") == email:
                traffic = stat
                break

        # Get totalGB/expiryTime from settings.clients
        settings = obj.get("settings", {})
        if isinstance(settings, str):
            import json
            settings = json.loads(settings)
        clients = settings.get("clients", [])
        total_bytes = 0
        expiry_time = 0
        for client in clients:
            if client.get("email") == email:
                total_bytes = client.get("totalGB", 0)
                expiry_time = client.get("expiryTime", 0)
                break

        up_bytes = traffic.get("up", 0) if traffic else 0
        down_bytes = traffic.get("down", 0) if traffic else 0
        # clientStats may also have its own total field
        if traffic and traffic.get("total", 0) > 0:
            total_bytes = traffic["total"]

        used_bytes = up_bytes + down_bytes
        remaining_bytes = max(0, total_bytes - used_bytes) if total_bytes > 0 else 0
        return {
            "total_bytes": total_bytes,
            "total_gb": round(total_bytes / (1024 * 1024 * 1024), 2) if total_bytes > 0 else 0,
            "up_bytes": up_bytes,
            "down_bytes": down_bytes,
            "used_bytes": used_bytes,
            "used_gb": round(used_bytes / (1024 * 1024 * 1024), 2),
            "remaining_bytes": remaining_bytes,
            "remaining_gb": round(remaining_bytes / (1024 * 1024 * 1024), 2) if total_bytes > 0 else 0,
            "expiry_time": expiry_time,
        }

    async def _update_client(self, email: str, updates: dict) -> bool:
        inbounds = await self.get_inbounds()
        for inbound in inbounds:
            inbound_id = inbound.get("id")
            clients = inbound.get("settings", {}).get("clients", [])
            for client in clients:
                if client.get("email") == email:
                    client.update(updates)
                    result = await self._post(f"/panel/api/inbounds/update/{inbound_id}", inbound)
                    if result and result.get("success"):
                        logger.info(f"Updated client '{email}' on inbound {inbound_id}: {updates}")
                        return True
                    else:
                        logger.error(f"Failed to update client '{email}': {result}")
                        return False
        return False

    async def update_client_total_gb(self, email: str, extra_gb: float) -> bool:
        inbounds = await self.get_inbounds()
        for inbound in inbounds:
            clients = inbound.get("settings", {}).get("clients", [])
            for client in clients:
                if client.get("email") == email:
                    current_total = client.get("totalGB", 0)
                    extra_bytes = int(extra_gb * 1024 * 1024 * 1024)
                    new_total = current_total + extra_bytes if current_total > 0 else extra_bytes
                    if await self._update_client(email, {"totalGB": new_total}):
                        logger.info(f"Updated totalGB for '{email}' from {current_total} to {new_total}")
                        return True
                    return False
        return False

    async def regenerate_sub_link(self, email: str) -> str | None:
        inbounds = await self.get_inbounds()
        for inbound in inbounds:
            clients = inbound.get("settings", {}).get("clients", [])
            for client in clients:
                if client.get("email") == email:
                    new_sub_id = uuid.uuid4().hex[:16]
                    if await self._update_client(email, {"subId": new_sub_id}):
                        new_link = self.get_sub_link(email, new_sub_id)
                        logger.info(f"Regenerated sub link for '{email}': {new_link}")
                        return new_link
                    return None
        return None

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


panel_api = PanelAPI()
