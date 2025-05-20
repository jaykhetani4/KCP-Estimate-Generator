from django.db import models
from django.contrib.auth.models import User

class PaverBlockType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Estimate(models.Model):
    party_name = models.CharField(max_length=200)
    date = models.DateField()
    paver_block_type = models.ForeignKey(PaverBlockType, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transportation_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loading_unloading_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, help_text="Additional notes or terms and conditions")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"KCP-ESTIMATE-{self.party_name}"

    def save(self, *args, **kwargs):
        # Calculate GST amount
        self.gst_amount = (self.price * self.gst_percentage) / 100
        # Calculate total amount
        self.total_amount = self.price + self.gst_amount + self.transportation_charge + self.loading_unloading_cost
        super().save(*args, **kwargs)
