import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

st.set_page_config(
    page_title="Dashboard Produção & Vendas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CONFIG ──────────────────────────────────────────────────────────────────
SHEET_ID = "1kuSDOqybbwOrxr3zHSYBCSpQ17Rj3H-ZEcsnNllahVA"
MESES = {
    "JAN 26": "JAN%2026",
    "FEV 26": "FEV%2026",
    "MARC 26": "MARC%2026",
    "ABR 26": "ABR%2026",
}
ORDEM_MESES = list(MESES.keys())
DESTINOS_VENDA = ["ESTOQUE", "PRODUÇÃO", "VENDA", "PRODUCAO"]

PALETA = px.colors.qualitative.Set2
PALETA2 = px.colors.qualitative.Pastel

# ── CARREGAMENTO DE DADOS ────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sheet(sheet_name: str, sheet_encoded: str) -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={sheet_encoded}"
    )
    try:
        df = pd.read_csv(url, header=0, dtype=str)
    except Exception as e:
        st.warning(f"Erro ao carregar {sheet_name}: {e}")
        return pd.DataFrame()

    if df.empty or len(df.columns) < 10:
        return pd.DataFrame()

    # Seleciona só as 14 primeiras colunas úteis
    df = df.iloc[:, :14].copy()
    df.columns = [
        "DATA", "PLATAFORMA", "DESTINO", "QNT", "KIT_UND",
        "TIPO", "POL", "PUFF", "NAMO", "BANQUE",
        "TOTAL", "MODELO", "TECIDO", "COR",
    ]

    df["MES"] = sheet_name

    # Datas
    df["DATA"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")

    # Numéricos
    for col in ["QNT", "POL", "PUFF", "NAMO", "BANQUE", "TOTAL"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "."), errors="coerce"
        )

    # Strings — uppercase e sem espaço
    str_cols = ["PLATAFORMA", "DESTINO", "KIT_UND", "TIPO", "MODELO", "TECIDO", "COR"]
    for col in str_cols:
        df[col] = df[col].fillna("").str.strip().str.upper()

    # Separa linhas com dois modelos (ex: "ROMA, ITALIA" → duas linhas: ROMA e ITALIA)
    linhas_extras = []
    idx_remover = []
    for i, row in df[df["MODELO"].str.contains(",", na=False)].iterrows():
        modelos = [m.strip() for m in row["MODELO"].split(",")]
        for modelo in modelos:
            nova = row.copy()
            nova["MODELO"] = modelo
            linhas_extras.append(nova)
        idx_remover.append(i)
    if idx_remover:
        df = df.drop(index=idx_remover)
        df = pd.concat([df, pd.DataFrame(linhas_extras)], ignore_index=True)

    # Normaliza variação de acentuação em PRODUÇÃO
    df["DESTINO"] = df["DESTINO"].str.replace("PRODUCAO", "PRODUÇÃO")

    # Remove linhas sem data ou plataforma
    df = df.dropna(subset=["DATA"])
    df = df[df["PLATAFORMA"].notna() & (df["PLATAFORMA"] != "") & (df["PLATAFORMA"] != "PLATAFORMA")]

    return df


@st.cache_data(ttl=300)
def load_all() -> pd.DataFrame:
    dfs = [load_sheet(n, e) for n, e in MESES.items()]
    dfs = [d for d in dfs if not d.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Produção & Vendas")
    st.markdown("---")

    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.subheader("Filtros globais")

    meses_sel = st.multiselect(
        "Meses:", ORDEM_MESES, default=ORDEM_MESES
    )

    incluir_assis = st.checkbox("Incluir ASSIS nas análises", value=False)

    st.markdown("---")
    st.caption("Atualização automática: 5 min")
    st.caption(f"Carregado: {datetime.now().strftime('%d/%m %H:%M')}")


# ── CARGA ────────────────────────────────────────────────────────────────────
with st.spinner("Carregando dados..."):
    df_raw = load_all()

if df_raw.empty:
    st.error("Não foi possível carregar os dados. Verifique a planilha.")
    st.stop()

# Aplica filtro de meses
df_raw = df_raw[df_raw["MES"].isin(meses_sel)] if meses_sel else df_raw

# df_v = todas as vendas (excluindo ASSIS se não marcado)
if incluir_assis:
    df_v = df_raw.copy()
else:
    df_v = df_raw[df_raw["DESTINO"] != "ASSIS"].copy()

if df_v.empty:
    st.warning("Nenhum dado nos meses selecionados.")
    st.stop()

# Filtro de intervalo de datas (após carregar dados para usar min/max reais)
data_min = df_v["DATA"].min().date()
data_max = df_v["DATA"].max().date()

with st.sidebar:
    st.markdown("---")
    st.subheader("Intervalo de datas")
    data_inicio = st.date_input(
        "De:", value=data_min, min_value=data_min, max_value=data_max,
        format="DD/MM/YYYY",
    )
    data_fim = st.date_input(
        "Até:", value=data_max, min_value=data_min, max_value=data_max,
        format="DD/MM/YYYY",
    )

if data_inicio > data_fim:
    st.sidebar.error("Data inicial não pode ser maior que a data final.")
    st.stop()

df_v = df_v[
    (df_v["DATA"].dt.date >= data_inicio) &
    (df_v["DATA"].dt.date <= data_fim)
].copy()

if df_v.empty:
    st.warning("Nenhum dado no intervalo de datas selecionado.")
    st.stop()

df_v["DIA"] = df_v["DATA"].dt.date
df_v["MES_NUM"] = df_v["DATA"].dt.month
df_v["MES_CAT"] = pd.Categorical(df_v["MES"], categories=ORDEM_MESES, ordered=True)

df_prod_est = df_v[df_v["DESTINO"].isin(["ESTOQUE", "PRODUÇÃO"])]
df_prod = df_v[df_v["DESTINO"] == "PRODUÇÃO"]
df_est = df_v[df_v["DESTINO"] == "ESTOQUE"]
df_kits = df_v[df_v["KIT_UND"] == "KIT"]
df_unds = df_v[df_v["KIT_UND"] == "UNIDADE"]


# ── HELPERS ──────────────────────────────────────────────────────────────────
def fmt(n):
    return f"{int(n):,}".replace(",", ".")


def pct(a, b):
    return f"{a / b * 100:.1f}%" if b else "0%"


def bar(df_in, x, y, title, color=None, orientation="v", top=None, color_seq=None):
    dff = df_in.copy()
    if top:
        dff = dff.nlargest(top, y)
    fig = px.bar(
        dff, x=x, y=y, title=title,
        color=color,
        color_discrete_sequence=color_seq or PALETA,
        orientation=orientation,
        text_auto=True,
    )
    fig.update_layout(showlegend=bool(color), height=400, title_font_size=14)
    fig.update_traces(textposition="outside")
    return fig


def pie(labels, values, title):
    fig = px.pie(
        names=labels, values=values, title=title,
        color_discrete_sequence=PALETA, hole=0.4,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=400, title_font_size=14)
    return fig


def heat(df_in, x, y, z, title):
    pivot = df_in.pivot_table(index=y, columns=x, values=z, aggfunc="sum", fill_value=0)
    fig = px.imshow(
        pivot, title=title, aspect="auto",
        color_continuous_scale="Blues", text_auto=True,
    )
    fig.update_layout(height=max(300, len(pivot) * 30 + 100), title_font_size=14)
    return fig


# ── ABAS ─────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📌 Resumo Geral",
    "📅 Vendas por Data",
    "🛒 Vendas por Plataforma",
    "🏭 Produção vs Estoque",
    "📦 Kit vs Unidade",
    "🪑 Tipo de Produto",
    "🎨 Modelo / Tecido / Cor",
    "🏆 Ranking de Combinações",
    "📈 Curva ABC",
])


# ════════════════════════════════════════════════════════════════════════════
# ABA 1 — RESUMO GERAL
# ════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.header("📌 Resumo Geral")

    total_pecas = int(df_v["TOTAL"].sum())
    total_pedidos = len(df_v)
    total_kits = len(df_kits)
    total_unds = len(df_unds)
    pct_kit = total_kits / total_pedidos * 100 if total_pedidos else 0
    pct_und = total_unds / total_pedidos * 100 if total_pedidos else 0

    vendas_dia = df_v.groupby("DIA")["TOTAL"].sum()
    media_diaria = vendas_dia.mean() if len(vendas_dia) else 0
    maior_dia_val = vendas_dia.max() if len(vendas_dia) else 0
    maior_dia_data = vendas_dia.idxmax() if len(vendas_dia) else "-"

    modelo_top = (
        df_v.groupby("MODELO")["TOTAL"].sum().idxmax()
        if df_v["MODELO"].notna().any() else "-"
    )
    cor_top = (
        df_v.groupby("COR")["TOTAL"].sum().idxmax()
        if df_v["COR"].notna().any() else "-"
    )
    plat_top = (
        df_v.groupby("PLATAFORMA")["TOTAL"].sum().idxmax()
        if df_v["PLATAFORMA"].notna().any() else "-"
    )

    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    c7, c8, c9 = st.columns(3)

    c1.metric("📦 Total de peças", fmt(total_pecas))
    c2.metric("📋 Total de pedidos", fmt(total_pedidos))
    c3.metric("🧩 Kits vendidos", fmt(total_kits))
    c4.metric("🔷 Unidades vendidas", fmt(total_unds))
    c5.metric("📊 % Kit vs Unidade", f"{pct_kit:.1f}% / {pct_und:.1f}%")
    c6.metric("📐 Média diária de peças", f"{media_diaria:.1f}")
    c7.metric("🏆 Maior dia", f"{fmt(maior_dia_val)} peças ({maior_dia_data})")
    c8.metric("⭐ Modelo mais vendido", modelo_top)
    c9.metric("🎨 Cor mais vendida", cor_top)

    st.metric("🛒 Plataforma com maior volume", plat_top)

    st.markdown("---")
    st.subheader("Visão por mês")

    mes_resumo = (
        df_v.groupby("MES_CAT", observed=True)
        .agg(Pedidos=("TOTAL", "count"), Pecas=("TOTAL", "sum"))
        .reset_index()
        .rename(columns={"MES_CAT": "Mês"})
    )

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(
            mes_resumo, x="Mês", y="Pecas", title="Peças por mês",
            text_auto=True, color_discrete_sequence=PALETA,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        fig = px.bar(
            mes_resumo, x="Mês", y="Pedidos", title="Pedidos por mês",
            text_auto=True, color_discrete_sequence=PALETA2,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# ABA 2 — VENDAS POR DATA
# ════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.header("📅 Vendas por Data")

    # Vendas por dia
    por_dia = df_v.groupby("DIA")["TOTAL"].sum().reset_index()
    por_dia.columns = ["Data", "Peças"]
    por_dia["Data"] = pd.to_datetime(por_dia["Data"])
    por_dia = por_dia.sort_values("Data")

    # Média móvel 7 dias
    por_dia["Média Móvel 7d"] = por_dia["Peças"].rolling(7, min_periods=1).mean()

    fig_dia = go.Figure()
    fig_dia.add_trace(go.Bar(
        x=por_dia["Data"], y=por_dia["Peças"],
        name="Peças/dia", marker_color="#5cb8e4", opacity=0.7,
    ))
    fig_dia.add_trace(go.Scatter(
        x=por_dia["Data"], y=por_dia["Média Móvel 7d"],
        name="Média móvel 7d", line=dict(color="#e45c5c", width=2),
    ))
    fig_dia.update_layout(
        title="Quantidade vendida por dia + Média Móvel 7 dias",
        xaxis_title="Data", yaxis_title="Peças",
        height=400,
    )
    st.plotly_chart(fig_dia, use_container_width=True)

    # Vendas por mês
    st.subheader("Vendas por mês")
    por_mes = (
        df_v.groupby("MES_CAT", observed=True)["TOTAL"]
        .sum()
        .reset_index()
    )
    por_mes.columns = ["Mês", "Peças"]
    fig_mes = px.bar(
        por_mes, x="Mês", y="Peças", title="Total de peças por mês",
        color_discrete_sequence=PALETA, text_auto=True,
    )
    fig_mes.update_traces(textposition="outside")
    st.plotly_chart(fig_mes, use_container_width=True)

    # Comparativo mês a mês
    st.subheader("Comparativo mês a mês")
    if len(meses_sel) >= 2:
        pares = [
            (ORDEM_MESES[i], ORDEM_MESES[i + 1])
            for i in range(len(ORDEM_MESES) - 1)
            if ORDEM_MESES[i] in meses_sel and ORDEM_MESES[i + 1] in meses_sel
        ]
        cols_comp = st.columns(len(pares)) if pares else [st]
        totais_mes = df_v.groupby("MES")["TOTAL"].sum().to_dict()

        for idx, (m1, m2) in enumerate(pares):
            v1 = totais_mes.get(m1, 0)
            v2 = totais_mes.get(m2, 0)
            delta = ((v2 - v1) / v1 * 100) if v1 else 0
            with cols_comp[idx]:
                st.metric(
                    f"{m1} vs {m2}",
                    f"{fmt(v2)} peças",
                    f"{delta:+.1f}% vs {m1}",
                )

    # Evolução diária por mês (agrupada por dia do mês)
    st.subheader("Evolução diária — todos os meses")
    df_v2 = df_v.copy()
    df_v2["DIA_MES"] = df_v2["DATA"].dt.day
    evo = (
        df_v2.groupby(["MES_CAT", "DIA_MES"], observed=True)["TOTAL"]
        .sum()
        .reset_index()
    )
    evo.columns = ["Mês", "Dia do mês", "Peças"]
    fig_evo = px.line(
        evo, x="Dia do mês", y="Peças", color="Mês",
        title="Evolução diária por mês",
        markers=True,
        color_discrete_sequence=PALETA,
    )
    st.plotly_chart(fig_evo, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# ABA 3 — VENDAS POR PLATAFORMA
# ════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.header("🛒 Vendas por Plataforma")

    por_plat = (
        df_v.groupby("PLATAFORMA")["TOTAL"]
        .sum()
        .reset_index()
        .sort_values("TOTAL", ascending=False)
    )
    por_plat.columns = ["Plataforma", "Peças"]

    col1, col2 = st.columns(2)
    with col1:
        fig = bar(por_plat, "Plataforma", "Peças", "Volume por plataforma")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = pie(por_plat["Plataforma"], por_plat["Peças"], "Participação por plataforma")
        st.plotly_chart(fig, use_container_width=True)

    # Kit vs Unidade por plataforma
    st.subheader("Kit vs Unidade por plataforma")
    plat_kit_und = (
        df_v.groupby(["PLATAFORMA", "KIT_UND"])["TOTAL"]
        .sum()
        .reset_index()
    )
    plat_kit_und.columns = ["Plataforma", "Tipo", "Peças"]
    fig = px.bar(
        plat_kit_und, x="Plataforma", y="Peças", color="Tipo",
        title="Kit vs Unidade por plataforma",
        barmode="group", color_discrete_sequence=PALETA,
        text_auto=True,
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        # Plataforma que mais vende kit
        top_plat_kit = (
            df_kits.groupby("PLATAFORMA")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        top_plat_kit.columns = ["Plataforma", "Peças"]
        st.plotly_chart(
            bar(top_plat_kit, "Plataforma", "Peças", "Plataformas — mais kits"),
            use_container_width=True,
        )
    with col4:
        # Plataforma que mais vende unidade
        top_plat_und = (
            df_unds.groupby("PLATAFORMA")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        top_plat_und.columns = ["Plataforma", "Peças"]
        st.plotly_chart(
            bar(top_plat_und, "Plataforma", "Peças", "Plataformas — mais unidades", color_seq=PALETA2),
            use_container_width=True,
        )

    # Heatmap plataforma x modelo
    st.subheader("Heatmap — Plataforma × Modelo")
    if df_v["MODELO"].any() and df_v["PLATAFORMA"].any():
        fig_heat = heat(
            df_v[df_v["MODELO"] != ""],
            x="PLATAFORMA", y="MODELO", z="TOTAL",
            title="Volume: Plataforma × Modelo",
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # Plataforma mais vende por cor
    st.subheader("Plataforma × Cor (Top 15 cores)")
    df_plat_cor = df_v[df_v["COR"] != ""]
    top_cores = df_plat_cor.groupby("COR")["TOTAL"].sum().nlargest(15).index
    df_plat_cor = df_plat_cor[df_plat_cor["COR"].isin(top_cores)]
    if not df_plat_cor.empty:
        fig = heat(df_plat_cor, x="PLATAFORMA", y="COR", z="TOTAL",
                   title="Volume: Plataforma × Cor")
        st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# ABA 4 — PRODUÇÃO vs ESTOQUE
# ════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.header("🏭 Produção vs Estoque")

    total_prod = int(df_prod["TOTAL"].sum())
    total_est = int(df_est["TOTAL"].sum())
    total_pe = total_prod + total_est
    ped_prod = len(df_prod)
    ped_est = len(df_est)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏭 Total produzido (peças)", fmt(total_prod))
    c2.metric("📦 Total do estoque (peças)", fmt(total_est))
    c3.metric("🏭 % Produção", pct(total_prod, total_pe))
    c4.metric("📦 % Estoque", pct(total_est, total_pe))

    col1, col2 = st.columns(2)
    with col1:
        fig = pie(["PRODUÇÃO", "ESTOQUE"], [total_prod, total_est],
                  "Produção vs Estoque (peças)")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        # Evolução produção vs estoque por mês
        pe_mes = (
            df_v[df_v["DESTINO"].isin(["PRODUÇÃO", "ESTOQUE"])]
            .groupby(["MES_CAT", "DESTINO"], observed=True)["TOTAL"]
            .sum()
            .reset_index()
        )
        pe_mes.columns = ["Mês", "Destino", "Peças"]
        fig = px.bar(
            pe_mes, x="Mês", y="Peças", color="Destino",
            title="Produção vs Estoque por mês",
            barmode="group", color_discrete_sequence=["#e45c5c", "#5cb8e4"],
            text_auto=True,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Modelos com maior demanda de produção")
    col3, col4 = st.columns(2)
    with col3:
        mod_prod = (
            df_prod.groupby("MODELO")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        mod_prod.columns = ["Modelo", "Peças"]
        st.plotly_chart(
            bar(mod_prod, "Modelo", "Peças", "Modelos mais produzidos", top=10),
            use_container_width=True,
        )
    with col4:
        mod_est = (
            df_est.groupby("MODELO")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        mod_est.columns = ["Modelo", "Peças"]
        st.plotly_chart(
            bar(mod_est, "Modelo", "Peças", "Modelos mais retirados do estoque",
                top=10, color_seq=PALETA2),
            use_container_width=True,
        )

    st.subheader("Cores com maior demanda de produção")
    col5, col6 = st.columns(2)
    with col5:
        cor_prod = (
            df_prod[df_prod["COR"] != ""].groupby("COR")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        cor_prod.columns = ["Cor", "Peças"]
        st.plotly_chart(
            bar(cor_prod, "Cor", "Peças", "Cores mais produzidas", top=15),
            use_container_width=True,
        )
    with col6:
        cor_est = (
            df_est[df_est["COR"] != ""].groupby("COR")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        cor_est.columns = ["Cor", "Peças"]
        st.plotly_chart(
            bar(cor_est, "Cor", "Peças", "Cores mais retiradas do estoque",
                top=15, color_seq=PALETA2),
            use_container_width=True,
        )

    # Modelos com maior dependência de produção (% produção no total)
    st.subheader("Dependência de produção por modelo")
    dep = (
        df_prod_est[df_prod_est["MODELO"] != ""]
        .groupby(["MODELO", "DESTINO"])["TOTAL"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col_dep in ["PRODUÇÃO", "ESTOQUE"]:
        if col_dep not in dep.columns:
            dep[col_dep] = 0
    dep["Total"] = dep["PRODUÇÃO"] + dep["ESTOQUE"]
    dep["% Produção"] = dep["PRODUÇÃO"] / dep["Total"] * 100
    dep = dep.sort_values("% Produção", ascending=False)

    fig_dep = px.bar(
        dep, x="MODELO", y="% Produção",
        title="% de produção por modelo (vs estoque)",
        color_discrete_sequence=["#e45c5c"], text_auto=".1f",
    )
    fig_dep.update_layout(yaxis_title="%", height=400)
    fig_dep.add_hline(y=50, line_dash="dash", line_color="gray",
                      annotation_text="50%")
    st.plotly_chart(fig_dep, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# ABA 5 — KIT vs UNIDADE
# ════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.header("📦 Kit vs Unidade")

    c1, c2, c3 = st.columns(3)
    c1.metric("🧩 Kits", fmt(total_kits))
    c2.metric("🔷 Unidades", fmt(total_unds))
    c3.metric("📊 % Kit / Unidade",
              f"{pct_kit:.1f}% / {pct_und:.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        fig = pie(["KIT", "UNIDADE"], [total_kits, total_unds],
                  "Kit vs Unidade (pedidos)")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = pie(
            ["KIT", "UNIDADE"],
            [int(df_kits["TOTAL"].sum()), int(df_unds["TOTAL"].sum())],
            "Kit vs Unidade (peças)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Modelos mais vendidos em Kit vs Unidade")
    mod_kit_und = (
        df_v[df_v["MODELO"] != ""]
        .groupby(["MODELO", "KIT_UND"])["TOTAL"]
        .sum()
        .reset_index()
    )
    mod_kit_und.columns = ["Modelo", "Tipo", "Peças"]
    fig = px.bar(
        mod_kit_und, x="Modelo", y="Peças", color="Tipo",
        title="Modelos mais vendidos — Kit vs Unidade",
        barmode="group", color_discrete_sequence=PALETA, text_auto=True,
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        cor_kit = (
            df_kits[df_kits["COR"] != ""].groupby("COR")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        cor_kit.columns = ["Cor", "Peças"]
        st.plotly_chart(
            bar(cor_kit, "Cor", "Peças", "Cores mais vendidas em Kit", top=15),
            use_container_width=True,
        )
    with col4:
        plat_kit = (
            df_kits.groupby("PLATAFORMA")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        plat_kit.columns = ["Plataforma", "Peças"]
        st.plotly_chart(
            bar(plat_kit, "Plataforma", "Peças",
                "Plataformas que mais vendem Kit", color_seq=PALETA2),
            use_container_width=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# ABA 6 — TIPO DE PRODUTO
# ════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.header("🪑 Tipo de Produto")

    df_tipo = df_v[df_v["TIPO"] != ""]

    por_tipo = (
        df_tipo.groupby("TIPO")["TOTAL"]
        .sum()
        .reset_index()
        .sort_values("TOTAL", ascending=False)
    )
    por_tipo.columns = ["Tipo", "Peças"]

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            bar(por_tipo, "Tipo", "Peças", "Volume por tipo de produto"),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            pie(por_tipo["Tipo"], por_tipo["Peças"], "Participação por tipo"),
            use_container_width=True,
        )

    st.subheader("Tipo por plataforma")
    tipo_plat = (
        df_tipo.groupby(["PLATAFORMA", "TIPO"])["TOTAL"]
        .sum()
        .reset_index()
    )
    tipo_plat.columns = ["Plataforma", "Tipo", "Peças"]
    fig = px.bar(
        tipo_plat, x="Plataforma", y="Peças", color="Tipo",
        title="Tipo de produto por plataforma",
        barmode="stack", color_discrete_sequence=PALETA,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tipo por mês")
    tipo_mes = (
        df_tipo.groupby(["MES_CAT", "TIPO"], observed=True)["TOTAL"]
        .sum()
        .reset_index()
    )
    tipo_mes.columns = ["Mês", "Tipo", "Peças"]
    fig = px.bar(
        tipo_mes, x="Mês", y="Peças", color="Tipo",
        title="Tipo de produto por mês",
        barmode="group", color_discrete_sequence=PALETA, text_auto=True,
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        tipo_prod = (
            df_prod[df_prod["TIPO"] != ""].groupby("TIPO")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        tipo_prod.columns = ["Tipo", "Peças"]
        st.plotly_chart(
            bar(tipo_prod, "Tipo", "Peças", "Tipos mais produzidos"),
            use_container_width=True,
        )
    with col4:
        tipo_est = (
            df_est[df_est["TIPO"] != ""].groupby("TIPO")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        tipo_est.columns = ["Tipo", "Peças"]
        st.plotly_chart(
            bar(tipo_est, "Tipo", "Peças", "Tipos mais retirados do estoque",
                color_seq=PALETA2),
            use_container_width=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# ABA 7 — MODELO / TECIDO / COR
# ════════════════════════════════════════════════════════════════════════════
with tabs[6]:
    st.header("🎨 Modelo / Tecido / Cor")

    # ── Modelos ──────────────────────────────────────────────────────────────
    st.subheader("Ranking de modelos")
    df_mod = df_v[df_v["MODELO"] != ""]

    mod_rank = (
        df_mod.groupby("MODELO")["TOTAL"]
        .sum()
        .reset_index()
        .sort_values("TOTAL", ascending=True)
    )
    mod_rank.columns = ["Modelo", "Peças"]
    fig = px.bar(
        mod_rank, x="Peças", y="Modelo", orientation="h",
        title="Ranking de modelos (total de peças)",
        color_discrete_sequence=PALETA, text_auto=True,
    )
    fig.update_layout(height=max(300, len(mod_rank) * 35 + 80))
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        mod_mes = (
            df_mod.groupby(["MES_CAT", "MODELO"], observed=True)["TOTAL"]
            .sum()
            .reset_index()
        )
        mod_mes.columns = ["Mês", "Modelo", "Peças"]
        fig = px.bar(
            mod_mes, x="Mês", y="Peças", color="Modelo",
            title="Modelo por mês", barmode="stack",
            color_discrete_sequence=PALETA,
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        mod_plat = (
            df_mod.groupby(["PLATAFORMA", "MODELO"])["TOTAL"]
            .sum()
            .reset_index()
        )
        mod_plat.columns = ["Plataforma", "Modelo", "Peças"]
        fig = px.bar(
            mod_plat, x="Plataforma", y="Peças", color="Modelo",
            title="Modelo por plataforma", barmode="stack",
            color_discrete_sequence=PALETA,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Tecidos ───────────────────────────────────────────────────────────────
    st.subheader("Análise por tecido")
    df_tec = df_v[df_v["TECIDO"] != ""]

    col3, col4 = st.columns(2)
    with col3:
        tec_rank = (
            df_tec.groupby("TECIDO")["TOTAL"].sum()
            .reset_index().sort_values("TOTAL", ascending=False)
        )
        tec_rank.columns = ["Tecido", "Peças"]
        st.plotly_chart(
            bar(tec_rank, "Tecido", "Peças", "Volume por tecido"),
            use_container_width=True,
        )
    with col4:
        tec_plat = (
            df_tec.groupby(["PLATAFORMA", "TECIDO"])["TOTAL"].sum()
            .reset_index()
        )
        tec_plat.columns = ["Plataforma", "Tecido", "Peças"]
        fig = px.bar(
            tec_plat, x="Plataforma", y="Peças", color="Tecido",
            title="Tecido por plataforma", barmode="stack",
            color_discrete_sequence=PALETA,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Cores ────────────────────────────────────────────────────────────────
    st.subheader("Análise por cor")
    df_cor = df_v[df_v["COR"] != ""]

    cor_rank = (
        df_cor.groupby("COR")["TOTAL"].sum()
        .reset_index().sort_values("TOTAL", ascending=True)
    )
    cor_rank.columns = ["Cor", "Peças"]
    fig = px.bar(
        cor_rank, x="Peças", y="Cor", orientation="h",
        title="Ranking de cores",
        color_discrete_sequence=PALETA, text_auto=True,
    )
    fig.update_layout(height=max(300, len(cor_rank) * 25 + 80))
    st.plotly_chart(fig, use_container_width=True)

    col5, col6 = st.columns(2)
    with col5:
        cor_mes = (
            df_cor.groupby(["MES_CAT", "COR"], observed=True)["TOTAL"].sum()
            .reset_index()
        )
        cor_mes.columns = ["Mês", "Cor", "Peças"]
        fig = px.bar(
            cor_mes, x="Mês", y="Peças", color="Cor",
            title="Cor por mês", barmode="stack",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col6:
        cor_plat = (
            df_cor.groupby(["PLATAFORMA", "COR"])["TOTAL"].sum()
            .reset_index()
        )
        cor_plat.columns = ["Plataforma", "Cor", "Peças"]
        fig = px.bar(
            cor_plat, x="Plataforma", y="Peças", color="Cor",
            title="Cor por plataforma", barmode="stack",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Heatmaps ──────────────────────────────────────────────────────────────
    st.subheader("Heatmaps")
    col7, col8 = st.columns(2)
    with col7:
        df_mc = df_v[(df_v["MODELO"] != "") & (df_v["COR"] != "")]
        if not df_mc.empty:
            fig = heat(df_mc, x="COR", y="MODELO", z="TOTAL",
                       title="Modelo × Cor")
            st.plotly_chart(fig, use_container_width=True)
    with col8:
        df_tc = df_v[(df_v["TECIDO"] != "") & (df_v["COR"] != "")]
        if not df_tc.empty:
            fig = heat(df_tc, x="COR", y="TECIDO", z="TOTAL",
                       title="Tecido × Cor")
            st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# ABA 8 — RANKING DE COMBINAÇÕES
# ════════════════════════════════════════════════════════════════════════════
with tabs[7]:
    st.header("🏆 Ranking de Combinações")

    comb_cols = ["TIPO", "MODELO", "TECIDO", "COR"]
    df_comb = df_v[df_v["MODELO"] != ""].copy()

    # Top 10 geral
    top10_geral = (
        df_comb.groupby(comb_cols)["TOTAL"]
        .sum()
        .reset_index()
        .sort_values("TOTAL", ascending=False)
        .head(10)
    )
    top10_geral.columns = ["Tipo", "Modelo", "Tecido", "Cor", "Peças"]
    st.subheader("Top 10 combinações geral")
    st.dataframe(top10_geral, use_container_width=True, hide_index=True)

    # Top 10 por plataforma
    st.subheader("Top 10 combinações por plataforma")
    plat_opts = sorted(df_comb["PLATAFORMA"].unique())
    plat_sel = st.selectbox("Selecione a plataforma:", plat_opts)
    top10_plat = (
        df_comb[df_comb["PLATAFORMA"] == plat_sel]
        .groupby(comb_cols)["TOTAL"]
        .sum()
        .reset_index()
        .sort_values("TOTAL", ascending=False)
        .head(10)
    )
    top10_plat.columns = ["Tipo", "Modelo", "Tecido", "Cor", "Peças"]
    st.dataframe(top10_plat, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        # Top 10 que mais vão para produção
        top10_prod = (
            df_prod[df_prod["MODELO"] != ""]
            .groupby(comb_cols)["TOTAL"]
            .sum()
            .reset_index()
            .sort_values("TOTAL", ascending=False)
            .head(10)
        )
        if not top10_prod.empty:
            top10_prod.columns = ["Tipo", "Modelo", "Tecido", "Cor", "Peças"]
            st.subheader("Top 10 — mais produzidas")
            st.dataframe(top10_prod, use_container_width=True, hide_index=True)

    with col2:
        # Top 10 que mais saem de estoque
        top10_est = (
            df_est[df_est["MODELO"] != ""]
            .groupby(comb_cols)["TOTAL"]
            .sum()
            .reset_index()
            .sort_values("TOTAL", ascending=False)
            .head(10)
        )
        if not top10_est.empty:
            top10_est.columns = ["Tipo", "Modelo", "Tecido", "Cor", "Peças"]
            st.subheader("Top 10 — mais retiradas do estoque")
            st.dataframe(top10_est, use_container_width=True, hide_index=True)

    # Produtos com baixo giro
    st.subheader("Produtos com baixo giro (≤ 2 peças no período)")
    baixo_giro = (
        df_comb.groupby(comb_cols)["TOTAL"]
        .sum()
        .reset_index()
        .sort_values("TOTAL")
    )
    baixo_giro.columns = ["Tipo", "Modelo", "Tecido", "Cor", "Peças"]
    st.dataframe(
        baixo_giro[baixo_giro["Peças"] <= 2],
        use_container_width=True,
        hide_index=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# ABA 9 — CURVA ABC
# ════════════════════════════════════════════════════════════════════════════
with tabs[8]:
    st.header("📈 Curva ABC por Volume")

    st.info(
        "**A** = 80% do volume total | **B** = 15% | **C** = 5%\n\n"
        "Produtos da curva A são os mais críticos para o negócio."
    )

    granularidade = st.selectbox(
        "Analisar por:",
        ["Modelo", "Cor", "Tecido", "Combinação (Modelo+Tecido+Cor)"],
    )

    if granularidade == "Modelo":
        group_cols = ["TIPO", "MODELO"]
        label_col = "Modelo"
    elif granularidade == "Cor":
        group_cols = ["TIPO", "COR"]
        label_col = "Cor"
    elif granularidade == "Tecido":
        group_cols = ["TIPO", "TECIDO"]
        label_col = "Tecido"
    else:
        group_cols = ["TIPO", "MODELO", "TECIDO", "COR"]
        label_col = "Combinação"

    mask = pd.Series(True, index=df_v.index)
    for c in group_cols:
        mask = mask & (df_v[c] != "")
    df_abc = df_v[mask].copy()
    abc = (
        df_abc.groupby(group_cols)["TOTAL"]
        .sum()
        .reset_index()
        .sort_values("TOTAL", ascending=False)
    )

    if granularidade == "Combinação (Modelo+Tecido+Cor)":
        abc[label_col] = abc["TIPO"] + " | " + abc["MODELO"] + " | " + abc["TECIDO"] + " | " + abc["COR"]
        abc = abc[[label_col, "TOTAL"]].reset_index(drop=True)
    else:
        abc = abc.rename(columns={"TIPO": "Tipo", group_cols[-1]: label_col})

    total_vol = abc["TOTAL"].sum()
    abc["% Volume"] = abc["TOTAL"] / total_vol * 100
    abc["Acumulado %"] = abc["% Volume"].cumsum()

    def classifica(acum):
        if acum <= 80:
            return "A"
        elif acum <= 95:
            return "B"
        return "C"

    abc["Curva"] = abc["Acumulado %"].apply(classifica)

    col_a = abc[abc["Curva"] == "A"]
    col_b = abc[abc["Curva"] == "B"]
    col_c = abc[abc["Curva"] == "C"]

    m1, m2, m3 = st.columns(3)
    m1.metric("🟢 Curva A", f"{len(col_a)} itens ({pct(len(col_a), len(abc))})")
    m2.metric("🟡 Curva B", f"{len(col_b)} itens ({pct(len(col_b), len(abc))})")
    m3.metric("🔴 Curva C", f"{len(col_c)} itens ({pct(len(col_c), len(abc))})")

    # Gráfico ABC
    cores_abc = {"A": "#2ecc71", "B": "#f39c12", "C": "#e74c3c"}
    fig = px.bar(
        abc.head(50), x=label_col, y="TOTAL", color="Curva",
        title=f"Curva ABC — {granularidade} (Top 50)",
        color_discrete_map=cores_abc,
        text_auto=True,
    )
    fig.update_layout(height=450, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    # Tabela completa
    st.subheader("Tabela completa da curva ABC")
    abc_display = abc.copy()
    abc_display["TOTAL"] = abc_display["TOTAL"].astype(int)
    abc_display["% Volume"] = abc_display["% Volume"].round(2)
    abc_display["Acumulado %"] = abc_display["Acumulado %"].round(2)
    abc_display.index = range(1, len(abc_display) + 1)
    st.dataframe(
        abc_display.style.apply(
            lambda row: [
                f"background-color: {'#d5f5e3' if row['Curva'] == 'A' else '#fef9e7' if row['Curva'] == 'B' else '#fdecea'}"
            ] * len(row),
            axis=1,
        ),
        use_container_width=True,
    )
