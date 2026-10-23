web: python manage.py migrate --no-input && python manage.py collectstatic --no-input && gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000} --log-file -
