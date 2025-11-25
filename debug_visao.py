from ultralytics import YOLO
import mss
import numpy as np
import cv2
import keyboard
import time
import ctypes

# ==============================================================================
# --- CONFIGURAÇÕES ---
# ==============================================================================

MODEL_PATH = "runs/detect/train10/weights/best.pt" 
CONFIDENCE = 0.3  # Confiança mínima para mostrar

# Resolução será detectada automaticamente
LARGURA = None
ALTURA = None
MONITOR = None

# Tamanho da janela de visualização
TAMANHO_JANELA = 0.5  # 50% do tamanho original

# Cores para cada classe (BGR)
CORES_CLASSES = {
    'Enemy': (0, 255, 0),        # Verde
    'Blueberry': (255, 0, 0),    # Azul
    'Orange': (0, 165, 255),     # Laranja
    'Melon': (0, 255, 255),      # Amarelo
    'Banana': (0, 255, 255),     # Ciano
    'Strawberry': (147, 20, 255),# Rosa
    'apple': (0, 0, 255),        # Vermelho
    'Acorn': (42, 42, 165),      # Marrom
    'Mushroom': (203, 192, 255), # Rosa claro
    'pine': (34, 139, 34),       # Verde escuro
    'Mount': (128, 128, 128),    # Cinza
}

def detectar_resolucao():
    """Detecta automaticamente a resolução do monitor principal"""
    user32 = ctypes.windll.user32
    largura = user32.GetSystemMetrics(0)
    altura = user32.GetSystemMetrics(1)
    return largura, altura

def main():
    global LARGURA, ALTURA, MONITOR
    
    print("="*60)
    print("--- DEBUG DE VISÃO DA IA ---")
    print("="*60)
    print("Este modo mostra tudo que a IA está detectando")
    print("NÃO faz cliques ou movimento automático")
    print("Pressione 'Q' para sair")
    print("="*60)
    
    # Detecta resolução automaticamente
    LARGURA, ALTURA = detectar_resolucao()
    MONITOR = {"top": 0, "left": 0, "width": LARGURA, "height": ALTURA}
    
    print(f"\n>>> Resolução detectada: {LARGURA}x{ALTURA}")
    print(f">>> Confiança mínima: {CONFIDENCE}")
    print(f">>> Modelo: {MODEL_PATH}")
    
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass

    try:
        model = YOLO(MODEL_PATH)
        print(f">>> Modelo carregado com sucesso!")
        print(f">>> Classes disponíveis: {list(model.names.values())}")
    except Exception as e:
        print(f"Erro ao carregar modelo: {e}")
        return

    sct = mss.mss()
    print("\n>>> Iniciando captura...\n")
    
    time.sleep(2)
    
    frame_count = 0
    deteccoes_totais = {}

    while True:
        if keyboard.is_pressed('q'):
            break

        screenshot = np.array(sct.grab(MONITOR))
        frame = np.ascontiguousarray(screenshot[:, :, :3])

        # Detecta objetos
        results = model(frame, conf=CONFIDENCE, verbose=False)

        deteccoes_frame = {}
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                classe_nome = model.names[cls]
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                
                # Conta detecções
                if classe_nome not in deteccoes_frame:
                    deteccoes_frame[classe_nome] = 0
                deteccoes_frame[classe_nome] += 1
                
                if classe_nome not in deteccoes_totais:
                    deteccoes_totais[classe_nome] = 0
                deteccoes_totais[classe_nome] += 1
                
                # Escolhe cor baseada na classe
                cor = CORES_CLASSES.get(classe_nome, (255, 255, 255))
                
                # Desenha caixa
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), cor, 2)
                
                # Calcula centro
                centro_x = int((x1 + x2) / 2)
                centro_y = int((y1 + y2) / 2)
                cv2.circle(frame, (centro_x, centro_y), 5, cor, -1)
                
                # Label com classe e confiança
                label = f"{classe_nome} {conf:.2f}"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                
                # Fundo para o texto
                cv2.rectangle(frame, (int(x1), int(y1) - 20), (int(x1) + w, int(y1)), cor, -1)
                cv2.putText(frame, label, (int(x1), int(y1) - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                
                # Mostra coordenadas do centro
                coord_text = f"({centro_x},{centro_y})"
                cv2.putText(frame, coord_text, (centro_x + 10, centro_y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1)

        # Imprime no console a cada 30 frames (cerca de 1 segundo)
        frame_count += 1
        if frame_count % 30 == 0 and deteccoes_frame:
            print(f"\n--- Frame {frame_count} ---")
            for classe, qtd in sorted(deteccoes_frame.items()):
                print(f"  {classe}: {qtd} detectado(s)")

        # Prepara visualização
        largura_vis = int(frame.shape[1] * TAMANHO_JANELA)
        altura_vis = int(frame.shape[0] * TAMANHO_JANELA)
        frame_vis = cv2.resize(frame, (largura_vis, altura_vis))

        # Painel de informações na tela
        y_offset = 30
        cv2.putText(frame_vis, "=== DEBUG MODE ===", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        y_offset += 40
        cv2.putText(frame_vis, f"Frame: {frame_count}", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        y_offset += 30
        cv2.putText(frame_vis, "Deteccoes neste frame:", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Mostra detecções do frame atual
        y_offset += 25
        if deteccoes_frame:
            for classe, qtd in sorted(deteccoes_frame.items()):
                cor = CORES_CLASSES.get(classe, (255, 255, 255))
                cv2.putText(frame_vis, f"  {classe}: {qtd}", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 2)
                y_offset += 25
        else:
            cv2.putText(frame_vis, "  Nenhuma", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
            y_offset += 25

        # Total acumulado
        y_offset += 10
        cv2.putText(frame_vis, "Total acumulado:", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 25
        for classe, total in sorted(deteccoes_totais.items()):
            cv2.putText(frame_vis, f"  {classe}: {total}", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            y_offset += 20

        # Legenda de cores no canto direito
        legend_x = largura_vis - 200
        legend_y = 30
        cv2.putText(frame_vis, "Legenda:", (legend_x, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        legend_y += 25
        for classe, cor in sorted(CORES_CLASSES.items()):
            cv2.rectangle(frame_vis, (legend_x, legend_y - 12), (legend_x + 15, legend_y), cor, -1)
            cv2.putText(frame_vis, classe, (legend_x + 20, legend_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1)
            legend_y += 20

        # Mostra a visualização
        nome_janela = "DEBUG - Visao da IA"
        cv2.imshow(nome_janela, frame_vis)
        cv2.moveWindow(nome_janela, 50, 0)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Resumo final
    print("\n" + "="*60)
    print("--- RESUMO FINAL ---")
    print("="*60)
    print(f"Total de frames processados: {frame_count}")
    print(f"\nDetecções acumuladas:")
    for classe, total in sorted(deteccoes_totais.items(), key=lambda x: x[1], reverse=True):
        print(f"  {classe}: {total} vezes")
    print("="*60)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
