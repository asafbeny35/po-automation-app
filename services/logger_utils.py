import json

def log_po(po, title="PO DEBUG"):
    print(f"\n===== {title} =====")
    try:
        if hasattr(po, "model_dump"):
            print(json.dumps(po.model_dump(), ensure_ascii=False, indent=2))
        elif hasattr(po, "dict"):
            print(json.dumps(po.dict(), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(vars(po), ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        print("log_po failed:", repr(e))
    print(f"===== END {title} =====\n")
