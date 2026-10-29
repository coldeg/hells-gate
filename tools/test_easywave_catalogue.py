"""Catalogue grouping, atomic assignments, isolation from RF and conflict checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from test_easywave_tx_result import gateway
from identification import Identification
from catalogue import Catalogue


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = json.loads(gateway.REGISTRY_FILE.read_text(encoding='utf-8'))
        self.events = {'devices': {'012345_0_0': dict(identity='012345_0_0', word='048D1428',
                                                  last_seen='2026-09-13T10:00:00Z', count=2)}}
        self.form = Identification(Path(self.temp.name) / 'labels.json', self.registry, self.events)
        self.catalogue = Catalogue(self.form)

    def request(self, operation='save', identity='012345_0_0', **extra):
        return dict(request_id='request_' + str(len(self.catalogue.receipts)), revision=self.catalogue.revision,
                    identity=identity, operation=operation, fields=dict(source='Entrée', button='Touche couloir',
                    icon='Escalier', area='Entrée', section_id='example_group_3'), **extra)

    def test_five_radio_aliases_become_four_sections_with_one_reference(self):
        view = self.catalogue.view()
        self.assertEqual(len(view['sections']), 4)
        corridor = next(s for s in view['sections'] if s['id'] == 'example_group_3')
        self.assertEqual(len(corridor['identities']), 2)
        self.assertEqual(corridor['tx_alias'], 'example_command_2')

    def test_new_assignment_joins_existing_section_without_creating_tx_and_survives_restart(self):
        before = copy.deepcopy(self.registry)
        self.assertTrue(self.catalogue.apply(self.request()))
        loaded = Identification(self.form.path, self.registry, self.events)
        view = Catalogue(loaded).view()
        self.assertEqual(len(view['sections']), 4)
        section = next(s for s in view['sections'] if s['id'] == 'example_group_3')
        self.assertEqual(len(section['identities']), 3)
        self.assertIsNone(loaded.items()['012345_0_0']['tx_alias'])
        self.assertIsNone(loaded.items()['012345_0_0']['action_id'])
        self.assertEqual(self.registry, before)

    def test_conflict_rejected_without_partial_write(self):
        request = self.request()
        self.assertTrue(self.catalogue.apply(request))
        before = copy.deepcopy(self.form.labels)
        stale = dict(request, request_id='another_client', fields=dict(request['fields'], button='Wrong'))
        self.assertFalse(self.catalogue.apply(stale))
        self.assertEqual(self.form.labels, before)
        self.assertFalse(self.catalogue.receipts[-1]['ok'])

    def test_duplicate_request_is_not_applied_twice(self):
        request = self.request()
        self.catalogue.apply(request)
        revision = self.catalogue.revision
        self.assertFalse(self.catalogue.apply(request))
        self.assertEqual(revision, self.catalogue.revision)
        self.assertEqual(len(self.catalogue.receipts), 1)

    def test_reference_change_selects_only_one_existing_alias(self):
        self.assertTrue(self.catalogue.apply(self.request('prefer', '031002_3_0')))
        section = next(s for s in self.catalogue.view()['sections'] if s['id'] == 'example_group_3')
        self.assertEqual(section['tx_alias'], 'example_command_3')
        self.assertEqual(self.form.items()['031002_3_0']['icon'], 'mdi:stairs')
        self.assertFalse(self.catalogue.apply(self.request('prefer')))

    def test_known_radio_cannot_be_reassigned_to_different_physical_action(self):
        request = self.request(identity='031003_1_1')
        self.assertFalse(self.catalogue.apply(request))
        self.assertEqual(self.form.labels, {})

    def test_ignore_is_reversible_and_does_not_identify_unknown(self):
        self.assertTrue(self.catalogue.apply(self.request('ignore')))
        item = next(i for i in self.catalogue.view()['items'] if i['identity']=='012345_0_0')
        self.assertTrue(item['ignored'])
        self.assertFalse(item['known'])
        self.assertTrue(self.catalogue.apply(self.request('restore')))
        self.assertNotIn('012345_0_0', self.form.items())

    def test_rx_updates_count_without_metadata_revision_change(self):
        revision = self.catalogue.revision
        self.events['devices']['012345_0_0']['count'] += 1
        self.assertEqual(self.catalogue.revision, revision)
        item = next(i for i in self.catalogue.view()['items'] if i['identity']=='012345_0_0')
        self.assertEqual(item['count'], 3)

    def test_create_section_has_no_radio_command(self):
        request = self.request()
        request['fields'].update(section_id='__new__', section_name='Jardin')
        self.assertTrue(self.catalogue.apply(request))
        section = next(s for s in self.catalogue.view()['sections'] if s['name']=='Jardin')
        self.assertIsNone(section['reference'])
        self.assertIsNone(section['tx_alias'])

    def test_malformed_fields_fail_closed(self):
        for value in ([], 1, {'section_id': []}, {'source': [], 'button':'x'}):
            request = self.request()
            request['fields'] = value
            self.assertFalse(self.catalogue.apply(request))
            self.assertEqual(self.form.labels, {})

    def test_latest_unknown_outside_first_hundred_is_selectable(self):
        self.registry['physical_buttons'] = [dict(identity=str(i), source='Example', button='Button') for i in range(1,101)]
        self.events['devices'] = {str(i):dict(identity=str(i), word='00000000', last_seen=str(i).zfill(3)) for i in range(101)}
        self.form.handle('latest', 'PRESS')
        self.assertEqual(self.form.selected, '0')


if __name__ == '__main__':
    unittest.main()
