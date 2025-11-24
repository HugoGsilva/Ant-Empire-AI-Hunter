from ultralytics import YOLO
import mss
import numpy as np
import cv2
import time
import keyboard

# --- CONFIGURAÇÕES ---
# O caminho para o arquivo que foi gerado no final do treino
# Se você rodar de novo e criar train8, mude aqui para train8
MODEL_PATH = "runs/detect/train7/weights/best.pt"

# Área de captura (Ajuste para sua resolução se necessário)
# Dica: Deixe menor que a tela total para ganhar performance e focar no centro
MONITOR = {"top": 0, "left": 0, "width": 1920, "height": 1080}

CONFIDENCE_THRESHOLD = 0.5 # Só mostra se tiver 50% de certeza

def main():
    print("Carregando o cérebro da IA...")
    try:
        model = YOLO(MODEL_PATH)
    except Exception as e:
        print(f"Erro ao carregar modelo: {e}")
        print("Verifique se o caminho do arquivo 'best.pt' está correto!")
        return

    sct = mss.mss()
    print("--- BOT INICIADO ---")
    print("Pressione 'Q' para sair.")

    while True:
        # 1. Captura a tela
        screenshot = np.array(sct.grab(MONITOR))
        
        # Remove o canal Alpha (transparência) para ficar compatível
        frame = screenshot[:, :, :3]

        # 2. A IA faz a previsão
        # verbose=False evita que encha seu terminal de texto
        results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

        # 3. Desenhar na tela (Debug)
        # O próprio YOLO tem uma função .plot() que desenha as caixas automaticamente
        frame_com_desenhos = results[0].plot()

        # 4. Lógica de decisão (Simulação)
        # Vamos ler as caixas para saber onde os inimigos estão
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Pega as coordenadas
                x1, y1, x2, y2 = box.xyxy[0]
                cls = int(box.cls[0]) # 0 = Enemy, 1 = Mount
                current_class = model.names[cls]

                if current_class == 'Enemy':
                    # Calcula o centro do inimigo
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    
                    # Desenha uma bolinha no centro do inimigo
                    cv2.circle(frame_com_desenhos, (center_x, center_y), 5, (0, 0, 255), -1)
                    
                    # Lógica simples de direção (só print por enquanto)
                    screen_center_x = MONITOR["width"] // 2
                    if center_x < screen_center_x - 100:
                        print(f"Inimigo à ESQUERDA! (Distância: {screen_center_x - center_x})")
                    elif center_x > screen_center_x + 100:
                        print(f"Inimigo à DIREITA! (Distância: {center_x - screen_center_x})")
                    else:
                        print(">>> NA MIRA! ATACAR! <<<")

        # 5. Mostra a janela
        cv2.imshow("Visao do Bot (YOLOv8)", frame_com_desenhos)

        # Sai se apertar Q
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        # Segurança extra: se segurar Q no teclado
        if keyboard.is_pressed('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()