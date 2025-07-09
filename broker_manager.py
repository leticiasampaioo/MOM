import pika
import requests
from requests.auth import HTTPBasicAuth

class BrokerManager:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.api_url = 'http://localhost:15672/api'
        self.auth = HTTPBasicAuth('guest', 'guest')

        # Inicializa o conjunto de usuários com as filas já existentes
        self.users = set(self.listar_usuarios())

    def criar_usuario(self, nome):
        if nome in self.users:
            return f"Usuário '{nome}' já existe."
        self.channel.queue_declare(queue=nome)
        self.users.add(nome)
        return f"Usuário '{nome}' criado com sucesso."

    def remover_usuario(self, nome):
        if nome in self.users:
            self.channel.queue_delete(queue=nome)
            self.users.remove(nome)
            return f"Usuário '{nome}' removido."
        return f"Usuário '{nome}' não encontrado."

    def listar_usuarios(self):
        try:
            resp = requests.get(f"{self.api_url}/queues", auth=self.auth)
            resp.raise_for_status()
            filas = resp.json()
            nomes_filas = [fila['name'] for fila in filas]
            return nomes_filas
        except Exception as e:
            return [f"Erro ao listar usuários: {e}"]

    def criar_topico(self, nome):
        self.channel.exchange_declare(exchange=nome, exchange_type='fanout')
        return f"Tópico '{nome}' criado."

    def remover_topico(self, nome):
        if nome.startswith("amq.") or nome == "":
            return f"Remoção do tópico '{nome}' não permitida (exchange do sistema)."
        try:
            self.channel.exchange_delete(exchange=nome)
            return f"Tópico '{nome}' removido com sucesso."
        except Exception as e:
            return f"Erro ao remover tópico '{nome}': {e}"

    def listar_topicos(self):
        try:
            resp = requests.get(f"{self.api_url}/exchanges", auth=self.auth)
            resp.raise_for_status()
            exchanges = resp.json()
            topicos = [ex['name'] for ex in exchanges if ex['type'] == 'fanout' and ex['name'] != '']
            return topicos
        except Exception as e:
            return [f"Erro ao listar tópicos: {e}"]

    def contar_mensagens_fila(self, fila):
        try:
            q = self.channel.queue_declare(queue=fila, passive=True)
            return q.method.message_count
        except pika.exceptions.ChannelClosedByBroker:
            return None
