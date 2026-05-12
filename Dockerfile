FROM python:3.12-slim
WORKDIR /app
COPY render_bot.py requirements.txt ./
RUN pip install -r requirements.txt
CMD python render_bot.py
