from ferrovault.application.services.enterprise import EnterpriseIdentity
from ferrovault.application.services.siem import MemorySiemSink
from tests.application.test_vault_service import FakeRepo, _service


def test_vault_service_exposes_enterprise_posture_and_siem_stream():
    repo = FakeRepo()
    svc = _service(repo)
    svc.init_vault("pw")
    svc.add_entry(
        "pw",
        "postgres-prod",
        "root",
        "secret",
        category="Databases",
        team_vault="Platform",
        sensitivity="critical",
        allowed_groups=("platform",),
        rotation_interval_days=30,
        totp="JBSWY3DPEHPK3PXP",
    )

    posture = svc.enterprise_posture("pw", EnterpriseIdentity(role="admin"))
    sink = MemorySiemSink()
    streamed = svc.stream_audit("pw", sink)

    assert posture.entries == 1
    assert posture.team_vaults == 1
    assert posture.high_sensitivity == 1
    assert posture.twofa_coverage_percent == 100
    assert streamed >= 2
    assert sink.events[-1].event_type == "add"
