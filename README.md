# ecoflow-mqtt-prometheus-exporter

An Ecoflow MQTT to prometheus metrics converter

It is not required to request REST `APP_KEY` and `SECRET_KEY` since MQTT credentials can be extracted from `api.ecoflow.com` (see [Usage](#usage) section)

[![Dashboard](images/EcoflowMQTT.png?raw=true)](https://grafana.com/grafana/dashboards/17812-ecoflow-mqtt/)

## Disclaimers

Disclaimer 1: This project is in no way connected to Ecoflow the company, and is entirely developed as a fun project (with no guarantees of anything)

Disclaimer 2: This has only been tested with __Ecoflow DELTA 2__

## About

An implementation of a prometheus exporter for [Ecoflow](https://www.ecoflow.com/) products that support the EcoFlow MQTT backend

The project provides:

- Simple python program that accepts a number of arguments to collect information about an Ecoflow product and then exports the collected metrics to a prometheus endpoint
- Bash script to extract MQTT credentials
- [Docker image](https://hub.docker.com/repository/docker/berezhinskiy/ecoflow-mqtt-prometheus-exporter) for your convenience
- [Dashboard for Grafana](https://grafana.com/grafana/dashboards/17812-ecoflow-mqtt/)

All metrics produced are prefixed with `ecoflow` and reports label `device_sn` for multiple device support

## Usage

- Get your unit's serial number (displayed on Ecoflow application)
- Get MQTT credentials for your Ecoflow account:

```bash
> bash get_mqtt_credentials.sh
Checking if jq is installed
Checking if base64 is installed
Checking if curl is installed
Checking if sed is installed

Everything is ready to extract the mqtt data
Please log in now:

Ecoflow email:
Ecoflow password:
{
  "code": "0",
  "message": "Success",
  "data": {
    "url": "mqtt.ecoflow.com",
    "port": "8883",
    "protocol": "mqtts",
    "certificateAccount": "app-b12d847861bb84eaa103446f606d41bb",
    "certificatePassword": "28dd5feff0bf4420bfcdaecfc18418a6"
  }
}
```

- The program is parameterized via environment variables:

Required:

`DEVICE_SN` - the device serial number

`MQTT_USERNAME` - the username provided by script as `certificateAccount`

`MQTT_PASSWORD` - the password provided by script as `certificatePassword`

Optional:

`MQTT_BROKER` - (default: `mqtt.ecoflow.com`)

`MQTT_PORT` - (default: `8883`)

`EXPORTER_PORT` - (default: `9090`)

`LOG_LEVEL` - (default: `INFO`) Possible values: `DEBUG`, `INFO`, `WARNING`, `ERROR`

Example of running docker image:

`docker run -e DEVICE_SN=<your device SN> -e MQTT_USERNAME=<your MQTT username> -e MQTT_PASSWORD=<your MQTT password> -it -p 9090:9090 --network=host berezhinskiy/ecoflow-mqtt-prometheus-exporter`

will run the image with the exporter running on *:9090

## Exported metrics

- `ecoflow_online`
- `ecoflow_mqtt_messages_receive_total`
- `ecoflow_mppt_car_out_vol`
- `ecoflow_mppt_car_state`
- `ecoflow_mppt_discharge_type`
- `ecoflow_mppt_fault_code`
- `ecoflow_mppt_dc24v_state`
- `ecoflow_mppt_cfg_ac_xboost`
- `ecoflow_mppt_car_temp`
- `ecoflow_mppt_out_watts`
- `ecoflow_mppt_sw_ver`
- `ecoflow_mppt_x60_chg_type`
- `ecoflow_mppt_car_out_amp`
- `ecoflow_mppt_out_amp`
- `ecoflow_mppt_chg_pause_flag`
- `ecoflow_mppt_dcdc12v_watts`
- `ecoflow_mppt_ac_standby_mins`
- `ecoflow_mppt_pow_standby_min`
- `ecoflow_mppt_in_watts`
- `ecoflow_mppt_dcdc12v_vol`
- `ecoflow_mppt_in_amp`
- `ecoflow_mppt_scr_standby_min`
- `ecoflow_mppt_in_vol`
- `ecoflow_mppt_car_out_watts`
- `ecoflow_mppt_mppt_temp`
- `ecoflow_mppt_out_vol`
- `ecoflow_mppt_cfg_ac_enabled`
- `ecoflow_mppt_chg_type`
- `ecoflow_mppt_dcdc12v_amp`
- `ecoflow_mppt_beep_state`
- `ecoflow_mppt_cfg_ac_out_vol`
- `ecoflow_mppt_cfg_chg_type`
- `ecoflow_mppt_dc24v_temp`
- `ecoflow_mppt_car_standby_min`
- `ecoflow_mppt_dc_chg_current`
- `ecoflow_mppt_chg_state`
- `ecoflow_mppt_cfg_chg_watts`
- `ecoflow_mppt_cfg_ac_out_freq`
- `ecoflow_pd_input_watts`
- `ecoflow_pd_typec1_temp`
- `ecoflow_pd_watts_in_sum`
- `ecoflow_pd_dc_in_used_time`
- `ecoflow_pd_wifi_ver`
- `ecoflow_pd_model`
- `ecoflow_pd_wifi_auto_rcvy`
- `ecoflow_pd_beep_mode`
- `ecoflow_pd_remain_time`
- `ecoflow_pd_typec2_watts`
- `ecoflow_pd_ext4p8_port`
- `ecoflow_pd_charger_type`
- `ecoflow_pd_chg_sun_power`
- `ecoflow_pd_pv_chg_prio_set`
- `ecoflow_pd_car_temp`
- `ecoflow_pd_usb1_watts`
- `ecoflow_pd_in_watts`
- `ecoflow_pd_dsg_power_a_c`
- `ecoflow_pd_qc_usb2_watts`
- `ecoflow_pd_wire_watts`
- `ecoflow_pd_chg_power_a_c`
- `ecoflow_pd_lcd_off_sec`
- `ecoflow_pd_ext_rj45_port`
- `ecoflow_pd_sys_ver`
- `ecoflow_pd_typec2_temp`
- `ecoflow_pd_car_used_time`
- `ecoflow_pd_typec1_watts`
- `ecoflow_pd_chg_dsg_state`
- `ecoflow_pd_out_watts`
- `ecoflow_pd_soc`
- `ecoflow_pd_qc_usb1_watts`
- `ecoflow_pd_ext3p8_port`
- `ecoflow_pd_chg_power_d_c`
- `ecoflow_pd_dsg_power_d_c`
- `ecoflow_pd_ac_enabled`
- `ecoflow_pd_standby_min`
- `ecoflow_pd_typec_used_time`
- `ecoflow_pd_bright_level`
- `ecoflow_pd_usbqc_used_time`
- `ecoflow_pd_ac_auto_on_cfg`
- `ecoflow_pd_dc_out_state`
- `ecoflow_pd_watts_out_sum`
- `ecoflow_pd_usb_used_time`
- `ecoflow_pd_mppt_used_time`
- `ecoflow_pd_wifi_rssi`
- `ecoflow_pd_output_watts`
- `ecoflow_pd_err_code`
- `ecoflow_pd_car_watts`
- `ecoflow_pd_usb2_watts`
- `ecoflow_pd_car_state`
- `ecoflow_pd_inv_used_time`
- `ecoflow_bms_ems_status_dsg_cmd`
- `ecoflow_bms_ems_status_chg_vol`
- `ecoflow_bms_ems_status_chg_remain_time`
- `ecoflow_bms_ems_status_f32_lcd_show_soc`
- `ecoflow_bms_ems_status_max_charge_soc`
- `ecoflow_bms_ems_status_para_vol_max`
- `ecoflow_bms_ems_status_lcd_show_soc`
- `ecoflow_bms_ems_status_bms_model`
- `ecoflow_bms_ems_status_chg_amp`
- `ecoflow_bms_ems_status_chg_state`
- `ecoflow_bms_ems_status_open_ups_flag`
- `ecoflow_bms_ems_status_open_bms_idx`
- `ecoflow_bms_ems_status_min_dsg_soc`
- `ecoflow_bms_ems_status_para_vol_min`
- `ecoflow_bms_ems_status_min_open_oil_eb`
- `ecoflow_bms_ems_status_chg_cmd`
- `ecoflow_bms_ems_status_max_avail_num`
- `ecoflow_bms_ems_status_max_close_oil_eb`
- `ecoflow_bms_ems_status_ems_is_normal_flag`
- `ecoflow_bms_ems_status_bms_war_state`
- `ecoflow_bms_ems_status_dsg_remain_time`
- `ecoflow_bms_ems_status_fan_level`
- `ecoflow_bms_bms_status_sys_ver`
- `ecoflow_bms_bms_status_min_cell_temp`
- `ecoflow_bms_bms_status_design_cap`
- `ecoflow_bms_bms_status_temp`
- `ecoflow_bms_bms_status_min_cell_vol`
- `ecoflow_bms_bms_status_cycles`
- `ecoflow_bms_bms_status_f32_show_soc`
- `ecoflow_bms_bms_status_output_watts`
- `ecoflow_bms_bms_status_max_cell_vol`
- `ecoflow_bms_bms_status_type`
- `ecoflow_bms_bms_status_soh`
- `ecoflow_bms_bms_status_max_cell_temp`
- `ecoflow_bms_bms_status_remain_cap`
- `ecoflow_bms_bms_status_cell_id`
- `ecoflow_bms_bms_status_min_mos_temp`
- `ecoflow_bms_bms_status_vol`
- `ecoflow_bms_bms_status_remain_time`
- `ecoflow_bms_bms_status_full_cap`
- `ecoflow_bms_bms_status_bq_sys_stat_reg`
- `ecoflow_bms_bms_status_open_bms_idx`
- `ecoflow_bms_bms_status_amp`
- `ecoflow_bms_bms_status_num`
- `ecoflow_bms_bms_status_bms_fault`
- `ecoflow_bms_bms_status_soc`
- `ecoflow_bms_bms_status_err_code`
- `ecoflow_bms_bms_status_input_watts`
- `ecoflow_bms_bms_status_tag_chg_amp`
- `ecoflow_bms_bms_status_max_mos_temp`
- `ecoflow_inv_dc_in_vol`
- `ecoflow_inv_cfg_ac_work_mode`
- `ecoflow_inv_slow_chg_watts`
- `ecoflow_inv_dc_in_amp`
- `ecoflow_inv_cfg_ac_out_freq`
- `ecoflow_inv_output_watts`
- `ecoflow_inv_err_code`
- `ecoflow_inv_dc_in_temp`
- `ecoflow_inv_inv_out_freq`
- `ecoflow_inv_charger_type`
- `ecoflow_inv_ac_in_amp`
- `ecoflow_inv_fan_state`
- `ecoflow_inv_cfg_ac_xboost`
- `ecoflow_inv_cfg_ac_enabled`
- `ecoflow_inv_out_temp`
- `ecoflow_inv_inv_type`
- `ecoflow_inv_cfg_ac_out_vol`
- `ecoflow_inv_ac_dip_switch`
- `ecoflow_inv_ac_in_vol`
- `ecoflow_inv_inv_out_vol`
- `ecoflow_inv_fast_chg_watts`
- `ecoflow_inv_input_watts`
- `ecoflow_inv_standby_mins`
- `ecoflow_inv_chg_pause_flag`
- `ecoflow_inv_ac_in_freq`
- `ecoflow_inv_discharge_type`
- `ecoflow_inv_inv_out_amp`
- `ecoflow_inv_sys_ver`
