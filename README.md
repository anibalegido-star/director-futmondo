# Director Deportivo · Futmondo

App móvil de tu director deportivo de Futmondo. Cada mañana y cada tarde, GitHub
descarga los datos de tu liga, los analiza y publica la app. Tú la abres en el
móvil.

**El Director solo recomienda.** Las pujas y las cláusulas las haces tú en Futmondo.

## Cómo protege tus datos

- Este repositorio es **público**; es la única forma gratuita de usar GitHub Pages. Por eso no guarda ningún dato de tu liga sin cifrar.
- Tu token de Futmondo está en los **secretos** del repositorio, que nadie puede leer.
- Los datos de la liga se publican **cifrados** (AES-256), y el histórico también.
- La clave para descifrarlos solo está en tus secretos y en tu enlace personal, detrás del `#`. Los navegadores nunca envían esa parte al servidor.
- Sin tu enlace, la web solo muestra un campo para pegar la clave.

## Instalación (una sola vez, unos 10 minutos)

Abre el archivo `app_movil_CLAVE.txt` que tienes en `Escritorio\futmondo`. Contiene tu clave y tu enlace.

1. **Crea el repositorio.** En GitHub pulsa **New repository**:
   - Nombre: `director-futmondo`
   - Visibilidad: **Public**
   - Sin README.
2. **Sube los archivos.** Arrastra el contenido de `Escritorio\futmondo\app_movil` a *uploading an existing file* y pulsa **Commit changes**. Si conectas GitHub a Claude, puede subirlo él.
3. **Crea la tarea automática.** En el repositorio pulsa *Add file → Create new file*:
   - Como nombre escribe exactamente `.github/workflows/director.yml`.
   - Pega dentro el contenido del archivo `director.yml` de esta carpeta.
   - Pulsa **Commit changes**.
   - Después borra del repositorio la copia `director.yml` que quedó en la raíz.
4. **Añade los secretos.** Ve a *Settings → Secrets and variables → Actions → New repository secret* y crea uno por cada valor:

   | Nombre | Valor |
   |---|---|
   | `FUTMONDO_TOKEN` | el de tu `.env` (`Escritorio\futmondo\.env`) |
   | `FUTMONDO_USER_ID` | el de tu `.env` |
   | `FUTMONDO_CHAMPIONSHIP_ID` | el de tu `.env` |
   | `FUTMONDO_USERTEAM_ID` | el de tu `.env` |
   | `DIRECTOR_KEY` | la clave de `app_movil_CLAVE.txt` |
   | `ANTHROPIC_API_KEY` | *(opcional)*: si la pones, el parte lo redacta Claude |

5. **Activa la web.** En *Settings → Pages → Build and deployment → Source* elige **GitHub Actions**.
6. **Primera ejecución.** En la pestaña *Actions*, abre *Director Deportivo* y pulsa **Run workflow**. Tarda unos 3 minutos.
7. **En el móvil:**
   - Abre tu enlace personal (el de `app_movil_CLAVE.txt`).
   - Añade la app a la pantalla de inicio: en iPhone, *Compartir → Añadir a pantalla de inicio*; en Android, *menú → Instalar app*.
   - La primera vez que la abras desde el icono, pega el enlace otra vez.
   - Pon tu saldo tocando la tarjeta **Saldo**.

## Uso

- Se actualiza sola dos veces al día: hacia las 06:17, justo después de que se renueve el mercado, y hacia las 18:17.
- El botón ↻ de la app abre la página de GitHub desde la que lanzas una actualización (**Run workflow**).
- Tu saldo se guarda solo en el móvil. Sirve para ordenar y filtrar lo que puedes pagar.

## Avisos

- GitHub desactiva las tareas programadas de un repositorio público si pasan 60 días sin cambios en él. Te avisa por correo y se reactivan con un clic en *Actions*.
- Si un día la descarga falla (por ejemplo, porque Futmondo bloquee los servidores de GitHub), la app sigue mostrando los últimos datos buenos.
- El histórico se guarda en la caché de GitHub y en una copia cifrada que se conserva 30 días. Si se pierde, se vuelve a partir de la semilla (`seed/director.db.enc`).

## Para desarrolladores

```
pip install -r requirements.txt
python run.py                                    # análisis + panel local (usa .env)
DIRECTOR_KEY=... python run.py --exportar public/data.enc
python -m fm.crypto nueva-clave | cifrar | descifrar
```
