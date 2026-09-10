# DP-Guard — Full Prototype

**Typed Differential Privacy for Verified LLM-Orchestrated Security in Zero-Touch 6G Networks**

Полная рабочая версия архитектуры DP-Guard: реальная структурированная телеметрия UE-сессий, OpenAI LLM (с fallback на mock), typed policy, audit log и closed-loop orchestration.

## Архитектура (4 плоскости + вспомогательные модули)

| Модуль | Плоскость | Назначение |
|--------|-----------|------------|
| `network_telemetry.py` | Telemetry (источник) | Загрузка UE-сессий из JSON, агрегация KPI |
| `telemetry_plane.py` | Telemetry | Laplace mechanism, инкапсуляция raw data |
| `privacy_policy.py` | Privacy Policy | Typed access control, role-based authorization |
| `privacy_accountant.py` | Privacy Policy | Privacy filter, контроль epsilon-бюджета |
| `admissibility_verifier.py` | Verification | CI под Laplace-шум, блокировка действий |
| `orchestrator.py` | Orchestration | Closed-loop: intent -> LLM -> DP -> verify -> act |
| `openai_planner.py` | Orchestration | Реальный LLM через OpenAI API |
| `action_executor.py` | Actuator | Выполнение команд на симулированной сети |
| `audit_log.py` | Compliance | JSONL аудит всех эпох |

## Быстрый старт

```powershell
cd C:\Users\IVAN\Projects\DP_Guard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### С OpenAI (реальный LLM)

```powershell
copy .env.example .env
# Отредактируй .env: вставь OPENAI_API_KEY=sk-...
python main.py
```

Без API-ключа автоматически используется mock LLM (offline demo).

## Структура проекта

```
DP_Guard/
├── main.py
├── requirements.txt
├── .env.example
├── README.md
├── DEMO_GUIDE.txt
├── ALGORITHMS_AND_STATUS.txt
├── PROSTYM_YAZYKOM.txt
├── data/
│   ├── ue_sessions.json          # 12 UE-сессий (raw records)
│   └── network_slices.json         # Топология 6G slices
├── logs/
│   └── audit.jsonl                 # Аудит (создаётся при запуске)
├── tests/
│   └── test_dp_guard.py
└── dp_guard/
    ├── config.py
    ├── network_telemetry.py
    ├── telemetry_plane.py
    ├── privacy_policy.py
    ├── privacy_accountant.py
    ├── admissibility_verifier.py
    ├── orchestrator.py
    ├── openai_planner.py
    ├── mock_llm.py
    ├── llm_factory.py
    ├── action_executor.py
    └── audit_log.py
```

## Метрики телеметрии (6 typed metrics)

| Metric | Описание | Sensitivity |
|--------|----------|-------------|
| `threat_level` | Max threat score в slice | 1.0 |
| `active_connections` | Число UE-сессий | 1.0 |
| `anomaly_score` | % аномальных сессий | 5.0 |
| `failed_auth_attempts` | Сумма auth failures | 1.0 |
| `slice_load_percent` | Нагрузка slice | 2.0 |
| `packet_loss_rate` | Packet loss % | 0.5 |

## Демо-сценарий (3 эпохи)

1. **Эпоха 1** — LLM предлагает `allow_traffic` -> verifier **блокирует** (threat upper bound > 30)
2. **Эпоха 2** — расширенный DP-план -> снова **блокировка** allow_traffic
3. **Эпоха 3** — LLM предлагает `block_traffic` -> **выполняется** (restrictive action always admissible)

## Тесты

```powershell
pytest tests/ -v
```

## Документация

- `PROSTYM_YAZYKOM.txt` — объяснение простыми словами
- `DEMO_GUIDE.txt` — пошаговая инструкция для преподавателя
- `ALGORITHMS_AND_STATUS.txt` — алгоритмы и статус реализации

## Версия

v1.0.0 — full prototype (скелет расширен до полной версии)
