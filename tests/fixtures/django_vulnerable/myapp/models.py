from django.db import models


class User(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    api_key = "sk_live_hardcoded_key_in_model_file_12345"

    def get_orders(self, status):
        # SEC-020: SQL injection via .raw()
        return User.objects.raw(f"SELECT * FROM orders WHERE user_id = {self.id} AND status = '{status}'")

    def get_filtered(self, query):
        # SEC-020: SQL injection via .extra()
        return User.objects.extra(where=[f"username LIKE '%{query}%'"])
