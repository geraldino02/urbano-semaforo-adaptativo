"""
Deteccao visual e classificacao de semaforos.
Monitora o semaforo de pedestres na calcada via cores HSV e filtro temporal anti-flicker,
identificando indiretamente quando a via veicular esta aberta ou fechada.
"""

import cv2
import numpy as np
import time
from collections import deque


def esta_na_roi(bbox_centro, roi):
    if not roi or len(roi) < 4:
        return False
    cx, cy = bbox_centro
    rx1, ry1, rx2, ry2 = roi
    return (min(rx1, rx2) <= cx <= max(rx1, rx2)) and (min(ry1, ry2) <= cy <= max(ry1, ry2))


class ClassificadorPedestre4Fases:
    """Classificador temporal para semaforos de pedestres (sem foco amarelo)."""

    def __init__(self, janela_s=1.8):
        self.janela_s = janela_s
        self.buffer = deque(maxlen=45)

        self.fase_pedestre = "DESCONHECIDO"
        self.cor_via = "DESCONHECIDO"
        self.ts_inicio_fase_pedestre = time.time()
        self.ts_inicio_fase_via = time.time()
        self.ultimo_valido_ts = 0.0

        self.ultimo_vermelho_fixo_s = 0.0
        self.ultimo_vermelho_piscante_s = 0.0
        self.ultimo_verde_fixo_s = 0.0
        self.ultimo_verde_piscante_s = 0.0

        self.ultimo_verde_via_s = 0.0
        self.ultimo_amarelo_via_s = 0.0
        self.ultimo_vermelho_via_s = 0.0
        self.ultimo_ciclo_completo_s = 0.0
        self.ciclos_concluidos = 0

    def extrair_mascaras_hsv(self, crop_bgr):
        if crop_bgr is None or crop_bgr.size == 0:
            return 0, 0
        h, w = crop_bgr.shape[:2]
        if h < 6 or w < 6:
            return 0, 0

        metade = h // 2
        top = crop_bgr[:metade, :]
        bot = crop_bgr[metade:, :]

        hsv_top = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)
        m_r1 = cv2.inRange(hsv_top, np.array([0, 50, 70]), np.array([12, 255, 255]))
        m_r2 = cv2.inRange(hsv_top, np.array([160, 50, 70]), np.array([180, 255, 255]))
        m_r3 = cv2.inRange(hsv_top, np.array([0, 20, 180]), np.array([15, 80, 255]))
        hsv_r_count = cv2.countNonZero(cv2.bitwise_or(m_r1, cv2.bitwise_or(m_r2, m_r3)))

        b_t, g_t, r_t = cv2.split(top)
        rgb_r_count = np.count_nonzero((r_t.astype(int) > 115) & (r_t.astype(int) > g_t.astype(int) + 35) & (r_t.astype(int) > b_t.astype(int) + 35))
        score_r = max(hsv_r_count, rgb_r_count)

        hsv_bot = cv2.cvtColor(bot, cv2.COLOR_BGR2HSV)
        m_g1 = cv2.inRange(hsv_bot, np.array([35, 40, 60]), np.array([95, 255, 255]))
        m_g2 = cv2.inRange(hsv_bot, np.array([38, 15, 170]), np.array([92, 80, 255]))
        hsv_g_count = cv2.countNonZero(cv2.bitwise_or(m_g1, m_g2))

        b_b, g_b, r_b = cv2.split(bot)
        rgb_g_count = np.count_nonzero((g_b.astype(int) > 75) & (g_b.astype(int) > r_b.astype(int) + 20) & (g_b.astype(int) > b_b.astype(int) + 10))
        score_g = max(hsv_g_count, rgb_g_count)

        return score_r, score_g

    def processar_frame(self, crop_bgr, agora=None):
        if agora is None:
            agora = time.time()

        score_r, score_g = self.extrair_mascaras_hsv(crop_bgr)
        limiar_ativo = 14
        r_on = (score_r >= limiar_ativo and score_r > score_g * 1.3)
        g_on = (score_g >= limiar_ativo and score_g > score_r * 1.3)

        self.buffer.append((agora, r_on, g_on, score_r, score_g))

        amostras = [a for a in self.buffer if (agora - a[0]) <= self.janela_s]
        n = len(amostras)
        if n < 3:
            return self.fase_pedestre, self.cor_via

        r_count = sum(1 for a in amostras if a[1])
        g_count = sum(1 for a in amostras if a[2])
        r_trans = sum(1 for i in range(1, n) if amostras[i][1] != amostras[i - 1][1])
        g_trans = sum(1 for i in range(1, n) if amostras[i][2] != amostras[i - 1][2])

        nova_fase_ped = "DESCONHECIDO"
        nova_cor_via = "DESCONHECIDO"

        if g_trans >= 2 and g_count >= 2 and r_count <= 1:
            nova_fase_ped = "VERDE_PISCANTE"
            nova_cor_via = "VERMELHO"

        elif r_trans >= 2 and r_count >= 2 and g_count <= 1:
            nova_fase_ped = "VERMELHO_PISCANTE"
            nova_cor_via = "AMARELO"

        elif g_count >= 0.45 * n and g_trans < 2 and r_count <= 1:
            nova_fase_ped = "VERDE_FIXO"
            nova_cor_via = "VERMELHO"

        elif r_count >= 0.45 * n and r_trans < 2 and g_count <= 1:
            nova_fase_ped = "VERMELHO_FIXO"
            nova_cor_via = "VERDE"

        if nova_fase_ped != "DESCONHECIDO":
            self.ultimo_valido_ts = agora

            if nova_fase_ped != self.fase_pedestre:
                duracao_ped = round(agora - self.ts_inicio_fase_pedestre, 1)
                if self.fase_pedestre == "VERDE_FIXO":
                    self.ultimo_verde_fixo_s = duracao_ped
                elif self.fase_pedestre == "VERDE_PISCANTE":
                    self.ultimo_verde_piscante_s = duracao_ped
                elif self.fase_pedestre == "VERMELHO_PISCANTE":
                    self.ultimo_vermelho_piscante_s = duracao_ped
                elif self.fase_pedestre == "VERMELHO_FIXO":
                    self.ultimo_vermelho_fixo_s = duracao_ped

                if nova_cor_via != self.cor_via and self.cor_via != "DESCONHECIDO":
                    duracao_via = round(agora - self.ts_inicio_fase_via, 1)
                    if self.cor_via == "VERDE":
                        self.ultimo_verde_via_s = duracao_via
                    elif self.cor_via == "AMARELO":
                        self.ultimo_amarelo_via_s = duracao_via
                    elif self.cor_via == "VERMELHO":
                        self.ultimo_vermelho_via_s = duracao_via
                        self.ciclos_concluidos += 1
                        self.ultimo_ciclo_completo_s = round(
                            self.ultimo_verde_via_s + self.ultimo_amarelo_via_s + self.ultimo_vermelho_via_s, 1
                        )
                    self.ts_inicio_fase_via = agora

                self.fase_pedestre = nova_fase_ped
                self.cor_via = nova_cor_via
                self.ts_inicio_fase_pedestre = agora

        elif agora - self.ultimo_valido_ts > 2.5:
            self.fase_pedestre = "DESCONHECIDO"
            self.cor_via = "DESCONHECIDO"

        return self.fase_pedestre, self.cor_via


class DetectorSemaforoReal:
    def __init__(self, tempo_min_fase=3.0, tempo_confirmacao=0.8, modo_padrao="PEDESTRE"):
        self.tempo_minimo_fase = tempo_min_fase
        self.tempo_confirmacao = tempo_confirmacao

        self.tipo_semaforo = modo_padrao.upper()
        self.cor_atual = "DESCONHECIDO"
        self.fase_pedestre = "DESCONHECIDO"
        self.cor_pedestre = "DESCONHECIDO"

        self.tempo_inicio_fase = time.time()
        self.tempo_na_fase = 0.0

        self.classificador_pedestre = ClassificadorPedestre4Fases()

        self.ultimo_verde_real = 0.0
        self.ultimo_vermelho_real = 0.0
        self.ultimo_amarelo_real = 0.0
        self.ultimo_ciclo_completo = 0.0
        self.ciclos_concluidos = 0

        self.roi_padrao_pedestre = (47, 120, 70, 180)
        self.caixa_fixada = None

    def alternar_modo(self):
        self.tipo_semaforo = "VEICULAR" if self.tipo_semaforo == "PEDESTRE" else "PEDESTRE"
        print(f"\n[Modo Semaforo Alterado] Novo modo: {self.tipo_semaforo}")
        self.cor_atual = "DESCONHECIDO"
        self.fase_pedestre = "DESCONHECIDO"
        self.tempo_inicio_fase = time.time()

    def processar_frame(self, frame_bgr, boxes_semaforo_yolo=None, roi_manual=None, cruzaram_instante=0, veiculos_na_tela=0, motor_decisao=None):
        agora = time.time()
        h_f, w_f = frame_bgr.shape[:2]

        if self.caixa_fixada:
            roi_ativa = self.caixa_fixada
        elif roi_manual and len(roi_manual) == 4:
            roi_ativa = tuple(int(v) for v in roi_manual)
        elif self.tipo_semaforo == "PEDESTRE":
            roi_ativa = self.roi_padrao_pedestre
        else:
            roi_ativa = None

        caixa_escolhida = roi_ativa
        cor_via_instante = "DESCONHECIDO"
        fase_ped_instante = "DESCONHECIDO"

        if self.tipo_semaforo == "PEDESTRE" and roi_ativa:
            rx1, ry1, rx2, ry2 = [int(v) for v in roi_ativa]
            rx1, ry1 = max(0, min(rx1, rx2)), max(0, min(ry1, ry2))
            rx2, ry2 = min(w_f, max(rx1, rx2)), min(h_f, max(ry1, ry2))

            if rx2 > rx1 and ry2 > ry1:
                crop_ped = frame_bgr[ry1:ry2, rx1:rx2]
                fase_ped_instante, cor_via_instante = self.classificador_pedestre.processar_frame(crop_ped, agora=agora)
                caixa_escolhida = (rx1, ry1, rx2, ry2)

        elif self.tipo_semaforo == "VEICULAR" and roi_ativa:
            rx1, ry1, rx2, ry2 = [int(v) for v in roi_ativa]
            crop = frame_bgr[ry1:ry2, rx1:rx2]
            cor_via_instante = self._analisar_veicular_3tercos(crop)
            fase_ped_instante = "NAO_APLICAVEL"
            caixa_escolhida = (rx1, ry1, rx2, ry2)

        if self.tipo_semaforo == "PEDESTRE":
            self.fase_pedestre = fase_ped_instante
            if "VERMELHO" in fase_ped_instante:
                self.cor_pedestre = "VERMELHO"
            elif "VERDE" in fase_ped_instante:
                self.cor_pedestre = "VERDE"
            else:
                self.cor_pedestre = "DESCONHECIDO"

            if cor_via_instante != "DESCONHECIDO":
                if self.cor_atual == "DESCONHECIDO" or cor_via_instante != self.cor_atual:
                    self.cor_atual = cor_via_instante
                    self.tempo_inicio_fase = agora

            self.ultimo_verde_real = self.classificador_pedestre.ultimo_verde_via_s
            self.ultimo_amarelo_real = self.classificador_pedestre.ultimo_amarelo_via_s
            self.ultimo_vermelho_real = self.classificador_pedestre.ultimo_vermelho_via_s
            self.ultimo_ciclo_completo = self.classificador_pedestre.ultimo_ciclo_completo_s
            self.ciclos_concluidos = self.classificador_pedestre.ciclos_concluidos
        else:
            if cor_via_instante != "DESCONHECIDO" and cor_via_instante != self.cor_atual:
                self.cor_atual = cor_via_instante
                self.tempo_inicio_fase = agora

        self.tempo_na_fase = round(agora - self.tempo_inicio_fase, 1)

        if motor_decisao:
            motor_decisao.auto_calibrar_tipo_semaforo(
                cor_bruta_detectada=self.cor_pedestre if self.tipo_semaforo == "PEDESTRE" else self.cor_atual,
                cruzaram_no_instante=cruzaram_instante,
                veiculos_na_tela=veiculos_na_tela,
                bbox_tl=caixa_escolhida
            )

        return {
            "cor_atual": self.cor_atual,
            "fase_pedestre": self.fase_pedestre,
            "cor_pedestre": self.cor_pedestre,
            "tipo_semaforo": self.tipo_semaforo,
            "modo_efetivo": "PEDESTRE",
            "tempo_na_fase_s": self.tempo_na_fase,
            "ultimo_verde_real_s": self.ultimo_verde_real,
            "ultimo_vermelho_real_s": self.ultimo_vermelho_real,
            "ultimo_amarelo_real_s": self.ultimo_amarelo_real,
            "ciclo_total_real_s": self.ultimo_ciclo_completo,
            "ciclos_medidos": self.ciclos_concluidos,
            "caixa_detectada": caixa_escolhida,
            "roi_ativa": roi_ativa,
            "detalhes_pedestre": {
                "verde_fixo_s": self.classificador_pedestre.ultimo_verde_fixo_s,
                "verde_piscante_s": self.classificador_pedestre.ultimo_verde_piscante_s,
                "vermelho_piscante_s": self.classificador_pedestre.ultimo_vermelho_piscante_s,
                "vermelho_fixo_s": self.classificador_pedestre.ultimo_vermelho_fixo_s
            }
        }

    def _analisar_veicular_3tercos(self, crop):
        if crop is None or crop.size == 0:
            return "DESCONHECIDO"
        h = crop.shape[0]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask_r1 = cv2.inRange(hsv, np.array([0, 70, 100]), np.array([10, 255, 255]))
        mask_r2 = cv2.inRange(hsv, np.array([160, 70, 100]), np.array([180, 255, 255]))
        mask_red = cv2.bitwise_or(mask_r1, mask_r2)
        mask_yellow = cv2.inRange(hsv, np.array([11, 80, 120]), np.array([35, 255, 255]))
        mask_green = cv2.inRange(hsv, np.array([36, 60, 95]), np.array([95, 255, 255]))

        pts_r = cv2.countNonZero(mask_red[:int(h * 0.35), :])
        pts_y = cv2.countNonZero(mask_yellow[int(h * 0.33):int(h * 0.67), :])
        pts_g = cv2.countNonZero(mask_green[int(h * 0.65):, :])

        max_pts = max(pts_r, pts_y, pts_g)
        if max_pts < 30:
            return "DESCONHECIDO"
        if max_pts == pts_r:
            return "VERMELHO"
        elif max_pts == pts_g:
            return "VERDE"
        elif max_pts == pts_y:
            return "AMARELO"
        return "DESCONHECIDO"

    def selecionar_por_clique(self, click_x, click_y, boxes_yolo=None):
        raio_w, raio_h = 30, 45
        self.caixa_fixada = (max(0, click_x - raio_w), max(0, click_y - raio_h), click_x + raio_w, click_y + raio_h)
        print(f"\n[ROI] Semaforo fixado manualmente pelo clique: {self.caixa_fixada}")
        print(f"Comando alternativo: --roi-semaforo {self.caixa_fixada[0]},{self.caixa_fixada[1]},{self.caixa_fixada[2]},{self.caixa_fixada[3]}")

    def desenhar_painel_visual(self, frame_annotated, info_semaforo, roi_config=None):
        caixa = info_semaforo.get("caixa_detectada")
        cor_v = info_semaforo.get("cor_atual", "DESCONHECIDO")
        fase_ped = info_semaforo.get("fase_pedestre", "DESCONHECIDO")
        tempo = info_semaforo.get("tempo_na_fase_s", 0.0)

        cores_bgr = {
            "VERMELHO": (0, 0, 255),
            "AMARELO": (0, 215, 255),
            "VERDE": (0, 255, 0),
            "DESCONHECIDO": (180, 180, 180)
        }
        bgr_via = cores_bgr.get(cor_v, (180, 180, 180))

        if caixa and len(caixa) == 4:
            x1, y1, x2, y2 = [int(v) for v in caixa]
            cv2.rectangle(frame_annotated, (x1, y1), (x2, y2), (255, 200, 0), 2)
            cv2.putText(frame_annotated, f"PEDESTRE: {fase_ped}", (x1 - 15, max(14, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
            cv2.putText(frame_annotated, f"VIA: {cor_v}", (x1, min(frame_annotated.shape[0] - 5, y2 + 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, bgr_via, 2)

        h, w = frame_annotated.shape[:2]
        hud_text = f"SINAL VIA: {cor_v} ({tempo:.1f}s) | PEDESTRE: {fase_ped}"
        if info_semaforo.get("ultimo_verde_real_s", 0) > 0:
            hud_text += f" | U.Verde: {info_semaforo['ultimo_verde_real_s']}s"
        if info_semaforo.get("ultimo_vermelho_real_s", 0) > 0:
            hud_text += f" | U.Verm: {info_semaforo['ultimo_vermelho_real_s']}s"
        if info_semaforo.get("ciclo_total_real_s", 0) > 0:
            hud_text += f" | Ciclo: {info_semaforo['ciclo_total_real_s']}s"

        cv2.rectangle(frame_annotated, (10, h - 75), (w - 10, h - 48), (15, 15, 20), -1)
        cv2.putText(frame_annotated, hud_text, (18, h - 56),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, bgr_via, 2)
