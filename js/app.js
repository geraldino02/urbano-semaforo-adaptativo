// Simulação Simples de Banco de Dados local
const db = {
    carCount: 1420,
    riskCount: 12,
    trafficLevel: 'Médio',
    alerts: [
        { id: 1, type: 'danger', title: 'Risco de Colisão', desc: 'Veículos muito próximos na Av. Principal', time: 'Agora', icon: 'ph-warning' },
        { id: 2, type: 'warning', title: 'Parada Brusca', desc: 'Frenagem detectada no cruzamento 4', time: '2 min atrás', icon: 'ph-car-profile' },
        { id: 3, type: 'info', title: 'Fluxo Intenso', desc: 'Aumento de 15% no volume na última hora', time: '15 min atrás', icon: 'ph-trend-up' }
    ],
    settings: {
        minDistance: 2.5,
        baseTime: 45
    }
};

// Inicialização do Sistema Urbano (TCC)
document.addEventListener('DOMContentLoaded', () => {
    // Mobile Toggle
    const mobileToggle = document.querySelector('.mobile-toggle');
    const sidebar = document.querySelector('.sidebar');
    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    // Pages initialization
    initDashboard();
});

// Dashboard Init
let trafficChart = null;
let lastJsonUpdate = '';

function initDashboard() {
    // Init Chart first (empty, will be filled by polling)
    const ctx = document.getElementById('trafficChart');
    if (ctx) {
        trafficChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Média por Intervalo',
                    data: [],
                    fill: true,
                    backgroundColor: 'rgba(0, 210, 255, 0.1)',
                    borderColor: 'rgba(0, 210, 255, 1)',
                    tension: 0.4,
                    borderWidth: 2,
                    pointBackgroundColor: '#0f111a',
                    pointBorderColor: '#00d2ff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                },
                {
                    label: 'Pico no Intervalo',
                    data: [],
                    fill: false,
                    borderColor: 'rgba(245, 158, 11, 0.7)',
                    backgroundColor: 'rgba(245, 158, 11, 0.2)',
                    tension: 0.3,
                    borderWidth: 1,
                    borderDash: [3, 3],
                    pointBackgroundColor: '#0f111a',
                    pointBorderColor: '#f59e0b',
                    pointBorderWidth: 2,
                    pointRadius: 3
                },
                {
                    label: 'Total Acumulado',
                    data: [],
                    fill: false,
                    borderColor: 'rgba(142, 45, 226, 0.8)',
                    tension: 0.4,
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointBackgroundColor: '#0f111a',
                    pointBorderColor: '#8e2de2',
                    pointBorderWidth: 2,
                    pointRadius: 3,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: '#94a3b8', font: { size: 11 } }
                    }
                },
                scales: {
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' },
                        title: { display: true, text: 'No Intervalo', color: '#94a3b8' }
                    },
                    y1: {
                        position: 'right',
                        grid: { display: false },
                        ticks: { color: '#8e2de2' },
                        title: { display: true, text: 'Acumulado', color: '#8e2de2' }
                    },
                    x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    // First load with mock data (in case run.py hasn't started)
    updateDashboardUI(null);

    // Start polling dados_trafego.json every 2 seconds
    fetchTrafficData();
    setInterval(fetchTrafficData, 2000);


}

async function fetchTrafficData() {
    try {
        const res = await fetch('dados_trafego.json?_t=' + Date.now());
        if (!res.ok) throw new Error('JSON não encontrado');
        const data = await res.json();

        // Only update if data changed
        const updateKey = data.ultima_atualizacao + '_' + data.total_veiculos;
        if (updateKey !== lastJsonUpdate) {
            lastJsonUpdate = updateKey;
            updateDashboardUI(data);
        }
    } catch (e) {
        // JSON not available yet — keep mock data or last known state
    }
}

function updateDashboardUI(data) {
    const intervalCountEl = document.getElementById('interval-count');
    const densityCountEl = document.getElementById('density-count');
    const trafficLevelEl = document.getElementById('traffic-level');
    const gainPctEl = document.getElementById('gain-pct');
    const alertsContainer = document.querySelector('.alerts-list');
    const statusIndicator = document.getElementById('data-source-status');

    if (!data) {
        if (intervalCountEl) intervalCountEl.textContent = '0 veíc';
        if (densityCountEl) densityCountEl.textContent = '0.0 veíc';
        if (trafficLevelEl) trafficLevelEl.textContent = 'Aguardando...';
        if (gainPctEl) gainPctEl.textContent = '0.0%';
        if (statusIndicator) {
            statusIndicator.textContent = '⏳ Aguardando IA iniciar...';
            statusIndicator.style.color = 'var(--warning)';
        }
        return;
    }

    // === LIVE DATA FROM run_live.py ===

    // 1. Fluxo do Ciclo Atual
    if (intervalCountEl) {
        intervalCountEl.textContent = `${data.intervalo_atual ?? 0} veíc`;
    }

    // 2. Densidade Média na Tela
    if (densityCountEl) {
        const dens = data.densidade_media ?? (data.semaforo?.adaptativo?.fila_atual ?? data.veiculos_na_tela ?? 0);
        densityCountEl.textContent = `${typeof dens === 'number' ? dens.toFixed(1) : dens} veíc`;
    }

    // 3. Classificação do Nível de Tráfego
    if (trafficLevelEl) {
        trafficLevelEl.textContent = data.fluxo || 'BAIXO';
        const levelColors = {
            'BAIXO': 'var(--success)',
            'MÉDIO': 'var(--warning)',
            'ALTO': 'var(--danger)',
            'CONGESTIONADO': '#dc2626'
        };
        trafficLevelEl.style.color = levelColors[data.fluxo] || 'var(--text-main)';
    }

    // 4. Ganho de Eficiência IA
    if (gainPctEl && data.semaforo?.comparativo?.reducao_tempo_espera_pct !== undefined) {
        gainPctEl.textContent = `+${data.semaforo.comparativo.reducao_tempo_espera_pct}%`;
    }

    // Update traffic lights simulation UI
    if (data.semaforo || data.semaforo_real) {
        updateTrafficLightsUI(data.semaforo, data.semaforo_real);
    }

    // Update chart with historico data
    if (trafficChart && data.historico && data.historico.length > 0) {
        trafficChart.data.labels = data.historico.map(h => h.timestamp);
        trafficChart.data.datasets[0].data = data.historico.map(h => h.veiculos);
        trafficChart.data.datasets[1].data = data.historico.map(h => h.pico || h.veiculos);
        trafficChart.data.datasets[2].data = data.historico.map(h => h.total_acumulado);
        trafficChart.update('none');
    }



    // Generate alerts from real data
    if (alertsContainer) {
        const alerts = [];

        // Motor de Decisão Autônomo (TCC)
        if (data.motor_decisao && data.motor_decisao.justificativa_decisao) {
            alerts.push({
                type: 'info', icon: 'ph-brain',
                title: `Decisão IA: ${data.motor_decisao.acao_atual || 'AUTÔNOMO'}`,
                desc: data.motor_decisao.justificativa_decisao,
                time: data.ultima_atualizacao ? data.ultima_atualizacao.split(' ')[1] : ''
            });
        }

        // Stream info
        if (data.fonte) {
            alerts.push({
                type: 'info', icon: 'ph-broadcast',
                title: `${data.fonte}`,
                desc: `${data.fps_processamento || 0} FPS · ${data.snapshots_no_intervalo || 0} snapshots no intervalo`,
                time: data.ultima_atualizacao ? data.ultima_atualizacao.split(' ')[1] : ''
            });
        }

        if (data.fluxo === 'ALTO' || data.fluxo === 'CONGESTIONADO') {
            alerts.push({
                type: 'danger', icon: 'ph-warning',
                title: data.fluxo === 'CONGESTIONADO' ? 'Trânsito Congestionado' : 'Fluxo ALTO detectado',
                desc: data.fluxo === 'CONGESTIONADO' ? `Média de veículos parados: ${data.intervalo_atual}` : `Média: ${data.intervalo_atual} veículos${data.pico_intervalo ? ' · Pico: ' + data.pico_intervalo : ''}`,
                time: data.ultima_atualizacao ? data.ultima_atualizacao.split(' ')[1] : 'Agora'
            });
        }

        if (data.total_veiculos > 50) {
            alerts.push({
                type: 'warning', icon: 'ph-car-profile',
                title: 'Volume elevado',
                desc: `Total acumulado: ${data.total_veiculos} veículos detectados`,
                time: data.ultima_atualizacao.split(' ')[1] || ''
            });
        }

        // Show last historico entries as info alerts
        const lastEntries = (data.historico || []).slice(-3).reverse();
        lastEntries.forEach(h => {
            alerts.push({
                type: (h.fluxo === 'ALTO' || h.fluxo === 'CONGESTIONADO') ? 'danger' : h.fluxo === 'MÉDIO' ? 'warning' : 'info',
                icon: 'ph-trend-up',
                title: `Intervalo ${h.timestamp}`,
                desc: `${h.veiculos} veículos · Fluxo ${h.fluxo}`,
                time: h.timestamp
            });
        });

        if (alerts.length === 0) {
            alerts.push({
                type: 'info', icon: 'ph-check-circle',
                title: 'Tudo normal',
                desc: 'Nenhum alerta no momento',
                time: 'Agora'
            });
        }

        alertsContainer.innerHTML = alerts.slice(0, 6).map(alert => `
            <div class="alert-item ${alert.type}">
                <div class="icon"><i class="${alert.icon}"></i></div>
                <div class="alert-content">
                    <h4>${alert.title}</h4>
                    <p>${alert.desc}</p>
                </div>
                <span class="alert-time">${alert.time}</span>
            </div>
        `).join('');
    }

    // Update status indicator
    if (statusIndicator) {
        const streamStatus = data.stream_status || 'local';
        const fonte = data.fonte || 'Arquivo local';
        const fps = data.fps_processamento || 0;

        if (streamStatus === 'ao_vivo') {
            statusIndicator.innerHTML = `<i class="ph-fill ph-broadcast" style="color:var(--success)"></i> <strong>AO VIVO</strong> · ${fps} FPS · ${data.ultima_atualizacao.split(' ')[1] || ''}`;
            statusIndicator.style.color = 'var(--success)';
        } else if (streamStatus === 'reconectando') {
            statusIndicator.innerHTML = `<i class="ph-fill ph-spinner" style="color:var(--warning); animation: spin 1s linear infinite"></i> Reconectando...`;
            statusIndicator.style.color = 'var(--warning)';
        } else if (streamStatus === 'offline') {
            statusIndicator.innerHTML = `<i class="ph-fill ph-wifi-slash" style="color:var(--danger)"></i> Offline · Último: ${data.ultima_atualizacao}`;
            statusIndicator.style.color = 'var(--danger)';
        } else {
            statusIndicator.innerHTML = `<i class="ph-fill ph-pulse" style="color:var(--success)"></i> Ao vivo · ${data.ultima_atualizacao}`;
            statusIndicator.style.color = 'var(--success)';
        }
    }
}

function animateNumber(el, from, to, duration) {
    const start = performance.now();
    const step = (timestamp) => {
        const progress = Math.min((timestamp - start) / duration, 1);
        const current = Math.floor(from + (to - from) * progress);
        el.textContent = current.toLocaleString();
        if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}


let monitorLastJsonUpdate = '';

// Settings Init
function initSettings() {
    const minInput = document.getElementById('min-dist');
    const timeInput = document.getElementById('base-time');

    if(minInput) minInput.value = localStorage.getItem('urbano_minDist') || db.settings.minDistance;
    if(timeInput) timeInput.value = localStorage.getItem('urbano_baseTime') || db.settings.baseTime;
}

function saveSettings(e) {
    e.preventDefault();
    const minInput = document.getElementById('min-dist').value;
    const timeInput = document.getElementById('base-time').value;

    localStorage.setItem('urbano_minDist', minInput);
    localStorage.setItem('urbano_baseTime', timeInput);

    alert('Configurações salvas com sucesso!');
}

// ==========================================
// RENDERIZADOR DO SEMÁFORO INTELIGENTE (TCC)
// ==========================================
function updateTrafficLightsUI(simData, realData) {
    if (!simData && !realData) return;

    const fixo = simData ? simData.fixo : null;
    const ai = simData ? simData.adaptativo : null;
    const comp = simData ? simData.comparativo : null;

    // 1. Atualiza Semáforo Real Detectado na Câmera
    if (realData) {
        setBulbState('light-real-red', realData.cor_atual === 'VERMELHO');
        setBulbState('light-real-yellow', realData.cor_atual === 'AMARELO');
        setBulbState('light-real-green', realData.cor_atual === 'VERDE');

        const timerRealEl = document.getElementById('timer-real');
        const stateRealEl = document.getElementById('state-real');
        const greenRealEl = document.getElementById('green-real');
        const redRealEl = document.getElementById('red-real');
        const cycleRealEl = document.getElementById('cycle-real');

        if (timerRealEl) timerRealEl.textContent = `${realData.tempo_na_fase_s || 0.0}s`;
        if (stateRealEl) {
            const cor = realData.cor_atual || 'DESCONHECIDO';
            const fasePed = realData.fase_pedestre;
            if (fasePed && fasePed !== 'DESCONHECIDO') {
                const labelPed = fasePed.replace('_', ' ');
                stateRealEl.textContent = `PEDESTRE: ${labelPed} ➔ VIA: ${cor}`;
            } else {
                stateRealEl.textContent = cor === 'DESCONHECIDO' ? 'ANALISANDO CÂMERA...' : `SINAL VIA: ${cor}`;
            }
            stateRealEl.style.color = cor === 'VERDE' ? 'var(--success)' : cor === 'AMARELO' ? 'var(--warning)' : cor === 'VERMELHO' ? 'var(--danger)' : 'var(--text-muted)';
        }
        if (greenRealEl) greenRealEl.textContent = `${realData.ultimo_verde_real_s || 0.0}s`;
        if (redRealEl) redRealEl.textContent = `${realData.ultimo_vermelho_real_s || 0.0}s`;
        if (cycleRealEl) cycleRealEl.textContent = `${realData.ciclo_total_real_s || 0.0}s`;
    }

    // Atualiza Comparativo de Eficiência
    if (comp) {
        const topGainEl = document.getElementById('gain-pct');
        const gainEl = document.getElementById('sim-gain-badge');

        if (topGainEl) topGainEl.textContent = `+${comp.reducao_tempo_espera_pct}%`;
        if (gainEl) gainEl.textContent = `+${comp.reducao_tempo_espera_pct}% Eficiência IA`;
    }

    // Atualiza Semáforo Tradicional (Fixo)
    if (fixo) {
        setBulbState('light-fixo-red', fixo.estado === 'VERMELHO');
        setBulbState('light-fixo-yellow', fixo.estado === 'AMARELO');
        setBulbState('light-fixo-green', fixo.estado === 'VERDE');

        const timerEl = document.getElementById('timer-fixo');
        const stateEl = document.getElementById('state-fixo');
        const waitEl = document.getElementById('wait-fixo');
        const queueEl = document.getElementById('queue-fixo');
        const servedEl = document.getElementById('served-fixo');

        if (timerEl) timerEl.textContent = `${fixo.tempo_restante}s`;
        if (stateEl) {
            stateEl.textContent = `FASE ${fixo.estado} (${fixo.tempo_verde_config}s fixos)`;
            stateEl.style.color = fixo.estado === 'VERDE' ? 'var(--success)' : fixo.estado === 'AMARELO' ? 'var(--warning)' : fixo.estado === 'VERMELHO' ? 'var(--danger)' : 'var(--text-muted)';
        }
        if (waitEl) waitEl.textContent = `${fixo.tempo_medio_espera_s}s`;
        if (queueEl) queueEl.textContent = `${fixo.fila_atual} veículos`;
        if (servedEl) servedEl.textContent = `${fixo.veiculos_atendidos}`;
    }

    // Atualiza Semáforo Inteligente (IA Urbano)
    if (ai) {
        setBulbState('light-ai-red', ai.estado === 'VERMELHO');
        setBulbState('light-ai-yellow', ai.estado === 'AMARELO');
        setBulbState('light-ai-green', ai.estado === 'VERDE');

        const timerEl = document.getElementById('timer-ai');
        const stateEl = document.getElementById('state-ai');
        const waitEl = document.getElementById('wait-ai');
        const queueEl = document.getElementById('queue-ai');
        const greenCalcEl = document.getElementById('green-calc-ai');

        if (timerEl) timerEl.textContent = `${ai.tempo_restante}s`;
        if (stateEl) {
            stateEl.textContent = `FASE ${ai.estado} (Demanda Dinâmica)`;
            stateEl.style.color = ai.estado === 'VERDE' ? 'var(--primary)' : ai.estado === 'AMARELO' ? 'var(--warning)' : ai.estado === 'VERMELHO' ? 'var(--danger)' : 'var(--text-muted)';
        }
        if (waitEl) waitEl.textContent = `${ai.tempo_medio_espera_s}s`;
        if (queueEl) queueEl.textContent = `${ai.fila_atual} veículos`;
        if (greenCalcEl) greenCalcEl.textContent = `${ai.tempo_verde_atual}s`;
    }
}

function setBulbState(id, isActive) {
    const el = document.getElementById(id);
    if (!el) return;
    if (isActive) {
        el.classList.add('active');
    } else {
        el.classList.remove('active');
    }
}

function animateNumber(el, from, to, duration) {
    const start = performance.now();
    const step = (timestamp) => {
        const progress = Math.min((timestamp - start) / duration, 1);
        const current = Math.floor(from + (to - from) * progress);
        el.textContent = current.toLocaleString();
        if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}
