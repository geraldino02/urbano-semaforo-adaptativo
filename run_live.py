"""
Arquivo principal do sistema.
Captura a transmissao ao vivo do YouTube, faz a deteccao e rastreamento de veiculos
com YOLOv8 e BYTETrack, conta cruzamentos por linha virtual e atualiza os semaforos.
"""

import os
import sys

os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

from ultralytics import YOLO
import cv2
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    if hasattr(cv2, "setLogLevel"):
        cv2.setLogLevel(0)
import time
import json
import subprocess
import argparse
import threading
from datetime import datetime
from collections import deque
from semaforo_simulador import SimuladorTrafego
from detector_semaforo import DetectorSemaforoReal

parser = argparse.ArgumentParser(description="Urbano - Monitoramento de trafego ao vivo")
parser.add_argument("--url", default="https://www.youtube.com/watch?v=pkHBcvRuyaA",
                    help="URL do YouTube (live ou video)")
parser.add_argument("--intervalo", type=int, default=60,
                    help="Intervalo de analise em segundos (default: 60)")
parser.add_argument("--headless", action="store_true",
                    help="Executa sem interface grafica")
parser.add_argument("--quality", default="720",
                    help="Qualidade: best, 360, 480, 720 (default: 720)")
parser.add_argument("--model", default="yolov8n.pt",
                    help="Caminho do modelo YOLO")
parser.add_argument("--conf", type=float, default=0.35,
                    help="Confianca minima YOLO (default: 0.35)")
parser.add_argument("--imgsz", type=int, default=640,
                    help="Dimensoes da imagem de inferencia YOLO")
parser.add_argument("--linha-esq", type=int, default=320,
                    help="Coordenada Y da linha no canto esquerdo")
parser.add_argument("--linha-dir", type=int, default=280,
                    help="Coordenada Y da linha no canto direito")
parser.add_argument("--fps", type=int, default=10,
                    help="FPS alvo de processamento")
parser.add_argument("--roi-semaforo", default="47,120,70,180",
                    help="ROI do semaforo x1,y1,x2,y2")
parser.add_argument("--tipo-semaforo", default="pedestre", choices=["auto", "pedestre", "veicular"],
                    help="Modo do semaforo: pedestre, veicular ou auto")
args = parser.parse_args()

YOUTUBE_URL = args.url
INTERVALO = args.intervalo
HEADLESS = args.headless
MODEL_PATH = args.model
QUALITY = args.quality
CONFIDENCE = args.conf
IMG_SIZE = args.imgsz
TARGET_FPS = args.fps
WIDTH, HEIGHT = 960, 540
JSON_FILE = "dados_trafego.json"
CSV_FILE = "metricas_semaforo.csv"

linha_y_esq = args.linha_esq
linha_y_dir = args.linha_dir

ids_vistos_total = set()
ids_intervalo = set()
ids_ja_contados = set()
posicoes_anteriores = {}
historico = []
frame_count = 0
stream_status = "conectando"
fps_real = 0.0
running = True
fluxo_atual = "BAIXO"
total_veiculos_anteriores = 0
soma_veiculos_tela = 0
frames_no_intervalo = 0

if os.path.exists(JSON_FILE):
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            dados_antigos = json.load(f)
            total_veiculos_anteriores = dados_antigos.get("total_veiculos", 0)
            historico = dados_antigos.get("historico", [])[-50:]
    except Exception:
        pass

roi_semaforo_config = None
if args.roi_semaforo:
    try:
        roi_semaforo_config = [int(v.strip()) for v in args.roi_semaforo.split(",")]
    except Exception:
        pass

json_lock = threading.Lock()
simulador_semaforo = SimuladorTrafego()
detector_sinal_real = DetectorSemaforoReal(modo_padrao=args.tipo_semaforo)
ultimo_veiculos_na_tela = 0
ultimo_info_sinal_real = {
    "cor_atual": "DESCONHECIDO",
    "fase_pedestre": "DESCONHECIDO",
    "cor_pedestre": "DESCONHECIDO",
    "tipo_semaforo": args.tipo_semaforo.upper(),
    "tempo_na_fase_s": 0.0,
    "ultimo_verde_real_s": 0.0,
    "ultimo_vermelho_real_s": 0.0,
    "ultimo_amarelo_real_s": 0.0,
    "ciclo_total_real_s": 0.0
}


def registrar_metricas_csv(sim_metricas, qtd_cruzou, media_tela, nivel_fluxo, info_real=None):
    try:
        arquivo_novo = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0
        with open(CSV_FILE, "a", encoding="utf-8-sig") as f:
            if arquivo_novo:
                cabecalho = [
                    "Data e Hora",
                    "Veiculos Cruzaram",
                    "Densidade Media (Tela)",
                    "Classificacao do Fluxo",
                    "Sinal Real da Rua (Cor)",
                    "Verde Real Medido (s)",
                    "Vermelho Real Medido (s)",
                    "Ciclo Real Rua (s)",
                    "Tempo Verde IA (s)",
                    "Tempo Verde Fixo (s)",
                    "Fila com IA (veiculos)",
                    "Fila Tradicional (veiculos)",
                    "Espera Media IA (s)",
                    "Espera Media Fixo (s)",
                    "Ganho de Eficiencia (%)"
                ]
                f.write(";".join(cabecalho) + "\n")

            fixo = sim_metricas.get("fixo", {})
            ai = sim_metricas.get("adaptativo", {})
            comp = sim_metricas.get("comparativo", {})
            real = info_real or {}

            ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            cor_agora = real.get("cor_atual", "DESCONHECIDO")
            tempo_fase_atual = real.get("tempo_na_fase_s", 0.0)
            if cor_agora == "VERDE":
                verde_medido = round(tempo_fase_atual, 1)
                verm_medido = real.get("ultimo_vermelho_real_s", 0.0)
            elif cor_agora == "VERMELHO":
                verde_medido = real.get("ultimo_verde_real_s", 0.0)
                verm_medido = round(tempo_fase_atual, 1)
            else:
                verde_medido = real.get("ultimo_verde_real_s", 0.0)
                verm_medido = real.get("ultimo_vermelho_real_s", 0.0)

            ciclo_estimado = round(verde_medido + verm_medido, 1) if (verde_medido + verm_medido) > 0 else real.get("ciclo_total_real_s", 0.0)

            dados_linha = [
                str(ts),
                str(qtd_cruzou),
                f"{media_tela:.1f}",
                str(nivel_fluxo),
                str(cor_agora),
                f"{verde_medido:.1f}",
                f"{verm_medido:.1f}",
                f"{ciclo_estimado:.1f}",
                str(ai.get('tempo_verde_atual', 0)),
                str(fixo.get('tempo_verde_config', 35)),
                str(ai.get('fila_atual', 0)),
                str(fixo.get('fila_atual', 0)),
                str(ai.get('tempo_medio_espera_s', 0)),
                str(fixo.get('tempo_medio_espera_s', 0)),
                f"{comp.get('reducao_tempo_espera_pct', 0)}%"
            ]
            f.write(";".join(dados_linha) + "\n")

        try:
            from gerar_excel import converter_csv_para_excel
            converter_csv_para_excel()
        except Exception:
            pass
    except Exception as e:
        print(f"Erro ao gravar CSV/Excel: {e}")


class StreamReader(threading.Thread):
    def __init__(self, cap, target_fps=10):
        super().__init__(daemon=True)
        self.cap = cap
        self.stopped = False
        self.frames_read = 0
        self.queue = deque(maxlen=600)

        self.stream_fps = cap.get(cv2.CAP_PROP_FPS)
        if not self.stream_fps or self.stream_fps < 1:
            self.stream_fps = 30.0

        self.frame_skip = max(1, int(self.stream_fps / target_fps))
        print(f"Stream original a {self.stream_fps} FPS. Intervalo de leitura: {self.frame_skip} quadros para ~{target_fps} FPS.")

    def run(self):
        count = 0
        while not self.stopped and running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            count += 1
            if count % self.frame_skip == 0:
                self.queue.append(frame)
            self.frames_read += 1

    def stop(self):
        self.stopped = True


def get_next_frame(reader_thread):
    if len(reader_thread.queue) > 0:
        return reader_thread.queue.popleft()
    return None


def get_stream_url(youtube_url, quality="720"):
    print(f"Obtendo URL da transmissao: {youtube_url}")

    if quality == "best":
        fmt = "best[ext=mp4]/best"
    elif quality in ["360", "480", "720", "1080"]:
        fmt = f"best[height<={quality}][ext=mp4]/best[height<={quality}]/best"
    else:
        fmt = "best[height<=720][ext=mp4]/best"

    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp",
             "--get-url", "-f", fmt,
             "--no-warnings",
             "--extractor-args", "youtube:player_client=android",
             youtube_url],
            capture_output=True, text=True, timeout=30
        )
        url = result.stdout.strip().split('\n')[0]
        if url and url.startswith("http"):
            print("URL do stream obtida com sucesso.")
            return url

        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp",
             "--get-url", "-f", "best",
             "--no-warnings",
             "--extractor-args", "youtube:player_client=android",
             youtube_url],
            capture_output=True, text=True, timeout=30
        )
        url = result.stdout.strip().split('\n')[0]
        if url and url.startswith("http"):
            return url

        print(f"Erro yt-dlp: {result.stderr.strip()}")
        return None
    except Exception as e:
        print(f"Erro na captura do stream: {e}")
        return None


def get_linha_y(cx):
    return int(linha_y_esq + (linha_y_dir - linha_y_esq) * (cx / WIDTH))


def classificar_fluxo(qtd_cruzou, media_tela):
    if media_tela >= 6.0:
        return "CONGESTIONADO"
    elif media_tela >= 3.5:
        return "ALTO"

    if qtd_cruzou >= 15:
        return "ALTO"
    elif qtd_cruzou >= 8:
        return "MEDIO"

    return "BAIXO"


def salvar_json():
    total_real = total_veiculos_anteriores + len(ids_vistos_total)

    semaforo_metricas = simulador_semaforo.passo(
        qtd_cruzou_intervalo=len(ids_intervalo),
        veiculos_na_tela=ultimo_veiculos_na_tela,
        intervalo_segundos=INTERVALO
    )

    media_dens = round(soma_veiculos_tela / max(1, frames_no_intervalo), 1) if frames_no_intervalo > 0 else ultimo_veiculos_na_tela

    dados = {
        "total_veiculos": total_real,
        "intervalo_atual": len(ids_intervalo),
        "veiculos_na_tela": ultimo_veiculos_na_tela,
        "densidade_media": media_dens,
        "fluxo": fluxo_atual,
        "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tempo_intervalo": INTERVALO,
        "frame_atual": frame_count,
        "stream_status": stream_status,
        "fps_processamento": round(fps_real, 1),
        "fonte": "LIVE - YouTube",
        "semaforo": semaforo_metricas,
        "semaforo_real": ultimo_info_sinal_real,
        "motor_decisao": semaforo_metricas.get("motor_decisao", {}),
        "historico": historico[-50:]
    }
    try:
        with json_lock:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def conectar_stream(youtube_url, quality):
    stream_url = get_stream_url(youtube_url, quality)
    if not stream_url:
        return None

    print("Conectando via OpenCV...")
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("Falha ao abrir stream de video.")
        return None

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    print("Conexao estabelecida.")
    return cap


print("Carregando modelo YOLO...")
model = YOLO(MODEL_PATH)
print("Modelo carregado com sucesso.")

if hasattr(model, 'names'):
    print(f"Classes registradas no modelo: {len(model.names)}")

print("-" * 50)
print(f"URBANO - Monitoramento de Trafego")
print(f"Origem: {YOUTUBE_URL[-50:]}")
print(f"Intervalo: {INTERVALO}s | Confianca: {CONFIDENCE} | Resolucao: {IMG_SIZE}")
print(f"Linha de corte: esq={linha_y_esq} dir={linha_y_dir}")
print(f"Comandos: ESC = sair | P = modo pedestre/veicular | L = alternar linha | Clique = fixar ROI")
print("-" * 50)

salvar_json()

cap = conectar_stream(YOUTUBE_URL, QUALITY)
if not cap:
    print("Nao foi possivel conectar a transmissao.")
    sys.exit(1)

stream_status = "ao_vivo"
salvar_json()

reader = StreamReader(cap, target_fps=TARGET_FPS)
reader.start()

print("Preenchendo buffer inicial...", end=" ", flush=True)
while len(reader.queue) < 40 and not reader.stopped:
    time.sleep(0.3)
print(f"OK ({len(reader.queue)} frames).")


def on_mouse_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        detector_sinal_real.selecionar_por_clique(x, y)


if not HEADLESS:
    cv2.namedWindow("URBANO - Live", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("URBANO - Live", 1200, 700)
    cv2.setMouseCallback("URBANO - Live", on_mouse_click)

inicio = time.time()
ultima_escrita_json = time.time()
INTERVALO_JSON = 1.0
frames_processados = 0
fps_timer = time.time()
show_linha = True
sem_frame_count = 0
reconexoes = 0

print("Processamento iniciado.\n")

try:
    while running:
        frame = get_next_frame(reader)

        if frame is None:
            sem_frame_count += 1
            if sem_frame_count > 100:
                print("\nAusencia de frames no buffer. Reconectando stream...")
                stream_status = "reconectando"
                salvar_json()
                reader.stop()
                cap.release()
                time.sleep(3)

                cap = conectar_stream(YOUTUBE_URL, QUALITY)
                if cap:
                    reader = StreamReader(cap, target_fps=TARGET_FPS)
                    reader.start()
                    stream_status = "ao_vivo"
                    sem_frame_count = 0
                    reconexoes += 1
                    print(f"Reconectado com sucesso (tentativa {reconexoes}).")
                else:
                    print("Falha na reconexao. Nova tentativa em 10s...")
                    time.sleep(10)
            else:
                time.sleep(0.1)
            continue

        sem_frame_count = 0
        frame_count += 1
        frames_processados += 1

        frame = cv2.resize(frame, (WIDTH, HEIGHT))

        results = model.track(
            frame,
            persist=True,
            conf=CONFIDENCE,
            imgsz=IMG_SIZE,
            tracker="bytetrack.yaml",
            classes=[2, 3, 5, 7],
            verbose=False
        )

        veiculos_na_tela = 0
        cruzaram_neste_frame = 0

        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            cls_ids = boxes.cls.int().cpu().tolist()
            xyxy_all = boxes.xyxy.cpu().tolist()
            ids_all = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(cls_ids)
            veiculos_na_tela = len(cls_ids)

            for i, id_ in enumerate(ids_all):
                if id_ is not None:
                    x1, y1, x2, y2 = xyxy_all[i]
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    ly = get_linha_y(cx)

                    if id_ not in ids_ja_contados:
                        if id_ in posicoes_anteriores:
                            cy_anterior = posicoes_anteriores[id_]
                            if cy_anterior < ly <= cy:
                                ids_vistos_total.add(id_)
                                ids_intervalo.add(id_)
                                ids_ja_contados.add(id_)
                                cruzaram_neste_frame += 1

                    posicoes_anteriores[id_] = cy

        ultimo_info_sinal_real = detector_sinal_real.processar_frame(
            frame,
            roi_manual=roi_semaforo_config,
            cruzaram_instante=cruzaram_neste_frame,
            veiculos_na_tela=veiculos_na_tela,
            motor_decisao=simulador_semaforo.motor_decisao
        )

        ultimo_veiculos_na_tela = veiculos_na_tela
        soma_veiculos_tela += veiculos_na_tela
        frames_no_intervalo += 1

        agora = time.time()
        if agora - fps_timer >= 5.0:
            fps_real = frames_processados / (agora - fps_timer)
            frames_processados = 0
            fps_timer = agora

        if os.path.exists("stop.txt"):
            print("\nSinal de parada (stop.txt) recebido. Encerrando...")
            os.remove("stop.txt")
            break

        if agora - inicio >= INTERVALO:
            media_veiculos_tela = soma_veiculos_tela / max(1, frames_no_intervalo)
            qtd = len(ids_intervalo)
            nivel = classificar_fluxo(qtd, media_veiculos_tela)
            fluxo_atual = nivel

            total = total_veiculos_anteriores + len(ids_vistos_total)

            print(f"[{INTERVALO}s] Cruzaram: {qtd} | Densidade media: {media_veiculos_tela:.1f} | Fluxo: {nivel} | "
                  f"Total: {total} | Sinal: {ultimo_info_sinal_real['cor_atual']} | FPS: {fps_real:.1f}")

            historico.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "veiculos": qtd,
                "fluxo": nivel,
                "total_acumulado": total,
                "sinal_real": ultimo_info_sinal_real.get("cor_atual", "DESCONHECIDO")
            })

            if len(historico) > 30:
                historico.pop(0)

            ids_intervalo.clear()
            soma_veiculos_tela = 0
            frames_no_intervalo = 0
            inicio = agora

            metricas_atuais = simulador_semaforo.passo(qtd, media_veiculos_tela, INTERVALO)
            registrar_metricas_csv(metricas_atuais, qtd, media_veiculos_tela, nivel, ultimo_info_sinal_real)
            salvar_json()

        if agora - ultima_escrita_json >= INTERVALO_JSON:
            salvar_json()
            ultima_escrita_json = agora

        annotated = results[0].plot()

        detector_sinal_real.desenhar_painel_visual(annotated, ultimo_info_sinal_real, roi_config=roi_semaforo_config)

        if show_linha:
            cv2.line(annotated, (0, linha_y_esq), (WIDTH, linha_y_dir), (0, 0, 255), 2)
            mid_y = (linha_y_esq + linha_y_dir) // 2
            cv2.putText(annotated, "RADAR",
                        (WIDTH // 2 - 30, mid_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        total = total_veiculos_anteriores + len(ids_vistos_total)
        q_size = len(reader.queue)

        cv2.putText(annotated, f"LIVE | Total: {total}",
                    (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 255, 0), 2)

        cv2.putText(annotated, f"Intervalo: {len(ids_intervalo)}",
                    (20, 65), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 0), 2)

        delay_sec = q_size / max(fps_real, 1.0)
        cv2.putText(annotated, f"FPS processado: {fps_real:.1f}",
                    (20, HEIGHT - 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (180, 180, 180), 1)
        cv2.putText(annotated, f"Buffer: {q_size} quadros (~{delay_sec:.1f}s)",
                    (20, HEIGHT - 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (180, 200, 255), 1)

        cv2.putText(annotated, datetime.now().strftime('%H:%M:%S'),
                    (WIDTH - 120, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (180, 180, 180), 1)

        if not HEADLESS:
            cv2.imshow("URBANO - Live", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                print("\nEncerrado pelo operador (ESC).")
                break
            elif key == ord('l') or key == ord('L'):
                show_linha = not show_linha
            elif key == ord('p') or key == ord('P'):
                detector_sinal_real.alternar_modo()
            elif key == ord('+') or key == ord('='):
                linha_y_esq += 10
                linha_y_dir += 10
                print(f"Linha ajustada: esq={linha_y_esq} dir={linha_y_dir}")
            elif key == ord('-') or key == ord('_'):
                linha_y_esq -= 10
                linha_y_dir -= 10
                print(f"Linha ajustada: esq={linha_y_esq} dir={linha_y_dir}")

except KeyboardInterrupt:
    print("\nInterrompido por Ctrl+C.")

running = False
reader.stop()
stream_status = "offline"
salvar_json()

cap.release()
if not HEADLESS:
    cv2.destroyAllWindows()

print(f"\n{'-' * 50}")
print("Sessao finalizada com sucesso.")
print(f"Total de veiculos contabilizados: {total_veiculos_anteriores + len(ids_vistos_total)}")
print(f"Total de quadros processados: {frame_count}")
print(f"Arquivo de telemetria: {JSON_FILE}")
print(f"{'-' * 50}")
