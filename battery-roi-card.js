// Battery ROI Scoreboard card for Home Assistant.
// Lit is loaded from Lit's official prebuilt bundle; if your HA has no
// internet, download that file next to this one and change the URL.
import {
  LitElement,
  html,
  css,
  nothing,
} from "https://cdn.jsdelivr.net/gh/lit/dist@3/all/lit-all.min.js";

const DEFAULTS = {
  title: "Battery ROI",
  daily: "sensor.battery_roi_profit_daily",
  monthly: "sensor.battery_roi_profit_monthly",
  rate: "sensor.battery_roi_rate",
  soc: "sensor.battery_roi_state_of_charge",
  price: "sensor.battery_roi_price",
  currency: "EUR",
};

class BatteryRoiCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
  }

  getCardSize() {
    return 3;
  }

  _num(entityId) {
    const value = parseFloat(this.hass?.states[entityId]?.state);
    return Number.isFinite(value) ? value : null;
  }

  _money(value, { digits = 2, signed = false } = {}) {
    if (value === null || value === undefined) return "–";
    return new Intl.NumberFormat(this.hass.locale?.language ?? this.hass.language, {
      style: "currency",
      currency: this._config.currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      signDisplay: signed ? "exceptZero" : "auto",
    }).format(value);
  }

  _trend(value) {
    if (value === null || Math.abs(value) < 0.005) return "flat";
    return value > 0 ? "up" : "down";
  }

  _moreInfo(entityId) {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      })
    );
  }

  _tile(label, entityId, previousLabel) {
    const value = this._num(entityId);
    const last = parseFloat(this.hass.states[entityId]?.attributes?.last_period);
    const trend = this._trend(value);
    const icon = { up: "mdi:trending-up", down: "mdi:trending-down", flat: "mdi:trending-neutral" }[trend];
    return html`
      <button class="tile ${trend}" @click=${() => this._moreInfo(entityId)}>
        <span class="label">${label}</span>
        <span class="value">
          <ha-icon .icon=${icon}></ha-icon>${this._money(value, { signed: true })}
        </span>
        ${Number.isFinite(last)
          ? html`<span class="sub">${previousLabel} ${this._money(last)}</span>`
          : nothing}
      </button>
    `;
  }

  render() {
    if (!this.hass || !this._config) return nothing;
    const c = this._config;
    const rate = this._num(c.rate);
    const soc = this._num(c.soc);
    const price = this._num(c.price);
    const rateTrend = this._trend(rate);
    const rateText =
      rateTrend === "flat" ? "Idle" : rateTrend === "up" ? "Earning" : "Spending";

    return html`
      <ha-card .header=${c.title}>
        <div class="tiles">
          ${this._tile("Today", c.daily, "Yesterday")}
          ${this._tile("This month", c.monthly, "Last month")}
        </div>
        <div class="ticker" @click=${() => this._moreInfo(c.rate)}>
          <span class="live ${rateTrend}">
            ${rateText} ${rate === null ? "" : `${this._money(Math.abs(rate))}/h`}
          </span>
          <span class="meta">
            ${price === null ? nothing : html`<span>${this._money(price, { digits: 3 })}/kWh</span>`}
            ${soc === null ? nothing : html`<span>${Math.round(soc)}%</span>`}
          </span>
        </div>
      </ha-card>
    `;
  }

  static styles = css`
    .tiles {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      padding: 0 16px 12px;
    }
    .tile {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
      padding: 12px;
      border: 1px solid var(--divider-color);
      border-radius: var(--ha-card-border-radius, 12px);
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      font: inherit;
      text-align: left;
      cursor: pointer;
    }
    .label,
    .sub,
    .meta {
      color: var(--secondary-text-color);
      font-size: 0.85em;
    }
    .value {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 1.6em;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
    }
    .up .value,
    .live.up {
      color: var(--success-color);
    }
    .down .value,
    .live.down {
      color: var(--error-color);
    }
    .flat .value,
    .live.flat {
      color: var(--primary-text-color);
    }
    .ticker {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-top: 1px solid var(--divider-color);
      cursor: pointer;
    }
    .live {
      font-weight: 500;
      font-variant-numeric: tabular-nums;
    }
    .meta {
      display: flex;
      gap: 12px;
    }
  `;
}

customElements.define("battery-roi-card", BatteryRoiCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "battery-roi-card",
  name: "Battery ROI Scoreboard",
  description: "Daily and monthly profit from charging cheap and discharging expensive.",
});
