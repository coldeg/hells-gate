"""Direct operation from complete RF evidence, without metadata or activation gates."""
import copy
import json
import queue
from types import SimpleNamespace
from unittest.mock import Mock
from test_easywave_catalogue import CatalogueTests
from catalogue import Catalogue
from identification import Identification
from test_easywave_tx_result import TxResultTests, gateway


class DirectCommandTests(CatalogueTests):
    def item(self, identity='012345_0_0'):
        return next(i for i in self.catalogue.view()['items'] if i['identity'] == identity)

    def recognize(self):
        self.catalogue.firmware_ready = True
        self.events['devices']['012345_0_0'].update(tail=0, frame_confirmations=2)

    def test_unnamed_recognized_button_is_actionable_without_section_or_activation(self):
        self.recognize()
        item = self.item()
        self.assertFalse(item['known'])
        self.assertIsNone(item['section_id'])
        self.assertEqual(item['command_state'], 'available')
        self.assertEqual(item['tx_alias'], 'rx_048D1428')
        self.assertFalse(self.form.path.exists())

    def test_naming_is_optional_and_never_installs_or_emits(self):
        self.recognize()
        self.catalogue.install_tx = Mock()
        request = self.request()
        request['fields']['section_id'] = ''
        self.assertTrue(self.catalogue.apply(request))
        self.assertEqual(self.item()['tx_alias'], 'rx_048D1428')
        self.catalogue.install_tx.assert_not_called()
        loaded = Catalogue(Identification(self.form.path, self.registry, self.events))
        loaded.firmware_ready = True
        self.assertEqual(next(i for i in loaded.view()['items'] if i['identity']=='012345_0_0')['tx_alias'], 'rx_048D1428')

    def test_legacy_disabled_or_unconfirmed_labels_cannot_block_recognized_buttons(self):
        self.recognize()
        self.catalogue.apply(self.request())
        self.form.labels['012345_0_0'].update(tx_enabled=False, tx_confirmed=False)
        self.assertEqual(self.item()['command_state'], 'available')
        self.assertEqual(self.item()['tx_alias'], 'rx_048D1428')
        self.form.labels['031003_1_1'] = dict(source='Example', button='Button', tx_enabled=False)
        self.assertEqual(self.item('031003_1_1')['command_state'], 'available')

    def test_partial_or_conflicting_frames_never_create_a_radio_command(self):
        self.recognize()
        event = self.events['devices']['012345_0_0']
        for invalid in ({'tail':None}, {'tail':2}, {'tail':True}, {'frame_confirmations':1}, {'frame_confirmations':'2'}):
            event.update(tail=0, frame_confirmations=2)
            event.update(invalid)
            self.assertIsNone(self.item()['tx_alias'])
            self.assertTrue(self.item()['activation_reason'])
        event.update(tail=0, frame_confirmations=2)
        self.catalogue.firmware_ready = False
        self.assertIsNone(self.item()['tx_alias'])

    def test_native_commands_remain_available_without_a_new_confirmation(self):
        self.assertEqual(self.item('031003_1_1')['command_state'], 'available')

    def test_old_disable_request_does_not_change_labels(self):
        self.recognize()
        before = copy.deepcopy(self.form.labels)
        self.assertFalse(self.catalogue.apply(self.request('disable')))
        self.assertEqual(before, self.form.labels)
        self.assertEqual(self.item()['command_state'], 'available')

    def test_area_id_survives_restart(self):
        request = self.request()
        request['fields'].update(area='Entrée', area_id='entree')
        self.assertTrue(self.catalogue.apply(request))
        loaded = Catalogue(Identification(self.form.path, self.registry, self.events))
        self.assertEqual(next(i for i in loaded.view()['items'] if i['identity']=='012345_0_0')['area_id'], 'entree')


class DirectTxTests(TxResultTests):
    def learned_bridge(self):
        bridge = self.bridge()
        bridge.by_alias = {'rx_048D1428': {'identity':'012345_0_0'}}
        bridge.identification = Mock()
        bridge.identification.command_frame.return_value = {'word':'048D1428', 'tail':0}
        bridge.catalogue.firmware_ready = True
        bridge.install_tx = Mock(return_value=True)
        bridge.wait_serial = Mock(side_effect=[('TX_ARMED', {}), ('TX_COMPLETE', {'success':'true','rx_resumed':'true'})])
        return bridge

    def test_manual_press_prepares_then_sends_once_with_client_correlation(self):
        bridge = self.learned_bridge()
        bridge.transmit('rx_048D1428', 'client_request_1234')
        bridge.install_tx.assert_called_once_with({'word':'048D1428', 'tail':0})
        writes = [c.args[0] for c in bridge.serial.write.call_args_list]
        self.assertEqual(len(writes), 2)
        self.assertTrue(writes[0].startswith(b'ARM_TX '))
        self.assertTrue(writes[1].startswith(b'TX rx_048D1428 '))
        self.assertEqual(bridge.publish_tx_result.call_args.kwargs['client_request'], 'client_request_1234')

    def test_failed_learning_never_arms_or_reserves_airtime(self):
        bridge = self.learned_bridge()
        bridge.install_tx.return_value = False
        bridge.last_install_reason = 'cache_missing'
        bridge.transmit('rx_048D1428', 'client_request_1234')
        bridge.serial.write.assert_not_called()
        bridge.budget.reserve.assert_not_called()
        self.assertEqual(bridge.publish_tx_result.call_args.args[1], 'rejected_learning')

    def test_removed_evidence_or_alias_mismatch_cannot_transmit(self):
        for frame in (None, {'word':'12345678','tail':0}):
            bridge = self.learned_bridge()
            bridge.identification.command_frame.return_value = frame
            bridge.transmit('rx_048D1428')
            bridge.install_tx.assert_not_called()
            bridge.serial.write.assert_not_called()

    def test_install_sends_only_install_not_arm_or_tx(self):
        bridge = self.bridge()
        bridge.wait_serial = Mock(return_value=('TX_INSTALLED', {'success':'true', 'word':'048D1428'}))
        self.assertTrue(bridge.install_tx({'word':'048D1428', 'tail':0}))
        self.assertEqual(bridge.serial.write.call_count, 1)
        self.assertTrue(bridge.serial.write.call_args.args[0].startswith(b'INSTALL_TX 048D1428 0 '))

    def test_json_press_is_queued_once_and_retained_replay_is_rejected(self):
        bridge = self.bridge()
        bridge.commands = queue.Queue(maxsize=1)
        message = SimpleNamespace(topic='nikobus/easywave/tx/example_command_3/set',
            payload=json.dumps({'action':'PRESS','request_id':'client_request_1234'}).encode(), retain=False)
        bridge.on_message(None,None,message)
        self.assertEqual(bridge.commands.get_nowait(), ('example_command_3','client_request_1234'))
        bridge.on_message(None,None,message)
        self.assertTrue(bridge.commands.empty())
        message.retain = True
        bridge.on_message(None,None,message)
        self.assertTrue(bridge.commands.empty())
        bridge.serial.write.assert_not_called()

    def test_partial_frames_and_false_activation_flags_are_handled_on_alias_refresh(self):
        from pathlib import Path
        import tempfile
        registry = {'physical_buttons':[], 'actions':{}}
        event = {'identity':'012345_0_0', 'word':'048D1428','tail':0,'frame_confirmations':2}
        with tempfile.TemporaryDirectory() as temporary:
            bridge = self.bridge()
            bridge.identification = Identification(Path(temporary)/'labels.json',registry,{'devices':{event['identity']:event}})
            bridge.catalogue.firmware_ready = True
            bridge.refresh_aliases()
            self.assertIn('rx_048D1428', bridge.by_alias)
            event['frame_confirmations'] = 1
            bridge.refresh_aliases()
            self.assertNotIn('rx_048D1428', bridge.by_alias)
