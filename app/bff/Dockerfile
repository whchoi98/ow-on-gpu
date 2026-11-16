FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY auth.py bff.py routing.py texts.py websearch.py test_bff.py ./

USER 1000
EXPOSE 8080
CMD ["python", "bff.py"]
