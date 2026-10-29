/**
 * Per-card locale adapter. I follow the current HA user's preferences, never a
 * server-wide language flag, so two people can use different languages at once.
 * The build embeds the JSON packs as HG_TRANSLATIONS; no runtime fetch is needed.
 */
class HellsGateLocale {
  constructor() {
    this.update(null);
  }

  update(hass) {
    const settings = hass?.locale || {};
    const requested = settings.language || hass?.language || globalThis.navigator?.language ||
      'en';
    let language;
    try {
      language = Intl.getCanonicalLocales(String(requested).replaceAll('_', '-'))[0];
    } catch (_) {
      language = 'en';
    }
    const base = language.split('-')[0];
    const signature = JSON.stringify([language, settings, hass?.config?.time_zone]);
    const changed = this.signature !== signature;
    this.signature = signature;
    this.language = language;
    this.uiLanguage = Object.hasOwn(HG_TRANSLATIONS, base) ? base : 'en';
    this.settings = settings;
    this.serverTimeZone = hass?.config?.time_zone;
    return changed;
  }

  t(key, parameters = {}) {
    const text = HG_TRANSLATIONS[this.uiLanguage]?.[key] ?? HG_TRANSLATIONS.en[key] ?? key;
    return text.replace(/\{([a-z_]+)\}/g, (match, name) => parameters[name] ?? match);
  }

  plural(key, count) {
    const category = new Intl.PluralRules(this.uiLanguage).select(count);
    return this.t(key + (category === 'one' ? '_one' : '_other'), {
      count: this.number(count)
    });
  }

  number(value) {
    const formats = {
      comma_decimal: 'en-US',
      decimal_comma: 'de-DE',
      space_comma: 'fr-FR',
      quote_decimal: 'de-CH'
    };
    const format = this.settings.number_format;
    const locale = formats[format] || (format === 'system' ? navigator.language : this.language);
    return new Intl.NumberFormat(locale, {
      useGrouping: format !== 'none'
    }).format(value);
  }

  date(stamp) {
    const settings = this.settings;
    const browser = globalThis.navigator?.language || this.language;
    const dateLocale = ({
        DMY: 'en-GB',
        MDY: 'en-US',
        YMD: 'sv-SE'
      })[settings.date_format] ||
      (settings.date_format === 'system' ? browser : this.language);
    const timeLocale = settings.time_format === 'system' ? browser : this.language;
    const options = {};
    if (settings.time_zone !== 'local' && this.serverTimeZone) options.timeZone = this
      .serverTimeZone;
    if (settings.time_format === '12') options.hourCycle = 'h12';
    if (settings.time_format === '24') options.hourCycle = 'h23';
    const value = new Date(stamp);
    try {
      const date = new Intl.DateTimeFormat(dateLocale, {
        day: '2-digit',
        month: '2-digit',
        ...(options.timeZone ? {
          timeZone: options.timeZone
        } : {})
      }).format(value);
      const time = new Intl.DateTimeFormat(timeLocale, {
        hour: '2-digit',
        minute: '2-digit',
        ...options
      }).format(value);
      return date + ' · ' + time;
    } catch (_) {
      // An invalid server time zone must not make the controls unusable.
      return value.toLocaleString(this.language);
    }
  }

  age(stamp) {
    if (!stamp) return this.t('never_received');
    const seconds = Math.max(0, (Date.now() - Date.parse(stamp)) / 1000);
    if (!Number.isFinite(seconds)) return this.t('unknown_date');
    if (seconds < 20) return this.t('just_now');
    if (seconds < 60) return this.t('under_minute');
    if (seconds < 3600) return new Intl.RelativeTimeFormat(this.language, {
      numeric: 'always'
    }).format(-Math.floor(seconds / 60), 'minute');
    return this.date(stamp);
  }

  serverMessage(message) {
    // Only protocol messages use this compatibility adapter. I never translate
    // a user's names, room names, radio identities or saved icon identifiers.
    const key = Object.keys(HG_TRANSLATIONS.fr).find(key => HG_TRANSLATIONS.fr[key] === message);
    return key ? this.t(key) : String(message || '');
  }
}
