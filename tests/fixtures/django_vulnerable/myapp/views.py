import os
import pickle
import subprocess
import logging

from django.http import JsonResponse, HttpResponse
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)


def get_user(request, user_id):
    from django.db import connection
    # SEC-020: SQL injection via raw query
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    row = cursor.fetchone()

    # SEC-046: Logging sensitive data
    logging.info("User token: %s", request.headers.get('Authorization'))

    return JsonResponse({"user": row})


def search(request):
    query = request.GET.get("q", "")
    # SEC-022: eval usage
    result = eval(query)
    return JsonResponse({"result": result})


def render_profile(request):
    name = request.GET.get("name", "")
    # SEC-022: XSS via mark_safe
    html = mark_safe(f"<h1>Welcome, {name}!</h1>")
    return HttpResponse(html)


def export_data(request):
    data = request.body
    # SEC-022: Pickle deserialization of user input
    obj = pickle.loads(data)
    return JsonResponse({"exported": str(obj)})


def run_command(request):
    cmd = request.GET.get("cmd", "ls")
    # SEC-022: Command injection via os.system
    os.system(cmd)
    # SEC-022: Also via subprocess shell=True
    result = subprocess.run(cmd, shell=True, capture_output=True)
    return JsonResponse({"output": result.stdout.decode()})


def get_order(request, order_id):
    from myapp.models import Order
    order = Order.objects.get(id=order_id)
    return JsonResponse({"order": str(order)})


def delete_record(request, record_id):
    from myapp.models import Record
    Record.objects.get(pk=record_id).delete()
    return JsonResponse({"deleted": True})


def admin_login(request):
    # SEC-018: Default credentials
    username = "admin"
    password = "admin123"
    if request.POST.get("user") == username and request.POST.get("pass") == password:
        return JsonResponse({"status": "logged in"})
    return JsonResponse({"status": "denied"}, status=401)
