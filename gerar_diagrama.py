import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Configuração de alta definição (300 DPI) para impressão e visualização nítida
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

fig, ax = plt.subplots(figsize=(17, 9.5), dpi=300)
ax.set_facecolor('#F8FAFC')
fig.patch.set_facecolor('#F8FAFC')

# Título conciso e com fonte ampliada
plt.title("ARQUITETURA GERAL DO SISTEMA\nFluxo de Dados",
          fontsize=24, fontweight='bold', color='#0F172A', pad=30)

def draw_card(ax, x, y, w, h, title, subtitle, items, color_header, color_bg='#FFFFFF', color_border='#CBD5E1'):
    # Sombra sutil
    shadow = patches.FancyBboxPatch((x+0.004, y-0.007), w, h,
                                   boxstyle="round,pad=0.012,rounding_size=0.02",
                                   facecolor='#E2E8F0', edgecolor='none', zorder=1)
    ax.add_patch(shadow)
    
    # Caixa principal com borda sólida
    box = patches.FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.012,rounding_size=0.02",
                                facecolor=color_bg, edgecolor=color_border, linewidth=1.8, zorder=2)
    ax.add_patch(box)
    
    # Barra colorida superior
    header_bar = patches.FancyBboxPatch((x, y + h - 0.058), w, 0.058,
                                        boxstyle="round,pad=0.005,rounding_size=0.012",
                                        facecolor=color_header, edgecolor='none', zorder=3)
    ax.add_patch(header_bar)
    
    # Título do bloco
    ax.text(x + w/2, y + h - 0.029, title, fontsize=12.5, fontweight='bold', color='#FFFFFF',
            ha='center', va='center', zorder=4)
    
    # Subtítulo (Tecnologia/Módulo)
    ax.text(x + w/2, y + h - 0.092, subtitle, fontsize=11.5, fontweight='bold', color=color_header,
            ha='center', va='center', zorder=4)
    
    # Linhas de tópicos
    start_y = y + h - 0.145
    for i, item in enumerate(items):
        ax.text(x + 0.012, start_y - (i * 0.046), f"• {item}", fontsize=10.2, color='#1E293B',
                ha='left', va='center', zorder=4)

def draw_arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color="#2563EB", lw=2.5, mutation_scale=16),
                zorder=5)
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = y1 + 0.038
        ax.text(mid_x, mid_y, label, fontsize=9.2, fontweight='bold', color="#1E40AF",
                ha='center', va='bottom', bbox=dict(boxstyle="round,pad=0.2", fc="#EFF6FF", ec="#93C5FD", lw=1.1),
                zorder=6)

# =========================================================================
# LINHA 1: INGESTÃO E VISÃO COMPUTACIONAL (SUPERIOR: y = 0.51, h = 0.35)
# =========================================================================

# 1. Ingestão
draw_card(ax, 0.02, 0.51, 0.20, 0.35,
          "1. INGESTÃO DE VÍDEO", "YouTube Live Stream",
          ["Câmera pública urbana", "Balneário Camboriú (SC)", "Transmissão contínua HLS", "Ângulo oblíquo da pista"],
          color_header='#DC2626')

# 2. Resolvedor
draw_card(ax, 0.27, 0.51, 0.20, 0.35,
          "2. RESOLVEDOR HLS", "yt-dlp Library",
          ["Extração dinâmica de URL", "Manifesto HLS (.m3u8)", "Resolução: 960 x 540", "Zero arquivos no disco"],
          color_header='#D97706')

# 3. Captura Assíncrona
draw_card(ax, 0.52, 0.51, 0.21, 0.35,
          "3. CAPTURA ASSÍNCRONA", "Thread StreamReader (OpenCV)",
          ["Fila circular: deque(maxlen=600)", "Descarte de frames velhos", "Elimina o Latency Drift", "Amostragem: 10 FPS (leve)"],
          color_header='#0284C7')

# 4. Rede Neural & Rastreamento
draw_card(ax, 0.78, 0.51, 0.20, 0.35,
          "4. REDE NEURAL & MOT", "YOLOv8n + BYTETrack",
          ["YOLOv8 Nano (3,2M params)", "Classes: carro, moto, ônibus, cam.", "Detecções de baixa conf.", "Preserva IDs sob oclusão"],
          color_header='#4F46E5')

# Setas Linha Superior
draw_arrow(ax, 0.22, 0.68, 0.27, 0.68, "URL Live")
draw_arrow(ax, 0.47, 0.68, 0.52, 0.68, "Stream .m3u8")
draw_arrow(ax, 0.73, 0.68, 0.78, 0.68, "Frames 10 FPS")

# Seta de descida para a Linha 2
ax.annotate("", xy=(0.88, 0.42), xytext=(0.88, 0.51),
            arrowprops=dict(arrowstyle="-|>", color="#2563EB", lw=2.5, mutation_scale=16),
            zorder=5)
ax.text(0.88, 0.465, "Detecções e Frames", fontsize=9.2, fontweight='bold', color="#1E40AF",
        ha='center', va='center', bbox=dict(boxstyle="round,pad=0.2", fc="#EFF6FF", ec="#93C5FD", lw=1.1),
        zorder=6)

# =========================================================================
# LINHA 2: SENSORES, SIMULAÇÃO E INTERFACE (INFERIOR: y = 0.06, h = 0.35)
# =========================================================================

# 5. Sensores Virtuais
draw_card(ax, 0.75, 0.06, 0.23, 0.35,
          "5. SENSORES VIRTUAIS", "Linha Diagonal & Detector HSV",
          ["Tripwire: y = 320 - (40/960)x", "Contagem por centroide (Set)", "ROI Pedestre [47,166,70,218]", "Filtro 1,8s (4 Fases HSV)"],
          color_header='#7C3AED')

# 6. Decisão e Simulação
draw_card(ax, 0.50, 0.06, 0.21, 0.35,
          "6. DECISÃO & SIMULAÇÃO", "Motor Adaptativo & Filas",
          ["Green Extension (onda verde)", "Green Truncation (corte vazio)", "Simulador Fixo vs Adaptativo", "Cálculo: atraso, CO2 e comb."],
          color_header='#059669')

# 7. Barramento
draw_card(ax, 0.26, 0.06, 0.19, 0.35,
          "7. BARRAMENTO", "dados_trafego.json",
          ["Gravação atômica a cada 1s", "Comunicação assíncrona", "Status semáforo real e IA", "Logs persistentes em CSV/XLSX"],
          color_header='#0D9488')

# 8. Frontend Web
draw_card(ax, 0.02, 0.06, 0.19, 0.35,
          "8. SUPERVISÃO WEB", "Dashboard (HTML/CSS/JS)",
          ["Consumo assíncrono (JSON)", "Semáforo animado interativo", "Gráficos de fluxo (Chart.js)", "Telemetria de trânsito em tempo real"],
          color_header='#0369A1')

# Setas Linha Inferior (da direita para a esquerda)
draw_arrow(ax, 0.75, 0.235, 0.71, 0.235, "Fluxo/Fases")
draw_arrow(ax, 0.50, 0.235, 0.45, 0.235, "Decisões")
draw_arrow(ax, 0.26, 0.235, 0.21, 0.235, "Fetch (1s)")

ax.set_xlim(0, 1.0)
ax.set_ylim(0, 0.95)
ax.axis('off')

plt.tight_layout()
output_path = "diagrama_arquitetura.png"
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"[OK] Diagrama gerado com sucesso em: {output_path}")
