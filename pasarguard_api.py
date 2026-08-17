"""
PasarGuardAPI class - talks to PasarGuard panel (FastAPI + Xray)
"""
import json
import logging
import aiohttp
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PasarGuardAPI:
    def __init__(self, panel_url="", panel_user="", panel_pass="", sub_path="sub"):
        self.panel_url = panel_url.rstrip("/") if panel_url else ""
        self.panel_user = panel_user or ""
        self.panel_pass = panel_pass or ""
        self.sub_path = sub_path or "sub"
        self.token = None
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True)
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _auth_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def login(self) -> bool:
        """Login via JWT token endpoint. Returns True on success."""
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.panel_url}/api/admin/token",
                data={"username": self.panel_user, "password": self.panel_pass},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get("access_token")
                    return self.token is not None
                logger.error(f"PasarGuard login failed: {resp.status}")
        except Exception as e:
            logger.error(f"PasarGuard login error: {e}")
        return False

    async def _get(self, path: str, params: dict = None) -> dict | list | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.get(
                url, params=params,
                headers=self._auth_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            )
            if resp.status == 200:
                return await resp.json()
            body = await resp.text()
            logger.error(f"PasarGuard GET {resp.status}: {url} -> {body[:200]}")
        except Exception as e:
            logger.error(f"PasarGuard GET error: {e}")
        return None

    async def _post(self, path: str, data: dict = None) -> dict | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.post(
                url, json=data or {},
                headers=self._auth_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            )
            body = await resp.text()
            if resp.status in (200, 201):
                try:
                    return json.loads(body)
                except Exception:
                    return {"message": body}
            logger.error(f"PasarGuard POST {resp.status}: {url} -> {body[:200]}")
        except Exception as e:
            logger.error(f"PasarGuard POST error: {e}")
        return None

    async def _put(self, path: str, data: dict = None) -> dict | None:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.put(
                url, json=data or {},
                headers=self._auth_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            )
            body = await resp.text()
            if resp.status == 200:
                try:
                    return json.loads(body)
                except Exception:
                    return {"message": body}
            logger.error(f"PasarGuard PUT {resp.status}: {url} -> {body[:200]}")
        except Exception as e:
            logger.error(f"PasarGuard PUT error: {e}")
        return None

    async def _delete(self, path: str) -> bool:
        session = await self._get_session()
        url = f"{self.panel_url}{path}"
        try:
            resp = await session.delete(
                url,
                headers=self._auth_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            )
            return resp.status in (200, 204)
        except Exception as e:
            logger.error(f"PasarGuard DELETE error: {e}")
        return False

    # ── Health / System ──────────────────────────────────────

    async def health_check(self) -> bool:
        session = await self._get_session()
        try:
            async with session.get(
                f"{self.panel_url}/health",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def get_system_stats(self) -> dict | None:
        return await self._get("/api/system")

    # ── Inbounds / Hosts ─────────────────────────────────────

    async def get_hosts(self) -> list[dict]:
        result = await self._get("/api/hosts")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "hosts" in result:
            return result["hosts"]
        return []

    async def get_groups(self) -> list[dict]:
        result = await self._get("/api/groups")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "groups" in result:
            return result["groups"]
        return []

    async def get_inbounds_summary(self) -> list[dict]:
        result = await self._get("/api/inbounds")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "inbounds" in result:
            return result["inbounds"]
        return []

    async def get_first_group_id(self) -> int | None:
        """Get the first available group ID. PasarGuard requires at least one group."""
        groups = await self.get_groups()
        if groups and len(groups) > 0:
            return groups[0].get("id")
        return None

    # ── User Management ──────────────────────────────────────

    async def create_user(
        self,
        username: str,
        data_limit_gb: float = 0,
        expire_days: int = 0,
        group_ids: list[int] = None,
        note: str = "",
    ) -> dict | None:
        """Create a new user on PasarGuard panel."""
        payload = {
            "username": username,
            "status": "active",
            "note": note or "Created by NigVpnBot",
        }

        if data_limit_gb > 0:
            payload["data_limit"] = int(data_limit_gb * 1024 * 1024 * 1024)
        else:
            payload["data_limit"] = 0

        if expire_days > 0:
            expire_dt = datetime.utcnow() + timedelta(days=expire_days)
            payload["expire"] = expire_dt.isoformat() + "Z"
        else:
            payload["expire"] = 0

        if group_ids:
            payload["group_ids"] = group_ids
        else:
            first_gid = await self.get_first_group_id()
            if first_gid is not None:
                payload["group_ids"] = [first_gid]
            else:
                logger.warning("PasarGuard: no groups found, user may fail to create")

        result = await self._post("/api/user", payload)
        if result:
            logger.info(f"PasarGuard user '{username}' created: {result}")
        return result

    async def get_user(self, username: str) -> dict | None:
        return await self._get(f"/api/user/{username}")

    async def get_user_by_id(self, user_id: int) -> dict | None:
        return await self._get(f"/api/user/by-id/{user_id}")

    async def update_user(self, username: str, **kwargs) -> dict | None:
        return await self._put(f"/api/user/{username}", kwargs)

    async def delete_user(self, username: str) -> bool:
        return await self._delete(f"/api/user/{username}")

    async def get_user_usage(self, username: str) -> dict | None:
        return await self._get(f"/api/user/{username}/usage")

    async def reset_user_traffic(self, username: str) -> dict | None:
        return await self._post(f"/api/user/{username}/reset")

    async def revoke_subscription(self, username: str) -> dict | None:
        return await self._post(f"/api/user/{username}/revoke_sub")

    # ── Subscription ─────────────────────────────────────────

    def get_subscription_url(self, username: str, token: str = None) -> str:
        """Build subscription URL for a user. Prefer token-based URL if available."""
        if token:
            return f"{self.panel_url}/{self.sub_path}/{token}/"
        return f"{self.panel_url}/{self.sub_path}/{username}/"

    def extract_subscription_url(self, user_data: dict) -> str | None:
        """Extract subscription_url from a user creation response."""
        if not user_data:
            return None
        sub_url = user_data.get("subscription_url")
        if sub_url:
            return sub_url
        return None

    async def get_subscription_info(self, token: str) -> dict | None:
        return await self._get(f"/{self.sub_path}/{token}/info")

    # ── Traffic ──────────────────────────────────────────────

    async def get_client_traffic(self, username: str) -> dict | None:
        """Get traffic info for a user. Compatible format with 3x-ui."""
        usage = await self.get_user_usage(username)
        if not usage:
            return None

        user = await self.get_user(username)
        if not user:
            return None

        used_bytes = usage.get("used_traffic", 0) or 0
        data_limit = user.get("data_limit", 0) or 0
        expire = user.get("expire", 0) or 0

        if isinstance(expire, str):
            try:
                expire_dt = datetime.fromisoformat(expire.replace("Z", "+00:00"))
                expire_ts = int(expire_dt.timestamp() * 1000)
            except Exception:
                expire_ts = 0
        elif isinstance(expire, (int, float)):
            expire_ts = int(expire * 1000) if expire > 0 else 0
        else:
            expire_ts = 0

        total_gb = round(data_limit / (1024**3), 2) if data_limit > 0 else 0
        used_gb = round(used_bytes / (1024**3), 2)
        remaining_gb = round((data_limit - used_bytes) / (1024**3), 2) if data_limit > 0 else 0

        return {
            "total_bytes": data_limit,
            "total_gb": total_gb,
            "up_bytes": 0,
            "down_bytes": used_bytes,
            "used_bytes": used_bytes,
            "used_gb": used_gb,
            "remaining_bytes": max(0, data_limit - used_bytes) if data_limit > 0 else 0,
            "remaining_gb": remaining_gb,
            "expiry_time": expire_ts,
        }

    # ── Backup ───────────────────────────────────────────────

    async def backup_database(self) -> str | None:
        """Export all users to a local SQLite file."""
        import sqlite3 as _sqlite3
        from datetime import datetime as _dt

        users = await self._get("/api/users")
        if not users:
            logger.warning("No PasarGuard users found for backup")
            return None

        if isinstance(users, dict) and "users" in users:
            users = users["users"]

        now_str = _dt.utcnow().strftime("%Y-%m-%d_%H-%M")
        db_path = f"/tmp/pasarguard_backup_{now_str}.db"

        conn = _sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT, status TEXT,
            data_limit INTEGER, used_traffic INTEGER,
            expire TEXT, note TEXT,
            created_at TEXT, edit_at TEXT
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS panel_info (
            key TEXT PRIMARY KEY, value TEXT
        )""")

        cur.execute("INSERT INTO panel_info (key, value) VALUES (?, ?)",
                     ("panel_url", self.panel_url))
        cur.execute("INSERT INTO panel_info (key, value) VALUES (?, ?)",
                     ("backup_date", now_str))

        for u in users:
            cur.execute(
                "INSERT INTO users (id, username, status, data_limit, used_traffic, expire, note, created_at, edit_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    u.get("id", 0),
                    u.get("username", ""),
                    u.get("status", ""),
                    u.get("data_limit", 0),
                    u.get("used_traffic", 0) or u.get("lifetime_used_traffic", 0),
                    str(u.get("expire", "")),
                    u.get("note", ""),
                    str(u.get("created_at", "")),
                    str(u.get("edit_at", "")),
                ),
            )

        conn.commit()
        conn.close()

        logger.info("PasarGuard backup created: %s (%d users)", db_path, len(users))
        return db_path


pasarguard_api = PasarGuardAPI()
