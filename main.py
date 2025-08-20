from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import requests, bitrix
import re

app = FastAPI()

CAMPOS_VENCIDOS_RJ = ["UF_CRM_1745350930427","UF_CRM_1745350938898","UF_CRM_1745351181",
    "UF_CRM_1745351211", "UF_CRM_1745351248","UF_CRM_1745351275","UF_CRM_1745351301",
    "UF_CRM_1745351327","UF_CRM_1745351352","UF_CRM_1745351376","UF_CRM_1745351405",
    "UF_CRM_1745351431","UF_CRM_1745351489","UF_CRM_1745351517","UF_CRM_1745351546"
]

CAMPOS_VENCIDOS_PROTON = ["UF_CRM_1755280142","UF_CRM_1755280154","UF_CRM_1755280163",
    "UF_CRM_1755280173","UF_CRM_1755280182","UF_CRM_1755280199","UF_CRM_1755280209",
    "UF_CRM_1755280219","UF_CRM_1755280241","UF_CRM_1755280251","UF_CRM_1755280507",
    "UF_CRM_1755280259","UF_CRM_1755280270","UF_CRM_1755280281","UF_CRM_1755280298"
]

class Titulo:
    def __init__(self, texto: str, tipo: str):
        padrao = r"^(.*) - (.*) - (.*) - (.*) - (.*) - (.*)$"
        if re.fullmatch(padrao, texto) is None:
            raise ValueError("O título não está no formato adequado.")
        
        componentes = texto.split("-")

        self.texto = texto
        self.idTitulo = componentes[0].strip()
        self.parcela = componentes[1].strip()
        self.emissao = componentes[2].strip()
        self.vencimento = componentes[3].strip()
        self.valor = float(componentes[4].strip().replace("R$", "").replace(",", "."))
        self.valorSemJuros = float(componentes[5].strip().replace("R$", "").replace(",", "."))
        self.tipo = tipo

def listar_titulos(dicionario: dict) -> dict:
        titulos = {}

        for campo in CAMPOS_VENCIDOS_RJ:
            valor = dicionario[campo]

            if valor:
                titulo = Titulo(valor, 'rj')
                titulos[titulo.idTitulo] = titulo

        for campo in CAMPOS_VENCIDOS_PROTON:
            valor = dicionario[campo]

            if valor:
                titulo = Titulo(valor, 'proton')
                titulos[titulo.idTitulo] = titulo
    
        return titulos

@app.post('/enviar-para-negativacao')
async def enviar_para_negativacao(id: str):
    try:
        card = bitrix.deal_get(id)
    except requests.exceptions.HTTPError as http_err:
        raise HTTPException(status_code=500, detail=f"Erro HTTP ao conectar com Bitrix24: {http_err}")
    except requests.exceptions.RequestException as err:
        print(f"Erro de conexão ao Bitrix24: {err}")
        raise HTTPException(status_code=500, detail=f"Erro de conexão ao Bitrix24: {err}")

    if card.get("STAGE_ID") != "C14:6":
        return JSONResponse({
            "status": "fail",
            "message": "O négocio não está na coluna esperada."
        }, status_code=400)

    titulos_a_negativar : str = card.get("UF_CRM_1739193194466")

    if not titulos_a_negativar:
        bitrix.deal_update(id, {"STAGE_ID" : "C14:7"})

        return JSONResponse({
            "status": "partial_success",
            "message": "O pedido foi processado, mas o campo necessário está em branco.",
        }, status_code=206)

    lista_a_negativar = titulos_a_negativar.replace(" ", "").split(";")

    titulos_registrados = listar_titulos(card)
    
    titulos_encontrados = []

    for titulo in lista_a_negativar:
        busca = titulos_registrados.get(titulo)

        if not busca:
            bitrix.deal_update(id, {"STAGE_ID" : "C14:7"})
            return JSONResponse({
                "status": "partial_success",
                "message": "O pedido foi processado, mas um ou mais títulos são inválidos.",
            }, status_code=206)

        titulos_encontrados.append(busca)

    for titulo in titulos_encontrados:
        bitrix.deal_add({
            "TITLE": card.get("TITLE"), # Nome do Cliente
            "UF_CRM_1732556583": card.get("UF_CRM_1732556583"), # ID Externo
            "UF_CRM_1717013491407": card.get("UF_CRM_1717013491407"), # ID do cliente
            "UF_CRM_664E0602C9B87": card.get("UF_CRM_664E0602C9B87"), # CNPJ/CPF
            "UF_CRM_1732556420": card.get("UF_CRM_1732556420"), # Responsável pela Cobrança
            "UF_CRM_1732556462": card.get("UF_CRM_1732556462"),  # Responsavel pela Negativação
            "UF_CRM_1732556235": card.get("UF_CRM_1732556235"), # ID do Vendedor HCG
            "UF_CRM_1732556265": card.get("UF_CRM_1732556265"), # Nome do Vendedor HCG
            "UF_CRM_1733856514": card.get("UF_CRM_1733856514"), # ID do Vendedor HIPERCG
            "UF_CRM_1733856494": card.get("UF_CRM_1733856494"), # Nome do Vendedor HIPERCG
            "OPPORTUNITY": titulo.valor,
            "UF_CRM_1745350930427": titulo.texto if titulo.tipo == "rj" else None,
            "UF_CRM_1755280142": titulo.texto if titulo.tipo == "proton" else None,

            "ASSIGNED_BY_ID": card.get("ASSIGNED_BY_ID"), # Responsável
            "CONTACT_IDS": card.get("CONTACT_ID"), # Contatos
            "CATEGORY_ID": '16', # Número do Pipeline
            "STAGE_ID": 'C16:NEW' # Fase do Negócio
        })

    bitrix.deal_update(id, {"STAGE_ID": "C14:PREPARATION"})

    return JSONResponse({
        "status": "sucess",
        "message": "O pedido foi processado e os títulos criados no funil de negativação",
    }, status_code=200)

@app.post("/alterar-status")
def alterar_status(id: str):
    try:
        card = bitrix.deal_get(id)
    except requests.exceptions.HTTPError as http_err:
        raise HTTPException(status_code=500, detail=f"Erro HTTP ao conectar com Bitrix24: {http_err}")
    except requests.exceptions.RequestException as err:
        print(f"Erro de conexão ao Bitrix24: {err}")
        raise HTTPException(status_code=500, detail=f"Erro de conexão ao Bitrix24: {err}")
    
    estagio = card.get('STAGE_ID')
    id_externo = card.get('UF_CRM_1732556583')

    if not id_externo:
        return JSONResponse(
            {
                "status": "fail",
                "message": "O campo obrigatório 'UF_CRM_1732556583' está em branco. Impossivel processar o pedido.",
            }, 
            status_code=400
        )

    cards_cobranca = bitrix.deal_list({"CATEGORY_ID": "14", "=UF_CRM_1732556583": id_externo}, [])
    
    if not cards_cobranca:
        return JSONResponse(
            {
                "status": "fail",
                "message": "Não foi encontrado negócio equivalente no funil 14.",
            }, 
            status_code=200
        )
    
    correspondente = cards_cobranca[0]
    status_negativacao_correspondente = correspondente.get('UF_CRM_1755287872064')
    id_correspondente = correspondente.get('ID')

    if estagio == 'C16:NEW' or estagio == 'C16:FINAL_INVOICE': # a negativar / iniciar segunda negativação
        if not status_negativacao_correspondente:
            bitrix.deal_update(id_correspondente, {"UF_CRM_1755287872064": "258"})
            return JSONResponse({
                "status": "sucess",
                "message": "Status alterado para 'SOLICITADO'.",
            }, status_code=200)
        
    elif estagio == 'C16:PREPARATION' or estagio == 'C16:LOSE':
        bitrix.deal_update(id_correspondente, {"UF_CRM_1755287872064": "250"})
        return JSONResponse({
                "status": "sucess",
                "message": "Status alterado para 'NEGATIVADO'.",
        }, status_code=200)
    
    elif estagio == 'C16:EXECUTING' or estagio == 'C16:WON':
        outros_cards = bitrix.deal_list(
            {"!ID": id, "CATEGORY_ID": "16", "=UF_CRM_1732556583": id_externo, 
             "!STAGE_ID": ['C16:EXECUTING', 'C16:WON']}, 
            []
        )

        if not outros_cards:
            bitrix.deal_update(id_correspondente, {"UF_CRM_1755287872064": "252"})
            return JSONResponse({
                "status": "sucess",
                "message": "Status alterado para 'BAIXADO'.",
            }, status_code=200)
    
    # status: Negativado - 250;  Baixado - 252; Solicitado - 258

@app.post('/retirar-negativacao')
def retirar_negativacao(id: str):
    try:
        card = bitrix.deal_get(id)
    except requests.exceptions.HTTPError as http_err:
        raise HTTPException(status_code=500, detail=f"Erro HTTP ao conectar com Bitrix24: {http_err}")
    except requests.exceptions.RequestException as err:
        print(f"Erro de conexão ao Bitrix24: {err}")
        raise HTTPException(status_code=500, detail=f"Erro de conexão ao Bitrix24: {err}")
    
    if card.get("STAGE_ID") != "C14:WON":
        return JSONResponse({
            "status": "fail",
            "message": "O négocio não está na coluna esperada."
        }, status_code=400)

    id_externo = card.get('UF_CRM_1732556583')
    status_negativacao = card.get('UF_CRM_1755287872064')

    if status_negativacao == '250' or status_negativacao == '258':
        cards_negativados = bitrix.deal_list({"CATEGORY_ID": "16", "=UF_CRM_1732556583": id_externo}, [])

        titulos_pagos = [
            card.get(campo) for campo in CAMPOS_VENCIDOS_RJ + CAMPOS_VENCIDOS_PROTON 
            if card.get(campo)
        ]

        for card_negativado in cards_negativados:
            id_negativado = card_negativado.get('ID')
            estagio_negativado = card_negativado.get('STAGE_ID')
            titulo_rj = card_negativado.get('UF_CRM_1745350930427')
            titulo_proton = card_negativado.get('UF_CRM_1755280142')

            if titulo_rj in titulos_pagos or titulo_proton in titulos_pagos:
                if estagio_negativado == 'C16:NEW' or estagio_negativado == 'C16:PREPARATION':
                    bitrix.deal_update(id_negativado, {"STAGE_ID": 'C16:PREPAYMENT_INVOIC'})
                elif estagio_negativado == 'C16:FINAL_INVOICE' or estagio_negativado == 'C16:LOSE':
                    bitrix.deal_update(id_negativado, {"STAGE_ID": 'C16:1'})
        
        return JSONResponse({
            "status": "sucess",
            "message": "Títulos equivalentes atualizados no funil 16.",
        }, status_code=200)