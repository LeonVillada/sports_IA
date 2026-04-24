# 🏆 Master Document: Sports AI Predictor (SaaS)

## 📖 Visión del Proyecto
Desarrollar una plataforma de Inteligencia Artificial que prediga resultados de fútbol con alta precisión, enfocándose en el mercado de **Hándicap Asiático** y probabilidades complejas ("parábolas" de goles). El objetivo es ofrecerlo como un servicio SaaS profesional.

## 🛠️ Stack Tecnológico Actual
- **Lenguaje:** Python 3.11 (Entorno Virtual `venv`).
- **Base de Datos:** MySQL (XAMPP local).
- **Backend:** FastAPI (Servidor de alto rendimiento).
- **IA/Matemática:** Pandas, TensorFlow, SciPy (Poisson Distribution).
- **Frontend:** HTML5, CSS3 Premium (Glassmorphism), JavaScript.

## 🗂️ Arquitectura de Datos
1. **Ligas y Equipos:** Mapeo único para evitar duplicados.
2. **Partidos (Matches):** Histórico desde 2010 + Próximos encuentros.
3. **Cuotas (Odds):** Seguimiento de casas de apuestas (Bet365 inicial).
4. **Predicciones:** Almacenamiento de confianza de la IA y retroalimentación de aciertos.

## 🚀 Fases del Desarrollo (Hoja de Ruta)
### Fase 1: Cimientos (COMPLETADO)
- [x] Configuración de entorno y MySQL.
- [x] Motor de ingesta de datos históricos gratuitos.
- [x] Carga inicial de Premier League y La Liga.

### Fase 2: El Cerebro (EN CURSO)
- [ ] Implementación de Distribución de Poisson (Cálculo de probabilidades).
- [ ] Desarrollo de Red Neuronal (Deep Learning).
- [ ] Creación de interfaz web (Dashboard).

### Fase 3: Producto y Nube (FUTURO)
- [ ] Despliegue en la nube (AWS/DigitalOcean).
- [ ] Sistema de pagos (PayPal/PSE).
- [ ] Alertas automáticas (Telegram/Push).

## 🛡️ Reglas de Oro del Proyecto
- **Costo Mínimo:** Priorizar fuentes de datos y herramientas gratuitas durante el desarrollo.
- **Retroalimentación:** La IA debe aprender de cada acierto y desacierto automáticamente.
- **Doble Perfil:** Interfaz "Pro" (datos técnicos) y "Friendly" (gráficos sencillos).
