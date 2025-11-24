from ultralytics import YOLO
import os

def main():
    # 1. Carrega um modelo pré-treinado (o "cérebro" virgem)
    # O 'yolov8n.pt' é a versão Nano. É muito rápida.
    model = YOLO('yolov8n.pt') 

    # 2. Caminho para o seu arquivo data.yaml
    # O comando os.path.abspath garante que o Windows não se confunda com as pastas
    caminho_yaml = os.path.abspath("datasets/data.yaml")

    print(f"Iniciando treinamento com o arquivo: {caminho_yaml}")

    # 3. Começa o treinamento
    # epochs=100: Ele vai passar pelas suas fotos 100 vezes.
    # imgsz=640: Tamanho padrão da imagem.
    results = model.train(
        data=caminho_yaml, 
        epochs=100, 
        imgsz=640,
        plots=True,
        batch=16       # Se der erro de "Out of Memory", diminua para 8 ou 4
    )

if __name__ == '__main__':
    # Necessário para Windows para evitar loops de processamento
    main()