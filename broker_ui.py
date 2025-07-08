import tkinter as tk
from tkinter import scrolledtext, messagebox
from broker_manager import BrokerManager

class BrokerInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Broker Manager - RabbitMQ")

        self.broker = BrokerManager()

        tk.Label(root, text="Usuário:").grid(row=0, column=0, sticky="e")
        self.usuario_entry = tk.Entry(root)
        self.usuario_entry.grid(row=0, column=1)

        tk.Button(root, text="Adicionar Usuário", command=self.adicionar_usuario).grid(row=0, column=2)
        tk.Button(root, text="Remover Usuário", command=self.remover_usuario).grid(row=0, column=3)
        tk.Button(root, text="Listar Usuários", command=self.listar_usuarios).grid(row=0, column=4)

        tk.Label(root, text="Tópico:").grid(row=1, column=0, sticky="e")
        self.topico_entry = tk.Entry(root)
        self.topico_entry.grid(row=1, column=1)

        tk.Button(root, text="Criar Tópico", command=self.criar_topico).grid(row=1, column=2)
        tk.Button(root, text="Remover Tópico", command=self.remover_topico).grid(row=1, column=3)
        tk.Button(root, text="Listar Tópicos", command=self.listar_topicos).grid(row=1, column=4)

        tk.Label(root, text="Fila para contagem:").grid(row=2, column=0, sticky="e")
        self.fila_contar_entry = tk.Entry(root)
        self.fila_contar_entry.grid(row=2, column=1)
        tk.Button(root, text="Contar Mensagens", command=self.contar_mensagens).grid(row=2, column=2)

        self.saida = scrolledtext.ScrolledText(root, width=70, height=20)
        self.saida.grid(row=3, column=0, columnspan=5, pady=10)

    def adicionar_usuario(self):
        nome = self.usuario_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do usuário.")
            return
        resultado = self.broker.criar_usuario(nome)
        self.saida.insert(tk.END, resultado + "\n")

    def remover_usuario(self):
        nome = self.usuario_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do usuário.")
            return
        resultado = self.broker.remover_usuario(nome)
        self.saida.insert(tk.END, resultado + "\n")

    def listar_usuarios(self):
        usuarios = self.broker.listar_usuarios()
        self.saida.insert(tk.END, "Usuários:\n")
        for u in usuarios:
            self.saida.insert(tk.END, f" - {u}\n")
        self.saida.insert(tk.END, "\n")

    def criar_topico(self):
        nome = self.topico_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do tópico.")
            return
        resultado = self.broker.criar_topico(nome)
        self.saida.insert(tk.END, resultado + "\n")

    def remover_topico(self):
        nome = self.topico_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do tópico.")
            return
        resultado = self.broker.remover_topico(nome)
        self.saida.insert(tk.END, resultado + "\n")

    def listar_topicos(self):
        topicos = self.broker.listar_topicos()
        self.saida.insert(tk.END, "Tópicos:\n")
        if isinstance(topicos, list):
            for t in topicos:
                self.saida.insert(tk.END, f" - {t}\n")
        else:
            self.saida.insert(tk.END, str(topicos) + "\n")
        self.saida.insert(tk.END, "\n")

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

   

if __name__ == "__main__":
    root = tk.Tk()
    app = BrokerInterface(root)
    root.mainloop()
