import os
import subprocess
import sys
import platform

VENV_DIR = "venv"

def criar_venv():
    if not os.path.exists(VENV_DIR):
        print("Criando ambiente virtual...")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
    else:
        print("Ambiente virtual já existe.")

def instalar_dependencias():
    pip_exe = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin", "pip")
    print("Instalando dependências via requirements.txt...")
    subprocess.check_call([pip_exe, "install", "-r", "requirements.txt"])

def habilitar_plugin_management():
    print("Habilitando plugin rabbitmq_management...")
    try:
        if os.name == "nt" or platform.system() == "Windows":
            # Para Windows
            subprocess.run(["rabbitmq-plugins", "enable", "rabbitmq_management"], check=True)
        else:
            # Para Linux/WSL
            subprocess.run(["sudo", "rabbitmq-plugins", "enable", "rabbitmq_management"], check=True)
        print("Plugin rabbitmq_management habilitado com sucesso!")
    except subprocess.CalledProcessError:
        print("❌ Erro ao tentar habilitar o plugin rabbitmq_management. Verifique se o RabbitMQ está instalado e ativo.")

def main():
    criar_venv()
    instalar_dependencias()
    habilitar_plugin_management()
    print("\nSetup concluído!")
    print(f"Para ativar o ambiente virtual, use:")
    if os.name == "nt":
        print(f"  {VENV_DIR}\\Scripts\\activate.bat")
    else:
        print(f"  source {VENV_DIR}/bin/activate")

if __name__ == "__main__":
    main()
