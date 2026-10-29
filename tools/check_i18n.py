"""Verify per-user locale behavior and capture fictional English community screenshots."""
import json
from pathlib import Path
from local_ui_browser import Browser

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs/assets'


def main():
    ASSETS.mkdir(parents=True,exist_ok=True)
    with Browser() as browser:
        browser.viewport(1280,1000)
        browser.open(ROOT/'frontend/demo.html')
        browser.js('window.card=demoCard;window.shadow=card.shadowRoot')
        assert browser.js("shadow.querySelector('nav').textContent.includes('Controls')")
        browser.screenshot(ASSETS/'ui-controls-desktop.png')
        for language,label in [('fr-BE','Pilotage'),('en-GB','Controls'),('nl-BE','Bediening'),('de-DE','Steuerung'),('ja-JP','Controls'),('not_a_locale_!','Controls')]:
            browser.js('setDemoLocale('+json.dumps(language)+')')
            assert browser.js('shadow.querySelector("nav").textContent.includes('+json.dumps(label)+')'),language
            assert browser.js("shadow.querySelector('main').textContent.includes('Desk lamp')"), 'User names must not be translated'
            for width in (390,320):
                browser.viewport(width,844)
                for page in ('commands','switches','activity'):
                    browser.js('shadow.querySelector("[data-page='+page+']").click()')
                    assert browser.js('document.documentElement.scrollWidth<=innerWidth'),(language,width,page)
            browser.viewport(1280,1000)
            browser.js("shadow.querySelector('[data-page=commands]').click()")
        # HA locale takes precedence over the browser. Editing remains local and stable.
        browser.js("setDemoLocale('fr-BE');shadow.querySelector('[data-page=switches]').click();shadow.querySelector('[data-edit=\"012345_0_0\"]').click();shadow.querySelector('#button').value='My unchanged draft';setDemoLocale('de-DE')")
        assert browser.js("shadow.querySelector('#button').value")=='My unchanged draft'
        assert browser.js("shadow.querySelector('#save').textContent")=='Speichern'
        assert browser.js('card.editId')=='012345_0_0'
        assert browser.js('demoCalls.length')==0
        browser.js("setDemoLocale('en-US')")
        browser.screenshot(ASSETS/'ui-edit-button.png')
        browser.js("card.closeDialog();setDemoLocale('en-US');demoHass.locale.time_format='12';demoHass.locale.date_format='MDY';demoCard.hass=demoHass")
        assert 'PM' in browser.js("card.locale.date('2026-10-29T13:05:00Z')")
        browser.js("demoHass.locale.time_format='24';demoHass.locale.date_format='DMY';demoCard.hass=demoHass")
        stamp=browser.js("card.locale.date('2026-10-29T13:05:00Z')")
        assert '29/10' in stamp and '14:05' in stamp,stamp
        browser.js("setDemoLocale('fr-BE')")
        assert browser.js("card.locale.number(1234.5)").endswith(',5')
        assert browser.js("card.locale.plural('associated',1)")=='1 touche associée'
        assert browser.js("card.locale.plural('associated',2)")=='2 touches associées'
        # Learning candidates survive a profile language change too.
        browser.js("card.openLearning();document.querySelector('#receive').click();setDemoLocale('nl-BE')")
        assert browser.js("shadow.querySelectorAll('#learning-list .row').length")==1
        browser.js("card.closeDialog();setDemoLocale('en-US');shadow.querySelector('[data-page=commands]').click()")
        browser.viewport(390,844)
        browser.screenshot(ASSETS/'ui-controls-mobile.png')
        assert not browser.errors,browser.errors
        report=dict(passed=True,languages=['en','fr','nl','de'],regional_variants=True,english_fallback=True,
                    user_labels_preserved=True,draft_and_learning_preserved=True,ha_time_preferences=True,
                    mobile_widths=[390,320],service_calls=0,ui_errors=[],fictional_screenshots=True)
        (ROOT/'frontend/i18n_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))


if __name__=='__main__':
    main()
