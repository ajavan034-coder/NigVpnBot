import asyncio
import sys
import sqlite3
import logging

logging.basicConfig(level=logging.DEBUG, format='%(name)s %(levelname)s %(message)s')

sys.path.insert(0, '.')
from pasarguard_api import PasarGuardAPI

async def test():
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    panels = conn.execute("SELECT * FROM panels WHERE panel_type = 'pasarguard'").fetchall()
    if not panels:
        print("NO PASARGUARD PANELS FOUND IN DB")
        conn.close()
        return

    for p in panels:
        print(f"\n=== Panel: {p['name']} ===")
        print(f"URL: {p['url']}")
        print(f"Username: {p['username']}")
        print(f"Password: {p['password'][:3]}***")

        api = PasarGuardAPI(
            panel_url=p['url'],
            panel_user=p['username'],
            panel_pass=p['password'],
        )

        # Step 1: Login
        print("\n--- Step 1: Login ---")
        ok = await api.login()
        print(f"Login OK: {ok}")
        if not ok:
            await api.close()
            continue

        # Step 2: Get groups
        print("\n--- Step 2: Get Groups ---")
        groups = await api.get_groups()
        print(f"Groups: {groups}")

        # Step 3: Create test user
        print("\n--- Step 3: Create User ---")
        import random, string
        rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        uname = f"testbot_{rnd}"
        result = await api.create_user(username=uname, data_limit_gb=1, expire_days=1)
        print(f"Create result keys: {list(result.keys()) if result else None}")
        if result:
            print(f"  id: {result.get('id')}")
            print(f"  username: {result.get('username')}")
            print(f"  subscription_url: {result.get('subscription_url', 'NOT PRESENT')}")
            print(f"  uuid: {result.get('uuid', 'NOT PRESENT')}")
            print(f"  token: {result.get('token', 'NOT PRESENT')}")
            print(f"  sub_token: {result.get('sub_token', 'NOT PRESENT')}")
            for k, v in result.items():
                if 'sub' in str(k).lower() or 'token' in str(k).lower() or 'url' in str(k).lower():
                    print(f"  {k}: {v}")

        # Step 4: Fetch user to get subscription URL
        print("\n--- Step 4: Fetch User ---")
        user_data = await api.get_user(uname)
        print(f"User data keys: {list(user_data.keys()) if user_data else None}")
        if user_data:
            for k, v in user_data.items():
                if 'sub' in str(k).lower() or 'token' in str(k).lower() or 'url' in str(k).lower() or 'uuid' in str(k).lower():
                    print(f"  {k}: {v}")

        # Step 5: Get subscription URL
        print("\n--- Step 5: Subscription URL ---")
        sub_url = await api.get_subscription_url_for_user(uname)
        print(f"Subscription URL: {sub_url}")

        fallback_url = api.build_subscription_url(uname)
        print(f"Fallback URL: {fallback_url}")

        # Step 6: Download config
        if sub_url:
            print("\n--- Step 6: Download WireGuard Config ---")
            conf = await api.download_wireguard_config(sub_url)
            if conf:
                print(f"Config length: {len(conf)} chars")
                print(f"Config preview:\n{conf[:500]}")
            else:
                print("Config download FAILED")
                # Try fallback URL
                print(f"\nTrying fallback URL: {fallback_url}")
                conf2 = await api.download_wireguard_config(fallback_url)
                if conf2:
                    print(f"Fallback config length: {len(conf2)} chars")
                    print(f"Fallback config preview:\n{conf2[:500]}")
                else:
                    print("Fallback also FAILED")

        # Step 7: Cleanup - delete test user
        print("\n--- Step 7: Cleanup ---")
        deleted = await api.delete_user(uname)
        print(f"Deleted test user: {deleted}")

        await api.close()

    conn.close()

asyncio.run(test())
