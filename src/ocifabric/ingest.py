import json
from datetime import datetime
from pathlib import Path

from .watermark import next_watermark, select_new_objects


def list_all_objects(client, namespace, bucket, prefix):
    objects, start = [], None
    while True:
        resp = client.list_objects(
            namespace, bucket, prefix=prefix, fields="name,size,timeModified", start=start
        )
        objects.extend(resp.data.objects)
        start = resp.data.next_start_with
        if not start:
            return objects


def load_state(state_path):
    path = Path(state_path)
    if not path.exists():
        return None
    return datetime.fromisoformat(json.loads(path.read_text())["watermark"])


def save_state(state_path, watermark):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"watermark": watermark.isoformat()}))


def ingest(client, namespace, bucket, prefix, landing_dir, state_path, lookback_minutes=60):
    last = load_state(state_path)
    picked = select_new_objects(
        list_all_objects(client, namespace, bucket, prefix), last, lookback_minutes
    )
    landing = Path(landing_dir).resolve()
    for obj in picked:
        target = (landing / obj.name).resolve()
        if not target.is_relative_to(landing):
            raise ValueError(f"object name escapes landing dir: {obj.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(client.get_object(namespace, bucket, obj.name).data.content)
    # State is committed only after every file lands, so a crashed run just re-runs.
    watermark = next_watermark(picked, last)
    if watermark is not None:
        save_state(state_path, watermark)
    return [o.name for o in picked]


def oci_client_from_secrets(user, tenancy, fingerprint, key_content, region):
    import oci

    config = {
        "user": user,
        "tenancy": tenancy,
        "fingerprint": fingerprint,
        "key_content": key_content,
        "region": region,
    }
    return oci.object_storage.ObjectStorageClient(config)
