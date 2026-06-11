CONFIG_FILE = "config.txt"

def load_config() -> dict:
    config = {}
    current_key = None
    current_list = []

    with open(CONFIG_FILE, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line and not raw_line.startswith((" ", "\t")):
                if current_key and current_list:
                    config[current_key] = current_list
                    current_list = []

                key, _, value = line.partition("=")
                key   = key.strip()
                value = value.strip()

                if value:
                    config[key] = value
                    current_key = None
                else:
                    current_key  = key
                    current_list = []

            elif current_key and raw_line.startswith((" ", "\t")):
                item = line.strip()
                if item:
                    current_list.append(item)

    if current_key and current_list:
        config[current_key] = current_list

    return config

def get_config():
    raw = load_config()
    return {
        "product_name":         raw.get("product_name", "Unknown Product"),
        "keywords":             [k.strip() for k in raw.get("keywords", "").split(",")],
        "url_must_contain":     raw.get("url_must_contain", ""),
        "relevant_url_parts":   raw.get("relevant_url_parts", []),  # ← новое
        "seed_urls":            raw.get("seed_urls", []),
        "allowed_domains":      raw.get("allowed_domains", []),
        "skip_urls":            raw.get("skip_urls", []),
        "max_pages":            int(raw.get("max_pages", 300)),
        "max_pages_per_domain": int(raw.get("max_pages_per_domain", 100)),
        "max_depth":            int(raw.get("max_depth", 3)),
        "delay":                float(raw.get("delay", 1.0)),
        "telegram_token":       raw.get("telegram_token", ""),
        "telegram_chat_id":     raw.get("telegram_chat_id", ""),
    }

if __name__ == "__main__":
    import json
    cfg = get_config()
    print("✅ Конфиг прочитан:\n")
    print(json.dumps(cfg, ensure_ascii=False, indent=2))