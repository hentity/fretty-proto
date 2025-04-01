import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy.signal import find_peaks
import os
import sys
import sounddevice as sd
import pyaudio
from datetime import datetime

from fretty.notes import note_to_frequency, spot_to_note

# config
lowest_freq = 70
highest_freq = 2000
fluctuation_tolerance = 2.0

device_info = sd.query_devices(kind='input')
input_device_index = device_info['index']
SAMPLE_RATE = int(device_info['default_samplerate'])
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024

def estimate_fundamental(peaks, power_values):
    """Finds the approximate fundamental frequency from detected peaks using an approximate GCD method.
    
    Removes peaks that are too close together (< 68 Hz), keeping the stronger peak. 
    After estimating the fundamental frequency, checks whether all remaining peaks are integer multiples of it.
    """
    filter_threshold = 0.4
    npeaks_unfiltered = len(peaks)
    
    # Sort peaks and power values together
    sorted_indices = np.argsort(peaks)
    peaks_sorted = peaks[sorted_indices]
    power_sorted = power_values[sorted_indices]
    
    removed_peaks = []  # Store removed peaks for plotting
    removed_power = []

    # Iteratively remove peaks that are too close (< 68 Hz)
    while True:
        if len(peaks_sorted) < 2:
            break
        
        spacings = np.diff(peaks_sorted)
        min_spacing_idx = np.argmin(spacings)
        min_spacing = spacings[min_spacing_idx]

        if min_spacing >= lowest_freq:
            break
        
        # Determine which peak to remove (weaker one)
        if power_sorted[min_spacing_idx] < power_sorted[min_spacing_idx + 1]:
            remove_idx = min_spacing_idx
        else:
            remove_idx = min_spacing_idx + 1

        # Store removed peaks for visualization
        removed_peaks.append(peaks_sorted[remove_idx])
        removed_power.append(power_sorted[remove_idx])

        # Remove the peak with lower power
        peaks_sorted = np.delete(peaks_sorted, remove_idx)
        power_sorted = np.delete(power_sorted, remove_idx)

    npeaks_filtered = len(peaks_sorted)
    if npeaks_filtered == 0:
        return None, None, removed_peaks, removed_power
    filter_reduction = npeaks_filtered / npeaks_unfiltered
    if filter_reduction < filter_threshold:
        return None, None, removed_peaks, removed_power
    
    if len(peaks_sorted) == 1:
        estimated_fundamental = peaks_sorted[0]
        if lowest_freq <= estimated_fundamental <= highest_freq:
            return peaks_sorted, peaks_sorted[0], removed_peaks, removed_power
        else:
            return None, None, removed_peaks, removed_power
    
    # Compute frequency differences
    spacings = np.diff(peaks_sorted)
    min_spacing = np.min(spacings)
    multiples = spacings / min_spacing

    threshold = 0.05
    rounded_multiples = np.round(multiples)
    valid_multiples = rounded_multiples[np.abs(multiples - rounded_multiples) <= threshold]

    # Filter spacings and divide by corresponding valid multiples
    valid_indices = np.abs(multiples - rounded_multiples) <= threshold
    filtered_spacings = spacings[valid_indices]
    normalized_spacings = filtered_spacings / valid_multiples

    # Compute the average of normalized spacings
    if len(normalized_spacings) > 0:
        estimated_fundamental = np.mean(normalized_spacings)
    else:
        return None, None, removed_peaks, removed_power

    # **Final Validation: Check if all peaks are integer multiples of the fundamental**
    peak_multiples = peaks_sorted / estimated_fundamental
    rounded_peak_multiples = np.round(peak_multiples)
    valid_peak_multiples = np.abs(peak_multiples - rounded_peak_multiples) <= threshold

    if not np.all(valid_peak_multiples):
        return None, None, removed_peaks, removed_power

    if lowest_freq <= estimated_fundamental <= highest_freq:
        return peaks_sorted, estimated_fundamental, removed_peaks, removed_power
    else:    
        return None, None, removed_peaks, removed_power

# Function to classify a frequency as a fretboard position
def classify_note(frequency):
    """Finds the closest matching fretboard position for a given frequency."""
    if frequency is None:
        return None
    
    # Find the closest note
    closest_note = min(note_to_frequency, key=lambda note: abs(note_to_frequency[note] - frequency))

    # Map to the correct fretboard position(s)
    return closest_note


LOG_FILE = "audio_debug.log"

def log_message(message):
    """Logs messages to a file instead of printing to stdout."""
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")

# def record_audio(duration):
#     """Records audio from the microphone using pyaudio."""
#     p = pyaudio.PyAudio()
    
#     stream = p.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE,
#                     input=True, input_device_index=input_device_index, frames_per_buffer=CHUNK)

#     frames = []
#     for _ in range(int(SAMPLE_RATE / CHUNK * duration)):
#         data = stream.read(CHUNK, exception_on_overflow=False)
#         frames.append(data)
    
#     stream.stop_stream()
#     stream.close()
#     p.terminate()

#     # Convert raw audio bytes to NumPy array
#     audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
#     audio_data = audio_data.astype(np.float32) / 32768.0  # Normalize
    
#     return audio_data

import pyaudio
import numpy as np

def record_audio(duration):
    """Records audio from the microphone using pyaudio with error handling."""
    p = pyaudio.PyAudio()
    stream = None
    frames = []

    try:
        # Attempt to open stream
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=SAMPLE_RATE,
                        input=True,
                        input_device_index=input_device_index,
                        frames_per_buffer=CHUNK)

        # Read data in chunks
        for _ in range(int(SAMPLE_RATE / CHUNK * duration)):
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception as e:
                print(f"Error reading audio chunk: {e}")
                break

    except Exception as e:
        print(f"Error opening audio stream: {e}")
        return np.array([])  # Return empty array to indicate failure

    finally:
        # Clean up stream safely
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e:
                print(f"Error closing stream: {e}")
        p.terminate()

    if not frames:
        print("No audio frames captured.")
        return np.array([])

    # Convert to NumPy array
    try:
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        audio_data = audio_data.astype(np.float32) / 32768.0  # Normalize
        return audio_data
    except Exception as e:
        print(f"Error converting audio to NumPy array: {e}")
        return np.array([])


def listen(duration):
    """Listens to microphone for a given duration, reports any notes detected"""
    
    segment = record_audio(duration)
    
    # compute fft
    fft_result = np.fft.fft(segment)
    freqs = np.fft.fftfreq(len(segment), 1 / SAMPLE_RATE)
    
    # get power spectrum (fft magnitude squared)
    power_spectrum = np.abs(fft_result) ** 2
    
    # band pass
    mask = (freqs >= lowest_freq) & (freqs <= highest_freq)
    freqs = freqs[mask]
    power_spectrum = power_spectrum[mask]
    
    # find peaks
    peak_indices, _ = find_peaks(power_spectrum, height=max(power_spectrum) * 0.1)
    peak_frequencies = freqs[peak_indices]
    power_values = power_spectrum[peak_indices]
    
    # Estimate fundamental frequency
    # _, estimated_fundamental, _, _ = estimate_fundamental(peak_frequencies, power_values)

    true_peaks, estimated_fundamental, removed_peaks, removed_power = estimate_fundamental(peak_frequencies, power_values)

    # # Plot power spectrum
    # plt.figure(figsize=(8, 4))
    # plt.plot(freqs, power_spectrum, label="Power Spectrum")

    # # Overlay harmonic markers
    # if estimated_fundamental:
    #     harmonics = [estimated_fundamental * i for i in range(1, 2000 // int(estimated_fundamental) + 1)]
    #     for h in harmonics:
    #         plt.axvline(x=h, color="r", linestyle="--", alpha=0.7, label="Estimated Harmonic" if h == harmonics[0] else "")

    # # Plot detected peaks in **blue**
    # plt.scatter(peak_frequencies, power_values, color='blue', label="Detected Peaks", zorder=3)

    # # Plot **removed peaks** in **red** with transparency
    # if removed_peaks:
    #     plt.scatter(removed_peaks, removed_power, color='red', alpha=0.5, label="Removed Peaks", zorder=3)

    # plt.title(f"Estimated Fundamental: {estimated_fundamental:.2f} Hz" if estimated_fundamental else "No fundamental found")
    # plt.xlabel("Frequency (Hz)")
    # plt.ylabel("Power")
    # plt.legend()
    # plt.grid()
    # plt.show()
    # plt.savefig("plot.png")
    
    # Identify note
    detected_note = classify_note(estimated_fundamental)
    
    if detected_note:
        return detected_note
    
    return None