"""Atomic naming and grouping; complete recognized commands are directly usable."""
import copy
import hashlib
import json
import re
import uuid
import time


class Catalogue:
    # Presentation model and atomic metadata API. I do not perform serial I/O here.
    def __init__(self, identification):
        self.form = identification
        self.receipts = []
        self.install_tx = None
        self.firmware_ready = False
        self.tests = {}

    def record_tx(self, alias, nonce, success):
        for item in self.form.items().values():
            if item.get('tx_alias') == alias:
                identity = item['identity']
                self.tests.pop(identity, None)
                if success:
                    self.tests[identity] = dict(nonce=nonce, at=time.time(), revision=self.revision)

    def command_state(self, identity, item, label):
        return 'available' if item.get('tx_alias') else 'learning'

    @property
    def revision(self):
        # Receptions change counters/timestamps, not this metadata revision. A form
        # stays editable while radio observations continue in the background.
        value = {'labels': self.form.labels, 'registry': self.form.registry}
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()[:20]

    def view(self):
        # Join optional labels, observations and radio capability by stable identity.
        from identification import ICONS
        known = self.form.items()
        radio = self.form.radio_items(self.firmware_ready)
        devices = self.form.discovery['devices']
        entries = []
        for identity in sorted(set(known) | set(devices)):
            item, event = radio.get(identity, {}), devices.get(identity, {})
            label = self.form.labels.get(identity, {})
            entries.append(dict(identity=identity, serial=identity.split('_')[0],
                known=identity in known, source=item.get('source', ''), button=item.get('button', ''),
                icon=item.get('icon', ICONS['Interrupteur']), icon_choice=label.get('icon', next(
                    (k for k, v in ICONS.items() if v == item.get('icon')), 'Interrupteur')),
                area=label.get('area', ''), area_id=label.get('area_id', ''), position=label.get('position', ''),
                ignored=label.get('ignored', False),
                section_id=label.get('section_id', item.get('action_id')),
                tx_alias=item.get('tx_alias'),
                command_state=self.command_state(identity, item, label),
                can_activate=bool(item.get('tx_alias')),
                activation_reason=('' if item.get('tx_alias') else
                    'La passerelle doit être mise à jour pour reproduire cette touche.' if not self.firmware_ready else
                    'Appuyez sur la touche physique pour terminer la reconnaissance du signal.'),
                test_nonce=self.tests.get(identity, {}).get('nonce') if time.time()-self.tests.get(identity, {}).get('at', 0)<600 and self.tests.get(identity, {}).get('revision') == self.revision else None,
                last_seen=event.get('last_seen'), count=event.get('count', 0)))
        sections = {key: dict(id=key, name=name) for key, name in self.form.registry['actions'].items()}
        for label in self.form.labels.values():
            if label.get('section_id') and label.get('section_name'):
                sections.setdefault(label['section_id'], dict(id=label['section_id'], name=label['section_name']))
        for section in sections.values():
            # A group chooses one source button. Pressing a group is not a broadcast
            # to every associated switch and does not reprogram its physical target.
            members = [e for e in entries if e['section_id'] == section['id']]
            eligible = [e for e in members if e['tx_alias']]
            preferred = next((e for e in eligible if self.form.labels.get(e['identity'], {}).get('preferred')), None)
            # Existing verified four-touch corridor is the default over its alternate source.
            default = next((e for e in eligible if e['tx_alias'] == 'example_command_2'), None)
            chosen = preferred or default or next(iter(eligible), None)
            section.update(identities=[e['identity'] for e in members],
                reference=chosen['identity'] if chosen else None,
                tx_alias=chosen['tx_alias'] if chosen else None,
                icon=chosen['icon'] if chosen else (members[0]['icon'] if members else ICONS['Interrupteur']),
                needs_review=bool(chosen and chosen['command_state'] == 'review'))
        return dict(schema_version=4, revision=self.revision, items=entries, sections=list(sections.values()),
                    icons=ICONS, receipts=list(self.receipts))

    def apply(self, request):
        # Validate the revision, edit a copy, persist once, then publish one receipt.
        # Repeated request IDs cannot commit the same write twice.
        from identification import ICONS
        if not isinstance(request, dict):
            raise ValueError('Requête invalide.')
        request_id = request.get('request_id', '')
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', request_id):
            raise ValueError('Identifiant de requête invalide.')
        # QoS retries must not commit twice or overwrite a newer draft.
        if any(r['request_id'] == request_id for r in self.receipts):
            return False
        try:
            if request.get('revision') != self.revision:
                raise ValueError('Le catalogue a changé. Fermez puis rouvrez la fiche avant de réessayer.')
            identity = request.get('identity')
            current = next((e for e in self.view()['items'] if e['identity'] == identity), None)
            if not current:
                raise ValueError('Cette touche n’est plus disponible.')
            updated = copy.deepcopy(self.form.labels)
            label = updated.setdefault(identity, dict(source=current['source'], button=current['button'],
                                                      icon=current['icon_choice'], identified=current['known']))
            operation = request.get('operation', 'save')
            if operation in ('ignore', 'restore'):
                label['ignored'] = operation == 'ignore'
            elif operation == 'activate':
                # Compatibility with a cached old card; activation is no longer a prerequisite.
                if not current['tx_alias']:
                    raise ValueError(current['activation_reason'])
                label.update(tx_enabled=True)
            elif operation == 'disable':
                raise ValueError('Les touches reconnues sont directement utilisables. Rechargez Hell’s Gate.')
            elif operation in ('confirm', 'review'):
                if not current['tx_alias']:
                    raise ValueError('Activez d’abord cette commande.')
                if operation == 'confirm':
                    proof = self.tests.get(identity, {})
                    if (not proof.get('nonce') or request.get('fields', {}).get('test_nonce') != proof['nonce']
                            or time.time()-proof.get('at', 0) > 600 or proof.get('revision') != self.revision):
                        raise ValueError('Testez cette touche depuis HA avant de confirmer son effet.')
                label['tx_confirmed'] = operation == 'confirm'
                self.tests.pop(identity, None)
            elif operation == 'prefer':
                if not current['tx_alias'] or not current['section_id']:
                    raise ValueError('Cette touche ne possède pas de commande radio disponible.')
                for entry in self.view()['items']:
                    if entry['section_id'] == current['section_id'] and entry['identity'] in updated:
                        updated[entry['identity']]['preferred'] = False
                label['preferred'] = True
            elif operation == 'save':
                fields = request.get('fields')
                if not isinstance(fields, dict):
                    raise ValueError('Formulaire incomplet.')
                text = {}
                for key in ('source', 'button', 'area', 'area_id', 'position'):
                    value = fields.get(key, '')
                    if not isinstance(value, str):
                        raise ValueError('Un nom doit être du texte.')
                    text[key] = self.form.name(value)
                if not text['source'] or not text['button']:
                    raise ValueError('Renseignez le nom de l’interrupteur et de la touche.')
                if fields.get('icon') not in ICONS:
                    raise ValueError('Choisissez une icône de la liste.')
                section = fields.get('section_id') or None
                if section is not None and not isinstance(section, str):
                    raise ValueError('Section invalide.')
                sections = {s['id']: s for s in self.view()['sections']}
                if section == '__new__':
                    name = fields.get('section_name', '')
                    if not isinstance(name, str) or not self.form.name(name):
                        raise ValueError('Donnez un nom à la nouvelle section.')
                    name = self.form.name(name)
                    if any(s['name'].casefold() == name.casefold() for s in sections.values()):
                        raise ValueError('Cette section existe déjà : sélectionnez-la dans la liste.')
                    section = 'section_' + uuid.uuid4().hex[:12]
                    label['section_name'] = name
                elif section and section not in sections:
                    raise ValueError('Section absente du catalogue.')
                # A label never changes what an already-programmed RF word actually does.
                native = next((b for b in self.form.registry['physical_buttons'] if b['identity'] == identity), {})
                if native.get('tx_alias') and section != native.get('action_id'):
                    raise ValueError('Cette commande radio reste liée à son éclairage existant.')
                if section in sections:
                    label['section_name'] = sections[section]['name']
                if section != current['section_id']:
                    label['tx_confirmed'] = False
                    self.tests.pop(identity, None)
                label.update(text, icon=fields['icon'], section_id=section, identified=True, ignored=False)
            else:
                raise ValueError('Opération inconnue.')
            self.form.write_labels(updated)
            receipt = dict(request_id=request_id, ok=True, identity=identity, message='Fiche enregistrée.')
        except (ValueError, OSError, TypeError, AttributeError) as error:
            receipt = dict(request_id=request_id, ok=False, message=str(error),
                           code='conflict' if request.get('revision') != self.revision else 'invalid')
        self.receipts = (self.receipts + [receipt])[-20:]
        return receipt['ok']
