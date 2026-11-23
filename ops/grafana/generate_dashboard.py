import json
from pathlib import Path

PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}
APP_JOBS = "lending-service|catalog-service|notification-service"

_id = 0
_panels: list[dict] = []


def _next() -> int:
    global _id
    _id += 1
    return _id


def target(expr, legend="", ref="A", instant=False, fmt="time_series"):
    return {
        "refId": ref,
        "expr": expr,
        "legendFormat": legend,
        "instant": instant,
        "range": not instant,
        "format": fmt,
        "datasource": PROM,
    }


def row(title, y):
    _panels.append(
        {"id": _next(), "type": "row", "title": title, "collapsed": False,
         "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}
    )


def timeseries(title, targets, x, y, w=8, h=8, unit="short", thresholds=None, stack=False, desc=""):
    defaults = {
        "unit": unit,
        "custom": {
            "lineWidth": 2, "fillOpacity": 25 if stack else 8, "showPoints": "never",
            "stacking": {"mode": "normal" if stack else "none"},
            "thresholdsStyle": {"mode": "line" if thresholds else "off"},
        },
        "color": {"mode": "palette-classic"},
    }
    if thresholds:
        defaults["thresholds"] = {
            "mode": "absolute",
            "steps": [{"color": "green", "value": None}, {"color": "red", "value": thresholds}],
        }
    _panels.append({
        "id": _next(), "type": "timeseries", "title": title, "description": desc,
        "datasource": PROM, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    })


def stat(title, targets, x, y, w=4, h=4, mappings=None, unit="short", thresholds=None, desc=""):
    steps = thresholds or [{"color": "green", "value": None}]
    _panels.append({
        "id": _next(), "type": "stat", "title": title, "description": desc,
        "datasource": PROM, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": targets,
        "fieldConfig": {"defaults": {
            "unit": unit, "mappings": mappings or [],
            "thresholds": {"mode": "absolute", "steps": steps},
            "color": {"mode": "thresholds"}}, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": "background", "graphMode": "none", "textMode": "value_and_name",
                    "orientation": "auto"},
    })


def pie(title, targets, x, y, w=8, h=8, desc=""):
    _panels.append({
        "id": _next(), "type": "piechart", "title": title, "description": desc,
        "datasource": PROM, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": targets,
        "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
        "options": {"pieType": "donut", "displayLabels": ["name"],
                    "legend": {"displayMode": "table", "placement": "right", "showLegend": True,
                               "values": ["value", "percent"]},
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "tooltip": {"mode": "single"}},
    })


def table(title, targets, x, y, w=8, h=8):
    _panels.append({
        "id": _next(), "type": "table", "title": title, "datasource": PROM,
        "gridPos": {"h": h, "w": w, "x": x, "y": y}, "targets": targets,
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {"showHeader": True},
        "transformations": [{"id": "organize", "options": {
            "excludeByName": {"Time": True, "Value": True, "__name__": True, "alertstate": True}}}],
    })


def logs(title, expr, x, y, w=24, h=10):
    _panels.append({
        "id": _next(), "type": "logs", "title": title, "datasource": LOKI,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": [{"refId": "A", "expr": expr, "queryType": "range", "datasource": LOKI}],
        "options": {"showTime": True, "wrapLogMessage": True, "enableLogDetails": True,
                    "sortOrder": "Descending", "dedupStrategy": "none", "prettifyLogMessage": True},
    })


UP_DOWN = [{"type": "value", "options": {
    "0": {"text": "DOWN", "color": "red", "index": 0},
    "1": {"text": "UP", "color": "green", "index": 1}}}]
UP_STEPS = [{"color": "red", "value": None}, {"color": "green", "value": 1}]

y = 0
row("Cluster health — стан вузлів", y); y += 1
stat("Стан вузлів (up)", [target('up{job!="prometheus"}', "{{job}}")], 0, y, w=12, h=5,
     mappings=UP_DOWN, thresholds=UP_STEPS,
     desc="1 = Prometheus успішно зняв метрики; 0 = вузол недоступний (alert NodeDown)")
stat("Споживачі черги loan_notifications",
     [target('rabbitmq_detailed_queue_consumers{queue="loan_notifications"}', "consumers")],
     12, y, w=4, h=5, thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}])
stat("Firing-алертів", [target('count(ALERTS{alertstate="firing"}) or vector(0)', "alerts")],
     16, y, w=4, h=5, thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}])
stat("Підключень до БД (всього)",
     [target('sum(pg_stat_database_numbackends{datname=~"catalog_db|lending_db|notification_db"})', "db conns")],
     20, y, w=4, h=5)
y += 5
table("Активні алерти", [target('ALERTS{alertstate="firing"}', "", instant=True, fmt="table")], 0, y, w=24, h=5)
y += 5

row("Метрики сервісів — latency p50/p95/p99, throughput, error rate", y); y += 1
svc = '{service=~"$service"}'
timeseries("Latency p50 / p95 / p99", [
    target(f"service:http_request_duration_seconds:p50{svc}", "{{service}} ({{role}}) p50", "A"),
    target(f"service:http_request_duration_seconds:p95{svc}", "{{service}} ({{role}}) p95", "B"),
    target(f"service:http_request_duration_seconds:p99{svc}", "{{service}} ({{role}}) p99", "C"),
], 0, y, w=12, unit="s", thresholds=1,
    desc="Червона лінія — поріг алерту HighLatencyP99 (p99 > 1 с)")
timeseries("Throughput (запитів/с)", [
    target(f"service:http_requests:rate1m{svc}", "{{service}} ({{role}})")], 12, y, w=6, unit="reqps")
timeseries("Error rate (частка 5xx)", [
    target(f"service:http_errors:ratio_rate1m{svc}", "{{service}} ({{role}})")], 18, y, w=6,
    unit="percentunit", thresholds=0.05, desc="Поріг алерту HighErrorRate — 5%")
y += 8

row("Notification-service — обробка повідомлень", y); y += 1
timeseries("Notification processing latency p50/p95/p99", [
    target('service:notification_processing_seconds:p50{service="notification-service"}', 'p50', 'A'),
    target('service:notification_processing_seconds:p95{service="notification-service"}', 'p95', 'B'),
    target('service:notification_processing_seconds:p99{service="notification-service"}', 'p99', 'C'),
], 0, y, w=12, unit="s")
timeseries("Notification throughput", [
    target('service:notification_events:rate5m{service="notification-service"}', 'events/s')
], 12, y, w=6, unit="ops")
timeseries("Notification error ratio", [
    target('service:notification_errors:ratio_rate5m{service="notification-service"}', 'errors')
], 18, y, w=6, unit="percentunit")
y += 8

row("Replication lag — відставання доставки подій (Outbox → RabbitMQ → SAGA)", y); y += 1
timeseries("Outbox lag: вік найстарішого NEW-повідомлення", [
    target("outbox_oldest_new_age_seconds", "outbox lag")], 0, y, w=8, unit="s", thresholds=15,
    desc="Аналог replication lag. Поріг алерту OutboxReplicationLagHigh — 15 с")
timeseries("Outbox за статусами", [target("outbox_messages", "{{status}}")], 8, y, w=8, stack=True)
timeseries("Глибина черг RabbitMQ", [
    target('rabbitmq_detailed_queue_messages_ready{queue=~"loan.*"}', "{{queue}}")], 16, y, w=8)
y += 8
timeseries("SAGA: вік найстарішої PENDING-позики", [
    target("saga_pending_oldest_age_seconds", "pending age")], 0, y, w=8, unit="s", thresholds=20)
timeseries("SAGA: компенсації за хвилину", [
    target("sum by (reason) (increase(saga_compensations_total[1m]))", "{{reason}}")], 8, y, w=8)
timeseries("SAGA end-to-end p95 (створення → ACTIVE)", [
    target("histogram_quantile(0.95, sum by (le) (rate(saga_confirmation_seconds_bucket[1m])))", "p95")],
    16, y, w=8, unit="s")
y += 8

row("Shard distribution — розподіл навантаження й даних між сервісами/БД", y); y += 1
pie("Частка запитів за сервісами (за період)", [
    target('sum by (service) (increase(http_requests_total[$__range]))', "{{service}}", instant=True)],
    0, y, w=6)
pie("Запити за ендпоінтами (за період)", [
    target('topk(8, sum by (service, path) (increase(http_requests_total[$__range])))',
           "{{service}} {{path}}", instant=True)], 6, y, w=6)
pie("Позики за статусами", [target("loans_by_status", "{{status}}", instant=True)], 12, y, w=6)
pie("З'єднання за базами (шард = БД сервісу)", [
    target('pg_stat_database_numbackends{datname=~"catalog_db|lending_db|notification_db"}',
           "{{datname}}", instant=True)], 18, y, w=6)
y += 8

row("Бізнес-метрики та ресурси", y); y += 1
timeseries("Бізнес: позики за хвилину", [
    target("rate(loans_created_total[1m]) * 60", "створено"),
    target("rate(loans_returned_total[1m]) * 60", "повернено", "B"),
    target("rate(saga_confirmed_total[1m]) * 60", "підтверджено SAGA", "C")], 0, y, w=8)
timeseries("notification-service: події за результатом", [
    target("sum by (result) (rate(notification_events_total[1m]))", "{{result}}")], 8, y, w=8, unit="ops")
timeseries("CPU (ядер) / пам'ять сервісів", [
    target(f'rate(process_cpu_seconds_total{{job=~"{APP_JOBS}"}}[1m])', "CPU {{job}}"),
    target(f'process_resident_memory_bytes{{job=~"{APP_JOBS}"}} / 1e9', "RSS ГБ {{job}}", "B")],
    16, y, w=8)
y += 8

row("Централізовані логи (Loki) — клік по trace_id відкриває трасу в Jaeger", y); y += 1
logs("Помилки та попередження (JSON-логи)",
     '{compose_service=~"lending-service|catalog-service|notification-service"} | json | level=~"ERROR|WARNING"', 0, y)
y += 10
logs("Усі логи за trace_id (змінна $trace_id)",
     '{compose_service=~"lending-service|catalog-service|notification-service"} | json | trace_id=~"$trace_id"',
     0, y, h=8)

dashboard = {
    "uid": "soa-observability",
    "title": "SOA Library — Observability",
    "tags": ["soa", "lr6", "observability"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "5s",
    "time": {"from": "now-15m", "to": "now"},
    "panels": _panels,
    "links": [
        {"title": "Jaeger", "type": "link", "url": "http://localhost:16686", "targetBlank": True, "icon": "external link"},
        {"title": "Jira", "type": "link", "url": "https://home.atlassian.com", "targetBlank": True, "icon": "external link"},
        {"title": "n8n", "type": "link", "url": "http://localhost:5678", "targetBlank": True, "icon": "external link"},
    ],
    "templating": {"list": [
        {"name": "service", "type": "query", "datasource": PROM, "label": "Сервіс",
         "query": {"query": "label_values(http_requests_total, service)", "refId": "svc"},
         "refresh": 2, "includeAll": True, "multi": True, "allValue": ".*",
         "current": {"selected": True, "text": "All", "value": "$__all"}},
        {"name": "trace_id", "type": "textbox", "label": "trace_id", "query": ".+",
         "current": {"text": ".+", "value": ".+"}},
    ]},
    "annotations": {"list": [{
        "name": "Алерти", "enable": True, "iconColor": "red", "datasource": PROM,
        "expr": 'ALERTS{alertstate="firing"}', "titleFormat": "{{alertname}}", "textFormat": "{{summary}}",
        "step": "15s"}]},
}

out = Path(__file__).parent / "dashboards" / "soa-observability.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{out}: {len(_panels)} елементів")
