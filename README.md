<div align="center">

<img src="custom_components/battery_roi/brand/icon.png" alt="" width="96">

# Battery ROI

**How much money did your home battery actually make today?**

A Home Assistant integration that multiplies every kWh your battery charges and discharges by the price at that exact moment, and shows the result as a live profit ticker.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz/docs/faq/custom_repositories/)
[![Home Assistant 2024.11+](https://img.shields.io/badge/Home%20Assistant-2024.11%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![CI](https://github.com/PeterSlijkhuis/Battery-ROI/actions/workflows/ci.yml/badge.svg)](https://github.com/PeterSlijkhuis/Battery-ROI/actions/workflows/ci.yml)
![Version](https://img.shields.io/github/v/release/PeterSlijkhuis/Battery-ROI)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PeterSlijkhuis&repository=Battery-ROI&category=integration)
[![Open your Home Assistant instance and start setting up Battery ROI.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=battery_roi)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/card-dark.png">
  <img alt="Battery ROI card showing today's and this month's profit with trend arrows" src="docs/card-light.png" width="520">
</picture>

**[Setup in 5 steps](#step-by-step-setup)** · [Troubleshooting](#after-setup) · [How profit is calculated](#how-profit-is-calculated)

</div>

---

## Why

Standard energy dashboards show kWh. With dynamic prices (EPEX, Nordpool, Tibber, Frank Energie, Zonneplan …) the question that matters is money: *did charging at 3 AM and discharging at 7 PM pay off?* Battery ROI answers that per day, per month, and since the day you installed it.

## Features

- 🧮 **Real profit, not an estimate**: every 30 seconds, energy × the price that applied at that moment
- 🖱️ **No YAML**: pick your own sensors in a setup screen, change them later without losing your totals
- 🔌 **Works with any battery that has a power sensor in Home Assistant** (EcoFlow, Zendure, Marstek, Anker SOLIX, Victron, Huawei, SolarEdge, Sessy, Tesla Powerwall and so on), any grid meter, any dynamic price sensor, W/kW and EUR/kWh, ct/kWh or EUR/MWh
- ☀️ **Solar aware**: with a feed-in price and a grid meter, it knows whether a kWh replaced buying or selling
- 📈 **Dashboard card included**: today, this month, yesterday, last month, live €/h, monthly pace, payback and efficiency
- 🎨 **Matches your theme**: the card uses only Home Assistant theme variables, light and dark
- 🇳🇱 **English and Dutch**: setup screen and card follow your Home Assistant language
- ✏️ **Visual card editor**: no YAML needed on the dashboard either
- 📴 **Works offline**: the card and its UI library ship inside the integration, no CDN

## Requirements

| What | Why |
| --- | --- |
| Home Assistant **2024.11** or newer | Uses the current config and options flow APIs |
| [HACS](https://hacs.xyz/) | To install and update (manual install also works) |
| A **battery power** sensor | Power into and out of the battery, as two sensors or one signed sensor |
| A **price** sensor | Your dynamic tariff per kWh |
| *Optional:* feed-in price, grid power, solar production, state of charge | Better accuracy and more on the card |

No extra Python packages are installed. The card's only library, [Lit](https://lit.dev), is bundled.

## Step-by-step setup

Five steps, about 10 minutes. Every step says exactly where to click in Home Assistant.

> **Before you start:** you need [HACS](https://hacs.xyz/docs/use/) installed, and your battery and price sensors must already exist in Home Assistant (for example from your battery's own integration, a smart meter integration like DSMR or HomeWizard, and a price integration like Nordpool, ENTSO-e or Tibber).

### Step 1 · Find your sensors

Write down the names of the sensors you'll pick in step 4.

1. Go to **Settings → Devices & services → Entities** (tab at the top).
2. Type in the search box to find each one:

| You need | Search for | What it looks like |
| --- | --- | --- |
| Battery charge power *(required)* | `battery` + `power`, or your battery brand | Watts that go **into** the battery. Some batteries have one sensor that is positive while charging and negative while discharging; that's fine |
| Battery discharge power | `battery` + `power`, or your battery brand | Watts that come **out of** the battery. Skip if the sensor above is signed |
| Electricity price *(required)* | `price`, `tibber`, `nordpool`, `epex` | Your current price per kWh |
| Grid power *(recommended)* | `grid`, `p1`, `net`, `power_consumption` | Your smart meter or energy monitor: watts from (+) or to (−) the grid |
| Feed-in price *(recommended)* | `price` | What you get per exported kWh. With a dynamic contract this is often the same price sensor |
| Solar production | `solar`, `pv`, `inverter` | Watts your panels produce right now |
| Battery level | `battery` + `level`, `soc`, `state_of_charge` | Battery % |

**Examples by brand.** Entity names differ per integration and per firmware, so treat these as hints, not exact names:

| Kind | Brand or integration | Sensor to look for |
| --- | --- | --- |
| Battery | EcoFlow, Zendure, Anker SOLIX | separate *input* / *output* power sensors → fill both charge and discharge |
| Battery | Marstek, Victron, Huawei, SolarEdge, Sessy, Tesla Powerwall | one *battery power* sensor, positive one way and negative the other → fill charge only and set *Positive power means* |
| Grid | DSMR / Slimme meter, HomeWizard P1, P1 Monitor, Shelly EM, Tibber Pulse | *power consumption* minus *power production*, or one signed *active power* sensor |
| Solar | Enphase, SolarEdge, SMA, Growatt, Fronius, APsystems | *current power* or *AC power* of the inverter |
| Price | Nordpool, ENTSO-e, EnergyZero, Tibber, Frank Energie, Zonneplan, Octopus | *current price* |

Your grid meter (or battery) only has two separate sensors, one per direction, and you want one signed sensor? Make one with a [template helper](https://my.home-assistant.io/redirect/helpers/) (**Settings → Devices & services → Helpers → Create helper → Template → Template sensor**, state `{{ states('sensor.power_consumption')|float(0) - states('sensor.power_production')|float(0) }}`, unit W, device class Power).

> **Not sure which way a signed sensor goes?** Open it (click the name) while the battery is charging. Positive number = "positive means charging".

### Step 2 · Install Battery ROI with HACS

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PeterSlijkhuis&repository=Battery-ROI&category=integration)

Click the button above and choose your Home Assistant, **or** do it by hand:

1. Open **HACS** in the sidebar.
2. Click **⋮** (top right) → **Custom repositories**.
3. Paste `https://github.com/PeterSlijkhuis/Battery-ROI`, pick type **Integration**, click **Add**.
4. Search HACS for **Battery ROI**, open it, click **Download** (bottom right).
5. HACS asks which version: keep the newest (for example `v0.2.1`) and click **Download**.

<details>
<summary>No HACS? Install by hand</summary>

Copy the folder `custom_components/battery_roi` from this repository into `/config/custom_components/` on your Home Assistant (for example with the *File editor* or *Samba* add-on), so you end up with `/config/custom_components/battery_roi/manifest.json`.
</details>

### Step 3 · Restart Home Assistant

1. Go to **Settings → System**.
2. Click the **power icon** (top right) → **Restart Home Assistant** → **Restart**.
3. Wait until Home Assistant is back (about a minute), then **refresh your browser** (Ctrl+F5). In the phone app: close the app completely and open it again. Without this the card won't show up in step 5.

### Step 4 · Add the integration and pick your sensors

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=battery_roi)

Click the button above, **or**:

1. Go to **Settings → Devices & services**.
2. Click **+ Add integration** (bottom right).
3. Search for **Battery ROI** and click it.
4. Fill in the form with the sensors from step 1. Only the two fields marked required are needed; open the folded sections for more accuracy.
5. Click **Submit**.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/setup-dark.png">
  <img alt="Battery ROI setup screen" src="docs/setup-light.png" width="420">
</picture>

All fields explained:

| Section | Field | Required | What to enter |
| --- | --- | :---: | --- |
| Battery | Charge power | ✅ | Power into the battery, or one signed battery power sensor |
| | Discharge power | | Power out of the battery. Leave empty when the field above is signed |
| | Positive power means | | Only for a signed sensor: does positive mean charging or discharging? |
| | State of charge | | Battery %, shown on the card |
| Prices | Electricity price (import) | ✅ | EPEX, Nordpool, ENTSO-e, Tibber, Frank Energie, Zonneplan… |
| | Extra cost per kWh, excl. VAT | | **Only for raw market prices** (EPEX, Nordpool): energy tax + supplier fee in EUR/kWh |
| | VAT % | | **Only for raw market prices**: 21 in the Netherlands |
| | Feed-in price sensor | | What you get per exported kWh, from a sensor |
| | Fixed feed-in price | | Same, as a fixed amount (0 if you get nothing). Use one of the two |
| Grid and solar | Grid power | | Smart meter or energy monitor, + import / − export |
| | Solar production | | Shown on the card |
| Battery costs | Standby power | | Watts the battery uses itself that its power sensors miss |
| | Wear cost per kWh discharged | | Purchase price ÷ (capacity in kWh × rated cycles) |
| | Purchase cost | | What the battery cost you; adds a payback sensor |
| | Battery installed on | | Fills in the totals from Home Assistant's history from this day on, see [Start from your install date](#start-from-your-install-date) |

> **Tibber, Frank Energie, Zonneplan** sensors already include tax and VAT: leave *Extra cost* and *VAT* empty.

### Step 5 · Put the card on your dashboard

1. Open the dashboard where you want the card.
2. Click the **pencil** (top right) to edit. On the default *Overview* dashboard Home Assistant first asks you to **Take control**; confirm it.
3. Click **+ Add card** (bottom right), type **Battery ROI** in the search box, and click the card.
4. The card already points at the right sensors, so there is nothing to fill in. Click **Save**, then **Done** (top right).

Prefer YAML? Add a **Manual** card with:

```yaml
type: custom:battery-roi-card
```

The numbers start at €0 from the moment you finish step 4, unless you filled in *Battery installed on*. Read the next section before you judge them.

## Your first day: why the numbers look odd

Battery ROI books money **when it happens**. Charging costs money right away; the payoff only arrives when the battery discharges later at a higher price. So a normal first day looks like this:

| When | What you see | Why |
| --- | --- | --- |
| Battery charging (night, cheap hours, or solar) | Profit slightly **negative**, red arrow, *Spending €0.03/h* | You paid for energy that is now sitting in the battery |
| Battery full, waiting | Profit stays put, *Idle* | Nothing flows, nothing is booked (except standby power, if you entered it) |
| Battery discharging (evening peak) | Profit climbs, turns **positive**, green arrow, *Earning* | Every kWh out replaces a kWh you would have bought at the high price |
| End of the day | *Today* is the day's real result; tomorrow it moves to *Yesterday* | |

Some numbers stay **Unknown** at first, on purpose:

| Sensor | Shows up when | Why wait |
| --- | --- | --- |
| Efficiency | 1 kWh has been charged | Smaller amounts give meaningless percentages |
| Payback | You entered a purchase cost, 7 days have passed **and** profit is positive | One day says nothing about a year |
| Pace | From the 2nd of the month | A projection from a few hours is noise |

**Judge the battery on a full day, and better on a full week.** A single charge without a discharge will always be red.

## Reading the card

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/card-dark.png">
  <img alt="Battery ROI card" src="docs/card-light.png" width="420">
</picture>

| Part of the card | Meaning |
| --- | --- |
| **Today** / **This month** tiles | Profit so far, with *Yesterday* / *Last month* underneath for comparison |
| **Lifetime** tile | Everything the battery has earned since you set up Battery ROI (or last pressed *Reset totals*), with the start date underneath |
| Arrow and color | Green arrow up = earned money, red arrow down = cost money, grey = (about) zero |
| *Earning / Spending / Idle €…/h* | What the battery earns or costs **right now**, per hour |
| Price, ☀ kW, 🔋 % | Current price per kWh, solar production and battery level (only if you set those sensors) |
| Pace | This month's profit projected to a full month |
| Payback | Years until the battery has paid for itself at the rate so far |
| Efficiency | kWh out ÷ kWh in; 80 to 90% is normal for home batteries |

Tap a tile or the ticker to see its history graph.

## After setup

| I want to… | Where |
| --- | --- |
| Change which sensors are used | **Settings → Devices & services → Battery ROI → Configure** (your totals are kept) |
| Fill in history from the day you got the battery | **Configure** → *Battery costs* → **Battery installed on**, see below |
| Start the totals from zero | **Settings → Devices & services → Battery ROI → device → Reset totals → Press** |
| See all Battery ROI numbers | **Settings → Devices & services → Battery ROI → device** |
| See a number's history | Tap it on the card |
| Change what the card shows | Edit the dashboard → click the card → **Edit** |
| Update to a new version | **Settings** lists an update for **Battery ROI** at the top → click it → **Install**, then restart (step 3). The card then shows an orange *Battery ROI was updated* bar: tap it once to load the new card |

### Start from your install date

Had the battery before you installed Battery ROI? Fill in **Battery installed on** (in setup, or later via **Configure** → *Battery costs*). Battery ROI then replays Home Assistant's own history from that day and fills in Today, This month, Lifetime, energy and payback. A notification tells you when it's done and from which day it found data.

How far back it can go depends on what Home Assistant kept:

| Period | What Battery ROI uses | Accuracy |
| --- | --- | --- |
| Last ~10 days (the recorder's default) | Every recorded sensor change | Same as live tracking |
| Older | Hourly averages from long-term statistics | Close, but prices and power inside an hour are averaged |
| Before your sensors existed in Home Assistant | Nothing | Not counted |

- Long-term statistics only exist for sensors with a *state class*. Most battery power sensors have one; some price sensors don't, and hours without a price are skipped.
- Hours when Home Assistant was off are skipped rather than guessed.
- The replay **replaces** the current totals. It runs once per date; change the date to run it again.

**Numbers look wrong?**

- *Profit is negative on day one* → normal while the battery is charging, see [Your first day](#your-first-day-why-the-numbers-look-odd).
- *Profit goes down while the battery is **discharging*** → the sign is flipped. Change **Positive power means** (step 4 via Configure), or check your grid power sensor, then **Reset totals**.
- *Profit is far too small or large* → check the price sensor's unit (EUR/kWh, ct/kWh and EUR/MWh are handled) and that *Extra cost* is only filled in for raw market prices.
- *Card says Battery ROI isn't set up* → finish step 4, then refresh the browser.
- *Card doesn't appear in the card list, or "Custom element doesn't exist: battery-roi-card"* → the page was loaded before Battery ROI was installed, and Home Assistant never adds a new card to a page that is already open. In a browser press Ctrl+F5. In the phone app close the app completely (swipe it away) and open it again. Still missing? **Settings → Companion app → Troubleshooting → Reset frontend cache**, then close and reopen the app once more.

### Card options

The visual editor covers everything. For YAML, all keys are optional:

| Option | Default |
| --- | --- |
| `title` | `Battery ROI` |
| `daily` | `sensor.battery_roi_profit_today` |
| `monthly` | `sensor.battery_roi_profit_this_month` |
| `total` | `sensor.battery_roi_profit_total` (the Lifetime tile) |
| `rate` | `sensor.battery_roi_rate` |
| `payback` | `sensor.battery_roi_payback` |
| `efficiency` | `sensor.battery_roi_efficiency` |
| `price`, `soc` | read from the rate sensor |
| `currency` | your Home Assistant currency |

The **pace** line projects this month's profit to a full month, using the exact time elapsed; it stays hidden on the 1st.

## Sensors

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/sensors-dark.png">
  <img alt="Battery ROI sensors in Home Assistant" src="docs/sensors-light.png" align="right" width="260">
</picture>

| Sensor | Meaning |
| --- | --- |
| `sensor.battery_roi_rate` | €/h right now. Positive = earning. Attributes: price, feed-in price, grid kW, solar kW, state of charge |
| `sensor.battery_roi_profit_today` | Profit today, `last_period` = yesterday |
| `sensor.battery_roi_profit_this_month` | Profit this month, `last_period` = last month |
| `sensor.battery_roi_profit_total` | Profit since setup, `tracking_since` = start date |
| `sensor.battery_roi_energy_charged` | kWh into the battery |
| `sensor.battery_roi_energy_discharged` | kWh out of the battery |
| `sensor.battery_roi_efficiency` | Discharged ÷ charged, shown after 1 kWh |
| `sensor.battery_roi_payback` | Years until the battery has paid for itself at the average rate so far. Only exists if you entered a purchase cost; shown after 7 days with positive profit |
| `button.battery_roi_reset_totals` | Start all totals from zero |

Totals survive restarts. Gaps longer than 15 minutes (Home Assistant down, sensor offline) are skipped rather than guessed.

<br clear="right">

## How profit is calculated

Profit is **your grid bill without the battery minus your grid bill with it**.

```mermaid
flowchart LR
    B[Battery power<br/>charge / discharge] --> S((every 30 s))
    P[Price now<br/>+ extra cost] --> S
    F[Feed-in price] -.-> S
    G[Grid power] -.-> S
    S --> R[€/h right now]
    R --> T[Today · Month · Total]
```

- **Price sensor only.** `profit per hour = (discharge kW − charge kW) × price`. The same price is used in both directions, which is right under net metering (*salderingsregeling*).
- **Plus feed-in price and grid power.** Battery ROI can tell solar charging from grid charging. Each kWh is valued at the price it actually displaced:

| Battery is… | While the house is… | Valued at |
| --- | --- | --- |
| discharging | importing from the grid | import price (avoided buying) |
| discharging | exporting | feed-in price (extra sold) |
| charging | exporting solar surplus | feed-in price (gave up selling) |
| charging | importing | import price (bought) |

**Is solar charging free?** Only if you'd get nothing for exporting it. Storing a solar kWh means not selling it, so it costs whatever you'd have been paid:

- **Net metering (saldering):** an exported kWh cancels a bought one, so a stored solar kWh is worth the full price. Leave both feed-in fields empty; the plain price model is then correct.
- **No net metering:** set a feed-in price (sensor or fixed) plus grid power. Solar charging then costs that feed-in price, often a few cents, and grid charging costs the full import price.
- **You get nothing for export:** set the fixed feed-in price to 0 and solar charging is free.

Included: round-trip losses, because you charge more kWh than you get back. Optional: the battery's own standby draw, and wear per kWh discharged (counted once, not on both charge and discharge).

> **Tip for the Netherlands:** net metering ends on 1 January 2027. From then on a stored solar kWh is worth the feed-in price, not the import price, so add a feed-in price and your grid meter to keep the numbers honest.

> **Tip for raw EPEX prices:** they exclude energy tax, supplier fee and VAT. Fill in *Extra cost per kWh* and *VAT*: the import price becomes (market price + extra cost) × (1 + VAT).

## FAQ

<details>
<summary><b>Why do I see "icon not available" instead of the Battery ROI icon?</b></summary>

The icon ships inside the integration, which Home Assistant supports from version 2026.3. On older versions the icon stays empty; everything else works.

</details>

<details>
<summary><b>Why not just use the battery's state of charge?</b></summary>

State of charge moves in whole percents and hides charging losses, so a 5 kWh battery can hide 50 Wh per step. Power sensors give the real flow.
</details>

<details>
<summary><b>The numbers start at zero. Can I import history?</b></summary>

Yes, see [Start from your install date](#start-from-your-install-date).
</details>

<details>
<summary><b>Can I use my own card?</b></summary>

Yes. All numbers are ordinary sensors, so Mushroom, Tile or any other card works.
</details>

## Development

```bash
pip install -r requirements_test.txt
pytest
```

CI runs Home Assistant's `hassfest` validation and the test suite on every pull request. The screenshots above come from a real Home Assistant 2026.2 with demo sensors.

## License

[MIT](LICENSE)

## Contributing

Issues and pull requests are welcome at [github.com/PeterSlijkhuis/Battery-ROI](https://github.com/PeterSlijkhuis/Battery-ROI/issues).
