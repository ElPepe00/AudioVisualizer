import numpy as np
import pygame
import math
import sys
from AudioProcessor import AudioProcessor


class VisualizadorFractal:
    """Maneja la interfaz de usuario, la ventana y el dibujado (Vista/Controlador)."""

    def __init__(self, width=800, height=600):
        # Iniciamos solo el módulo de video, saltándonos el mixer (audio) de Pygame.
        pygame.display.init()
        pygame.font.init()          # MEJORA — HUD de modo activo
        self.width = width
        self.height = height
        # MEJORA — Ventana redimensionable
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("Visualizador Fractal de Audio")
        self.clock = pygame.time.Clock()

        # Instancia de nuestro procesador (Encapsulación)
        self.audio = AudioProcessor()

        # MEJORA — Surface semi-transparente para el trail (persistencia retinal).
        # En lugar de borrar la pantalla entera con fill(), superponemos una capa
        # negra con alpha bajo. Esto hace que las trazas del fractal se desvanezcan
        # gradualmente, igual que en Milkdrop/ProjectM.
        self._recrear_trail()

        # MEJORA — Fuente pequeña para el HUD
        self._font = pygame.font.SysFont("monospace", 13)
        self._nombres_modo = [
            "Líneas clásicas",
            "Nodos circulares",
            "Triángulos",
            "Círculos alternos",
        ]

        # Estado visual — idéntico al original
        self.smooth_subgraves = 0.0
        self.smooth_graves = 0.0
        self.smooth_medios_bajos = 0.0
        self.smooth_medios_altos = 0.0
        self.smooth_agudos = 0.0
        self.smooth_brillo = 0.0
        self.color_offset = 0.0

        # Variables para el detector de ritmo — idéntico al original
        self.modo_actual = 0
        self.ultimo_cambio_modo = 0

        # BPM — pulso visual sincronizado con el tempo estimado
        # Cuando falta poco para el siguiente beat pintamos un anillo
        # que se expande y desvanece desde el centro, como un metrónomo.
        self._pulso_radio = 0.0          # radio actual del anillo
        self._pulso_alpha = 0.0          # opacidad 0-255
        self._pulso_activo = False       # True el frame en que se dispara
        
        # MEJORA — Caleidoscopio reactivo al ritmo
        self._num_brazos = 6             # número de brazos del caleidoscopio
        self._expansion_beat = 0.0       # factor de expansión durante beats (0-1)
        self._rotacion_bpm = 0.0         # ángulo de rotación sincronizado con BPM
        
        # MEJORA — Múltiples puntos de origen para los caleidoscopios
        self._puntos_origen = [
            {"nombre": "centro", "tipo": "fijo"},
            {"nombre": "izquierda", "tipo": "dinamico"},
            {"nombre": "derecha", "tipo": "dinamico"},
        ]

    # ------------------------------------------------------------------
    # Recrear trail cuando cambia el tamaño de ventana
    # ------------------------------------------------------------------

    def _recrear_trail(self):
        """Crea o recrea el surface del trail según el tamaño actual."""
        self._trail = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self._trail.fill((0, 0, 0, 30))  # alpha 30 ≈ desvanecimiento en ~20 frames

    # ------------------------------------------------------------------
    # Fractal recursivo — IGUAL al original, sin tocar
    # ------------------------------------------------------------------

    def _dibujar_fractal_recursivo(self, x, y, angulo, longitud, profundidad, grosor, factor_angulo, hue_base, modo):
        if profundidad == 0:
            return

        x_fin = x + longitud * math.cos(angulo)
        y_fin = y + longitud * math.sin(angulo)

        color = pygame.Color(0)
        color.hsva = (int(hue_base + profundidad * 15) % 360, 100, 100, 100)

        if modo == 0:
            pygame.draw.line(self.screen, color, (int(x), int(y)), (int(x_fin), int(y_fin)), max(1, int(grosor)))
        elif modo == 1:
            pygame.draw.line(self.screen, color, (int(x), int(y)), (int(x_fin), int(y_fin)), max(1, int(grosor // 3)))
            pygame.draw.circle(self.screen, color, (int(x_fin), int(y_fin)), max(2, int(grosor * 1.2)))
        elif modo == 2:
            p1 = (x_fin + grosor * 2 * math.cos(angulo), y_fin + grosor * 2 * math.sin(angulo))
            p2 = (x + grosor * 1.5 * math.cos(angulo + math.pi/2), y + grosor * 1.5 * math.sin(angulo + math.pi/2))
            p3 = (x + grosor * 1.5 * math.cos(angulo - math.pi/2), y + grosor * 1.5 * math.sin(angulo - math.pi/2))
            pygame.draw.polygon(self.screen, color, [p1, p2, p3])
        elif modo == 3:
            pygame.draw.circle(self.screen, color, (int(x_fin), int(y_fin)), max(1, int(grosor * 1.5)), 1 if profundidad % 2 == 0 else 0)

        nueva_longitud = longitud * 0.7
        nuevo_grosor = grosor * 0.7

        self._dibujar_fractal_recursivo(x_fin, y_fin, angulo - factor_angulo, nueva_longitud, profundidad - 1, nuevo_grosor, factor_angulo, hue_base, modo)
        self._dibujar_fractal_recursivo(x_fin, y_fin, angulo + factor_angulo, nueva_longitud, profundidad - 1, nuevo_grosor, factor_angulo, hue_base, modo)

    # ------------------------------------------------------------------
    # Calcular posiciones dinámicas de los puntos de origen
    # ------------------------------------------------------------------

    def _calcular_puntos_origen(self):
        """
        Devuelve una lista con (x, y) de los puntos de origen para los caleidoscopios.
        El patrón cambia dinámicamente según qué frecuencias dominan.
        """
        puntos = []
        tiempo_ms = pygame.time.get_ticks()
        
        # Determinar qué frecuencias dominan
        subgraves_dominan = self.smooth_subgraves > 0.6 and self.smooth_subgraves > self.smooth_medios_altos
        graves_dominan = self.smooth_graves > 0.5 and self.smooth_graves > self.smooth_agudos
        medios_dominan = self.smooth_medios_altos > 0.6 and self.smooth_medios_altos > self.smooth_graves
        agudos_dominan = self.smooth_agudos > 0.6
        brillo_activo = self.smooth_brillo > 0.7
        
        energia_total = self.smooth_medios_altos + self.smooth_agudos + self.smooth_brillo
        
        # PATRÓN 1: Solo subgraves → Solo centro (pulsación central)
        if subgraves_dominan and energia_total < 0.5:
            puntos.append((self.width // 2, self.height // 2))
        
        # PATRÓN 2: Graves dominantes → Centro + lados
        elif graves_dominan and energia_total < 0.6:
            # Centro
            puntos.append((self.width // 2, self.height // 2))
            
            # Izquierda — oscila arriba-abajo según graves
            desplazamiento_y_izq = math.sin(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((self.width // 4, self.height // 2 + int(desplazamiento_y_izq)))
            
            # Derecha — oscila con desfase
            desplazamiento_y_der = math.cos(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((3 * self.width // 4, self.height // 2 + int(desplazamiento_y_der)))
        
        # PATRÓN 3: Medios-altos dominantes → Solo lados (sin centro)
        elif medios_dominan and energia_total > 0.5:
            # Izquierda
            desplazamiento_y_izq = math.sin(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((self.width // 4, self.height // 2 + int(desplazamiento_y_izq)))
            
            # Derecha
            desplazamiento_y_der = math.cos(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((3 * self.width // 4, self.height // 2 + int(desplazamiento_y_der)))
        
        # PATRÓN 4: Agudos intensos → Centro + arriba + abajo (vertical)
        elif agudos_dominan and energia_total > 0.6:
            # Centro
            puntos.append((self.width // 2, self.height // 2))
            # Arriba-centro
            puntos.append((self.width // 2, int(self.height * 0.15)))
            # Abajo-centro
            puntos.append((self.width // 2, int(self.height * 0.85)))
        
        # PATRÓN 5: Brillo máximo → Todo activado (centro, lados, arriba, abajo, esquinas)
        elif brillo_activo or energia_total > 0.75:
            # Centro
            puntos.append((self.width // 2, self.height // 2))
            
            # Lados
            desplazamiento_y_izq = math.sin(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((self.width // 4, self.height // 2 + int(desplazamiento_y_izq)))
            
            desplazamiento_y_der = math.cos(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((3 * self.width // 4, self.height // 2 + int(desplazamiento_y_der)))
            
            # Arriba y abajo
            puntos.append((self.width // 2, int(self.height * 0.15)))
            puntos.append((self.width // 2, int(self.height * 0.85)))
            
            # Esquinas
            puntos.append((int(self.width * 0.15), int(self.height * 0.15)))  # arriba-izq
            puntos.append((int(self.width * 0.85), int(self.height * 0.15)))  # arriba-der
            puntos.append((int(self.width * 0.15), int(self.height * 0.85)))  # abajo-izq
            puntos.append((int(self.width * 0.85), int(self.height * 0.85)))  # abajo-der
        
        # PATRÓN DEFAULT: Centro + lados (configuración balanceada)
        else:
            # Centro
            puntos.append((self.width // 2, self.height // 2))
            
            # Izquierda
            desplazamiento_y_izq = math.sin(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((self.width // 4, self.height // 2 + int(desplazamiento_y_izq)))
            
            # Derecha
            desplazamiento_y_der = math.cos(tiempo_ms / 2000.0) * (self.smooth_graves * 150)
            puntos.append((3 * self.width // 4, self.height // 2 + int(desplazamiento_y_der)))
            
            # Arriba-centro si hay energía media
            if energia_total > 0.4:
                puntos.append((self.width // 2, int(self.height * 0.15)))
                puntos.append((self.width // 2, int(self.height * 0.85)))
        
        return puntos

    # ------------------------------------------------------------------
    # Suavizado — MISMO coeficiente que el original (0.7 / 0.3)
    # ------------------------------------------------------------------

    def _actualizar_suavizado(self, subgraves, graves, medios_bajos, medios_altos, agudos, brillo):
        """Interpola los valores crudos para evitar movimientos bruscos."""
        self.smooth_subgraves    = self.smooth_subgraves    * 0.7 + subgraves    * 0.3
        self.smooth_graves       = self.smooth_graves       * 0.7 + graves       * 0.3
        self.smooth_medios_bajos = self.smooth_medios_bajos * 0.7 + medios_bajos * 0.3
        self.smooth_medios_altos = self.smooth_medios_altos * 0.7 + medios_altos * 0.3
        self.smooth_agudos       = self.smooth_agudos       * 0.7 + agudos       * 0.3
        self.smooth_brillo       = self.smooth_brillo       * 0.7 + brillo       * 0.3

    # ------------------------------------------------------------------
    # Renderizado — MISMO flujo que el original + mejoras puntuales
    # ------------------------------------------------------------------

    def _renderizar_fotograma(self, subgraves):
        """Contiene toda la lógica de dibujado de cada frame."""

        actividad_total = (
            self.smooth_subgraves + self.smooth_graves +
            self.smooth_medios_bajos + self.smooth_medios_altos +
            self.smooth_agudos + self.smooth_brillo
        )

        # Silencio → pantalla negra, sin trail
        if actividad_total < 0.05:
            self.screen.fill((0, 0, 0))
            pygame.display.flip()
            return

        # ------------------------------------------------------------------
        # MEJORA — Fondo con trail en lugar de fill completo.
        # Durante un beat fuerte mantenemos el fill original del original
        # (flash blanco-azulado) para preservar el impacto visual.
        # En el resto de frames el trail hace que las trazas se desvanezcan.
        # ------------------------------------------------------------------
        if subgraves > 0.65:
            # Flash de beat: fill completo (igual que el original)
            self.screen.fill((min(255, int(subgraves * 350)), 220, 255))
        else:
            # Trail suave: superponer capa semi-transparente sobre el frame anterior
            self.screen.blit(self._trail, (0, 0))

            # Fondo de color HSV tenue (mismo cálculo que el original)
            bg_hue = (pygame.time.get_ticks() / 30.0) % 360
            bg_brightness = min(100, int(self.smooth_subgraves * 150))
            bg_color = pygame.Color(0)
            bg_color.hsva = (bg_hue, 90, bg_brightness, 100)
            # Pintamos solo si el brillo es mayor que cero para no tapar el trail
            if bg_brightness > 5:
                # Surface temporal con alpha para mezclar el fondo con el trail
                bg_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                bg_surf.fill((*bg_color[:3], 40))
                self.screen.blit(bg_surf, (0, 0))

        # Parámetros del fractal — idénticos al original
        angulo_base       = math.pi / 5
        apertura_dinamica = angulo_base + (self.smooth_medios_altos * 2.5)
        longitud_tronco   = 40 + (self.smooth_graves * 150)
        profundidad_maxima = min(8, 5 + int(self.smooth_agudos * 8))

        self.color_offset = (self.color_offset + 1 + self.smooth_medios_bajos * 60) % 360

        inicio_x = self.width  // 2
        inicio_y = self.height // 2

        # Partículas orbitales — idénticas al original
        num_particulas = 8 + int(self.smooth_brillo * 80)
        radio_orbita   = 80 + (self.smooth_medios_bajos * 400)
        for p in range(num_particulas):
            angulo_p = (
                p * (2 * math.pi / max(1, num_particulas)) +
                (pygame.time.get_ticks() / 1500.0) * (1 + self.smooth_agudos * 3)
            )
            px = inicio_x + math.cos(angulo_p) * radio_orbita
            py = inicio_y + math.sin(angulo_p) * radio_orbita
            radio_p = max(3, int(self.smooth_brillo * 60))
            color_p = pygame.Color(0)
            color_p.hsva = ((self.color_offset + p * 15) % 360, 90, 100, 100)
            pygame.draw.circle(self.screen, color_p, (int(px), int(py)), radio_p)

        # Centro pulsante — idéntico al original
        radio_centro = 15 + int(self.smooth_subgraves * 200)
        color_centro = pygame.Color(0)
        color_centro.hsva = ((self.color_offset + 180) % 360, 100, 100, 100)
        pygame.draw.circle(self.screen, color_centro, (inicio_x, inicio_y), radio_centro)
        pygame.draw.circle(self.screen, (255, 255, 255), (inicio_x, inicio_y),
                           radio_centro + 2, max(1, int(self.smooth_subgraves * 10)))

        # ------------------------------------------------------------------
        # MEJORA — Detector de beat mejorado (usa AudioProcessor.detectar_beat)
        # en lugar del umbral fijo del original. Cooldown de 4 s conservado.
        # Ahora también activa la expansión del caleidoscopio.
        # ------------------------------------------------------------------
        tiempo_actual = pygame.time.get_ticks()
        beat = self.audio.detectar_beat(subgraves)
        if beat and (tiempo_actual - self.ultimo_cambio_modo > 4000):
            self.modo_actual = (self.modo_actual + 1) % 4
            self.ultimo_cambio_modo = tiempo_actual
        
        # Activar expansión del caleidoscopio en cada beat
        if beat:
            self._expansion_beat = 1.0

        # Caleidoscopio fractal — MEJORADO: más brazos y reactivo al ritmo
        # Número de brazos depende de la energía de medios-altos
        num_brazos_dinamico = min(12, 4 + int(self.smooth_medios_altos * 8))
        
        # Profundidad dinámica basada en agudos
        profundidad_dinamica = min(10, 5 + int(self.smooth_agudos * 5))
        
        # Rotación sincronizada con BPM
        if self.audio.bpm.bpm > 0:
            periodo_bpm = 60.0 / self.audio.bpm.bpm
            self._rotacion_bpm = (pygame.time.get_ticks() / (periodo_bpm * 1000.0)) * (2 * math.pi)
        
        # Decaimiento de expansión de beat
        if self._expansion_beat > 0:
            self._expansion_beat = max(0, self._expansion_beat - 0.08)
        
        # MEJORA — Dibujar desde múltiples puntos de origen
        puntos_origen = self._calcular_puntos_origen()
        
        for punto_idx, (origen_x, origen_y) in enumerate(puntos_origen):
            for i in range(num_brazos_dinamico):
                # Ángulo base con simetría radial + rotación por BPM + movimiento por graves
                # Cada punto tiene un desfase de color diferente
                angulo_inicial = (i * (2 * math.pi / num_brazos_dinamico) + 
                                self._rotacion_bpm + 
                                self.smooth_graves * 0.5)
                
                # Longitud del tronco aumenta con expansion de beat
                long_con_expansion = longitud_tronco * (1.0 + self._expansion_beat * 0.5)
                
                # Grosor ligeramente diferente según el punto de origen
                grosor_dinamico = max(1, 5 + int(self.smooth_brillo * 15) - punto_idx)
                
                self._dibujar_fractal_recursivo(
                    x=origen_x, y=origen_y,
                    angulo=angulo_inicial,
                    longitud=long_con_expansion,
                    profundidad=profundidad_dinamica,
                    grosor=grosor_dinamico,
                    factor_angulo=apertura_dinamica,
                    hue_base=(self.color_offset + punto_idx * 60) % 360,  # color diferente por punto
                    modo=self.modo_actual,
                )

        # ------------------------------------------------------------------
        # Pulso visual de BPM — anillo que se expande desde el centro
        # sincronizado con el tempo estimado (no con el onset crudo).
        # ------------------------------------------------------------------
        seg_hasta_beat = self.audio.bpm.segundos_hasta_siguiente_beat()
        if seg_hasta_beat != -1:
            periodo = 60.0 / max(self.audio.bpm.bpm, 1)
            # Disparar el pulso cuando queda < 1 frame para el siguiente beat
            if seg_hasta_beat < (1.0 / 60.0) or self.audio.beat_detectado:
                self._pulso_radio = radio_centro + 10
                self._pulso_alpha = 220

            # Animar el anillo: crece y se desvanece
            if self._pulso_alpha > 0:
                self._pulso_radio += 8
                self._pulso_alpha = max(0, self._pulso_alpha - 18)
                pulso_color = pygame.Color(0)
                # Color complementario al centro para que destaque
                pulso_hue = (self.color_offset + 90) % 360
                pulso_color.hsva = (pulso_hue, 80, 100, 100)
                if self._pulso_radio < max(self.width, self.height):
                    pygame.draw.circle(
                        self.screen, pulso_color,
                        (inicio_x, inicio_y),
                        int(self._pulso_radio), 2,
                    )

        # ------------------------------------------------------------------
        # HUD — modo activo + BPM con barra de confianza + indicador de beat
        # ------------------------------------------------------------------
        linea1 = self._font.render(
            f"Modo {self.modo_actual}: {self._nombres_modo[self.modo_actual]}  "
            f"{'● BEAT' if self.audio.beat_detectado else ''}",
            True, (200, 200, 200),
        )
        linea2 = self._font.render(
            self.audio.bpm.bpm_str,
            True,
            # Verde si hay buena confianza, amarillo si es estimación débil
            (80, 255, 120) if self.audio.bpm.confianza > 0.6
            else (255, 220, 60) if self.audio.bpm.bpm > 0
            else (140, 140, 140),
        )
        self.screen.blit(linea1, (8, 8))
        self.screen.blit(linea2, (8, 24))

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Bucle principal — idéntico al original + teclas ← → para cambio manual
    # ------------------------------------------------------------------

    def ejecutar(self):
        """Bucle principal de la aplicación."""
        self.audio.iniciar_hilo()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    # MEJORA — Manejar redimensionamiento de ventana
                    self.width, self.height = event.size
                    self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                    self._recrear_trail()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    # MEJORA — Cambio manual de modo con flechas
                    elif event.key == pygame.K_RIGHT:
                        self.modo_actual = (self.modo_actual + 1) % 4
                    elif event.key == pygame.K_LEFT:
                        self.modo_actual = (self.modo_actual - 1) % 4
                    # MEJORA — Pantalla completa con tecla F
                    elif event.key == pygame.K_f:
                        self.is_fullscreen = not self.is_fullscreen
                        if self.is_fullscreen:
                            self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode((self.width, self.height))

            fft_data = self.audio.obtener_espectro()

            # Rangos de bins idénticos al original
            subgraves    = np.mean(fft_data[1:3])
            graves       = np.mean(fft_data[3:10])
            medios_bajos = np.mean(fft_data[10:30])
            medios_altos = np.mean(fft_data[30:60])
            agudos       = np.mean(fft_data[60:120])
            brillo       = np.mean(fft_data[120:250])

            self._actualizar_suavizado(subgraves, graves, medios_bajos, medios_altos, agudos, brillo)
            self._renderizar_fotograma(subgraves)

            self.clock.tick(60)

        self.audio.detener()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    app = VisualizadorFractal()
    app.ejecutar()