"""One-shot script to inject an e2e-test homie_proxy config entry.
Run inside the ha-dev container before restarting HA."""
import json
import datetime

PATH = "/config/.storage/core.config_entries"

with open(PATH) as f:
    doc = json.load(f)

# Remove any prior e2e entry so reruns are idempotent.
doc["data"]["entries"] = [
    e for e in doc["data"]["entries"]
    if e.get("entry_id") != "homieproxy_e2e_test_01"
]

now = datetime.datetime.now(datetime.timezone.utc).isoformat()
doc["data"]["entries"].append({
    "created_at": now,
    "modified_at": now,
    "entry_id": "homieproxy_e2e_test_01",
    "domain": "homie_proxy",
    "title": "HomieProxy — testroute",
    "source": "user",
    "minor_version": 1,
    "version": 1,
    "data": {
        "name": "testroute",
        "tokens": ["e2e-token-abc"],
        "restrict_out": "any",
        "restrict_out_cidrs": [],
        "restrict_in_cidrs": [],
        "requires_auth": False,
        "timeout": 30,
        "stream_chunk_size": 0,
    },
    "options": {},
    "subentries": [],
    "disabled_by": None,
    "discovery_keys": {},
    "pref_disable_new_entities": False,
    "pref_disable_polling": False,
    "unique_id": None,
})

with open(PATH, "w") as f:
    json.dump(doc, f, indent=2)
print("INJECTED")
