# DigitalOcean App Platform process types.
# Build Command (dashboard): pip install -r requirements.txt && python manage.py collectstatic --noinput
# Run Command (dashboard): gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 3
web: gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 3
release: python manage.py migrate --noinput
