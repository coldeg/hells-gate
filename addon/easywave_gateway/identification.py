"""Local naming of received signals. No serial access and no TX commands."""
import copy
import json
import os
import re
from pathlib import Path

EMPTY = 'Choisir un signal reçu'
ICONS = {
    'Interrupteur': 'mdi:light-switch', 'Interrupteur double': 'mdi:toggle-switch-variant',
    'Plafonnier': 'mdi:ceiling-light', 'Plafonniers': 'mdi:ceiling-light-multiple',
    'Lustre': 'mdi:chandelier', 'Spots': 'mdi:track-light',
    'Appliques': 'mdi:wall-sconce-flat', 'Ruban LED': 'mdi:led-strip-variant',
    'Lampadaire': 'mdi:floor-lamp', 'Lampe de bureau': 'mdi:desk-lamp',
    'Éclairage extérieur': 'mdi:outdoor-lamp', 'Groupe de lumières': 'mdi:lightbulb-group',
    'Prise': 'mdi:power-socket-eu', 'Volet': 'mdi:window-shutter',
    'Store': 'mdi:roller-shade', 'Stores vénitiens': 'mdi:blinds',
    'Ventilateur': 'mdi:fan', 'Ventilateur de plafond': 'mdi:ceiling-fan',
    'Portail': 'mdi:gate', 'Garage': 'mdi:garage', 'Chauffage': 'mdi:radiator',
    'Pompe': 'mdi:water-pump', 'Fontaine': 'mdi:fountain', 'Piscine': 'mdi:pool',
    'Salle de bain': 'mdi:shower', 'Escalier': 'mdi:stairs',
}


class Identification:
    # I separate optional human labels from discovery evidence. A name cannot
    # replace received bits, supply a missing tail bit or authorize a transmission.
    def __init__(self, path, registry, discovery):
        self.path = Path(path)
        self.registry = registry
        self.discovery = discovery
        self.labels = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        self.selected = None
        self.source = ''
        self.button = ''
        self.icon = 'Interrupteur'
        self.result = 'Choisissez un signal, puis donnez-lui un nom.'

    def items(self):
        # This is the named/native catalogue, not the complete command-capability set.
        items = {item['identity']: copy.deepcopy(item) for item in self.registry['physical_buttons']}
        for identity, label in self.labels.items():
            if label.get('identified') is False:
                continue
            if identity not in items:
                event = self.discovery['devices'].get(identity)
                if not event:
                    continue
                items[identity] = dict(identity=identity, word=event['word'], action_id=None, tx_alias=None)
            # Naming fields cannot replace radio identity or the native RF word.
            items[identity].update(source=label['source'], button=label['button'])
            items[identity]['icon'] = ICONS.get(label.get('icon', 'Interrupteur'), ICONS['Interrupteur'])
            frame = label.get('tx_frame', {})
            if (not items[identity].get('tx_alias') and re.fullmatch(r'[0-9A-F]{8}', str(frame.get('word', '')))
                    and frame.get('word') == items[identity].get('word') and frame.get('tail') in (0, 1)):
                items[identity].update(tx_alias='rx_' + frame['word'], action_id=label.get('section_id'))
        return items

    def choices(self):
        events = sorted(self.discovery['devices'].values(), key=lambda e: e.get('last_seen', ''), reverse=True)
        identities = [e['identity'] for e in events[:100]]
        if self.selected and self.selected not in identities:
            identities.append(self.selected)
        items = self.items()
        return {identity: (f"{items[identity]['source']} · {items[identity]['button']} [{identity}]"
                           if identity in items else f'Signal {identity}') for identity in identities}

    def command_frame(self, identity):
        """Only reproduce complete RF evidence; a label never supplies radio bits."""
        event = self.discovery['devices'].get(identity, {})
        word = event.get('word', '')
        if not re.fullmatch(r'[0-9A-F]{8}', str(word)):
            return None
        confirmations = event.get('frame_confirmations', 0)
        if (type(confirmations) is int and confirmations >= 2
                and type(event.get('tail')) is int and event['tail'] in (0, 1)):
            return dict(word=word, tail=event['tail'])
        saved = self.labels.get(identity, {}).get('tx_frame', {})
        if (saved.get('word') == word and type(saved.get('tail')) is int
                and saved['tail'] in (0, 1)):
            return dict(word=word, tail=saved['tail'])
        return None

    def radio_items(self, firmware_ready):
        """Command capability is independent of naming, grouping and old activation flags."""
        items = self.items()
        for identity, event in self.discovery['devices'].items():
            items.setdefault(identity, dict(identity=identity, word=event.get('word'),
                source='', button='', icon=ICONS['Interrupteur'], action_id=None, tx_alias=None))
        for identity, item in items.items():
            if item.get('tx_alias') and not item['tx_alias'].startswith('rx_'):
                continue
            frame = self.command_frame(identity) if firmware_ready else None
            item['tx_alias'] = 'rx_' + frame['word'] if frame else None
            item['action_id'] = self.labels.get(identity, {}).get('section_id', item.get('action_id'))
        return items

    @staticmethod
    def name(value):
        value = value.strip()
        if len(value) > 80 or any(ord(c) < 32 for c in value):
            raise ValueError('Nom limité à 80 caractères, sur une seule ligne.')
        return value

    def handle(self, field, value):
        if field == 'latest' and value == 'PRESS':
            known = self.items()
            unknowns = [e for e in self.discovery['devices'].values() if e['identity'] not in known]
            if not unknowns:
                raise ValueError('Aucun signal inconnu reçu pour le moment.')
            event = max(unknowns, key=lambda e: e.get('last_seen', ''))
            self.selected = event['identity']  # Keep even an old candidate in the bounded options.
            return self.handle('signal', self.choices()[event['identity']])
        if field == 'signal':
            if value == EMPTY:
                self.selected, self.source, self.button = None, '', ''
                self.icon = 'Interrupteur'
            else:
                choices = self.choices()
                matches = [identity for identity, label in choices.items() if label == value]
                if len(matches) != 1:
                    raise ValueError('Signal absent de la liste. Choisissez-le à nouveau.')
                self.selected = matches[0]
                item = self.items().get(self.selected, {})
                self.source, self.button = item.get('source', ''), item.get('button', '')
                default_icon = next((name for name, icon in ICONS.items() if icon == item.get('icon')), 'Interrupteur')
                self.icon = self.labels.get(self.selected, {}).get('icon', default_icon)
            self.result = 'Signal sélectionné. Complétez les deux noms puis enregistrez.'
        elif field in ('source', 'button'):
            setattr(self, field, self.name(value))
        elif field == 'icon' and value in ICONS:
            self.icon = value
        elif field == 'save' and value == 'PRESS':
            if self.selected not in self.discovery['devices']:
                raise ValueError('Sélectionnez un signal effectivement reçu.')
            source, button = self.name(self.source), self.name(self.button)
            if not source or not button:
                raise ValueError('Indiquez le nom de l’interrupteur et celui de la touche.')
            updated = copy.deepcopy(self.labels)
            updated.setdefault(self.selected, {}).update(source=source, button=button, icon=self.icon,
                                                         identified=True, ignored=False)
            self.write_labels(updated)
            item = self.items()[self.selected]
            self.result = ('Attribution enregistrée. Bouton de commande existant conservé.' if item.get('tx_alias')
                           else 'Nom enregistré. Une touche reconnue est directement actionnable dans Hell’s Gate.')
            return True
        else:
            raise ValueError('Action d’attribution inconnue.')
        return False

    def write_labels(self, updated):
        # Flush a complete replacement and rename atomically; never partially save
        # one user's fields into another user's draft.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(updated, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)
        self.labels = updated

    def states(self):
        event = self.discovery['devices'].get(self.selected, {})
        choices = self.choices()
        return dict(signal=choices.get(self.selected, EMPTY), source=self.source, button=self.button, icon=self.icon,
                    result=self.result, selected=dict(identity=self.selected, last_seen=event.get('last_seen'),
                    count=event.get('count', 0), label=choices.get(self.selected, EMPTY),
                    tx_available=bool(self.items().get(self.selected, {}).get('tx_alias'))))

    def configs(self, device, availability, topic):
        fields = [('select', 'signal', 'Signal à identifier'), ('text', 'source', 'Nom de l’interrupteur'),
                  ('button', 'latest', 'Identifier le dernier signal inconnu'),
                  ('text', 'button', 'Nom de la touche'), ('select', 'icon', 'Icône de la touche'),
                  ('button', 'save', 'Enregistrer l’attribution'),
                  ('sensor', 'result', 'Résultat de l’attribution')]
        configs = []
        for component, field, name in fields:
            obj = 'identify_' + field
            config = dict(name=name, unique_id='easywave_' + obj, device=device, availability=availability)
            if component != 'sensor':
                config.update(command_topic=f'{topic}/identify/{field}/set', retain=False, qos=0)
            if component != 'button':
                config['state_topic'] = f'{topic}/identify/{field}'
            if component == 'select':
                config['options'] = list(ICONS) if field == 'icon' else [EMPTY, *self.choices().values()]
                config['icon'] = ICONS[self.icon] if field == 'icon' else 'mdi:access-point'
            elif component == 'text':
                config.update(min=0, max=80, mode='text')
            elif component == 'button':
                config['payload_press'] = 'PRESS'
            else:
                config['json_attributes_topic'] = f'{topic}/identify/selected'
                config['icon'] = ICONS[self.icon]
            configs.append((component, obj, config))
        return configs
