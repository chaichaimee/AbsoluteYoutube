# AbsoluteYoutube

Potente descargador de YouTube para usuarios de NVDA

![NVDA Logo](https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico)

**Autor:** chai chaimee  
**GitHub:** https://github.com/chaichaimee/AbsoluteYoutube

## Descripción

AbsoluteYoutube es un complemento avanzado para NVDA que permite descargar videos y medios de YouTube directamente desde el navegador en formatos MP3, MP4 o WAV. Incluye sistemas inteligentes en segundo plano para descargas eficientes y reanudables, recorte de videos, capturas, copia de URL corta y un administrador completo de descargas fallidas – todo accesible con gestos simples y menús.

## Teclas rápidas

- **NVDA+Y** – Gesto de descarga (detección de toques)  
  - Toque simple: Descargar como MP3  
  - Toque doble: Descargar como MP4  
  - Toque triple: Descargar como WAV  

- **CTRL+Shift+Y** – Menú contextual / Carpeta  
  - Toque simple: Abrir menú contextual (con todas las opciones)  
  - Toque doble: Abrir carpeta de destino  

- **NVDA+Shift+Y** : Alternar modo lista de reproducción  

- **ALT+Windows+Y** : Ciclar calidad MP3 (128 → 192 → 256 → 320 kbps)  

Todas las teclas usan detección de toques (~0.4 segundos). Reasigna en NVDA → Gestos de entrada.

## Características

- **Descarga multi-formato (MP3 / MP4 / WAV)**  
  Presiona NVDA+Y una, dos o tres veces para descargar el video actual en el formato elegido. Soporta videos individuales y listas. En modo lista crea automáticamente subcarpeta con nombre de la playlist y guarda todo allí – descargas individuales quedan separadas y organizadas.

- **Sistema inteligente de descarga en segundo plano**  
  - Gestor de cola: Descargas se ejecutan secuencialmente o con concurrencia limitada (hasta 4 configurable).  
  - Reanudación al reiniciar: Descargas interrumpidas se guardan y pueden reanudarse automáticamente o por pregunta.  
  - Reparación automática: Limpia archivos temporales corruptos antes de nuevas descargas.  
  - Omitir existentes: Omite automáticamente archivos ya descargados.  
  - Descarga multi-parte: Divide archivo en hasta 16 partes para mayor velocidad (opcional).  
  Todas las funciones en Ajustes NVDA → AbsoluteYoutube.

- **Recorte de clips de video**  
  En página YouTube → Menú contextual (CTRL+Shift+Y toque simple) → Configuración recorte.  
  Establecer inicio/fin → Elegir MP3 (128–320 kbps), MP4 (H.265) o WAV → Previsualizar → Descargar clip.  
  Guardado como "Trimmed Clip 1.mp3", etc.

- **Captura de instantánea**  
  Menú contextual → Snapshot.  
  Descarga miniatura de alta calidad como .jpg completo – ideal para portadas.

- **Copiar URL corta**  
  Menú contextual → Copy video Shorten URL.  
  Convierte enlace completo a formato corto y copia al portapapeles al instante.

- **Gestor de descargas fallidas**  
  Menú contextual → Download fail manager.  
  Lista con título, duración, URL.  
  Clic derecho:  
  - Eliminar seleccionado  
  - Descargar ahora (reintentar)  
  - Descargar todos  
  - Limpiar todo  
  Elementos fallidos se mantienen – reintenta cuando quieras.

- **Actualización yt-dlp**  
  Manual: Ajustes → Update yt-dlp now.  
  Auto: Activar "Auto-update yt-dlp on startup".

**Nota**  
Todas las funciones configurables en Ajustes NVDA → AbsoluteYoutube. Teclas modificables en Gestos de entrada.