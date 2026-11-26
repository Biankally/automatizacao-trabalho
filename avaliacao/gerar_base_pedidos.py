"""Gera as bases de pedidos INVENTADOS para treinar e testar o classificador.

- teste.json: escrita a mao, frases variadas e casos dificeis. NUNCA entra no treino.
- treino_v1.json: base pequena (v1 e v2), gerada por combinacao de modelos de frase.
- treino_v3.json: base ampliada (v3): mais verbos, mais objetos, mais jeitos de falar.

Rodar: python avaliacao/gerar_base_pedidos.py
O sorteio usa semente fixa: rodar de novo gera exatamente as mesmas bases.
"""

from __future__ import annotations

import itertools
import json
import random
import re
import unicodedata
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "pedidos"

# ---------------------------------------------------------------- teste (a mao)
TESTE = [
    # completar: preencher o que esta vazio
    ("tem uns emails em branco no cadastro, puxa do rh pra mim", "completar"),
    ("preenche o telefone de quem ainda não tem, usando a lista do RH", "completar"),
    ("quero que os CPFs vazios sejam completados com a base do RH", "completar"),
    ("completa só as células vazias de endereço", "completar"),
    ("onde o cargo estiver faltando, coloque o que está na planilha da diretoria", "completar"),
    ("falta o e-mail de alguns servidores, consegue completar pela matrícula?", "completar"),
    ("preencher as datas de admissão que ficaram em branco", "completar"),
    ("nas linhas sem setor, traga o setor da outra planilha", "completar"),
    ("complementar o CEP de quem está sem", "completar"),
    ("adiciona o ramal nas linhas onde ele não aparece", "completar"),
    ("os telefones que estão vazios precisam ser preenchidos com os da origem", "completar"),
    ("só preencher o que está vazio, não mexe no resto", "completar"),
    ("faltam lotações no cadastro, completar usando a matrícula", "completar"),
    ("buscar no RH o email de quem não tem email", "completar"),
    ("completar dados faltantes de endereço a partir da base nova", "completar"),
    ("vê quem está sem nome social e preenche com o da outra base", "completar"),
    ("pegar os cargos que faltam da planilha do RH", "completar"),
    ("preenchimento dos CPFs em branco", "completar"),
    ("colocar o telefone onde a célula estiver vazia", "completar"),
    ("quero completar os e-mails ausentes", "completar"),
    ("completa o setor de quem ficou sem", "completar"),
    ("as matrículas novas estão sem email, puxar do RH", "completar"),
    # trocar: substituir valor existente
    ("o email de muita gente está desatualizado, troca pelo do RH", "trocar"),
    ("atualiza os telefones com a lista nova", "trocar"),
    ("substituir os endereços antigos pelos da base atual", "trocar"),
    ("os cargos mudaram, corrige conforme a planilha da diretoria", "trocar"),
    ("deixa o setor igual ao que está no RH", "trocar"),
    ("sobrescreve o CEP com o da origem", "trocar"),
    ("trocar os e-mails errados pelos certos", "trocar"),
    ("a lotação está errada em várias linhas, atualizar pela matrícula", "trocar"),
    ("alinhar os ramais do cadastro com os do RH", "trocar"),
    ("corrigir os nomes sociais usando a base nova", "trocar"),
    ("quero que o telefone fique igual ao da outra planilha mesmo se já tiver um", "trocar"),
    ("atualização dos emails com base no RH", "trocar"),
    ("muda o cargo para o que está na planilha nova", "trocar"),
    ("substitui as datas de admissão pelas corretas", "trocar"),
    ("os CPFs estão com erro, troque pelos da base oficial", "trocar"),
    ("sincronizar o email do cadastro com o do RH", "trocar"),
    ("refaz os endereços com a versão atual", "trocar"),
    ("corrige os setores que estão diferentes do RH", "trocar"),
    ("atualizar telefone desatualizado", "trocar"),
    ("trocar email antigo por email novo", "trocar"),
    ("renovar os dados de lotação com a planilha atual", "trocar"),
    ("ajusta os cargos para ficarem iguais aos do RH", "trocar"),
    # fora do escopo
    ("faz um gráfico de pizza com os setores", "fora_do_escopo"),
    ("quanto é a soma da coluna de salários?", "fora_do_escopo"),
    ("apaga as linhas duplicadas", "fora_do_escopo"),
    ("ordena a planilha por nome", "fora_do_escopo"),
    ("manda essa planilha por email pro chefe", "fora_do_escopo"),
    ("cria uma tabela dinâmica das vendas", "fora_do_escopo"),
    ("calcular a média das notas", "fora_do_escopo"),
    ("transforma a planilha em PDF", "fora_do_escopo"),
    ("conta quantos servidores tem em cada setor", "fora_do_escopo"),
    ("pinta de vermelho quem está atrasado", "fora_do_escopo"),
    ("junta todas as abas numa só", "fora_do_escopo"),
    ("filtra só quem é do setor financeiro", "fora_do_escopo"),
    ("coloca senha na planilha", "fora_do_escopo"),
    ("traduz os cabeçalhos para inglês", "fora_do_escopo"),
    ("exclui os servidores aposentados", "fora_do_escopo"),
    ("separa a planilha em uma por setor", "fora_do_escopo"),
    ("me diz qual setor gastou mais", "fora_do_escopo"),
    ("cria uma planilha nova com o modelo de férias", "fora_do_escopo"),
    ("renomeia a coluna B para Nome Completo", "fora_do_escopo"),
    ("faz um dashboard das inspeções do mês", "fora_do_escopo"),
    ("remove os espaços extras dos nomes", "fora_do_escopo"),
    ("gera um relatório com o total por mês", "fora_do_escopo"),
]

# ---------------------------------------------------------------- treino (combinacao)
OBJETOS_V1 = ["o email", "os emails", "o telefone", "o cpf", "o endereço", "o cargo"]
OBJETOS_V3 = OBJETOS_V1 + ["os telefones", "o e-mail", "os endereços", "o setor", "a data de admissão",
                           "o cep", "o nome social", "a lotação", "o ramal", "os cargos", "a matrícula funcional",
                           "o celular", "a unidade", "o departamento"]
FONTES_V1 = ["com o do rh", "pela planilha do rh", "usando a base nova"]
FONTES_V3 = FONTES_V1 + ["da planilha de cadastro", "conforme a planilha da diretoria", "com os dados da origem",
                         "pela base antiga", "a partir da outra planilha", "pela matrícula", "pelo cpf",
                         "usando a lista atual", "com a base oficial", ""]

COMPLETAR_V1 = ["completar {o} vazio {f}", "preencha {o} que falta {f}", "complete {o} em branco {f}"]
COMPLETAR_V3 = COMPLETAR_V1 + [
    "preencher {o} onde estiver vazio {f}", "completa {o} de quem não tem {f}", "adicionar {o} que está faltando {f}",
    "colocar {o} nas células em branco {f}", "preenche {o} ausente {f}", "puxar {o} para as linhas sem {o} {f}",
    "completar os campos vazios de {o} {f}", "trazer {o} que falta {f}", "quem está sem {o}, preencher {f}",
    "só completar {o} que estiver em branco {f}", "faltando {o}, completar {f}",
]
TROCAR_V1 = ["atualize {o} {f}", "substitua {o} {f}", "corrija {o} {f}"]
TROCAR_V3 = TROCAR_V1 + [
    "atualizar {o} desatualizado {f}", "trocar {o} errado {f}", "substituir {o} antigo {f}", "corrigir {o} {f}",
    "sobrescrever {o} {f}", "deixar {o} igual {f}", "alinhar {o} {f}", "mudar {o} {f}",
    "troca {o} pelo correto {f}", "atualiza {o} mesmo se já tiver {f}", "{o} está errado, corrigir {f}",
]
FORA_V1 = ["faça um gráfico de {x}", "some {x}", "apague {x}", "ordene {x}", "calcule a média de {x}"]
FORA_V3 = FORA_V1 + [
    "crie um gráfico com {x}", "conte quantos são {x}", "exclua {x}", "filtre {x}", "remova duplicados de {x}",
    "envie por email {x}", "gere um pdf de {x}", "crie uma tabela dinâmica de {x}", "traduza {x}",
    "junte as abas de {x}", "formate as cores de {x}", "proteja com senha {x}", "renomeie {x}",
    "imprima {x}", "agrupe por mês {x}", "destaque em vermelho {x}", "faça um resumo de {x}",
]
COISAS_V1 = ["as vendas", "os valores", "os salários"]
COISAS_V3 = COISAS_V1 + ["a planilha", "os funcionários", "as notas", "os pedidos do mês", "as colunas",
                         "os setores", "os atrasados", "as despesas", "os nomes"]


def _normalizar(texto: str) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", sem))


def _gerar(modelos_c, modelos_t, modelos_f, objetos, fontes, coisas, por_classe, semente):
    rnd = random.Random(semente)
    proibidos = {_normalizar(t) for t, _ in TESTE}

    def amostra(modelos, combos, classe):
        frases = sorted({" ".join(m.format(o=a, f=b, x=a).split()) for m in modelos for a, b in combos})
        frases = [f for f in frases if _normalizar(f) not in proibidos]
        rnd.shuffle(frases)
        return [(f, classe) for f in frases[:por_classe]]

    combos = list(itertools.product(objetos, fontes))
    combos_f = [(c, "") for c in coisas]
    base = amostra(modelos_c, combos, "completar") + amostra(modelos_t, combos, "trocar") + \
        amostra(modelos_f, combos_f, "fora_do_escopo")
    rnd.shuffle(base)
    return base


def main() -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    bases = {
        "teste": TESTE,
        "treino_v1": _gerar(COMPLETAR_V1, TROCAR_V1, FORA_V1, OBJETOS_V1, FONTES_V1, COISAS_V1, 15, 1),
        "treino_v3": _gerar(COMPLETAR_V3, TROCAR_V3, FORA_V3, OBJETOS_V3, FONTES_V3, COISAS_V3, 150, 3),
    }
    for nome, dados in bases.items():
        (PASTA / f"{nome}.json").write_text(json.dumps([list(d) for d in dados], ensure_ascii=False, indent=0),
                                           encoding="utf-8")
        contagem = {c: sum(1 for _, r in dados if r == c) for c in ("completar", "trocar", "fora_do_escopo")}
        print(f"{nome}: {len(dados)} pedidos {contagem}")


if __name__ == "__main__":
    main()
