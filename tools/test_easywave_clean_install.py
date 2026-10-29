"""Fresh production state and passive reception, with serial/MQTT fully mocked."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from test_easywave_tx_result import gateway

ROOT = Path(__file__).resolve().parents[1]


class CleanInstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        production = ROOT / 'addon/easywave_gateway/registry.json'
        overrides = dict(DATA_DIR=folder, DISCOVERY_FILE=folder/'discovery.json',
                         TX_HISTORY_FILE=folder/'tx_history.json', EVENT_LOG_FILE=folder/'events.jsonl',
                         EXPORT_DIR=folder/'mirror', EXPORT_DISCOVERY_FILE=folder/'mirror/discovery.json',
                         EXPORT_EVENT_LOG_FILE=folder/'mirror/events.jsonl', REGISTRY_FILE=production)
        changes = patch.multiple(gateway, **overrides)
        changes.start()
        self.addCleanup(changes.stop)
        environment = patch.dict('os.environ', EASYWAVE_MQTT_USERNAME='offline-test',
                                 EASYWAVE_MQTT_PASSWORD='not-a-credential', EASYWAVE_TX_ENABLED='false')
        environment.start()
        self.addCleanup(environment.stop)
        self.serial = Mock()
        self.client = Mock()
        paho = types.ModuleType('paho')
        mqtt = types.ModuleType('paho.mqtt')
        client = types.ModuleType('paho.mqtt.client')
        client.Client = Mock(return_value=self.client)
        client.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
        paho.mqtt, mqtt.client = mqtt, client
        serial = types.ModuleType('serial')
        serial.Serial = Mock(return_value=self.serial)
        with patch.dict(sys.modules, {'paho': paho, 'paho.mqtt': mqtt,
                                    'paho.mqtt.client': client, 'serial': serial}):
            self.bridge = gateway.EasywaveGateway()

    def test_production_starts_without_devices_or_commands(self):
        self.assertEqual(self.bridge.registry, {'actions': {}, 'physical_buttons': []})
        self.assertEqual(self.bridge.discovery, {'devices': {}})
        self.assertEqual(self.bridge.by_alias, {})
        self.assertEqual(self.bridge.identification.labels, {})
        self.assertEqual(self.bridge.catalogue.view()['items'], [])
        self.assertFalse(self.bridge.tx_enabled)
        self.serial.write.assert_not_called()
        self.client.connect.assert_not_called()

    def test_passive_reception_discovers_an_unnamed_button_without_tx(self):
        self.bridge.catalogue.firmware_ready = True
        self.bridge.frames['048D1428'] = {'tail': 0, 'frame_confirmations': 2}
        self.bridge.process_event(dict(word='048D1428', serial22='012345', key2='0',
                                       side_variant='0', rssi_dbm='-55', plausibility_valid='true'))
        self.assertEqual(len(self.bridge.discovery['devices']), 1)
        self.assertEqual(self.bridge.identification.labels, {})
        self.assertIn('rx_048D1428', self.bridge.by_alias)
        self.assertEqual(len(self.bridge.catalogue.view()['items']), 1)
        self.serial.write.assert_not_called()
        self.client.connect.assert_not_called()
        self.assertTrue(any(call.args[0] == 'nikobus/easywave/rx/event' for call in self.client.publish.call_args_list))


if __name__ == '__main__':
    unittest.main()
