"""Auto-issuance triggers. A certificate is created automatically when:

  - a Purchase's enrollment_status flips to 'completed' (self-paced online
    course or internship — course_type distinguishes them);
  - a live-class Batch (a "face-to-face" course run) is marked 'completed',
    which certifies every student registered in it;
  - a single BatchRegistration is marked 'completed' individually (e.g. an
    instructor certifying one student without closing the whole batch).

All three funnel through certificates.services.issue_certificate, which is
idempotent per (student, course) — see the unique constraint on Certificate.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from live_classes.models import Batch, BatchRegistration
from purchases.models import Purchase

from .services import auto_issue_for_batch, auto_issue_for_batch_registration, auto_issue_for_purchase


@receiver(post_save, sender=Purchase)
def handle_purchase_saved(sender, instance, **kwargs):
    if instance.enrollment_status == 'completed':
        auto_issue_for_purchase(instance)


@receiver(post_save, sender=Batch)
def handle_batch_saved(sender, instance, **kwargs):
    if instance.status == 'completed':
        auto_issue_for_batch(instance)


@receiver(post_save, sender=BatchRegistration)
def handle_batch_registration_saved(sender, instance, **kwargs):
    if instance.status == 'completed':
        auto_issue_for_batch_registration(instance)
