import numpy as np

from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.calibration import DeviceCalibration

def transform_audio_data(num_audio_channels: int, full_audio_data_bytes: list[int], num_output_channels: int) -> bytes:
    if num_audio_channels is None:
        print("Number of channels not set, returning empty bytes")
        return bytes()

    if num_output_channels > num_audio_channels:
        print("Can't increase number of channels past original")
        return bytes()

    raw_array = np.array(full_audio_data_bytes, dtype=np.int32)

    spatial_data = raw_array.reshape(-1, num_audio_channels)

    d_channels = num_audio_channels // num_output_channels
    leftover = num_audio_channels % num_output_channels

    leftover_channel = [] if leftover == 0 else [np.mean(spatial_data[:, num_audio_channels-leftover:num_audio_channels], axis=1)]
    channels = [np.mean(spatial_data[:, i * d_channels:(i + 1) * d_channels], axis=1) for i in range(num_output_channels)] + leftover_channel

    # Divides by 255 since whisper expects 16 bit but the aria stream appears to be 24 bit
    channels = tuple(map(lambda channel: (channel / 255).astype(np.int16), channels))

    output_bytes = np.column_stack(channels)

    return output_bytes.tobytes()

def project_eyegaze(eyegaze_data: EyeGaze, device_calibration: DeviceCalibration) -> (tuple[float, float] | None):
    if device_calibration is None:
        return None

    # Code adapted from: projectaria_tools/tools/aria_rerun_viewer/aria_data_plotter.py
    spatial_gaze_point_in_cpf = eyegaze_data.spatial_gaze_point_in_cpf
    T_device_cpf = device_calibration.get_transform_device_cpf()
    spatial_gaze_point_in_device = T_device_cpf @ spatial_gaze_point_in_cpf

    rgb_calib = device_calibration.get_camera_calib("camera-rgb")

    spatial_gaze_point_in_camera = (
        rgb_calib.get_transform_device_camera().inverse()
        @ spatial_gaze_point_in_device
    )

    # project the eye gaze point onto the image
    maybe_pixel = rgb_calib.project(spatial_gaze_point_in_camera)

    return maybe_pixel