import uuid
import json
import re
import logging
import asyncio
import aiohttp
from urllib.parse import urlencode
from datetime import datetime, timedelta
import web_db

logger = logging.getLogger(__name__)


class PanelAPI:
    def __init__(self, panel_url="", panel_user="", panel_pass="", sub_link_template="", inbound_ids=None, panel_id=None):
        self.panel_id = panel_id
        self.panel_url = panel_url.rstrip("/") if panel_url else ""
        self.panel_user = panel_user or ""
        self.panel_pass = panel_pass or ""
        self.sub_link_template = sub_link_template or ""
        self.inbound_ids = inbound_ids if inbound_ids is not None else []
        self.base_path = ""
        self.session: aiohttp.ClientSession | None = None
        self.csrf_token: str = ""
        if not panel_url:
            try:
                self.reload_config()
            except Exception:
                pass
        else:
            self._extract_base_path()

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
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        needs_new = (
            self.session is None
            or self.session.closed
            or (current_loop is not None and getattr(self, '_session_loop', None) is not current_loop)
        )
        if needs_new:
            if self.session and not self.session.closed:
                try:
                    await self.session.close()
                except Exception:
                    pass
            self.session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True)
            )
            self._session_loop = current_loop
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

    async def get_wireguard_inbound_ids(self) -> list[int]:
        inbounds = await self.get_inbounds()
        return [inbound.get("id") for inbound in inbounds
                if inbound.get("protocol") == "wireguard" and inbound.get("enable")]

    async def is_wireguard_inbound(self, inbound_id: int) -> bool:
        inbound = await self.get_inbound(inbound_id)
        if inbound:
            return inbound.get("protocol") == "wireguard"
        return False

    async def get_inbound_protocol(self, inbound_id: int) -> str:
        inbound = await self.get_inbound(inbound_id)
        if inbound:
            return inbound.get("protocol", "unknown")
        return "unknown"

    async def download_wireguard_conf(self, sub_id: str) -> str | None:
        import base64 as _b64
        import urllib.parse as _url
        session = await self._get_session()
        sub_url = self.get_sub_link("", sub_id)
        try:
            async with session.get(sub_url, ssl=False, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                text = (await resp.text()).strip()

                if "[Interface]" in text:
                    return text

                try:
                    decoded = _b64.b64decode(text).decode("utf-8", errors="replace")
                except Exception:
                    decoded = text

                if not decoded.startswith("wireguard://"):
                    logger.error("Sub response is not wireguard:// URI: %s", decoded[:100])
                    return None

                parsed = _url.urlparse(decoded)
                pk_b64 = _url.unquote(parsed.username) if parsed.username else ""
                params = _url.parse_qs(parsed.query)
                address = params.get("address", [""])[0]
                dns = params.get("dns", [""])[0].replace("+", ", ")
                mtu = params.get("mtu", ["1300"])[0]
                pubkey = _url.unquote(params.get("publickey", [""])[0])
                host = parsed.hostname or ""
                port = parsed.port or 12825

                conf_lines = [
                    "[Interface]",
                    f"PrivateKey = {pk_b64}",
                    f"Address = {address}",
                    f"DNS = {dns}",
                    f"MTU = {mtu}",
                    "",
                    "[Peer]",
                    f"PublicKey = {pubkey}",
                    f"Endpoint = {host}:{port}",
                    "AllowedIPs = 0.0.0.0/0, ::/0",
                    "",
                ]
                return "\n".join(conf_lines)
        except Exception as e:
            logger.error(f"WireGuard conf download error: {e}")
        return None

    async def add_client(self, inbound_ids: list[int], email: str, total_gb: float = 0, days: int = 0, ip_limit: int = 0) -> dict | None:
        user_uuid = str(uuid.uuid4())
        sub_id = uuid.uuid4().hex[:16]

        total_bytes = int(total_gb * 1024 * 1024 * 1024) if total_gb > 0 else 0
        expiry_time = 0
        if days > 0:
            expiry_time = int((datetime.utcnow() + timedelta(days=days)).timestamp() * 1000)

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
                "limitIp": ip_limit,
                "tgId": 0,
                "group": "",
                "comment": "",
                "enable": True,
            },
            "inboundIds": inbound_ids,
        }

        logger.info(f"Adding client '{email}' to inbounds {inbound_ids}...")
        result = await self._post("/panel/api/clients/add", client_payload)
        logger.info(f"add_client result: {result}")
        if result and result.get("success"):
            await self.restart_xray()
            return {"uuid": user_uuid, "sub_id": sub_id, "email": email}

        logger.error(f"Failed to add client: {result}")
        return None


    async def reload_xray(self):
        """Reload xray via SIGUSR1 (works for VLESS/VMess, NOT for WireGuard)."""
        import subprocess
        try:
            result = subprocess.run(
                ["bash", "-c", "PID=$(pgrep -o -f 'xray-linux-amd64'); if [ -n \"$PID\" ]; then kill -USR1 $PID && echo \"reload_sent:$PID\"; else echo 'no_xray'; fi"],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout.strip()
            logger.info(f"Xray SIGUSR1 reload: {output}")
            if output.startswith("reload_sent:"):
                import asyncio
                await asyncio.sleep(1)
                return {"success": True, "method": "sigusr1", "pid": output.split(":")[1]}
        except Exception as e:
            logger.warning(f"SIGUSR1 failed: {e}")

        return await self._api_restart_xray()

    async def _api_restart_xray(self):
        """Full xray restart via API."""
        try:
            result = await self._post("/panel/api/server/restartXrayService", {})
            logger.info(f"Xray API restart result: {result}")
            return result
        except Exception as e:
            logger.error(f"Xray API restart failed: {e}")
            return None

    async def restart_xray(self, force_full: bool = False):
        """Restart xray. Uses SIGUSR1 for non-WG, full restart for WireGuard."""
        if force_full:
            return await self._api_restart_xray()
        return await self._api_restart_xray()
    def get_sub_link(self, email: str, sub_id: str) -> str:
        if self.sub_link_template:
            tmpl = self.sub_link_template
            if "{sub_id}" in tmpl or "{id}" in tmpl:
                return tmpl.replace("{sub_id}", sub_id).replace("{id}", sub_id)
            return tmpl.rstrip("/") + "/" + sub_id
        import re
        match = re.search(r"https?://([^:/]+)", self.panel_url)
        host = match.group(1) if match else "localhost"
        return f"https://{host}:2096/sub/{sub_id}"

    async def create_config(self, email: str, days: int = 30, total_gb: int = 0, inbound_ids: list[int] | None = None, ip_limit: int = 0) -> dict | None:
        if inbound_ids is None:
            inbound_ids = self.inbound_ids if self.inbound_ids else []
        if not inbound_ids:
            vid = await self.get_vless_inbound_id()
            if vid is not None:
                inbound_ids = [vid]

        # Validate inbound_ids against current panel inbounds
        if inbound_ids:
            try:
                current_inbounds = await self.get_inbounds()
                current_ids = {ib["id"] for ib in current_inbounds}
                valid_ids = [iid for iid in inbound_ids if iid in current_ids]
                if not valid_ids and current_inbounds:
                    valid_ids = [current_inbounds[0]["id"]]
                    logger.warning(f"All specified inbound_ids {inbound_ids} not found on panel. Falling back to first available inbound {valid_ids[0]}.")
                elif len(valid_ids) < len(inbound_ids):
                    missing = set(inbound_ids) - set(valid_ids)
                    logger.warning(f"Some inbound_ids {missing} not found on panel. Using only valid ones: {valid_ids}")
                inbound_ids = valid_ids
            except Exception as e:
                logger.error(f"Failed to validate inbound_ids: {e}")

        if not inbound_ids:
            logger.error("No inbounds configured")
            return None

        result = await self.add_client(inbound_ids, email, total_gb=total_gb, days=days, ip_limit=ip_limit)
        if result:
            sub_link = self.get_sub_link(email, result["sub_id"])
            expire_date = (datetime.utcnow() + timedelta(days=days)).isoformat()

            # Detect if any of the inbounds is WireGuard
            protocol = "v2ray"
            try:
                for iid in inbound_ids:
                    p = await self.get_inbound_protocol(iid)
                    if p == "wireguard":
                        protocol = "wireguard"
                        break
            except Exception:
                pass

            return {
                "uuid": result["uuid"],
                "email": result["email"],
                "sub_link": sub_link,
                "sub_id": result["sub_id"],
                "expire_date": expire_date,
                "protocol": protocol,
            }

        logger.error("Failed to add client to panel")
        return None

    async def create_test_config(self, email: str, total_mb: int = 102400, days: int = 1, custom_inbound_ids: list = None) -> dict | None:
        if custom_inbound_ids:
            inbound_ids = custom_inbound_ids
        else:
            inbound_ids = self.inbound_ids if self.inbound_ids else []
        if not inbound_ids:
            vid = await self.get_vless_inbound_id()
            if vid is not None:
                inbound_ids = [vid]

        # Validate inbound_ids against current panel inbounds
        if inbound_ids:
            try:
                current_inbounds = await self.get_inbounds()
                current_ids = {ib["id"] for ib in current_inbounds}
                valid_ids = [iid for iid in inbound_ids if iid in current_ids]
                if not valid_ids and current_inbounds:
                    valid_ids = [current_inbounds[0]["id"]]
                inbound_ids = valid_ids
            except Exception:
                pass

        if not inbound_ids:
            logger.error("No inbounds configured")
            return None

        total_gb = total_mb / 1024
        result = await self.add_client(inbound_ids, email, total_gb=total_gb, days=days)
        if result:
            sub_link = self.get_sub_link(email, result["sub_id"])
            expire_date = (datetime.utcnow() + timedelta(days=days)).isoformat()

            # Detect if any of the inbounds is WireGuard
            protocol = "v2ray"
            try:
                for iid in inbound_ids:
                    p = await self.get_inbound_protocol(iid)
                    if p == "wireguard":
                        protocol = "wireguard"
                        break
            except Exception:
                pass

            return {
                "uuid": result["uuid"],
                "email": result["email"],
                "sub_link": sub_link,
                "sub_id": result["sub_id"],
                "expire_date": expire_date,
                "protocol": protocol,
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
        inbounds = await self.get_inbounds()
        target_inbound_id = None
        target_clients = []
        for inbound in inbounds:
            settings = inbound.get("settings", {})
            if isinstance(settings, str):
                import json
                settings = json.loads(settings)
            clients = settings.get("clients", [])
            if any(c.get("email") == email for c in clients):
                target_inbound_id = inbound.get("id")
                target_clients = clients
                break

        if target_inbound_id is None:
            return None

        data = await self._get(f"/panel/api/inbounds/get/{target_inbound_id}")
        if not data or not data.get("success"):
            return None
        obj = data.get("obj", {})

        client_stats = obj.get("clientStats", [])
        traffic = None
        for stat in client_stats:
            if stat.get("email") == email:
                traffic = stat
                break

        total_bytes = 0
        expiry_time = 0
        for client in target_clients:
            if client.get("email") == email:
                total_bytes = client.get("totalGB", 0)
                expiry_time = client.get("expiryTime", 0)
                break

        up_bytes = traffic.get("up", 0) if traffic else 0
        down_bytes = traffic.get("down", 0) if traffic else 0
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

    async def backup_database(self) -> str | None:
        """Create a .db backup of the 3x-ui panel by exporting all data via API
        and packaging it as a SQLite database file. Returns the file path."""
        import sqlite3 as _sqlite3

        inbounds = await self.get_inbounds()
        if not inbounds:
            logger.warning("No inbounds found for backup on panel %s", self.panel_id)
            return None

        full_data = []
        for inbound in inbounds:
            detail = await self.get_inbound(inbound["id"])
            if detail:
                full_data.append(detail)

        if not full_data:
            return None

        from datetime import datetime as _dt
        now_str = _dt.utcnow().strftime("%Y-%m-%d_%H-%M")
        db_path = f"/tmp/3xui_backup_{now_str}.db"

        conn = _sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS inbounds (
            id INTEGER PRIMARY KEY, tag TEXT, protocol TEXT, port INTEGER,
            settings TEXT, stream_settings TEXT, sniffing TEXT,
            enable INTEGER, expiry_time INTEGER, total INTEGER,
            remark TEXT, listen TEXT, traffic INTEGER
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbound_id INTEGER, email TEXT, uuid TEXT,
            sub_id TEXT, enable INTEGER, total_gb REAL,
            expiry_time INTEGER, ip_limit INTEGER,
            FOREIGN KEY (inbound_id) REFERENCES inbounds(id)
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS panel_info (
            key TEXT PRIMARY KEY, value TEXT
        )""")

        cur.execute("INSERT INTO panel_info (key, value) VALUES (?, ?)",
                     ("panel_url", self.panel_url))
        cur.execute("INSERT INTO panel_info (key, value) VALUES (?, ?)",
                     ("backup_date", now_str))
        cur.execute("INSERT INTO panel_info (key, value) VALUES (?, ?)",
                     ("panel_id", str(self.panel_id or "")))

        for inbound in full_data:
            cur.execute(
                "INSERT INTO inbounds (id, tag, protocol, port, settings, stream_settings, sniffing, enable, expiry_time, total, remark, listen, traffic) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    inbound.get("id"),
                    inbound.get("tag", ""),
                    inbound.get("protocol", ""),
                    inbound.get("port", 0),
                    json.dumps(inbound.get("settings", {}), ensure_ascii=False),
                    json.dumps(inbound.get("streamSettings", {}), ensure_ascii=False),
                    json.dumps(inbound.get("sniffing", {}), ensure_ascii=False),
                    1 if inbound.get("enable") else 0,
                    inbound.get("expiryTime", 0),
                    inbound.get("total", 0),
                    inbound.get("remark", ""),
                    inbound.get("listen", ""),
                    inbound.get("traffic", 0),
                ),
            )

            clients = inbound.get("clientStats", []) or []
            settings = inbound.get("settings", {})
            clients_list = settings.get("clients", []) if isinstance(settings, dict) else []

            for cl in clients_list:
                email = cl.get("email", "")
                cl_uuid = cl.get("id", "")
                sub_id = cl.get("subId", "")
                enable = 1 if cl.get("enable", True) else 0
                total_gb = cl.get("totalGB", 0)
                expiry = cl.get("expiryTime", 0)
                ip_limit = cl.get("limitIp", 0)

                cur.execute(
                    "INSERT INTO clients (inbound_id, email, uuid, sub_id, enable, total_gb, expiry_time, ip_limit) VALUES (?,?,?,?,?,?,?,?)",
                    (inbound.get("id"), email, cl_uuid, sub_id, enable, total_gb, expiry, ip_limit),
                )

        conn.commit()
        conn.close()

        logger.info("3x-ui backup created: %s (%d inbounds)", db_path, len(full_data))
        return db_path

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


class PanelManager:
    def __init__(self):
        self._instances: dict[int, PanelAPI] = {}
        self._default: PanelAPI | None = None

    async def load_all(self):
        import database as db
        panels = await db.get_active_panels()
        self._instances.clear()
        for p in panels:
            inbound_ids = [int(x.strip()) for x in (p.get("inbound_ids") or "").split(",") if x.strip().isdigit()]
            instance = PanelAPI(
                panel_url=p["url"],
                panel_user=p["username"],
                panel_pass=p["password"],
                sub_link_template=p.get("sub_link_template", ""),
                inbound_ids=inbound_ids,
                panel_id=p["id"],
            )
            self._instances[p["id"]] = instance
            if p.get("is_default"):
                self._default = instance
        if not self._default and self._instances:
            self._default = next(iter(self._instances.values()))
        if not self._default:
            self._default = panel_api

    def get(self, panel_id: int) -> PanelAPI | None:
        return self._instances.get(panel_id)

    def get_default(self) -> PanelAPI | None:
        return self._default or panel_api

    async def add(self, panel_data: dict) -> PanelAPI:
        import database as db
        inbound_ids_str = panel_data.get("inbound_ids", "")
        panel_id = await db.add_panel(
            name=panel_data["name"],
            url=panel_data["url"],
            username=panel_data.get("username", ""),
            password=panel_data.get("password", ""),
            sub_link_template=panel_data.get("sub_link_template", ""),
            inbound_ids=inbound_ids_str,
            is_default=panel_data.get("is_default", False),
            volume_gb=panel_data.get("volume_gb", 0),
            panel_type=panel_data.get("panel_type", "v2ray"),
            free_test_enabled=panel_data.get("free_test_enabled", 0),
            free_test_mb=panel_data.get("free_test_mb", 102400),
            free_test_days=panel_data.get("free_test_days", 1),
            free_test_inbound_ids=panel_data.get("free_test_inbound_ids", ""),
        )
        inbound_ids = [int(x.strip()) for x in inbound_ids_str.split(",") if x.strip().isdigit()]
        instance = PanelAPI(
            panel_url=panel_data["url"],
            panel_user=panel_data["username"],
            panel_pass=panel_data["password"],
            sub_link_template=panel_data.get("sub_link_template", ""),
            inbound_ids=inbound_ids,
            panel_id=panel_id,
        )
        self._instances[panel_id] = instance
        if panel_data.get("is_default") or not self._default:
            self._default = instance
        return instance

    async def remove(self, panel_id: int):
        import database as db
        await db.delete_panel(panel_id)
        instance = self._instances.pop(panel_id, None)
        if instance:
            await instance.close()
        if self._default and self._default.panel_id == panel_id:
            self._default = next(iter(self._instances.values()), None) or panel_api

    async def update(self, panel_id: int, **kwargs):
        import database as db
        await db.update_panel(panel_id, **kwargs)
        if "url" in kwargs or "username" in kwargs or "password" in kwargs or "sub_link_template" in kwargs or "inbound_ids" in kwargs:
            panel = await db.get_panel(panel_id)
            if panel:
                inbound_ids = [int(x.strip()) for x in (panel.get("inbound_ids") or "").split(",") if x.strip().isdigit()]
                self._instances[panel_id] = PanelAPI(
                    panel_url=panel["url"],
                    panel_user=panel["username"],
                    panel_pass=panel["password"],
                    sub_link_template=panel.get("sub_link_template", ""),
                    inbound_ids=inbound_ids,
                    panel_id=panel_id,
                )

    async def set_default(self, panel_id: int):
        import database as db
        await db.set_default_panel(panel_id)
        self._default = self._instances.get(panel_id)

    async def test_connection(self, panel_id: int) -> dict:
        panel = self.get(panel_id)
        if not panel:
            return {"success": False, "error": "Panel not found"}
        ok = await panel.login()
        if not ok:
            return {"success": False, "error": "Login failed - check username/password"}
        inbounds = await panel.get_inbounds()
        total_clients = 0
        for ib in inbounds:
            total_clients += len(ib.get("settings", {}).get("clients", []))
        return {
            "success": True,
            "inbounds_count": len(inbounds),
            "total_clients": total_clients,
        }

    async def test_connection_detailed(self, panel_id: int) -> dict:
        panel = self.get(panel_id)
        if not panel:
            return {"success": False, "error": "Panel not found", "login_ok": False, "url_reachable": False}

        import time
        result = {
            "success": False,
            "login_ok": False,
            "url_reachable": False,
            "response_time_ms": 0,
            "inbounds_count": 0,
            "inbounds_by_protocol": {},
            "total_clients": 0,
            "error": None,
            "inbounds": [],
            "sub_template": panel.sub_link_template or "خودکار",
        }

        # Test URL reachability
        try:
            session = await panel._get_session()
            start = time.time()
            async with session.get(panel.panel_url, ssl=False, timeout=__import__("aiohttp").ClientTimeout(total=10)) as resp:
                result["response_time_ms"] = int((time.time() - start) * 1000)
                result["url_reachable"] = resp.status < 400
        except Exception as e:
            result["error"] = f"URL unreachable: {e}"
            return result

        # Test login
        ok = await panel.login()
        result["login_ok"] = ok
        if not ok:
            result["error"] = "Login failed - check username/password"
            return result

        # Get inbounds
        try:
            inbounds = await panel.get_inbounds()
            result["inbounds_count"] = len(inbounds)
            protocol_counts = {}
            for ib in inbounds:
                proto = ib.get("protocol", "unknown")
                protocol_counts[proto] = protocol_counts.get(proto, 0) + 1
                client_count = len(ib.get("settings", {}).get("clients", []))
                result["total_clients"] += client_count
                result["inbounds"].append({
                    "id": ib.get("id"),
                    "tag": ib.get("tag"),
                    "protocol": proto,
                    "enabled": ib.get("enable", False),
                    "clients": client_count,
                })
            result["inbounds_by_protocol"] = protocol_counts
        except Exception as e:
            result["error"] = f"Failed to fetch inbounds: {e}"

        result["success"] = True
        return result

    async def test_connection_with_creds(self, url: str, username: str, password: str) -> dict:
        temp = PanelAPI(panel_url=url, panel_user=username, panel_pass=password)
        try:
            ok = await temp.login()
            if not ok:
                return {"success": False, "error": "Login failed - check username/password"}
            inbounds = await temp.get_inbounds()
            total_clients = 0
            for ib in inbounds:
                total_clients += len(ib.get("settings", {}).get("clients", []))
            return {
                "success": True,
                "inbounds_count": len(inbounds),
                "total_clients": total_clients,
                "inbounds": [
                    {"id": ib.get("id"), "tag": ib.get("tag"), "protocol": ib.get("protocol"),
                     "enable": ib.get("enable"), "client_count": len(ib.get("settings", {}).get("clients", []))}
                    for ib in inbounds
                ],
            }
        finally:
            await temp.close()

    async def get_inbounds_summary(self, panel_id: int) -> list[dict]:
        panel = self.get(panel_id)
        if not panel:
            return []
        inbounds = await panel.get_inbounds()
        return [
            {"id": ib.get("id"), "tag": ib.get("tag"), "protocol": ib.get("protocol"),
             "enable": ib.get("enable"), "client_count": len(ib.get("settings", {}).get("clients", []))}
            for ib in inbounds
        ]

    async def get_all_clients(self, panel_id: int) -> list[dict]:
        panel = self.get(panel_id)
        if not panel:
            return []
        inbounds = await panel.get_inbounds()
        clients = []
        for ib in inbounds:
            for client in ib.get("settings", {}).get("clients", []):
                clients.append({
                    "email": client.get("email"),
                    "uuid": client.get("id"),
                    "inbound_id": ib.get("id"),
                    "inbound_tag": ib.get("tag"),
                    "total_gb": client.get("totalGB", 0),
                    "expiry_time": client.get("expiryTime", 0),
                    "enable": client.get("enable", True),
                })
        return clients

    async def get_client_configs(self, panel_id: int, email: str) -> list:
        panel = self.get(panel_id)
        if not panel:
            panel = self.get_default()
        if not panel:
            return []
        return await panel.get_client_configs(email)

    async def create_config(self, panel_id: int, email: str, days: int, total_gb: int, inbound_ids: list[int], ip_limit: int = 0) -> dict | None:
        panel = self.get(panel_id)
        if not panel:
            panel = self.get_default()
        if not panel:
            return None
        return await panel.create_config(email, days, total_gb, inbound_ids, ip_limit)

    async def get_client_traffic(self, panel_id: int, email: str) -> dict | None:
        panel = self.get(panel_id)
        if not panel:
            panel = self.get_default()
        if not panel:
            return None
        return await panel.get_client_traffic(email)

    async def update_client_total_gb(self, panel_id: int, email: str, extra_gb: float) -> bool:
        panel = self.get(panel_id)
        if not panel:
            panel = self.get_default()
        if not panel:
            return False
        return await panel.update_client_total_gb(email, extra_gb)

    async def regenerate_sub_link(self, panel_id: int, email: str) -> str | None:
        panel = self.get(panel_id)
        if not panel:
            panel = self.get_default()
        if not panel:
            return None
        return await panel.regenerate_sub_link(email)

    async def close_all(self):
        for panel in self._instances.values():
            await panel.close()


panel_api = PanelAPI()
panel_manager = PanelManager()

# Wireguard panel integration
try:
    from wireguard_api import wireguard_api, WireguardAPI
except ImportError:
    wireguard_api = None
    WireguardAPI = None

try:
    panel_api
except NameError:
    panel_api = PanelAPI()
