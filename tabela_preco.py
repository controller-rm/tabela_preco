import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

#st.set_page_config(page_title="Tabela de Preço", layout="wide")
def executar_tabela_preco(df_base=None):
    import streamlit as st

    def init_state():
        defaults = {
            "df_original": None,
            "df_trabalho": None,
            "simulacoes": [],
            "arquivo_principal_nome": None,
            "arquivo_custo_nome": None,
            "arquivo_grupo_nome": None,
            "df_grupo": None,
            "painel_grupos": [],
            "painel_subgrupos": [],
            "painel_perc_reajuste": 0.0,
            "painel_perc_icms": "",
            "painel_perc_pis": "",
            "painel_perc_cofins": "",
            "painel_perc_irpj": "",
            "painel_perc_cs": "",
            "painel_perc_comis": "",
            "painel_perc_custo_op": "",
            "painel_perc_lucro": "",
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    init_state()

    st.subheader("💲 Tabela de Preço")

    if df_base is not None and st.session_state["df_original"] is None:
        st.session_state["df_original"] = df_base.copy()
        st.session_state["df_trabalho"] = df_base.copy()

    st.title("📊 Tabela de Preço - Reajuste Inteligente")

    # =========================================================
    # CONFIGURAÇÕES
    # =========================================================
    COLUNAS_EXIBICAO = [
        "Cod.Produto",
        "Desc.Produto",
        "Data.Preco",
        "Grupo",
        "Subgrupo",
        "Linha",
        "Ncm",
        "Preco.Com.Liq",
        "Perc.Icms.Ven",
        "Perc.Pis.Ven",
        "Perc.Cofins.Ven",
        "Perc.Irpj.Ven",
        "Perc.Cs.Ven",
        "Perc.Comis.ven",
        "Perc.Custo.Op.Ven",
        "Perc.Lucro.Ven",
        "Preco.Ideal",
        "Preco.Venda",
        "Preco.Minimo",
    ]

    COLUNAS_ESPERADAS = [
        "Cod.Produto",
        "Desc.Produto",
        "Data.Preco",
        "Grupo",
        "Subgrupo",
        "Linha",
        "Ncm",
        "Preco.Com.Liq",
        "Perc.Icms.Ven",
        "Perc.Pis.Ven",
        "Perc.Cofins.Ven",
        "Perc.Irpj.Ven",
        "Perc.Cs.Ven",
        "Perc.Comis.ven",
        "Perc.Custo.Op.Ven",
        "Perc.Lucro.Ven",
        "Preco.Ideal",
        "Preco.Venda",
        "Preco.Minimo",
    ]

    COLUNAS_PERCENTUAIS = [
        "Perc.Icms.Ven",
        "Perc.Pis.Ven",
        "Perc.Cofins.Ven",
        "Perc.Irpj.Ven",
        "Perc.Cs.Ven",
        "Perc.Comis.ven",
        "Perc.Custo.Op.Ven",
        "Perc.Lucro.Ven",
    ]

    COLUNAS_NUMERICAS = [
        "Preco.Com.Liq",
        "Preco.Ideal",
        "Preco.Venda",
        "Preco.Minimo",
        *COLUNAS_PERCENTUAIS,
    ]

    COLUNAS_AUXILIARES_DEFAULT = {
        "Preco.Venda.Original": np.nan,
        "Preco.Com.Liq.Original": np.nan,
        "Perc_reajuste": 0.0,
        "Ajustado": "",
        "Origem_Preco.Com.Liq": "ARQUIVO",
        "Reajuste_vs_PrecoVenda_Original_%": 0.0,
        "Impacto_Reajuste_R$": 0.0,
        "Ultima_Simulacao": "",
        "Flag_Ajuste": "",
        "Impacto_Visual": "",
    }

    # =========================================================
    # SESSION STATE
    # =========================================================
    def init_state():
        defaults = {
            "df_original": None,
            "df_trabalho": None,
            "simulacoes": [],
            "arquivo_principal_nome": None,
            "arquivo_custo_nome": None,
            "arquivo_grupo_nome": None,
            "df_grupo": None,
            "painel_grupos": [],
            "painel_subgrupos": [],
            "painel_perc_reajuste": 0.0,
            "painel_perc_icms": "",
            "painel_perc_pis": "",
            "painel_perc_cofins": "",
            "painel_perc_irpj": "",
            "painel_perc_cs": "",
            "painel_perc_comis": "",
            "painel_perc_custo_op": "",
            "painel_perc_lucro": "",
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v


    init_state()

    # =========================================================
    # FUNÇÕES AUXILIARES
    # =========================================================
    def normalizar_numero(valor):
        if pd.isna(valor):
            return np.nan

        s = str(valor).strip()
        if s == "":
            return np.nan

        s = s.replace("R$", "").replace("%", "").replace("€", "").strip()

        if "," in s:
            s = s.replace(".", "").replace(",", ".")

        try:
            return float(s)
        except Exception:
            return np.nan


    def formatar_numero_br(valor, casas=2):
        if pd.isna(valor):
            return ""
        return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


    def parse_percent_input(valor_texto):
        s = str(valor_texto).strip()
        if s == "":
            return None
        return normalizar_numero(s)


    def validar_colunas(df, colunas_esperadas):
        faltando = [c for c in colunas_esperadas if c not in df.columns]
        if faltando:
            raise ValueError(f"Colunas faltando: {faltando}")


    def garantir_colunas_auxiliares(df):
        for col, default in COLUNAS_AUXILIARES_DEFAULT.items():
            if col not in df.columns:
                df[col] = default
        return df


    def calcular_preco_ideal(df):
        soma_perc = df[COLUNAS_PERCENTUAIS].fillna(0).sum(axis=1)
        divisor = 1 - (soma_perc / 100)
        df["Preco.Ideal"] = np.where(divisor <= 0, np.nan, df["Preco.Com.Liq"] / divisor)
        return df


    def calcular_percentual_vs_preco_venda_original(df):
        base = df["Preco.Venda.Original"].replace(0, np.nan)
        df["Reajuste_vs_PrecoVenda_Original_%"] = ((df["Preco.Ideal"] / base) - 1) * 100
        return df


    def atualizar_flags(df):
        df["Flag_Ajuste"] = np.where(
            df["Ajustado"].astype(str).str.strip() != "",
            "SIM",
            ""
        )
        df["Impacto_Visual"] = np.where(
            df["Impacto_Reajuste_R$"] > 0, "🟢",
            np.where(df["Impacto_Reajuste_R$"] < 0, "🔴", "")
        )
        return df


    @st.cache_data(show_spinner=False)
    def carregar_csv_principal_cache(file_bytes):
        arquivo = BytesIO(file_bytes)
        df = pd.read_csv(arquivo, sep=";", encoding="latin1", dtype=str)

        validar_colunas(df, COLUNAS_ESPERADAS)

        for c in ["Cod.Produto", "Desc.Produto", "Data.Preco", "Grupo", "Subgrupo", "Linha", "Ncm"]:
            df[c] = df[c].astype(str).str.strip()

        df = df[df["Grupo"].astype(str).str.strip() != "0"].copy()

        for c in COLUNAS_NUMERICAS:
            df[c] = df[c].apply(normalizar_numero)

        df["Preco.Venda.Original"] = df["Preco.Venda"]
        df["Preco.Com.Liq.Original"] = df["Preco.Com.Liq"]
        df["Perc_reajuste"] = 0.0
        df["Ajustado"] = ""
        df["Origem_Preco.Com.Liq"] = "ARQUIVO"
        df["Reajuste_vs_PrecoVenda_Original_%"] = 0.0
        df["Ultima_Simulacao"] = ""

        df = garantir_colunas_auxiliares(df)
        df = calcular_preco_ideal(df)
        df = calcular_percentual_vs_preco_venda_original(df)
        df["Impacto_Reajuste_R$"] = df["Preco.Ideal"] - df["Preco.Venda.Original"]
        df = atualizar_flags(df)

        return df.reset_index(drop=True)


    def carregar_csv_custo(arquivo):
        df = pd.read_csv(arquivo, sep=";", encoding="latin1", dtype=str)

        if "custo_form_recalculado" in df.columns:
            col_custo = "custo_form_recalculado"
        elif "custo_form" in df.columns:
            col_custo = "custo_form"
        else:
            raise ValueError("O arquivo de custo deve ter as colunas: produto;custo_form ou produto;custo_form_recalculado")

        validar_colunas(df.rename(columns={col_custo: "custo_temp"}), ["produto", "custo_temp"])

        df["produto"] = df["produto"].astype(str).str.strip()
        df[col_custo] = df[col_custo].apply(normalizar_numero)
        df = df.rename(columns={col_custo: "custo_aplicado"})
        return df[["produto", "custo_aplicado"]]


    def carregar_csv_grupo(arquivo):
        df = pd.read_csv(arquivo, sep=";", encoding="latin1", dtype=str)
        validar_colunas(df, ["grupo", "desc_grupo", "subgrupo", "desc_subgrupo"])

        for c in ["grupo", "desc_grupo", "subgrupo", "desc_subgrupo"]:
            df[c] = df[c].astype(str).str.strip()

        return df


    def aplicar_upload_custo(df_base, df_custo):
        df = df_base.copy()
        df = garantir_colunas_auxiliares(df)

        mapa_custo = dict(zip(df_custo["produto"], df_custo["custo_aplicado"]))
        mask = df["Cod.Produto"].astype(str).isin(mapa_custo.keys())

        if mask.any():
            df.loc[mask, "Preco.Com.Liq"] = df.loc[mask, "Cod.Produto"].map(mapa_custo)
            df.loc[mask, "Origem_Preco.Com.Liq"] = "UPLOAD_CUSTO"

            atual = df.loc[mask, "Ajustado"].astype(str).str.strip()
            df.loc[mask, "Ajustado"] = np.where(
                atual.eq(""),
                "CUSTO",
                atual + " | CUSTO"
            )

        df = calcular_preco_ideal(df)
        df = calcular_percentual_vs_preco_venda_original(df)
        df["Impacto_Reajuste_R$"] = df["Preco.Ideal"] - df["Preco.Venda.Original"]
        df = atualizar_flags(df)
        return df


    def obter_mask(df, grupos, subgrupos):
        if not grupos:
            return pd.Series([False] * len(df), index=df.index)

        mask = df["Grupo"].astype(str).isin([str(g) for g in grupos])

        if subgrupos:
            mask &= df["Subgrupo"].astype(str).isin([str(s) for s in subgrupos])

        return mask


    def aplicar_simulacao(
        df_base,
        grupos,
        subgrupos,
        perc_reajuste,
        perc_icms,
        perc_pis,
        perc_cofins,
        perc_irpj,
        perc_cs,
        perc_comis,
        perc_custo_op,
        perc_lucro,
    ):
        df = df_base.copy()
        df = garantir_colunas_auxiliares(df)

        mask = obter_mask(df, grupos, subgrupos)
        if not mask.any():
            return df, 0, "Nenhuma linha encontrada"

        sinais = []

        if perc_reajuste is not None and float(perc_reajuste) != 0:
            df.loc[mask, "Preco.Com.Liq"] = df.loc[mask, "Preco.Com.Liq"] * (1 + float(perc_reajuste) / 100)
            df.loc[mask, "Perc_reajuste"] = float(perc_reajuste)
            sinais.append("PRECO")

        mapa_percentuais = {
            "Perc.Icms.Ven": perc_icms,
            "Perc.Pis.Ven": perc_pis,
            "Perc.Cofins.Ven": perc_cofins,
            "Perc.Irpj.Ven": perc_irpj,
            "Perc.Cs.Ven": perc_cs,
            "Perc.Comis.ven": perc_comis,
            "Perc.Custo.Op.Ven": perc_custo_op,
            "Perc.Lucro.Ven": perc_lucro,
        }

        houve_percentuais = False
        for coluna, valor in mapa_percentuais.items():
            if valor is not None:
                df.loc[mask, coluna] = float(valor)
                houve_percentuais = True

        if houve_percentuais:
            sinais.append("PERCENTUAIS")

        if sinais:
            etiqueta = " | ".join(sinais)
            atual = df.loc[mask, "Ajustado"].astype(str).str.strip()
            df.loc[mask, "Ajustado"] = np.where(
                atual.eq(""),
                etiqueta,
                atual + " | " + etiqueta
            )

        sim_nome = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        df.loc[mask, "Ultima_Simulacao"] = sim_nome

        df = calcular_preco_ideal(df)
        df = calcular_percentual_vs_preco_venda_original(df)
        df["Impacto_Reajuste_R$"] = df["Preco.Ideal"] - df["Preco.Venda.Original"]
        df = atualizar_flags(df)

        return df, int(mask.sum()), sim_nome


    def filtrar_visualizacao(df, grupos, subgrupos):
        df_visual = df

        if grupos:
            df_visual = df_visual[df_visual["Grupo"].astype(str).isin([str(x) for x in grupos])]

            if subgrupos:
                df_visual = df_visual[df_visual["Subgrupo"].astype(str).isin([str(x) for x in subgrupos])]

        return df_visual


    def enriquecer_resumo_com_descricoes(df_resumo, df_grupo, incluir_subgrupo=True):
        if df_resumo.empty or df_grupo is None or df_grupo.empty:
            return df_resumo

        if incluir_subgrupo:
            mapa = (
                df_grupo[["grupo", "desc_grupo", "subgrupo", "desc_subgrupo"]]
                .drop_duplicates()
                .rename(columns={"grupo": "Grupo", "subgrupo": "Subgrupo"})
            )
            df_resumo = df_resumo.merge(mapa, on=["Grupo", "Subgrupo"], how="left")

            cols = df_resumo.columns.tolist()
            nova_ordem = []
            for c in ["Grupo", "desc_grupo", "Subgrupo", "desc_subgrupo"]:
                if c in cols:
                    nova_ordem.append(c)
            for c in cols:
                if c not in nova_ordem:
                    nova_ordem.append(c)

            return df_resumo[nova_ordem]

        mapa_grupo = (
            df_grupo[["grupo", "desc_grupo"]]
            .drop_duplicates()
            .rename(columns={"grupo": "Grupo"})
        )
        df_resumo = df_resumo.merge(mapa_grupo, on="Grupo", how="left")

        cols = df_resumo.columns.tolist()
        nova_ordem = []
        for c in ["Grupo", "desc_grupo"]:
            if c in cols:
                nova_ordem.append(c)
        for c in cols:
            if c not in nova_ordem:
                nova_ordem.append(c)

        return df_resumo[nova_ordem]


    def gerar_resumo_grupo_subgrupo(df, df_grupo=None):
        if df.empty:
            return pd.DataFrame()

        resumo = df.groupby(["Grupo", "Subgrupo"], dropna=False).agg(
            Qtde_Itens=("Cod.Produto", "count"),
            Itens_Ajustados=("Ajustado", lambda s: (s.astype(str).str.strip() != "").sum()),
            PrecoComLiq_Medio=("Preco.Com.Liq", "mean"),
            PrecoIdeal_Medio=("Preco.Ideal", "mean"),
            PrecoVendaOriginal_Medio=("Preco.Venda.Original", "mean"),
            PercReajuste_Medio=("Perc_reajuste", "mean"),
            ImpactoReajuste_Medio_RS=("Impacto_Reajuste_R$", "mean"),
            Soma_Venda=("Preco.Venda.Original", "sum"),
            Soma_Ideal=("Preco.Ideal", "sum"),
        ).reset_index()

        resumo["Perc_Reajuste_Ponderado_%"] = np.where(
            resumo["Soma_Venda"] == 0,
            0,
            ((resumo["Soma_Ideal"] / resumo["Soma_Venda"]) - 1) * 100
        )

        resumo = resumo.drop(columns=["Soma_Venda", "Soma_Ideal"])
        resumo = enriquecer_resumo_com_descricoes(resumo, df_grupo, incluir_subgrupo=True)
        return resumo


    def gerar_resumo_grupo(df, df_grupo=None):
        if df.empty:
            return pd.DataFrame()

        resumo = df.groupby(["Grupo"], dropna=False).agg(
            Qtde_Itens=("Cod.Produto", "count"),
            Itens_Ajustados=("Ajustado", lambda s: (s.astype(str).str.strip() != "").sum()),
            PrecoComLiq_Medio=("Preco.Com.Liq", "mean"),
            PrecoIdeal_Medio=("Preco.Ideal", "mean"),
            PrecoVendaOriginal_Medio=("Preco.Venda.Original", "mean"),
            PercReajuste_Medio=("Perc_reajuste", "mean"),
            ImpactoReajuste_Medio_RS=("Impacto_Reajuste_R$", "mean"),
            Soma_Venda=("Preco.Venda.Original", "sum"),
            Soma_Ideal=("Preco.Ideal", "sum"),
        ).reset_index()

        resumo["Perc_Reajuste_Ponderado_%"] = np.where(
            resumo["Soma_Venda"] == 0,
            0,
            ((resumo["Soma_Ideal"] / resumo["Soma_Venda"]) - 1) * 100
        )

        resumo = resumo.drop(columns=["Soma_Venda", "Soma_Ideal"])
        resumo = enriquecer_resumo_com_descricoes(resumo, df_grupo, incluir_subgrupo=False)
        return resumo


    def preparar_download_csv(df):
        df_export = df.copy()
        for col in df_export.columns:
            if pd.api.types.is_numeric_dtype(df_export[col]):
                df_export[col] = df_export[col].apply(
                    lambda x: formatar_numero_br(x, 2) if pd.notna(x) else ""
                )
        return df_export.to_csv(index=False, sep=";", encoding="utf-8-sig")


    def limpar_painel_inputs():
        st.session_state.painel_grupos = []
        st.session_state.painel_subgrupos = []
        st.session_state.painel_perc_reajuste = 0.0
        st.session_state.painel_perc_icms = ""
        st.session_state.painel_perc_pis = ""
        st.session_state.painel_perc_cofins = ""
        st.session_state.painel_perc_irpj = ""
        st.session_state.painel_perc_cs = ""
        st.session_state.painel_perc_comis = ""
        st.session_state.painel_perc_custo_op = ""
        st.session_state.painel_perc_lucro = ""


    def resetar_base_trabalho():
        if st.session_state.df_original is not None:
            st.session_state.df_trabalho = st.session_state.df_original.copy()
            st.session_state.arquivo_custo_nome = None


    def salvar_simulacao():
        df = st.session_state.df_trabalho.copy()
        df_visual = filtrar_visualizacao(
            df,
            st.session_state.painel_grupos,
            st.session_state.painel_subgrupos
        )

        resumo = gerar_resumo_grupo_subgrupo(df_visual, st.session_state.df_grupo)

        if resumo.empty:
            return False, "Não há dados para salvar."

        registro = {
            "datahora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "grupos": list(st.session_state.painel_grupos),
            "subgrupos": list(st.session_state.painel_subgrupos),
            "perc_reajuste": st.session_state.painel_perc_reajuste,
            "perc_icms": st.session_state.painel_perc_icms,
            "perc_pis": st.session_state.painel_perc_pis,
            "perc_cofins": st.session_state.painel_perc_cofins,
            "perc_irpj": st.session_state.painel_perc_irpj,
            "perc_cs": st.session_state.painel_perc_cs,
            "perc_comis": st.session_state.painel_perc_comis,
            "perc_custo_op": st.session_state.painel_perc_custo_op,
            "perc_lucro": st.session_state.painel_perc_lucro,
            "resumo": resumo.copy(),
        }

        st.session_state.simulacoes.insert(0, registro)
        st.session_state.simulacoes = st.session_state.simulacoes[:10]
        return True, "Simulação salva com sucesso."

    # =========================================================
    # CALLBACKS
    # =========================================================
    def acao_carregar_principal():
        arquivo = st.session_state.get("upload_principal")
        if arquivo is None:
            return

        try:
            df = carregar_csv_principal_cache(arquivo.getvalue())
            st.session_state.df_original = df.copy()
            st.session_state.df_trabalho = df.copy()
            st.session_state.arquivo_principal_nome = arquivo.name
            st.session_state.simulacoes = []
            st.session_state.arquivo_custo_nome = None
            limpar_painel_inputs()
            st.success("Base principal carregada com sucesso.")
        except Exception as e:
            st.error(f"Erro ao carregar CSV principal: {e}")


    def acao_aplicar_custo():
        if st.session_state.df_trabalho is None:
            st.warning("Carregue primeiro o CSV principal.")
            return

        arquivo = st.session_state.get("upload_custo")
        if arquivo is None:
            st.warning("Selecione o arquivo de custo.")
            return

        try:
            df_custo = carregar_csv_custo(arquivo)
            st.session_state.df_trabalho = aplicar_upload_custo(st.session_state.df_trabalho, df_custo)
            st.session_state.arquivo_custo_nome = arquivo.name
            st.success("Arquivo de custo aplicado com sucesso.")
        except Exception as e:
            st.error(f"Erro ao aplicar arquivo de custo: {e}")


    def acao_carregar_grupo():
        arquivo = st.session_state.get("upload_grupo")
        if arquivo is None:
            return

        try:
            st.session_state.df_grupo = carregar_csv_grupo(arquivo)
            st.session_state.arquivo_grupo_nome = arquivo.name
            st.success("Arquivo grupo.csv carregado com sucesso.")
        except Exception as e:
            st.error(f"Erro ao carregar grupo.csv: {e}")


    def acao_aplicar():
        if st.session_state.df_trabalho is None:
            st.warning("Carregue o CSV principal primeiro.")
            return

        grupos = list(st.session_state.painel_grupos)
        subgrupos = list(st.session_state.painel_subgrupos)

        df_novo, qtd, sim_nome = aplicar_simulacao(
            df_base=st.session_state.df_trabalho,
            grupos=grupos,
            subgrupos=subgrupos,
            perc_reajuste=st.session_state.painel_perc_reajuste,
            perc_icms=parse_percent_input(st.session_state.painel_perc_icms),
            perc_pis=parse_percent_input(st.session_state.painel_perc_pis),
            perc_cofins=parse_percent_input(st.session_state.painel_perc_cofins),
            perc_irpj=parse_percent_input(st.session_state.painel_perc_irpj),
            perc_cs=parse_percent_input(st.session_state.painel_perc_cs),
            perc_comis=parse_percent_input(st.session_state.painel_perc_comis),
            perc_custo_op=parse_percent_input(st.session_state.painel_perc_custo_op),
            perc_lucro=parse_percent_input(st.session_state.painel_perc_lucro),
        )

        st.session_state.df_trabalho = df_novo

        if qtd > 0:
            st.success(f"Aplicação concluída em {qtd} linha(s). Simulação: {sim_nome}")
        else:
            st.warning("Nenhuma linha foi ajustada. Selecione ao menos um Grupo.")


    def acao_limpar():
        resetar_base_trabalho()
        limpar_painel_inputs()
        st.success("Simulações limpas. Base restaurada.")


    def acao_salvar_simulacao():
        ok, msg = salvar_simulacao()
        if ok:
            st.success(msg)
        else:
            st.warning(msg)

    # =========================================================
    # UPLOADS
    # =========================================================
    with st.expander("📂 Upload da Tabela de Preço (CSV principal)", expanded=True):
        st.file_uploader(
            "Selecione o CSV principal",
            type=["csv"],
            key="upload_principal"
        )
        c1, c2 = st.columns([1, 4])
        c1.button("Carregar Base", on_click=acao_carregar_principal, use_container_width=True)
        if st.session_state.arquivo_principal_nome:
            c2.caption(f"Arquivo carregado: {st.session_state.arquivo_principal_nome}")

    with st.expander("📥 Sobrescrever Preco.Com.Liq por arquivo de custo", expanded=False):
        st.file_uploader(
            "Selecione o CSV de custo no formato: produto;custo_form ou produto;custo_form_recalculado",
            type=["csv"],
            key="upload_custo"
        )
        c1, c2 = st.columns([1, 4])
        c1.button("Aplicar Custo", on_click=acao_aplicar_custo, use_container_width=True)
        if st.session_state.arquivo_custo_nome:
            c2.caption(f"Arquivo de custo aplicado: {st.session_state.arquivo_custo_nome}")

    with st.expander("🗂️ Upload grupo.csv para descrições de Grupo/Subgrupo", expanded=False):
        st.file_uploader(
            "Selecione o arquivo grupo.csv",
            type=["csv"],
            key="upload_grupo"
        )
        c1, c2 = st.columns([1, 4])
        c1.button("Carregar grupo.csv", on_click=acao_carregar_grupo, use_container_width=True)
        if st.session_state.arquivo_grupo_nome:
            c2.caption(f"Arquivo carregado: {st.session_state.arquivo_grupo_nome}")

    if st.session_state.df_trabalho is None:
        st.info("Carregue a base principal para iniciar.")
        st.stop()

    st.session_state.df_trabalho = garantir_colunas_auxiliares(st.session_state.df_trabalho)

    # =========================================================
    # SIDEBAR COM FORM
    # =========================================================
    df_ref = st.session_state.df_trabalho
    st.sidebar.markdown("## ⚙️ Reajustes")

    grupos_disponiveis = sorted(df_ref["Grupo"].dropna().astype(str).unique().tolist())

    with st.sidebar.form(key="form_reajuste_unico", clear_on_submit=False):
        grupos_form = st.multiselect(
            "Grupo",
            options=grupos_disponiveis,
            default=st.session_state.painel_grupos
        )

        if grupos_form:
            subgrupos_disponiveis = sorted(
                df_ref[df_ref["Grupo"].astype(str).isin(grupos_form)]["Subgrupo"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
        else:
            subgrupos_disponiveis = []

        subgrupos_default = [s for s in st.session_state.painel_subgrupos if s in subgrupos_disponiveis]

        subgrupos_form = st.multiselect(
            "Subgrupo",
            options=subgrupos_disponiveis,
            default=subgrupos_default,
            help="O Subgrupo depende dos Grupos selecionados."
        )

        st.markdown("---")
        st.markdown("### 💰 Reajuste do Preco.Com.Liq")

        perc_reajuste_form = st.number_input(
            "Percentual de Reajuste (%)",
            min_value=-100.0,
            step=0.10,
            format="%.2f",
            value=float(st.session_state.painel_perc_reajuste)
        )

        st.markdown("---")
        st.markdown("### 📊 Sobrescrever percentuais")

        perc_icms_form = st.text_input("Perc.Icms.Ven", value=st.session_state.painel_perc_icms, placeholder="Deixe vazio para não alterar")
        perc_pis_form = st.text_input("Perc.Pis.Ven", value=st.session_state.painel_perc_pis, placeholder="Deixe vazio para não alterar")
        perc_cofins_form = st.text_input("Perc.Cofins.Ven", value=st.session_state.painel_perc_cofins, placeholder="Deixe vazio para não alterar")
        perc_irpj_form = st.text_input("Perc.Irpj.Ven", value=st.session_state.painel_perc_irpj, placeholder="Deixe vazio para não alterar")
        perc_cs_form = st.text_input("Perc.Cs.Ven", value=st.session_state.painel_perc_cs, placeholder="Deixe vazio para não alterar")
        perc_comis_form = st.text_input("Perc.Comis.ven", value=st.session_state.painel_perc_comis, placeholder="Deixe vazio para não alterar")
        perc_custo_op_form = st.text_input("Perc.Custo.Op.Ven", value=st.session_state.painel_perc_custo_op, placeholder="Deixe vazio para não alterar")
        perc_lucro_form = st.text_input("Perc.Lucro.Ven", value=st.session_state.painel_perc_lucro, placeholder="Deixe vazio para não alterar")

        col_f1, col_f2 = st.columns(2)
        aplicar_form = col_f1.form_submit_button("Aplicar", use_container_width=True)
        limpar_form = col_f2.form_submit_button("Limpar", use_container_width=True)

    salvar_form = st.sidebar.button("Salvar Simulação", use_container_width=True)

    # =========================================================
    # AÇÕES DO FORM
    # =========================================================
    if aplicar_form:
        st.session_state.painel_grupos = grupos_form
        st.session_state.painel_subgrupos = subgrupos_form
        st.session_state.painel_perc_reajuste = perc_reajuste_form
        st.session_state.painel_perc_icms = perc_icms_form
        st.session_state.painel_perc_pis = perc_pis_form
        st.session_state.painel_perc_cofins = perc_cofins_form
        st.session_state.painel_perc_irpj = perc_irpj_form
        st.session_state.painel_perc_cs = perc_cs_form
        st.session_state.painel_perc_comis = perc_comis_form
        st.session_state.painel_perc_custo_op = perc_custo_op_form
        st.session_state.painel_perc_lucro = perc_lucro_form
        acao_aplicar()
        st.rerun()

    if limpar_form:
        acao_limpar()
        st.rerun()

    if salvar_form:
        acao_salvar_simulacao()
        st.rerun()

    # =========================================================
    # BASE VISUAL FILTRADA
    # =========================================================
    
    df_visual = filtrar_visualizacao(
        st.session_state.df_trabalho,
        st.session_state.painel_grupos,
        st.session_state.painel_subgrupos
    )

    # =========================================================
    # MÉTRICAS LEVES
    # =========================================================
    m1, m2 = st.columns(2)
    m1.metric("Itens da Base", f"{len(df_visual):,}".replace(",", "."))
    m2.metric("Itens Ajustados", f"{(df_visual['Ajustado'].astype(str).str.strip() != '').sum():,}".replace(",", "."))

    # =========================================================
    # TABELA AJUSTADA
    # =========================================================
    st.markdown("## 📋 Tabela Ajustada")

    colunas_extras = [
        "Preco.Venda.Original",
        "Perc_reajuste",
        "Reajuste_vs_PrecoVenda_Original_%",
        "Impacto_Reajuste_R$",
        "Impacto_Visual",
        "Origem_Preco.Com.Liq",
        "Ajustado",
        "Flag_Ajuste",
        "Ultima_Simulacao",
    ]

    df_tabela = df_visual[COLUNAS_EXIBICAO + colunas_extras].copy()

    st.dataframe(
        df_tabela.style.format({
            "Preco.Com.Liq": "{:.2f}",
            "Perc.Icms.Ven": "{:.2f}",
            "Perc.Pis.Ven": "{:.2f}",
            "Perc.Cofins.Ven": "{:.2f}",
            "Perc.Irpj.Ven": "{:.2f}",
            "Perc.Cs.Ven": "{:.2f}",
            "Perc.Comis.ven": "{:.2f}",
            "Perc.Custo.Op.Ven": "{:.2f}",
            "Perc.Lucro.Ven": "{:.2f}",
            "Preco.Ideal": "{:.2f}",
            "Preco.Venda": "{:.2f}",
            "Preco.Minimo": "{:.2f}",
            "Preco.Venda.Original": "{:.2f}",
            "Perc_reajuste": "{:.2f}",
            "Reajuste_vs_PrecoVenda_Original_%": "{:.2f}",
            "Impacto_Reajuste_R$": "{:.2f}",
        }),
        use_container_width=True,
        height=520,
    )

    # =========================================================
    # RANKING DAS MAIORES DISTORÇÕES
    # =========================================================
    st.markdown("## 🎯 Ranking das Maiores Distorções de Preço")
    st.caption(
        "A distorção mostra a diferença entre o Preço de Venda Original e o Preço Ideal. "
        "🟢 indica necessidade de aumento. 🔴 indica que o preço atual está acima do ideal."
    )

    df_ranking = df_visual.copy()

    if not df_ranking.empty:
        df_ranking["Abs_Distorcao_%"] = df_ranking["Reajuste_vs_PrecoVenda_Original_%"].abs()
        df_ranking["Abs_Distorcao_R$"] = df_ranking["Impacto_Reajuste_R$"].abs()

        col_r1, col_r2 = st.columns([1, 2])

        with col_r1:
            top_n = st.selectbox(
                "Quantidade de itens no ranking",
                options=[10, 20, 30, 50, 100],
                index=1,
                key="ranking_top_n"
            )

        with col_r2:
            criterio = st.radio(
                "Ordenar ranking por",
                options=["Percentual", "Valor (R$)"],
                horizontal=True,
                key="ranking_criterio"
            )

        if criterio == "Percentual":
            df_ranking = df_ranking.sort_values("Abs_Distorcao_%", ascending=False)
        else:
            df_ranking = df_ranking.sort_values("Abs_Distorcao_R$", ascending=False)

        colunas_ranking = [
            "Cod.Produto",
            "Desc.Produto",
            "Grupo",
            "Subgrupo",
            "Preco.Venda.Original",
            "Preco.Ideal",
            "Reajuste_vs_PrecoVenda_Original_%",
            "Impacto_Reajuste_R$",
            "Impacto_Visual",
            "Ajustado",
            "Flag_Ajuste",
        ]

        st.dataframe(
            df_ranking[colunas_ranking].head(top_n).style.format({
                "Preco.Venda.Original": "{:.2f}",
                "Preco.Ideal": "{:.2f}",
                "Reajuste_vs_PrecoVenda_Original_%": "{:.2f}",
                "Impacto_Reajuste_R$": "{:.2f}",
            }),
            use_container_width=True,
            height=350
        )
    else:
        st.info("Sem dados para gerar ranking.")

    # =========================================================
    # RESUMOS
    # =========================================================
    st.markdown("## 📊 Resumo de Ajustes Médios por Grupo e Subgrupo")
    st.markdown("""
    ℹ️ **Como é calculado o percentual médio de reajuste**

    O percentual exibido é uma **média ponderada pelo valor de venda original**, calculada da seguinte forma:

    👉 (Soma do Preço Ideal ÷ Soma do Preço de Venda Original) - 1

    Isso representa o impacto real do reajuste no faturamento, evitando distorções de itens com valores muito baixos ou altos.
    ### ℹ️ Como são calculadas as médias do resumo

    As colunas abaixo são calculadas como **média aritmética simples** dos itens que compõem cada agrupamento exibido no resumo:

    - **PrecoComLiq_Medio**  
    Soma de todos os valores de **Preco.Com.Liq** do grupo ÷ quantidade de itens do grupo.

    - **PrecoIdeal_Medio**  
    Soma de todos os valores de **Preco.Ideal** do grupo ÷ quantidade de itens do grupo.

    - **PrecoVendaOriginal_Medio**  
    Soma de todos os valores de **Preco.Venda.Original** do grupo ÷ quantidade de itens do grupo.

    #### Fórmula geral
    Para qualquer uma dessas colunas:

    `Média = Soma dos valores da coluna / Quantidade de itens`

    #### Exemplo
    Se um grupo tiver 3 produtos com **Preco.Com.Liq** de:

    - 10,00
    - 20,00
    - 30,00

    Então:

    `PrecoComLiq_Medio = (10 + 20 + 30) / 3 = 20,00`

    #### Importante
    Essas três colunas são **médias simples**, ou seja, todos os produtos têm o mesmo peso no cálculo.

    Já a coluna **Perc_Reajuste_Ponderado_%** segue outra lógica: ela é uma **média ponderada pelo valor de venda original**, para representar melhor o impacto financeiro real do reajuste.            
    """)    
    st.caption(
        "Percentual médio ponderado = ((Soma do Preço Ideal ÷ Soma do Preço de Venda Original) - 1) × 100."
    )

    df_resumo_grupo_subgrupo = gerar_resumo_grupo_subgrupo(df_visual, st.session_state.df_grupo)

    if df_resumo_grupo_subgrupo.empty:
        st.info("Sem dados para o resumo por Grupo e Subgrupo.")
    else:
        st.dataframe(
            df_resumo_grupo_subgrupo.style.format({
                "PrecoComLiq_Medio": "{:.2f}",
                "PrecoIdeal_Medio": "{:.2f}",
                "PrecoVendaOriginal_Medio": "{:.2f}",
                "PercReajuste_Medio": "{:.2f}",
                "ImpactoReajuste_Medio_RS": "{:.2f}",
                "Perc_Reajuste_Ponderado_%": "{:.2f}",
            }),
            use_container_width=True,
            height=320
        )

    st.markdown("## 📊 Resumo de Ajustes Médios por Grupo")
    df_resumo_grupo = gerar_resumo_grupo(df_visual, st.session_state.df_grupo)

    if df_resumo_grupo.empty:
        st.info("Sem dados para o resumo por Grupo.")
    else:
        st.dataframe(
            df_resumo_grupo.style.format({
                "PrecoComLiq_Medio": "{:.2f}",
                "PrecoIdeal_Medio": "{:.2f}",
                "PrecoVendaOriginal_Medio": "{:.2f}",
                "PercReajuste_Medio": "{:.2f}",
                "ImpactoReajuste_Medio_RS": "{:.2f}",
                "Perc_Reajuste_Ponderado_%": "{:.2f}",
            }),
            use_container_width=True,
            height=320
        )

    # =========================================================
    # SIMULAÇÕES SALVAS
    # =========================================================
    st.markdown("## 💾 Simulações Salvas (máximo 10)")

    if st.session_state.simulacoes:
        for i, sim in enumerate(st.session_state.simulacoes, start=1):
            grupos_txt = ", ".join(sim["grupos"]) if sim["grupos"] else "-"
            subgrupos_txt = ", ".join(sim["subgrupos"]) if sim["subgrupos"] else "-"

            with st.expander(
                f"Simulação {i} | {sim['datahora']} | Grupo(s): {grupos_txt} | Subgrupo(s): {subgrupos_txt}"
            ):
                st.write(f"**Percentual de reajuste:** {sim['perc_reajuste']}")
                st.write({
                    "Perc.Icms.Ven": sim["perc_icms"],
                    "Perc.Pis.Ven": sim["perc_pis"],
                    "Perc.Cofins.Ven": sim["perc_cofins"],
                    "Perc.Irpj.Ven": sim["perc_irpj"],
                    "Perc.Cs.Ven": sim["perc_cs"],
                    "Perc.Comis.ven": sim["perc_comis"],
                    "Perc.Custo.Op.Ven": sim["perc_custo_op"],
                    "Perc.Lucro.Ven": sim["perc_lucro"],
                })
                st.dataframe(
                    sim["resumo"].style.format({
                        "PrecoComLiq_Medio": "{:.2f}",
                        "PrecoIdeal_Medio": "{:.2f}",
                        "PrecoVendaOriginal_Medio": "{:.2f}",
                        "PercReajuste_Medio": "{:.2f}",
                        "ImpactoReajuste_Medio_RS": "{:.2f}",
                        "Perc_Reajuste_Ponderado_%": "{:.2f}",
                    }),
                    use_container_width=True
                )
    else:
        st.info("Nenhuma simulação salva até o momento.")

    # =========================================================
    # DOWNLOAD
    # =========================================================
    st.markdown("## 📥 Download")

    csv_download = preparar_download_csv(st.session_state.df_trabalho)

    st.download_button(
        label="Download CSV Ajustado",
        data=csv_download,
        file_name="tabela_preco_ajustada.csv",
        mime="text/csv",
    )
    ############ csv
    # =========================================================
    # DOWNLOADS CSV - PADRÃO BRASILEIRO
    # =========================================================
    st.markdown("## 📥 Downloads CSV por DataFrame")

    def preparar_csv_br(df):
        df_export = df.copy()

        for col in df_export.columns:
            if pd.api.types.is_numeric_dtype(df_export[col]):
                df_export[col] = df_export[col].apply(
                    lambda x: formatar_numero_br(x, 2) if pd.notna(x) else ""
                )

        return df_export.to_csv(index=False, sep=";", encoding="utf-8-sig")


    # 1) Tabela Ajustada
    csv_tabela_ajustada = preparar_csv_br(df_tabela)

    st.download_button(
        label="Download CSV - Tabela Ajustada",
        data=csv_tabela_ajustada,
        file_name="tabela_ajustada.csv",
        mime="text/csv",
    )

    # 2) Ranking das Maiores Distorções
    if not df_ranking.empty:
        df_ranking_export = df_ranking[colunas_ranking].head(top_n).copy()
        csv_ranking = preparar_csv_br(df_ranking_export)

        st.download_button(
            label="Download CSV - Ranking Distorções",
            data=csv_ranking,
            file_name="ranking_distorcoes.csv",
            mime="text/csv",
        )

    # 3) Resumo por Grupo e Subgrupo
    if not df_resumo_grupo_subgrupo.empty:
        csv_resumo_grupo_subgrupo = preparar_csv_br(df_resumo_grupo_subgrupo)

        st.download_button(
            label="Download CSV - Resumo Grupo e Subgrupo",
            data=csv_resumo_grupo_subgrupo,
            file_name="resumo_grupo_subgrupo.csv",
            mime="text/csv",
        )

    # 4) Resumo por Grupo
    if not df_resumo_grupo.empty:
        csv_resumo_grupo = preparar_csv_br(df_resumo_grupo)

        st.download_button(
            label="Download CSV - Resumo Grupo",
            data=csv_resumo_grupo,
            file_name="resumo_grupo.csv",
            mime="text/csv",
        )
    ############# PDF
    def gerar_pdf_resumo_grupo(df_resumo_grupo, tamanho_fonte=8, altura_linha=10):
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.2 * cm,
            leftMargin=1.2 * cm,
            topMargin=1.2 * cm,
            bottomMargin=1.2 * cm
        )

        styles = getSampleStyleSheet()

        estilo_titulo = ParagraphStyle(
            "TituloResumoGrupo",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1F4E78"),
            spaceAfter=8,
        )

        estilo_subtitulo = ParagraphStyle(
            "SubtituloResumoGrupo",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#555555"),
            spaceAfter=12,
        )

        elementos = []
        elementos.append(Paragraph("Resumo de Ajustes Médios por Grupo", estilo_titulo))
        elementos.append(
            Paragraph(
                "Relatório gerado automaticamente com base nos dados filtrados na tela.",
                estilo_subtitulo
            )
        )
        elementos.append(Spacer(1, 0.2 * cm))

        if df_resumo_grupo is None or df_resumo_grupo.empty:
            elementos.append(Paragraph("Sem dados para gerar o relatório.", styles["Normal"]))
            doc.build(elementos)
            buffer.seek(0)
            return buffer

        df_pdf = df_resumo_grupo.copy()

        # manter apenas as colunas desejadas
        colunas_ordem = [
            "Grupo",
            "desc_grupo",
            "Qtde_Itens",
            "Itens_Ajustados",
            #"PrecoComLiq_Medio",
            "PrecoIdeal_Medio",
            "PrecoVendaOriginal_Medio",
            #"PercReajuste_Medio",
            "ImpactoReajuste_Medio_RS",
            "Perc_Reajuste_Ponderado_%"
        ]
        colunas_existentes = [c for c in colunas_ordem if c in df_pdf.columns]
        df_pdf = df_pdf[colunas_existentes].copy()

        # formatar ANTES de renomear, com 2 casas
        colunas_numericas_pdf = [
            #"PrecoComLiq_Medio",
            "PrecoIdeal_Medio",
            "PrecoVendaOriginal_Medio",
            #"PercReajuste_Medio",
            "ImpactoReajuste_Medio_RS",
            "Perc_Reajuste_Ponderado_%"
        ]

        for col in colunas_numericas_pdf:
            if col in df_pdf.columns:
                df_pdf[col] = df_pdf[col].apply(
                    lambda x: formatar_numero_br(x, 2) if pd.notna(x) else ""
                )

        # renomear para exibição
        df_pdf = df_pdf.rename(columns={
            "Grupo": "Grupo",
            "desc_grupo": "Descrição Grupo",
            "Qtde_Itens": "Qtd Itens",
            #"Itens_Ajustados": "Qtd Ajustados",
            "PrecoComLiq_Medio": "Preço Com Liq Médio",
            "PrecoIdeal_Medio": "Preço Ideal Médio",
            "PrecoVendaOriginal_Medio": "Preço V Médio",
            #"PercReajuste_Medio": "% Reaj Médio",
            "ImpactoReajuste_Medio_RS": "Impacto Médio (R$)",
            "Perc_Reajuste_Ponderado_%": "% Reajuste Ponderado"
        })

        dados = [df_pdf.columns.tolist()] + df_pdf.fillna("").values.tolist()

        larguras = []
        for col in df_pdf.columns:
            if col == "Grupo":
                larguras.append(1.6 * cm)
            elif col == "Descrição Grupo":
                larguras.append(4.2 * cm)
            elif col in ["Qtd Itens", "Qtd Ajustados"]:
                larguras.append(2.0 * cm)
            else:
                larguras.append(2.5 * cm)

        tabela = Table(dados, colWidths=larguras, repeatRows=1)

        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),

            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAF2F8")]),

            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A6A6A6")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#7F7F7F")),

            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), tamanho_fonte),
            ("LEADING", (0, 1), (-1, -1), altura_linha),

            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (1, -1), "LEFT"),

            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ]))

        elementos.append(tabela)
        elementos.append(Spacer(1, 0.3 * cm))
        elementos.append(
            Paragraph(
                "Obs.: Os valores médios são apresentados com 2 casas decimais.",
                estilo_subtitulo
            )
        )

        doc.build(elementos)
        buffer.seek(0)
        return buffer
    # =========================================================
    # PDF - RESUMO DE AJUSTES MÉDIOS POR GRUPO
    # =========================================================
    st.markdown("## 📄 PDF Profissional")

    pdf_resumo_grupo = gerar_pdf_resumo_grupo(df_resumo_grupo)

    st.download_button(
        label="Download PDF - Resumo de Ajustes Médios por Grupo",
        data=pdf_resumo_grupo,
        file_name="resumo_ajustes_medios_grupo.pdf",
        mime="application/pdf",
    )
