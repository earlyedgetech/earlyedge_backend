from common.models import TimeStampedModel
from django.db import models


class Refund(TimeStampedModel):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )

    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    processed_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds'
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f'Refund #{self.pk} - {self.purchase} ({self.status})'
