from __future__ import annotations

import streamlit as st

_CSS = """
<style>
/* Tipografía y layout general */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif;
}
.main .block-container {
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 1150px;
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
    box-shadow: 0 6px 16px rgba(10, 102, 194, 0.18);
}

/* Formularios como "tarjetas" */
div[data-testid="stForm"] {
    border: 1px solid #E4E9F0;
    border-radius: 14px;
    padding: 1.5rem 1.5rem 0.5rem 1.5rem;
    background: #FBFCFE;
}

/* Pestañas */
button[data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.95rem;
}

/* Métricas como tarjetas */
div[data-testid="stMetric"] {
    background: #F2F6FA;
    border: 1px solid #E4E9F0;
    border-radius: 12px;
    padding: 0.9rem 1.1rem;
}

/* Tablas con esquinas redondeadas */
div[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #E4E9F0;
}

/* Expanders */
div[data-testid="stExpander"] {
    border-radius: 10px;
    border: 1px solid #E4E9F0;
}

hr { margin: 1.6rem 0; }

/* Badge de estado (usado en la lista de usuarios) */
.omp-badge {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 700;
}
.omp-badge-ok { background: #E3F6E8; color: #1D8A3C; }
.omp-badge-warn { background: #FFF3D6; color: #A66A00; }
.omp-badge-danger { background: #FDE7E7; color: #C0392B; }
.omp-badge-muted { background: #EDEFF2; color: #5B6B7B; }
</style>
"""


def apply_theme() -> None:
    """Inyecta estilos CSS compartidos para una apariencia más profesional
    y consistente en todas las páginas del portal. Llamar una vez por
    página, justo después de st.set_page_config()."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Encabezado de página consistente: icono grande + título + subtítulo,
    en vez del st.title()/st.caption() plano por defecto."""
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.1rem;">
            <span style="font-size:2rem; line-height:1;">{icon}</span>
            <span style="font-size:1.9rem; font-weight:800; color:#1A2530;">{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f'<p style="color:#5B6B7B; margin-top:0.1rem; margin-bottom:1.3rem;">{subtitle}</p>',
            unsafe_allow_html=True,
        )
