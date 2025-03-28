import os
import re
import glob
import pandas as pd

# =========================
# CONFIGURAÇÕES DO USUÁRIO
# =========================

# ➤ Defina o caminho da pasta onde estão os arquivos PLAN*.ESTABELE e o arquivo de municípios
BASE_DIR = r"CAMINHO/DA/SUA/PASTA/AQUI"  # Exemplo: r"C:\Users\usuario\Downloads\base_dados"

# ➤ Nome do arquivo de municípios (formato CSV separado por ";")
MUNICIPIOS_FILENAME = "MUNICIPIOS.MUNICCSV"

# ➤ Nome do arquivo Excel de saída
OUTPUT_FILENAME = "CNPJs_filtrados.xlsx"

# ➤ CNAEs a serem filtrados (pode incluir qualquer lista válida)
CNAES_CONTABILIDADE = ["6920601", "6920602", "7020400"]

# ➤ Situação cadastral ativa (padrão: "02")
SITUACAO_ATIVA = "02"

# ➤ UF (estado) a ser filtrado (padrão: "MG")
UF_FILTRADA = "MG"

# ➤ Índice da coluna onde está o CNAE principal no arquivo PLAN*.ESTABELE
CNAE_PRINCIPAL_INDEX = 11

# ➤ Tamanho do chunk para leitura de arquivos grandes
CHUNK_SIZE = 100000

# =============================
# LEITURA DE ARQUIVOS NECESSÁRIOS
# =============================

# Caminho completo do arquivo de municípios
MUNICIPIOS_FILE = os.path.join(BASE_DIR, MUNICIPIOS_FILENAME)

# Arquivos PLAN*.ESTABELE ordenados corretamente
PLAN_PATTERN = r"PLAN(\d+)"
estabelecimentos_files = sorted(
    glob.glob(os.path.join(BASE_DIR, "PLAN*.ESTABELE")),
    key=lambda path: int(re.search(PLAN_PATTERN, path).group(1))
)

# Leitura da base de municípios
municipios_df = pd.read_csv(
    MUNICIPIOS_FILE,
    sep=";",
    encoding="latin1",
    dtype=str
)
municipios_df.rename(
    columns={
        municipios_df.columns[0]: "codigo_municipio",
        municipios_df.columns[1]: "municipio"
    },
    inplace=True
)

# =============================
# FUNÇÕES AUXILIARES
# =============================

def montar_endereco(row: pd.Series) -> str:
    tipo = str(row.get("tipo_logradouro", "")).strip().strip('"')
    logradouro = str(row.get("logradouro", "")).strip().strip('"')
    numero = str(row.get("num_endereco", "")).strip().strip('"')
    complemento = str(row.get("complemento", "")).strip().strip('"')
    bairro = str(row.get("bairro", "")).strip().strip('"')
    cep = str(row.get("cep", "")).strip().strip('"')

    endereco = f"{tipo} {logradouro}, {numero}"
    if complemento and complemento.lower() != "nan":
        endereco += f", {complemento}"
    endereco += f" - {bairro} - CEP: {cep}"
    return endereco

def formatar_telefone(ddd: str, telefone: str) -> str:
    ddd = str(ddd).strip().strip('"')
    telefone = str(telefone).strip().strip('"')
    if ddd and telefone and telefone.lower() != "nan":
        return ddd + telefone
    return ""

def processar_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    col_map = {
        0:  "cnpj_base",
        1:  "cod_filial",
        2:  "dv",
        5:  "sit_cad",
        CNAE_PRINCIPAL_INDEX: "cnae_principal",
        13: "tipo_logradouro",
        14: "logradouro",
        15: "num_endereco",
        16: "complemento",
        17: "bairro",
        18: "cep",
        19: "UF",
        20: "codigo_municipio",
        21: "DDD1",
        22: "telefone1",
        23: "DDD2",
        24: "telefone2",
        25: "DDD3",
        26: "telefone3",
        27: "email"
    }

    chunk.rename(columns=col_map, inplace=True, errors="ignore")

    if "cnae_principal" not in chunk.columns or "UF" not in chunk.columns:
        return pd.DataFrame()

    chunk = chunk[
        (chunk["UF"] == UF_FILTRADA) &
        (chunk["sit_cad"].str.strip('"') == SITUACAO_ATIVA)
    ]
    chunk = chunk.copy()

    if chunk.empty:
        return pd.DataFrame()

    chunk["cnae_principal"] = chunk["cnae_principal"].str.strip('"')
    chunk = chunk[chunk["cnae_principal"].isin(CNAES_CONTABILIDADE)]
    if chunk.empty:
        return pd.DataFrame()

    chunk["CNPJ"] = (
        chunk["cnpj_base"].str.strip('"') +
        chunk["cod_filial"].str.strip('"') +
        chunk["dv"].str.strip('"')
    )

    chunk["Endereco"] = chunk.apply(montar_endereco, axis=1)

    chunk["Telefone1"] = chunk.apply(lambda row: formatar_telefone(row.get("DDD1", ""), row.get("telefone1", "")), axis=1)
    chunk["Telefone2"] = chunk.apply(lambda row: formatar_telefone(row.get("DDD2", ""), row.get("telefone2", "")), axis=1)
    chunk["Telefone3"] = chunk.apply(lambda row: formatar_telefone(row.get("DDD3", ""), row.get("telefone3", "")), axis=1)

    colunas_finais = [
        "CNPJ", "UF", "cnae_principal", "codigo_municipio",
        "Endereco", "email", "Telefone1", "Telefone2", "Telefone3"
    ]
    return chunk[colunas_finais]

# =============================
# PROCESSAMENTO PRINCIPAL
# =============================

resultados = []

for arquivo in estabelecimentos_files:
    print(f"Processando arquivo: {arquivo}")
    for chunk in pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        header=None,
        chunksize=CHUNK_SIZE,
        dtype=str,
        low_memory=False
    ):
        df_processado = processar_chunk(chunk)
        if not df_processado.empty:
            resultados.append(df_processado)

if resultados:
    df_filtrado = pd.concat(resultados, ignore_index=True)
else:
    df_filtrado = pd.DataFrame(
        columns=[
            "CNPJ", "UF", "cnae_principal",
            "codigo_municipio", "Endereco", "email",
            "Telefone1", "Telefone2", "Telefone3"
        ]
    )

print(f"Total de registros após o filtro: {len(df_filtrado)}")

df_final = df_filtrado.merge(municipios_df, on="codigo_municipio", how="left")
df_final = df_final[
    [
        "CNPJ", "UF", "municipio",
        "cnae_principal", "Endereco",
        "email", "Telefone1", "Telefone2", "Telefone3"
    ]
]

# =============================
# EXPORTAÇÃO PARA EXCEL
# =============================

caminho_saida = os.path.join(BASE_DIR, OUTPUT_FILENAME)
MAX_LINHAS_POR_ABA = 1_000_000

total_linhas = len(df_final)
num_abas = (total_linhas // MAX_LINHAS_POR_ABA) + (1 if total_linhas % MAX_LINHAS_POR_ABA else 0)

with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
    for i in range(num_abas):
        inicio = i * MAX_LINHAS_POR_ABA
        fim = inicio + MAX_LINHAS_POR_ABA
        df_subset = df_final.iloc[inicio:fim]
        sheet_name = f"Parte_{i+1}"
        df_subset.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"Salvando aba '{sheet_name}' com {len(df_subset)} linhas.")

print(f"Processamento finalizado. Arquivo salvo em: {caminho_saida}")
