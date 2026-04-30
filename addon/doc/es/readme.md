<div align="center">
  <img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="Logo de NVDA" width="120">
  <h1>AbsoluteYoutube</h1>
  <br>
  <p>Potente descargador de YouTube para usuarios de NVDA</p>
</div>

<br>

<div align="center">
  <p><b>autor:</b> chai chaimee</p>
  <p><b>url:</b> https://github.com/chaichaimee/AbsoluteYoutube</p>
</div>

---
<br>

> ## Novedades: La Actualización "Unbound"
> **Acelera tu flujo de trabajo: ¡Descargas de enlaces directos!**
>
> ¿Por qué perder tiempo abriendo una página de vídeo cuando puedes obtenerlo al instante? Nuestra última actualización introduce la revolucionaria función **"Focus & Fetch"**. Simplemente enfoca el cursor en cualquier enlace de vídeo e inicia la descarga inmediatamente, ¡sin esperar a que carguen las páginas!
>
> • **Unbound Search:** Descubre más contenido que nunca. Nuestro nuevo motor omite los límites estándar del algoritmo de YouTube, encontrando vídeos que suelen estar ocultos en las búsquedas habituales.
>
> • **Gestor de canales favoritos:** Crea tu propia colección de creadores y obtén actualizaciones automáticas sobre el contenido más reciente.
>
> • **Control de cola inteligente:** Gestiona tus descargas de forma eficiente con el nuevo sistema de cola en segundo plano.

<br>

## Descripción
AbsoluteYoutube es un complemento avanzado para NVDA que te permite descargar vídeos y medios de YouTube en formatos MP3, MP4 o WAV directamente desde tu navegador. Incluye sistemas inteligentes en segundo plano para descargas eficientes y reanudables, recorte de vídeo, instantáneas, copia de URL cortas y un gestor completo de descargas fallidas, todo accesible con gestos y menús sencillos.

<br>

## Teclas de acceso rápido
**NVDA+Y** – Comando de descarga (detección de pulsaciones múltiples)  
• Una pulsación: Descargar como MP3 (Alta calidad)  
• Dos pulsaciones: Descargar como MP4 (Vídeo)  
• Tres pulsaciones: Descargar como WAV (Audio sin compresión)

**CTRL+Mayús+Y** – Opciones y herramientas  
• Una pulsación: Abrir menú contextual (Acceso a todas las herramientas)  
• Dos pulsaciones: Abrir carpeta de destino de descarga  
• **Tres pulsaciones: Abrir el nuevo diálogo de búsqueda** (Acceso a resultados de Unbound Search)

**NVDA+Ctrl+Y** – Alternar descarga automática  
• Cambia entre descarga instantánea y el **Modo Cola**. Cuando está desactivado, los enlaces se envían al Gestor de lista de descargas para una acción posterior.

**NVDA+Mayús+Y** : Activar/desactivar modo de lista de reproducción

**ALT+Windows+Y** : Ciclar calidad de MP3 (128 → 192 → 256 → 320 kbps)

> Todos los atajos utilizan detección de pulsación (ventana de tiempo ~0,4 segundos). Puedes reasignarlos en NVDA → Gestos de entrada.

<br>

## Funciones clave explicadas
* **1. Diálogo de búsqueda Unbound (Tres pulsaciones de Mayús+Ctrl+Y)**  
  Esta no es una búsqueda estándar. Al activar la triple pulsación, entras en una interfaz de búsqueda especializada. A diferencia del sitio web de YouTube, que limita los resultados según tu historial, esta herramienta obtiene datos sin procesar, dándote acceso a una mayor variedad de vídeos e información.

<br>

* **2. Colección de canales favoritos (Guía paso a paso)**  
  No pierdas la pista de tus creadores favoritos. Así es como puedes crear tu colección:  
  * **Paso 1:** Ve a YouTube y copia la URL del canal que quieras seguir (ej., youtube.com/@NombreDelCanal).
  * **Paso 2:** Abre el menú contextual de AbsoluteYoutube (Una pulsación Ctrl+Mayús+Y) y selecciona "Canales favoritos".
  * **Paso 3:** Selecciona la opción para añadir un nuevo canal y pega la URL copiada.
  * **El beneficio:** Una vez añadido, cada vez que abras este canal a través del diálogo, el sistema comprobará automáticamente si hay nuevos vídeos subidos y te los presentará en una lista al instante.

<br>

* **3. Gestor de lista de descargas y cola inteligente (NVDA+Ctrl+Y)**  
  Si estás ocupado y no quieres descargar inmediatamente, presiona **NVDA+Ctrl+Y** para desactivar la descarga automática. Todos los archivos solicitados se enviarán a una "Cola".  
  • Para procesarlos, abre el **Gestor de lista de descargas** desde el menú contextual.  
  • Haz clic derecho en cualquier elemento para iniciar la descarga, eliminarlo o reintentarlo.

<br>

* **4. Sistema inteligente de descarga en segundo plano**  
  • Gestor de colas: Las descargas se ejecutan una a una para ahorrar CPU/RAM.  
  • Reanudar al reiniciar: Las descargas interrumpidas se guardan y se reanudan automáticamente al reiniciar NVDA.  
  • Reparación automática de archivos: Limpia archivos temporales corruptos antes de comenzar.  
  • Omitir existentes: Evita descargar el mismo archivo dos veces.

<br>

* **5. Recortar clips de vídeo (uTubeTrim)**  
  Abrir menú contextual → Ajuste de recorte. Establece el tiempo de inicio/fin y elige tu formato. Perfecto para capturar segmentos específicos sin descargar todo el vídeo.

<br>

* **6. Gestor de descargas fallidas**  
  Lista persistente de elementos fallidos. Haz clic derecho en cualquier elemento para reintentar, limpiar o descargar todas las tareas restantes.

<br>

> **Nota:** Todas las funciones son altamente configurables en Configuración de NVDA → Absolute YouTube. Los atajos se pueden cambiar en Gestos de entrada.

<br>
<br>

## Apóyame
Si esta herramienta te ha facilitado la vida, considera impulsar la próxima actualización con una pequeña donación.

<br>

[![Apóyame](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01)

<br>

Tu apoyo significa mucho. Construyamos algo grande juntos.

<br>

&copy; 2026 Chai Chaimee Complemento NVDA lanzado bajo GNU