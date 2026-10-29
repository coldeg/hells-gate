"""Naming must survive restart and must never reach the RF transmit queue."""
import json
import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from test_easywave_tx_result import gateway
from identification import Identification


class IdentificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'labels.json'
        self.registry = json.loads(gateway.REGISTRY_FILE.read_text())
        self.discovery = {'devices': {
            '031003_1_1': dict(identity='031003_1_1', word='0C400D5B', count=9, last_seen='2026-09-06T10:00:00Z'),
            '012345_0_0': dict(identity='012345_0_0', word='048D1428', count=3, last_seen='2026-09-06T11:00:00Z'),
        }}
        self.form = Identification(self.path, self.registry, self.discovery)

    def fill(self, identity):
        self.form.handle('signal', self.form.choices()[identity])
        self.form.handle('source', 'Interrupteur entrée')
        self.form.handle('button', 'Plafonnier')

    def test_unknown_assignment_survives_restart_without_creating_tx(self):
        self.fill('012345_0_0')
        self.assertTrue(self.form.handle('save', 'PRESS'))
        loaded = Identification(self.path, self.registry, self.discovery)
        item = loaded.items()['012345_0_0']
        self.assertEqual(item['source'], 'Interrupteur entrée')
        self.assertEqual(item['button'], 'Plafonnier')
        self.assertIsNone(item['tx_alias'])
        self.assertIsNone(item['action_id'])

    def test_renaming_known_signal_preserves_word_alias_and_action(self):
        before = self.form.items()['031003_1_1']
        self.fill('031003_1_1')
        self.form.handle('save', 'PRESS')
        after = self.form.items()['031003_1_1']
        for field in ('word', 'tx_alias', 'action_id', 'identity'):
            self.assertEqual(before[field], after[field])

    def test_new_reception_cannot_change_selected_identity(self):
        self.fill('012345_0_0')
        self.discovery['devices']['031003_1_1']['last_seen'] = '2026-09-07T12:00:00Z'
        self.form.handle('save', 'PRESS')
        self.assertEqual(list(self.form.labels), ['012345_0_0'])

    def test_empty_and_stale_forms_are_not_saved(self):
        with self.assertRaises(ValueError):
            self.form.handle('save', 'PRESS')
        self.fill('012345_0_0')
        self.form.handle('source', ' ')
        with self.assertRaises(ValueError):
            self.form.handle('save', 'PRESS')
        self.assertFalse(self.path.exists())

    def test_mqtt_identification_cannot_enqueue_a_radio_command(self):
        bridge = gateway.EasywaveGateway.__new__(gateway.EasywaveGateway)
        bridge.identify_commands, bridge.commands = queue.Queue(), queue.Queue()
        bridge.by_alias = {i['tx_alias']: i for i in self.registry['physical_buttons'] if i.get('tx_alias')}
        bridge.publish_tx_result, bridge.serial = Mock(), Mock()
        for field, value in [('source', 'Salon'), ('button', 'Appliques'), ('save', 'PRESS')]:
            message = SimpleNamespace(topic=f'nikobus/easywave/identify/{field}/set', payload=value.encode(), retain=False)
            bridge.on_message(None, None, message)
        self.assertEqual(bridge.identify_commands.qsize(), 3)
        self.assertTrue(bridge.commands.empty())
        bridge.serial.write.assert_not_called()
        for alias in ('example_demo_a', 'example_demo_b'):
            bridge.on_message(None, None, SimpleNamespace(topic=f'nikobus/easywave/tx/{alias}/set', payload=b'PRESS', retain=False))
        self.assertTrue(bridge.commands.empty())

    def test_retained_save_is_ignored(self):
        bridge = gateway.EasywaveGateway.__new__(gateway.EasywaveGateway)
        bridge.identify_commands = queue.Queue()
        bridge.on_message(None, None, SimpleNamespace(topic='nikobus/easywave/identify/save/set', payload=b'PRESS', retain=True))
        self.assertTrue(bridge.identify_commands.empty())

    def test_latest_unknown_shortcut_freezes_identity_and_icon_persists(self):
        self.form.handle('latest', 'PRESS')
        self.assertEqual(self.form.selected, '012345_0_0')
        self.form.handle('icon', 'Appliques')
        self.form.handle('source', 'Entrée')
        self.form.handle('button', 'Mur')
        self.form.handle('save', 'PRESS')
        restored = Identification(self.path, self.registry, self.discovery)
        self.assertEqual(restored.items()['012345_0_0']['icon'], 'mdi:wall-sconce-flat')
        with self.assertRaises(ValueError):
            restored.handle('latest', 'PRESS')


if __name__ == '__main__':
    unittest.main()
