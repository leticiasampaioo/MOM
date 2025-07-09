import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
from user_client import Usuario

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente de Chat")
        self.usuario = None
        self.topicos_assinados = set()
        self.topico_selecionado = None
        self.usuario_selecionado = None

        self.configurar_interface()

    def configurar_interface(self):
        # === TOPO ===
        topo_frame = tk.Frame(self.root)
        topo_frame.pack(pady=10)

        tk.Label(topo_frame, text="Seu nome:").pack(side=tk.LEFT, padx=5)
        self.entrada_nome = tk.Entry(topo_frame, width=20)
        self.entrada_nome.pack(side=tk.LEFT)
        tk.Button(topo_frame, text="Entrar", bg="#4da6ff", command=self.entrar).pack(side=tk.LEFT, padx=5)

        self.titulo = tk.Entry(topo_frame, width=40, justify='center')
        self.titulo.insert(0, "APLICATIVO DE CHAT")
        self.titulo.pack(side=tk.LEFT, padx=40)

        # === CONTEÚDO PRINCIPAL ===
        conteudo_frame = tk.Frame(self.root)
        conteudo_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Esquerda - Usuários e mensagens privadas
        esquerda_frame = tk.Frame(conteudo_frame)
        esquerda_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        usuarios_frame = tk.LabelFrame(esquerda_frame, text="Usuários Online")
        usuarios_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.lista_usuarios = tk.Listbox(usuarios_frame, width=25, height=15)
        self.lista_usuarios.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.lista_usuarios.bind('<<ListboxSelect>>', self.selecionar_usuario)

        privado_frame = tk.LabelFrame(esquerda_frame, text="Mensagem Privada")
        privado_frame.pack(fill=tk.X, pady=5)
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

        mural_frame = tk.LabelFrame(direita_frame, text="Mural")
        mural_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.botao_topico = tk.Button(mural_frame, text="Selecionar Tópico", bg="#4da6ff", command=self.alternar_topico)
        self.botao_topico.pack(anchor='e', padx=5, pady=2)
        self.caixa_mural = scrolledtext.ScrolledText(mural_frame, width=50, height=10)
        self.caixa_mural.pack(fill=tk.BOTH, expand=True)

        frame_msg_mural = tk.Frame(mural_frame)
        frame_msg_mural.pack(fill=tk.X, pady=5)
        self.entrada_mural = tk.Entry(frame_msg_mural)
        self.entrada_mural.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entrada_mural.bind('<Return>', lambda e: self.publicar_no_topico())
        tk.Button(frame_msg_mural, text="Publicar", bg="#4da6ff", command=self.publicar_no_topico).pack(side=tk.LEFT)

        # Log
        log_frame = tk.LabelFrame(self.root, text="Registro de Atividades")
        log_frame.pack(fill=tk.X, padx=10, pady=10)
        self.caixa_log = scrolledtext.ScrolledText(log_frame, height=5)
        self.caixa_log.pack(fill=tk.X)
        self.caixa_log.config(state='disabled')

        self.registrar("Bem-vindo! Informe seu nome e clique em Entrar.")

    def entrar(self):
        nome = self.entrada_nome.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Por favor, informe seu nome de usuário.")
            return

        try:
            self.usuario = Usuario(nome)
        except Exception as e:
            messagebox.showerror("Erro de conexão", f"Não foi possível conectar ao servidor RabbitMQ:\n{e}")
            return

        threading.Thread(
            target=self.usuario.receber_mensagens,
            args=(self.mostrar_mensagem,),
            daemon=True
        ).start()

        self.registrar(f"Conectado como {nome}")

        # Carregar tópicos assinados (arquivo local)
        self.carregar_topicos_assinados()

        self.listar_topicos()
        self.atualizar_lista_usuarios()

        # Mostrar mural do primeiro tópico assinado
        if self.topicos_assinados:
            primeiro_topico = list(self.topicos_assinados)[0]
            self.visualizar_mural(primeiro_topico)

        self.root.after(5000, self.atualizacoes_periodicas)

    def carregar_topicos_assinados(self):
        try:
            with open(f"{self.usuario.nome}_topicos_assinados.txt", "r", encoding="utf-8") as f:
                for linha in f:
                    topico = linha.strip()
                    if topico:
                        sucesso = self.usuario.assinar_topico(topico)
                        if sucesso:
                            self.topicos_assinados.add(topico)
        except FileNotFoundError:
            pass

    def salvar_topicos_assinados(self):
        try:
            with open(f"{self.usuario.nome}_topicos_assinados.txt", "w", encoding="utf-8") as f:
                for t in self.topicos_assinados:
                    f.write(t + "\n")
        except Exception as e:
            self.registrar(f"Erro ao salvar tópicos assinados: {e}")

    def atualizacoes_periodicas(self):
        self.atualizar_lista_usuarios()
        self.root.after(5000, self.atualizacoes_periodicas)

    def listar_topicos(self):
        if not self.usuario:
            return

        for widget in self.container_topicos.winfo_children():
            widget.destroy()

        try:
            topicos = self.usuario.listar_topicos()
        except Exception as e:
            self.registrar(f"Erro ao listar tópicos: {e}")
            return

        for topico in topicos:
            frame = tk.Frame(self.container_topicos)
            frame.pack(fill=tk.X, pady=2)

            entrada = tk.Entry(frame, width=25)
            entrada.insert(0, topico)
            entrada.config(state='readonly')
            if topico in self.topicos_assinados:
                entrada.config(bg="#b2f0c2")
            entrada.pack(side=tk.LEFT)

            if topico in self.topicos_assinados:
                texto_botao = "Visualizar"
                comando = lambda t=topico: self.visualizar_mural(t)
            else:
                texto_botao = "Assinar"
                comando = lambda t=topico: self.assinar_topico(t)

            tk.Button(frame, text=texto_botao, bg="#4da6ff", command=comando).pack(side=tk.LEFT, padx=5)

    def assinar_topico(self, topico):
        if not self.usuario:
            return

        try:
            sucesso = self.usuario.assinar_topico(topico)
            if sucesso:
                self.topicos_assinados.add(topico)
                self.salvar_topicos_assinados()
                self.registrar(f"Assinado ao tópico: {topico}")
                self.listar_topicos()
            else:
                self.registrar(f"Não foi possível assinar o tópico {topico}.")
        except Exception as e:
            self.registrar(f"Erro ao assinar tópico: {e}")

    def visualizar_mural(self, topico):
        if topico not in self.topicos_assinados:
            messagebox.showinfo("Informação", f"Você precisa assinar '{topico}' primeiro.")
            return

        self.topico_selecionado = topico
        self.botao_topico.config(text=topico)
        self.caixa_mural.delete(1.0, tk.END)

        try:
            with open(f"{topico}.txt", "r", encoding="utf-8") as f:
                for msg in f.readlines():
                    self.caixa_mural.insert(tk.END, msg)
        except FileNotFoundError:
            self.caixa_mural.insert(tk.END, f"[{topico}] Nenhuma mensagem anterior.\n")

        self.registrar(f"Visualizando mural de {topico}")

    def alternar_topico(self):
        if self.topico_selecionado:
            self.registrar(f"Visualizando atualmente: {self.topico_selecionado}")

    def publicar_no_topico(self):
        if not self.usuario:
            return

        topico = self.topico_selecionado
        mensagem = self.entrada_mural.get().strip()

        if not topico or not mensagem:
            messagebox.showwarning("Aviso", "Por favor, selecione um tópico e digite uma mensagem.")
            return

        remetente = self.usuario.nome

        try:
            self.usuario.publicar_em_topico(topico, mensagem)
        except Exception as e:
            self.registrar(f"Erro ao publicar no tópico: {e}")
            return

        mensagem_formatada = f"[{topico}]{remetente}: {mensagem}\n"
        self.caixa_mural.insert(tk.END, mensagem_formatada)
        self.caixa_mural.yview(tk.END)

        self.entrada_mural.delete(0, tk.END)

        try:
            with open(f"{topico}.txt", "a", encoding="utf-8") as f:
                f.write(mensagem_formatada)
        except Exception as e:
            self.registrar(f"Erro ao salvar mensagem no arquivo: {e}")

        self.registrar(f"Publicado em '{topico}': {mensagem}")

    def atualizar_lista_usuarios(self):
        if not self.usuario:
            return

        try:
            usuarios = self.usuario.listar_usuarios()
        except Exception as e:
            self.registrar(f"Erro ao listar usuários: {e}")
            return

        selecao_atual = self.lista_usuarios.curselection()
        usuario_selecionado = self.lista_usuarios.get(selecao_atual) if selecao_atual else None

        self.lista_usuarios.delete(0, tk.END)
        for usuario in usuarios:
            if usuario != self.usuario.nome:
                self.lista_usuarios.insert(tk.END, usuario)

        if usuario_selecionado and usuario_selecionado in usuarios:
            indice = usuarios.index(usuario_selecionado)
            self.lista_usuarios.selection_set(indice)

    def selecionar_usuario(self, event):
        selecao = self.lista_usuarios.curselection()
        if selecao:
            usuario = self.lista_usuarios.get(selecao)
            self.entrada_destinatario.delete(0, tk.END)
            self.entrada_destinatario.insert(0, usuario)
            self.entrada_msg_privada.focus()

    def enviar_mensagem_privada(self):
        if not self.usuario:
            return

        destinatario = self.entrada_destinatario.get().strip()
        mensagem = self.entrada_msg_privada.get().strip()

        if not destinatario or not mensagem:
            messagebox.showwarning("Aviso", "Por favor, selecione um usuário e digite uma mensagem.")
            return

        try:
            self.usuario.enviar_para_usuario(destinatario, mensagem)
        except Exception as e:
            self.registrar(f"Erro ao enviar mensagem privada: {e}")
            return

        self.mostrar_mensagem(f"Você para {destinatario}: {mensagem}")
        self.entrada_msg_privada.delete(0, tk.END)

    def mostrar_mensagem(self, msg):
        if msg.startswith("PRIVADO:"):
            _, remetente, mensagem = msg.split(":", 2)
            self.caixa_log.config(state='normal')
            self.caixa_log.insert(tk.END, f"[Privado de {remetente}] {mensagem}\n")
            self.caixa_log.config(state='disabled')
            self.caixa_log.yview(tk.END)

        elif msg.startswith("[") and "]" in msg:
            nome_topico = msg[1:msg.index("]")]
            if nome_topico in self.topicos_assinados:
                if self.topico_selecionado == nome_topico:
                    self.caixa_mural.insert(tk.END, msg + '\n')
                    self.caixa_mural.yview(tk.END)
                try:
                    with open(f"{nome_topico}.txt", "a", encoding="utf-8") as f:
                        f.write(msg + '\n')
                except Exception as e:
                    self.registrar(f"Erro ao salvar mensagem no arquivo: {e}")
        else:
            self.registrar(msg)

    def registrar(self, msg):
        self.caixa_log.config(state='normal')
        self.caixa_log.insert(tk.END, msg + '\n')
        self.caixa_log.config(state='disabled')
        self.caixa_log.yview(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
