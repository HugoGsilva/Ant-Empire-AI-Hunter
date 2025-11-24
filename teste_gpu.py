import torch

print("--- DIAGNÓSTICO DE GPU ---")
try:
    tem_gpu = torch.cuda.is_available()
    print(f"CUDA Disponível? -> {tem_gpu}")
    
    if tem_gpu:
        print(f"Placa detectada: {torch.cuda.get_device_name(0)}")
        print("Tudo pronto! O treino vai voar. 🚀")
    else:
        print("Placa NÃO detectada. O treino será na CPU (Lento). 🐢")
        print("Versão do PyTorch instalada:", torch.__version__)
except ImportError:
    print("PyTorch nem está instalado.")