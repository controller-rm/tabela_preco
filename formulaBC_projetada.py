import pandas as pd
import streamlit as st
import os
import base64
import numpy as np
import mysql.connector
from dotenv import load_dotenv

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Projeto NC - Recalcular Custo Formulação", layout="wide")

MAPA_IMAGENS_GRUPO = {
    "Adex": "Controller_virtual-Adex.png",
    "Realfix": "Controller_virtual-Realfix.png",
    "DEFAULT": "Controller_virtual-PR.png"
}

def executar_formula(df_base=None):
    import streamlit as st

    st.title("📦 Fórmula BC Projetada")

    # Se quiser usar dados vindos da matriz
    if df_base is not None:
        st.success("Dados recebidos da Matriz Risco x Demanda")
        st.dataframe(df_base.head())

    # ==============================================================================
    # FUNÇÕES VISUAIS
    # ==============================================================================
    def obter_imagem_por_grupo(lk_grupo):
        return MAPA_IMAGENS_GRUPO.get(lk_grupo, MAPA_IMAGENS_GRUPO["DEFAULT"])


    def exibir_imagem_em_coluna(coluna, nome_arquivo, largura=200):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, nome_arquivo)

        if os.path.exists(logo_path):
            with coluna:
                st.image(logo_path, width=largura)
        else:
            st.warning(f"Imagem {nome_arquivo} não encontrada!")


    def get_base64_image(image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return encoded_string


    # ==============================================================================
    # FUNÇÕES AUXILIARES
    # ==============================================================================
    def normalizar_codigo(valor):
        if pd.isna(valor):
            return ""
        return str(valor).strip().upper()


    def to_float_br(valor):
        if pd.isna(valor):
            return 0.0

        if isinstance(valor, (int, float, np.integer, np.floating)):
            return float(valor)

        valor = str(valor).strip()

        if valor == "":
            return 0.0

        if "," in valor and "." in valor:
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", ".")

        try:
            return float(valor)
        except ValueError:
            return 0.0


    def formatar_decimal_br(valor, casas=4):
        if pd.isna(valor):
            return ""
        return f"{float(valor):.{casas}f}".replace(".", ",")


    def conectar_mysql():
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )


    def carregar_dados_mysql(query):
        conn = conectar_mysql()
        try:
            df = pd.read_sql(query, conn)
        finally:
            conn.close()
        return df


    def preparar_coluna_texto(df, coluna):
        if coluna not in df.columns:
            df[coluna] = ""
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()
        return df


    def preparar_coluna_num(df, coluna, default=0.0):
        if coluna not in df.columns:
            df[coluna] = default
        df[coluna] = df[coluna].apply(to_float_br)
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(default)
        return df


    def formatar_csv_brasileiro(df, colunas_numericas, casas=6):
        df_csv = df.copy()

        for col in colunas_numericas:
            if col in df_csv.columns:
                df_csv[col] = pd.to_numeric(df_csv[col], errors="coerce").fillna(0)
                df_csv[col] = df_csv[col].apply(
                    lambda x: f"{x:.{casas}f}".replace(".", ",")
                )

        return df_csv


    # ==============================================================================
    # CARREGAR VARIÁVEIS DE AMBIENTE
    # ==============================================================================
    load_dotenv()

    # ==============================================================================
    # CABEÇALHO / IDENTIDADE VISUAL
    # ==============================================================================
    try:
        df_grupos = pd.read_csv("Lk-grupo.csv", delimiter=";", encoding="utf-8")
        df_grupos.columns = [col.strip().upper().replace("-", "_") for col in df_grupos.columns]
        lista_grupos = df_grupos["LK_GRUPO"].dropna().unique().tolist()
    except Exception:
        lista_grupos = ["Adex", "Realfix"]

    lk_grupo_cliente = st.sidebar.selectbox(
        "Selecione o LK-GRUPO do cliente:",
        lista_grupos,
        key="lk_grupo_cliente"
    )

    texto_relatorio = st.sidebar.text_area(
        "Texto do Relatório:",
        "Esse programa lê a ESTRUTURA e PRODUTO, recalcula o custo da formulação, "
        "permite sobrescrever o vlrun_r de componentes MP e explodir todos os níveis "
        "da estrutura com os valores que compõem o custo."
    )

    nome_imagem = obter_imagem_por_grupo(lk_grupo_cliente)

    col1, col2, col3 = st.columns([1, 4, 1])
    exibir_imagem_em_coluna(col1, nome_imagem)
    exibir_imagem_em_coluna(col3, "Controller.png")

    with col2:
        st.title("Cálculo do Custo da Formulação com Explosão dos Níveis de Produção")

        with st.expander("❓ Informações do Programa"):
            st.info(
                """
                Regras desta versão:
                - Lê ESTRUTURA e PRODUTO do MySQL
                - Permite upload de uma lista manual contendo componente + vlrun_r
                - Se o componente for do tipo_material = MP e houver vlrun_r informado, usa esse valor no cálculo
                - Mantém a lógica original do custo_form
                - Identifica quais produtos tiveram alteração de custo_form após o recálculo
                - Permite informar um produto e extrair todos os níveis da estrutura de produção
                - Na explosão, exibe também os valores usados no cálculo do custo
                """
            )

        if os.path.exists("Auditor.png"):
            base64_image = get_base64_image("Auditor.png")
            st.markdown(
                f"""
                <style>
                .stApp {{
                    background: linear-gradient(rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.92)),
                                url('data:image/png;base64,{base64_image}') no-repeat center center fixed;
                    background-size: cover;
                }}
                </style>
                """,
                unsafe_allow_html=True
            )

    # ==============================================================================
    # LEITURA DO CSV DE REFORMULAÇÃO MANUAL
    # ==============================================================================
    st.subheader("📥 Lista manual para reformular vlrun_r dos componentes MP")

    uploaded_recalculo = st.file_uploader(
        "Faça upload do CSV com colunas 'componente' e 'vlrun_r'",
        type=["csv"],
        key="uploaded_recalculo"
    )

    df_recalculo = None

    if uploaded_recalculo is not None:
        try:
            df_recalculo = pd.read_csv(uploaded_recalculo, sep=";", encoding="latin1")

            colunas_necessarias = {"componente", "vlrun_r"}
            if not colunas_necessarias.issubset(df_recalculo.columns):
                st.error("O CSV deve conter as colunas: componente;vlrun_r")
                df_recalculo = None
            else:
                df_recalculo["componente"] = df_recalculo["componente"].apply(normalizar_codigo)
                df_recalculo["vlrun_r"] = df_recalculo["vlrun_r"].apply(to_float_br)
                df_recalculo = df_recalculo.drop_duplicates(subset=["componente"], keep="last")

                st.success("Lista manual carregada com sucesso.")
                st.dataframe(df_recalculo, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao ler CSV de recálculo: {e}")
            df_recalculo = None
    else:
        st.info("Nenhum arquivo manual enviado. O sistema usará somente os custos do banco.")

    # ==============================================================================
    # LEITURA DE CUSTO COMPLEMENTAR
    # ==============================================================================
    def carregar_custo_complementar():
        arquivo = "custo_complementar_resina.csv"

        if not os.path.exists(arquivo):
            return pd.DataFrame(columns=["produto", "custo_comp"])

        try:
            df = pd.read_csv(arquivo, delimiter=";", encoding="latin1")
            df.columns = df.columns.str.strip().str.lower()

            if "produto" not in df.columns or "custo_comp" not in df.columns:
                return pd.DataFrame(columns=["produto", "custo_comp"])

            df["produto"] = df["produto"].apply(normalizar_codigo)
            df["custo_comp"] = df["custo_comp"].apply(to_float_br)
            df = df[["produto", "custo_comp"]].drop_duplicates(subset=["produto"], keep="last")
            return df
        except Exception:
            return pd.DataFrame(columns=["produto", "custo_comp"])

    # ==============================================================================
    # CARREGAR BASE
    # ==============================================================================
    @st.cache_data(ttl=120, show_spinner=True)
    def carregar_dados_base():
        query_estrutura = "SELECT * FROM ESTRUTURA"
        query_produto = "SELECT * FROM PRODUTO"

        estrutura = carregar_dados_mysql(query_estrutura)
        produto = carregar_dados_mysql(query_produto)

        return estrutura, produto


    def montar_base_merged():
        estrutura, produto = carregar_dados_base()

        for col in ["produto", "componente"]:
            estrutura = preparar_coluna_texto(estrutura, col)

        for col in ["quantidade", "sequencia", "ult_custo_medio"]:
            estrutura = preparar_coluna_num(estrutura, col, 0.0)

        estrutura["produto"] = estrutura["produto"].apply(normalizar_codigo)
        estrutura["componente"] = estrutura["componente"].apply(normalizar_codigo)

        for col in ["codigo_produto_material", "descricao_produto", "tipo_material"]:
            produto = preparar_coluna_texto(produto, col)

        produto = preparar_coluna_num(produto, "valor_reposicao_4", 0.0)
        produto["codigo_produto_material"] = produto["codigo_produto_material"].apply(normalizar_codigo)

        colunas_produto = [
            "codigo_produto_material",
            "descricao_produto",
            "tipo_material",
            "valor_reposicao_4"
        ]

        merged_df = estrutura.merge(
            produto[colunas_produto],
            left_on="componente",
            right_on="codigo_produto_material",
            how="left"
        )

        descricao_pai = produto[["codigo_produto_material", "descricao_produto"]].drop_duplicates()
        descricao_pai = descricao_pai.rename(columns={
            "codigo_produto_material": "produto",
            "descricao_produto": "descricao_produto_pai"
        })

        merged_df = merged_df.merge(descricao_pai, on="produto", how="left")

        merged_df["descricao_produto"] = np.where(
            pd.to_numeric(merged_df["sequencia"], errors="coerce").fillna(0) == 0,
            merged_df["descricao_produto_pai"],
            merged_df["descricao_produto"]
        )

        merged_df["Chave"] = merged_df["produto"] + "-" + merged_df["componente"]

        merged_df = preparar_coluna_num(merged_df, "ult_custo_medio", 0.0)
        merged_df = preparar_coluna_num(merged_df, "valor_reposicao_4", 0.0)
        merged_df = preparar_coluna_texto(merged_df, "tipo_material")
        merged_df = preparar_coluna_num(merged_df, "quantidade", 0.0)
        merged_df = preparar_coluna_num(merged_df, "sequencia", 0.0)

        merged_df["produto"] = merged_df["produto"].apply(normalizar_codigo)
        merged_df["componente"] = merged_df["componente"].apply(normalizar_codigo)
        merged_df["tipo_material"] = merged_df["tipo_material"].apply(normalizar_codigo)

        return merged_df, produto

    # ==============================================================================
    # CÁLCULO HIERÁRQUICO - PRESERVANDO A LÓGICA ORIGINAL
    # ==============================================================================
    def recalcular_custos_hierarquicos(df_base, df_recalculo_manual=None):
        df = df_base.copy()

        df_custo_comp = carregar_custo_complementar()
        df = df.merge(df_custo_comp, on="produto", how="left")
        df["custo_comp"] = pd.to_numeric(df["custo_comp"], errors="coerce").fillna(0.0)

        if df_recalculo_manual is not None and not df_recalculo_manual.empty:
            df_aux = df_recalculo_manual.copy()
            df_aux["componente"] = df_aux["componente"].apply(normalizar_codigo)
            df_aux["vlrun_r_manual"] = df_aux["vlrun_r"].apply(to_float_br)
            df_aux = df_aux[["componente", "vlrun_r_manual"]].drop_duplicates(subset=["componente"], keep="last")
            df = df.merge(df_aux, on="componente", how="left")
        else:
            df["vlrun_r_manual"] = np.nan

        df["vlrun_r"] = np.where(
            (df["tipo_material"] == "MP") & (df["vlrun_r_manual"].notna()),
            df["vlrun_r_manual"],
            np.where(df["tipo_material"] != "FO", df["valor_reposicao_4"], 0.0)
        )

        df["vlrun_c"] = np.where(
            (df["tipo_material"] != "FO") & (df["vlrun_r"] == 0),
            df["ult_custo_medio"],
            0.0
        )

        # vlrun_m inicial
        df["vlrun_m"] = (df["vlrun_r"] + df["vlrun_c"]) * df["quantidade"]

        # vlrun_f hierárquico
        df["vlrun_f"] = 0.0

        for _ in range(10):
            vlrun_m_anterior = df["vlrun_m"].copy()
            vlrun_f_anterior = df["vlrun_f"].copy()

            soma_vlrun_m_por_produto = df.groupby("produto")["vlrun_m"].sum()

            mask_fo = df["tipo_material"] == "FO"
            df.loc[mask_fo, "vlrun_f"] = (
                df.loc[mask_fo, "componente"].map(soma_vlrun_m_por_produto).fillna(0.0) / 100.0
            )

            df["vlrun_m"] = np.where(
                df["custo_comp"] > 0,
                (df["vlrun_r"] + df["vlrun_c"] + df["vlrun_f"] + df["custo_comp"]) * df["quantidade"],
                (df["vlrun_r"] + df["vlrun_c"] + df["vlrun_f"]) * df["quantidade"]
            )

            variacao = (
                (df["vlrun_m"] - vlrun_m_anterior).abs().sum() +
                (df["vlrun_f"] - vlrun_f_anterior).abs().sum()
            )

            if variacao < 0.000001:
                break

        soma_custo_por_produto = df.groupby("produto")["vlrun_m"].sum()

        df["custo_form"] = df.apply(
            lambda row: soma_custo_por_produto.get(row["produto"], 0.0) + 0.01
            if row.get("sequencia", 1) == 0 else 0.0,
            axis=1
        )

        df["vlrun_kg"] = df["custo_form"] / 100.0

        df["Custo_Un"] = np.where(
            df["quantidade"] != 0,
            df["vlrun_m"] / df["quantidade"],
            0.0
        )

        df["origem_vlrun_r"] = np.where(
            (df["tipo_material"] == "MP") & (df["vlrun_r_manual"].notna()),
            "MANUAL",
            "BANCO"
        )

        return df

    # ==============================================================================
    # RASTREABILIDADE DAS ALTERAÇÕES NO CUSTO_FORM
    # ==============================================================================
    def adicionar_rastreabilidade_custo_form(df_resultado_banco, df_resultado_recalculado):
        """
        Compara o custo_form do cálculo original (sem manual) com o custo_form do cálculo recalculado
        e adiciona colunas de rastreabilidade sem alterar a lógica original do programa.
        """
        df_out = df_resultado_recalculado.copy()
        df_banco = df_resultado_banco.copy()

        # custo_form do banco por produto (apenas seq 0)
        base_banco = df_banco.loc[df_banco["sequencia"] == 0, ["produto", "custo_form"]].copy()
        base_banco = base_banco.rename(columns={"custo_form": "custo_form_banco"})
        base_banco = base_banco.drop_duplicates(subset=["produto"], keep="first")

        # custo_form recalculado por produto (apenas seq 0)
        base_recalc = df_out.loc[df_out["sequencia"] == 0, ["produto", "custo_form"]].copy()
        base_recalc = base_recalc.rename(columns={"custo_form": "custo_form_recalculado"})
        base_recalc = base_recalc.drop_duplicates(subset=["produto"], keep="first")

        comparativo = base_recalc.merge(base_banco, on="produto", how="left")

        comparativo["custo_form_banco"] = pd.to_numeric(
            comparativo["custo_form_banco"], errors="coerce"
        ).fillna(0.0)

        comparativo["custo_form_recalculado"] = pd.to_numeric(
            comparativo["custo_form_recalculado"], errors="coerce"
        ).fillna(0.0)

        comparativo["delta_custo_form"] = (
            comparativo["custo_form_recalculado"] - comparativo["custo_form_banco"]
        )

        comparativo["flag_custo_form_alterado"] = np.where(
            comparativo["delta_custo_form"].abs() > 0.000001,
            "SIM",
            "NAO"
        )

        comparativo["produto_custo_form_alterado"] = np.where(
            comparativo["flag_custo_form_alterado"] == "SIM",
            comparativo["produto"],
            ""
        )

        # traz o comparativo para todas as linhas do produto
        df_out = df_out.merge(
            comparativo[
                [
                    "produto",
                    "custo_form_banco",
                    "custo_form_recalculado",
                    "delta_custo_form",
                    "flag_custo_form_alterado",
                    "produto_custo_form_alterado"
                ]
            ],
            on="produto",
            how="left"
        )

        # garante consistência
        for col in ["custo_form_banco", "custo_form_recalculado", "delta_custo_form"]:
            df_out[col] = pd.to_numeric(df_out[col], errors="coerce").fillna(0.0)

        for col in ["flag_custo_form_alterado", "produto_custo_form_alterado"]:
            df_out[col] = df_out[col].fillna("")

        return df_out

    # ==============================================================================
    # EXPLOSÃO RECURSIVA DA ESTRUTURA
    # ==============================================================================
    def explodir_estrutura(produto_raiz, estrutura_df, produto_df, max_nivel=20):
        if not produto_raiz:
            return pd.DataFrame()

        estrutura = estrutura_df.copy()
        produtos = produto_df.copy()

        estrutura["produto"] = estrutura["produto"].apply(normalizar_codigo)
        estrutura["componente"] = estrutura["componente"].apply(normalizar_codigo)

        if "codigo_produto_material" in produtos.columns:
            produtos["codigo_produto_material"] = produtos["codigo_produto_material"].apply(normalizar_codigo)
        else:
            produtos["codigo_produto_material"] = ""

        for col in ["descricao_produto", "tipo_material"]:
            if col not in produtos.columns:
                produtos[col] = ""
            produtos[col] = produtos[col].fillna("").astype(str).str.strip()

        if "quantidade" not in estrutura.columns:
            estrutura["quantidade"] = 0.0
        estrutura["quantidade"] = estrutura["quantidade"].apply(to_float_br)

        produto_raiz = normalizar_codigo(produto_raiz)

        descricao_raiz = ""
        desc_match = produtos.loc[produtos["codigo_produto_material"] == produto_raiz, "descricao_produto"]
        if not desc_match.empty:
            descricao_raiz = desc_match.iloc[0]

        resultados = []
        visitados = set()

        resultados.append({
            "Nivel": 1,
            "Material": produto_raiz,
            "Descrição": descricao_raiz,
            "Unidade": "",
            "Quantidade": 100.0,
            "Produto_Pai": "",
            "Tipo_Material": "PAI",
            "Caminho": produto_raiz,
            "Chave_Explosao": f"{produto_raiz}|SEQ0"
        })

        def buscar_filhos(produto_pai, nivel_atual, fator_pai, caminho_pai):
            if nivel_atual > max_nivel:
                return

            filhos = estrutura[estrutura["produto"] == produto_pai].copy()

            if filhos.empty:
                return

            filhos = filhos.sort_values(by=["sequencia", "componente"], ascending=[True, True])

            for _, row in filhos.iterrows():
                componente = normalizar_codigo(row.get("componente", ""))
                quantidade = to_float_br(row.get("quantidade", 0))
                qtd_acumulada = fator_pai * quantidade / 100.0
                chave_ciclo = (produto_pai, componente, nivel_atual)

                desc = ""
                tipo_mat = ""
                unidade = ""

                prod_match = produtos[produtos["codigo_produto_material"] == componente]
                if not prod_match.empty:
                    desc = prod_match["descricao_produto"].iloc[0] if "descricao_produto" in prod_match.columns else ""
                    tipo_mat = prod_match["tipo_material"].iloc[0] if "tipo_material" in prod_match.columns else ""
                    if "unidade" in prod_match.columns:
                        unidade = prod_match["unidade"].iloc[0]

                caminho_atual = f"{caminho_pai} > {componente}"

                resultados.append({
                    "Nivel": nivel_atual,
                    "Material": componente,
                    "Descrição": desc,
                    "Unidade": unidade,
                    "Quantidade": qtd_acumulada,
                    "Produto_Pai": produto_pai,
                    "Tipo_Material": tipo_mat,
                    "Caminho": caminho_atual,
                    "Chave_Explosao": f"{produto_pai}|{componente}"
                })

                if chave_ciclo in visitados:
                    continue

                visitados.add(chave_ciclo)

                if componente in estrutura["produto"].values:
                    buscar_filhos(
                        produto_pai=componente,
                        nivel_atual=nivel_atual + 1,
                        fator_pai=qtd_acumulada,
                        caminho_pai=caminho_atual
                    )

        buscar_filhos(
            produto_pai=produto_raiz,
            nivel_atual=2,
            fator_pai=100.0,
            caminho_pai=produto_raiz
        )

        df_result = pd.DataFrame(resultados)

        if not df_result.empty:
            df_result["Quantidade"] = pd.to_numeric(df_result["Quantidade"], errors="coerce").fillna(0.0)

        return df_result

    # ==============================================================================
    # ENRIQUECER EXPLOSÃO COM OS VALORES DO CÁLCULO
    # ==============================================================================
    def enriquecer_explosao_com_custos(df_explodido, resultado_df):
        if df_explodido.empty:
            return df_explodido

        df_calc = resultado_df.copy()

        colunas_numericas = [
            "valor_reposicao_4", "vlrun_r", "vlrun_c", "vlrun_f", "vlrun_m",
            "custo_form", "vlrun_kg", "Custo_Un", "quantidade",
            "custo_form_banco", "custo_form_recalculado", "delta_custo_form"
        ]

        for col in colunas_numericas:
            if col not in df_calc.columns:
                df_calc[col] = 0.0
            df_calc[col] = df_calc[col].apply(to_float_br)

        for col in ["origem_vlrun_r", "flag_custo_form_alterado", "produto_custo_form_alterado"]:
            if col not in df_calc.columns:
                df_calc[col] = ""

        df_calc["produto"] = df_calc["produto"].apply(normalizar_codigo)
        df_calc["componente"] = df_calc["componente"].apply(normalizar_codigo)

        # chave para componentes
        df_calc["Chave_Explosao"] = df_calc["produto"] + "|" + df_calc["componente"]

        # linhas de sequência 0 para produto raiz
        df_seq0 = df_calc[df_calc["sequencia"] == 0].copy()
        df_seq0["Chave_Explosao"] = df_seq0["produto"] + "|SEQ0"

        # componentes normais (sequencia != 0)
        df_comp = df_calc[df_calc["sequencia"] != 0].copy()

        cols_merge = [
            "Chave_Explosao",
            "valor_reposicao_4",
            "vlrun_r",
            "vlrun_c",
            "vlrun_f",
            "vlrun_m",
            "custo_form",
            "vlrun_kg",
            "Custo_Un",
            "origem_vlrun_r",
            "custo_form_banco",
            "custo_form_recalculado",
            "delta_custo_form",
            "flag_custo_form_alterado",
            "produto_custo_form_alterado"
        ]

        base_merge = pd.concat([
            df_seq0[cols_merge],
            df_comp[cols_merge]
        ], ignore_index=True)

        base_merge = base_merge.drop_duplicates(subset=["Chave_Explosao"], keep="first")

        df_out = df_explodido.merge(base_merge, on="Chave_Explosao", how="left")

        for col in [
            "valor_reposicao_4", "vlrun_r", "vlrun_c", "vlrun_f", "vlrun_m",
            "custo_form", "vlrun_kg", "Custo_Un",
            "custo_form_banco", "custo_form_recalculado", "delta_custo_form"
        ]:
            if col in df_out.columns:
                df_out[col] = pd.to_numeric(df_out[col], errors="coerce").fillna(0.0)

        for col in ["origem_vlrun_r", "flag_custo_form_alterado", "produto_custo_form_alterado"]:
            if col in df_out.columns:
                df_out[col] = df_out[col].fillna("")

        return df_out

    # ==============================================================================
    # BOTÃO DE LIMPAR CACHE
    # ==============================================================================
    if st.button("Limpar Cache e Recarregar Dados"):
        st.cache_data.clear()
        st.success("Cache limpo com sucesso.")

    # ==============================================================================
    # PROCESSAMENTO PRINCIPAL
    # ==============================================================================
    try:
        base_merged, df_produto_base = montar_base_merged()
    except Exception as e:
        st.error(f"Erro ao carregar base do MySQL: {e}")
        st.stop()

    try:
        # cálculo original do banco
        resultado_df_banco = recalcular_custos_hierarquicos(base_merged, None)

        # cálculo recalculado com manual (ou igual ao banco caso não exista CSV manual)
        resultado_df = recalcular_custos_hierarquicos(base_merged, df_recalculo)

        # adiciona rastreabilidade da alteração do custo_form
        resultado_df = adicionar_rastreabilidade_custo_form(resultado_df_banco, resultado_df)

    except Exception as e:
        st.error(f"Erro ao recalcular custos: {e}")
        st.stop()

    # ==============================================================================
    # FILTROS
    # ==============================================================================
    st.markdown("## Filtros")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        produto_options = sorted([p for p in resultado_df["produto"].dropna().unique().tolist() if p])
        produto_options = ["Todos"] + produto_options
        selected_produtos = st.multiselect("Selecione os Produtos", produto_options, default=["Todos"])

    with col_f2:
        componente_options = sorted([c for c in resultado_df["componente"].dropna().unique().tolist() if c])
        componente_options = ["Todos"] + componente_options
        selected_componentes = st.multiselect("Selecione os Componentes", componente_options, default=["Todos"])

    with col_f3:
        origem_options = ["Todos", "BANCO", "MANUAL"]
        selected_origem = st.multiselect("Origem do vlrun_r", origem_options, default=["Todos"])

    with col_f4:
        alteracao_options = ["Todos", "SIM", "NAO"]
        selected_alteracao = st.multiselect("Alterou custo_form?", alteracao_options, default=["Todos"])

    df_view = resultado_df.copy()

    if "Todos" not in selected_produtos:
        df_view = df_view[df_view["produto"].isin(selected_produtos)]

    if "Todos" not in selected_componentes:
        df_view = df_view[df_view["componente"].isin(selected_componentes)]

    if "Todos" not in selected_origem:
        df_view = df_view[df_view["origem_vlrun_r"].isin(selected_origem)]

    if "Todos" not in selected_alteracao:
        df_view = df_view[df_view["flag_custo_form_alterado"].isin(selected_alteracao)]

    # ==============================================================================
    # RESUMO
    # ==============================================================================
    st.markdown("## Resumo")

    col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)

    qtd_componentes_manuais = df_view.loc[df_view["origem_vlrun_r"] == "MANUAL", "componente"].nunique()
    qtd_produtos = df_view["produto"].nunique()
    qtd_linhas = len(df_view)
    custo_total_seq0 = df_view.loc[df_view["sequencia"] == 0, "custo_form"].sum()
    qtd_produtos_alterados = df_view.loc[
        df_view["flag_custo_form_alterado"] == "SIM", "produto"
    ].nunique()

    col_r1.metric("Produtos", f"{qtd_produtos}")
    col_r2.metric("Linhas", f"{qtd_linhas}")
    col_r3.metric("Componentes MP alterados", f"{qtd_componentes_manuais}")
    col_r4.metric("Produtos com custo alterado", f"{qtd_produtos_alterados}")
    col_r5.metric(
        "Soma custo_form (seq 0)",
        f"{custo_total_seq0:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    # ==============================================================================
    # TABELA RESULTADO
    # ==============================================================================
    st.markdown("## Resultado do Recálculo")

    hidden_columns = [
        "codigo_empresa", "codigo_filial", "perc_na_formula", "medida_1_corte",
        "medida_2_corte", "nro_partes", "nro_item_desenho", "obs_ligacao",
        "qtde_referencial", "tem_regra_existencia", "codigo_desenho",
        "usuario_inclusao", "hora_alteracao", "usuario_alteracao",
        "qtde_prod_minuto", "data_alteracao", "hora_inclusao", "ult_preco_compra",
        "data_inclusao", "descricao_produto_pai", "codigo_produto_material"
    ]

    colunas_exibicao = [col for col in df_view.columns if col not in hidden_columns]
    df_exibicao = df_view[colunas_exibicao].copy()

    colunas_float_4 = [
        "quantidade", "valor_reposicao_4", "ult_custo_medio", "vlrun_r_manual",
        "vlrun_r", "vlrun_c", "vlrun_f", "vlrun_m", "custo_comp",
        "Custo_Un", "custo_form", "vlrun_kg",
        "custo_form_banco", "custo_form_recalculado", "delta_custo_form"
    ]

    for col in colunas_float_4:
        if col in df_exibicao.columns:
            df_exibicao[col] = df_exibicao[col].apply(lambda x: formatar_decimal_br(x, 4))

    st.dataframe(df_exibicao, use_container_width=True, height=700)

    # ==============================================================================
    # EXPORTAÇÃO CSV
    # ==============================================================================
    st.markdown("## Exportação")

    colunas_numericas_export = [
        "quantidade", "valor_reposicao_4", "ult_custo_medio", "vlrun_r_manual",
        "vlrun_r", "vlrun_c", "vlrun_f", "vlrun_m", "custo_comp",
        "Custo_Un", "custo_form", "vlrun_kg",
        "custo_form_banco", "custo_form_recalculado", "delta_custo_form"
    ]

    df_export = formatar_csv_brasileiro(df_view, colunas_numericas_export, casas=6)

    csv = df_export.to_csv(index=False, sep=";", encoding="utf-8-sig")

    st.download_button(
        label="Baixar RESULTADO_FORM recalculado",
        data=csv,
        file_name="RESULTADO_FORM_RECALCULADO.csv",
        mime="text/csv"
    )

    # ==============================================================================
    # ALTERAÇÕES MANUAIS
    # ==============================================================================
    if df_recalculo is not None and not df_recalculo.empty:
        st.markdown("## Componentes alterados manualmente")

        df_alterados = df_view[df_view["origem_vlrun_r"] == "MANUAL"].copy()

        if not df_alterados.empty:
            cols_show = [
                "produto", "sequencia", "componente", "tipo_material",
                "quantidade", "vlrun_r_manual", "vlrun_r", "vlrun_c", "vlrun_f",
                "vlrun_m", "custo_form", "custo_form_banco",
                "custo_form_recalculado", "delta_custo_form",
                "flag_custo_form_alterado", "produto_custo_form_alterado"
            ]
            cols_show = [c for c in cols_show if c in df_alterados.columns]

            df_alterados = df_alterados[cols_show].copy()

            for col in [
                "quantidade", "vlrun_r_manual", "vlrun_r", "vlrun_c",
                "vlrun_f", "vlrun_m", "custo_form",
                "custo_form_banco", "custo_form_recalculado", "delta_custo_form"
            ]:
                if col in df_alterados.columns:
                    df_alterados[col] = df_alterados[col].apply(lambda x: formatar_decimal_br(x, 4))

            st.dataframe(df_alterados, use_container_width=True, height=400)
        else:
            st.info("Nenhum componente manual encontrado nos filtros aplicados.")

    # ==============================================================================
    # PRODUTOS COM ALTERAÇÃO DE CUSTO_FORM
    # ==============================================================================
    st.markdown("## Produtos com alteração de custo_form")

    df_produtos_alterados = (
        resultado_df.loc[resultado_df["sequencia"] == 0, [
            "produto",
            "descricao_produto",
            "custo_form_banco",
            "custo_form_recalculado",
            "delta_custo_form",
            "flag_custo_form_alterado"
        ]]
        .drop_duplicates(subset=["produto"], keep="first")
        .copy()
    )

    df_produtos_alterados = df_produtos_alterados[
        df_produtos_alterados["flag_custo_form_alterado"] == "SIM"
    ]

    if not df_produtos_alterados.empty:
        df_produtos_alterados_view = df_produtos_alterados.copy()

        for col in ["custo_form_banco", "custo_form_recalculado", "delta_custo_form"]:
            if col in df_produtos_alterados_view.columns:
                df_produtos_alterados_view[col] = df_produtos_alterados_view[col].apply(
                    lambda x: formatar_decimal_br(x, 4)
                )

        st.dataframe(df_produtos_alterados_view, use_container_width=True, height=300)

        # CSV padrão brasileiro
        colunas_numericas_produtos_alterados = [
            "custo_form_banco",
            "custo_form_recalculado",
            "delta_custo_form"
        ]

        df_produtos_alterados_csv = formatar_csv_brasileiro(
            df_produtos_alterados,
            colunas_numericas_produtos_alterados,
            casas=4
        )

        csv_produtos_alterados = df_produtos_alterados_csv.to_csv(
            index=False,
            sep=";",
            encoding="utf-8-sig"
        )

        st.download_button(
            label="Baixar CSV - Produtos com alteração de custo_form",
            data=csv_produtos_alterados,
            file_name="PRODUTOS_ALTERACAO_CUSTO_FORM.csv",
            mime="text/csv"
        )
    else:
        st.info("Nenhum produto teve alteração de custo_form.")

    # ==============================================================================
    # EXPLOSÃO DOS NÍVEIS DE PRODUÇÃO + AUDITORIA DE CUSTO
    # ==============================================================================
    st.markdown("## Explosão da Estrutura de Produção")

    col_e1, col_e2 = st.columns([2, 1])

    lista_produtos_explosao = sorted(base_merged["produto"].dropna().unique().tolist())

    with col_e1:
        produto_explosao = st.selectbox(
            "Selecione o produto para extrair todos os níveis da estrutura",
            options=[""] + lista_produtos_explosao,
            index=0,
            key="produto_explosao"
        )

    with col_e2:
        max_nivel_explosao = st.number_input(
            "Máx. níveis",
            min_value=1,
            max_value=50,
            value=20,
            step=1
        )

    if produto_explosao:
        df_explodido = explodir_estrutura(
            produto_raiz=produto_explosao,
            estrutura_df=base_merged,
            produto_df=df_produto_base,
            max_nivel=max_nivel_explosao
        )

        if not df_explodido.empty:
            df_explodido = enriquecer_explosao_com_custos(df_explodido, resultado_df)

            st.markdown(f"### Estrutura completa do produto: `{produto_explosao}`")

            df_explodido_view = df_explodido.copy()

            colunas_float_explosao = [
                "Quantidade", "valor_reposicao_4", "vlrun_r", "vlrun_c",
                "vlrun_f", "vlrun_m", "Custo_Un", "custo_form", "vlrun_kg",
                "custo_form_banco", "custo_form_recalculado", "delta_custo_form"
            ]

            for col in colunas_float_explosao:
                if col in df_explodido_view.columns:
                    df_explodido_view[col] = df_explodido_view[col].apply(lambda x: formatar_decimal_br(x, 6))

            colunas_final = [
                "Nivel", "Material", "Descrição", "Unidade", "Quantidade",
                "Produto_Pai", "Tipo_Material",
                "valor_reposicao_4", "vlrun_r", "vlrun_c", "vlrun_f", "vlrun_m",
                "Custo_Un", "custo_form", "vlrun_kg",
                "custo_form_banco", "custo_form_recalculado", "delta_custo_form",
                "origem_vlrun_r", "flag_custo_form_alterado",
                "produto_custo_form_alterado", "Caminho"
            ]
            colunas_final = [c for c in colunas_final if c in df_explodido_view.columns]

            st.dataframe(df_explodido_view[colunas_final], use_container_width=True, height=700)

            colunas_numericas_explodido = [
                "Quantidade", "valor_reposicao_4", "vlrun_r", "vlrun_c",
                "vlrun_f", "vlrun_m", "Custo_Un", "custo_form", "vlrun_kg",
                "custo_form_banco", "custo_form_recalculado", "delta_custo_form"
            ]

            df_explodido_csv = formatar_csv_brasileiro(df_explodido, colunas_numericas_explodido, casas=6)

            csv_explodido = df_explodido_csv.to_csv(index=False, sep=";", encoding="utf-8-sig")

            st.download_button(
                label="Baixar Estrutura Explodida com Custos",
                data=csv_explodido,
                file_name=f"ESTRUTURA_EXPLODIDA_CUSTO_{produto_explosao}.csv",
                mime="text/csv"
            )
        else:
            st.warning("Nenhuma estrutura encontrada para o produto informado.")