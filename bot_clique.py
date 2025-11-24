from ultralytics import YOLO
import mss
import numpy as np
import cv2
import keyboard
import time
import ctypes
import random  # <--- NOVA IMPORTAÇÃO PARA HUMANIZAÇÃO
from ctypes import wintypes

# ==============================================================================
# --- MÓDULO WIN32 API (OTIMIZADO) ---
# ==============================================================================

user32 = ctypes.windll.user32
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD),
                ("mi", MOUSEINPUT)]

def movimento_suave(x_atual, y_atual, x_destino, y_destino, largura_tela, altura_tela, passos=8):
    """
    Move o cursor de forma suave até o destino usando interpolação bezier simplificada.
    """
    for i in range(passos + 1):
        t = i / passos
        # Curva ease-out para movimento mais natural
        t_suave = 1 - (1 - t) ** 3
        
        x_intermediario = x_atual + (x_destino - x_atual) * t_suave
        y_intermediario = y_atual + (y_destino - y_atual) * t_suave
        
        abs_x = int(x_intermediario * 65535 / (largura_tela - 1))
        abs_y = int(y_intermediario * 65535 / (altura_tela - 1))
        
        mi_move = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None)
        user32.SendInput(1, ctypes.byref(INPUT(INPUT_MOUSE, mi_move)), ctypes.sizeof(INPUT))
        time.sleep(0.005)  # 5ms entre cada passo

def clique_clean(x, y, largura_tela, altura_tela):
    """
    Realiza um clique otimizado e fluido:
    1. Adiciona variação aleatória (Jitter) para parecer humano.
    2. Movimento suave até o alvo.
    3. Tempo de clique variável.
    """
    
    # Humanização: jitter reduzido para maior precisão
    offset_x = random.randint(-5, 5)
    offset_y = random.randint(-3, 3)
    
    target_x = max(0, min(x + offset_x, largura_tela - 1))
    target_y = max(0, min(y + offset_y, altura_tela - 1))

    # Pega posição atual do cursor
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
    
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    
    # Movimento suave até o alvo
    movimento_suave(pt.x, pt.y, target_x, target_y, largura_tela, altura_tela)
    
    # Conversão para coordenadas absolutas do alvo final
    abs_x = int(target_x * 65535 / (largura_tela - 1))
    abs_y = int(target_y * 65535 / (altura_tela - 1))

    # Clique com timing humanizado
    mi_down = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_ABSOLUTE, 0, None)
    mi_up = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_ABSOLUTE, 0, None)

    user32.SendInput(1, ctypes.byref(INPUT(INPUT_MOUSE, mi_down)), ctypes.sizeof(INPUT))
    time.sleep(0.06 + random.uniform(0, 0.04))  # 60-100ms (mais rápido e variável)
    user32.SendInput(1, ctypes.byref(INPUT(INPUT_MOUSE, mi_up)), ctypes.sizeof(INPUT))

# ==============================================================================
# --- CONFIGURAÇÕES DO BOT ---
# ==============================================================================

MODEL_PATH = "runs/detect/train7/weights/best.pt" 
CONFIDENCE = 0.5

# Tempos (em segundos)
INTERVALO_CLIQUE_BASE = 2.5   # Base para cálculo dinâmico
INTERVALO_GIRAR = 5.0    

TECLA_GIRAR = '.' 
LARGURA = 1920
ALTURA = 1080
MONITOR = {"top": 0, "left": 0, "width": LARGURA, "height": ALTURA}

# Anti-spam: rastreamento do último alvo
ultimo_alvo_pos = None
DISTANCIA_MINIMA_ALVO = 80  # Pixels de distância para considerar "mesmo alvo"

def main():
    print("--- BOT ROBLOX (CLEAN VERSION) ---")
    
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass

    try:
        model = YOLO(MODEL_PATH)
    except Exception:
        print("Erro: Modelo não encontrado.")
        return

    sct = mss.mss()
    print(">>> Bot rodando. Pressione 'Q' para sair.")
    time.sleep(3) # Tempo menor de início

    ultimo_tempo_clique = 0
    ultimo_tempo_girar = 0
    ultimo_alvo_pos = None  # Posição do último alvo clicado
    intervalo_clique_atual = INTERVALO_CLIQUE_BASE

    while True:
        if keyboard.is_pressed('q'):
            break

        screenshot = np.array(sct.grab(MONITOR))
        frame = np.ascontiguousarray(screenshot[:, :, :3])

        # verbose=False deixa o terminal limpo
        results = model(frame, conf=CONFIDENCE, verbose=False)

        inimigo_encontrado = False
        melhor_alvo = None
        maior_tamanho = 0

        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                if model.names[cls] == 'Enemy':
                    x1, y1, x2, y2 = box.xyxy[0]
                    tamanho = (x2 - x1) * (y2 - y1)
                    
                    # Prioriza inimigos próximos (maiores)
                    if tamanho > maior_tamanho:
                        maior_tamanho = tamanho
                        melhor_alvo = box
                        inimigo_encontrado = True

        tempo_atual = time.time()

        if inimigo_encontrado and melhor_alvo is not None:
            x1, y1, x2, y2 = melhor_alvo.xyxy[0]
            
            # --- OTIMIZAÇÃO: MIRA NO PÉ ---
            # Em vez de pegar o centro Y (barriga), pegamos 85% da altura (pé)
            centro_x = int((x1 + x2) / 2)
            centro_y = int(y1 + (y2 - y1) * 0.85) 

            # MELHORIA 1: Cooldown inteligente baseado em distância
            centro_tela_x, centro_tela_y = LARGURA / 2, ALTURA / 2
            distancia_centro = np.sqrt((centro_x - centro_tela_x)**2 + (centro_y - centro_tela_y)**2)
            
            if distancia_centro > 500:  # Muito longe
                intervalo_clique_atual = 3.5
                cor_info = (0, 165, 255)  # Laranja
            elif distancia_centro > 300:  # Distância média
                intervalo_clique_atual = 2.5
                cor_info = (0, 255, 255)  # Amarelo
            else:  # Perto
                intervalo_clique_atual = 2.0
                cor_info = (0, 255, 0)  # Verde

            # Desenha Debug (Caixa colorida por distância, Vermelho = Ponto de Clique)
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), cor_info, 2)
            cv2.circle(frame, (centro_x, centro_y), 4, (0, 0, 255), -1)
            cv2.putText(frame, f"Dist: {int(distancia_centro)}px", (int(x1), int(y1) - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor_info, 1)

            if tempo_atual - ultimo_tempo_clique >= intervalo_clique_atual:
                # MELHORIA 3: Anti-spam - verifica se não é o mesmo alvo
                pode_clicar = True
                
                if ultimo_alvo_pos is not None:
                    dist_ultimo_alvo = np.sqrt((centro_x - ultimo_alvo_pos[0])**2 + 
                                               (centro_y - ultimo_alvo_pos[1])**2)
                    
                    if dist_ultimo_alvo < DISTANCIA_MINIMA_ALVO:
                        pode_clicar = False
                        cv2.putText(frame, "MESMO ALVO", (centro_x - 40, centro_y - 15),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                if pode_clicar:
                    clique_clean(centro_x, centro_y, LARGURA, ALTURA)
                    ultimo_tempo_clique = tempo_atual
                    ultimo_alvo_pos = (centro_x, centro_y)
                    print(f"✓ Clicado em ({centro_x}, {centro_y}) | Dist: {int(distancia_centro)}px")
            else:
                # HUD Minimalista
                t_restante = round(intervalo_clique_atual - (tempo_atual - ultimo_tempo_clique), 1)
                cv2.putText(frame, f"{t_restante}s", (centro_x + 10, centro_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        else:
            if tempo_atual - ultimo_tempo_girar >= INTERVALO_GIRAR:
                print("Sem alvo. Girando...")
                keyboard.press(TECLA_GIRAR)
                time.sleep(0.2)
                keyboard.release(TECLA_GIRAR)
                ultimo_tempo_girar = tempo_atual

        cv2.imshow("Bot View", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()