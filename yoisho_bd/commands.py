"""Yoisho BD OS terminal commands (``sellbird yoisho-...``)."""

from __future__ import annotations

import asyncio

from yoisho_bd.store import Store


def configure_import(parser):
    parser.add_argument("csv_path", help="CSV with a header row; see yoisho_bd/importer.py")

    def _main(args):
        from yoisho_bd.importer import import_csv

        async def go():
            store = Store.for_sellbird()
            await store.init()
            result = await import_csv(store, args.csv_path)
            print(result.summary())
            for line in result.errors:
                print("  " + line)
        asyncio.run(go())
    return _main


def configure_status(parser):
    def _main(args):
        async def go():
            store = Store.for_sellbird()
            await store.init()
            counts = await store.counts()
            print("Yoisho BD OS records:")
            for key, value in counts.items():
                print(f"  {key.replace('_', ' ')}: {value}")
        asyncio.run(go())
    return _main
