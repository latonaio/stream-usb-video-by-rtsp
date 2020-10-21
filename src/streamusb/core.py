# coding: utf-8

# Copyright (c) 2019-2020 Latona. All rights reserved.

from aion.logger import lprint
from aion.microservice import main_decorator, Options

import asyncio
import json
from multiprocessing import Process
import gi
import subprocess
import threading
from time import sleep


gi.require_version('Gst', '1.0')  # noqa
gi.require_version('GstRtspServer', '1.0')  # noqa
from gi.repository import GLib, Gst, GstRtspServer  # isort:skip
import os

Gst.init(None)
# Gst.debug_set_active(True)
# Gst.debug_set_default_threshold(4)

# NOTE: DEFAULT C922N PRO STREAM WEBCAM
# NOTE: when use STREAMCAM, choose following resolutions
# 1920x1080、1280x720、960x540、848x480、640x360、320x240
DEFAULT_WIDTH = int(os.environ.get("WIDTH", 864))
DEFAULT_HEIGHT = int(os.environ.get("HEIGHT", 480))
DEFAULT_FPS = int(os.environ.get("FPS", 10))
DEFAULT_PORT = int(os.environ.get("PORT", 8554))
DEFAULT_URI = os.environ.get("URI", "/usb")

SERVICE_NAME = "stream-usb-video-by-rtsp"

def get_pipeline(width, height, fps):
    return f"""
        ( v4l2src io-mode=2 name=source !
        image/jpeg, width={width}, height={height}, framerate={fps}/1 !
        queue ! rtpjpegpay name=pay0 pt=96 )
    """

class DeviceConfigController:
    def __init__(self, config_path: str):
        self.__device_path = '/dev/video0'
        self.__config_path = config_path
        self.dc = DeviceConfig(self.config_path, self.device_path)

    @property
    def device_path(self):
        return self.__device_path
    
    @device_path.setter
    def device_path(self, device_path: str):
        self.__device_path = device_path

    @property
    def config_path(self):
        return self.__config_path

    @config_path.setter
    def config_path(self, config_path: str):
        self.__config_path = config_path
    
    def init_device_config(self):
        self.dc.device_path = self.device_path
        config = self.__load_config()
        auto_focus = config.get('auto_focus')
        focus_absolute = config.get('focus_absolute')
        if auto_focus == "on":
            self.dc.auto_focus = True
            self.dc.on_autofocus()
        elif auto_focus == "off" and focus_absolute is not None:
            self.dc.auto_focus = False
            self.dc.off_autofocus()
            self.dc.focus_absolute = focus_absolute
            self.dc.set_focus_absolute_camera()

    def fix_focus_absolute(self):
        res = self.dc.get_focus_absolute()
        self.dc.focus_absolute = res
        self.dc.auto_focus = False
        self.dc.off_autofocus()
        # self.dc.set_focus_absolute_camera()
        self.__update_config({'auto_focus': 'off', 'focus_absolute': res})
    
    def on_auto_focus(self):
        self.dc.auto_focus = True
        self.dc.on_autofocus()
        res = self.dc.get_focus_absolute()
        self.__update_config({'auto_focus': 'on', 'focus_absolute': res})

    def __create_config(self):
        conf =  {'auto_focus': 'on', 'focus_absolute': 10}
        with open(self.config_path, 'w') as f:
            f.write(conf)
  
    def __load_config(self) -> dict:
        if os.path.exists(self.config_path) == False:
            self.__create_config()
        with open(self.config_path) as f:
            conf = json.load(f)
        lprint("load config (config: {})".format(str(conf)))
        return  {'auto_focus': conf.get('auto_focus'), 'focus_absolute': conf.get('focus_absolute')}

    def __update_config(self, config: dict):
        with open(self.config_path, 'r+') as f:
            conf = json.load(f)     
            conf['auto_focus'] = config.get('auto_focus')
            conf['focus_absolute'] = config.get('focus_absolute')
            f.seek(0)
            f.write(json.dumps(conf))
            f.truncate()
        
class DeviceConfig:
    def __init__(self, config_path: str, device_path: str, auto_focus=True, focus_absolute=50):
        self.__config_path = config_path
        self.__device_path = device_path
        self.__auto_focus = auto_focus
        self.__focus_absolute = focus_absolute

    @property
    def config_path(self):
        return self.__config_path
    
    @config_path.setter
    def config_path(self, config_path):
        self.__config_path = config_path

    @property
    def device_path(self):
        return self.__device_path
    
    @device_path.setter
    def device_path(self, device_path):
        self.__device_path = device_path

    @property
    def auto_focus(self):
        return self.__auto_focus

    @auto_focus.setter
    def auto_focus(self, auto_focus: bool):
        self.__auto_focus = auto_focus

    @property
    def focus_absolute(self):
        return self.__focus_absolute

    @focus_absolute.setter
    def focus_absolute(self, focus_absolute: int):
        self.__focus_absolute = focus_absolute
    
    def get_focus_absolute(self):
        command = ['v4l2-ctl', '-d', self.device_path, '-C', 'focus_absolute']
        res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = res.stdout.decode("utf8")
        out = out[:-1]
        focus_absolute = out.replace('focus_absolute: ', '')
        lprint("current focus_absoulte: " + focus_absolute)
        return int(focus_absolute)
    
    def get_auto_focus(self):
        command = ['v4l2-ctl', '-d', self.device_path, '-C', 'auto_focus']
        res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return res.stdout

    def set_focus_absolute_camera(self):
        if self.auto_focus == False:
            self.off_autofocus()
            command = ['v4l2-ctl', '-d', self.device_path, '-c', 'focus_absolute=' + str(self.focus_absolute)]
            lprint("set absolute " + str(command))
            subprocess.run(command, stdout=subprocess.PIPE)
        else:
            lprint('auto focus mode has been already set')

    def on_autofocus(self):
        command = ['v4l2-ctl', '-d', self.device_path, '-c', 'focus_auto=1']
        subprocess.run(command, stdout=subprocess.PIPE)
    
    def off_autofocus(self):
        command = ['v4l2-ctl', '-d', self.device_path, '-c', 'focus_auto=0']
        subprocess.run(command, stdout=subprocess.PIPE)


class GstServer:
    def __init__(self, port, width, height, fps, device_path):
        port_str = str(port)
        pipe = get_pipeline(width, height, fps)
        self.pipe = None

        self.server = GstRtspServer.RTSPServer().new()
        self.server.set_service(port_str)
        self.server.connect("client-connected", self.client_connected)

        self.f = GstRtspServer.RTSPMediaFactory().new()
        self.f.set_eos_shutdown(True)
        self.f.set_launch(pipe)
        self.f.set_shared(True)
        self.f.connect("media-constructed", self.on_media_constructed)
        self.device_path = device_path

        m = self.server.get_mount_points()
        m.add_factory(DEFAULT_URI, self.f)
        self.server.attach(None)

    def start(self):
        loop = GLib.MainLoop()
        loop.run()
        self.stop()

    def client_connected(self, server, client):
        lprint(f'[RTSP] next service is connected')

    def on_media_constructed(self, factory, media):
        # get camera path
        if self.device_path is None:
            lprint("[RTSP] device is not connected")
            self.stop()
            return
        # get element state and check state
        self.pipe = media.get_element()
        appsrc = self.pipe.get_by_name('source')
        appsrc.set_property('device', self.device_path)

        self.pipe.set_state(Gst.State.PLAYING)
        ret, _, _ = self.pipe.get_state(Gst.CLOCK_TIME_NONE)
        if ret == Gst.StateChangeReturn.FAILURE:
            lprint("[RTSP] cant connect to device: " + self.device_path)
            self.stop()
        else:
            lprint(f"[RTSP] connect to device ({self.device_path})")

    def set_device_path(self, device_path):
        self.device_path = device_path

    def stop(self):
        if self.pipe is not None:
            self.pipe.send_event(Gst.Event.new_eos())


class DeviceData:
    process = None

    def __init__(self, serial, device_path, number, width, height, fps, is_docker, num):
        self.serial = serial
        port = DEFAULT_PORT + number
        self.addr = SERVICE_NAME + "-" + str(num).zfill(3) + "-srv:" + str(port) \
            if is_docker else "localhost:" + str(port)
        self.addr += DEFAULT_URI
        self.server = GstServer(port, width, height, fps, device_path)
        self.process = Process(target=self.server.start)
        self.process.start()
        lprint(f"[RTSP] ready at rtsp://{self.addr}")

    def get_serial(self):
        return self.serial

    def get_addr(self):
        return self.addr

    def set_device_path(self, device_path):
        self.server.set_device_path(device_path)

    def stop(self):
        self.server.stop()
        if self.process is not None:
            self.process.terminate()
            self.process.join()

class DeviceDataList:
    device_data_list = {}
    previous_device_list = []

    def start_rtsp_server(self, device_list: dict, scale: int, is_docker: bool, num: int, start_with_config: str, device_config: DeviceConfigController):
        metadata_list = []
        # start device list
        for serial, path in device_list.items():
            lprint(f"Get device data (serial: {serial}, path: {path})")
            # set device path
            if self.device_data_list.get(serial):
                self.device_data_list[serial].set_device_path(path)

            # check over scale or already set in device list
            if len(self.previous_device_list) >= scale or serial in self.previous_device_list:
                continue
            # フォーカス機能の初期化処理
            if start_with_config == "True":
                device_config.device_path = path
                device_config.init_device_config()
                lprint("start streaming with config file")

            # add new camera connection
            width = DEFAULT_WIDTH
            height = DEFAULT_HEIGHT
            fps = DEFAULT_FPS

            self.previous_device_list.append(serial)

            output_num = len(self.previous_device_list)
            device_data = DeviceData(serial, path, output_num, width, height, fps, is_docker, num)

            lprint(self.previous_device_list, output_num)

            metadata = {
                "width": width,
                "height": height,
                "framerate": fps,
                "addr": device_data.get_addr(),
            }
            metadata_list.append((metadata, output_num))
        return metadata_list

    def stop_all_device(self):
        for data in self.device_data_list:
            data.stop()


@main_decorator(SERVICE_NAME)
def main(opt: Options):
    conn = opt.get_conn()
    num = opt.get_number()

    scale = os.environ.get("SCALE")
    scale = 2 if not isinstance(scale, int) or scale <= 0 else scale
    debug = os.environ.get("DEBUG")
    device = DeviceDataList()
    start_with_config = DEFAULT_START_WITH_CONFIG if os.environ.get('START_WITH_CONFIG') is None else os.environ.get('START_WITH_CONFIG')
    config_path = '/var/lib/aion/Data/stream-usb-video-by-rtsp_' + str(num) + '/config.json'
    device_config = DeviceConfigController(config_path)
    # for debug
    if debug:
        conn.set_kanban(SERVICE_NAME, num)
        device.start_rtsp_server({"test": "/dev/video0"}, scale, opt.is_docker(), 1, False, device_config)
        while True:
            sleep(5)
    try:
        for kanban in conn.get_kanban_itr(SERVICE_NAME, num):
            key = kanban.get_connection_key()
            if key == "streaming":
                device_list = kanban.get_metadata().get("device_list")
                if not device_list:
                    continue
                metadata_list = device.start_rtsp_server(device_list, scale, opt.is_docker(), num, start_with_config, device_config)
                for metadata, num in metadata_list:
                    conn.output_kanban(
                        connection_key="camera_connected",
                        metadata={
                            "type": "start",
                            "rtsp": metadata,
                        }, 
                        process_number=num,
                    )
            elif key == "set_focus":
                auto_focus = kanban.get_metadata().get("auto_focus")
                if auto_focus == "on":
                    device_config.on_auto_focus()
                elif auto_focus == "off":
                    device_config.fix_focus_absolute()
                else:
                    lprint("invalid metadata (connection_key: {}, auto_focus: {})".format(key, auto_focus))
            
    finally:
        device.stop_all_device()
