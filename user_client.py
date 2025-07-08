import pika
import threading

class Usuario:
    def __init__(self, nome):
        self.nome = nome
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=nome)

    def receber_mensagens(self):
        def callback(ch, method, properties, body):
            print(f"[Mensagem recebida] {body.decode()}")
        self.channel.basic_consume(queue=self.nome, on_message_callback=callback, auto_ack=True)
        print(f"[{self.nome}] Aguardando mensagens...")
        self.channel.start_consuming()

    def enviar_para_usuario(self, destino, mensagem):
        self.channel.basic_publish(exchange='', routing_key=destino, body=f"De {self.nome}: {mensagem}")
        print(f"[Enviado para {destino}] {mensagem}")

    def assinar_topico(self, nome_topico):
        self.channel.exchange_declare(exchange=nome_topico, exchange_type='fanout')
        self.channel.queue_bind(exchange=nome_topico, queue=self.nome)
        print(f"[{self.nome}] Assinado ao tópico '{nome_topico}'")

    def publicar_em_topico(self, nome_topico, mensagem):
        self.channel.basic_publish(exchange=nome_topico, routing_key='', body=f"De {self.nome} no tópico '{nome_topico}': {mensagem}")
        print(f"[Publicado em {nome_topico}] {mensagem}")

if __name__ == "__main__":
    nome = input("Digite seu nome de usuário: ")
    user = Usuario(nome)
    threading.Thread(target=user.receber_mensagens, daemon=True).start()

    while True:
        print("\n1. Enviar mensagem direta\n2. Assinar tópico\n3. Enviar para tópico\n4. Sair")
        op = input("Escolha: ")

        if op == '1':
            dest = input("Destinatário: ")
            msg = input("Mensagem: ")
            user.enviar_para_usuario(dest, msg)
        elif op == '2':
            topico = input("Tópico: ")
            user.assinar_topico(topico)
        elif op == '3':
            topico = input("Tópico: ")
            msg = input("Mensagem: ")
            user.publicar_em_topico(topico, msg)
        elif op == '4':
            print("Encerrando...")
            break
        else:
            print("Opção inválida.")