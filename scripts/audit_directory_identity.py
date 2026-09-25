"""Audit consistency of the bundled RBI DLA identity index.

This does not prove an app is safe or legal. It verifies that identities present in
our local official snapshot do not get lost because of parser/matcher bugs.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import Config
from services.dla_lookup import DirectoryIndex


def main():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=Config.DIRECTORY_STALE_AFTER_DAYS)
    if not index.meta.get("available"):
        raise SystemExit("Directory unavailable")

    package_failures = []
    for package_id in sorted(index.by_package):
        result = index.lookup(
            "Store title may change",
            "Store developer may change",
            f"https://play.google.com/store/apps/details?id={package_id}",
        )
        if result.get("status") != "Listed" or result.get("match_score") != 100:
            package_failures.append((package_id, result.get("status"), result.get("match_score")))

    row_failures = []
    for row in index.rows:
        result = index.lookup(row["app_name"], row["developer_name"], row["app_url"])
        if result.get("status") != "Listed":
            row_failures.append((row["source_record_no"], row["app_name"], result.get("status"), result.get("match_method")))

    print("DIRECTORY IDENTITY AUDIT")
    print("=" * 64)
    print(f"Snapshot date       : {index.meta.get('snapshot_date')}")
    print(f"Usable DLA rows     : {index.meta.get('row_count')}")
    print(f"Package-bearing rows: {index.meta.get('package_rows')}")
    print(f"Unique packages     : {index.meta.get('unique_packages')}")
    print(f"Package failures    : {len(package_failures)}")
    print(f"Official-row failures: {len(row_failures)}")

    if package_failures:
        print("\nFirst package failures:")
        for item in package_failures[:20]:
            print(" -", item)
    if row_failures:
        print("\nFirst row failures:")
        for item in row_failures[:20]:
            print(" -", item)

    if package_failures or row_failures:
        raise SystemExit(1)
    print("PASS: all indexed official identities resolve consistently.")


if __name__ == "__main__":
    main()
