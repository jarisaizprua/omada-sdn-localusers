from __future__ import annotations

import streamlit as st

_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
:root {
    --omp-primary: #2452FF;
    --omp-primary-dark: #1636B0;
    --omp-accent: #7C5CFC;
    --omp-bg: #F4F6FB;
    --omp-card: #FFFFFF;
    --omp-border: #E4E8F1;
    --omp-text: #1A2233;
    --omp-muted: #64748B;
    --omp-green: #16A34A;
    --omp-green-bg: #E7F8ED;
    --omp-amber: #B7791F;
    --omp-amber-bg: #FFF3D6;
    --omp-red: #DC2626;
    --omp-red-bg: #FDE8E8;
}

/* Tipografía */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
h1, h2, h3, .omp-heading {
    font-family: 'Poppins', 'Inter', sans-serif !important;
}

/* Fondo general con leve contraste para que las tarjetas blancas resalten */
[data-testid="stAppViewContainer"] {
    background: var(--omp-bg);
}
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1180px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #12173B;
}
[data-testid="stSidebar"] * {
    color: #E7EAF6 !important;
}
[data-testid="stSidebarNavLink"] {
    border-radius: 8px;
    margin: 2px 8px;
    font-weight: 600;
}
[data-testid="stSidebarNavLink"]:hover {
    background: rgba(124, 92, 252, 0.25);
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: linear-gradient(135deg, var(--omp-primary), var(--omp-accent));
}

/* Botones */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid transparent;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(36, 82, 255, 0.25);
}
button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--omp-primary), var(--omp-accent)) !important;
    border: none !important;
}

/* Formularios como "tarjetas" */
div[data-testid="stForm"] {
    border: 1px solid var(--omp-border);
    border-radius: 16px;
    padding: 1.6rem 1.6rem 0.6rem 1.6rem;
    background: var(--omp-card);
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 8px 24px -14px rgba(36, 82, 255, 0.18);
}

/* Contenedores con borde (tarjetas de navegación, agrupaciones) */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid var(--omp-border) !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 10px 26px -16px rgba(36, 82, 255, 0.2);
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(16, 24, 40, 0.06), 0 16px 32px -14px rgba(36, 82, 255, 0.28);
}

/* Pestañas */
button[data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.95rem;
}
[data-baseweb="tab-highlight"] {
    background: linear-gradient(135deg, var(--omp-primary), var(--omp-accent)) !important;
}

/* Métricas como tarjetas */
div[data-testid="stMetric"] {
    background: var(--omp-card);
    border: 1px solid var(--omp-border);
    border-radius: 14px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}

/* Tablas con esquinas redondeadas */
div[data-testid="stDataFrame"] {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid var(--omp-border);
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}

/* Expanders */
div[data-testid="stExpander"] {
    border-radius: 12px;
    border: 1px solid var(--omp-border);
}

hr { margin: 1.6rem 0; border-color: var(--omp-border); }

/* Badge de estado */
.omp-badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 700;
}
.omp-badge-ok { background: var(--omp-green-bg); color: var(--omp-green); }
.omp-badge-warn { background: var(--omp-amber-bg); color: var(--omp-amber); }
.omp-badge-danger { background: var(--omp-red-bg); color: var(--omp-red); }
.omp-badge-muted { background: #EDEFF2; color: var(--omp-muted); }

/* Encabezado de página */
.omp-header-wrap { margin-bottom: 1.4rem; }
.omp-header-row { display: flex; align-items: center; gap: 0.7rem; }
.omp-header-icon {
    font-size: 1.9rem;
    line-height: 1;
    width: 3rem; height: 3rem;
    display: flex; align-items: center; justify-content: center;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--omp-primary), var(--omp-accent));
}
.omp-header-title {
    font-size: 1.85rem;
    font-weight: 800;
    color: var(--omp-text);
    font-family: 'Poppins', sans-serif;
}
.omp-header-subtitle {
    color: var(--omp-muted);
    margin: 0.3rem 0 0 3.7rem;
    font-size: 0.98rem;
}
.omp-header-bar {
    height: 4px;
    width: 64px;
    margin: 0.7rem 0 0 3.7rem;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--omp-primary), var(--omp-accent));
}

/* Tarjetas de navegación en la portada */
.omp-nav-card-title { font-weight: 700; font-size: 1.05rem; color: var(--omp-text); }
.omp-nav-card-desc { color: var(--omp-muted); font-size: 0.88rem; margin-top: 0.2rem; }
.omp-nav-card-icon { font-size: 1.6rem; }
</style>
"""


def apply_theme() -> None:
    """Inyecta estilos CSS compartidos para una apariencia más profesional
    y consistente en todas las páginas del portal. Llamar una vez por
    página, justo después de st.set_page_config()."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Encabezado de página con icono en badge, título y barra de acento
    en degradé, en vez del st.title()/st.caption() plano por defecto."""
    subtitle_html = f'<p class="omp-header-subtitle">{subtitle}</p>' if subtitle else ""
    html = (
        '<div class="omp-header-wrap">'
        '<div class="omp-header-row">'
        f'<div class="omp-header-icon">{icon}</div>'
        f'<div class="omp-header-title">{title}</div>'
        "</div>"
        f"{subtitle_html}"
        '<div class="omp-header-bar"></div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def status_badge(text: str, kind: str = "muted") -> str:
    """Devuelve el HTML de un badge de color (ok/warn/danger/muted) para
    insertar con st.markdown(..., unsafe_allow_html=True)."""
    return f'<span class="omp-badge omp-badge-{kind}">{text}</span>'

