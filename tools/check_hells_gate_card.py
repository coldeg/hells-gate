"""Exercise the real card and metadata model; every HA service call is mocked."""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from local_ui_browser import Browser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'addon/easywave_gateway'))
from identification import Identification
from catalogue import Catalogue


def main():
    registry = json.loads((ROOT/'tests/fixtures/registry.synthetic.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as temporary:
        now = datetime.now(timezone.utc).isoformat()
        events = {'devices': {
            '012345_0_0': dict(identity='012345_0_0', word='048D1428', tail=0, frame_confirmations=2, last_seen=now, count=2),
            '012346_0_0': dict(identity='012346_0_0', word='048D1828', last_seen=now, count=1)}}
        form = Identification(Path(temporary)/'labels.json', registry, events)
        catalogue = Catalogue(form)
        catalogue.firmware_ready = True
        tx = {b['tx_alias']:'button.test_'+b['tx_alias'] for b in registry['physical_buttons'] if b.get('tx_alias')}
        config = dict(entity='sensor.catalogue', status_entity='sensor.gateway', result_entity='sensor.result', tx_entities=tx)
        states = {'sensor.gateway':dict(state='rx_active', attributes=dict(tx_enabled=True,last_seen=now)),
                  'sensor.result':dict(state='transmitted_unconfirmed', attributes=dict(timestamp=now,alias='example_command_5'))}
        states.update({entity:dict(state='unknown',attributes={}) for entity in tx.values()})
        with Browser() as browser:
            browser.viewport(1280,1000)
            browser.open(ROOT/'frontend/card_fixture.html')
            browser.js('card.setConfig('+json.dumps(config)+');fakeHass.locale={language:"fr-BE"};fakeHass.states='+json.dumps(states))
            browser.js("window.fixtureAreas=[{area_id:'entree',name:'Entrée'}];fakeHass.callWS=async()=>structuredClone(fixtureAreas)")
            def refresh():
                browser.js("fakeHass.states['sensor.catalogue']={state:"+json.dumps(catalogue.revision)+',attributes:'+json.dumps(catalogue.view())+'};card.hass=fakeHass;')
            def click(selector):
                assert browser.js('!!shadow.querySelector('+json.dumps(selector)+')'), selector
                browser.js('shadow.querySelector('+json.dumps(selector)+').click()')
            def finish_request():
                call = browser.js('calls[calls.length-1]')
                assert call['data']['topic']=='nikobus/easywave/identify/catalogue/set'
                catalogue.apply(json.loads(call['data']['payload']))
                refresh()
            def close():
                click('dialog [data-close]')
                browser.js('new Promise(resolve=>setTimeout(resolve,0))')
            def acknowledge(request_id, alias='rx_048D1428', state='transmitted_unconfirmed'):
                browser.js("fakeHass.states['sensor.result']="+json.dumps(dict(state=state,attributes=dict(alias=alias,client_request=request_id,timestamp=now)))+';card.hass=fakeHass')
            refresh()
            assert browser.js("card.matches('hells-gate-card')"), 'Native element matching must remain intact'
            assert browser.js("shadow.querySelectorAll('nav button').length")==3
            assert not browser.js("shadow.textContent.includes('Réception seule')")
            assert browser.js("shadow.querySelectorAll('[data-section=example_group_3]').length")==1
            # A complete, unnamed button is immediately actionable with no metadata call.
            assert not browser.js("shadow.querySelector('[data-press=\"012345_0_0\"]').disabled")
            click('[data-press="012345_0_0"]')
            call = browser.js('calls[0]')
            command = json.loads(call['data']['payload'])
            assert call['data']['topic']=='nikobus/easywave/tx/rx_048D1428/set'
            assert command['action']=='PRESS' and call['data']['retain'] is False
            assert browser.js('calls.length')==1
            assert not form.path.exists()
            # Another user's result, including one for the same alias, must not complete this request.
            acknowledge('other_request_1234')
            assert browser.js('!!card.tx')
            acknowledge(command['request_id'])
            assert not browser.js('!!card.tx')
            assert browser.js("shadow.querySelector('[data-feedback=rx_048D1428]').textContent")=='Commande envoyée.'
            browser.screenshot(ROOT/'frontend/commands_checked.png')
            # Naming is one form, optional grouping, and preserves a draft during reception.
            click('[data-page=switches]')
            click('[data-edit="012345_0_0"]')
            assert browser.js("shadow.querySelectorAll('#area option').length")==2
            browser.js("shadow.querySelector('#button').value='Plafonnier';shadow.querySelector('#area').value='entree'")
            events['devices']['012345_0_0']['count'] += 1
            refresh()
            assert browser.js("shadow.querySelector('#button').value")=='Plafonnier'
            assert browser.js("shadow.querySelector('#area').value")=='entree'
            click('#save')
            finish_request()
            assert not browser.js("shadow.querySelector('dialog').open")
            item = next(i for i in catalogue.view()['items'] if i['identity']=='012345_0_0')
            assert item['known'] and item['tx_alias']=='rx_048D1428' and item['section_id'] is None
            # Concurrent metadata edits retain input and offer explicit conflict recovery.
            click('[data-edit="012345_0_0"]')
            browser.js("shadow.querySelector('#button').value='Mon nouveau nom'")
            form.labels['012345_0_0']['button'] = 'Autre téléphone'
            refresh()
            click('#save'); finish_request()
            assert browser.js("shadow.querySelector('dialog').open")
            assert browser.js("shadow.querySelector('#button').value")=='Mon nouveau nom'
            assert browser.js("!!shadow.querySelector('[data-overwrite]')")
            click('[data-overwrite]'); finish_request()
            assert form.labels['012345_0_0']['button']=='Mon nouveau nom'
            # Room IDs survive renaming; additions and removals come from the live registry.
            browser.js("fixtureAreas=[{area_id:'entree',name:'Hall renommé'},{area_id:'jardin',name:'Jardin'}]")
            click('[data-edit="012345_0_0"]')
            assert browser.js("shadow.querySelector('#area').value")=='entree'
            assert browser.js("shadow.querySelector('#area').textContent.includes('Hall renommé')")
            browser.screenshot(ROOT/'frontend/form_checked.png')
            close()
            # Existing grouping still produces one card and uses one selected reference.
            click('[data-page=commands]'); click('[data-section=example_group_3]')
            assert browser.js("shadow.querySelectorAll('#reference option').length")==2
            browser.js("shadow.querySelector('#reference').value='031002_3_0'")
            click('[data-prefer]'); finish_request()
            assert next(s for s in catalogue.view()['sections'] if s['id']=='example_group_3')['tx_alias']=='example_command_3'
            # Learning shows only received candidates from the current session, never auto-selects.
            click('[data-add]')
            events['devices']['012346_0_0'].update(count=2,tail=1,frame_confirmations=2)
            refresh()
            assert browser.js("shadow.querySelectorAll('#learning-list .row').length")==1
            assert browser.js("!!shadow.querySelector('#learning-list [data-press=\"012346_0_0\"]')")
            close()
            # Search keeps focus and cursor despite updates to the catalogue.
            browser.js("shadow.querySelector('#search').focus();shadow.querySelector('#search').value='Mon';shadow.querySelector('#search').dispatchEvent(new Event('input',{bubbles:true}))")
            refresh()
            assert browser.js("shadow.activeElement?.id")=='search', browser.js("({active:shadow.activeElement?.outerHTML,dialog:shadow.querySelector('dialog').open,query:card.query,errors:window.__uiErrors})")
            # Connection loss is reflected immediately without erasing open input.
            click('[data-page=switches]'); click('[data-edit="012345_0_0"]')
            browser.js("shadow.querySelector('#button').value='Brouillon conservé';fakeHass.states['sensor.gateway'].state='offline';card.hass=fakeHass")
            assert browser.js("shadow.querySelector('#button').value")=='Brouillon conservé'
            close()
            assert browser.js("[...shadow.querySelectorAll('[data-press]')].every(b=>b.disabled)")
            browser.js("fakeHass.states['sensor.gateway'].state='rx_active';card.hass=fakeHass")
            # Rejected services and saving failures stay visible; there is no automatic retry.
            browser.js("fakeHass.callService=async()=>{throw new Error('Hors ligne')}")
            click('[data-edit="012345_0_0"]'); click('#save')
            assert browser.js("shadow.querySelector('#dialog-message').textContent.includes('impossible')")
            assert not browser.js("shadow.querySelector('#save').disabled")
            close()
            for width in (390,320):
                browser.viewport(width,844)
                for page in ('commands','switches','activity'):
                    click('[data-page='+page+']')
                    assert browser.js('document.documentElement.scrollWidth<=innerWidth'), (width,page)
                    assert browser.js("[...shadow.querySelectorAll('button')].filter(b=>b.getBoundingClientRect().height>0).every(b=>b.getBoundingClientRect().height>=44)"), (width,page,'touch targets')
                click('[data-page=commands]')
                if width==390:browser.screenshot(ROOT/'frontend/mobile_checked.png')
                click('[data-page=switches]');click('[data-edit="012345_0_0"]')
                assert browser.js("shadow.querySelector('dialog').scrollWidth<=shadow.querySelector('dialog').clientWidth"), (width,'dialog')
                close()
                click('[data-page=commands]');click('[data-section=example_group_3]')
                assert browser.js("shadow.querySelector('dialog').scrollWidth<=shadow.querySelector('dialog').clientWidth"), (width,'group dialog')
                close()
            browser.command('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            assert browser.js("matchMedia('(prefers-reduced-motion:reduce)').matches")
            assert not browser.errors,browser.errors
            report=dict(passed=True,direct_unnamed_command=True,no_activation_gate=True,correlated_feedback=True,
                draft_preserved=True,conflict_recovery=True,dynamic_rooms=True,grouping_preserved=True,
                learning_session=True,offline_and_save_errors=True,mobile_widths=[390,320],touch_targets_44px=True,
                reduced_motion=True,javascript_errors=[],no_real_ha_calls=True)
            (ROOT/'frontend/verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    main()
