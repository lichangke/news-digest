from __future__ import annotations

import argparse
import json
import sys

from .pipeline import build_result, save_result


LEGACY_NOTE = (
    "[legacy-entry] app.main now delegates to app.pipeline; "
    "use `python -m app.pipeline ...` as the standard entrypoint."
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Legacy compatibility entrypoint. Prefer `python -m app.pipeline`."
    )
    parser.add_argument("--run-type", choices=["morning", "evening"], required=True)
    parser.add_argument("--channel", choices=["general", "ai"], default="general")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--ignore-state", action="store_true")
    parser.add_argument("--sync-wiki", action="store_true")
    args = parser.parse_args()

    print(LEGACY_NOTE, file=sys.stderr)

    result = build_result(
        args.run_type,
        args.channel,
        ignore_state=args.ignore_state,
        sync_wiki_enabled=args.sync_wiki,
        demo=args.demo,
    )
    result.setdefault("meta", {})["entrypoint"] = "app.main"
    result["meta"]["delegates_to"] = "app.pipeline"
    result_path = save_result(result)
    print(json.dumps({"ok": result.get("ok", False), "result_path": str(result_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
