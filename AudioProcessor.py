import sys
import threading
import time
import numpy as np
import soundcard as sc


# ---------------------------------------------------------------------------
# Detector de BPM — algoritmo de inter-onset intervals (IOI)
# ---------------------------------------------------------------------------
# Estrategia:
#   1. Cada vez que detectar_beat() confirma un onset de bombo, guardamos
#      el timestamp en un buffer circular de los últimos N onsets.
#   2. Calculamos los intervalos entre onsets consecutivos (IOI).
#   3. El BPM = 60 / mediana(IOI), que es más robusto que la media frente
#      a onsets dobles o fallos esporádicos.
#   4. Solo publicamos un BPM si tenemos ≥ 4 onsets recientes y todos los
#      IOI están dentro del rango 40–240 BPM (razonable para música).
#
# Referencia: Dixon, S. "Automatic Extraction of Tempo and Beat from
#             Expressive Performances" (JNMR, 2001).
# ---------------------------------------------------------------------------

class DetectorBPM:
    """Estima el BPM en tiempo real a partir de los onsets del bombo."""

    BPM_MIN = 40
    BPM_MAX = 240
    MAX_ONSETS = 16       # ventana deslizante de onsets
    CADUCIDAD_S = 4.0     # descartar onsets con más de N segundos de antigüedad

    def __init__(self):
        self._onsets: list[float] = []   # timestamps en segundos (time.monotonic)
        self.bpm: float = 0.0            # BPM estimado (0 = sin datos suficientes)
        self.confianza: float = 0.0      # 0.0–1.0 (qué regular es el tempo)

    def registrar_onset(self):
        """Llama a este método cada vez que se detecta un golpe de bombo."""
        ahora = time.monotonic()
        self._onsets.append(ahora)

        # Mantener solo la ventana reciente
        self._onsets = [t for t in self._onsets if ahora - t <= self.CADUCIDAD_S]
        if len(self._onsets) > self.MAX_ONSETS:
            self._onsets = self._onsets[-self.MAX_ONSETS:]

        self._recalcular()

    def _recalcular(self):
        """Recalcula BPM y confianza a partir del historial de onsets."""
        if len(self._onsets) < 4:
            self.bpm = 0.0
            self.confianza = 0.0
            return

        ioi = np.diff(self._onsets)   # intervalos entre onsets consecutivos

        # Filtrar IOI que no corresponden a BPM musicalmente razonables
        bpm_de_ioi = 60.0 / (ioi + 1e-9)
        mascara = (bpm_de_ioi >= self.BPM_MIN) & (bpm_de_ioi <= self.BPM_MAX)

        # Intentar con la mitad del IOI (onsets en corcheas → tempo en negras)
        if mascara.sum() < 2:
            ioi2 = ioi / 2.0
            bpm_de_ioi2 = 60.0 / (ioi2 + 1e-9)
            mascara2 = (bpm_de_ioi2 >= self.BPM_MIN) & (bpm_de_ioi2 <= self.BPM_MAX)
            if mascara2.sum() >= 2:
                ioi = ioi2
                mascara = mascara2

        ioi_validos = ioi[mascara]
        if len(ioi_validos) < 2:
            self.bpm = 0.0
            self.confianza = 0.0
            return

        mediana_ioi = float(np.median(ioi_validos))
        self.bpm = round(60.0 / mediana_ioi, 1)

        # Confianza: qué tan bajas son las desviaciones respecto a la mediana
        desviacion = float(np.std(ioi_validos) / (mediana_ioi + 1e-9))
        self.confianza = float(np.clip(1.0 - desviacion * 4, 0.0, 1.0))

    @property
    def bpm_str(self) -> str:
        """Cadena lista para mostrar en HUD."""
        if self.bpm <= 0:
            return "BPM: --"
        barras = int(self.confianza * 4)
        conf = "█" * barras + "░" * (4 - barras)
        return f"BPM: {self.bpm:.0f}  {conf}"

    def segundos_hasta_siguiente_beat(self) -> float:
        """
        Devuelve cuántos segundos faltan para el próximo beat estimado,
        o -1 si no hay datos suficientes.
        Útil para sincronizar efectos visuales con el tempo.
        """
        if self.bpm <= 0 or not self._onsets:
            return -1.0
        periodo = 60.0 / self.bpm
        elapsed = time.monotonic() - self._onsets[-1]
        return periodo - (elapsed % periodo)


# ---------------------------------------------------------------------------
# AudioProcessor
# ---------------------------------------------------------------------------

class AudioProcessor:
    """Maneja la captura y análisis matemático del audio (Modelo)."""

    def __init__(self, sample_rate=44100, frames=1024):
        self.sample_rate = sample_rate
        self.frames = frames
        self.audio_data = np.zeros((self.frames, 2))
        self.running = False

        # Ventana de Hann para eliminar fugas espectrales en la FFT
        self._ventana_hann = np.hanning(self.frames)

        # Buffer circular para detección de beat por energía relativa
        self._historial_energia = np.zeros(43)  # ~1 s a 43 fps
        self._idx_historial = 0
        self.beat_detectado = False

        # Cooldown para no registrar el mismo golpe varias veces seguidas
        self._ultimo_onset_t: float = 0.0
        self._cooldown_onset: float = 0.2  # 200 ms mínimo entre onsets (~300 BPM max)

        # Detector de BPM
        self.bpm = DetectorBPM()

        self.mic = self._iniciar_microfono()

    def _iniciar_microfono(self):
        print("Iniciando el sistema de audio... (puede tardar unos segundos)")
        default_speaker = sc.default_speaker()
        try:
            mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
            print("¡Todo listo! Escuchando el audio del sistema... Pulsa ESC para salir.")
            return mic
        except IndexError:
            print("Error: No se encontró el canal de audio interno.")
            sys.exit()

    def capturar_audio(self):
        with self.mic.recorder(samplerate=self.sample_rate) as recorder:
            while self.running:
                try:
                    self.audio_data = recorder.record(numframes=self.frames)
                except Exception:
                    pass

    def iniciar_hilo(self):
        self.running = True
        hilo = threading.Thread(target=self.capturar_audio, daemon=True)
        hilo.start()

    def detener(self):
        self.running = False

    def obtener_espectro(self):
        """Devuelve el espectro FFT normalizado con ventana de Hann."""
        mono_data = np.mean(self.audio_data, axis=1) * self._ventana_hann
        fft_data = np.abs(np.fft.rfft(mono_data))
        max_val = np.max(fft_data)
        if max_val > 1.0:
            fft_data = fft_data / max_val
        else:
            fft_data = np.zeros_like(fft_data)
        return fft_data

    def detectar_beat(self, subgraves_actual: float) -> bool:
        """
        Detección de onset por energía relativa + registro en DetectorBPM.

        - Dispara si subgraves_actual supera 1.5× la media histórica.
        - El cooldown evita registrar el mismo golpe más de una vez.
        - Cuando se confirma un onset nuevo, lo notifica al DetectorBPM.
        """
        media = np.mean(self._historial_energia) + 1e-6
        es_onset = subgraves_actual > 1.5 * media

        # Actualizar buffer circular siempre
        self._historial_energia[self._idx_historial] = subgraves_actual
        self._idx_historial = (self._idx_historial + 1) % len(self._historial_energia)

        ahora = time.monotonic()
        if es_onset and (ahora - self._ultimo_onset_t) > self._cooldown_onset:
            self.beat_detectado = True
            self._ultimo_onset_t = ahora
            self.bpm.registrar_onset()       # <-- alimenta el detector de BPM
        else:
            self.beat_detectado = False

        return self.beat_detectado