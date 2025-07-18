import pika
import requests
from requests.auth import HTTPBasicAuth
import json
import threading
import time 

class Usuario:
    def __init__(self, nome):
        self.nome = nome
        self.consume_connection = None
        self.consume_channel = None
        
        # Inicializa a conexão do consumidor imediatamente
        self._conectar_consumidor()

        # Declara as filas para este usuário no canal do consumidor
        # Filas duráveis para persistir mensagens e configurações após reinícios do RabbitMQ
        self.consume_channel.queue_declare(queue=nome, durable=True)
        self.consume_channel.queue_declare(queue=f"{nome}_topicos", durable=True) 

    #Estabelece a conexão para consumo de mensagens
    def _conectar_consumidor(self):
       
        if not self.consume_connection or self.consume_connection.is_closed:
            print(f"[{self.nome}] Conectando consumidor ao RabbitMQ...")
            # Usa ConnectionParameters com heartbeat para detecção de conexão perdida
            # Um heartbeat de 60 segundos ajuda a manter a conexão viva e detectar desconexões
            params = pika.ConnectionParameters('localhost', heartbeat=60) 
            self.consume_connection = pika.BlockingConnection(params)
            self.consume_channel = self.consume_connection.channel()
            print(f"[{self.nome}] Consumidor conectado.")

    #Consome mensagens das filas
    def receber_mensagens(self, callback):
      
        def on_message(ch, method, properties, body):
            try:
                mensagem = body.decode('utf-8')
                # O callback (mostrar_mensagem na UI) agora será chamado
                # para processar e exibir a mensagem na thread principal da UI.
                callback(mensagem) 
                # Se auto_ack=False, você faria o ack aqui: ch.basic_ack(method.delivery_tag)
            except Exception as e:
                print(f"[{self.nome}] Erro ao processar mensagem no callback: {e}")

        self.consume_channel.basic_qos(prefetch_count=1)

        # Configura o consumo de mensagens privadas
        self.consume_channel.basic_consume(
            queue=self.nome,
            on_message_callback=on_message,
            auto_ack=True # Para simplicidade, auto_ack é True. Considere ack manual em produção.
        )

        # Configura o consumo de mensagens de tópicos
        self.consume_channel.basic_consume(
            queue=f"{self.nome}_topicos",
            on_message_callback=on_message,
            auto_ack=True
        )

        print(f"[{self.nome}] Iniciando consumo de mensagens...")
        try:
            self.consume_channel.start_consuming()
        except KeyboardInterrupt:
            print(f"[{self.nome}] Consumo interrompido por KeyboardInterrupt.")
            self.consume_channel.stop_consuming()
        except pika.exceptions.StreamClosedError as e:
            # Erro comum quando a conexão é perdida. Tenta reconectar e reiniciar o consumo.
            print(f"[{self.nome}] StreamClosedError: O stream de conexão foi fechado. Tentando reconectar... {e}")
            time.sleep(5) # Pequena pausa antes de tentar reconectar
            self._conectar_consumidor() # Tenta reconectar
            self.receber_mensagens(callback) # Tenta reiniciar o consumo
        except Exception as e:
            # Outros erros inesperados no consumo. Tenta reconectar.
            print(f"[{self.nome}] Erro inesperado no consumo: {e}. Tentando reconectar...")
            time.sleep(5) # Pequena pausa
            self._conectar_consumidor()
            self.receber_mensagens(callback)

    #Cria e retorna uma nova conexão e canal para operações de publicação
    def _obter_canal_publicacao(self):
        
        # heartbeat de 60 segundos para as conexões de publicação também.
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', heartbeat=60))
        return connection, connection.channel()

    def enviar_para_usuario(self, destino, mensagem):
       
        publish_connection = None
        publish_channel = None
        try:
            publish_connection, publish_channel = self._obter_canal_publicacao()
            mensagem_formatada = f"PRIVADO:{self.nome}:{mensagem}"
            publish_channel.basic_publish(
                exchange='',          # Exchange padrão para envio direto para filas
                routing_key=destino,  # A fila de destino é o nome do usuário
                body=mensagem_formatada.encode('utf-8') # Codifica a mensagem para bytes
            )
            print(f"[{self.nome}] Enviada mensagem para '{destino}': {mensagem}")
            return True
        except Exception as e:
            print(f"Erro ao enviar mensagem privada: {e}")
            return False
        finally:
            # Garante que o canal e a conexão de publicação sejam fechados.
            if publish_channel and publish_channel.is_open:
                publish_channel.close()
            if publish_connection and publish_connection.is_open:
                publish_connection.close()

    def assinar_topico(self, nome_topico):
        
        publish_connection = None
        publish_channel = None
        try:
            publish_connection, publish_channel = self._obter_canal_publicacao()
            # Declara o exchange como 'fanout' e durável. Fanout envia para todas as filas ligadas.
            publish_channel.exchange_declare(
                exchange=nome_topico,
                exchange_type='fanout',
                durable=True 
            )
            # Vincula a fila de tópicos do usuário ao exchange
            publish_channel.queue_bind(
                exchange=nome_topico,
                queue=f"{self.nome}_topicos"
            )
            print(f"[{self.nome}] Assinou o tópico '{nome_topico}'.")
            return True
        except Exception as e:
            print(f"Erro ao assinar tópico: {e}")
            return False
        finally:
            if publish_channel and publish_channel.is_open:
                publish_channel.close()
            if publish_connection and publish_connection.is_open:
                publish_connection.close()

    def publicar_em_topico(self, nome_topico, mensagem):
    
        publish_connection = None
        publish_channel = None
        try:
            publish_connection, publish_channel = self._obter_canal_publicacao()
            # Garante que o exchange exista antes de publicar.
            publish_channel.exchange_declare(
                exchange=nome_topico,
                exchange_type='fanout',
                durable=True
            )
            mensagem_formatada = f"[{nome_topico}]{self.nome}: {mensagem}"
            publish_channel.basic_publish(
                exchange=nome_topico, # Publica no exchange do tópico
                routing_key='',      # Routing key vazia para exchanges fanout
                body=mensagem_formatada.encode('utf-8')
            )
            print(f"[{self.nome}] Publicada mensagem no tópico '{nome_topico}': {mensagem}")
            return True
        except Exception as e:
            print(f"Erro ao publicar no tópico: {e}")
            return False
        finally:
            if publish_channel and publish_channel.is_open:
                publish_channel.close()
            if publish_connection and publish_connection.is_open:
                publish_connection.close()

    def listar_topicos(self):
        
        url = 'http://localhost:15672/api/exchanges/%2F'  # %2F é o vhost padrão "/"
        auth = HTTPBasicAuth('guest', 'guest') # Credenciais padrão do RabbitMQ
        try:
            response = requests.get(url, auth=auth)
            if response.status_code == 200:
                exchanges = response.json()
                # Filtra apenas os exchanges do tipo 'fanout' (usados para tópicos)
                # e que não são os exchanges internos do RabbitMQ (amq.)
                topicos = [
                    ex['name'] for ex in exchanges
                    if ex['type'] == 'fanout' and not ex['name'].startswith('amq.')
                ]
                return topicos
            else:
                print(f"Erro ao listar tópicos: Status {response.status_code} - {response.text}")
                return []
        except requests.exceptions.ConnectionError:
            print("Erro de conexão ao tentar listar tópicos. O servidor RabbitMQ Management pode não estar rodando ou acessível.")
            return []
        except Exception as e:
            print(f"Erro inesperado ao listar tópicos: {e}")
            return []

    def listar_usuarios(self):
        
        url = 'http://localhost:15672/api/queues/%2F'
        auth = HTTPBasicAuth('guest', 'guest')
        try:
            response = requests.get(url, auth=auth)
            if response.status_code == 200:
                queues = response.json()
                # Filtra filas que não são internas (amq.) e que não são filas de tópicos (terminam com _topicos)
                usuarios = [
                    q['name'] for q in queues
                    if not q['name'].startswith('amq.') and not q['name'].endswith('_topicos')
                ]
                return usuarios
            else:
                print(f"Erro ao listar usuários: Status {response.status_code} - {response.text}")
                return []
        except requests.exceptions.ConnectionError:
            print("Erro de conexão ao tentar listar usuários. O servidor RabbitMQ Management pode não estar rodando ou acessível.")
            return []
        except Exception as e:
            print(f"Erro inesperado ao listar usuários: {e}")
            return []

    def __del__(self):
       
        if hasattr(self, 'consume_connection') and self.consume_connection:
            try:
                if not self.consume_connection.is_closed:
                    self.consume_connection.close()
                    print(f"[{self.nome}] Conexão de consumo fechada.")
            except Exception as e:
                print(f"Erro ao fechar conexão de consumo em __del__: {e}")