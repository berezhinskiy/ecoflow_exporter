# ⚡ EcoFlow to Prometheus exporter

![GitHub](https://img.shields.io/github/license/berezhinskiy/ecoflow_exporter)
![Build Status](https://github.com/berezhinskiy/ecoflow_exporter/workflows/CI/badge.svg)
![GitHub branch checks state](https://img.shields.io/github/checks-status/berezhinskiy/ecoflow_exporter/master)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/berezhinskiy/ecoflow_exporter)

## About

An implementation of a Prometheus exporter for [EcoFlow](https://www.ecoflow.com/) products. To receive information from the device, exporter works the same way as the official mobile application by subscribing to EcoFlow MQTT Broker `mqtt.ecoflow.com`

Unlike REST API exporters, it is not required to request for `APP_KEY` and `SECRET_KEY` since MQTT credentials can be extracted from `api.ecoflow.com`. Another benefit of such implementation is that it provides much more device information:

[![Dashboard](images/EcoflowMQTT.png?raw=true)](https://grafana.com/grafana/dashboards/17812-ecoflow/)

The project provides:

- [Python program](ecoflow_exporter.py) that accepts a number of arguments to collect information about a device and exports the collected metrics to a prometheus endpoint
- [Dashboard for Grafana](https://grafana.com/grafana/dashboards/17812-ecoflow/)
- [Docker image](https://github.com/berezhinskiy/ecoflow_exporter/pkgs/container/ecoflow_exporter) for your convenience
- [Quick Start guide](docker-compose/) for your pleasure

The exporter collects all possible metrics names and their values sent by the device to MQTT EcoFlow Broker. In case of any new objects in the queue, new metrics will be generated automatically based on the JSON object key/value. For example, payload:

```json
{
  "bms_bmsStatus.minCellTemp": 25,
  "bms_bmsStatus.maxCellTemp": 27,
  "bms_emsStatus.f32LcdShowSoc": 56.5,
  "inv.acInVol": 242182,
  "inv.invOutVol": 244582
}
```

will generate the following metrics:

```plain
ecoflow_bms_bms_status_min_cell_temp{device="XXXXXXXXXXXXXXXX"} 25.0
ecoflow_bms_bms_status_max_cell_temp{device="XXXXXXXXXXXXXXXX"} 27.0
ecoflow_bms_ems_status_f32_lcd_show_soc{device="XXXXXXXXXXXXXXXX"} 56.5
ecoflow_inv_ac_in_vol{device="XXXXXXXXXXXXXXXX"} 242182.0
ecoflow_inv_inv_out_vol{device="XXXXXXXXXXXXXXXX"} 244582.0
```

All metrics are prefixed with `ecoflow` and reports label `device` for multiple device support

## Disclaimers

⚠️ This project is in no way connected to EcoFlow company, and is entirely developed as a fun project with no guarantees of anything.

⚠️ Unexpectedly, some values are always zero (like `ecoflow_bms_ems_status_fan_level` and `ecoflow_inv_fan_state`). It is not a bug in the exporter. No need to create an issue. The exporter just converts the MQTT payload to Prometheus format. It implements small hacks like [here](ecoflow_exporter.py#L248-L252), but in general, values is provided by the device as it is. To dive into received payloads, enable `DEBUG` logging.

⚠️ This has only been tested with the following EcoFlow products:

- __RIVER Max__
- __RIVER 2__
- __RIVER 2 Max__
- __DELTA Max__
- __DELTA 2__
- __DELTA 2 Max__
- __DELTA Pro__

Please, create an issue to let me know if exporter works well (or not) with your model.

## Usage

- Connect the device to WiFi and register an EcoFlow account using the official mobile application
- Get your unit's serial number
- Exporter is parameterized via environment variables:

Required:

`DEVICE_SN` - the device serial number

`ECOFLOW_USERNAME` - EcoFlow account username

`ECOFLOW_PASSWORD` - EcoFlow account password

Optional:

`DEVICE_NAME` - If given, this name will be exported as `device` label instead of the device serial number

`ECOFLOW_API_HOST` - (default: `api.ecoflow.com`).

`EXPORTER_PORT` - (default: `9090`)

`LOG_LEVEL` - (default: `INFO`) Possible values: `DEBUG`, `INFO`, `WARNING`, `ERROR`

- Example of running docker image:

```bash
docker run -e DEVICE_SN=<your device SN> -e ECOFLOW_USERNAME=<your username> -e ECOFLOW_PASSWORD=<your password> -it -p 9090:9090 --network=host ghcr.io/berezhinskiy/ecoflow_exporter
```

will run the image with the exporter on `*:9090`

## Quick Start

Don't know anything about Prometheus? Wanna a quick start? Lazy person? [This guide](docker-compose/) is for you.

## Metrics

Prepared by exporter itself:

- `ecoflow_online`
- `ecoflow_mqtt_messages_receive_total`
- `ecoflow_mqtt_messages_receive_created`

Actual list of payload metrics:

- `ecoflow_bms_bms_status_amp`
- `ecoflow_bms_bms_status_bms_fault`
- `ecoflow_bms_bms_status_bq_sys_stat_reg`
- `ecoflow_bms_bms_status_cell_id`
- `ecoflow_bms_bms_status_cycles`
- `ecoflow_bms_bms_status_design_cap`
- `ecoflow_bms_bms_status_err_code`
- `ecoflow_bms_bms_status_f32_show_soc`
- `ecoflow_bms_bms_status_full_cap`
- `ecoflow_bms_bms_status_input_watts`
- `ecoflow_bms_bms_status_max_cell_temp`
- `ecoflow_bms_bms_status_max_cell_vol`
- `ecoflow_bms_bms_status_max_mos_temp`
- `ecoflow_bms_bms_status_min_cell_temp`
- `ecoflow_bms_bms_status_min_cell_vol`
- `ecoflow_bms_bms_status_min_mos_temp`
- `ecoflow_bms_bms_status_num`
- `ecoflow_bms_bms_status_open_bms_idx`
- `ecoflow_bms_bms_status_output_watts`
- `ecoflow_bms_bms_status_remain_cap`
- `ecoflow_bms_bms_status_remain_time`
- `ecoflow_bms_bms_status_soc`
- `ecoflow_bms_bms_status_soh`
- `ecoflow_bms_bms_status_sys_ver`
- `ecoflow_bms_bms_status_tag_chg_amp`
- `ecoflow_bms_bms_status_temp`
- `ecoflow_bms_bms_status_type`
- `ecoflow_bms_bms_status_vol`
- `ecoflow_bms_ems_status_bms_model`
- `ecoflow_bms_ems_status_bms_war_state`
- `ecoflow_bms_ems_status_chg_amp`
- `ecoflow_bms_ems_status_chg_cmd`
- `ecoflow_bms_ems_status_chg_remain_time`
- `ecoflow_bms_ems_status_chg_state`
- `ecoflow_bms_ems_status_chg_vol`
- `ecoflow_bms_ems_status_dsg_cmd`
- `ecoflow_bms_ems_status_dsg_remain_time`
- `ecoflow_bms_ems_status_ems_is_normal_flag`
- `ecoflow_bms_ems_status_f32_lcd_show_soc`
- `ecoflow_bms_ems_status_fan_level`
- `ecoflow_bms_ems_status_lcd_show_soc`
- `ecoflow_bms_ems_status_max_avail_num`
- `ecoflow_bms_ems_status_max_charge_soc`
- `ecoflow_bms_ems_status_max_close_oil_eb`
- `ecoflow_bms_ems_status_min_dsg_soc`
- `ecoflow_bms_ems_status_min_open_oil_eb`
- `ecoflow_bms_ems_status_open_bms_idx`
- `ecoflow_bms_ems_status_open_ups_flag`
- `ecoflow_bms_ems_status_para_vol_max`
- `ecoflow_bms_ems_status_para_vol_min`
- `ecoflow_inv_ac_dip_switch`
- `ecoflow_inv_ac_in_amp`
- `ecoflow_inv_ac_in_freq`
- `ecoflow_inv_ac_in_vol`
- `ecoflow_inv_cfg_ac_enabled`
- `ecoflow_inv_cfg_ac_out_freq`
- `ecoflow_inv_cfg_ac_out_vol`
- `ecoflow_inv_cfg_ac_work_mode`
- `ecoflow_inv_cfg_ac_xboost`
- `ecoflow_inv_charger_type`
- `ecoflow_inv_chg_pause_flag`
- `ecoflow_inv_dc_in_amp`
- `ecoflow_inv_dc_in_temp`
- `ecoflow_inv_dc_in_vol`
- `ecoflow_inv_discharge_type`
- `ecoflow_inv_err_code`
- `ecoflow_inv_fan_state`
- `ecoflow_inv_fast_chg_watts`
- `ecoflow_inv_input_watts`
- `ecoflow_inv_inv_out_amp`
- `ecoflow_inv_inv_out_freq`
- `ecoflow_inv_inv_out_vol`
- `ecoflow_inv_inv_type`
- `ecoflow_inv_out_temp`
- `ecoflow_inv_output_watts`
- `ecoflow_inv_slow_chg_watts`
- `ecoflow_inv_standby_mins`
- `ecoflow_inv_sys_ver`
- `ecoflow_mppt_ac_standby_mins`
- `ecoflow_mppt_beep_state`
- `ecoflow_mppt_car_out_amp`
- `ecoflow_mppt_car_out_vol`
- `ecoflow_mppt_car_out_watts`
- `ecoflow_mppt_car_standby_min`
- `ecoflow_mppt_car_state`
- `ecoflow_mppt_car_temp`
- `ecoflow_mppt_cfg_ac_enabled`
- `ecoflow_mppt_cfg_ac_out_freq`
- `ecoflow_mppt_cfg_ac_out_vol`
- `ecoflow_mppt_cfg_ac_xboost`
- `ecoflow_mppt_cfg_chg_type`
- `ecoflow_mppt_cfg_chg_watts`
- `ecoflow_mppt_chg_pause_flag`
- `ecoflow_mppt_chg_state`
- `ecoflow_mppt_chg_type`
- `ecoflow_mppt_dc24v_state`
- `ecoflow_mppt_dc24v_temp`
- `ecoflow_mppt_dc_chg_current`
- `ecoflow_mppt_dcdc12v_amp`
- `ecoflow_mppt_dcdc12v_vol`
- `ecoflow_mppt_dcdc12v_watts`
- `ecoflow_mppt_discharge_type`
- `ecoflow_mppt_fault_code`
- `ecoflow_mppt_in_amp`
- `ecoflow_mppt_in_vol`
- `ecoflow_mppt_in_watts`
- `ecoflow_mppt_mppt_temp`
- `ecoflow_mppt_out_amp`
- `ecoflow_mppt_out_vol`
- `ecoflow_mppt_out_watts`
- `ecoflow_mppt_pow_standby_min`
- `ecoflow_mppt_scr_standby_min`
- `ecoflow_mppt_sw_ver`
- `ecoflow_mppt_x60_chg_type`
- `ecoflow_pd_ac_auto_on_cfg`
- `ecoflow_pd_ac_enabled`
- `ecoflow_pd_beep_mode`
- `ecoflow_pd_bright_level`
- `ecoflow_pd_car_state`
- `ecoflow_pd_car_temp`
- `ecoflow_pd_car_used_time`
- `ecoflow_pd_car_watts`
- `ecoflow_pd_charger_type`
- `ecoflow_pd_chg_dsg_state`
- `ecoflow_pd_chg_power_a_c`
- `ecoflow_pd_chg_power_d_c`
- `ecoflow_pd_chg_sun_power`
- `ecoflow_pd_dc_in_used_time`
- `ecoflow_pd_dc_out_state`
- `ecoflow_pd_dsg_power_a_c`
- `ecoflow_pd_dsg_power_d_c`
- `ecoflow_pd_err_code`
- `ecoflow_pd_ext3p8_port`
- `ecoflow_pd_ext4p8_port`
- `ecoflow_pd_ext_rj45_port`
- `ecoflow_pd_in_watts`
- `ecoflow_pd_input_watts`
- `ecoflow_pd_inv_used_time`
- `ecoflow_pd_lcd_off_sec`
- `ecoflow_pd_model`
- `ecoflow_pd_mppt_used_time`
- `ecoflow_pd_out_watts`
- `ecoflow_pd_output_watts`
- `ecoflow_pd_pv_chg_prio_set`
- `ecoflow_pd_qc_usb1_watts`
- `ecoflow_pd_qc_usb2_watts`
- `ecoflow_pd_remain_time`
- `ecoflow_pd_soc`
- `ecoflow_pd_standby_min`
- `ecoflow_pd_sys_ver`
- `ecoflow_pd_typec1_temp`
- `ecoflow_pd_typec1_watts`
- `ecoflow_pd_typec2_temp`
- `ecoflow_pd_typec2_watts`
- `ecoflow_pd_typec_used_time`
- `ecoflow_pd_usb1_watts`
- `ecoflow_pd_usb2_watts`
- `ecoflow_pd_usb_used_time`
- `ecoflow_pd_usbqc_used_time`
- `ecoflow_pd_watts_in_sum`
- `ecoflow_pd_watts_out_sum`
- `ecoflow_pd_wifi_auto_rcvy`
- `ecoflow_pd_wifi_rssi`
- `ecoflow_pd_wifi_ver`
- `ecoflow_pd_wire_watts`
