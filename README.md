# Visualizador Fractal de Audio 🎵✨

Un visualizador de música en tiempo real que genera **fractales caleidoscópicos reactivos** sincronizados con el ritmo y las frecuencias del audio. Combina detección de beats, análisis espectral FFT y geometría fractal para crear visualizaciones hipnotizantes.

## Características Principales

### 🎨 Visualización Fractal Dinámica
- **Fractales recursivos** que cambian de forma según el audio
- **4 modos de dibujo**: Líneas clásicas, nodos circulares, triángulos y círculos alternos
- **Colores HSV** con desvanecimiento suave (trail visual)
- **Rotación sincronizada con BPM** del tempo detectado

### 🔊 Análisis de Audio en Tiempo Real
- Captura de audio del sistema mediante **loopback**
- Análisis espectral con **FFT (transformada de Fourier rápida)**
- Descomposición en **6 rangos de frecuencia**: subgraves, graves, medios-bajos, medios-altos, agudos y brillo
- **Suavizado exponencial** para transiciones fluidas

### 🎯 Detección Inteligente de Beats
- Algoritmo de **inter-onset intervals (IOI)** para estimación de BPM
- Detección de energía relativa en subgraves
- **Confianza de tempo** visualizada en el HUD
- Cooldown anti-rebote (200 ms mínimo entre beats)

### 🌊 Patrones Adaptativos Inteligentes
El caleidoscopio cambia de configuración automáticamente según qué frecuencias dominan:

| Patrón | Situación | Descripción |
|--------|-----------|-------------|
| **Centro único** | Subgraves intensos | Pulsación central pura |
| **Centro + Lados** | Graves dominantes | Configuración clásica balanceada |
| **Solo Lados** | Medios-altos fuertes | Fractales laterales sin centro |
| **Vertical** | Agudos intensos | Centro, arriba y abajo |
| **Explosión** | Brillo máximo | 9 puntos: centro, lados, arriba, abajo y 4 esquinas |

### 📊 Interfaz de Usuario
- **HUD en tiempo real** con modo actual, indicador de beat y BPM
- **Barra de confianza** de tempo (colores: verde = confianza alta, amarillo = baja)
- **Pulso visual BPM** sincronizado con el tempo estimado
- **Cambio de modo manual** con teclas ← →

## Requisitos

### Sistema Operativo
- Windows (testado en Windows 10+)
- Linux (requiere configuración adicional de audio)
- macOS (requiere ajustes de permisos)

### Python
- Python 3.8+

### Dependencias
```
numpy
pygame-ce >= 2.5.0
soundcard >= 0.4.6
```

## Instalación

### 1. Clonar o descargar el proyecto
```bash
cd AudioVisualizer
```

### 2. Crear un entorno virtual (recomendado)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS
```

### 3. Instalar dependencias
```bash
pip install numpy pygame-ce soundcard
```

### Nota sobre Audio en Windows
El visualizador usa **loopback recording** para capturar audio del sistema:

- **Windows 10/11**: Se recomienda usar **Stereo Mix** (mezcla estéreo) o VB-Audio Virtual Cable
- Verificar que el dispositivo loopback esté disponible en Sonido → Grabación
- Si no aparece, habilitar en el Panel de Control

## Uso

### Ejecutar el visualizador
```bash
python visualizer.py
```

### Interfaz
- **Ventana redimensionable**: Arrastra los bordes o esquinas para cambiar el tamaño
- Los fractales se adaptan automáticamente al nuevo tamaño
- Los puntos de origen se recalculan proporcionalmente
- Todos los elementos escalan fluidamente

### Controles
| Tecla | Acción |
|-------|--------|
| **ESC** | Salir |
| **← (flecha izquierda)** | Modo anterior |
| **→ (flecha derecha)** | Modo siguiente |

### Recomendaciones
- Reproducir música con **volumen moderado-alto** para activar todos los patrones
- Géneros con buena definición de beats (EDM, Pop, Hip-hop) funcionan mejor
- Los fractales reaccionan mejor en momentos con **cambios dinámicos** de energía

## Arquitectura

### Diseño Modular

```
visualizer_spotify/
├── visualizer.py          # Controlador/Vista (Pygame)
├── AudioProcessor.py      # Modelo (análisis de audio)
└── README.md              # Documentación
```

### Componentes

#### **AudioProcessor.py** — Procesamiento de Audio
```
AudioProcessor
├── capturar_audio()       # Thread daemon de captura
├── obtener_espectro()     # FFT normalizado
├── detectar_beat()        # Detección de onset
└── DetectorBPM
    ├── registrar_onset()  # Registro temporal
    ├── bpm_str            # Cadena para HUD
    └── segundos_hasta_siguiente_beat()  # Sincronización visual
```

**Algoritmo de BPM (IOI)**:
1. Cada beat dispara `registrar_onset()` con timestamp
2. Se calcula la diferencia entre onsets consecutivos (IOI)
3. BPM = 60 / mediana(IOI)
4. Se valida que todos los IOI estén en rango 40-240 BPM
5. Se calcula confianza como `1 - (desv_std / mediana) * 4`

#### **VisualizadorFractal** — Renderización
```
VisualizadorFractal
├── _dibujar_fractal_recursivo()  # Recursión binaria
├── _calcular_puntos_origen()     # Lógica de patrones
├── _actualizar_suavizado()       # Interpolación exponencial
└── _renderizar_fotograma()       # Loop principal de render
```

### Flujo de Datos

```
Audio del Sistema
       ↓
[AudioProcessor]
       ↓
FFT + Descomposición en 6 bandas
       ↓
Detección de Beat + Cálculo de BPM
       ↓
[VisualizadorFractal]
       ↓
Cálculo de parámetros dinámicos:
  - Número de brazos (medios-altos)
  - Profundidad (agudos)
  - Rotación (BPM)
  - Expansión (beats)
  - Puntos de origen (patrón adaptativo)
       ↓
Renderizado con Pygame @ 60 FPS
```

## Detalles Técnicos

### Descomposición de Frecuencias
```python
subgraves    = FFT[1:3]      # 43-172 Hz (graves profundos)
graves       = FFT[3:10]     # 172-516 Hz (bajo)
medios_bajos = FFT[10:30]    # 516-1547 Hz (cálido)
medios_altos = FFT[30:60]    # 1547-3093 Hz (presencia)
agudos       = FFT[60:120]   # 3093-6186 Hz (brillo)
brillo       = FFT[120:250]  # 6186-12500 Hz (ultra-brillante)
```

### Parámetros Dinámicos Reactivos

#### Número de Brazos
```python
num_brazos = min(12, 4 + int(smooth_medios_altos * 8))
# Mínimo 4, máximo 12 según energía en medios-altos
```

#### Profundidad de Recursión
```python
profundidad = min(10, 5 + int(smooth_agudos * 5))
# Mínimo 5, máximo 10 según intensidad de agudos
```

#### Rotación Sincronizada con BPM
```python
periodo = 60 / bpm
rotacion = (tiempo_ms / (periodo * 1000)) * 2π
# Rotación completa cada beat
```

#### Expansión por Beat
```python
expansion = 1.0 (al detectar beat)
expansion *= 0.92 cada frame (decaimiento)
longitud = longitud_base * (1 + expansion * 0.5)
```

### Suavizado Exponencial
```python
smooth_valor = smooth_valor * 0.7 + valor_crudo * 0.3
# 0.7/0.3 ratio = ~20 frames de interpolación
```

### Trail Visual (Persistencia Retinal)
```python
# En lugar de fill() completo, usamos blitting semi-transparente
trail_surface = pygame.Surface(size, SRCALPHA)
trail_surface.fill((0, 0, 0, 30))  # Alpha 30 ≈ 20 frames decaimiento
screen.blit(trail_surface, (0, 0))
```

## Escalado Dinámico y Redimensionamiento

La ventana es completamente **redimensionable** y todos los elementos se adaptan proporcionalmente:

- **Centros de pantalla**: Se recalculan cada frame como `width // 2` e `height // 2`
- **Puntos de origen**: Se actualizan dinámicamente en función del tamaño actual
  - Centro: `(width // 2, height // 2)`
  - Izquierda: `(width // 4, ...)`
  - Derecha: `(3 * width // 4, ...)`
  - Esquinas: `(0.15 * width, ...)` etc.
- **Partículas orbitales**: El radio orbita se escala con los medios-bajos
- **Trail visual**: Se recrea automáticamente al cambiar tamaño

### Rendimiento en Redimensionamiento
- El trail se recrea eficientemente solo cuando cambia el tamaño
- Los fractales se redibujan cada frame con los nuevos centros
- La rotación BPM se mantiene sincronizada

## Ejemplos de Reacción

### 🥁 Música EDM/Techno
- **Beats claros** → Expansión perceptible
- **Bajos constantes** → Patrón Centro + Lados estable
- **Builds progresivos** → Aumento gradual de brazos
- **Drop** → Explosión a 9 puntos

### 🎸 Música Rock
- **Refrán vs Verso** → Alternancia de patrones
- **Intro lenta** → Pocos brazos, rotación lenta
- **Solo de guitarra** → Aumento de agudos → Profundidad máxima
- **Batería en crescendo** → Expansión de beat más intensa

### 🎹 Música Clásica/Ambient
- **Dinámica lenta** → Cambios suaves de configuración
- **Crescendos** → Lenta acumulación de brazos
- **Silencios** → Pantalla negra (< 0.05 energía)

## Referencias Científicas

### Detección de Beats
**Dixon, S.** (2001). *Automatic Extraction of Tempo and Beat from Expressive Performances*. Journal of New Music Research.

**Algorithm**: Robust beat tracking usando inter-onset intervals (IOI) y análisis de energía espectral.

### Procesamiento de Audio
- **FFT (Fast Fourier Transform)**: Descomposición en componentes frecuenciales
- **Ventana de Hann**: Reduce fugas espectrales en análisis espectral
- **Normalización**: Valores entre 0-1 independiente del volumen

### Fractales
- **Recursión binaria**: Cada rama genera 2 subramas
- **Factor de escala**: 0.7 en longitud y grosor por nivel
- **Ángulo dinámico**: Varía según energía media-alta

## Problemas Comunes

### ❌ "Error: No se encontró el canal de audio interno"
**Solución**: 
- Windows: Habilitar Stereo Mix en Sonido → Grabación
- Alternativa: Usar [VB-Audio Virtual Cable](https://vb-audio.com/Cable/)

### ❌ Visualización muy lenta/jerky
**Soluciones**:
- Reducir resolución de ventana en `__init__`: `VisualizadorFractal(width=640, height=480)`
- Reducir `profundidad_dinamica` máxima en `_renderizar_fotograma()`
- Cerrar otras aplicaciones que consuman GPU

### ❌ No detecta BPM
**Causas y soluciones**:
- Necesita mínimo 4 beats en los últimos 4 segundos
- Música con beats muy irregulares o lentos (< 40 BPM)
- Probar con música de tempo estable (80-140 BPM)

### ❌ Colores saturados/parpadeo
**Solución**: Ajustar el brillo en fondo → `bg_surf.fill((*bg_color[:3], 40))`

## Mejoras Futuras

- 🎵 Integración con Spotify API para metadatos
- 🎚️ Panel de controles para ajustar parámetros en tiempo real
- 🖼️ Exportar frames a vídeo
- 🌈 Más temas de colores personalizables
- 📊 Análisis espectrograma en tiempo real
- 🔊 Soporte para entrada de micrófono
- 🎮 Modo interactivo con controles MIDI

## Licencia

Este proyecto es de código abierto. Libre para uso educativo y personal.

## Autor

Desarrollado por Josep Oliver como herramienta de análisis de audio y visualización artística.

---

**¡Disfruta del espectáculo visual!** 🎬✨

Para reportar problemas o sugerir mejoras, verifica los logs de consola para mensajes de depuración.
