"""Regression tests for serial acknowledgments and honest RF result reporting."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "addon/easywave_gateway/gateway.py"
SPEC = importlib.util.spec_from_file_location("easywave_addon", SOURCE)
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)
gateway.REGISTRY_FILE = Path(__file__).resolve().parents[1] / "tests/fixtures/registry.synthetic.json"


class TxResultTests(unittest.TestCase):
    def test_budget_status_refresh_is_periodic_and_forceable_without_tx(self):
        bridge = self.bridge()
        with patch.object(gateway.time, 'monotonic', side_effect=[100., 159., 160., 161.]):
            bridge.refresh_status()
            bridge.refresh_status()
            self.assertEqual(bridge.serial.write.call_count, 1)
            bridge.refresh_status()
            self.assertEqual(bridge.serial.write.call_count, 2)
            bridge.refresh_status(force=True)
        self.assertEqual(bridge.serial.write.call_count, 3)
        self.assertTrue(all(c.args == (b'STATUS\n',) for c in bridge.serial.write.call_args_list))

    def test_retired_test_buttons_are_removed_from_discovery(self):
        bridge = self.bridge()
        bridge.by_identity = {}
        bridge.publish_config = Mock()
        bridge.client = Mock()
        bridge.publish_static_discovery()
        buttons = [c.args[2] for c in bridge.publish_config.call_args_list if c.args[0] == 'button']
        self.assertEqual(buttons, [])
        self.assertEqual({c.args[0] for c in bridge.client.publish.call_args_list},
                         {f'homeassistant/button/easywave/tx_example_demo_{v}/config' for v in ('a', 'b')})
        self.assertTrue(all(c.args[1] == '' for c in bridge.client.publish.call_args_list))

    def test_campaign_serial_alias_and_polarity_are_preserved(self):
        for variant, polarity in [('a', 'normal'), ('b', 'inverted')]:
            bridge = self.bridge()
            bridge.wait_serial = Mock(side_effect=[('TX_ARMED', {}), ('TX_COMPLETE',
                {'success': 'true', 'rx_resumed': 'true', 'polarity': polarity})])
            with patch.object(gateway.secrets, 'token_hex', return_value='aaaaaaaa'):
                bridge.transmit('example_demo_' + variant)
            self.assertEqual(bridge.serial.write.call_args.args[0],
                             f'TX example_demo_{variant} AAAAAAAA\n'.encode())
            self.assertEqual(bridge.publish_tx_result.call_args.kwargs['polarity'], polarity)

    def bridge(self):
        bridge = gateway.EasywaveGateway.__new__(gateway.EasywaveGateway)
        bridge.serial = Mock()
        bridge.budget = Mock()
        bridge.budget.reserve.return_value = (True, "reserved", 0)
        bridge.publish_tx_result = Mock()
        bridge.by_alias = dict.fromkeys(['example_command_3', 'example_demo_a', 'example_demo_b'])
        bridge.tx_enabled = True
        bridge.catalogue = Mock()
        bridge.publish_identification = Mock()
        return bridge

    def test_unrelated_or_missing_nonce_cannot_acknowledge(self):
        bridge = self.bridge()
        bridge.serial.readline.side_effect = [
            b"TX_COMPLETE success=true\n",
            b"TX_COMPLETE request=BBBBBBBB success=true\n",
            b"TX_COMPLETE request=AAAAAAAA success=true\n",
        ]
        kind, fields = bridge.wait_serial("AAAAAAAA", {"TX_COMPLETE"}, 1)
        self.assertEqual(kind, "TX_COMPLETE")
        self.assertEqual(fields["request"], "AAAAAAAA")
        self.assertEqual(bridge.serial.readline.call_count, 3)

    def test_legacy_uncorrelated_rejection_fails_closed(self):
        bridge = self.bridge()
        bridge.serial.readline.return_value = b"COMMAND_REJECT reason=invalid_tx_command\n"
        self.assertEqual(bridge.wait_serial("AAAAAAAA", {"COMMAND_REJECT"}, 1)[0], "COMMAND_REJECT")

    def transmit_result(self, fields):
        bridge = self.bridge()
        bridge.wait_serial = Mock(side_effect=[("TX_ARMED", {}), ("TX_COMPLETE", fields)])
        with patch.object(gateway.secrets, "token_hex", return_value="aaaaaaaa"):
            bridge.transmit("example_command_3")
        return bridge.publish_tx_result.call_args

    def test_radio_completion_is_not_physical_success(self):
        call = self.transmit_result({"success": "true", "rx_resumed": "true", "airtime_us": "95928"})
        self.assertEqual(call.args[1], "transmitted_unconfirmed")
        self.assertFalse(call.kwargs["physical_state_confirmed"])
        self.assertEqual(call.kwargs["airtime_us"], 95928)
        self.assertEqual(call.kwargs["reserved_airtime_us"], gateway.BURST_AIRTIME_US)

    def test_rx_restore_failure_remains_visible(self):
        call = self.transmit_result({"success": "true", "rx_resumed": "false"})
        self.assertEqual(call.args[1], "transmitted_rx_failed")
        self.assertIsNone(call.kwargs["airtime_us"])

    def test_invalid_airtime_is_not_fabricated(self):
        call = self.transmit_result({"success": "false", "airtime_us": "bad"})
        self.assertEqual(call.args[1], "failed_firmware")
        self.assertIsNone(call.kwargs["airtime_us"])


if __name__ == "__main__":
    unittest.main()
