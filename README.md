# Battery ROI Scoreboard

A Home Assistant card that shows how much money your home battery made today and this month by charging when power was cheap and discharging when it was expensive.

![preview](docs/preview.png)

## What "profit" means here

```
profit = ∫ (discharge_kW − charge_kW) × tariff_now  dt
```

Every moment the battery discharges, the energy is valued at that moment's tariff. Every moment it charges, the energy is costed at that moment's tariff. This equals "hourly kWh × hourly price" but also works with 15‑minute prices.

Included: round‑trip losses (you charge more kWh than you get back).
Not included: battery wear, and the difference between import and feed‑in prices (one all‑in price is used for both directions; see caveats).

## Install

1. Copy `packages/battery_roi.yaml` to `<config>/packages/` and make sure `configuration.yaml` has:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
2. Edit the **CONFIG** block at the top of that file. Every entity id marked `PLACEHOLDER` must point at your own sensors:
   | Placeholder | What it should be |
   | --- | --- |
   | `sensor.ecoflow_battery_charge_power` | Power into the battery, W |
   | `sensor.ecoflow_battery_discharge_power` | Power out of the battery, W |
   | `sensor.electricity_price_current` | Dynamic tariff, EUR/kWh |
   | `sensor.ecoflow_battery_level` | State of charge, % (display only) |
   | `sensor.p1_meter_active_power` | HomeWizard P1 power, W (display only) |
3. Restart Home Assistant. You get:
   - `sensor.battery_roi_rate` live EUR/h (positive = earning)
   - `sensor.battery_roi_profit_total` running total
   - `sensor.battery_roi_profit_daily` / `sensor.battery_roi_profit_monthly` (previous period in `last_period`)
4. Copy `battery-roi-card.js` to `<config>/www/`, add it under Settings → Dashboards → Resources as `/local/battery-roi-card.js` (type: JavaScript module), and add the card:
   ```yaml
   type: custom:battery-roi-card
   ```
   Optional keys: `title`, `daily`, `monthly`, `rate`, `soc`, `price`, `currency` (default `EUR`).

The card uses only Home Assistant theme variables (`--success-color`, `--error-color`, `--primary-text-color`, ...), so it follows your theme and dark mode.

## Caveats

- **State of charge is not enough.** SoC changes are rounded to whole percents and hide losses, so the maths uses charge and discharge power. If your EcoFlow only exposes one signed power sensor, the CONFIG block shows the variant to use.
- **One price for both directions.** Right for Dutch net metering (saldering) where exported kWh are netted at the import price. Saldering ends on 1 January 2027; after that, energy the battery exports is worth the feed‑in price and solar energy stored in it costs you the feed‑in price you gave up. The HomeWizard P1 sensor is already aliased in the package for that split.
- **Lit is loaded from a CDN** (`cdn.jsdelivr.net`). If your Home Assistant has no internet, download that file into `www/` and change the import URL at the top of the card.
