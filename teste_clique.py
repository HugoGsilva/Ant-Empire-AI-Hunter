import pydirectinput
import pyautogui
import time
import keyboard

print("--- TESTE DE CLIQUE ---")
print("1. Abra o Roblox.")
print("2. Eu vou clicar no centro da tela a cada 2 segundos.")
print("3. Pressione 'Q' para parar.")
print("Iniciando em 5 segundos...")
time.sleep(5)

# Pega o tamanho da tela para achar o meio
largura, altura = pyautogui.size()
centro_x, centro_y = int(largura / 2), int(altura / 2)

while True:
    if keyboard.is_pressed('q'):
        break
    
    print("Tentando clicar...")
    
    # 1. Garante que o mouse está no meio
    pyautogui.moveTo(centro_x, centro_y)
    
    # 2. Tenta CLIQUE ESQUERDO (Padrão de ataque/andar)
    pydirectinput.mouseDown(button='left')
    time.sleep(0.1) # Segura um pouco
    pydirectinput.mouseUp(button='left')
    
    # 3. Pequena pausa e Tenta CLIQUE DIREITO (Caso seja esse)
    time.sleep(0.5)
    pydirectinput.mouseDown(button='right')
    time.sleep(0.1)
    pydirectinput.mouseUp(button='right')

    time.sleep(2)qqqq