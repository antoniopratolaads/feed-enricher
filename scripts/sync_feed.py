#!/usr/bin/env python3
"""Feed sync CLI — scarica/carica un feed per un cliente, calcola delta,
salva snapshot, aggiorna coda enrichment.

Usage:
    python -m scripts.sync_feed --client "Nike IT" --feed main \
        --url https://store.nike.com/products.xml

    python -m scripts.sync_feed --client nike-it --feed main \
        --file /path/to/catalog.csv --no-pending

    python -m scripts.sync_feed --list-clients
    python -m scripts.sync_feed --list-feeds --client nike-it

Designed to run from cron (daily). Returns non-zero on errors.
Does NOT trigger enrichment — use the Streamlit UI or a separate script.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root: `python scripts/sync_feed.py ...`
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from utils import clients as cs
from utils import feed_diff
from utils.feed_parser import load_feed, normalize_columns


def _find_client(client_arg: str) -> str | None:
    """Resolve a client by slug or name (case-insensitive)."""
    all_c = cs.list_clients()
    for c in all_c:
        if c["slug"] == client_arg:
            return c["slug"]
    for c in all_c:
        if c.get("name", "").lower() == client_arg.lower():
            return c["slug"]
    return None


def cmd_list_clients() -> int:
    clients = cs.list_clients()
    if not clients:
        print("Nessun cliente registrato.")
        return 0
    print(f"{'SLUG':25s}  {'NAME':30s}  {'FEEDS':6s}  CREATED")
    for c in clients:
        print(f"{c['slug']:25s}  {c['name']:30s}  {c.get('n_feeds', 0):<6d}  {c.get('created_at', '')[:10]}")
    return 0


def cmd_list_feeds(client_slug: str) -> int:
    feeds = cs.list_feeds(client_slug)
    if not feeds:
        print(f"Nessun feed per cliente '{client_slug}'.")
        return 0
    print(f"{'SLUG':25s}  {'NAME':30s}  {'SNAPSHOTS':10s}  {'PENDING':8s}  LAST_SYNC")
    for f in feeds:
        print(
            f"{f['slug']:25s}  {f['name']:30s}  "
            f"{f.get('n_snapshots', 0):<10d}  {f.get('n_pending', 0):<8d}  "
            f"{(f.get('last_sync_at') or '—')[:19]}"
        )
    return 0


def cmd_sync(client_slug: str, feed_slug: str,
             url: str | None = None, file_path: str | None = None,
             mark_pending: bool = True, json_out: bool = False) -> int:
    feed = cs.get_feed(client_slug, feed_slug)
    if not feed:
        print(f"✗ Feed '{feed_slug}' non trovato per cliente '{client_slug}'.", file=sys.stderr)
        return 2

    source = url or file_path or feed.get("source_url")
    if not source:
        print("✗ Nessuna sorgente: passa --url o --file, o imposta source_url nel feed.",
              file=sys.stderr)
        return 2

    # Load
    try:
        if file_path:
            raw = load_feed(Path(file_path).read_bytes(), filename=Path(file_path).name)
        else:
            raw = load_feed(source)
        new_df = normalize_columns(raw)
    except Exception as e:  # noqa
        print(f"✗ Errore caricamento feed: {e}", file=sys.stderr)
        return 3

    # Diff
    old_df = cs.get_latest_snapshot(client_slug, feed_slug)
    delta = feed_diff.compute_delta(
        old_df, new_df, strategy=feed.get("id_strategy", "hierarchical")
    )
    summary = feed_diff.delta_summary(delta)

    # Persist snapshot + pending
    cs.save_snapshot(client_slug, feed_slug, new_df)
    if mark_pending:
        cs.add_pending(client_slug, feed_slug, delta.added, reason="new")
        cs.add_pending(client_slug, feed_slug, delta.modified, reason="modified")
    cs.log_event(client_slug, feed_slug, "sync_cli", {**summary, "source": source})

    report = {
        "client": client_slug,
        "feed": feed_slug,
        "source": source,
        "n_products": int(len(new_df)),
        **summary,
        "pending_queued": int(summary["added"] + summary["modified"]) if mark_pending else 0,
    }

    if json_out:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"✓ Sync completato · {client_slug}/{feed_slug}")
        print(f"   prodotti: {report['n_products']:,}")
        print(f"   nuovi:    {summary['added']:,}")
        print(f"   modif.:   {summary['modified']:,}")
        print(f"   rimossi:  {summary['removed']:,}")
        print(f"   invariati:{summary['unchanged']:,}")
        if mark_pending:
            print(f"   coda enrich: +{report['pending_queued']} (totale aggiornato)")

    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync feed cliente + calcola delta.")
    p.add_argument("--client", help="Client slug o nome")
    p.add_argument("--feed", help="Feed slug (per sync)")
    p.add_argument("--url", help="URL del feed (override quello salvato)")
    p.add_argument("--file", help="Path a file feed (XML/CSV/JSON/XLSX)")
    p.add_argument("--no-pending", action="store_true",
                   help="Non aggiungere i nuovi/modificati alla coda enrichment")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.add_argument("--list-clients", action="store_true", help="Elenca clienti")
    p.add_argument("--list-feeds", action="store_true", help="Elenca feed del cliente")

    args = p.parse_args(argv)

    if args.list_clients:
        return cmd_list_clients()

    if not args.client:
        print("✗ --client richiesto.", file=sys.stderr)
        return 1

    slug = _find_client(args.client)
    if not slug:
        print(f"✗ Cliente '{args.client}' non trovato.", file=sys.stderr)
        return 1

    if args.list_feeds:
        return cmd_list_feeds(slug)

    if not args.feed:
        print("✗ --feed richiesto.", file=sys.stderr)
        return 1

    return cmd_sync(
        client_slug=slug,
        feed_slug=args.feed,
        url=args.url,
        file_path=args.file,
        mark_pending=not args.no_pending,
        json_out=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
