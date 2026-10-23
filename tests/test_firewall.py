import pytest
from app.firewall_helper import FirewallHelper
from tests.mock_ros import RouterOSMock

@pytest.mark.asyncio
async def test_fasttrack_lifecycle():
    mock = RouterOSMock()

    # 1. Initial status: FastTrack is active
    status = await FirewallHelper.check_fasttrack_status(mock.exec_cmd)
    assert status["exists"] is True
    assert status["is_active"] is True

    # 2. Safely disable FastTrack for Simple Queue QoS
    ok, msg = await FirewallHelper.disable_fasttrack_safe(mock.exec_cmd)
    assert ok is True
    assert mock.fasttrack_disabled is True

    # Check status again
    status_disabled = await FirewallHelper.check_fasttrack_status(mock.exec_cmd)
    assert status_disabled["exists"] is True
    assert status_disabled["is_active"] is False

    # 3. Restore FastTrack back to factory state
    ok, msg = await FirewallHelper.restore_fasttrack(mock.exec_cmd)
    assert ok is True
    assert mock.fasttrack_disabled is False

    status_restored = await FirewallHelper.check_fasttrack_status(mock.exec_cmd)
    assert status_restored["is_active"] is True
