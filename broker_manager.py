import pika
import requests
from requests.auth import HTTPBasicAuth
import time

class BrokerManager:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.api_url = 'http://localhost:15672/api'
        self.auth = HTTPBasicAuth('guest', 'guest')
        self._connect_to_rabbitmq()

        # Inicializa o conjunto de usuários com as filas já existentes
        # Filtra as filas de tópico para não as confundir com usuários diretos
        self.users = {q for q in self.listar_usuarios() if not q.endswith('_topicos')}

    def _connect_to_rabbitmq(self):
        """Estabelece a conexão com o RabbitMQ."""
        if self.connection and self.connection.is_open:
            return

        try:
            # heartbeat para manter a conexão viva
            self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', heartbeat=60))
            self.channel = self.connection.channel()
            print("[BrokerManager] Conectado ao RabbitMQ.")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[BrokerManager] ERRO CRÍTICO: Não foi possível conectar ao RabbitMQ: {e}")
            print("[BrokerManager] Certifique-se de que o RabbitMQ está rodando e acessível.")
            self.connection = None
            self.channel = None
            # Relevanta o erro para o chamador se a conexão inicial falhar
            raise ConnectionError(f"Falha ao conectar ao RabbitMQ: {e}") 

    def _ensure_connected(self):
        """Garante que a conexão e o canal estejam abertos. Tenta reconectar se necessário."""
        if not self.connection or self.connection.is_closed or not self.channel or self.channel.is_closed:
            print("[BrokerManager] Conexão ou canal perdidos. Tentando reconectar...")
            try:
                self._connect_to_rabbitmq()
            except ConnectionError: # Captura o erro relançado por _connect_to_rabbitmq
                print("[BrokerManager] Não foi possível restabelecer a conexão com o RabbitMQ.")
                return False
            
            if not self.connection or self.connection.is_closed:
                return False
        return True

    def _handle_precondition_failed(self, name, item_type="fila", durable_expected=True):
        """
        Lida com o erro PRECONDITION_FAILED, tentando excluir e recriar a fila/exchange.
        AVISO: Esta função PODE apagar dados de filas/exchanges existentes.
        """
        print(f"[BrokerManager][AVISO] Conflito de declaração para {item_type} '{name}'. "
              f"Tentando excluir e recriar com durable={durable_expected}. Isso APAGARÁ dados existentes.")
        try:
            if item_type == "fila":
                self.channel.queue_delete(queue=name)
                time.sleep(0.05) # Pequeno delay para garantir que o RabbitMQ processe a exclusão
                self.channel.queue_declare(queue=name, durable=durable_expected)
            elif item_type == "exchange":
                self.channel.exchange_delete(exchange=name)
                time.sleep(0.05) # Pequeno delay
                self.channel.exchange_declare(exchange=name, exchange_type='fanout', durable=durable_expected)
            print(f"[BrokerManager] {item_type.capitalize()} '{name}' recriada com sucesso como durable={durable_expected}.")
            return True
        except Exception as delete_e:
            print(f"[BrokerManager][ERRO] Falha ao excluir ou recriar {item_type} '{name}': {delete_e}")
            return False

    def criar_usuario(self, nome):
        if not self._ensure_connected():
            return "Erro: Conexão com RabbitMQ não estabelecida."

        # Verifica se o usuário já existe no conjunto local (cache simples)
        if nome in self.users:
            # Tenta declarar as filas para garantir que estejam duráveis, mesmo que o usuário já "exista"
            # Isso é crucial para corrigir estados inconsistentes de filas não-duráveis
            result_main = self._declare_queue_robustly(nome, "fila")
            result_topic = self._declare_queue_robustly(f"{nome}_topicos", "fila")
            
            if "Conflito irrecuperável" in result_main or "Conflito irrecuperável" in result_topic:
                 return f"Usuário '{nome}' já existe, mas houve um erro ao verificar/corrigir suas filas: {result_main} | {result_topic}"
            return f"Usuário '{nome}' já existe (filas verificadas/corrigidas)."

        # Se o usuário não está no cache local, tenta criá-lo
        result_main = self._declare_queue_robustly(nome, "fila")
        if "Conflito irrecuperável" in result_main:
            return f"Erro ao criar usuário '{nome}': {result_main}"

        result_topic = self._declare_queue_robustly(f"{nome}_topicos", "fila")
        if "Conflito irrecuperável" in result_topic:
            # Se a fila principal foi criada mas a de tópico falhou, tente reverter (opcionalmente)
            # ou apenas retorne o erro para que o usuário saiba que algo deu errado
            return f"Erro ao criar filas de tópico para '{nome}': {result_topic}"

        self.users.add(nome)
        return f"Usuário '{nome}' e suas filas criados/verificados com sucesso."

    def _declare_queue_robustly(self, queue_name, item_type):
        """
        Tenta declarar uma fila/exchange e lida com PRECONDITION_FAILED.
        Retorna uma mensagem de sucesso ou erro.
        """
        try:
            if item_type == "fila":
                self.channel.queue_declare(queue=queue_name, durable=True)
            elif item_type == "exchange":
                self.channel.exchange_declare(exchange=queue_name, exchange_type='fanout', durable=True)
            return "Sucesso na declaração."
        except pika.exceptions.ChannelClosedByBroker as e:
            if "PRECONDITION_FAILED" in str(e):
                if self._handle_precondition_failed(queue_name, item_type, True):
                    return "Sucesso na declaração (após correção)."
                else:
                    return f"Conflito irrecuperável para {item_type} '{queue_name}'. Detalhes: {e}"
            else:
                return f"Erro inesperado ao declarar {item_type} '{queue_name}': {e}"
        except Exception as e:
            return f"Erro geral ao declarar {item_type} '{queue_name}': {e}"


    def remover_usuario(self, nome):
        if not self._ensure_connected():
            return "Erro: Conexão com RabbitMQ não estabelecida."

        if nome not in self.users:
            return f"Usuário '{nome}' não encontrado na lista local."

        # Tenta remover a fila principal
        try:
            self.channel.queue_delete(queue=nome)
            print(f"[BrokerManager] Fila principal '{nome}' removida.")
        except pika.exceptions.ChannelClosedByBroker as e:
             print(f"[BrokerManager][AVISO] Fila principal '{nome}' não pôde ser removida, talvez não exista: {e}")
        except Exception as e:
            print(f"[BrokerManager][ERRO] Erro ao remover fila principal '{nome}': {e}")
            # Continua para tentar remover a fila de tópicos, mesmo com erro aqui

        # Tenta remover a fila de tópicos associada
        try:
            self.channel.queue_delete(queue=f"{nome}_topicos")
            print(f"[BrokerManager] Fila de tópicos '{nome}_topicos' removida.")
        except pika.exceptions.ChannelClosedByBroker as e:
            print(f"[BrokerManager][AVISO] Fila de tópicos '{nome}_topicos' não pôde ser removida, talvez não exista: {e}")
        except Exception as e:
            print(f"[BrokerManager][ERRO] Erro ao remover fila de tópicos '{nome}_topicos': {e}")
            
        self.users.remove(nome) # Remove do conjunto local, independente dos erros de exclusão no RabbitMQ
        return f"Usuário '{nome}' e suas filas associadas removidos (ou tentativa de remoção)."

    def listar_usuarios(self):
        """Lista usuários ativos (representados por filas não-tópicas) via API HTTP."""
        try:
            resp = requests.get(f"{self.api_url}/queues", auth=self.auth)
            resp.raise_for_status() 
            filas = resp.json()
            nomes_filas = [
                fila['name'] for fila in filas
                if not fila['name'].startswith('amq.') and not fila['name'].endswith('_topicos')
            ]
            return nomes_filas
        except requests.exceptions.ConnectionError:
            print("[BrokerManager] Erro de conexão ao listar usuários (API). O plugin RabbitMQ Management pode não estar rodando ou acessível.")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"[BrokerManager] Erro HTTP ao listar usuários: {e} - Resposta: {e.response.text}")
            return []
        except Exception as e:
            print(f"[BrokerManager] Erro inesperado ao listar usuários (API): {e}")
            return []

    def criar_topico(self, nome):
        if not self._ensure_connected():
            return "Erro: Conexão com RabbitMQ não estabelecida."

        return self._declare_queue_robustly(nome, "exchange")

    def remover_topico(self, nome):
        if not self._ensure_connected():
            return "Erro: Conexão com RabbitMQ não estabelecida."

        if nome.startswith("amq.") or nome == "":
            return f"Remoção do tópico '{nome}' não permitida (exchange do sistema)."
        try:
            self.channel.exchange_delete(exchange=nome)
            return f"Tópico '{nome}' removido com sucesso."
        except pika.exceptions.ChannelClosedByBroker as e:
            print(f"[BrokerManager][AVISO] Tópico '{nome}' não pôde ser removido, talvez não exista: {e}")
            return f"Aviso: Tópico '{nome}' não pôde ser removido ou não existe."
        except Exception as e:
            return f"Erro ao remover tópico '{nome}': {e}"

    def listar_topicos(self):
        """Lista tópicos (exchanges fanout não-internos) via API HTTP."""
        try:
            resp = requests.get(f"{self.api_url}/exchanges", auth=self.auth)
            resp.raise_for_status() 
            exchanges = resp.json()
            topicos = [ex['name'] for ex in exchanges if ex['type'] == 'fanout' and not ex['name'].startswith('amq.') and ex['name'] != '']
            return topicos
        except requests.exceptions.ConnectionError:
            print("[BrokerManager] Erro de conexão ao listar tópicos (API). O plugin RabbitMQ Management pode não estar rodando ou acessível.")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"[BrokerManager] Erro HTTP ao listar tópicos: {e} - Resposta: {e.response.text}")
            return []
        except Exception as e:
            print(f"[BrokerManager] Erro inesperado ao listar tópicos (API): {e}")
            return []

    def contar_mensagens_fila(self, fila):
        if not self._ensure_connected():
            return None # Não pode contar se não está conectado

        try:
            q = self.channel.queue_declare(queue=fila, passive=True)
            return q.method.message_count
        except pika.exceptions.ChannelClosedByBroker as e:
            print(f"[BrokerManager][AVISO] Fila '{fila}' não encontrada ao tentar contar mensagens: {e}")
            return None
        except Exception as e:
            print(f"[BrokerManager][ERRO] Erro ao contar mensagens da fila '{fila}': {e}")
            return None

    def close(self):
        """Fecha a conexão do RabbitMQ."""
        if self.channel and self.channel.is_open:
            try:
                self.channel.close()
                print("[BrokerManager] Canal fechado.")
            except Exception as e:
                print(f"[BrokerManager] Erro ao fechar canal: {e}")
        if self.connection and self.connection.is_open:
            try:
                self.connection.close()
                print("[BrokerManager] Conexão RabbitMQ fechada.")
            except Exception as e:
                print(f"[BrokerManager] Erro ao fechar conexão: {e}")

    def __del__(self):
        self.close()

# Exemplo de uso interativo (se este arquivo for executado diretamente)
if __name__ == "__main__":
    try:
        broker = BrokerManager()
    except ConnectionError as e:
        print(f"Não foi possível iniciar o BrokerManager: {e}")
        exit(1) # Sai se não conseguir conectar ao RabbitMQ

    while True:
        print("\n--- Menu do Broker Manager (Console) ---")
        print("1. Criar Usuário")
        print("2. Remover Usuário")
        print("3. Listar Usuários")
        print("4. Criar Tópico")
        print("5. Remover Tópico")
        print("6. Listar Tópicos")
        print("7. Contar Mensagens na Fila")
        print("8. Sair")
        
        escolha = input("Escolha uma opção: ")

        if escolha == '1':
            nome = input("Nome do usuário a criar: ")
            print(broker.criar_usuario(nome))
        elif escolha == '2':
            nome = input("Nome do usuário a remover: ")
            print(broker.remover_usuario(nome))
        elif escolha == '3':
            usuarios = broker.listar_usuarios()
            print("\n--- Usuários Ativos ---")
            if usuarios:
                for user in usuarios:
                    print(f"- {user}")
            else:
                print("Nenhum usuário ativo encontrado.")
        elif escolha == '4':
            nome = input("Nome do tópico a criar: ")
            print(broker.criar_topico(nome))
        elif escolha == '5':
            nome = input("Nome do tópico a remover: ")
            print(broker.remover_topico(nome))
        elif escolha == '6':
            topicos = broker.listar_topicos()
            print("\n--- Tópicos Disponíveis ---")
            if topicos:
                for topico in topicos:
                    print(f"- {topico}")
            else:
                print("Nenhum tópico encontrado.")
        elif escolha == '7':
            fila = input("Nome da fila para contar mensagens: ")
            count = broker.contar_mensagens_fila(fila)
            if count is not None:
                print(f"Mensagens na fila '{fila}': {count}")
            else:
                print(f"Não foi possível contar mensagens na fila '{fila}'.")
        elif escolha == '8':
            print("Saindo do Broker Manager.")
            broker.close()
            break
        else:
            print("Opção inválida. Tente novamente.")