import pika
import requests
from requests.auth import HTTPBasicAuth
import json

class Usuario:
    def __init__(self, nome):
        self.nome = nome
        self.connection = None
        self.channel = None
        self.conectar()

        # Fila para mensagens privadas (entre usuários)
        self.channel.queue_declare(queue=nome)

        # Fila para mensagens de tópicos
        self.channel.queue_declare(queue=f"{nome}_topicos")  # <- REMOVIDO exclusive=True

    def conectar(self):
        """Estabelece conexão com o RabbitMQ"""
        if not self.connection or self.connection.is_closed:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            self.channel = self.connection.channel()

    def receber_mensagens(self, callback):
        """
        Consome mensagens das filas (privadas e de tópicos) e chama o callback
        que deve atualizar o mural da interface com a mensagem recebida.
        """
        def on_message(ch, method, properties, body):
            try:
                mensagem = body.decode('utf-8')
                callback(mensagem)
            except Exception as e:
                print(f"Erro ao processar mensagem: {e}")

        # Consome mensagens privadas
        self.channel.basic_consume(
            queue=self.nome,
            on_message_callback=on_message,
            auto_ack=True
        )

        # Consome mensagens de tópicos
        self.channel.basic_consume(
            queue=f"{self.nome}_topicos",
            on_message_callback=on_message,
            auto_ack=True
        )

        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
        except Exception as e:
            print(f"Erro no consumo: {e}")

    def enviar_para_usuario(self, destino, mensagem):
        """Envia mensagem privada diretamente para outro usuário"""
        try:
            self.conectar()
            mensagem_formatada = f"PRIVADO:{self.nome}:{mensagem}"
            self.channel.basic_publish(
                exchange='',
                routing_key=destino,
                body=mensagem_formatada
            )
        except Exception as e:
            print(f"Erro ao enviar mensagem privada: {e}")

    def assinar_topico(self, nome_topico):
        """Assina um tópico e o vincula à fila de tópicos do usuário"""
        try:
            self.conectar()
            self.channel.exchange_declare(
                exchange=nome_topico,
                exchange_type='fanout'
            )
            self.channel.queue_bind(
                exchange=nome_topico,
                queue=f"{self.nome}_topicos"
            )
            return True
        except Exception as e:
            print(f"Erro ao assinar tópico: {e}")
            return False

    def publicar_em_topico(self, nome_topico, mensagem):
        """Publica uma mensagem em um tópico para todos os assinantes"""
        try:
            self.conectar()
            mensagem_formatada = f"[{nome_topico}]{self.nome}:{mensagem}"
            self.channel.basic_publish(
                exchange=nome_topico,
                routing_key='',
                body=mensagem_formatada
            )
            return True
        except Exception as e:
            print(f"Erro ao publicar no tópico: {e}")
            return False

    def listar_topicos(self):
        """Consulta os tópicos disponíveis via API HTTP do RabbitMQ"""
        url = 'http://localhost:15672/api/exchanges/%2F'  # %2F é o vhost "/"
        auth = HTTPBasicAuth('guest', 'guest')
        try:
            response = requests.get(url, auth=auth)
            if response.status_code == 200:
                exchanges = response.json()
                topicos = [
                    ex['name'] for ex in exchanges
                    if ex['type'] == 'fanout' and not ex['name'].startswith('amq.')
                ]
                return topicos
            return []
        except Exception as e:
            print(f"Erro ao listar tópicos: {e}")
            return []

    def listar_usuarios(self):
        """Consulta as filas de usuários (exceto as de tópicos)"""
        url = 'http://localhost:15672/api/queues/%2F'
        auth = HTTPBasicAuth('guest', 'guest')
        try:
            response = requests.get(url, auth=auth)
            if response.status_code == 200:
                queues = response.json()
                usuarios = [
                    q['name'] for q in queues
                    if not q['name'].startswith('amq.') and not q['name'].endswith('_topicos')
                ]
                return usuarios
            return []
        except Exception as e:
            print(f"Erro ao listar usuários: {e}")
            return []

    def __del__(self):
        """Fecha a conexão ao destruir o objeto"""
        if hasattr(self, 'connection') and self.connection:
            try:
                self.connection.close()
            except:
                pass
