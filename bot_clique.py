from ultralytics import YOLO
import mss
import numpy as np
import cv2
import keyboard
import time
import ctypes
import random
import threading
import win32gui
import win32api
import win32con
from ctypes import wintypes

# ==============================================================================
# --- MÓDULO DE OVERLAY TRANSPARENTE ---
# ==============================================================================

class OverlayWindow:
    """Janela transparente que desenha por cima do jogo"""
    
    def __init__(self, largura, altura):
        self.largura = largura
        self.altura = altura
        self.deteccoes = []  # Lista de caixas para desenhar
        self.alvo_atual = None  # Alvo selecionado
        self.running = False
        self.hwnd = None
        
    def criar_janela(self):
        """Cria a janela transparente"""
        import win32gui, win32con
        
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wndproc
        wc.lpszClassName = "OverlayWindow"
        wc.hbrBackground = win32gui.GetStockObject(win32con.NULL_BRUSH)
        
        try:
            win32gui.RegisterClass(wc)
        except:
            pass
        
        self.hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST,
            "OverlayWindow",
            "Overlay",
            win32con.WS_POPUP,
            0, 0, self.largura, self.altura,
            None, None, None, None
        )
        
        win32gui.SetLayeredWindowAttributes(
            self.hwnd,
            win32api.RGB(0, 0, 0),
            0,
            win32con.LWA_COLORKEY
        )
        
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        
    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_PAINT:
            self._desenhar()
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    
    def _desenhar(self):
        """Desenha as detecções na janela"""
        hdc = win32gui.GetDC(self.hwnd)
        
        # Limpa a janela (fundo preto transparente)
        win32gui.FillRect(hdc, (0, 0, self.largura, self.altura), 
                         win32gui.GetStockObject(win32con.BLACK_BRUSH))
        
        # Desenha cada detecção
        for deteccao in self.deteccoes:
            x1, y1, x2, y2, conf = deteccao
            cor = win32api.RGB(0, 255, 0)  # Verde
            pen = win32gui.CreatePen(win32con.PS_SOLID, 2, cor)
            old_pen = win32gui.SelectObject(hdc, pen)
            
            # Desenha retângulo
            win32gui.Rectangle(hdc, int(x1), int(y1), int(x2), int(y2))
            
            win32gui.SelectObject(hdc, old_pen)
            win32gui.DeleteObject(pen)
        
        # Desenha alvo atual (vermelho)
        if self.alvo_atual:
            cx, cy = self.alvo_atual
            cor = win32api.RGB(255, 0, 0)
            brush = win32gui.CreateSolidBrush(cor)
            win32gui.SelectObject(hdc, brush)
            win32gui.Ellipse(hdc, cx-6, cy-6, cx+6, cy+6)
            win32gui.DeleteObject(brush)
        
        win32gui.ReleaseDC(self.hwnd, hdc)
    
    def atualizar(self, deteccoes, alvo=None):
        """Atualiza as detecções a serem desenhadas"""
        self.deteccoes = deteccoes
        self.alvo_atual = alvo
        if self.hwnd:
            win32gui.InvalidateRect(self.hwnd, None, True)
    
    def fechar(self):
        """Fecha a janela overlay"""
        if self.hwnd:
            win32gui.DestroyWindow(self.hwnd)

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
CONFIDENCE = 0.5

# Tempos (em segundos)
INTERVALO_CLIQUE = 2.5   # Tempo suficiente para ele andar até o bicho
INTERVALO_GIRAR = 5.0    
INTERVALO_ENTRE_GIROS = 1.5  # Tempo entre cada giro ao procurar
TEMPO_ESPERA_ANDAR = 10.0  # Tempo para aguardar o personagem terminar de andar após clicar

TECLA_GIRAR = '.'

# Estados do bot
ESTADO_PROCURANDO_ENEMY = "procurando_enemy"
ESTADO_COLETANDO_BLUEBERRY = "coletando_blueberry"
ESTADO_IDLE = "idle" 

# Resolução será detectada automaticamente
LARGURA = None
ALTURA = None
MONITOR = None

# Modo de visualização (True = overlay na tela, False = janela separada)
USAR_OVERLAY = False

def detectar_resolucao():
    """Detecta automaticamente a resolução do monitor principal"""
    user32 = ctypes.windll.user32
    largura = user32.GetSystemMetrics(0)
    altura = user32.GetSystemMetrics(1)
    return largura, altura

def main():
    global LARGURA, ALTURA, MONITOR
    
    print("--- BOT ROBLOX (AUTO-DETECT RESOLUTION) ---")
    
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
    
    # Cria overlay se ativado
    overlay = None
    if USAR_OVERLAY:
        overlay = OverlayWindow(LARGURA, ALTURA)
        overlay.criar_janela()
        print(">>> Overlay ativado - Visualização na tela do jogo!")
    
    time.sleep(3)

    ultimo_tempo_clique = 0
    ultimo_tempo_girar = 0
    tempo_ultimo_clique_alvo = 0  # Controle para esperar após clicar em qualquer alvo (enemy ou blueberry)
    
    # Controle de estado para blueberries
    estado_atual = ESTADO_IDLE
    giros_realizados = 0
    ultima_blueberry = None  # Guarda a última blueberry encontrada
    tempo_inicio_procura = 0

    while True:
        if keyboard.is_pressed('q'):
            break

        screenshot = np.array(sct.grab(MONITOR))
        frame = np.ascontiguousarray(screenshot[:, :, :3])

        # verbose=False deixa o terminal limpo
        results = model(frame, conf=CONFIDENCE, verbose=False)

        inimigo_encontrado = False
        blueberry_encontrada = False
        melhor_alvo = None
        melhor_blueberry = None
        melhor_score = float('inf')
        melhor_score_blueberry = float('inf')
        deteccoes_para_overlay = []  # Para enviar ao overlay
        
        # Centro da tela para cálculo de prioridade
        centro_tela_x, centro_tela_y = LARGURA / 2, ALTURA / 2

        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                classe_nome = model.names[cls]
                
                # Filtra inimigos com confiança mínima de 0.6
                if classe_nome == 'Enemy' and conf >= 0.6:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Adiciona para o overlay
                    deteccoes_para_overlay.append((x1, y1, x2, y2, conf))
                    
                    # Calcula centro do alvo
                    centro_alvo_x = (x1 + x2) / 2
                    centro_alvo_y = (y1 + y2) / 2
                    
                    # Calcula distância do centro da tela
                    distancia = np.sqrt((centro_alvo_x - centro_tela_x)**2 + 
                                      (centro_alvo_y - centro_tela_y)**2)
                    
                    # Calcula tamanho do alvo
                    tamanho = (x2 - x1) * (y2 - y1)
                    
                    # Score: prioriza alvos próximos do centro E com tamanho razoável
                    # Menor score = melhor alvo
                    score = distancia / (tamanho ** 0.3)  # Balanceia distância vs tamanho
                    
                    if score < melhor_score:
                        melhor_score = score
                        melhor_alvo = box
                        inimigo_encontrado = True
                
                # Filtra blueberries com confiança mínima de 0.5
                elif classe_nome == 'Blueberry' and conf >= 0.5:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Adiciona para o overlay com cor diferente
                    deteccoes_para_overlay.append((x1, y1, x2, y2, conf))
                    
                    # Calcula centro da blueberry
                    centro_blueberry_x = (x1 + x2) / 2
                    centro_blueberry_y = (y1 + y2) / 2
                    
                    # Calcula distância do centro da tela
                    distancia = np.sqrt((centro_blueberry_x - centro_tela_x)**2 + 
                                      (centro_blueberry_y - centro_tela_y)**2)
                    
                    # Prioriza blueberries mais próximas
                    if distancia < melhor_score_blueberry:
                        melhor_score_blueberry = distancia
                        melhor_blueberry = box
                        blueberry_encontrada = True

        tempo_atual = time.time()

        # PRIORIDADE 1: Inimigos (ataca) - SEMPRE prioriza
        if inimigo_encontrado and melhor_alvo is not None:
            # Reset estado se estava procurando
            estado_atual = ESTADO_IDLE
            giros_realizados = 0
            
            x1, y1, x2, y2 = melhor_alvo.xyxy[0].cpu().numpy()
            
            # --- OTIMIZAÇÃO: MIRA NO CENTRO-BAIXO ---
            # Centro horizontal e 70% da altura (centro-baixo do alvo)
            centro_x = int((x1 + x2) / 2)
            centro_y = int(y1 + (y2 - y1) * 0.70)
            
            # Atualiza overlay com alvo atual
            if USAR_OVERLAY and overlay:
                overlay.atualizar(deteccoes_para_overlay, (centro_x, centro_y))

            # Desenha Debug na janela mini (se não usar overlay)
            if not USAR_OVERLAY:
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.circle(frame, (centro_x, centro_y), 6, (0, 0, 255), -1)
                cv2.putText(frame, "ENEMY", (int(x1), int(y1) - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Verifica se já passou tempo suficiente desde o último clique
            if tempo_atual - tempo_ultimo_clique_alvo >= TEMPO_ESPERA_ANDAR:
                # Clique direito para atacar
                clique_clean(centro_x, centro_y, LARGURA, ALTURA)
                tempo_ultimo_clique_alvo = tempo_atual
                print(f">>> Atacando inimigo! Aguardando {TEMPO_ESPERA_ANDAR}s...")
            else:
                # HUD mostrando tempo restante
                if not USAR_OVERLAY:
                    t_restante = round(TEMPO_ESPERA_ANDAR - (tempo_atual - tempo_ultimo_clique_alvo), 1)
                    cv2.putText(frame, f"Cooldown: {t_restante}s", (centro_x + 10, centro_y), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

        # PRIORIDADE 2: Blueberries (sistema de busca inteligente)
        elif blueberry_encontrada and melhor_blueberry is not None:
            x1, y1, x2, y2 = melhor_blueberry.xyxy[0].cpu().numpy()
            
            # Centro da blueberry
            centro_x = int((x1 + x2) / 2)
            centro_y = int((y1 + y2) / 2)
            
            # Guarda referência da blueberry
            ultima_blueberry = (centro_x, centro_y)
            
            # Atualiza overlay com blueberry atual
            if USAR_OVERLAY and overlay:
                overlay.atualizar(deteccoes_para_overlay, (centro_x, centro_y))

            # Desenha Debug na janela mini
            if not USAR_OVERLAY:
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                cv2.circle(frame, (centro_x, centro_y), 6, (255, 0, 255), -1)
                estado_texto = f"BLUEBERRY [{estado_atual}]"
                cv2.putText(frame, estado_texto, (int(x1), int(y1) - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            # MÁQUINA DE ESTADOS
            if estado_atual == ESTADO_IDLE or estado_atual == ESTADO_COLETANDO_BLUEBERRY:
                # Clica na blueberry e inicia busca por enemies
                if tempo_atual - tempo_ultimo_clique_alvo >= TEMPO_ESPERA_ANDAR:
                    clique_clean(centro_x, centro_y, LARGURA, ALTURA)
                    tempo_ultimo_clique_alvo = tempo_atual  # Marca o momento do clique
                    estado_atual = ESTADO_PROCURANDO_ENEMY
                    giros_realizados = 0
                    tempo_inicio_procura = tempo_atual
                    print(f">>> Clicou na blueberry, aguardando {TEMPO_ESPERA_ANDAR}s para personagem andar...")
                else:
                    # HUD Minimalista
                    if not USAR_OVERLAY:
                        t_restante = round(TEMPO_ESPERA_ANDAR - (tempo_atual - tempo_ultimo_clique_alvo), 1)
                        cv2.putText(frame, f"Cooldown: {t_restante}s", (centro_x + 10, centro_y), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            
            elif estado_atual == ESTADO_PROCURANDO_ENEMY:
                # Já clicou na blueberry, agora gira 2x procurando enemies
                # (Esse estado será processado na próxima iteração quando não achar a blueberry no centro)
                pass

        # PRIORIDADE 3: Sem alvo visível
        else:
            # Atualiza overlay sem alvo
            if USAR_OVERLAY and overlay:
                overlay.atualizar(deteccoes_para_overlay, None)
            
            # Se está no modo de procura após clicar na blueberry
            if estado_atual == ESTADO_PROCURANDO_ENEMY:
                # Aguarda 10 segundos após clicar na blueberry antes de começar a girar
                tempo_desde_clique = tempo_atual - tempo_ultimo_clique_alvo
                
                if tempo_desde_clique < TEMPO_ESPERA_ANDAR:
                    # Ainda esperando o personagem terminar de andar
                    tempo_restante = TEMPO_ESPERA_ANDAR - tempo_desde_clique
                    if not USAR_OVERLAY:
                        cv2.putText(frame, f"Aguardando andar: {tempo_restante:.1f}s", 
                                   (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    # Não faz nada, apenas aguarda
                    pass
                
                elif giros_realizados < 2:
                    # Já esperou 10s, agora pode girar
                    if tempo_atual - ultimo_tempo_girar >= INTERVALO_ENTRE_GIROS:
                        print(f">>> Procurando enemies... Giro {giros_realizados + 1}/2")
                        keyboard.press(TECLA_GIRAR)
                        time.sleep(0.2)
                        keyboard.release(TECLA_GIRAR)
                        ultimo_tempo_girar = tempo_atual
                        giros_realizados += 1
                        
                        # Se completou 2 giros e tem blueberry guardada, volta a coletar
                        if giros_realizados >= 2:
                            if ultima_blueberry is not None:
                                print(">>> Nenhum inimigo encontrado após 2 giros. Voltando para blueberry...")
                                estado_atual = ESTADO_COLETANDO_BLUEBERRY
                            else:
                                estado_atual = ESTADO_IDLE
            
            # Modo normal: sem blueberry e sem estar procurando
            elif estado_atual != ESTADO_PROCURANDO_ENEMY:
                estado_atual = ESTADO_IDLE
                giros_realizados = 0
                
                if tempo_atual - ultimo_tempo_girar >= INTERVALO_GIRAR:
                    print(">>> Sem alvo. Girando...")
                    keyboard.press(TECLA_GIRAR)
                    time.sleep(0.2)
                    keyboard.release(TECLA_GIRAR)
                    ultimo_tempo_girar = tempo_atual

        # --- MODO VISUALIZAÇÃO ---
        # Tamanho configurável (ajuste o valor abaixo)
        TAMANHO_JANELA = 0.5  # 50% do tamanho original (mude para 0.6, 0.7, 0.8 etc)
        
        largura_vis = int(frame.shape[1] * TAMANHO_JANELA)
        altura_vis = int(frame.shape[0] * TAMANHO_JANELA)
        frame_vis = cv2.resize(frame, (largura_vis, altura_vis))

        # Mostra a visualização
        nome_janela = "Bot View"
        cv2.imshow(nome_janela, frame_vis)
        
        # Posição da janela (ajuste conforme sua tela)
        cv2.moveWindow(nome_janela, 50, 00)  # Canto superior esquerdo

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()