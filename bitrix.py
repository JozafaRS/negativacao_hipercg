import requests
from tenacity import retry, wait_fixed, stop_after_attempt
from time import sleep
from os import environ
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

WEBHOOK = environ.get('URL_WEBHOOK')

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def deal_list_batch(filtro: dict, selecao: list, order: dict = {}) -> dict:
    """
    Função auxiliar da função deal_list\n
    Retorna apenas 50 cards por execução
    """
    resposta = requests.post(
            WEBHOOK + 'crm.deal.list.json',
            json={
                'order': {'ID': 'ASC'},
                'filter': filtro,
                'select': selecao,
                'order': order,
                'start': -1,
            },
            headers={
                'Content-Type': 'application/json'
            }
    )

    if resposta.status_code != 200:
        raise requests.ConnectionError(f'Erro de Conexão: {resposta.status_code}')

    return resposta.json()

def deal_list(filtro: dict, selecao: list, order: dict = {}) -> list:
    """Retorna todos os cards do Bitrix com os filtros especificados"""
    cards = []
    id = 0

    while True:
        filtro['>ID'] = id

        dados = deal_list_batch(filtro, selecao, order)

        if not dados['result']:
            break

        id = dados['result'][-1]['ID']
        

        cards.extend(dados['result'])
        

        sleep(0.5)

    return cards

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def deal_update(id: int, campos: dict) -> dict:
    """Atualiza os campos especificados para o card"""
    resposta = requests.post(
            WEBHOOK + 'crm.deal.update.json',
            json={
                'id': id,
                'fields': campos
            },
            headers={
                'Content-Type': 'application/json'
            }
    )

    if resposta.status_code != 200:
        raise requests.ConnectionError(f'Erro de Conexão: {resposta.status_code}')

    return resposta.json()

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def deal_get(id: int) -> dict:
    """Retorna as informações do card pesquisado"""
    print('Buscando card...')
    resposta = requests.post(
        WEBHOOK + 'crm.deal.get.json',
        json={
            'id': id
        },
        headers={
            'Content-Type': 'application/json'
        }
    )

    if resposta.status_code != 200:
        raise requests.ConnectionError(f'Erro de Conexão: {resposta.status_code}')

    return resposta.json()['result']

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def deal_add(campos: dict) -> dict:
    """Cria um novo card com os campos especificados para o card"""
    resposta = requests.post(
            WEBHOOK + 'crm.deal.add.json',
            json={
                'fields': campos
            },
            headers={
                'Content-Type': 'application/json'
            }
    )

    if resposta.status_code != 200:
        raise requests.ConnectionError(f'Erro de Conexão: {resposta.status_code}')

    return resposta.json()

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def contact_add(campos: dict) -> dict:
    """Cria um novo card com os campos especificados para o card"""
    resposta = requests.post(
            WEBHOOK + 'crm.contact.add.json',
            json={
                'fields': campos
            },
            headers={
                'Content-Type': 'application/json'
            }
    )

    if resposta.status_code != 200:
        raise requests.ConnectionError(f'Erro de Conexão: {resposta.status_code}')

    return resposta.json()['result']