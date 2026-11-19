"""
Simulador comparativo de trafego em tempo discreto.
Executa em paralelo o modelo de tempo fixo tradicional e o modelo adaptativo com IA,
calculando tamanho de filas, tempos de espera e percentual de economia de tempo.
"""

import time
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from motor_decisao import MotorDecisaoTrafego


class SemaforoFixo:
    """Modelo semaforico de tempo fixo."""

    def __init__(self, tempo_verde=35, tempo_amarelo=4, tempo_vermelho=35):
        self.tempo_verde = tempo_verde
        self.tempo_amarelo = tempo_amarelo
        self.tempo_vermelho = tempo_vermelho
        self.duracao_ciclo = tempo_verde + tempo_amarelo + tempo_vermelho

        self.estado = "VERDE"
        self.tempo_no_estado = 0.0
        self.fila_veiculos = 0
        self.tempo_espera_acumulado = 0.0
        self.veiculos_atendidos = 0
        self.historico_espera = []

    def atualizar(self, delta_t, taxa_chegada_por_segundo, taxa_vazao_por_segundo=0.45):
        novos_veiculos = taxa_chegada_por_segundo * delta_t
        self.fila_veiculos += novos_veiculos
        self.tempo_no_estado += delta_t

        if self.estado == "VERDE":
            vazao = min(self.fila_veiculos, taxa_vazao_por_segundo * delta_t)
            self.fila_veiculos -= vazao
            self.veiculos_atendidos += vazao

            if self.tempo_no_estado >= self.tempo_verde:
                self.estado = "AMARELO"
                self.tempo_no_estado = 0.0

        elif self.estado == "AMARELO":
            vazao = min(self.fila_veiculos, (taxa_vazao_por_segundo * 0.3) * delta_t)
            self.fila_veiculos -= vazao
            self.veiculos_atendidos += vazao

            if self.tempo_no_estado >= self.tempo_amarelo:
                self.estado = "VERMELHO"
                self.tempo_no_estado = 0.0

        elif self.estado == "VERMELHO":
            self.tempo_espera_acumulado += (self.fila_veiculos * delta_t)

            if self.tempo_no_estado >= self.tempo_vermelho:
                self.estado = "VERDE"
                self.tempo_no_estado = 0.0

        if self.veiculos_atendidos > 0:
            tempo_medio = self.tempo_espera_acumulado / self.veiculos_atendidos
            self.historico_espera.append(tempo_medio)

    def get_tempo_restante(self):
        if self.estado == "VERDE":
            return max(0.0, self.tempo_verde - self.tempo_no_estado)
        elif self.estado == "AMARELO":
            return max(0.0, self.tempo_amarelo - self.tempo_no_estado)
        else:
            return max(0.0, self.tempo_vermelho - self.tempo_no_estado)


class SemaforoAdaptativo:
    """Modelo semaforico adaptativo atuado por fluxo."""

    def __init__(self, verde_min=12, verde_max=55, tempo_amarelo=4, vermelho_base=30, motor_decisao=None):
        self.verde_min = verde_min
        self.verde_max = verde_max
        self.tempo_amarelo = tempo_amarelo
        self.vermelho_base = vermelho_base
        self.motor_decisao = motor_decisao

        self.tempo_verde_atual = verde_min
        self.tempo_vermelho_atual = vermelho_base

        self.estado = "VERDE"
        self.tempo_no_estado = 0.0
        self.fila_veiculos = 0
        self.tempo_espera_acumulado = 0.0
        self.veiculos_atendidos = 0
        self.historico_espera = []

    def calcular_tempo_verde_ideal(self, veiculos_detectados, taxa_chegada):
        tempo_por_carro = 2.2
        demanda_tempo = self.verde_min + (veiculos_detectados * tempo_por_carro) + (taxa_chegada * 10)
        verde_calculado = max(self.verde_min, min(self.verde_max, demanda_tempo))
        return round(verde_calculado, 1)

    def atualizar(self, delta_t, taxa_chegada_por_segundo, veiculos_na_tela=0, taxa_vazao_por_segundo=0.45):
        novos_veiculos = taxa_chegada_por_segundo * delta_t
        self.fila_veiculos += novos_veiculos
        self.tempo_no_estado += delta_t

        if self.estado == "VERDE":
            vazao = min(self.fila_veiculos, taxa_vazao_por_segundo * delta_t)
            self.fila_veiculos -= vazao
            self.veiculos_atendidos += vazao

            acao = "MANTER"
            if self.motor_decisao:
                acao, _ = self.motor_decisao.decidir_proxima_fase(
                    self.estado, self.tempo_no_estado, self.fila_veiculos, veiculos_na_tela, self.tempo_verde_atual
                )

            if acao == "ENCERRAR_VERDE":
                self.estado = "AMARELO"
                self.tempo_no_estado = 0.0
            elif acao == "ESTENDER_VERDE":
                self.tempo_verde_atual = min(self.verde_max, round(self.tempo_verde_atual + (1.5 * delta_t), 1))
            elif self.tempo_no_estado >= self.tempo_verde_atual:
                self.estado = "AMARELO"
                self.tempo_no_estado = 0.0

        elif self.estado == "AMARELO":
            vazao = min(self.fila_veiculos, (taxa_vazao_por_segundo * 0.3) * delta_t)
            self.fila_veiculos -= vazao
            self.veiculos_atendidos += vazao

            if self.tempo_no_estado >= self.tempo_amarelo:
                self.estado = "VERMELHO"
                self.tempo_no_estado = 0.0
                self.tempo_vermelho_atual = self.vermelho_base

        elif self.estado == "VERMELHO":
            self.tempo_espera_acumulado += (self.fila_veiculos * delta_t)

            if self.tempo_no_estado >= self.tempo_vermelho_atual:
                self.estado = "VERDE"
                self.tempo_no_estado = 0.0
                self.tempo_verde_atual = self.calcular_tempo_verde_ideal(
                    max(self.fila_veiculos, veiculos_na_tela),
                    taxa_chegada_por_segundo
                )

        if self.veiculos_atendidos > 0:
            tempo_medio = self.tempo_espera_acumulado / self.veiculos_atendidos
            self.historico_espera.append(tempo_medio)

    def get_tempo_restante(self):
        if self.estado == "VERDE":
            return max(0.0, self.tempo_verde_atual - self.tempo_no_estado)
        elif self.estado == "AMARELO":
            return max(0.0, self.tempo_amarelo - self.tempo_no_estado)
        else:
            return max(0.0, self.tempo_vermelho_atual - self.tempo_no_estado)


class SimuladorTrafego:
    """Coordena e sincroniza os modelos semaforicos em tempo discreto."""

    def __init__(self):
        self.motor_decisao = MotorDecisaoTrafego()
        self.fixo = SemaforoFixo(tempo_verde=35, tempo_amarelo=4, tempo_vermelho=35)
        self.adaptativo = SemaforoAdaptativo(
            verde_min=12, verde_max=55, tempo_amarelo=4, vermelho_base=30, motor_decisao=self.motor_decisao
        )
        self.ultimo_tempo = time.time()

    def passo(self, qtd_cruzou_intervalo, veiculos_na_tela, intervalo_segundos=60):
        agora = time.time()
        delta_t = min(1.0, agora - self.ultimo_tempo) if self.ultimo_tempo else 0.1
        self.ultimo_tempo = agora

        taxa_chegada = max(0.05, qtd_cruzou_intervalo / max(1, intervalo_segundos))

        self.fixo.atualizar(delta_t, taxa_chegada)
        self.adaptativo.atualizar(delta_t, taxa_chegada, veiculos_na_tela)

        espera_fixo = (self.fixo.tempo_espera_acumulado / max(1, self.fixo.veiculos_atendidos))
        espera_adapt = (self.adaptativo.tempo_espera_acumulado / max(1, self.adaptativo.veiculos_atendidos))

        ganho_pct = 0.0
        if espera_fixo > 0:
            ganho_pct = max(0.0, ((espera_fixo - espera_adapt) / espera_fixo) * 100.0)

        segundos_economizados = max(0.0, espera_fixo - espera_adapt)

        return {
            "fixo": {
                "estado": self.fixo.estado,
                "tempo_restante": round(self.fixo.get_tempo_restante(), 1),
                "tempo_verde_config": self.fixo.tempo_verde,
                "fila_atual": round(self.fixo.fila_veiculos, 1),
                "tempo_medio_espera_s": round(espera_fixo, 1),
                "veiculos_atendidos": int(self.fixo.veiculos_atendidos)
            },
            "adaptativo": {
                "estado": self.adaptativo.estado,
                "tempo_restante": round(self.adaptativo.get_tempo_restante(), 1),
                "tempo_verde_atual": round(self.adaptativo.tempo_verde_atual, 1),
                "fila_atual": round(self.adaptativo.fila_veiculos, 1),
                "tempo_medio_espera_s": round(espera_adapt, 1),
                "veiculos_atendidos": int(self.adaptativo.veiculos_atendidos)
            },
            "comparativo": {
                "reducao_tempo_espera_pct": round(ganho_pct, 1),
                "segundos_economizados_por_veiculo": round(segundos_economizados, 1)
            },
            "motor_decisao": self.motor_decisao.obter_status()
        }


if __name__ == "__main__":
    print("Iniciando simulacao de teste...")
    simulador = SimuladorTrafego()

    cenarios = [
        ("Trafego Leve", 6, 2),
        ("Trafego Moderado", 14, 4),
        ("Pico / Intenso", 28, 8)
    ]

    for nome, fluxo, densidade in cenarios:
        print(f"\n--- Cenario: {nome} (Fluxo: {fluxo} veic/min, Densidade: {densidade} veic) ---")
        for segundo in range(30):
            res = simulador.passo(qtd_cruzou_intervalo=fluxo, veiculos_na_tela=densidade, intervalo_segundos=60)
            time.sleep(0.01)

        print(f"  Fixo       -> Estado: {res['fixo']['estado']} ({res['fixo']['tempo_restante']}s) | Fila: {res['fixo']['fila_atual']} | Espera: {res['fixo']['tempo_medio_espera_s']}s")
        print(f"  Adaptativo -> Estado: {res['adaptativo']['estado']} ({res['adaptativo']['tempo_restante']}s) | Verde: {res['adaptativo']['tempo_verde_atual']}s | Fila: {res['adaptativo']['fila_atual']} | Espera: {res['adaptativo']['tempo_medio_espera_s']}s")
        print(f"  Reducao do tempo de espera: {res['comparativo']['reducao_tempo_espera_pct']}% | Economia: {res['comparativo']['segundos_economizados_por_veiculo']}s")
