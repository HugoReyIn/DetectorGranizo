# Detector de Granizo

Detector de Granizo es una aplicación web desarrollada con FastAPI y ejecutada mediante Uvicorn. Permite la gestión de campos agrícolas con un sistema de apertura y cierre automatizado de techos como protección frente a granizo. La aplicación incluye un dashboard interactivo, visualización de estados en tiempo real e interfaz responsive adaptable tanto a dispositivos móviles como a escritorio.

## Requisitos

Para ejecutar el proyecto es necesario tener instalado Python 3.9 o superior y pip. Se recomienda también tener Git instalado para clonar el repositorio.

## Instalación

Primero, clona el repositorio en tu equipo utilizando el siguiente comando:

```bash
git clone https://github.com/tuusuario/detector-granizo.git
cd detector-granizo
```

## Requisitos

Para ejecutar el proyecto es necesario tener instalado Python 3.9 o superior y pip. Se recomienda también tener Git instalado para clonar el repositorio.

## Instalación

Primero, clona el repositorio en tu equipo utilizando el siguiente comando:

```bash
git clone https://github.com/HugoReyIn/DetectorGranizo.git
cd DetectorGranizo
```
Si no utilizas Git, puedes descargar el proyecto manualmente y acceder a la carpeta raíz desde la terminal.

Una vez dentro del proyecto, crea un entorno virtual ejecutando:

```bash
python -m venv venv
```

Después, activa el entorno virtual. En Windows:
```bash
venv\Scripts\activate
```

En Mac o Linux:
```bash
source venv/bin/activate
```

Cuando el entorno esté activado verás el prefijo ```(venv)``` en la terminal.

Con el entorno activo, instala las dependencias definidas en el archivo ```requirements.txt``` mediante:

```bash
pip install -r requirements.txt
```

## Ejecución en localhost
Para iniciar la aplicación en un servidor local utilizando Uvicorn ejecuta:

```bash
uvicorn Main:app --reload
```
Donde ```Main``` es el nombre del archivo principal (Main.py) y ```app``` es la instancia de FastAPI.

Una vez iniciado el servidor, abre tu navegador y accede a la siguiente dirección:

```cpp
http://127.0.0.1:8000
```

El parámetro ```--reload``` permite que el servidor se reinicie automáticamente al detectar cambios en el código durante el desarrollo.

Si deseas ejecutar la aplicación en modo producción, puedes iniciar el servidor sin el parámetro ```--reload```:

```bash
uvicorn Main:app
```

## Finalizar entorno virtual

Cuando termines de trabajar en el proyecto puedes desactivar el entorno virtual ejecutando:
```bash
deactivate
```