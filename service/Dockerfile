FROM python:3.12-slim
WORKDIR /app
COPY rising_service.py rising_room.py rising_tournament.py ./
USER 65534:65534
EXPOSE 7010
ENTRYPOINT ["python", "-u", "rising_service.py", "--bind", "0.0.0.0", "--port", "7010"]
