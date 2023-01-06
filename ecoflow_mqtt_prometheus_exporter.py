import logging as log
import sys
import os
import random
import ssl
import time
import json
import paho.mqtt.client as mqtt
from queue import Queue
from prometheus_client import start_http_server, Gauge


class EcoflowMetrics:
    def __init__(self, message_queue, device_sn, polling_interval_seconds=5):
        self.device_sn = device_sn
        self.message_queue = message_queue
        self.polling_interval_seconds = polling_interval_seconds

        #
        # Metrics were generated from Ecoflow MQTT objects
        # Function to convert Ecoflow JSON key to prometheus name
        #
        # def convert_to_prometheus_name(value):
        #     new = value[0].lower()
        #     for character in value[1:]:
        #         if character.isupper():
        #             new += '_'
        #         new += character.lower()
        #     return f"{new}"
        #
        # name = "mppt.carOutVol"
        # name_prefix = convert_to_prometheus_name(name.split(".")[0])
        # name_suffix = convert_to_prometheus_name(name.split(".")[1])
        # print(f"{name_prefix}_{name_suffix}")

        self.online = Gauge("online", "online", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_car_out_vol = Gauge("mppt_car_out_vol", "mppt.carOutVol", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_car_state = Gauge("mppt_car_state", "mppt.carState", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_discharge_type = Gauge("mppt_discharge_type", "mppt.dischargeType", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_fault_code = Gauge("mppt_fault_code", "mppt.faultCode", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_dc24v_state = Gauge("mppt_dc24v_state", "mppt.dc24vState", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_cfg_ac_xboost = Gauge("mppt_cfg_ac_xboost", "mppt.cfgAcXboost", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_car_temp = Gauge("mppt_car_temp", "mppt.carTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_out_watts = Gauge("mppt_out_watts", "mppt.outWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_sw_ver = Gauge("mppt_sw_ver", "mppt.swVer", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_x60_chg_type = Gauge("mppt_x60_chg_type", "mppt.x60ChgType", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_car_out_amp = Gauge("mppt_car_out_amp", "mppt.carOutAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_out_amp = Gauge("mppt_out_amp", "mppt.outAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_chg_pause_flag = Gauge("mppt_chg_pause_flag", "mppt.chgPauseFlag", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_dcdc12v_watts = Gauge("mppt_dcdc12v_watts", "mppt.dcdc12vWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_ac_standby_mins = Gauge("mppt_ac_standby_mins", "mppt.acStandbyMins", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_pow_standby_min = Gauge("mppt_pow_standby_min", "mppt.powStandbyMin", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_in_watts = Gauge("mppt_in_watts", "mppt.inWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_dcdc12v_vol = Gauge("mppt_dcdc12v_vol", "mppt.dcdc12vVol", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_in_amp = Gauge("mppt_in_amp", "mppt.inAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_scr_standby_min = Gauge("mppt_scr_standby_min", "mppt.scrStandbyMin", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_in_vol = Gauge("mppt_in_vol", "mppt.inVol", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_car_out_watts = Gauge("mppt_car_out_watts", "mppt.carOutWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_mppt_temp = Gauge("mppt_mppt_temp", "mppt.mpptTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_out_vol = Gauge("mppt_out_vol", "mppt.outVol", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_cfg_ac_enabled = Gauge("mppt_cfg_ac_enabled", "mppt.cfgAcEnabled", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_chg_type = Gauge("mppt_chg_type", "mppt.chgType", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_dcdc12v_amp = Gauge("mppt_dcdc12v_amp", "mppt.dcdc12vAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_beep_state = Gauge("mppt_beep_state", "mppt.beepState", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_cfg_ac_out_vol = Gauge("mppt_cfg_ac_out_vol", "mppt.cfgAcOutVol", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_cfg_chg_type = Gauge("mppt_cfg_chg_type", "mppt.cfgChgType", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_dc24v_temp = Gauge("mppt_dc24v_temp", "mppt.dc24vTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_car_standby_min = Gauge("mppt_car_standby_min", "mppt.carStandbyMin", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_dc_chg_current = Gauge("mppt_dc_chg_current", "mppt.dcChgCurrent", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_chg_state = Gauge("mppt_chg_state", "mppt.chgState", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_cfg_chg_watts = Gauge("mppt_cfg_chg_watts", "mppt.cfgChgWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.mppt_cfg_ac_out_freq = Gauge("mppt_cfg_ac_out_freq", "mppt.cfgAcOutFreq", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_input_watts = Gauge("pd_input_watts", "pd.inputWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_typec1_temp = Gauge("pd_typec1_temp", "pd.typec1Temp", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_watts_in_sum = Gauge("pd_watts_in_sum", "pd.wattsInSum", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_dc_in_used_time = Gauge("pd_dc_in_used_time", "pd.dcInUsedTime", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_wifi_ver = Gauge("pd_wifi_ver", "pd.wifiVer", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_model = Gauge("pd_model", "pd.model", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_wifi_auto_rcvy = Gauge("pd_wifi_auto_rcvy", "pd.wifiAutoRcvy", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_beep_mode = Gauge("pd_beep_mode", "pd.beepMode", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_remain_time = Gauge("pd_remain_time", "pd.remainTime", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_typec2_watts = Gauge("pd_typec2_watts", "pd.typec2Watts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_ext4p8_port = Gauge("pd_ext4p8_port", "pd.ext4p8Port", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_charger_type = Gauge("pd_charger_type", "pd.chargerType", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_chg_sun_power = Gauge("pd_chg_sun_power", "pd.chgSunPower", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_pv_chg_prio_set = Gauge("pd_pv_chg_prio_set", "pd.pvChgPrioSet", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_car_temp = Gauge("pd_car_temp", "pd.carTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_usb1_watts = Gauge("pd_usb1_watts", "pd.usb1Watts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_in_watts = Gauge("pd_in_watts", "pd.inWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_dsg_power_a_c = Gauge("pd_dsg_power_a_c", "pd.dsgPowerAC", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_qc_usb2_watts = Gauge("pd_qc_usb2_watts", "pd.qcUsb2Watts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_wire_watts = Gauge("pd_wire_watts", "pd.wireWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_chg_power_a_c = Gauge("pd_chg_power_a_c", "pd.chgPowerAC", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_lcd_off_sec = Gauge("pd_lcd_off_sec", "pd.lcdOffSec", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_ext_rj45_port = Gauge("pd_ext_rj45_port", "pd.extRj45Port", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_sys_ver = Gauge("pd_sys_ver", "pd.sysVer", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_typec2_temp = Gauge("pd_typec2_temp", "pd.typec2Temp", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_car_used_time = Gauge("pd_car_used_time", "pd.carUsedTime", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_typec1_watts = Gauge("pd_typec1_watts", "pd.typec1Watts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_chg_dsg_state = Gauge("pd_chg_dsg_state", "pd.chgDsgState", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_out_watts = Gauge("pd_out_watts", "pd.outWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_soc = Gauge("pd_soc", "pd.soc", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_qc_usb1_watts = Gauge("pd_qc_usb1_watts", "pd.qcUsb1Watts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_ext3p8_port = Gauge("pd_ext3p8_port", "pd.ext3p8Port", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_chg_power_d_c = Gauge("pd_chg_power_d_c", "pd.chgPowerDC", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_dsg_power_d_c = Gauge("pd_dsg_power_d_c", "pd.dsgPowerDC", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_ac_enabled = Gauge("pd_ac_enabled", "pd.acEnabled", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_standby_min = Gauge("pd_standby_min", "pd.standbyMin", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_typec_used_time = Gauge("pd_typec_used_time", "pd.typecUsedTime", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_bright_level = Gauge("pd_bright_level", "pd.brightLevel", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_usbqc_used_time = Gauge("pd_usbqc_used_time", "pd.usbqcUsedTime", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_ac_auto_on_cfg = Gauge("pd_ac_auto_on_cfg", "pd.acAutoOnCfg", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_dc_out_state = Gauge("pd_dc_out_state", "pd.dcOutState", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_watts_out_sum = Gauge("pd_watts_out_sum", "pd.wattsOutSum", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_usb_used_time = Gauge("pd_usb_used_time", "pd.usbUsedTime", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_mppt_used_time = Gauge("pd_mppt_used_time", "pd.mpptUsedTime", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_wifi_rssi = Gauge("pd_wifi_rssi", "pd.wifiRssi", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_output_watts = Gauge("pd_output_watts", "pd.outputWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_err_code = Gauge("pd_err_code", "pd.errCode", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_car_watts = Gauge("pd_car_watts", "pd.carWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_usb2_watts = Gauge("pd_usb2_watts", "pd.usb2Watts", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_car_state = Gauge("pd_car_state", "pd.carState", labelnames=["device_sn"], namespace="ecoflow")
        self.pd_inv_used_time = Gauge("pd_inv_used_time", "pd.invUsedTime", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_dsg_cmd = Gauge("bms_ems_status_dsg_cmd", "bms_emsStatus.dsgCmd", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_chg_vol = Gauge("bms_ems_status_chg_vol", "bms_emsStatus.chgVol", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_chg_remain_time = Gauge("bms_ems_status_chg_remain_time", "bms_emsStatus.chgRemainTime", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_f32_lcd_show_soc = Gauge("bms_ems_status_f32_lcd_show_soc", "bms_emsStatus.f32LcdShowSoc", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_max_charge_soc = Gauge("bms_ems_status_max_charge_soc", "bms_emsStatus.maxChargeSoc", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_para_vol_max = Gauge("bms_ems_status_para_vol_max", "bms_emsStatus.paraVolMax", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_lcd_show_soc = Gauge("bms_ems_status_lcd_show_soc", "bms_emsStatus.lcdShowSoc", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_bms_model = Gauge("bms_ems_status_bms_model", "bms_emsStatus.bmsModel", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_chg_amp = Gauge("bms_ems_status_chg_amp", "bms_emsStatus.chgAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_chg_state = Gauge("bms_ems_status_chg_state", "bms_emsStatus.chgState", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_open_ups_flag = Gauge("bms_ems_status_open_ups_flag", "bms_emsStatus.openUpsFlag", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_open_bms_idx = Gauge("bms_ems_status_open_bms_idx", "bms_emsStatus.openBmsIdx", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_min_dsg_soc = Gauge("bms_ems_status_min_dsg_soc", "bms_emsStatus.minDsgSoc", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_para_vol_min = Gauge("bms_ems_status_para_vol_min", "bms_emsStatus.paraVolMin", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_min_open_oil_eb = Gauge("bms_ems_status_min_open_oil_eb", "bms_emsStatus.minOpenOilEb", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_chg_cmd = Gauge("bms_ems_status_chg_cmd", "bms_emsStatus.chgCmd", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_max_avail_num = Gauge("bms_ems_status_max_avail_num", "bms_emsStatus.maxAvailNum", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_max_close_oil_eb = Gauge("bms_ems_status_max_close_oil_eb", "bms_emsStatus.maxCloseOilEb", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_ems_is_normal_flag = Gauge("bms_ems_status_ems_is_normal_flag", "bms_emsStatus.emsIsNormalFlag", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_bms_war_state = Gauge("bms_ems_status_bms_war_state", "bms_emsStatus.bmsWarState", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_dsg_remain_time = Gauge("bms_ems_status_dsg_remain_time", "bms_emsStatus.dsgRemainTime", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_ems_status_fan_level = Gauge("bms_ems_status_fan_level", "bms_emsStatus.fanLevel", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_sys_ver = Gauge("bms_bms_status_sys_ver", "bms_bmsStatus.sysVer", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_min_cell_temp = Gauge("bms_bms_status_min_cell_temp", "bms_bmsStatus.minCellTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_design_cap = Gauge("bms_bms_status_design_cap", "bms_bmsStatus.designCap", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_temp = Gauge("bms_bms_status_temp", "bms_bmsStatus.temp", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_min_cell_vol = Gauge("bms_bms_status_min_cell_vol", "bms_bmsStatus.minCellVol", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_cycles = Gauge("bms_bms_status_cycles", "bms_bmsStatus.cycles", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_f32_show_soc = Gauge("bms_bms_status_f32_show_soc", "bms_bmsStatus.f32ShowSoc", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_output_watts = Gauge("bms_bms_status_output_watts", "bms_bmsStatus.outputWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_max_cell_vol = Gauge("bms_bms_status_max_cell_vol", "bms_bmsStatus.maxCellVol", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_type = Gauge("bms_bms_status_type", "bms_bmsStatus.type", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_soh = Gauge("bms_bms_status_soh", "bms_bmsStatus.soh", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_max_cell_temp = Gauge("bms_bms_status_max_cell_temp", "bms_bmsStatus.maxCellTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_remain_cap = Gauge("bms_bms_status_remain_cap", "bms_bmsStatus.remainCap", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_cell_id = Gauge("bms_bms_status_cell_id", "bms_bmsStatus.cellId", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_min_mos_temp = Gauge("bms_bms_status_min_mos_temp", "bms_bmsStatus.minMosTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_vol = Gauge("bms_bms_status_vol", "bms_bmsStatus.vol", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_remain_time = Gauge("bms_bms_status_remain_time", "bms_bmsStatus.remainTime", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_full_cap = Gauge("bms_bms_status_full_cap", "bms_bmsStatus.fullCap", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_bq_sys_stat_reg = Gauge("bms_bms_status_bq_sys_stat_reg", "bms_bmsStatus.bqSysStatReg", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_open_bms_idx = Gauge("bms_bms_status_open_bms_idx", "bms_bmsStatus.openBmsIdx", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_amp = Gauge("bms_bms_status_amp", "bms_bmsStatus.amp", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_num = Gauge("bms_bms_status_num", "bms_bmsStatus.num", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_bms_fault = Gauge("bms_bms_status_bms_fault", "bms_bmsStatus.bmsFault", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_soc = Gauge("bms_bms_status_soc", "bms_bmsStatus.soc", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_err_code = Gauge("bms_bms_status_err_code", "bms_bmsStatus.errCode", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_input_watts = Gauge("bms_bms_status_input_watts", "bms_bmsStatus.inputWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_tag_chg_amp = Gauge("bms_bms_status_tag_chg_amp", "bms_bmsStatus.tagChgAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.bms_bms_status_max_mos_temp = Gauge("bms_bms_status_max_mos_temp", "bms_bmsStatus.maxMosTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_dc_in_vol = Gauge("inv_dc_in_vol", "inv.dcInVol", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_cfg_ac_work_mode = Gauge("inv_cfg_ac_work_mode", "inv.cfgAcWorkMode", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_slow_chg_watts = Gauge("inv_slow_chg_watts", "inv.SlowChgWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_dc_in_amp = Gauge("inv_dc_in_amp", "inv.dcInAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_cfg_ac_out_freq = Gauge("inv_cfg_ac_out_freq", "inv.cfgAcOutFreq", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_output_watts = Gauge("inv_output_watts", "inv.outputWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_err_code = Gauge("inv_err_code", "inv.errCode", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_dc_in_temp = Gauge("inv_dc_in_temp", "inv.dcInTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_inv_out_freq = Gauge("inv_inv_out_freq", "inv.invOutFreq", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_charger_type = Gauge("inv_charger_type", "inv.chargerType", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_ac_in_amp = Gauge("inv_ac_in_amp", "inv.acInAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_fan_state = Gauge("inv_fan_state", "inv.fanState", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_cfg_ac_xboost = Gauge("inv_cfg_ac_xboost", "inv.cfgAcXboost", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_cfg_ac_enabled = Gauge("inv_cfg_ac_enabled", "inv.cfgAcEnabled", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_out_temp = Gauge("inv_out_temp", "inv.outTemp", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_inv_type = Gauge("inv_inv_type", "inv.invType", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_cfg_ac_out_vol = Gauge("inv_cfg_ac_out_vol", "inv.cfgAcOutVol", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_ac_dip_switch = Gauge("inv_ac_dip_switch", "inv.acDipSwitch", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_ac_in_vol = Gauge("inv_ac_in_vol", "inv.acInVol", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_inv_out_vol = Gauge("inv_inv_out_vol", "inv.invOutVol", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_fast_chg_watts = Gauge("inv_fast_chg_watts", "inv.FastChgWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_input_watts = Gauge("inv_input_watts", "inv.inputWatts", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_standby_mins = Gauge("inv_standby_mins", "inv.standbyMins", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_chg_pause_flag = Gauge("inv_chg_pause_flag", "inv.chgPauseFlag", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_ac_in_freq = Gauge("inv_ac_in_freq", "inv.acInFreq", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_discharge_type = Gauge("inv_discharge_type", "inv.dischargeType", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_inv_out_amp = Gauge("inv_inv_out_amp", "inv.invOutAmp", labelnames=["device_sn"], namespace="ecoflow")
        self.inv_sys_ver = Gauge("inv_sys_ver", "inv.sysVer", labelnames=["device_sn"], namespace="ecoflow")

    def run_metrics_loop(self):
        while True:
            self.fetch()
            time.sleep(self.polling_interval_seconds)

    def fetch(self):
        if self.message_queue.qsize() > 0:
            log.info(f"Processing {self.message_queue.qsize()} event(s) from the message queue")
            self.online.labels(device_sn=self.device_sn).set(1)
        else:
            log.info("Message queue is empty")
            self.online.labels(device_sn=self.device_sn).set(0)

        while not self.message_queue.empty():
            message = self.message_queue.get()
            if message is None:
                continue

            try:
                message = json.loads(message)
                params = message['params']
            except Exception:
                log.error(f"Cannot parse MQTT message: {message}")
                continue
            log.debug(f"Processing {params}")
            self.process(params)

    def process(self, message):
        #
        # Metrics were generated from Ecoflow MQTT JSON objects
        #
        try:
            self.mppt_car_out_vol.labels(device_sn=self.device_sn).set(message["mppt.carOutVol"])
            message.pop("mppt.carOutVol", None)
        except KeyError:
            pass
        try:
            self.mppt_car_state.labels(device_sn=self.device_sn).set(message["mppt.carState"])
            message.pop("mppt.carState", None)
        except KeyError:
            pass
        try:
            self.mppt_discharge_type.labels(device_sn=self.device_sn).set(message["mppt.dischargeType"])
            message.pop("mppt.dischargeType", None)
        except KeyError:
            pass
        try:
            self.mppt_fault_code.labels(device_sn=self.device_sn).set(message["mppt.faultCode"])
            message.pop("mppt.faultCode", None)
        except KeyError:
            pass
        try:
            self.mppt_dc24v_state.labels(device_sn=self.device_sn).set(message["mppt.dc24vState"])
            message.pop("mppt.dc24vState", None)
        except KeyError:
            pass
        try:
            self.mppt_cfg_ac_xboost.labels(device_sn=self.device_sn).set(message["mppt.cfgAcXboost"])
            message.pop("mppt.cfgAcXboost", None)
        except KeyError:
            pass
        try:
            self.mppt_car_temp.labels(device_sn=self.device_sn).set(message["mppt.carTemp"])
            message.pop("mppt.carTemp", None)
        except KeyError:
            pass
        try:
            self.mppt_out_watts.labels(device_sn=self.device_sn).set(message["mppt.outWatts"])
            message.pop("mppt.outWatts", None)
        except KeyError:
            pass
        try:
            self.mppt_sw_ver.labels(device_sn=self.device_sn).set(message["mppt.swVer"])
            message.pop("mppt.swVer", None)
        except KeyError:
            pass
        try:
            self.mppt_x60_chg_type.labels(device_sn=self.device_sn).set(message["mppt.x60ChgType"])
            message.pop("mppt.x60ChgType", None)
        except KeyError:
            pass
        try:
            self.mppt_car_out_amp.labels(device_sn=self.device_sn).set(message["mppt.carOutAmp"])
            message.pop("mppt.carOutAmp", None)
        except KeyError:
            pass
        try:
            self.mppt_out_amp.labels(device_sn=self.device_sn).set(message["mppt.outAmp"])
            message.pop("mppt.outAmp", None)
        except KeyError:
            pass
        try:
            self.mppt_chg_pause_flag.labels(device_sn=self.device_sn).set(message["mppt.chgPauseFlag"])
            message.pop("mppt.chgPauseFlag", None)
        except KeyError:
            pass
        try:
            self.mppt_dcdc12v_watts.labels(device_sn=self.device_sn).set(message["mppt.dcdc12vWatts"])
            message.pop("mppt.dcdc12vWatts", None)
        except KeyError:
            pass
        try:
            self.mppt_ac_standby_mins.labels(device_sn=self.device_sn).set(message["mppt.acStandbyMins"])
            message.pop("mppt.acStandbyMins", None)
        except KeyError:
            pass
        try:
            self.mppt_pow_standby_min.labels(device_sn=self.device_sn).set(message["mppt.powStandbyMin"])
            message.pop("mppt.powStandbyMin", None)
        except KeyError:
            pass
        try:
            self.mppt_in_watts.labels(device_sn=self.device_sn).set(message["mppt.inWatts"])
            message.pop("mppt.inWatts", None)
        except KeyError:
            pass
        try:
            self.mppt_dcdc12v_vol.labels(device_sn=self.device_sn).set(message["mppt.dcdc12vVol"])
            message.pop("mppt.dcdc12vVol", None)
        except KeyError:
            pass
        try:
            self.mppt_in_amp.labels(device_sn=self.device_sn).set(message["mppt.inAmp"])
            message.pop("mppt.inAmp", None)
        except KeyError:
            pass
        try:
            self.mppt_scr_standby_min.labels(device_sn=self.device_sn).set(message["mppt.scrStandbyMin"])
            message.pop("mppt.scrStandbyMin", None)
        except KeyError:
            pass
        try:
            self.mppt_in_vol.labels(device_sn=self.device_sn).set(message["mppt.inVol"])
            message.pop("mppt.inVol", None)
        except KeyError:
            pass
        try:
            self.mppt_car_out_watts.labels(device_sn=self.device_sn).set(message["mppt.carOutWatts"])
            message.pop("mppt.carOutWatts", None)
        except KeyError:
            pass
        try:
            self.mppt_mppt_temp.labels(device_sn=self.device_sn).set(message["mppt.mpptTemp"])
            message.pop("mppt.mpptTemp", None)
        except KeyError:
            pass
        try:
            self.mppt_out_vol.labels(device_sn=self.device_sn).set(message["mppt.outVol"])
            message.pop("mppt.outVol", None)
        except KeyError:
            pass
        try:
            self.mppt_cfg_ac_enabled.labels(device_sn=self.device_sn).set(message["mppt.cfgAcEnabled"])
            message.pop("mppt.cfgAcEnabled", None)
        except KeyError:
            pass
        try:
            self.mppt_chg_type.labels(device_sn=self.device_sn).set(message["mppt.chgType"])
            message.pop("mppt.chgType", None)
        except KeyError:
            pass
        try:
            self.mppt_dcdc12v_amp.labels(device_sn=self.device_sn).set(message["mppt.dcdc12vAmp"])
            message.pop("mppt.dcdc12vAmp", None)
        except KeyError:
            pass
        try:
            self.mppt_beep_state.labels(device_sn=self.device_sn).set(message["mppt.beepState"])
            message.pop("mppt.beepState", None)
        except KeyError:
            pass
        try:
            self.mppt_cfg_ac_out_vol.labels(device_sn=self.device_sn).set(message["mppt.cfgAcOutVol"])
            message.pop("mppt.cfgAcOutVol", None)
        except KeyError:
            pass
        try:
            self.mppt_cfg_chg_type.labels(device_sn=self.device_sn).set(message["mppt.cfgChgType"])
            message.pop("mppt.cfgChgType", None)
        except KeyError:
            pass
        try:
            self.mppt_dc24v_temp.labels(device_sn=self.device_sn).set(message["mppt.dc24vTemp"])
            message.pop("mppt.dc24vTemp", None)
        except KeyError:
            pass
        try:
            self.mppt_car_standby_min.labels(device_sn=self.device_sn).set(message["mppt.carStandbyMin"])
            message.pop("mppt.carStandbyMin", None)
        except KeyError:
            pass
        try:
            self.mppt_dc_chg_current.labels(device_sn=self.device_sn).set(message["mppt.dcChgCurrent"])
            message.pop("mppt.dcChgCurrent", None)
        except KeyError:
            pass
        try:
            self.mppt_chg_state.labels(device_sn=self.device_sn).set(message["mppt.chgState"])
            message.pop("mppt.chgState", None)
        except KeyError:
            pass
        try:
            self.mppt_cfg_chg_watts.labels(device_sn=self.device_sn).set(message["mppt.cfgChgWatts"])
            message.pop("mppt.cfgChgWatts", None)
        except KeyError:
            pass
        try:
            self.mppt_cfg_ac_out_freq.labels(device_sn=self.device_sn).set(message["mppt.cfgAcOutFreq"])
            message.pop("mppt.cfgAcOutFreq", None)
        except KeyError:
            pass
        try:
            self.pd_input_watts.labels(device_sn=self.device_sn).set(message["pd.inputWatts"])
            message.pop("pd.inputWatts", None)
        except KeyError:
            pass
        try:
            self.pd_typec1_temp.labels(device_sn=self.device_sn).set(message["pd.typec1Temp"])
            message.pop("pd.typec1Temp", None)
        except KeyError:
            pass
        try:
            self.pd_watts_in_sum.labels(device_sn=self.device_sn).set(message["pd.wattsInSum"])
            message.pop("pd.wattsInSum", None)
        except KeyError:
            pass
        try:
            self.pd_dc_in_used_time.labels(device_sn=self.device_sn).set(message["pd.dcInUsedTime"])
            message.pop("pd.dcInUsedTime", None)
        except KeyError:
            pass
        try:
            self.pd_wifi_ver.labels(device_sn=self.device_sn).set(message["pd.wifiVer"])
            message.pop("pd.wifiVer", None)
        except KeyError:
            pass
        try:
            self.pd_model.labels(device_sn=self.device_sn).set(message["pd.model"])
            message.pop("pd.model", None)
        except KeyError:
            pass
        try:
            self.pd_wifi_auto_rcvy.labels(device_sn=self.device_sn).set(message["pd.wifiAutoRcvy"])
            message.pop("pd.wifiAutoRcvy", None)
        except KeyError:
            pass
        try:
            self.pd_beep_mode.labels(device_sn=self.device_sn).set(message["pd.beepMode"])
            message.pop("pd.beepMode", None)
        except KeyError:
            pass
        try:
            self.pd_remain_time.labels(device_sn=self.device_sn).set(message["pd.remainTime"])
            message.pop("pd.remainTime", None)
        except KeyError:
            pass
        try:
            self.pd_typec2_watts.labels(device_sn=self.device_sn).set(message["pd.typec2Watts"])
            message.pop("pd.typec2Watts", None)
        except KeyError:
            pass
        try:
            self.pd_ext4p8_port.labels(device_sn=self.device_sn).set(message["pd.ext4p8Port"])
            message.pop("pd.ext4p8Port", None)
        except KeyError:
            pass
        try:
            self.pd_charger_type.labels(device_sn=self.device_sn).set(message["pd.chargerType"])
            message.pop("pd.chargerType", None)
        except KeyError:
            pass
        try:
            self.pd_chg_sun_power.labels(device_sn=self.device_sn).set(message["pd.chgSunPower"])
            message.pop("pd.chgSunPower", None)
        except KeyError:
            pass
        try:
            self.pd_pv_chg_prio_set.labels(device_sn=self.device_sn).set(message["pd.pvChgPrioSet"])
            message.pop("pd.pvChgPrioSet", None)
        except KeyError:
            pass
        try:
            self.pd_car_temp.labels(device_sn=self.device_sn).set(message["pd.carTemp"])
            message.pop("pd.carTemp", None)
        except KeyError:
            pass
        try:
            self.pd_usb1_watts.labels(device_sn=self.device_sn).set(message["pd.usb1Watts"])
            message.pop("pd.usb1Watts", None)
        except KeyError:
            pass
        try:
            self.pd_in_watts.labels(device_sn=self.device_sn).set(message["pd.inWatts"])
            message.pop("pd.inWatts", None)
        except KeyError:
            pass
        try:
            self.pd_dsg_power_a_c.labels(device_sn=self.device_sn).set(message["pd.dsgPowerAC"])
            message.pop("pd.dsgPowerAC", None)
        except KeyError:
            pass
        try:
            self.pd_qc_usb2_watts.labels(device_sn=self.device_sn).set(message["pd.qcUsb2Watts"])
            message.pop("pd.qcUsb2Watts", None)
        except KeyError:
            pass
        try:
            self.pd_wire_watts.labels(device_sn=self.device_sn).set(message["pd.wireWatts"])
            message.pop("pd.wireWatts", None)
        except KeyError:
            pass
        try:
            self.pd_chg_power_a_c.labels(device_sn=self.device_sn).set(message["pd.chgPowerAC"])
            message.pop("pd.chgPowerAC", None)
        except KeyError:
            pass
        try:
            self.pd_lcd_off_sec.labels(device_sn=self.device_sn).set(message["pd.lcdOffSec"])
            message.pop("pd.lcdOffSec", None)
        except KeyError:
            pass
        try:
            self.pd_ext_rj45_port.labels(device_sn=self.device_sn).set(message["pd.extRj45Port"])
            message.pop("pd.extRj45Port", None)
        except KeyError:
            pass
        try:
            self.pd_sys_ver.labels(device_sn=self.device_sn).set(message["pd.sysVer"])
            message.pop("pd.sysVer", None)
        except KeyError:
            pass
        try:
            self.pd_typec2_temp.labels(device_sn=self.device_sn).set(message["pd.typec2Temp"])
            message.pop("pd.typec2Temp", None)
        except KeyError:
            pass
        try:
            self.pd_car_used_time.labels(device_sn=self.device_sn).set(message["pd.carUsedTime"])
            message.pop("pd.carUsedTime", None)
        except KeyError:
            pass
        try:
            self.pd_typec1_watts.labels(device_sn=self.device_sn).set(message["pd.typec1Watts"])
            message.pop("pd.typec1Watts", None)
        except KeyError:
            pass
        try:
            self.pd_chg_dsg_state.labels(device_sn=self.device_sn).set(message["pd.chgDsgState"])
            message.pop("pd.chgDsgState", None)
        except KeyError:
            pass
        try:
            self.pd_out_watts.labels(device_sn=self.device_sn).set(message["pd.outWatts"])
            message.pop("pd.outWatts", None)
        except KeyError:
            pass
        try:
            self.pd_soc.labels(device_sn=self.device_sn).set(message["pd.soc"])
            message.pop("pd.soc", None)
        except KeyError:
            pass
        try:
            self.pd_qc_usb1_watts.labels(device_sn=self.device_sn).set(message["pd.qcUsb1Watts"])
            message.pop("pd.qcUsb1Watts", None)
        except KeyError:
            pass
        try:
            self.pd_ext3p8_port.labels(device_sn=self.device_sn).set(message["pd.ext3p8Port"])
            message.pop("pd.ext3p8Port", None)
        except KeyError:
            pass
        try:
            self.pd_chg_power_d_c.labels(device_sn=self.device_sn).set(message["pd.chgPowerDC"])
            message.pop("pd.chgPowerDC", None)
        except KeyError:
            pass
        try:
            self.pd_dsg_power_d_c.labels(device_sn=self.device_sn).set(message["pd.dsgPowerDC"])
            message.pop("pd.dsgPowerDC", None)
        except KeyError:
            pass
        try:
            self.pd_ac_enabled.labels(device_sn=self.device_sn).set(message["pd.acEnabled"])
            message.pop("pd.acEnabled", None)
        except KeyError:
            pass
        try:
            self.pd_standby_min.labels(device_sn=self.device_sn).set(message["pd.standbyMin"])
            message.pop("pd.standbyMin", None)
        except KeyError:
            pass
        try:
            self.pd_typec_used_time.labels(device_sn=self.device_sn).set(message["pd.typecUsedTime"])
            message.pop("pd.typecUsedTime", None)
        except KeyError:
            pass
        try:
            self.pd_bright_level.labels(device_sn=self.device_sn).set(message["pd.brightLevel"])
            message.pop("pd.brightLevel", None)
        except KeyError:
            pass
        try:
            self.pd_usbqc_used_time.labels(device_sn=self.device_sn).set(message["pd.usbqcUsedTime"])
            message.pop("pd.usbqcUsedTime", None)
        except KeyError:
            pass
        try:
            self.pd_ac_auto_on_cfg.labels(device_sn=self.device_sn).set(message["pd.acAutoOnCfg"])
            message.pop("pd.acAutoOnCfg", None)
        except KeyError:
            pass
        try:
            self.pd_dc_out_state.labels(device_sn=self.device_sn).set(message["pd.dcOutState"])
            message.pop("pd.dcOutState", None)
        except KeyError:
            pass
        try:
            self.pd_watts_out_sum.labels(device_sn=self.device_sn).set(message["pd.wattsOutSum"])
            message.pop("pd.wattsOutSum", None)
        except KeyError:
            pass
        try:
            self.pd_usb_used_time.labels(device_sn=self.device_sn).set(message["pd.usbUsedTime"])
            message.pop("pd.usbUsedTime", None)
        except KeyError:
            pass
        try:
            self.pd_mppt_used_time.labels(device_sn=self.device_sn).set(message["pd.mpptUsedTime"])
            message.pop("pd.mpptUsedTime", None)
        except KeyError:
            pass
        try:
            self.pd_wifi_rssi.labels(device_sn=self.device_sn).set(message["pd.wifiRssi"])
            message.pop("pd.wifiRssi", None)
        except KeyError:
            pass
        try:
            self.pd_output_watts.labels(device_sn=self.device_sn).set(message["pd.outputWatts"])
            message.pop("pd.outputWatts", None)
        except KeyError:
            pass
        try:
            self.pd_err_code.labels(device_sn=self.device_sn).set(message["pd.errCode"])
            message.pop("pd.errCode", None)
        except KeyError:
            pass
        try:
            self.pd_car_watts.labels(device_sn=self.device_sn).set(message["pd.carWatts"])
            message.pop("pd.carWatts", None)
        except KeyError:
            pass
        try:
            self.pd_usb2_watts.labels(device_sn=self.device_sn).set(message["pd.usb2Watts"])
            message.pop("pd.usb2Watts", None)
        except KeyError:
            pass
        try:
            self.pd_car_state.labels(device_sn=self.device_sn).set(message["pd.carState"])
            message.pop("pd.carState", None)
        except KeyError:
            pass
        try:
            self.pd_inv_used_time.labels(device_sn=self.device_sn).set(message["pd.invUsedTime"])
            message.pop("pd.invUsedTime", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_dsg_cmd.labels(device_sn=self.device_sn).set(message["bms_emsStatus.dsgCmd"])
            message.pop("bms_emsStatus.dsgCmd", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_chg_vol.labels(device_sn=self.device_sn).set(message["bms_emsStatus.chgVol"])
            message.pop("bms_emsStatus.chgVol", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_chg_remain_time.labels(device_sn=self.device_sn).set(message["bms_emsStatus.chgRemainTime"])
            message.pop("bms_emsStatus.chgRemainTime", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_f32_lcd_show_soc.labels(device_sn=self.device_sn).set(message["bms_emsStatus.f32LcdShowSoc"])
            message.pop("bms_emsStatus.f32LcdShowSoc", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_max_charge_soc.labels(device_sn=self.device_sn).set(message["bms_emsStatus.maxChargeSoc"])
            message.pop("bms_emsStatus.maxChargeSoc", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_para_vol_max.labels(device_sn=self.device_sn).set(message["bms_emsStatus.paraVolMax"])
            message.pop("bms_emsStatus.paraVolMax", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_lcd_show_soc.labels(device_sn=self.device_sn).set(message["bms_emsStatus.lcdShowSoc"])
            message.pop("bms_emsStatus.lcdShowSoc", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_bms_model.labels(device_sn=self.device_sn).set(message["bms_emsStatus.bmsModel"])
            message.pop("bms_emsStatus.bmsModel", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_chg_amp.labels(device_sn=self.device_sn).set(message["bms_emsStatus.chgAmp"])
            message.pop("bms_emsStatus.chgAmp", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_chg_state.labels(device_sn=self.device_sn).set(message["bms_emsStatus.chgState"])
            message.pop("bms_emsStatus.chgState", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_open_ups_flag.labels(device_sn=self.device_sn).set(message["bms_emsStatus.openUpsFlag"])
            message.pop("bms_emsStatus.openUpsFlag", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_open_bms_idx.labels(device_sn=self.device_sn).set(message["bms_emsStatus.openBmsIdx"])
            message.pop("bms_emsStatus.openBmsIdx", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_min_dsg_soc.labels(device_sn=self.device_sn).set(message["bms_emsStatus.minDsgSoc"])
            message.pop("bms_emsStatus.minDsgSoc", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_para_vol_min.labels(device_sn=self.device_sn).set(message["bms_emsStatus.paraVolMin"])
            message.pop("bms_emsStatus.paraVolMin", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_min_open_oil_eb.labels(device_sn=self.device_sn).set(message["bms_emsStatus.minOpenOilEb"])
            message.pop("bms_emsStatus.minOpenOilEb", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_chg_cmd.labels(device_sn=self.device_sn).set(message["bms_emsStatus.chgCmd"])
            message.pop("bms_emsStatus.chgCmd", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_max_avail_num.labels(device_sn=self.device_sn).set(message["bms_emsStatus.maxAvailNum"])
            message.pop("bms_emsStatus.maxAvailNum", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_max_close_oil_eb.labels(device_sn=self.device_sn).set(message["bms_emsStatus.maxCloseOilEb"])
            message.pop("bms_emsStatus.maxCloseOilEb", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_ems_is_normal_flag.labels(device_sn=self.device_sn).set(message["bms_emsStatus.emsIsNormalFlag"])
            message.pop("bms_emsStatus.emsIsNormalFlag", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_bms_war_state.labels(device_sn=self.device_sn).set(message["bms_emsStatus.bmsWarState"])
            message.pop("bms_emsStatus.bmsWarState", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_dsg_remain_time.labels(device_sn=self.device_sn).set(message["bms_emsStatus.dsgRemainTime"])
            message.pop("bms_emsStatus.dsgRemainTime", None)
        except KeyError:
            pass
        try:
            self.bms_ems_status_fan_level.labels(device_sn=self.device_sn).set(message["bms_emsStatus.fanLevel"])
            message.pop("bms_emsStatus.fanLevel", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_sys_ver.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.sysVer"])
            message.pop("bms_bmsStatus.sysVer", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_min_cell_temp.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.minCellTemp"])
            message.pop("bms_bmsStatus.minCellTemp", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_design_cap.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.designCap"])
            message.pop("bms_bmsStatus.designCap", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_temp.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.temp"])
            message.pop("bms_bmsStatus.temp", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_min_cell_vol.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.minCellVol"])
            message.pop("bms_bmsStatus.minCellVol", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_cycles.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.cycles"])
            message.pop("bms_bmsStatus.cycles", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_f32_show_soc.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.f32ShowSoc"])
            message.pop("bms_bmsStatus.f32ShowSoc", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_output_watts.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.outputWatts"])
            message.pop("bms_bmsStatus.outputWatts", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_max_cell_vol.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.maxCellVol"])
            message.pop("bms_bmsStatus.maxCellVol", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_type.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.type"])
            message.pop("bms_bmsStatus.type", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_soh.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.soh"])
            message.pop("bms_bmsStatus.soh", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_max_cell_temp.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.maxCellTemp"])
            message.pop("bms_bmsStatus.maxCellTemp", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_remain_cap.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.remainCap"])
            message.pop("bms_bmsStatus.remainCap", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_cell_id.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.cellId"])
            message.pop("bms_bmsStatus.cellId", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_min_mos_temp.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.minMosTemp"])
            message.pop("bms_bmsStatus.minMosTemp", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_vol.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.vol"])
            message.pop("bms_bmsStatus.vol", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_remain_time.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.remainTime"])
            message.pop("bms_bmsStatus.remainTime", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_full_cap.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.fullCap"])
            message.pop("bms_bmsStatus.fullCap", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_bq_sys_stat_reg.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.bqSysStatReg"])
            message.pop("bms_bmsStatus.bqSysStatReg", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_open_bms_idx.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.openBmsIdx"])
            message.pop("bms_bmsStatus.openBmsIdx", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_amp.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.amp"])
            message.pop("bms_bmsStatus.amp", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_num.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.num"])
            message.pop("bms_bmsStatus.num", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_bms_fault.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.bmsFault"])
            message.pop("bms_bmsStatus.bmsFault", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_soc.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.soc"])
            message.pop("bms_bmsStatus.soc", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_err_code.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.errCode"])
            message.pop("bms_bmsStatus.errCode", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_input_watts.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.inputWatts"])
            message.pop("bms_bmsStatus.inputWatts", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_tag_chg_amp.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.tagChgAmp"])
            message.pop("bms_bmsStatus.tagChgAmp", None)
        except KeyError:
            pass
        try:
            self.bms_bms_status_max_mos_temp.labels(device_sn=self.device_sn).set(message["bms_bmsStatus.maxMosTemp"])
            message.pop("bms_bmsStatus.maxMosTemp", None)
        except KeyError:
            pass
        try:
            self.inv_dc_in_vol.labels(device_sn=self.device_sn).set(message["inv.dcInVol"])
            message.pop("inv.dcInVol", None)
        except KeyError:
            pass
        try:
            self.inv_cfg_ac_work_mode.labels(device_sn=self.device_sn).set(message["inv.cfgAcWorkMode"])
            message.pop("inv.cfgAcWorkMode", None)
        except KeyError:
            pass
        try:
            self.inv_slow_chg_watts.labels(device_sn=self.device_sn).set(message["inv.SlowChgWatts"])
            message.pop("inv.SlowChgWatts", None)
        except KeyError:
            pass
        try:
            self.inv_dc_in_amp.labels(device_sn=self.device_sn).set(message["inv.dcInAmp"])
            message.pop("inv.dcInAmp", None)
        except KeyError:
            pass
        try:
            self.inv_cfg_ac_out_freq.labels(device_sn=self.device_sn).set(message["inv.cfgAcOutFreq"])
            message.pop("inv.cfgAcOutFreq", None)
        except KeyError:
            pass
        try:
            self.inv_output_watts.labels(device_sn=self.device_sn).set(message["inv.outputWatts"])
            message.pop("inv.outputWatts", None)
        except KeyError:
            pass
        try:
            self.inv_err_code.labels(device_sn=self.device_sn).set(message["inv.errCode"])
            message.pop("inv.errCode", None)
        except KeyError:
            pass
        try:
            self.inv_dc_in_temp.labels(device_sn=self.device_sn).set(message["inv.dcInTemp"])
            message.pop("inv.dcInTemp", None)
        except KeyError:
            pass
        try:
            self.inv_inv_out_freq.labels(device_sn=self.device_sn).set(message["inv.invOutFreq"])
            message.pop("inv.invOutFreq", None)
        except KeyError:
            pass
        try:
            self.inv_charger_type.labels(device_sn=self.device_sn).set(message["inv.chargerType"])
            message.pop("inv.chargerType", None)
        except KeyError:
            pass
        try:
            self.inv_ac_in_amp.labels(device_sn=self.device_sn).set(message["inv.acInAmp"])
            message.pop("inv.acInAmp", None)
        except KeyError:
            pass
        try:
            self.inv_fan_state.labels(device_sn=self.device_sn).set(message["inv.fanState"])
            message.pop("inv.fanState", None)
        except KeyError:
            pass
        try:
            self.inv_cfg_ac_xboost.labels(device_sn=self.device_sn).set(message["inv.cfgAcXboost"])
            message.pop("inv.cfgAcXboost", None)
        except KeyError:
            pass
        try:
            self.inv_cfg_ac_enabled.labels(device_sn=self.device_sn).set(message["inv.cfgAcEnabled"])
            message.pop("inv.cfgAcEnabled", None)
        except KeyError:
            pass
        try:
            self.inv_out_temp.labels(device_sn=self.device_sn).set(message["inv.outTemp"])
            message.pop("inv.outTemp", None)
        except KeyError:
            pass
        try:
            self.inv_inv_type.labels(device_sn=self.device_sn).set(message["inv.invType"])
            message.pop("inv.invType", None)
        except KeyError:
            pass
        try:
            self.inv_cfg_ac_out_vol.labels(device_sn=self.device_sn).set(message["inv.cfgAcOutVol"])
            message.pop("inv.cfgAcOutVol", None)
        except KeyError:
            pass
        try:
            self.inv_ac_dip_switch.labels(device_sn=self.device_sn).set(message["inv.acDipSwitch"])
            message.pop("inv.acDipSwitch", None)
        except KeyError:
            pass
        try:
            self.inv_ac_in_vol.labels(device_sn=self.device_sn).set(message["inv.acInVol"])
            if int(message["inv.acInVol"]) == 0:
                self.inv_ac_in_amp.labels(device_sn=self.device_sn).set(0)
            message.pop("inv.acInVol", None)
        except KeyError:
            pass
        try:
            self.inv_inv_out_vol.labels(device_sn=self.device_sn).set(message["inv.invOutVol"])
            message.pop("inv.invOutVol", None)
        except KeyError:
            pass
        try:
            self.inv_fast_chg_watts.labels(device_sn=self.device_sn).set(message["inv.FastChgWatts"])
            message.pop("inv.FastChgWatts", None)
        except KeyError:
            pass
        try:
            self.inv_input_watts.labels(device_sn=self.device_sn).set(message["inv.inputWatts"])
            message.pop("inv.inputWatts", None)
        except KeyError:
            pass
        try:
            self.inv_standby_mins.labels(device_sn=self.device_sn).set(message["inv.standbyMins"])
            message.pop("inv.standbyMins", None)
        except KeyError:
            pass
        try:
            self.inv_chg_pause_flag.labels(device_sn=self.device_sn).set(message["inv.chgPauseFlag"])
            message.pop("inv.chgPauseFlag", None)
        except KeyError:
            pass
        try:
            self.inv_ac_in_freq.labels(device_sn=self.device_sn).set(message["inv.acInFreq"])
            message.pop("inv.acInFreq", None)
        except KeyError:
            pass
        try:
            self.inv_discharge_type.labels(device_sn=self.device_sn).set(message["inv.dischargeType"])
            message.pop("inv.dischargeType", None)
        except KeyError:
            pass
        try:
            self.inv_inv_out_amp.labels(device_sn=self.device_sn).set(message["inv.invOutAmp"])
            message.pop("inv.invOutAmp", None)
        except KeyError:
            pass
        try:
            self.inv_sys_ver.labels(device_sn=self.device_sn).set(message["inv.sysVer"])
            message.pop("inv.sysVer", None)
        except KeyError:
            pass

        if len(message) > 0:
            log.warning(f"Some values was not processed: {message}")


class EcoflowMQTT():

    def __init__(self, message_queue, device_sn, username, password, broker_addr, broker_port):
        self.message_queue = message_queue
        self.broker_addr = broker_addr
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.topic = f"/app/device/property/{device_sn}"
        self.client = mqtt.Client(f'python-mqtt-{random.randint(0, 100)}')

    def connect(self):
        self.client.username_pw_set(self.username, self.password)
        self.client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        self.client.tls_insecure_set(False)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.connect(self.broker_addr, self.broker_port)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info(f"Connected to MQTT Broker {self.broker_addr}:{self.broker_port}")
            self.client.subscribe(self.topic)
        elif rc == -1:
            log.error("Connection timed out")
        elif rc == 1:
            log.error("Connection refused - incorrect protocol version")
        elif rc == 2:
            log.error("Connection refused - invalid client identifier")
        elif rc == 3:
            log.error("Connection refused - server unavailable")
        elif rc == 4:
            log.error("Connection refused - bad username or password")
        elif rc == 5:
            log.error("Connection refused - not authorised")
        else:
            log.error(
                f"Another error {rc} occured, please check the mqtt-paho documentation")
        return client

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning(f"Unexpected MQTT disconnection: {rc}. Will auto-reconnect")

    def on_message(self, client, userdata, message):
        self.message_queue.put(message.payload.decode("utf-8"))


def main():
    log.basicConfig(stream=sys.stdout, level=log.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    device_sn = str(os.getenv("DEVICE_SN"))
    username = str(os.getenv("MQTT_USERNAME"))
    password = str(os.getenv("MQTT_PASSWORD"))
    broker_addr = str(os.getenv("MQTT_BROKER", "mqtt.ecoflow.com"))
    broker_port = int(os.getenv("MQTT_PORT", "8883"))
    exporter_port = int(os.getenv("EXPORTER_PORT", "9090"))

    message_queue = Queue()

    ecoflow_mqtt = EcoflowMQTT(message_queue, device_sn, username, password, broker_addr, broker_port)
    ecoflow_mqtt.connect()

    metrics = EcoflowMetrics(message_queue, device_sn)
    start_http_server(exporter_port)
    metrics.run_metrics_loop()


if __name__ == '__main__':
    main()
