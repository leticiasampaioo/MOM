import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
import time
import pika
from user_client import Usuario

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente de Chat RabbitMQ")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.usuario = None
        self.topicos_assinados = set()
        self.topico_selecionado = None
        self.usuario_selecionado = None
        self.mensagens_privadas = {}
        self.conversa_privada_atual = None

        self.configurar_interface()

    def configurar_interface(self):
        # === TOPO ===
        topo_frame = tk.Frame(self.root)
        topo_frame.pack(pady=10)

        tk.Label(topo_frame, text="Seu nome:").pack(side=tk.LEFT, padx=5)
        self.entrada_nome = tk.Entry(topo_frame, width=20)
        self.entrada_nome.pack(side=tk.LEFT)
        tk.Button(topo_frame, text="Entrar", bg="#4da6ff", command=self.entrar).pack(side=tk.LEFT, padx=5)

        self.titulo = tk.Entry(topo_frame, width=40, justify='center', state='readonly')
        self.titulo.insert(0, "APLICATIVO DE CHAT RABBITMQ")
        self.titulo.pack(side=tk.LEFT, padx=40)

        # === CONTEÚDO PRINCIPAL ===
        conteudo_frame = tk.Frame(self.root)
        conteudo_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Esquerda - Usuários e mensagens privadas
        esquerda_frame = tk.Frame(conteudo_frame)
        esquerda_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        usuarios_frame = tk.LabelFrame(esquerda_frame, text="Usuários")
        usuarios_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.lista_usuarios = tk.Listbox(usuarios_frame, width=25, height=10)
        self.lista_usuarios.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.lista_usuarios.bind('<<ListboxSelect>>', self.selecionar_usuario)

        privado_frame = tk.LabelFrame(esquerda_frame, text="Mensagem Privada")
        privado_frame.pack(fill=tk.X, pady=5)

        self.caixa_mensagens_privadas = scrolledtext.ScrolledText(privado_frame, height=8, state='disabled', bg="white")
        self.caixa_mensagens_privadas.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(privado_frame, text="Para:").pack(anchor='w')
        self.entrada_destinatario = tk.Entry(privado_frame)
        self.entrada_destinatario.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(privado_frame, text="Mensagem:").pack(anchor='w')
        self.entrada_msg_privada = tk.Entry(privado_frame)
        self.entrada_msg_privada.pack(fill=tk.X, padx=5, pady=2)
        self.entrada_msg_privada.bind('<Return>', lambda e: self.enviar_mensagem_privada())
        tk.Button(privado_frame, text="Enviar", bg="#4da6ff", command=self.enviar_mensagem_privada).pack(pady=5)

        # Direita - Tópicos e mural
        direita_frame = tk.Frame(conteudo_frame)
        direita_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        topicos_frame = tk.LabelFrame(direita_frame, text="Tópicos")
        topicos_frame.pack(fill=tk.X, pady=5)
        self.container_topicos = tk.Frame(topicos_frame)
        self.container_topicos.pack(fill=tk.BOTH, expand=True)
        tk.Button(topicos_frame, text="Criar Novo Tópico", bg="#6495ED", command=self.criar_novo_topico_dialog).pack(pady=5)

        mural_frame = tk.LabelFrame(direita_frame, text="Mural")
        mural_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.botao_topico = tk.Button(mural_frame, text="Nenhum Tópico Selecionado", bg="#ADD8E6", command=self.alternar_topico)
        self.botao_topico.pack(anchor='e', padx=5, pady=2)
        self.caixa_mural = scrolledtext.ScrolledText(mural_frame, width=50, height=10, state='disabled')
        self.caixa_mural.pack(fill=tk.BOTH, expand=True)

        frame_msg_mural = tk.Frame(mural_frame)
        frame_msg_mural.pack(fill=tk.X, pady=5)
        self.entrada_mural = tk.Entry(frame_msg_mural, state='disabled')
        self.entrada_mural.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entrada_mural.bind('<Return>', lambda e: self.publicar_no_topico())
        self.botao_publicar_mural = tk.Button(frame_msg_mural, text="Publicar", bg="#4da6ff", command=self.publicar_no_topico, state='disabled')
        self.botao_publicar_mural.pack(side=tk.LEFT)

        # Log
        log_frame = tk.LabelFrame(self.root, text="Registro de Atividades")
        log_frame.pack(fill=tk.X, padx=10, pady=10)
        self.caixa_log = scrolledtext.ScrolledText(log_frame, height=5, state='disabled')
        self.caixa_log.pack(fill=tk.X)
        self.caixa_log.config(state='disabled')

        self.registrar("Bem-vindo! Informe seu nome e clique em Entrar.")

    def entrar(self):
        nome = self.entrada_nome.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Por favor, informe seu nome de usuário.")
            self.registrar("ERRO: Tentativa de entrar sem nome de usuário.")
            return

        if self.usuario is not None:
            messagebox.showinfo("Info", f"Você já está conectado como {self.usuario.nome}.")
            return

        try:
            self.usuario = Usuario(nome)
        except pika.exceptions.AMQPConnectionError as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao servidor RabbitMQ. Verifique se está rodando.\nDetalhes: {e}")
            self.registrar(f"ERRO: Falha na conexão com RabbitMQ: {e}")
            self.usuario = None
            return
        except pika.exceptions.ChannelClosedByBroker as e:
            if "PRECONDITION_FAILED" in str(e):
                error_msg = (
                    f"A fila '{nome}' ou '{nome}_topicos' no RabbitMQ já existe com propriedades diferentes (durable=False).\n"
                    "Por favor, EXCLUA a(s) fila(s) problemática(s) na interface de gerenciamento do RabbitMQ (http://localhost:15672/api/queues) e tente novamente."
                    f"\nDetalhes técnicos: {e}"
                )
                messagebox.showerror("Erro de Fila Existente", error_msg)
                self.registrar(f"ERRO: {error_msg}")
                self.usuario = None
                return
            else:
                messagebox.showerror("Erro de Conexão", f"Um erro inesperado ocorreu ao conectar: {e}")
                self.registrar(f"ERRO: Erro inesperado ao conectar ao RabbitMQ: {e}")
                self.usuario = None
                return
        except Exception as e:
            messagebox.showerror("Erro Inesperado", f"Ocorreu um erro ao tentar conectar: {e}")
            self.registrar(f"ERRO: Erro geral ao tentar conectar: {e}")
            self.usuario = None
            return

        threading.Thread(
            target=self.usuario.receber_mensagens,
            args=(self.mostrar_mensagem,),
            daemon=True
        ).start()

        self.entrada_nome.config(state='readonly')

        self.carregar_topicos_assinados()

        self.listar_topicos()
        self.atualizar_lista_usuarios()

        if self.topicos_assinados:
            primeiro_topico = list(self.topicos_assinados)[0]
            self.visualizar_mural(primeiro_topico)
        else:
            self.botao_topico.config(text="Nenhum Tópico Selecionado")
            self.entrada_mural.config(state='disabled')
            self.botao_publicar_mural.config(state='disabled')
            self.caixa_mural.config(state='disabled')

        self.root.after(5000, self.atualizacoes_periodicas)

    def _on_closing(self):
        
        if self.usuario:
            self.registrar("INFO: Fechando conexão do usuário ao sair.")
            del self.usuario
        self.root.destroy()

    def carregar_topicos_assinados(self):
        
        arquivo_topicos = f"{self.usuario.nome}_topicos_assinados.txt"
        if os.path.exists(arquivo_topicos):
            try:
                with open(arquivo_topicos, "r", encoding="utf-8") as f:
                    for linha in f:
                        topico = linha.strip()
                        if topico:
                            sucesso = self.usuario.assinar_topico(topico)
                            if sucesso:
                                self.topicos_assinados.add(topico)
                            else:
                                self.registrar(f"AVISO: Falha ao re-assinar o tópico: {topico}")
            except Exception as e:
                self.registrar(f"ERRO: Erro ao carregar tópicos assinados do arquivo: {e}")

    def salvar_topicos_assinados(self):
        
        if self.usuario:
            try:
                with open(f"{self.usuario.nome}_topicos_assinados.txt", "w", encoding="utf-8") as f:
                    for t in self.topicos_assinados:
                        f.write(t + "\n")
            except Exception as e:
                self.registrar(f"ERRO: Erro ao salvar tópicos assinados: {e}")

    def atualizacoes_periodicas(self):
        
        if self.usuario:
            self.atualizar_lista_usuarios()
            self.listar_topicos()
        self.root.after(5000, self.atualizacoes_periodicas)

    def criar_novo_topico_dialog(self):
        
        if not self.usuario:
            messagebox.showwarning("Aviso", "Por favor, entre com seu nome primeiro.")
            self.registrar("AVISO: Tentativa de criar tópico sem estar logado.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Criar Novo Tópico")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Nome do Tópico:").pack(pady=10)
        entrada_novo_topico = tk.Entry(dialog, width=30)
        entrada_novo_topico.pack(pady=5)

        def confirmar_criacao():
            novo_topico = entrada_novo_topico.get().strip()
            if novo_topico:
                if self.usuario.publicar_em_topico(novo_topico, "Novo tópico criado!"):
                    messagebox.showinfo("Sucesso", f"Tópico '{novo_topico}' criado e mensagem inicial publicada.")
                    self.registrar(f"INFO: Tópico '{novo_topico}' criado.")
                    self.assinar_topico(novo_topico)
                    dialog.destroy()
                else:
                    messagebox.showerror("Erro", f"Não foi possível criar ou publicar no tópico '{novo_topico}'.")
                    self.registrar(f"ERRO: Falha ao criar ou publicar no tópico '{novo_topico}'.")
            else:
                messagebox.showwarning("Aviso", "O nome do tópico não pode ser vazio.")
                self.registrar("AVISO: Tentativa de criar tópico com nome vazio.")

        tk.Button(dialog, text="Criar", command=confirmar_criacao).pack(pady=10)
        self.root.wait_window(dialog)

    def listar_topicos(self):
        
        if not self.usuario:
            return

        for widget in self.container_topicos.winfo_children():
            widget.destroy()

        try:
            topicos = self.usuario.listar_topicos()
        except Exception as e:
            self.registrar(f"ERRO: Erro ao listar tópicos: {e}")
            return

        for topico in topicos:
            frame = tk.Frame(self.container_topicos)
            frame.pack(fill=tk.X, pady=2)

            entrada = tk.Entry(frame, width=25)
            entrada.insert(0, topico)
            entrada.config(state='readonly')

            if topico in self.topicos_assinados:
                entrada.config(bg="#b2f0c2") # Verde claro
                texto_botao = "Visualizar"
                comando = lambda t=topico: self.visualizar_mural(t)
            else:
                entrada.config(bg="white") # Cor padrão, corrigido do SystemButtonFace
                texto_botao = "Assinar"
                comando = lambda t=topico: self.assinar_topico(t)

            entrada.pack(side=tk.LEFT)
            tk.Button(frame, text=texto_botao, bg="#4da6ff", command=comando).pack(side=tk.LEFT, padx=5)

    def assinar_topico(self, topico):
        
        if not self.usuario:
            return

        try:
            sucesso = self.usuario.assinar_topico(topico)
            if sucesso:
                self.topicos_assinados.add(topico)
                self.salvar_topicos_assinados()
                self.listar_topicos()
                self.visualizar_mural(topico)
            else:
                self.registrar(f"AVISO: Falha ao assinar o tópico {topico}.")
        except Exception as e:
            self.registrar(f"ERRO: Erro ao assinar tópico: {e}")

    def visualizar_mural(self, topico):
        
        if topico not in self.topicos_assinados:
            messagebox.showinfo("Informação", f"Você precisa assinar '{topico}' primeiro para visualizá-lo.")
            self.registrar(f"AVISO: Tentativa de visualizar tópico não assinado: {topico}.")
            return

        self.topico_selecionado = topico
        self.botao_topico.config(text=f"Mural: {topico}")

        self.caixa_mural.config(state='normal')
        self.entrada_mural.config(state='normal')
        self.botao_publicar_mural.config(state='normal')

        self.caixa_mural.delete(1.0, tk.END)

        try:
            with open(f"{topico}.txt", "r", encoding="utf-8") as f:
                for msg in f.readlines():
                    self.caixa_mural.insert(tk.END, msg)
        except FileNotFoundError:
            self.caixa_mural.insert(tk.END, f"[{topico}] Nenhuma mensagem anterior neste mural.\n")

        self.caixa_mural.config(state='disabled')
        self.caixa_mural.yview(tk.END)
        self.entrada_mural.focus_set()

    def alternar_topico(self):
        
        if self.topico_selecionado:
            messagebox.showinfo("Tópico Atual", f"Você está visualizando o tópico: '{self.topico_selecionado}'")
        else:
            messagebox.showinfo("Tópico Atual", "Nenhum tópico selecionado. Assine ou crie um.")

    def publicar_no_topico(self):
        
        if not self.usuario:
            return

        topico = self.topico_selecionado
        mensagem = self.entrada_mural.get().strip()

        if not topico:
            messagebox.showwarning("Aviso", "Por favor, selecione um tópico para publicar.")
            self.registrar("AVISO: Tentativa de publicar sem tópico selecionado.")
            return
        if not mensagem:
            messagebox.showwarning("Aviso", "Por favor, digite uma mensagem para publicar.")
            self.registrar("AVISO: Tentativa de publicar mensagem vazia.")
            return

        try:
            sucesso = self.usuario.publicar_em_topico(topico, mensagem)
            if not sucesso:
                self.registrar(f"AVISO: Falha ao publicar em '{topico}'.")
                return
        except Exception as e:
            self.registrar(f"ERRO: Erro inesperado ao publicar no tópico: {e}")
            return

        self.entrada_mural.delete(0, tk.END)
        self.registrar(f"INFO: Mensagem publicada em '{topico}': {mensagem}")

    def atualizar_lista_usuarios(self):
        
        if not self.usuario:
            return

        selecao_indices = self.lista_usuarios.curselection()
        selecao_nomes = [self.lista_usuarios.get(i) for i in selecao_indices]

        self.lista_usuarios.delete(0, tk.END)
        try:
            usuarios = self.usuario.listar_usuarios()
            for user in sorted(usuarios):
                if user != self.usuario.nome:
                    self.lista_usuarios.insert(tk.END, user)
        except Exception as e:
            self.registrar(f"ERRO: Erro ao listar usuários: {e}")

        for nome in selecao_nomes:
            try:
                idx = self.lista_usuarios.get(0, tk.END).index(nome)
                self.lista_usuarios.selection_set(idx)
            except ValueError:
                pass

    def selecionar_usuario(self, event):
        
        selecao = self.lista_usuarios.curselection()
        if selecao:
            usuario_selecionado = self.lista_usuarios.get(selecao[0])
            self.entrada_destinatario.delete(0, tk.END)
            self.entrada_destinatario.insert(0, usuario_selecionado)
            self.entrada_msg_privada.focus()

            self.conversa_privada_atual = usuario_selecionado
            self._carregar_mensagens_privadas(usuario_selecionado)

    def _carregar_mensagens_privadas(self, usuario_para_carregar):
        
        self.caixa_mensagens_privadas.config(state='normal')
        self.caixa_mensagens_privadas.delete(1.0, tk.END)

        mensagens = self.mensagens_privadas.get(usuario_para_carregar, [])
        for msg in mensagens:
            self.caixa_mensagens_privadas.insert(tk.END, msg + '\n')

        self.caixa_mensagens_privadas.config(state='disabled')
        self.caixa_mensagens_privadas.yview(tk.END)

    def enviar_mensagem_privada(self):
        
        if not self.usuario:
            return

        destinatario = self.entrada_destinatario.get().strip()
        mensagem = self.entrada_msg_privada.get().strip()

        if not destinatario or not mensagem:
            messagebox.showwarning("Aviso", "Por favor, selecione um usuário e digite uma mensagem para enviar.")
            self.registrar("AVISO: Tentativa de enviar mensagem privada incompleta.")
            return

        # Obter o timestamp atual para a mensagem enviada
        timestamp = time.strftime("[%H:%M]")
        mensagem_com_timestamp = f"{timestamp} Você: {mensagem}"

        try:
            sucesso = self.usuario.enviar_para_usuario(destinatario, mensagem)
            if sucesso:
                # Adiciona a mensagem formatada (com timestamp) ao histórico local
                if destinatario not in self.mensagens_privadas:
                    self.mensagens_privadas[destinatario] = []
                self.mensagens_privadas[destinatario].append(mensagem_com_timestamp)

                # Se estiver conversando com o destinatário, atualiza a caixa de chat privada
                if self.conversa_privada_atual == destinatario:
                    self._adicionar_mensagem_privada_ui(mensagem_com_timestamp)

                self.registrar(f"INFO: Você enviou para {destinatario}: {mensagem}")
                self.entrada_msg_privada.delete(0, tk.END)
            else:
                self.registrar(f"AVISO: Falha ao enviar mensagem privada para {destinatario}.")
        except Exception as e:
            self.registrar(f"ERRO: Erro inesperado ao enviar mensagem privada: {e}")

    # --- Métodos para processar e exibir mensagens recebidas ---

    def mostrar_mensagem(self, msg):
        
        self.root.after(0, self._processar_e_exibir_mensagem_na_ui, msg)

    def _processar_e_exibir_mensagem_na_ui(self, msg):
        
        if msg.startswith("PRIVADO:"):
            try:
                _, remetente, mensagem_conteudo = msg.split(":", 2)
                timestamp = time.strftime("[%H:%M]") # Adiciona timestamp para mensagens recebidas
                mensagem_formatada = f"{timestamp} [{remetente}] {mensagem_conteudo}"

                # Armazena a mensagem no histórico local
                if remetente not in self.mensagens_privadas:
                    self.mensagens_privadas[remetente] = []
                self.mensagens_privadas[remetente].append(mensagem_formatada)

                # Se o remetente for o usuário com quem estamos conversando, exibe na UI
                if self.conversa_privada_atual == remetente:
                    self._adicionar_mensagem_privada_ui(mensagem_formatada)

                self.registrar(f"INFO: Mensagem privada de '{remetente}': {mensagem_conteudo}")
            except ValueError:
                self.registrar(f"ERRO: Formato de mensagem privada inválido: {msg}")
        elif msg.startswith("[") and "]" in msg:
            try:
                primeiro_colchete = msg.index("[")
                segundo_colchete = msg.index("]")
                nome_topico = msg[primeiro_colchete + 1 : segundo_colchete]

                if nome_topico in self.topicos_assinados:
                    try:
                        with open(f"{nome_topico}.txt", "a", encoding="utf-8") as f:
                            f.write(msg + '\n')
                    except Exception as e:
                        self.registrar(f"ERRO: Erro ao salvar mensagem no arquivo do tópico '{nome_topico}': {e}")
                else:
                    self.registrar(f"INFO: Mensagem recebida para tópico não assinado: '{nome_topico}' - {msg}")

                if self.topico_selecionado == nome_topico:
                    self._adicionar_mensagem_mural(nome_topico, msg + '\n')
                    self.registrar(f"INFO: Mensagem recebida em '{nome_topico}': {msg}")
                else:
                    pass

            except (ValueError, IndexError):
                 self.registrar(f"ERRO: Formato de mensagem de tópico inválido: {msg}")
        else:
            self.registrar(f"INFO: MENSAGEM GERAL RECEBIDA: {msg}")

    def _adicionar_mensagem_mural(self, topico, mensagem):
        
        if self.topico_selecionado == topico:
            self.caixa_mural.config(state='normal')
            self.caixa_mural.insert(tk.END, mensagem)
            self.caixa_mural.config(state='disabled')
            self.caixa_mural.yview(tk.END)

    def _adicionar_mensagem_privada_ui(self, mensagem):
        
        self.caixa_mensagens_privadas.config(state='normal')
        self.caixa_mensagens_privadas.insert(tk.END, mensagem + '\n')
        self.caixa_mensagens_privadas.config(state='disabled')
        self.caixa_mensagens_privadas.yview(tk.END)

    def registrar(self, msg):
        
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        self.root.after(0, self._adicionar_log, f"{timestamp} {msg}\n")

    def _adicionar_log(self, text):
        
        self.caixa_log.config(state='normal')
        self.caixa_log.insert(tk.END, text)
        self.caixa_log.config(state='disabled')
        self.caixa_log.yview(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()