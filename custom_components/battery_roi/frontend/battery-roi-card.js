// Battery ROI Scoreboard card for Home Assistant.
// Served and registered by the battery_roi integration; Lit ships alongside
// so the card also works without internet.
import { LitElement, html, css, nothing } from "./lit.js";

const DEFAULTS = {
  title: "Battery ROI",
  daily: "sensor.battery_roi_profit_today",
  monthly: "sensor.battery_roi_profit_this_month",
  rate: "sensor.battery_roi_rate",
  payback: "sensor.battery_roi_payback",
  efficiency: "sensor.battery_roi_efficiency",
  // Price and state of charge come from the rate sensor's attributes
  // unless you point these at other entities.
  soc: null,
  price: null,
  currency: null,
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

  _attrNum(value) {
    const n = parseFloat(value);
    return Number.isFinite(n) ? n : null;
  }

  _money(value, { digits = 2, signed = false } = {}) {
    if (value === null || value === undefined) return "–";
    return new Intl.NumberFormat(this.hass.locale?.language ?? this.hass.language, {
      style: "currency",
      currency: this._config.currency ?? this.hass.config?.currency ?? "EUR",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      signDisplay: signed ? "exceptZero" : "auto",
    }).format(value);
  }

  _trend(value) {
    if (value === null || Math.abs(value) < 0.005) return "flat";
    return value > 0 ? "up" : "down";
  }

  // Month-to-date profit projected over the whole month, using the exact
  // time elapsed and this month's real length. Hidden in the first day,
  // when a few hours of data would be blown up 30x.
  _pace(monthly) {
    if (monthly === null) return null;
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    const elapsed = now - start;
    if (elapsed < 86400000) return null;
    return (monthly * (end - start)) / elapsed;
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
    const rateAttrs = this.hass.states[c.rate]?.attributes ?? {};
    const soc = c.soc ? this._num(c.soc) : this._attrNum(rateAttrs.soc);
    const price = c.price ? this._num(c.price) : this._attrNum(rateAttrs.price);
    const solar = this._attrNum(rateAttrs.solar_kw);
    const pace = this._pace(this._num(c.monthly));
    const payback = this._num(c.payback);
    const efficiency = this._num(c.efficiency);
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
            ${solar === null ? nothing : html`<span><ha-icon .icon=${"mdi:solar-power"}></ha-icon>${solar.toFixed(1)} kW</span>`}
            ${soc === null ? nothing : html`<span><ha-icon .icon=${"mdi:battery"}></ha-icon>${Math.round(soc)}%</span>`}
          </span>
        </div>
        ${pace === null && payback === null && efficiency === null
          ? nothing
          : html`<div class="outlook">
              ${pace === null ? nothing : html`<span>Pace ${this._money(pace, { signed: true })}/month</span>`}
              ${payback === null ? nothing : html`<span>Payback ${payback.toFixed(1)} y</span>`}
              ${efficiency === null ? nothing : html`<span>Efficiency ${Math.round(efficiency)}%</span>`}
            </div>`}
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
    .meta,
    .outlook {
      display: flex;
      gap: 12px;
    }
    .meta span {
      display: flex;
      align-items: center;
      gap: 2px;
    }
    .meta ha-icon {
      --mdc-icon-size: 16px;
    }
    .outlook {
      flex-wrap: wrap;
      padding: 0 16px 12px;
      color: var(--secondary-text-color);
      font-size: 0.85em;
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
