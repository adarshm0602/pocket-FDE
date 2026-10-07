"""Private, immutable analysis snapshots. No API keys or session tokens stored."""
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

RECORD = re.compile(r"^[0-9]{20}-[a-f0-9]{12}$")


class DemoLimit(Exception):
    pass


class WorkspaceStore:
    def __init__(self):
        self.token = os.getenv("BLOB_READ_WRITE_TOKEN")
        self.root = Path(os.getenv("POCKET_FDE_DATA_DIR", str(Path.home() / ".local/share/pocket-fde")))

    @property
    def mode(self):
        return "private cloud storage" if self.token else "local disk"

    def _client(self):
        from vercel.blob import BlobClient
        return BlobClient(token=self.token)

    def _path(self, identity, record):
        if not re.fullmatch(r"[a-f0-9]{32}", identity) or not RECORD.fullmatch(record):
            raise ValueError("Invalid saved analysis identifier")
        return f"workspaces/{identity}/{record}.json"

    def save(self, identity, incident, analysis):
        if os.getenv("VERCEL") and not self.token:
            raise RuntimeError("Private cloud storage is not configured")
        record = f"{time.time_ns():020d}-{uuid4().hex[:12]}"
        path = self._path(identity, record)
        data = {"id": record, "created_at": time.time(), "incident": incident, "analysis": analysis}
        content = json.dumps(data, ensure_ascii=False).encode()
        if self.token:
            with self._client() as client:
                client.put(path, content, access="private", content_type="application/json", overwrite=False)
        else:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("xb") as stream:
                os.chmod(target, 0o600)
                stream.write(content)
        return record

    def get(self, identity, record):
        path = self._path(identity, record)
        if self.token:
            from vercel.blob.errors import BlobNotFoundError
            with self._client() as client:
                try:
                    result = client.get(path, access="private")
                except BlobNotFoundError:
                    return None
                return json.loads(result.content) if result and result.status_code == 200 else None
        target = self.root / path
        return json.loads(target.read_bytes()) if target.exists() else None

    def recent(self, identity):
        prefix = f"workspaces/{identity}/"
        if not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise ValueError("Invalid workspace")
        if self.token:
            # Immutable names use reverse sorting; pagination keeps history intact.
            with self._client() as client:
                names = [item.pathname.rsplit("/", 1)[-1][:-5]
                         for item in client.iter_objects(prefix=prefix)]
        else:
            names = [p.stem for p in (self.root / prefix).glob("*.json")]
        records = []
        for name in sorted(names, reverse=True)[:20]:
            data = self.get(identity, name)
            if data:
                records.append({"id": name, "title": data["incident"]["title"],
                                "created_at": data["created_at"],
                                "retrieval_mode": data["analysis"]["retrieval_mode"]})
        return records

    def reserve_model_call(self, identity):
        """Persist limits across replicas: 15-second cooldown, 50 model requests/day.

        Immutable slot names cannot be overwritten; competing reservations fail
        closed. Failed provider calls also consume a slot, limiting repeated costs.
        """
        if not os.getenv("VERCEL"):
            return
        if not self.token:
            raise RuntimeError("Private cloud storage is not configured")
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prefix = f"limits/{day}/requests/"
        cooldown = f"limits/{day}/cooldown/{identity}/{int(time.time() // 15)}.json"
        with self._client() as client:
            slots = client.list_objects(prefix=prefix, limit=50).blobs
            if len(slots) >= 50:
                raise DemoLimit("The demo's daily model limit is reached. Try tomorrow.")
            # Both writes are create-only: concurrent requests cannot claim the
            # same cooldown or budget slot. Never refund a reserved paid request.
            try:
                client.put(cooldown, b'{}', access="private", overwrite=False)
                client.put(f"{prefix}{len(slots):03d}.json", b'{}', access="private", overwrite=False)
            except Exception as exc:
                raise DemoLimit("Please wait 15 seconds before another model request. If saving is unavailable, model calls pause until it recovers.") from exc
