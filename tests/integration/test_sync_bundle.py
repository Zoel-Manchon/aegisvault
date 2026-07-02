import os
import tempfile

from ferrovault.container import build_vault_service
from ferrovault.application.services.sync import SyncBundle


def test_encrypted_sync_bundle_can_restore_to_new_vault_file():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.fv")
        dst = os.path.join(d, "dst.fv")
        svc = build_vault_service(src)
        svc.init_vault("pw")
        svc.add_entry("pw", "prod-api", "svc", "secret-token")

        payload = svc.export_sync_bundle("pw", created_by="zoel", device_id="nitro")
        bundle = SyncBundle.from_json(payload)
        assert bundle.manifest.created_by == "zoel"
        assert bundle.manifest.device_id == "nitro"
        assert "secret-token" not in payload

        restored = build_vault_service(dst)
        restored.import_sync_bundle(payload)

        assert restored.get_secret("pw", "prod-api") == "secret-token"
