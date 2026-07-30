# DP-Guard Prototype (Skeleton)

**Typed Differential Privacy for Verified LLM-Orchestrated Security in Zero-Touch 6G Networks**

Минимальный рабочий скелет архитектуры DP-Guard на Python 3.10+.  
LLM не имеет доступа к сырой телеметрии — только к DP-агрегатам с учётом privacy budget.

## Архитектура (4 плоскости)

| Модуль | Плоскость | Назначение |
|--------|-----------|------------|
| `telemetry_plane.py` | Telemetry | Единственный доступ к raw data; Laplace mechanism |
| `privacy_accountant.py` | Privacy Policy | Privacy filter; контроль ε-бюджета |
| `admissibility_verifier.py` | Verification | Проверка безопасности действий при DP-шуме |
| `orchestrator.py` | Orchestration | Closed-loop: intent → LLM plan → DP reads → verify → act |

## Быстрый старт

```powershell
cd C:\Users\IVAN\Projects\DP_Guard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Структура проекта

```
DP_Guard/
├── main.py                          # Демо: 3 эпохи orchestration
├── requirements.txt
├── README.md
├── DEMO_GUIDE.txt                   # Пошаговая инструкция для преподавателя
├── ALGORITHMS_AND_STATUS.txt        # Алгоритмы и статус реализации
└── dp_guard/
    ├── __init__.py
    ├── exceptions.py
    ├── types.py
    ├── telemetry_plane.py
    ├── privacy_accountant.py
    ├── admissibility_verifier.py
    ├── mock_llm.py
    └── orchestrator.py
```

## Что демонстрирует main.py

1. **Эпоха 1** — DP-чтения threat_level и active_connections; LLM предлагает `allow_traffic`.
2. **Эпоха 2** — расширенный план; admissibility verifier блокирует `allow_traffic`, т.к. истинный threat=45 > порог 30 (верхняя граница CI превышает порог).
3. **Эпоха 3** — исчерпание privacy budget (ε_tot=1.2).

## Ограничения текущего скелета

- Mock LLM вместо OpenAI API
- Pure ε-DP (без δ), простое суммирование бюджета
- Нет typed policy language (DPolicy/LightDP)
- Нет Gaussian mechanism, Rényi DP, DTMC verification
- Нет персистентного логирования и REST API

## Ссылки

Основано на статье: *DP-Guard: Typed Differential Privacy for Verified LLM-Orchestrated Security in Zero-Touch 6G Networks*.
