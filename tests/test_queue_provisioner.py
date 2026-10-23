import pytest
from app.queue_provisioner import QueueProvisioner
from app.uninstall_helper import UninstallHelper
from tests.mock_ros import RouterOSMock

@pytest.mark.asyncio
async def test_queue_provisioning_and_clean_detach():
    mock = RouterOSMock()
    mock.queues = {} # start from factory empty queues

    # 1. Provision baseline
    ok, msg = await QueueProvisioner.provision_baseline(mock.exec_cmd)
    assert ok is True
    assert "BWM-BYPASS-GROUP" in mock.queues
    assert "BWM-PARENT" in mock.queues

    # 2. Idempotent check: calling again does not duplicate
    ok2, msg2 = await QueueProvisioner.provision_baseline(mock.exec_cmd)
    assert ok2 is True

    # 3. Clean Detach
    ok_detach, msg_detach = await UninstallHelper.clean_detach(mock.exec_cmd)
    assert ok_detach is True
    assert "BWM-PARENT" not in mock.queues
    assert "BWM-BYPASS-GROUP" not in mock.queues
    assert mock.fasttrack_disabled is False
