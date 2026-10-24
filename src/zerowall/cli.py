import argparse, json, os, webbrowser
from .settings import Settings


def main():
    parser = argparse.ArgumentParser(prog="zerowall")
    parser.add_argument(
        "command", choices=["serve", "open", "doctor"], nargs="?", default="serve"
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    settings = Settings()
    if args.command == "open":
        webbrowser.open(settings.hosting.public_origin if settings.hosting.hosted else f"http://127.0.0.1:{args.port}/")
        print("Opened the hosted council access page." if settings.hosting.hosted else "Opened the local council directly at the prompt.")
    elif args.command == "doctor":
        from .db import open_store
        from .budget import Budget

        store = open_store(settings)
        with store.tx() as c:
            v = store.setting(c, "live_verification", {})
            storage = {'backend': 'supabase' if store.remote else 'local'}
            if store.remote:
                from .postgres import WORKER_LOCK
                storage.update(
                    ledger_imported=bool(store.setting(c, 'cloud_ledger_ready')),
                    worker_owns_queue=not c.execute('SELECT pg_try_advisory_xact_lock(?)', (WORKER_LOCK,)).fetchone()[0],
                    staged_files=c.execute('SELECT COUNT(*) FROM blob_files WHERE data IS NOT NULL').fetchone()[0],
                    staged_bytes=c.execute('SELECT COALESCE(SUM(size),0) FROM blob_files WHERE data IS NOT NULL').fetchone()[0],
                )
            print(
                json.dumps(
                    {
                        "python": "3.11+",
                        "key_present": bool(settings.api_key),
                        "openrouter_free_key_present": bool(
                            settings.openrouter_api_key
                        ),
                        "openrouter_enabled": settings.openrouter_enabled,
                        "direct_provider_keys_present": {provider: bool(key) for provider, key in settings.direct_keys.items()},
                        "direct_free_access_confirmed": settings.direct_free_confirmed,
                        "ui_built": settings.frontend.exists(),
                        "database": "ok",
                        "storage": storage,
                        "schema_version": 1,
                        "budget": Budget(store, settings).summary(c),
                        "live_verification_present": bool(v),
                        "inference_dispatched": False,
                    },
                    indent=2,
                )
            )
        store.close()
    else:
        import uvicorn
        from .api import create_app

        # One worker is part of the queue ownership contract; do not use --workers or reload.
        uvicorn.run(
            create_app(settings),
            host="0.0.0.0" if settings.hosting.hosted else "127.0.0.1",
            port=args.port,
            log_level="warning",
            proxy_headers=False,
            timeout_graceful_shutdown=60,
        )


if __name__ == "__main__":
    main()
