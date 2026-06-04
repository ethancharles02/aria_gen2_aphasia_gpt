import aria.sdk_gen2 as sdk_gen2

if __name__ == "__main__":
    # INSTRUCTIONS:
    # 1. Connect the glasses to a wi-fi network
    # 2. Forget that network so it is disconnected but don't turn off the glasses
    # 3. Run this script. The wi-fi strings should be empty but they aren't for me
    device_client = sdk_gen2.DeviceClient()

    device_config = sdk_gen2.DeviceClientConfig()
    device_client.set_client_config(device_config)

    device = device_client.connect()
    status = device.status()
    print(status.wifi_ip_address)
    print(status.wifi_ssid)