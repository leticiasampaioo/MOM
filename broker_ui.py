import tkinter as tk
from tkinter import scrolledtext, messagebox
from broker_manager import BrokerManager 

class BrokerInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Broker Manager - RabbitMQ")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing) # Adicionado para fechar a conexão

        try:
            self.broker = BrokerManager()
        except ConnectionError as e: # Captura o erro de conexão inicial do BrokerManager
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao RabbitMQ. Certifique-se de que está rodando. {e}")
            self.root.destroy() # Fecha a janela se não conseguir conectar
            return

        # Layout da Interface
        tk.Label(root, text="Usuário:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.usuario_entry = tk.Entry(root, width=30)
        self.usuario_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Button(root, text="Adicionar Usuário", command=self.adicionar_usuario, bg="#4CAF50").grid(row=0, column=2, padx=5, pady=5)
        tk.Button(root, text="Remover Usuário", command=self.remover_usuario, bg="#F44336").grid(row=0, column=3, padx=5, pady=5)
        tk.Button(root, text="Listar Usuários", command=self.listar_usuarios, bg="#2196F3").grid(row=0, column=4, padx=5, pady=5)

        tk.Label(root, text="Tópico:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.topico_entry = tk.Entry(root, width=30)
        self.topico_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Button(root, text="Criar Tópico", command=self.criar_topico, bg="#4CAF50").grid(row=1, column=2, padx=5, pady=5)
        tk.Button(root, text="Remover Tópico", command=self.remover_topico, bg="#F44336").grid(row=1, column=3, padx=5, pady=5)
        tk.Button(root, text="Listar Tópicos", command=self.listar_topicos, bg="#2196F3").grid(row=1, column=4, padx=5, pady=5)

        tk.Label(root, text="Fila para contagem:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.fila_contar_entry = tk.Entry(root, width=30)
        self.fila_contar_entry.grid(row=2, column=1, padx=5, pady=5)
        tk.Button(root, text="Contar Mensagens", command=self.contar_mensagens, bg="#FFC107").grid(row=2, column=2, padx=5, pady=5)

        self.saida = scrolledtext.ScrolledText(root, width=80, height=20, wrap=tk.WORD) # wrap=tk.WORD para quebrar linhas
        self.saida.grid(row=3, column=0, columnspan=5, pady=10, padx=10, sticky="nsew")

        # Configurações de redimensionamento de colunas/linhas
        root.grid_rowconfigure(3, weight=1)
        root.grid_columnconfigure(1, weight=1)

    def _on_closing(self):
       
        if hasattr(self, 'broker') and self.broker: # Verifica se self.broker foi inicializado
            self.broker.close()
        self.root.destroy()

    def adicionar_usuario(self):
        nome = self.usuario_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do usuário.")
            return
        resultado = self.broker.criar_usuario(nome)
        self.saida.insert(tk.END, resultado + "\n")
        self.saida.see(tk.END) 

    def remover_usuario(self):
        nome = self.usuario_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do usuário.")
            return
        resultado = self.broker.remover_usuario(nome)
        self.saida.insert(tk.END, resultado + "\n")
        self.saida.see(tk.END)

    def listar_usuarios(self):
        self.saida.delete(1.0, tk.END) 
        self.saida.insert(tk.END, "Listando Usuários...\n")
        usuarios = self.broker.listar_usuarios()
        self.saida.insert(tk.END, "--- Usuários Ativos ---\n")
        if usuarios:
            for u in usuarios:
                self.saida.insert(tk.END, f" - {u}\n")
        else:
            self.saida.insert(tk.END, "Nenhum usuário ativo encontrado.\n")
        self.saida.insert(tk.END, "\n")
        self.saida.see(tk.END)

    def criar_topico(self):
        nome = self.topico_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do tópico.")
            return
        resultado = self.broker.criar_topico(nome)
        self.saida.insert(tk.END, resultado + "\n")
        self.saida.see(tk.END)

    def remover_topico(self):
        nome = self.topico_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do tópico.")
            return
        resultado = self.broker.remover_topico(nome)
        self.saida.insert(tk.END, resultado + "\n")
        self.saida.see(tk.END)

    def listar_topicos(self):
        self.saida.delete(1.0, tk.END) 
        self.saida.insert(tk.END, "Listando Tópicos...\n")
        topicos = self.broker.listar_topicos()
        self.saida.insert(tk.END, "--- Tópicos Disponíveis ---\n")
        if isinstance(topicos, list):
            if topicos:
                for t in topicos:
                    self.saida.insert(tk.END, f" - {t}\n")
            else:
                self.saida.insert(tk.END, "Nenhum tópico encontrado.\n")
        else: # Caso a API retorne uma mensagem de erro em vez de lista
            self.saida.insert(tk.END, str(topicos) + "\n")
        self.saida.insert(tk.END, "\n")
        self.saida.see(tk.END)

    def contar_mensagens(self):
        fila = self.fila_contar_entry.get().strip()
        if not fila:
            messagebox.showerror("Erro", "Informe o nome da fila.")
            return
        count = self.broker.contar_mensagens_fila(fila)
        if count is None:
            self.saida.insert(tk.END, f"Fila '{fila}' não existe ou erro ao consultar.\n")
        else:
            self.saida.insert(tk.END, f"Fila '{fila}' tem {count} mensagens.\n")
        self.saida.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = BrokerInterface(root)
    root.mainloop()