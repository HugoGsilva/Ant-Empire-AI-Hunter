from ultralytics import YOLO
import mss
import numpy as np
import cv2
import keyboard
import time
import ctypes
import random
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
    1. Adiciona variação mínima (Jitter) para parecer humano sem perder precisão.
    2. Movimento suave até o alvo.
    3. Tempo de clique variável.
    """
    
    # Humanização: jitter MUITO reduzido para máxima precisão
    offset_x = random.randint(-2, 2)
    offset_y = random.randint(-2, 2)
    
    # Garante que as coordenadas estejam dentro dos limites
    target_x = int(max(0, min(x + offset_x, largura_tela - 1)))
    target_y = int(max(0, min(y + offset_y, altura_tela - 1)))

    # Pega posição atual do cursor
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
    
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    
    # Movimento suave até o alvo
    movimento_suave(pt.x, pt.y, target_x, target_y, largura_tela, altura_tela)
    
    # Pequena pausa após movimento para estabilizar
    time.sleep(0.02)
    
    # Conversão CORRIGIDA para coordenadas absolutas do alvo final
    abs_x = int((target_x * 65536) // largura_tela)
    abs_y = int((target_y * 65536) // altura_tela)
    
    # Garante que esteja no intervalo válido
    abs_x = max(0, min(abs_x, 65535))
    abs_y = max(0, min(abs_y, 65535))

    # Clique com timing humanizado
    mi_down = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_ABSOLUTE, 0, None)
    mi_up = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_ABSOLUTE, 0, None)

    user32.SendInput(1, ctypes.byref(INPUT(INPUT_MOUSE, mi_down)), ctypes.sizeof(INPUT))
    time.sleep(0.05 + random.uniform(0, 0.03))  # 50-80ms
    user32.SendInput(1, ctypes.byref(INPUT(INPUT_MOUSE, mi_up)), ctypes.sizeof(INPUT))

# ==============================================================================
# --- CONFIGURAÇÕES DO BOT ---
# ==============================================================================

MODEL_PATH = "runs/detect/train10/weights/best.pt" 
CONFIDENCE = 0.25  # Confiança reduzida para Melon (detecta menos que outras frutas)

# Tempos (em segundos)
TEMPO_ESPERA_ANDAR = 10.0  # Tempo para aguardar o personagem terminar de andar após clicar
INTERVALO_GIRAR = 5.0      # Tempo entre giros quando não há melancias
INTERVALO_ENTRE_GIROS = 1.5  # Tempo entre cada giro ao procurar

DEBUG_MODE = False  # Desativa debug para modo de produção

TECLA_GIRAR = '.'

# Resolução será detectada automaticamente
LARGURA = None
ALTURA = None
MONITOR = None

# Estados do bot
ESTADO_PROCURANDO_MELANCIA = "procurando_melancia"
ESTADO_COLETANDO = "coletando"
ESTADO_IDLE = "idle"

# Tamanho da janela de visualização
TAMANHO_JANELA = 0.5  # 50% do tamanho original

def detectar_resolucao():
    """Detecta automaticamente a resolução do monitor principal"""
    user32 = ctypes.windll.user32
    largura = user32.GetSystemMetrics(0)
    altura = user32.GetSystemMetrics(1)
    return largura, altura

def main():
    global LARGURA, ALTURA, MONITOR
    
    print("--- BOT COLETOR DE MELANCIAS ---")
    
    # Detecta resolução automaticamente
    LARGURA, ALTURA = detectar_resolucao()
    MONITOR = {"top": 0, "left": 0, "width": LARGURA, "height": ALTURA}
    
    print(f">>> Resolução detectada: {LARGURA}x{ALTURA}")
    print(f">>> Monitor configurado: {MONITOR}")
    
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
    
    time.sleep(3)

    ultimo_tempo_girar = 0
    tempo_ultimo_clique = 0  # Controle para esperar após clicar
    
    # Controle de estado
    estado_atual = ESTADO_IDLE
    giros_realizados = 0
    ultima_melancia = None

    while True:
        if keyboard.is_pressed('q'):
            break

        screenshot = np.array(sct.grab(MONITOR))
        frame = np.ascontiguousarray(screenshot[:, :, :3])

        # verbose=False deixa o terminal limpo
        results = model(frame, conf=CONFIDENCE, verbose=False)

        melancia_encontrada = False
        melhor_melancia = None
        melhor_score = float('inf')
        deteccoes = []
        deteccoes_por_classe = {}  # Contador por tipo
        
        # Centro da tela para cálculo de prioridade
        centro_tela_x, centro_tela_y = LARGURA / 2, ALTURA / 2

        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                classe_nome = model.names[cls]
                
                # DEBUG: Mostra tudo que está sendo detectado
                if DEBUG_MODE and conf >= CONFIDENCE:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    print(f"Detectado: {classe_nome} (confiança: {conf:.2f}) em [{int(x1)},{int(y1)}]")
                
                # Filtra APENAS melancias (Melon) com confiança mínima configurada
                if classe_nome == 'Melon' and conf >= CONFIDENCE:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Conta quantas de cada tipo
                    if classe_nome not in deteccoes_por_classe:
                        deteccoes_por_classe[classe_nome] = 0
                    deteccoes_por_classe[classe_nome] += 1
                    
                    # Adiciona para visualização com a classe detectada
                    deteccoes.append((x1, y1, x2, y2, conf, classe_nome))
                    
                    # Calcula centro da melancia
                    centro_x = (x1 + x2) / 2
                    centro_y = (y1 + y2) / 2
                    
                    # Calcula distância do centro da tela
                    distancia = np.sqrt((centro_x - centro_tela_x)**2 + 
                                      (centro_y - centro_tela_y)**2)
                    
                    # Prioriza melancias mais próximas do centro
                    if distancia < melhor_score:
                        melhor_score = distancia
                        melhor_melancia = box
                        melancia_encontrada = True

        tempo_atual = time.time()

        # PRIORIDADE 1: Melancia encontrada - coleta
        if melancia_encontrada and melhor_melancia is not None:
            # Reset estado
            estado_atual = ESTADO_COLETANDO
            giros_realizados = 0
            
            x1, y1, x2, y2 = melhor_melancia.xyxy[0].cpu().numpy()
            cls = int(melhor_melancia.cls[0])
            classe_detectada = model.names[cls]
            conf = float(melhor_melancia.conf[0])
            
            # Centro da melancia
            centro_x = int((x1 + x2) / 2)
            centro_y = int((y1 + y2) / 2)
            
            # Guarda referência da melancia
            ultima_melancia = (centro_x, centro_y)
            
            # Desenha Debug na janela - Melon em amarelo/ciano
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 3)
            cv2.circle(frame, (centro_x, centro_y), 8, (255, 0, 255), -1)
            cv2.putText(frame, f"MELON [{conf:.2f}]", (int(x1), int(y1) - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Verifica se já passou tempo suficiente desde o último clique
            if tempo_atual - tempo_ultimo_clique >= TEMPO_ESPERA_ANDAR:
                # Clique direito para andar até a melancia
                clique_clean(centro_x, centro_y, LARGURA, ALTURA)
                tempo_ultimo_clique = tempo_atual
                print(f">>> Coletando MELON! Confiança: {conf:.2f} | Aguardando {TEMPO_ESPERA_ANDAR}s...")
            else:
                # HUD mostrando tempo restante
                t_restante = round(TEMPO_ESPERA_ANDAR - (tempo_atual - tempo_ultimo_clique), 1)
                cv2.putText(frame, f"Cooldown: {t_restante}s", (centro_x + 10, centro_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

        # PRIORIDADE 2: Sem melancia - procura girando
        else:
            estado_atual = ESTADO_PROCURANDO_MELANCIA
            
            # Aguarda cooldown antes de girar
            if tempo_atual - tempo_ultimo_clique >= TEMPO_ESPERA_ANDAR:
                if tempo_atual - ultimo_tempo_girar >= INTERVALO_GIRAR:
                    print(">>> Sem MELON detectada. Girando para procurar...")
                    keyboard.press(TECLA_GIRAR)
                    time.sleep(0.2)
                    keyboard.release(TECLA_GIRAR)
                    ultimo_tempo_girar = tempo_atual
            else:
                # Mostra que está em cooldown
                tempo_restante = TEMPO_ESPERA_ANDAR - (tempo_atual - tempo_ultimo_clique)
                cv2.putText(frame, f"Aguardando: {tempo_restante:.1f}s", 
                           (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # --- MODO VISUALIZAÇÃO ---
        largura_vis = int(frame.shape[1] * TAMANHO_JANELA)
        altura_vis = int(frame.shape[0] * TAMANHO_JANELA)
        frame_vis = cv2.resize(frame, (largura_vis, altura_vis))

        # Status do bot
        cv2.putText(frame_vis, f"Estado: {estado_atual}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Contador de melancias detectadas
        total_melons = deteccoes_por_classe.get('Melon', 0)
        cv2.putText(frame_vis, f"Melons: {total_melons}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Mostra a visualização
        nome_janela = "Bot Melancia"
        cv2.imshow(nome_janela, frame_vis)
        
        # Posição da janela
        cv2.moveWindow(nome_janela, 50, 0)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
