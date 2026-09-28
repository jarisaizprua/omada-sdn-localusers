# 📶 Omada WiFi User Portal

Portal web en **Python + Streamlit** para administrar **usuarios locales de
WiFi (hotspot local users)** en uno o varios *sites* de un controlador
**TP-Link Omada SDN**, a través de su **Open API** (modo de autenticación
**Authorization Code**).

Pensado para ser **reutilizable en cualquier proyecto Omada**: toda la
configuración específica de la instalación vive en variables de entorno, y
el cliente de la API (`omada_client/`) es un paquete independiente que
puedes copiar a otro proyecto sin cambios.

---

## ✨ Funcionalidades

- **Login de administrador** con usuario/contraseña (hash `bcrypt`) +
  **verificación en dos pasos (MFA/TOTP)** compatible con Google
  Authenticator, Microsoft Authenticator, Authy, 1Password, etc. El
  enrolamiento se hace escaneando un **código QR** en el primer inicio de
  sesión.
- **Listado de sitios (sites)** disponibles en el controlador.
- **Gestión de usuarios locales de WiFi**: crear, editar y eliminar,
  aplicando la operación a **uno o varios sitios a la vez**.
- **Registro de auditoría** (quién hizo qué, cuándo, en qué sitio y con qué
  resultado) persistido en base de datos.
- **Roles**: `superadmin` (gestiona administradores del portal y ve la
  auditoría) y `operator` (gestiona usuarios de WiFi).
- Base de datos local en **DuckDB** (cero configuración, un solo archivo).

---

## 🏗️ Arquitectura

```
omada-portal/
├── app.py                      # Enrutador: login + MFA + navegación (st.navigation) + logo
├── config.py                   # Configuración vía variables de entorno (.env)
├── assets/
│   └── logo.svg                # Logo mostrado en la barra lateral (st.logo)
├── pages/
│   ├── 1_Sitios.py             # Listado de sites del controlador
│   ├── 2_Usuarios.py           # CRUD de usuarios locales de WiFi (multi-sitio)
│   └── 3_Administracion.py     # Gestión de admins del portal + auditoría (superadmin)
├── omada_client/                # Cliente Omada Open API — REUTILIZABLE en otros proyectos
│   ├── auth.py                  # Flujo OAuth2 Authorization Code
│   ├── client.py                 # Cliente HTTP genérico (/openapi/v1/{omadacId}/...)
│   ├── users.py                   # CRUD de usuarios locales (hotspot)
│   ├── token_store.py              # Persistencia de tokens en disco
│   └── exceptions.py
├── auth/                         # Autenticación y autorización del PORTAL (no de Omada)
│   ├── admin_store.py             # Repositorio de administradores (DuckDB)
│   ├── audit.py                    # Registro de auditoría (DuckDB)
│   ├── security.py                  # Hash de contraseñas (bcrypt)
│   ├── totp.py                       # MFA: secretos TOTP, QR, verificación
│   └── session_guard.py               # Protección de páginas de Streamlit
├── db/
│   └── database.py               # Conexión DuckDB (singleton) + esquema
├── services/
│   └── omada_service.py          # Fábrica cacheada del cliente Omada (st.cache_resource)
├── scripts/
│   ├── create_first_admin.py     # Crea el primer administrador
│   ├── reset_admin_password.py   # Resetea la contraseña de un administrador
│   ├── reset_admin_mfa.py        # Resetea el MFA de un administrador
│   └── test_omada_connection.py  # Diagnostica la conexión con Omada paso a paso
├── tests/
│   └── test_users_payload.py
├── data/                          # Base de datos DuckDB + cache de tokens (gitignored)
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── .gitignore
```

### Dos identidades distintas — no las confundas

| | ¿Quién es? | ¿Dónde se guarda? |
|---|---|---|
| **Administrador del portal** | Persona que entra a esta app web (tú, tu equipo) | Tabla `admins` en DuckDB, con contraseña + MFA |
| **Cuenta de servicio Omada** | Usuario del controlador Omada usado internamente por el backend para hablar con la Open API | `.env` (`OMADA_CONTROLLER_USERNAME` / `OMADA_CONTROLLER_PASSWORD`) |

---

## 🔐 Cómo funciona la autenticación con Omada (Authorization Code)

El modo *Authorization Code* del Omada Open API **no es un redirect OAuth
interactivo por navegador**: se resuelve con 3 llamadas encadenadas usando
las credenciales de un usuario del controlador (documentado en la guía
oficial, https://omada-northbound-docs.tplinkcloud.com/):

1. `POST /openapi/authorize/login` — con `client_id` + `omadac_id` en la
   query y `{username, password}` en el body → devuelve `csrfToken` y
   `sessionId`.
2. `POST /openapi/authorize/code` — con esos valores en cabeceras
   (`Csrf-Token`, `Cookie`) → devuelve el `authorization code`.
3. `POST /openapi/authorize/token` — con `client_id` + `client_secret` →
   devuelve `accessToken` (válido ~2h) y `refreshToken` (válido ~14 días).

El `OmadaAuthenticator` (`omada_client/auth.py`) hace esto automáticamente,
cachea el token en `data/.omada_token_cache.json` y lo renueva solo (primero
intenta con el `refreshToken`; si ya expiró, repite el flujo completo). El
resto de la aplicación nunca llama a estos endpoints directamente.

---

## 🚀 Puesta en marcha

### 1. Crear la aplicación en el controlador Omada

En el controlador: **Global View > Settings > Platform Integration > Open
API > Add New App**

- **Access mode:** `Authorization Code`
- **Redirect URL:** no se usa en este flujo; pon cualquier valor válido
  (ej. `http://localhost`)
- El controlador te mostrará 5 datos. Mapéalos así en tu `.env`:

  | Campo en el controlador | Variable en `.env` |
  |---|---|
  | Interface Access Address | `OMADA_BASE_URL` |
  | Omada ID | `OMADA_OMADAC_ID` |
  | Client ID | `OMADA_CLIENT_ID` |
  | Client Secret | `OMADA_CLIENT_SECRET` |
  | Oauth Login Page Address | `OMADA_OAUTH_LOGIN_PAGE_ADDRESS` *(opcional, solo informativo — no se usa en este flujo, es la URL de login por navegador de un redirect OAuth clásico)* |

- Crea (o reutiliza) un **usuario del controlador** dedicado, con permisos
  de vista sobre *Sites* y de modificación sobre *Hotspot / Usuarios
  Locales*. No uses el súper-admin del controlador para esto.

### 2. Clonar y configurar

```bash
git clone <tu-fork-de-este-repo>
cd omada-portal

pip install -r requirements.txt

cp .env.example .env
# Edita .env con tus datos del paso 1 (y genera un APP_SECRET_KEY con
# `python -c "import secrets; print(secrets.token_hex(32))"` o similar)
```

> **Entorno virtual (opcional).** Los comandos de arriba instalan las
> dependencias en tu Python global. Si prefieres aislarlas por proyecto:
> ```bash
> python -m venv .venv
> source .venv/bin/activate        # En Windows: .venv\Scripts\activate
> pip install -r requirements.txt
> ```
> `.venv/` ya está en `.gitignore`, así que nunca se sube al repositorio
> elijas la opción que elijas.

### 3. Crear el primer administrador del portal

```bash
python scripts/create_first_admin.py
```

Este primer usuario se crea automáticamente con rol `superadmin`. La
verificación en dos pasos (QR) se configura la primera vez que inicie
sesión en el portal.

### 3.5. (Recomendado) Verificar la conexión con Omada antes de abrir el portal

```bash
python scripts/test_omada_connection.py
```

Ejecuta cada paso del flujo *Authorization Code* por separado (login →
authorization code → access token → primera llamada a `/sites`) y, si algo
falla, imprime en qué paso exacto ocurrió y las causas más comunes según el
`errorCode` devuelto — por ejemplo, `errorCode=-30109` ("Invalid username or
password") casi siempre es: una contraseña con `#`/espacios sin comillas en
el `.env`, un espacio invisible pegado desde Windows, o estar usando el
TP-Link ID (cuenta cloud) en vez de un usuario **local** del controlador.

### 4. Ejecutar

```bash
streamlit run app.py
```

Abre `http://localhost:8501`, inicia sesión y escanea el QR con tu app de
autenticación preferida.

### Otros scripts útiles (`scripts/`)

| Script | Para qué sirve |
|---|---|
| `create_first_admin.py` | Crea el primer administrador (o adicionales) sin pasar por la web |
| `test_omada_connection.py` | Diagnostica paso a paso la conexión con el controlador Omada |
| `reset_admin_password.py` | Resetea la contraseña de un administrador existente (ej. si la olvidó). No toca su MFA. |
| `reset_admin_mfa.py` | Resetea el MFA de un administrador (ej. si perdió el teléfono). No toca su contraseña. |

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 📈 Notas

- El **límite de tasa** del controlador Omada (típicamente ~10
  solicitudes/segundo) se respeta con un pequeño *throttling* en
  `OmadaClient` (`OMADA_MIN_REQUEST_INTERVAL`).
- Rota el `Client Secret` de la app Omada y las contraseñas de la cuenta de
  servicio periódicamente; si alguna vez se filtran, revócalas de
  inmediato desde el controlador.
- El límite de intentos de login (`MAX_LOGIN_ATTEMPTS`) es solo por sesión
  de navegador; para un uso más expuesto considera añadir throttling a
  nivel de red (fail2ban, firewall, etc.) contra fuerza bruta.
- El paquete `omada_client/` no depende de Streamlit ni de DuckDB: puedes
  copiarlo a un script de automatización, un bot, otra app web, etc.
- Si más adelante quieres desplegarlo fuera de tu máquina (un servidor,
  Docker, Streamlit Cloud...), avísame y retomamos esa parte — por ahora
  el proyecto queda enfocado en correr como app local.

---

## 🗺️ Ideas para extender

- Exportar/import masivo de usuarios locales vía CSV/Excel.
- Notificaciones (email/SMS) al crear un usuario con contraseña temporal.
- Vincular la expiración de usuarios a un cron/job que los desactive
  automáticamente.
- Sincronizar con un directorio externo (LDAP/AD) para el login del portal.

