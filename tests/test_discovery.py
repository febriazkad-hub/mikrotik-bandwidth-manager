import pytest
from app.discovery import RouterDiscovery
from tests.mock_ros import RouterOSMock

def test_detect_wan_from_default_route():
    mock = RouterOSMock()
    route_output = ' 0 A S  dst-address=0.0.0.0/0 gateway=192.168.1.1 gateway-status="192.168.1.1 reachable via ether1" distance=1 scope=30'
    wan = RouterDiscovery.detect_wan_interface(route_output)
    assert wan == "ether1"

def test_detect_wan_fallback_dhcp():
    route_output = ""
    dhcp_output = ' 0   interface=pppoe-out1 status=bound address=10.0.0.2/32'
    wan = RouterDiscovery.detect_wan_interface(route_output, dhcp_output)
    assert wan == "pppoe-out1"

def test_detect_lan_bridge():
    bridge_output = ' 0 R  name=bridge mtu=auto actual-mtu=1500 l2mtu=1598 mac-address=00:0C:42:01:02:03 arp=enabled'
    lan = RouterDiscovery.detect_lan_bridge(bridge_output)
    assert lan == "bridge"

def test_parse_ros_resource_v6():
    res_text = (
        "version: 6.49.15 (long-term)\n"
        "board-name: hAP lite\n"
        "architecture-name: smips\n"
        "cpu-load: 12\n"
    )
    info = RouterDiscovery.parse_version_and_arch(res_text)
    assert info["board_name"] == "hAP lite"
    assert info["version"] == "6.49.15 (long-term)"
    assert info["major_version"] == 6
    assert info["architecture"] == "smips"

def test_parse_ros_resource_v7():
    res_text = (
        "version: 7.14.3 (stable)\n"
        "board-name: hAP ax2\n"
        "architecture-name: arm64\n"
        "cpu-load: 5\n"
    )
    info = RouterDiscovery.parse_version_and_arch(res_text)
    assert info["board_name"] == "hAP ax2"
    assert info["major_version"] == 7
    assert info["architecture"] == "arm64"
