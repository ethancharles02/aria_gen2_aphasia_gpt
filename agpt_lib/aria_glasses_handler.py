#!/usr/bin/env python3

# WARNING: Requires Aria Gen 2 Client-SDK to be installed (see
# https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/start)

import threading

import aria.stream_receiver as receiver
import aria.sdk_gen2 as sdk_gen2
from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
    ImageData,
    ImageDataRecord,
)

class AriaGlassesHandler:
    def __init__(self):
        self.stream_receiver = None
        self.server_config = None
        self.streaming_config = None
        self.device_client = sdk_gen2.DeviceClient()
        self.device: sdk_gen2.Device = None
        self.device_ip = None
        self.connect_over_wifi = None
        self._temperature_stop_event = threading.Event()
        self._device_throttling = False

    def setup_streaming_receiver(self, record_to_vrs: str = "", address: str = "0.0.0.0", port: int = 6768):
        self.server_config = sdk_gen2.HttpServerConfig()
        self.server_config.address = address
        self.server_config.port = port

        # Setup the receiver
        self.stream_receiver = receiver.StreamReceiver()
        self.stream_receiver.set_server_config(self.server_config)
        if record_to_vrs != "":
            self.stream_receiver.record_to_vrs(record_to_vrs)

        self.stream_receiver.set_rgb_queue_size(2)
        self.stream_receiver.set_et_queue_size(4)

        self.stream_receiver.register_rgb_callback(self._image_callback)
        self.stream_receiver.register_audio_callback(self._audio_callback)
        # self.stream_receiver.register_eye_gaze_callback(eyegaze_callback)

    def setup_device(
            self,
            device_ip: str = "",
            connect_over_wifi: bool = False,
            stream_config_name: str = "",
            stream_batch_period_ms: int = 200,
            streaming_ip: str = "",
            stream_over_wifi: bool = False):
        # Set up the device client config to specify the device to be connected to e.g. device serial
        # number. If nothing is specified, the first device in the list of connected devices will be
        # connected to
        device_config = sdk_gen2.DeviceClientConfig()
        self.device_client.set_client_config(device_config)

        # TODO a convenience feature might be to remember the device ip but that could get in the
        # way of the originaly device ip if provided. Maybe only if connect over wifi is initially
        # disabled?
        self.device_ip = device_ip
        if not stream_over_wifi and connect_over_wifi:
            print("WARNING: Can't stream data over USB when connected to Wi-Fi, connecting over USB")
            self.connect_over_wifi = False
        else:
            self.connect_over_wifi = connect_over_wifi

        if not self._attempt_device_connection():
            return

        if not self.connect_over_wifi and stream_over_wifi:
            # If connected over USB at first, the IP can be identified and used later
            status = self.device.status()
            ip = status.wifi_ip_address
            if ip:
                self.device_ip = ip
                self.connect_over_wifi = True
                old_device = self.device
                # Connect over wifi
                if self._attempt_device_connection():
                    print(f"Successfully switched device connection over Wi-Fi using IP: {self.device_ip}")
                else:
                    self.device = old_device
                    self.connect_over_wifi = False
                    stream_over_wifi = False
                    print("Failed to reconnect device over Wi-Fi, switching to streaming over USB connection")

        # Set recording config with profile name
        self.streaming_config = sdk_gen2.HttpStreamingConfig()

        if stream_config_name.endswith(".json"):
            self.streaming_config.profile_json = stream_config_name
        else:
            self.streaming_config.profile_name = stream_config_name

        if stream_over_wifi:
            print("Streaming data over Wi-Fi")
            self.streaming_config.streaming_interface = sdk_gen2.StreamingInterface.WIFI_STA
            self.streaming_config.batch_period_ms = stream_batch_period_ms
            self.streaming_config.advanced_config.endpoint.url = streaming_ip
            self.streaming_config.advanced_config.endpoint.verify_server_certificates = False
        else:
            print("Streaming data over USB")
            self.streaming_config.streaming_interface = sdk_gen2.StreamingInterface.USB_NCM

        self.device.set_streaming_config(self.streaming_config)

    def start_streaming_receiver(self):
        if self.stream_receiver is None:
            print("Streaming receiver not set up. Please call setup_streaming_receiver first")
            return
        self.stream_receiver.start_server()

    def start_device_streaming(self):
        if self.device is None:
            print("Device not set up. Please call setup_device first")
            return
        self.device.start_streaming()

    def _get_temp_str(self, status) -> str:
        temp_str = f"{status.skin_temp_celsius:.1f}°C"
        if status.thermal_mitigation_triggered:
            self._device_throttling = True
            temp_str += " (throttling)"
        else:
            self._device_throttling = False
        return temp_str

    def _temperature_monitor_loop(self):
        temp_str = None
        while not self._temperature_stop_event.is_set():
            if self.device is not None:
                # Attempts to reconnect to the device
                if not self.device_client.is_connected(self.device):
                    while not self.device_client.is_connected(self.device):
                        if self._attempt_device_connection():
                            print(f"[Temperature Monitor] Successfully reconnected to the device")
                        self._temperature_stop_event.wait(10.0)
                        if self._temperature_stop_event.is_set():
                            break
                try:
                    status = self.device.status()
                    if temp_str is None:
                        temp_str = self._get_temp_str(status)
                        print(f"Initial Temperature: {temp_str}")
                    else:
                        temp_str = self._get_temp_str(status)
                    if self.show_temperature_readings:
                        print(f"Temperature: {temp_str}", end="\r")
                    elif self._device_throttling:
                        print(f"WARNING: Device is throttling with temperature of {temp_str}")
                except Exception as exc:
                    print(f"Temperature read error: {exc}\n")
            self._temperature_stop_event.wait(1.0)
        if temp_str is not None:
            print(f"Final temperature: {temp_str}")

    def start_temperature_monitor(self, show_temperature_readings: bool = False):
        self.show_temperature_readings = show_temperature_readings
        _temp_thread = threading.Thread(target=self._temperature_monitor_loop, daemon=True)
        _temp_thread.start()

    def stop_temperature_monitor(self):
        self._temperature_stop_event.set()

    def stop_device_streaming(self):
        if self.device is not None:
            if not self.device_client.is_connected(self.device):
                print("Device was disconnected, attempting to reconnect")
                self._attempt_device_connection()

            self.device.stop_streaming()

    def stop_streaming_receiver(self):
        if self.stream_receiver is not None:
            self.stream_receiver.stop_server()

    def _attempt_device_connection(self, is_quiet: bool = False) -> bool:
        try:
            if self.connect_over_wifi:
                self.device = self.device_client.connect(sdk_gen2.DeviceTarget(ip=self.device_ip))
            else:
                self.device = self.device_client.connect()
            return True
        except Exception as e:
            if not is_quiet:
                print(f"Failed to connect to device with exception: {e}")
            return False

    def _image_callback(self, image_data: ImageData, image_record: ImageDataRecord):
        raise NotImplementedError

    def _audio_callback(self, audio_data: AudioData, audio_record: AudioDataRecord, num_channels: int):
        raise NotImplementedError
