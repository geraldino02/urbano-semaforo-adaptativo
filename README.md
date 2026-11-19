# URBANO — Controle Semafórico Adaptativo com Visão Computacional

Sistema inteligente desenvolvido para o Trabalho de Conclusão de Curso (TCC), focado no monitoramento de tráfego urbano em tempo real e na simulação de semáforos adaptativos a partir de transmissões públicas de vídeo (conceito de *retrofitting*).

### Destaques do Projeto:
- **Detecção e Rastreamento:** YOLOv8n + BYTETrack a 10 FPS com 94,4% de acurácia.
- **Semáforo Adaptativo:** Regras de extensão (*Green Extension*) e corte de verde (*Green Truncation*) para diminuir o tempo ocioso em ruas vazias.
- **Economia Comprovada:** Redução média de 9,83% no tempo de espera dos veículos (e até 11,48% em momentos de pico).
- **Sem Obras no Asfalto:** Processa imagens de câmeras já existentes no município de Balneário Camboriú (SC).
- **Dashboard Web:** Painel em tempo real com telemetria, simulação comparativa e exportação de relatórios em Excel/CSV.