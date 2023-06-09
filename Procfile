web: gunicorn --bind 127.0.0.1:8000 --workers=1 --threads=48 wsgi:application
worker_periodic_tasks: AWS_XRAY_SDK_ENABLED=false celery -A bemoSenderr worker -l INFO -E  --heartbeat-interval 60 --concurrency 1 --pool threads -n worker_periodic_tasks -Q periodic_tasks
worker_send_money: AWS_XRAY_SDK_ENABLED=false celery -A bemoSenderr worker -l INFO -E  --heartbeat-interval 60 --concurrency 1 --pool threads -n worker_send_money -Q send_money
worker_invoices: AWS_XRAY_SDK_ENABLED=false celery -A bemoSenderr worker -l INFO -E  --heartbeat-interval 60 --concurrency 1 --pool threads -n worker_invoices -Q invoices
worker_verification: AWS_XRAY_SDK_ENABLED=false celery -A bemoSenderr worker -l INFO -E  --heartbeat-interval 60 --concurrency 1 --pool threads -n worker_verification -Q verification
beat: AWS_XRAY_SDK_ENABLED=false celery -A bemoSenderr beat -l INFO -S redbeat.RedBeatScheduler --max-interval 30