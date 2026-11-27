"""Remove only rows and images marked with the Campus Link demo identifier."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

DEMO_ID = "campus-link-demo-v1"


def clear(store, confirm=False):
    if not confirm:
        raise SystemExit("Refusing to delete without --yes")
    removed = 0
    board_keys = []
    parts = ["board", "comment", "like", "report", "deadlines", "deleted"]
    for part in parts:
        for row in store.rows(part):
            if row.get("demo") == DEMO_ID:
                store.delete(part, row["RowKey"])
                removed += 1
                if part == "board":
                    board_keys.append(row["RowKey"])
    # Emoji reactions have one partition per post, so discover them through demo posts.
    for key in board_keys:
        for row in store.rows("emoji-" + key):
            if row.get("demo") == DEMO_ID:
                store.delete("emoji-" + key, row["RowKey"])
                removed += 1
        store.delete_picture(key)
    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--azure", action="store_true")
    parser.add_argument("--yes", action="store_true", help="confirm deletion of demo rows only")
    args = parser.parse_args()
    if args.azure and not (os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AZURE_STORAGE_ACCOUNT")):
        parser.error("Azure credentials are missing")
    if not args.azure and app.cloud:
        parser.error("App Service detected. Use --azure explicitly to delete cloud data.")
    store = app.Azure() if args.azure else app.Local(app.directory)
    print(f"removed {clear(store, args.yes)} demo rows")


if __name__ == "__main__":
    main()
