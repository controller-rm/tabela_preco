import streamlit as st
import pandas as pd
import numpy as np
import csv
from io import BytesIO
from formulaBC_projetada import executar_formula
from tabela_preco import executar_tabela_preco


st.set_page_config(
    page_title="Matriz Risco x Demanda",
    page_icon="📊",
    layout="wide"
)


# =========================================================
# FUNÇÕES UTILITÁRIAS
# =========================================================
def normalize_number(x):
    if pd.isna(x):
        return 0.0

    x = str(x).strip().replace('"', "").replace("'", "")

    if x == "":
        return 0.0

    if "," in x and "." in x:
        x = x.replace(".", "").replace(",", ".")
    elif "," in x:
        x = x.replace(",", ".")
    else:
        try:
            return float(x)
        except Exception:
            pass

    try:
        return float(x)
    except Exception:
        return 0.0


def detectar_separador(uploaded_file, encoding="latin-1"):
    sample = uploaded_file.read().decode(encoding, errors="ignore")
    uploaded_file.seek(0)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
        return dialect.delimiter
    except Exception:
        return ";"


def formatar_numero_br(valor, casas=4):
    if pd.isna(valor):
        return ""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def to_excel_bytes(dfs_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for nome_aba, df in dfs_dict.items():
            df.to_excel(writer, sheet_name=nome_aba[:31], index=False)
    output.seek(0)
    return output.getvalue()


# =========================================================
# PREPARAR BASE
# =========================================================
def preparar_dataframe_necessidade(df):
    df.columns = [str(c).strip().lower() for c in df.columns]

    mapa = {
        "produto": "codigo_produto_material",
        "codigo_produto_material": "codigo_produto_material",
        "quantidade_total": "quantidade_total",
        "quantidade_estoque": "quantidade_estoque",
        "consumo_medio_diario": "consumo_medio_diario",
        "lead_time": "lead_time",
        "estoque_seguranca": "estoque_seguranca",
        "descricao_produto": "descricao_produto",
        "tipo_material": "tipo_material",
        "ult_custo_medio": "ult_custo_medio",
        "valor_reposicao_4": "valor_reposicao_4",
    }

    df = df.rename(columns={c: mapa[c] for c in df.columns if c in mapa})

    obrigatorias = [
        "codigo_produto_material",
        "quantidade_total",
        "quantidade_estoque",
        "consumo_medio_diario",
        "lead_time",
        "estoque_seguranca",
    ]

    for col in obrigatorias:
        if col not in df.columns:
            df[col] = 0

    opcionais_texto = ["descricao_produto", "tipo_material"]
    for col in opcionais_texto:
        if col not in df.columns:
            df[col] = ""

    opcionais_numericas = ["ult_custo_medio", "valor_reposicao_4"]
    for col in opcionais_numericas:
        if col not in df.columns:
            df[col] = 0

    for col in df.columns:
        if col not in ["codigo_produto_material", "descricao_produto", "tipo_material"]:
            df[col] = df[col].apply(normalize_number)

    df["codigo_produto_material"] = df["codigo_produto_material"].astype(str).str.strip()

    df["quantidade_total_a_comprar"] = (
        df["quantidade_total"] + df["estoque_seguranca"] - df["quantidade_estoque"]
    ).clip(lower=0)

    df["estoque_final_projetado"] = (
        df["quantidade_estoque"] + df["quantidade_total_a_comprar"] - df["quantidade_total"]
    )

    return df


# =========================================================
# MATRIZ
# =========================================================
def calcular_matriz(df, q_demanda=0.75):
    df = df.copy()

    df["dias_cobertura_atual"] = np.where(
        df["consumo_medio_diario"] > 0,
        df["quantidade_estoque"] / df["consumo_medio_diario"],
        999999
    )

    df["dias_cobertura_final"] = np.where(
        df["consumo_medio_diario"] > 0,
        df["estoque_final_projetado"] / df["consumo_medio_diario"],
        999999
    )

    corte = df["consumo_medio_diario"].quantile(q_demanda)

    df["demanda_classificacao"] = np.where(
        df["consumo_medio_diario"] >= corte,
        "Alta",
        "Baixa"
    )

    df["flag_cobertura_ruim"] = (df["dias_cobertura_atual"] < df["lead_time"]).astype(int)
    df["flag_estoque_abaixo_seg"] = (df["quantidade_estoque"] < df["estoque_seguranca"]).astype(int)
    df["flag_final_abaixo_seg"] = (df["estoque_final_projetado"] < df["estoque_seguranca"]).astype(int)
    df["flag_compra_alta"] = (df["quantidade_total_a_comprar"] > df["quantidade_estoque"]).astype(int)

    df["score_risco"] = (
        df["flag_cobertura_ruim"] * 35 +
        df["flag_estoque_abaixo_seg"] * 25 +
        df["flag_final_abaixo_seg"] * 25 +
        df["flag_compra_alta"] * 15
    )

    df["risco_classificacao"] = np.where(
        df["score_risco"] >= 50,
        "Alto",
        "Baixo"
    )

    def definir_quadrante(row):
        if row["risco_classificacao"] == "Alto" and row["demanda_classificacao"] == "Alta":
            return "Alto risco + Alta demanda"
        elif row["risco_classificacao"] == "Alto" and row["demanda_classificacao"] == "Baixa":
            return "Alto risco + Baixa demanda"
        elif row["risco_classificacao"] == "Baixo" and row["demanda_classificacao"] == "Alta":
            return "Baixo risco + Alta demanda"
        else:
            return "Baixo risco + Baixa demanda"

    df["quadrante"] = df.apply(definir_quadrante, axis=1)

    mapa_acao = {
        "Alto risco + Alta demanda": "Aumentar preço / restringir venda / priorizar clientes",
        "Alto risco + Baixa demanda": "Segurar estoque / evitar queima / comprar com cautela",
        "Baixo risco + Alta demanda": "Manter preço / ganhar mercado / monitorar cobertura",
        "Baixo risco + Baixa demanda": "Queima seletiva / promoção / reduzir exposição",
    }
    df["acao_recomendada"] = df["quadrante"].map(mapa_acao)

    def semaforo(score):
        if score >= 80:
            return "🔴 Crítico"
        elif score >= 50:
            return "🟠 Alto"
        elif score >= 25:
            return "🟡 Atenção"
        return "🟢 Baixo"

    df["semaforo_risco"] = df["score_risco"].apply(semaforo)

    return df, corte


def resumo_quadrantes(df_matriz):
    ordem = [
        "Alto risco + Alta demanda",
        "Alto risco + Baixa demanda",
        "Baixo risco + Alta demanda",
        "Baixo risco + Baixa demanda",
    ]

    resumo = (
        df_matriz.groupby("quadrante", as_index=False)
        .agg(
            itens=("codigo_produto_material", "count"),
            estoque=("quantidade_estoque", "sum"),
            necessidade=("quantidade_total", "sum"),
            a_comprar=("quantidade_total_a_comprar", "sum"),
            consumo_dia=("consumo_medio_diario", "sum"),
        )
    )

    custo_map = (
        df_matriz.groupby("quadrante")
        .apply(lambda g: (g["quantidade_total_a_comprar"] * g["ult_custo_medio"]).sum(), include_groups=False)
        .to_dict()
    )

    resumo["custo_total_estimado"] = resumo["quadrante"].map(custo_map)
    resumo["ordem"] = resumo["quadrante"].map({q: i for i, q in enumerate(ordem)})
    resumo = resumo.sort_values("ordem").drop(columns="ordem")

    return resumo


# =========================================================
# ESTADO
# =========================================================
if "matriz_df" not in st.session_state:
    st.session_state["matriz_df"] = None

if "base_df" not in st.session_state:
    st.session_state["base_df"] = None

if "resumo_df" not in st.session_state:
    st.session_state["resumo_df"] = None

if "top_criticos_df" not in st.session_state:
    st.session_state["top_criticos_df"] = None

if "corte_demanda" not in st.session_state:
    st.session_state["corte_demanda"] = None


# =========================================================
# LAYOUT
# =========================================================
st.title("📊 MATRIZ: RISCO x DEMANDA")
st.markdown("""
Upload do arquivo **Necessidade_Compra** para geração da matriz.

---
""")

percentil = st.sidebar.slider(
    "Percentil demanda",
    min_value=0.50,
    max_value=0.95,
    value=0.75,
    step=0.05
)

tab1, tab2,tab3 = st.tabs(["📊 Matriz", "📦 Fórmula BC", "💲Tabela de Preco"])


# =========================================================
# TAB 1 - MATRIZ
# =========================================================
with tab1:
    arquivo = st.file_uploader(
        "📄 Upload Necessidade_Compra",
        type=["csv"],
        key="arquivo_necessidade_compra"
    )

    if arquivo is not None:
        sep = detectar_separador(arquivo)

        df = pd.read_csv(
            arquivo,
            sep=sep,
            engine="python",
            encoding="utf-8-sig",
            decimal=","
        )

        df = preparar_dataframe_necessidade(df)
        st.session_state["base_df"] = df.copy()

        st.success("Arquivo carregado com sucesso.")
        st.dataframe(df.head(20), use_container_width=True, height=300)

        if st.button("🚀 Gerar Matriz", use_container_width=True, key="btn_gerar_matriz"):
            matriz, corte = calcular_matriz(df, percentil)
            resumo = resumo_quadrantes(matriz)

            colunas_exibir = [
                "codigo_produto_material",
                "descricao_produto",
                "tipo_material",
                "quantidade_estoque",
                "quantidade_total",
                "consumo_medio_diario",
                "lead_time",
                "estoque_seguranca",
                "quantidade_total_a_comprar",
                "estoque_final_projetado",
                "dias_cobertura_atual",
                "dias_cobertura_final",
                "score_risco",
                "semaforo_risco",
                "risco_classificacao",
                "demanda_classificacao",
                "quadrante",
                "acao_recomendada",
                "ult_custo_medio",
            ]
            colunas_exibir = [c for c in colunas_exibir if c in matriz.columns]

            top_criticos = matriz.sort_values(
                by=["score_risco", "consumo_medio_diario"],
                ascending=[False, False]
            ).head(30)

            st.session_state["matriz_df"] = matriz.copy()
            st.session_state["resumo_df"] = resumo.copy()
            st.session_state["top_criticos_df"] = top_criticos.copy()
            st.session_state["corte_demanda"] = corte

    matriz = st.session_state["matriz_df"]
    resumo = st.session_state["resumo_df"]
    top_criticos = st.session_state["top_criticos_df"]
    corte = st.session_state["corte_demanda"]

    if matriz is not None:
        total_itens = len(matriz)
        total_alto_risco = (matriz["risco_classificacao"] == "Alto").sum()
        total_alta_demanda = (matriz["demanda_classificacao"] == "Alta").sum()
        total_criticos = (matriz["quadrante"] == "Alto risco + Alta demanda").sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Itens analisados", f"{total_itens}")
        col2.metric("Itens de alto risco", f"{total_alto_risco}")
        col3.metric("Itens de alta demanda", f"{total_alta_demanda}")
        col4.metric("Pior quadrante", f"{total_criticos}")

        st.markdown("### 📌 Resumo da Matriz")
        st.dataframe(resumo, use_container_width=True, height=250)

        st.markdown("### 📊 Distribuição por Quadrante")
        dist = (
            matriz["quadrante"]
            .value_counts()
            .rename_axis("quadrante")
            .reset_index(name="itens")
        )
        st.bar_chart(dist.set_index("quadrante"))

        st.markdown("### 📋 Base completa classificada")
        colunas_exibir = [
            "codigo_produto_material",
            "descricao_produto",
            "tipo_material",
            "quantidade_estoque",
            "quantidade_total",
            "consumo_medio_diario",
            "lead_time",
            "estoque_seguranca",
            "quantidade_total_a_comprar",
            "estoque_final_projetado",
            "dias_cobertura_atual",
            "dias_cobertura_final",
            "score_risco",
            "semaforo_risco",
            "risco_classificacao",
            "demanda_classificacao",
            "quadrante",
            "acao_recomendada",
            "ult_custo_medio",
        ]
        colunas_exibir = [c for c in colunas_exibir if c in matriz.columns]

        st.dataframe(
            matriz[colunas_exibir].sort_values(
                by=["score_risco", "consumo_medio_diario"],
                ascending=[False, False]
            ),
            use_container_width=True,
            height=600
        )

        st.markdown("### 🔥 Top itens críticos")
        st.dataframe(
            top_criticos[colunas_exibir],
            use_container_width=True,
            height=350
        )

        st.markdown("### 🧠 Regras aplicadas")
        st.info(
            f"""
**Demanda Alta**: consumo_medio_diario >= percentil {int(percentil * 100)}  
**Corte encontrado**: {formatar_numero_br(corte, 4)}

**Risco Alto**: score >= 50  
Score composto por:
- cobertura atual < lead time = 35 pts
- estoque atual < estoque segurança = 25 pts
- estoque final projetado < estoque segurança = 25 pts
- quantidade a comprar > estoque atual = 15 pts
"""
        )

        csv_matriz = matriz.to_csv(
            index=False,
            sep=";",
            decimal=",",
            encoding="utf-8-sig"
        ).encode("utf-8-sig")

        csv_resumo = resumo.to_csv(
            index=False,
            sep=";",
            decimal=",",
            encoding="utf-8-sig"
        ).encode("utf-8-sig")

        excel_bytes = to_excel_bytes({
            "matriz_completa": matriz,
            "resumo_quadrantes": resumo,
            "top_criticos": top_criticos
        })

        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "⬇️ Baixar CSV da Matriz",
                data=csv_matriz,
                file_name="matriz_risco_demanda.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_csv_matriz"
            )
        with c2:
            st.download_button(
                "⬇️ Baixar CSV do Resumo",
                data=csv_resumo,
                file_name="resumo_matriz_risco_demanda.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_csv_resumo"
            )
        with c3:
            st.download_button(
                "⬇️ Baixar Excel completo",
                data=excel_bytes,
                file_name="matriz_risco_demanda.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_excel_matriz"
            )
    else:
        st.info("Envie o CSV e gere a matriz para visualizar os resultados.")


# =========================================================
# TAB 2 - FÓRMULA BC
# =========================================================
with tab2:
    df_formula = st.session_state["matriz_df"]

    # Esta chamada só funciona corretamente se formulaBC_projetada.py
    # NÃO tiver st.title(), st.file_uploader(), etc. fora da função.
    executar_formula(df_base=df_formula)

# =========================================================
# TAB 3 - TABELA PRECO
# =========================================================

with tab3:
    executar_tabela_preco()