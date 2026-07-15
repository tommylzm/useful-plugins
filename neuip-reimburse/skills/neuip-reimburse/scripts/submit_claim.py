import argparse
import json

from scripts import neuip_client
from scripts.neuip_client import NeuipClient, AuthExpired, apply_cap


def main(argv=None, client_factory=lambda cfg, auth: NeuipClient(cfg, auth)) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--amount", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    cfg = neuip_client.load_config()
    auth = neuip_client.load_auth()
    cat = next((c for c in cfg.get("categories", []) if c["name"] == args.category), None)
    if cat is None:
        result = {"error": "unknown_category", "category": args.category}
        print(json.dumps(result, ensure_ascii=False))
        return result

    amount = apply_cap(args.amount, cat["cap"])
    client = client_factory(cfg, auth)
    try:
        resp = client.submit(args.pdf, cat["neuip_category_code"], amount, args.date, args.reason)
    except AuthExpired:
        result = {"error": "auth_expired", "hint": "run /neuip-reimburse --setup"}
        print(json.dumps(result, ensure_ascii=False))
        return result
    result = {"category": args.category, "submitted_amount": amount,
              "ok": True, "response": resp}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    import sys
    r = main()
    sys.exit(0 if r.get("ok") else 1)
