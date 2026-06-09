# Dockerfile — web-1-cookie-monster
# License: MIT.
#
# Minimal Python 3.12 image running the deliberately-vulnerable Flask app.
# The image takes no build-time secrets; the FLAG value is supplied via the
# environment at compose-up time (see ../docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir 'flask==3.0.3'

COPY app.py /app/app.py

# Drop to non-root.
RUN useradd --create-home --uid 10001 cookie
USER cookie

EXPOSE 8080

CMD ["python", "-u", "/app/app.py"]
