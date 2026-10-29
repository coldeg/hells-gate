/** Hell's Gate card: local controls, optional naming and per-user HA locale. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  } [c]));
  const icon = name =>
    `<ha-icon aria-hidden="true" icon="${esc(name || 'mdi:light-switch')}"></ha-icon>`;
  const requestId = () => globalThis.crypto?.randomUUID?.() || 'hg_' + Date.now().toString(36) +
    '_' + Math.random().toString(36).slice(2);
  const css = HG_CARD_CSS;

  class HellsGateCard extends HTMLElement {
    // UI state is local to this card instance. I never store a shared form in MQTT.
    constructor() {
      super();
      this.locale = new HellsGateLocale();
      this.attachShadow({
        mode: 'open'
      });
      this.page = 'commands';
      this.filter = 'all';
      this.query = '';
      this.areas = [];
      this.feedback = new Map();
      this.message = '';
      this.pending = null;
      this.tx = null;
      this.shadowRoot.innerHTML =
        `<style>${css}</style><ha-card><header><div class="brand"><span class="brand-icon">${icon('mdi:gate')}</span><div><h1>Hell’s Gate</h1><span id="health" class="health">${this.t('connecting')}</span></div></div><button class="primary" data-add>${icon('mdi:plus')} ${this.t('add')}</button></header><nav aria-label="${this.t('navigation')}"></nav><div id="message" role="status" aria-live="polite"></div><main></main></ha-card><dialog aria-labelledby="dialog-title"></dialog>`;
      this.shadowRoot.addEventListener('click', e => this.handleClick(e));
      this.shadowRoot.addEventListener('input', e => {
        if (e.target.id === 'search') {
          this.query = e.target.value;
          this.renderMain();
        }
      });
      this.shadowRoot.addEventListener('change', e => {
        if (e.target.id === 'section') this.el('#new-section').hidden = e.target.value !==
          '__new__';
      });
      this.shadowRoot.addEventListener('submit', e => {
        e.preventDefault();
        this.save();
      });
      this.el('dialog').addEventListener('close', () => {
        if (this.el('dialog').open) return;
        this.editId = null;
        this.learning = null;
        this.sectionId = null;
      });
      this.el('dialog').addEventListener('cancel', e => {
        e.preventDefault();
        this.closeDialog();
      });
    }
    el(selector) {
      return this.shadowRoot.querySelector(selector);
    }

    // Presentation-only text. Radio identifiers and user-authored labels bypass t().
    t(key, parameters) {
      return this.locale.t(key, parameters);
    }

    iconLabel(name) {
      const key = 'icon.' + this.data.icons[name];
      const label = this.t(key);
      return label === key ? name : label;
    }

    refreshOpenDialog() {
      if (!this.el('dialog').open) return;
      const focus = this.shadowRoot.activeElement;
      const focusId = focus?.id;
      const position = focus?.selectionStart;
      const opened = [...this.el('dialog').querySelectorAll('details')].map(d => d.open);
      const scroll = this.el('dialog').scrollTop;
      const revision = this.editRevision;
      // A language change must not silently rebase a concurrent metadata edit.
      this.relocalizing = true;
      if (this.editId) {
        this.readDraft();
        this.editForm();
      } else if (this.learning) {
        const session = this.learning;
        this.openLearning(session.id);
        this.learning = session;
        this.updateLearning();
      } else if (this.sectionId) {
        const reference = this.el('#reference')?.value;
        this.openSection(this.sectionId);
        if (reference && this.el('#reference')) this.el('#reference').value = reference;
      }
      this.relocalizing = false;
      this.editRevision = revision;
      this.el('dialog').querySelectorAll('details').forEach((d,i) => d.open = opened[i] || false);
      this.el('dialog').scrollTop = scroll;
      if (focusId) {
        const input = this.el('#' + focusId);
        input?.focus({preventScroll:true});
        if (position != null && input?.setSelectionRange) input.setSelectionRange(position,position);
      }
      if (this.pending) this.el('#save')?.setAttribute('disabled','');
    }

    // Home Assistant's card lifecycle: configuration is static; hass snapshots are live.
    setConfig(config) {
      if (!config.entity || !config.status_entity) throw new Error(this.t('config_required'));
      this.config = {
        tx_entities: {},
        ...config
      };
    }
    getCardSize() {
      return 10;
    }
    getGridOptions() {
      return {
        columns: 'full',
        min_columns: 12
      };
    }
    connectedCallback() {
      this.timer = setInterval(() => {
        this.updateTimes();
        this.loadAreas();
      }, 15000);
    }
    disconnectedCallback() {
      clearInterval(this.timer);
      clearTimeout(this.pendingTimer);
      clearTimeout(this.txTimer);
    }
    set hass(hass) {
      const localeChanged = this.locale.update(hass);
      this._hass = hass;
      this.lang = this.locale.uiLanguage;
      this.dataset.locale = this.locale.language;
      if (localeChanged) {
        this.message = '';
        this.el('[data-add]').innerHTML = icon('mdi:plus') + ' ' + this.t('add');
        this.el('nav').setAttribute('aria-label',this.t('navigation'));
      }
      if (!this.config) return;
      this.loadAreas();
      const cat = hass.states[this.config.entity];
      this.data = cat?.attributes?.items ? cat.attributes : null;
      // Metadata acknowledgements and RF results are separate correlated channels.
      if (this.pending && this.data) {
        const receipt = (this.data.receipts || []).find(r => r.request_id === this.pending
          .request_id);
        if (receipt) {
          clearTimeout(this.pendingTimer);
          this.pending = null;
          const sameDialog = this.pendingDialogGeneration === this.dialogGeneration;
          if (receipt.ok) {
            this.message = this.t('saved');
            if (sameDialog) this.closeDialog();
          } else {
            this.message = this.locale.serverMessage(receipt.message);
            if (sameDialog) {
              this.dialogMessage(this.locale.serverMessage(receipt.message), true);
              this.el('#save')?.removeAttribute('disabled');
              if (receipt.code === 'conflict' && this.editId) this.el('#dialog-message')
                .insertAdjacentHTML('beforeend',
                  `<div class="footer"><button type="button" data-reload>${this.t('reload')}</button><button type="button" data-overwrite>${this.t('overwrite')}</button></div>`
                  );
            }
          }
        }
      }
      const result = hass.states[this.config.result_entity];
      if (this.tx && result?.attributes.client_request === this.tx.request_id) {
        clearTimeout(this.txTimer);
        const text = this.resultText(result);
        this.feedback.set(this.tx.alias, {
          result,
          error: !result.state.startsWith('transmitted_')
        });
        this.message = text;
        this.tx = null;
        this.dialogMessage(text, !result.state.startsWith('transmitted_'));
      }
      this.renderMain();
      if (localeChanged) this.refreshOpenDialog();
      this.updateLearning();
      this.updateDialogButtons();
    }
    item(id) {
      return this.data?.items.find(i => i.identity === id);
    }
    section(id) {
      return this.data?.sections.find(s => s.id === id);
    }
    unknowns() {
      return this.data?.items.filter(i => !i.known && !i.ignored) || [];
    }
    sourceName(i) {
      const serials = [...new Set(this.data.items.map(x => x.serial))].sort();
      return i.source ||
        `${this.t('switch_prefix')} ${String(serials.indexOf(i.serial)+1).padStart(2,'0')}`;
    }
    buttonName(i) {
      return i.button ||
        `${this.t('button_prefix')} ${String.fromCharCode(65+(Number(i.identity.split('_')[1])*2)+Number(i.identity.split('_')[2]))}`;
    }
    areaName(i) {
      return i?.area_id ? (this.areas.find(a => a.area_id === i.area_id)?.name || this.t(
        'room_unavailable')) : (i?.area || '');
    }
    areaOptions(selected) {
      const options = this.areas.map(a =>
        `<option value="${esc(a.area_id)}" ${a.area_id===selected?'selected':''}>${esc(a.name)}</option>`
        );
      if (selected && !this.areas.some(a => a.area_id === selected)) options.unshift(
        `<option value="${esc(selected)}" selected>${this.t('room_unavailable')}</option>`);
      return options.join('');
    }
    async loadAreas(force = false) {
      // Stable area_id values survive renames; names always come from HA's registry.
      if (!this._hass?.callWS || this.loadingAreas || (!force && Date.now() - (this
          .areasLoadedAt || 0) < 15000)) return;
      this.loadingAreas = true;
      try {
        const areas = await this._hass.callWS({
          type: 'config/area_registry/list'
        });
        this.areas = areas.sort((a, b) => a.name.localeCompare(b.name, this.locale.language));
        this.areasReady = true;
        this.areasLoadedAt = Date.now();
        this.renderMain();
        const select = this.el('#area');
        if (select) {
          const selected = select.value;
          select.innerHTML = `<option value="">${this.t('choose_room')}</option>` + this
            .areaOptions(selected);
        }
      } catch (_) {
        this.areasLoadedAt = Date.now();
        this.areasReady = false;
        const note = this.el('#area-note');
        if (note) note.textContent = this.t('rooms_failed');
      } finally {
        this.loadingAreas = false;
      }
    }
    connection() {
      const g = this._hass?.states[this.config?.status_entity];
      return {
        online: g?.state === 'rx_active' && Date.now() - Date.parse(g.attributes.last_seen) <
          180000,
        enabled: g?.attributes.tx_enabled === true
      };
    }
    canTx(alias) {
      const c = this.connection();
      return !!alias && c.online && c.enabled;
    }
    age(stamp) {
      return this.locale.age(stamp);
    }
    time(stamp) {
      return `<span data-date="${esc(stamp||'')}">${esc(this.age(stamp))}</span>`;
    }
    updateTimes() {
      this.shadowRoot.querySelectorAll('[data-date]').forEach(e => e.textContent = this.age(e
        .dataset.date));
      const c = this.connection(),
        h = this.el('#health');
      h.className = 'health' + (c.online ? ' online' : '');
      h.textContent = c.online ? (c.enabled ? this.t('connected') : this.t(
        'commands_disabled')) : this.t('disconnected');
      this.updateDialogButtons();
      this.shadowRoot.querySelectorAll('main [data-press]').forEach(b => b.disabled = !this
        .canTx(b.dataset.alias) || !!this.tx);
    }
    resultText(result) {
      const a = result?.attributes || {};
      const messages = {
        transmitted_unconfirmed: this.t('tx_sent'),
        transmitted_rx_failed: this.t('tx_rx_failed'),
        failed_firmware: this.t('tx_failed'),
        failed_arm: this.t('tx_arm_failed'),
        rejected_busy: this.t('tx_busy'),
        rejected_tx_disabled: this.t('tx_disabled'),
        rejected_minimum_interval: this.t('tx_interval'),
        rejected_hourly_airtime_budget: this.t('tx_budget'),
        rejected_incomplete_frame: this.t('tx_incomplete'),
        rejected_learning: a.reason === 'storage_full' ? this.t('tx_memory') : this.t(
          'tx_learn'),
        rejected_invalid_command: this.t('tx_invalid')
      };
      return messages[result?.state] || this.t('tx_unknown');
    }
    action(i, compact = false) {
      // The catalogue exposes capability. Naming and grouping never unlock a press.
      if (!i.tx_alias)
      return `<button ${compact?'class="press-small"':''} data-learn="${esc(i.identity)}" aria-label="${this.t('recognize_label')} ${esc(this.buttonName(i))}">${icon('mdi:radar')}<span class="action-label">${this.t('recognize')}</span></button>`;
      const busy = this.tx?.alias === i.tx_alias;
      return `<button class="${compact?'press-small':'primary'}" data-press="${esc(i.identity)}" data-alias="${esc(i.tx_alias)}" ${!this.canTx(i.tx_alias)||this.tx?'disabled':''} aria-label="${this.t('press')} ${esc(this.buttonName(i))}">${busy?`<span class="spinner" aria-hidden="true"></span>`:icon('mdi:gesture-tap')}<span class="action-label">${busy?this.t('sending'):this.t('press')}</span></button>`;
    }
    feedbackFor(alias) {
      const f = this.feedback.get(alias);
      const text = f?.result ? this.resultText(f.result) : f?.key ? this.t(f.key) : f?.text || '';
      return `<p class="feedback${f?.error?' error':''}" data-feedback="${esc(alias||'')}">${esc(text)}</p>`;
    }
    renderMain() {
      // Avoid replacing unchanged markup, and preserve keyboard focus when data moves.
      if (!this.config) return;
      this.el('#message').textContent = this.message;
      const nav = [
        ['commands', 'mdi:remote', this.t('nav_controls')],
        ['switches', 'mdi:light-switch', this.t('nav_buttons')],
        ['activity', 'mdi:history', this.t('nav_activity')]
      ];
      const navHTML = nav.map(([p, ico, n]) =>
        `<button data-page="${p}" ${this.page===p?'aria-current="page"':''}>${icon(ico)}${n}${p==='switches'&&this.unknowns().length?`<span class="count">${this.unknowns().length}</span>`:''}</button>`
        ).join('');
      if (this.navHTML !== navHTML) {
        this.el('nav').innerHTML = navHTML;
        this.navHTML = navHTML;
      }
      if (!this.data) {
        this.el('main').innerHTML =
          `<div class="empty"><h3>${this.t('catalogue_loading')}</h3><p>${this.t('catalogue_wait')}</p></div>`;
        this.updateTimes();
        return;
      }
      const active = this.shadowRoot.activeElement,
        search = active?.id === 'search',
        position = active?.selectionStart;
      const focusKey = active?.dataset.press || active?.dataset.edit || active?.dataset.learn;
      const html = this[this.page]();
      if (this.mainHTML !== html) {
        this.el('main').innerHTML = html;
        this.mainHTML = html;
      }
      if (search) {
        this.el('#search')?.focus({
          preventScroll: true
        });
        this.el('#search')?.setSelectionRange(position, position);
      } else if (focusKey && active && !active.isConnected) {
        const target = [...this.el('main').querySelectorAll('button')].find(b => b.dataset
          .press === focusKey || b.dataset.edit === focusKey || b.dataset.learn === focusKey);
        target?.focus({
          preventScroll: true
        });
      }
      this.updateTimes();
    }
    searchBox() {
      return `<div class="search">${icon('mdi:magnify')}<label class="sr-only" for="search">${this.t('search_label')}</label><input id="search" type="search" value="${esc(this.query)}" placeholder="${this.t('search_hint')}"></div>`;
    }
    matchesQuery(i) {
      return `${this.sourceName(i)} ${this.buttonName(i)} ${this.areaName(i)} ${this.section(i.section_id)?.name||''}`
        .toLocaleLowerCase().includes(this.query.toLocaleLowerCase());
    }
    commands() {
      const cards = [];
      for (const section of this.data.sections) {
        const members = section.identities.map(id => this.item(id)).filter(i => i && !i
        .ignored);
        if (!members.length || !members.some(i => this.matchesQuery(i))) continue;
        const reference = members.find(i => i.identity === section.reference) || members[0];
        cards.push({
          id: section.id,
          title: section.name,
          item: reference,
          section: true,
          subtitle: members.length > 1 ? this.locale.plural('associated', members.length) :
            this.sourceName(reference),
          area: this.areaName(reference)
        });
      }
      for (const i of this.data.items.filter(i => !i.ignored && !i.section_id && (i.known || i
          .tx_alias) && this.matchesQuery(i))) cards.push({
        id: i.identity,
        title: this.buttonName(i),
        subtitle: this.sourceName(i),
        item: i,
        area: this.areaName(i)
      });
      const rank = c => c.item.tx_alias ? (c.section ? 0 : c.item.known ? 1 : 2) : 3;
      cards.sort((a, b) => rank(a) - rank(b));
      const rooms = [...new Set(cards.map(c => c.area || this.t('other_buttons')))].sort((a,
        b) => a === this.t('other_buttons') ? 1 : b === this.t('other_buttons') ? -1 : a
        .localeCompare(b, this.locale.language));
      return `
        <div class="intro"><div>
          <h2>${this.t('controls_heading')}</h2><p>${this.t('controls_intro')}</p>
        </div></div>
        <div class="tools">${this.searchBox()}</div>
        ${rooms.map(room => `
          <h3 class="room">${esc(room)}</h3>
          <div class="grid">
            ${cards.filter(c => (c.area || this.t('other_buttons')) === room)
              .map(c => this.commandCard(c)).join('')}
          </div>`).join('')}
        ${!cards.length ? `<div class="empty">
          <h3>${this.t('no_buttons')}</h3><p>${this.t('search_empty')}</p>
          <button data-add>${this.t('recognize_button')}</button>
        </div>` : ''}
        <p class="footnote">${this.t('no_state')}</p>`;
    }

    commandCard(card) {
      const editAction = card.section ? `data-section="${esc(card.id)}"` : `data-edit="${esc(card.id)}"`;
      return `<article class="tile">
        <div class="tile-head">
          <span class="symbol">${icon(card.item.icon)}</span>
          ${!card.item.known ? `<span class="badge">${this.t('unnamed')}</span>` : ''}
          <button class="quiet icon" ${editAction} aria-label="${this.t('edit')} ${esc(card.title)}">
            ${icon('mdi:dots-horizontal')}
          </button>
        </div>
        <h3>${esc(card.title)}</h3><small>${esc(card.subtitle)}</small>
        <div class="controls">${this.action(card.item)}</div>
        ${this.feedbackFor(card.item.tx_alias)}
      </article>`;
    }
    switches() {
      const items = this.data.items.filter(i => this.matchesQuery(i) && (this.filter ===
        'hidden' ? i.ignored : !i.ignored && (this.filter !== 'unnamed' || !i.known)));
      const serials = [...new Set(items.map(i => i.serial))];
      const filters = [['all',this.t('all')], ['unnamed',`${this.t('unnamed')} (${this.locale.number(this.unknowns().length)})`], ['hidden',this.t('hidden')]];
      return `
        <div class="intro"><div><h2>${this.t('buttons_heading')}</h2><p>${this.t('buttons_intro')}</p></div></div>
        <div class="tools">${this.searchBox()}
          <div class="filters" aria-label="${this.t('filter_buttons')}">
            ${filters.map(([value,label]) => `<button data-filter="${value}" aria-pressed="${this.filter===value}">${label}</button>`).join('')}
          </div>
        </div>
        <div class="grid">${serials.map(serial => this.switchPanel(items.filter(i => i.serial===serial))).join('')}</div>
        ${!items.length ? `<div class="empty"><h3>${this.t('no_buttons_here')}</h3><p>${this.t('receive_new')}</p><button data-add>${this.t('add_button')}</button></div>` : ''}`;
    }

    switchPanel(keys) {
      return `<article class="panel">
        <div class="switch-head"><div>
          <small>${esc(this.areaName(keys[0]) || this.t('room_optional'))}</small>
          <h3>${esc(this.sourceName(keys[0]))}</h3>
        </div>${icon('mdi:light-switch')}</div>
        <div class="keys">${keys.map(i => `<div class="key">
          <div class="key-body">
            <button data-edit="${esc(i.identity)}">
              <strong>${esc(this.buttonName(i))}</strong>
              <small>${esc(this.section(i.section_id)?.name || (!i.known ? this.t('give_name') : this.t('edit')))}</small>
            </button>${this.feedbackFor(i.tx_alias)}
          </div>
          ${i.ignored ? `<button class="quiet" data-restore="${esc(i.identity)}">${this.t('restore')}</button>` : this.action(i,true)}
        </div>`).join('')}</div>
      </article>`;
    }
    activity() {
      const result = this._hass.states[this.config.result_entity],
        last = this.data.items.find(i => i.tx_alias === result?.attributes?.alias);
      const rows = this.data.items.filter(i => i.last_seen).sort((a, b) => b.last_seen
        .localeCompare(a.last_seen)).slice(0, 30);
      return `<div class="intro"><div><h2>${this.t('activity_heading')}</h2><p>${this.t('activity_intro')}</p></div></div><section class="panel activity-summary"><small>${this.t('last_command')}</small><h3>${esc(last?this.buttonName(last):this.t('no_recent_command'))}</h3><p>${esc(result?.attributes?.alias?this.resultText(result):this.t('command_help'))}</p><small>${result?.attributes?.timestamp?this.time(result.attributes.timestamp):''}</small></section><section class="panel"><h3>${this.t('latest_receptions')}</h3>${rows.map(i=>`<div class="row">${icon(i.icon)}<div class="body"><strong>${esc(this.buttonName(i))}</strong><small>${esc(this.sourceName(i))} · ${this.locale.plural('receptions',i.count)}</small></div><small>${this.time(i.last_seen)}</small></div>`).join('')||`<p class="footnote">${this.t('no_receptions')}</p>`}</section><details><summary>${this.t('diagnostics')}</summary><dl><dt>Firmware</dt><dd>${esc(this._hass.states[this.config.status_entity]?.attributes.firmware)}</dd><dt>${this.t('airtime')}</dt><dd>${esc(this._hass.states[this.config.status_entity]?.attributes.burst_airtime_us)} µs</dd></dl></details>`;
    }
    showDialog(title, body) {
      if (!this.relocalizing) this.dialogGeneration = (this.dialogGeneration || 0) + 1;
      const d = this.el('dialog');
      if (!d.open) this.returnFocus = this.shadowRoot.activeElement;
      d.innerHTML =
        `<div class="dialog-head"><h2 id="dialog-title">${esc(title)}</h2><button class="quiet icon" data-close aria-label="${this.t('close')}">${icon('mdi:close')}</button></div><div id="dialog-message" role="status" aria-live="polite"></div>${body}`;
      if (!d.open) d.showModal();
    }
    closeDialog() {
      this.el('dialog').close();
      this.editId = null;
      this.learning = null;
      this.sectionId = null;
      const target = this.returnFocus?.isConnected ? this.returnFocus : this.el(
        'nav [aria-current]');
      target?.focus({
        preventScroll: true
      });
    }
    dialogMessage(text, error = false) {
      const e = this.el('#dialog-message');
      if (e) {
        e.className = text ? 'notice' + (error ? ' error' : '') : '';
        e.textContent = text;
      }
    }
    openEditor(id) {
      const i = this.item(id);
      if (!i) return;
      this.learning = null;
      this.sectionId = null;
      this.editId = id;
      this.editRevision = this.data.revision;
      this.draft = {
        source: i.source || this.sourceName(i),
        button: i.button || '',
        area: i.area || '',
        area_id: i.area_id || this.areas.find(a => a.name === i.area)?.area_id || '',
        position: i.position || '',
        icon: i.icon_choice || 'Interrupteur',
        section_id: i.section_id || '',
        section_name: ''
      };
      this.editForm();
      this.loadAreas(true);
    }
    editForm() {
      const i = this.item(this.editId),
        d = this.draft,
        native = i.tx_alias && !i.tx_alias.startsWith('rx_');
      this.showDialog(i.known ? this.t('edit_button') : this.t('give_name'),
        `<form><p class="subtitle">${i.tx_alias?this.t('usable_intro'):esc(this.locale.serverMessage(i.activation_reason))}</p><label>${this.t('button_name')}<input id="button" required maxlength="80" value="${esc(d.button)}" placeholder="${this.t('example_button')}" autofocus autocomplete="off"></label><label>${this.t('room')}<select id="area"><option value="">${this.t('choose_room')}</option>${this.areaOptions(d.area_id)}</select><small id="area-note">${this.areasReady?this.t('rooms_synced'):this.t('rooms_loading')}</small></label><details><summary>${icon(this.data.icons[d.icon])} ${this.t('icon')} · ${esc(this.iconLabel(d.icon))}</summary><div class="icons">${Object.entries(this.data.icons).map(([name,ico])=>`<button type="button" data-icon-choice="${esc(name)}" aria-pressed="${name===d.icon}">${icon(ico)}${esc(this.iconLabel(name))}</button>`).join('')}</div></details><details><summary>${this.t('grouping')}</summary><label>${this.t('switch_name')}<input id="source" maxlength="80" value="${esc(d.source)}" placeholder="${this.t('example_switch')}"></label><label>${this.t('equipment')}<select id="section" ${native?'disabled':''}><option value="">${this.t('no_group')}</option>${this.data.sections.map(s=>`<option value="${esc(s.id)}" ${s.id===d.section_id?'selected':''}>${esc(s.name)}</option>`).join('')}<option value="__new__" ${d.section_id==='__new__'?'selected':''}>${this.t('create_group')}</option></select><small>${this.t('group_help')}</small></label><label id="new-section" ${d.section_id==='__new__'?'':'hidden'}>${this.t('equipment_name')}<input id="section_name" maxlength="80" value="${esc(d.section_name)}" placeholder="${this.t('example_equipment')}"></label><p class="footnote">${this.t('group_display_only')}</p></details><div class="footer"><button type="button" class="quiet" data-close>${this.t('cancel')}</button><button type="submit" class="primary" id="save">${this.t('save')}</button></div></form>`
        );
    }
    readDraft() {
      for (const key of ['source', 'button', 'section_name']) this.draft[key] = this.el('#' +
        key)?.value.trim() || '';
      this.draft.source = this.draft.source || this.sourceName(this.item(this.editId));
      this.draft.area_id = this.el('#area')?.value || '';
      this.draft.area = this.draft.area_id ? (this.areas.find(a => a.area_id === this.draft
        .area_id)?.name || this.draft.area || '') : '';
      this.draft.section_id = this.el('#section')?.value || '';
    }
    save() {
      if (!this.editId || this.pending) return;
      this.readDraft();
      if (!this.draft.button) {
        this.dialogMessage(this.t('name_required'), true);
        this.el('#button').focus();
        return;
      }
      this.metadata('save', this.editId, this.draft, this.editRevision);
    }
    openSection(id) {
      const s = this.section(id);
      if (!s) return;
      this.editId = null;
      this.learning = null;
      this.sectionId = id;
      this.editRevision = this.data.revision;
      const rows = s.identities.map(i => this.item(i)).filter(Boolean),
        eligible = rows.filter(i => i.tx_alias && !i.ignored);
      this.showDialog(s.name,
        `<p class="subtitle">${this.locale.plural('equipment_buttons',rows.length)}</p>${rows.map(i=>`<div class="row"><div class="body"><strong>${esc(this.buttonName(i))}</strong><small>${esc(this.sourceName(i))}</small></div><div class="actions">${this.action(i,true)}<button class="quiet" data-edit="${esc(i.identity)}">${this.t('edit')}</button></div></div>`).join('')}${eligible.length>1?`<label>${this.t('reference')}<select id="reference">${eligible.map(i=>`<option value="${esc(i.identity)}" ${s.reference===i.identity?'selected':''}>${esc(this.sourceName(i))} · ${esc(this.buttonName(i))}</option>`).join('')}</select><small>${this.t('one_reference')}</small></label><div class="footer"><button id="save" class="primary" data-prefer>${this.t('save')}</button></div>`:`<div class="footer"><button data-close>${this.t('done')}</button></div>`}`
        );
    }
    openLearning(id = null) {
      if (!this.data) return;
      this.editId = null;
      this.sectionId = null;
      this.learning = {
        id,
        counts: Object.fromEntries(this.data.items.map(i => [i.identity, i.count])),
        started: Date.now()
      };
      this.showDialog(id ? this.t('recognize_this') : this.t('add_button'),
        `<div class="learning"><div class="pulse">${icon('mdi:gesture-tap')}</div><h3>${this.t('press_physical')}</h3><p>${this.t('learning_intro')}</p></div><div id="learning-list" aria-live="polite"></div><div class="footer"><button data-close>${this.t('done')}</button></div>`
        );
      this.updateLearning();
    }
    updateLearning() {
      if (!this.learning || !this.data || !this.el('dialog').open) return;
      const session = this.learning,
        items = this.data.items.filter(i => session.id ? i.identity === session.id : (i.count >
          0 && (i.count > (session.counts[i.identity] || 0) || Date.parse(i.last_seen) >=
            session.started))).sort((a, b) => a.identity.localeCompare(b.identity));
      const list = this.el('#learning-list');
      if (!list) return;
      const html = items.map(i =>
        `<div class="row"><div class="body"><strong>${esc(this.buttonName(i))}</strong><small>${esc(this.sourceName(i))} · ${i.tx_alias?this.t('recognized'):esc(this.locale.serverMessage(i.activation_reason))}</small></div><div class="actions">${i.tx_alias?this.action(i,true):''}<button data-edit="${esc(i.identity)}">${i.known?this.t('edit'):this.t('name')}</button></div></div>`
        ).join('') || `<p class="notice">${this.t('learning_wait')}</p>`;
      if (list.innerHTML !== html) list.innerHTML = html;
    }
    updateDialogButtons() {
      this.el('dialog').querySelectorAll('[data-press]').forEach(b => b.disabled = !this.canTx(b
        .dataset.alias) || !!this.tx);
    }
    async metadata(operation, identity, fields = null, revision = null) {
      // One atomic request carries the stable identity, expected revision and receipt ID.
      if (this.pending) return;
      const request = {
        operation,
        identity,
        fields,
        revision: revision || this.data.revision,
        request_id: requestId()
      };
      this.pending = request;
      this.pendingDialogGeneration = this.dialogGeneration;
      this.el('#save')?.setAttribute('disabled', '');
      try {
        await this._hass.callService('mqtt', 'publish', {
          topic: 'nikobus/easywave/identify/catalogue/set',
          payload: JSON.stringify(request),
          qos: 0,
          retain: false
        });
        if (!this.pending) return;
        this.pendingTimer = setTimeout(() => {
          this.pending = null;
          this.dialogMessage(this.t('save_timeout'), true);
          this.el('#save')?.removeAttribute('disabled');
        }, 10000);
      } catch (error) {
        this.pending = null;
        this.dialogMessage(this.t('save_failed_prefix') + error.message, true);
        this.message = this.t('not_saved');
        this.el('#save')?.removeAttribute('disabled');
        this.renderMain();
      }
    }
    async press(id) {
      // Only this explicit user gesture emits. I do not retry ambiguous radio results.
      const i = this.item(id);
      if (!i || !this.canTx(i.tx_alias) || this.tx) return;
      const request_id = requestId();
      this.tx = {
        alias: i.tx_alias,
        request_id
      };
      this.feedback.set(i.tx_alias, {
        key: 'sending'
      });
      this.renderMain();
      this.updateDialogButtons();
      this.txTimer = setTimeout(() => {
        if (this.tx?.request_id !== request_id) return;
        this.feedback.set(i.tx_alias, {
          key: 'tx_timeout',
          error: true
        });
        this.message = this.t('tx_timeout_prefix') + this.buttonName(i) + '.';
        this.tx = null;
        this.renderMain();
        this.updateDialogButtons();
      }, 12000);
      try {
        await this._hass.callService('mqtt', 'publish', {
          topic: 'nikobus/easywave/tx/' + i.tx_alias + '/set',
          payload: JSON.stringify({
            action: 'PRESS',
            request_id
          }),
          qos: 0,
          retain: false
        });
      } catch (error) {
        if (this.tx?.request_id !== request_id) return;
        clearTimeout(this.txTimer);
        this.tx = null;
        const text = this.t('send_failed_prefix') + error.message;
        this.feedback.set(i.tx_alias, {
          text,
          error: true
        });
        this.message = text;
        this.dialogMessage(text, true);
        this.renderMain();
        this.updateDialogButtons();
      }
    }
    handleClick(event) {
      const b = event.target.closest('button');
      if (!b) return;
      const d = b.dataset;
      if (d.page) {
        this.page = d.page;
        this.query = '';
        this.message = '';
        this.renderMain();
      } else if (d.add !== undefined) this.openLearning();
      else if (d.close !== undefined) this.closeDialog();
      else if (d.filter) {
        this.filter = d.filter;
        this.renderMain();
      } else if (d.press) this.press(d.press);
      else if (d.learn) this.openLearning(d.learn);
      else if (d.edit) this.openEditor(d.edit);
      else if (d.section) this.openSection(d.section);
      else if (d.prefer !== undefined) this.metadata('prefer', this.el('#reference').value,
        null, this.editRevision);
      else if (d.reload !== undefined) this.openEditor(this.editId);
      else if (d.overwrite !== undefined) {
        this.editRevision = this.data.revision;
        this.save();
      } else if (d.iconChoice) {
        this.readDraft();
        this.draft.icon = d.iconChoice;
        this.editForm();
      } else if (d.restore) this.metadata('restore', d.restore);
    }
  }
  if (!customElements.get('hells-gate-card')) customElements.define('hells-gate-card',
    HellsGateCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'hells-gate-card',
    name: 'Hell’s Gate',
    description: 'Recognized buttons are directly actionable.'
  });
})();
