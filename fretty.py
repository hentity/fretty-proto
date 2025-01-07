import pyaudio
import numpy as np
import scipy.fftpack
from scipy.io import wavfile
from guitar_notes import guitar_notes


def getNote(frequency):
    # Find the closest note in guitar_notes based on frequency
    closest_note = min(
        guitar_notes, key=lambda note: abs(guitar_notes[note] - frequency)
    )
    return closest_note


def normalizeNote(note):
    # Normalize notes to remove sharps and return the base note (e.g., A# -> A)
    return note


def remove_harmonics(frequencies, amplitudes, harmonic_threshold=0.05):
    filtered_frequencies = []
    filtered_amplitudes = []

    for i, freq in enumerate(frequencies):
        is_harmonic = False
        for j, base_freq in enumerate(filtered_frequencies):
            if (
                abs(freq - base_freq * round(freq / base_freq))
                < harmonic_threshold * base_freq
            ):
                is_harmonic = True
                break
        if not is_harmonic:
            filtered_frequencies.append(freq)
            filtered_amplitudes.append(amplitudes[i])

    return np.array(filtered_frequencies), np.array(filtered_amplitudes)


def record_audio_to_array(format, channels, rate, chunk, record_seconds):
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk
    )

    frames = []
    for _ in range(0, int(rate / chunk * record_seconds)):
        data = stream.read(chunk)
        frames.append(np.frombuffer(data, dtype=np.int16))

    stream.stop_stream()
    stream.close()
    audio.terminate()

    return np.concatenate(frames)


def main():
    # Configuration
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 2048
    RECORD_SECONDS = 0.1

    while True:
        # Record audio
        print("Recording...")
        signal = record_audio_to_array(FORMAT, CHANNELS, RATE, CHUNK, RECORD_SECONDS)
        if signal.size == 0:
            print("No audio signal to process. Skipping.")
            continue

        # If stereo, convert to mono
        if len(signal.shape) == 2:
            signal = signal.sum(axis=1) / 2

        # FFT Analysis
        N = signal.shape[0]
        fft = abs(np.fft.fft(signal))
        fft_one_side = fft[: N // 2]
        fft_frequencies = np.fft.fftfreq(N, d=1.0 / RATE)[: N // 2]

        # Normalize FFT values
        normalized_absolute_values = fft_one_side / np.linalg.norm(fft_one_side)
        print(fft_frequencies)

        # Restrict to the frequency range 80 to 1000 Hz
        valid_indices = np.where((fft_frequencies >= 80) & (fft_frequencies <= 1000))
        fft_frequencies = fft_frequencies[valid_indices]
        fft_amplitudes = normalized_absolute_values[valid_indices]

        # Remove higher harmonics
        fft_frequencies, fft_amplitudes = remove_harmonics(
            fft_frequencies, fft_amplitudes
        )

        # Find the dominant frequency in the valid range
        if fft_amplitudes.size > 0:
            max_index = np.argmax(fft_amplitudes)
            dominant_frequency = fft_frequencies[max_index]
            best_note = getNote(dominant_frequency)
            print("Detected note:", best_note)
        else:
            print("No valid note detected in the range 80-1000 Hz.")

        # print("Detected note:", recorded_notes[-1] if recorded_notes else None)
        # print("Detected notes:", recorded_notes)


if __name__ == "__main__":
    main()
