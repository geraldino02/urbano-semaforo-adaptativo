"""
Motor de decisao inteligente do semaforo.
Realiza a auto-calibracao sensorial (correlacao pedestre x fluxo de carros)
e decide extensoes (Green Extension) ou cortes de verde (Green Truncation) conforme a demanda.
"""

import time


class MotorDecisaoTrafego:
    """Motor de decisao para temporizacao adaptativa e auto-calibracao sensorial."""

    def __init__(self, verde_min=12.0, verde_max=55.0, tempo_amarelo=4.0):
        self.verde_min = verde_min
        self.verde_max = verde_max
        self.tempo_amarelo = tempo_amarelo

        self.modo_semaforo_inferido = "AUTO"
        self.confianca_inversao = 0.0
        self.amostras_cruzamento_vermelho = 0
        self.amostras_cruzamento_verde = 0
        self.amostras_analisadas = 0
        self.ultima_cor_observada = None
        self.tempo_inicio_cor = time.time()
        self.calibrado = False

        self.ultima_acao = "MONITORANDO"
        self.ultima_justificativa = "Inicializando motor de decisao..."

    def auto_calibrar_tipo_semaforo(self, cor_bruta_detectada, cruzaram_no_instante, veiculos_na_tela, bbox_tl=None):
        """Avalia se a sinalizacao observada opera como semaforo de pedestres ou veicular."""
        if cor_bruta_detectada == "DESCONHECIDO":
            return self.modo_semaforo_inferido

        agora = time.time()
        if cor_bruta_detectada != self.ultima_cor_observada:
            self.ultima_cor_observada = cor_bruta_detectada
            self.tempo_inicio_cor = agora

        tempo_na_cor = agora - self.tempo_inicio_cor

        if tempo_na_cor >= 2.0:
            if cruzaram_no_instante > 0 or veiculos_na_tela >= 2:
                self.amostras_analisadas += 1
                if cor_bruta_detectada == "VERMELHO":
                    self.amostras_cruzamento_vermelho += cruzaram_no_instante + (1 if veiculos_na_tela >= 2 else 0)
                elif cor_bruta_detectada == "VERDE":
                    self.amostras_cruzamento_verde += cruzaram_no_instante + (1 if veiculos_na_tela >= 2 else 0)

        peso_geometrico = 0.0
        if bbox_tl and len(bbox_tl) == 4:
            x1, y1, x2, y2 = bbox_tl
            w = max(1, abs(x2 - x1))
            h = max(1, abs(y2 - y1))
            ratio = h / float(w)
            if 1.4 <= ratio <= 2.2:
                peso_geometrico = 0.2

        total_amostras = self.amostras_cruzamento_vermelho + self.amostras_cruzamento_verde
        if total_amostras >= 4:
            taxa_inversao = (self.amostras_cruzamento_vermelho / float(total_amostras)) + peso_geometrico
            self.confianca_inversao = min(1.0, round(taxa_inversao, 2))

            if self.confianca_inversao >= 0.65:
                if self.modo_semaforo_inferido != "PEDESTRE":
                    print(f"\n[Motor de Decisao] Auto-calibracao concluida: PEDESTRE (Inversao logica)")
                    print(f"   Confianca: {int(self.confianca_inversao * 100)}%")
                self.modo_semaforo_inferido = "PEDESTRE"
                self.calibrado = True
            elif self.confianca_inversao <= 0.35:
                if self.modo_semaforo_inferido != "VEICULAR":
                    print(f"\n[Motor de Decisao] Auto-calibracao concluida: VEICULAR (Leitura direta)")
                    print(f"   Confianca: {int((1.0 - self.confianca_inversao) * 100)}%")
                self.modo_semaforo_inferido = "VEICULAR"
                self.calibrado = True

        return self.modo_semaforo_inferido

    def decidir_proxima_fase(self, estado_atual, tempo_na_fase, fila_estimada, veiculos_na_tela, tempo_verde_atual):
        """Avalia extensoes e encerramentos da fase ativa."""
        acao = "MANTER"
        justificativa = ""

        if estado_atual == "VERDE":
            if tempo_na_fase >= self.verde_max:
                acao = "ENCERRAR_VERDE"
                justificativa = f"Teto maximo de verde atingido ({self.verde_max}s)."

            elif tempo_na_fase >= self.verde_min and fila_estimada < 0.5 and veiculos_na_tela <= 1:
                acao = "ENCERRAR_VERDE"
                economia = round(self.verde_max - tempo_na_fase, 1)
                justificativa = f"Fila esvaziada aos {tempo_na_fase:.1f}s. Encerramento antecipado economizando {economia}s."

            elif tempo_na_fase >= tempo_verde_atual and (fila_estimada >= 1.5 or veiculos_na_tela >= 3):
                acao = "ESTENDER_VERDE"
                justificativa = f"Fluxo intenso detectado ({veiculos_na_tela} veiculos na via). Estendendo verde."

            else:
                acao = "MANTER_VERDE"
                justificativa = f"Fluxo sendo atendido normalmente. Restam {max(0.0, tempo_verde_atual - tempo_na_fase):.1f}s."

        elif estado_atual == "AMARELO":
            if tempo_na_fase >= self.tempo_amarelo:
                acao = "FECHAR_VERMELHO"
                justificativa = f"Tempo de amarelo ({self.tempo_amarelo}s) concluido."
            else:
                acao = "MANTER_AMARELO"
                justificativa = f"Transicao de seguranca em curso ({self.tempo_amarelo - tempo_na_fase:.1f}s restantes)."

        elif estado_atual == "VERMELHO":
            if fila_estimada >= 5.0 or veiculos_na_tela >= 5:
                justificativa = f"Fila acumulada ({int(fila_estimada)} veiculos). Preparando abertura."
            else:
                justificativa = "Fase de retencao da via."

        self.ultima_acao = acao
        self.ultima_justificativa = justificativa
        return acao, justificativa

    def obter_status(self):
        return {
            "modo_sensor": self.modo_semaforo_inferido,
            "calibrado_automaticamente": self.calibrado,
            "confianca_calibracao_pct": int(self.confianca_inversao * 100) if self.calibrado else 0,
            "acao_atual": self.ultima_acao,
            "justificativa_decisao": self.ultima_justificativa
        }
