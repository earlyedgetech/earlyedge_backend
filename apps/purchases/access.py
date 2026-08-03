"""Single source of truth for "does this student have access to this
course" — checked against a direct lifetime Purchase OR a non-expired
AccessPlan the course is included in. Reused anywhere course-gating is
needed (see live_classes.views._enrolled_course_ids)."""

from django.utils import timezone

from .models import PlanPurchase, Purchase


def enrolled_course_ids(student):
    """All course ids this student currently has access to, via either a
    direct purchase or an active plan — a single querysettable list for
    `__in` filters."""
    direct_ids = set(
        Purchase.objects.filter(student=student, enrollment_status='active').values_list('course_id', flat=True)
    )

    plan_course_ids = set()
    active_plans = PlanPurchase.objects.filter(
        student=student, expires_at__gt=timezone.now()
    ).select_related('plan').prefetch_related('plan__courses')
    for plan_purchase in active_plans:
        plan = plan_purchase.plan
        if plan.include_all_courses:
            from courses.models import Course

            plan_course_ids.update(Course.objects.values_list('id', flat=True))
        else:
            plan_course_ids.update(plan.courses.values_list('id', flat=True))

    return direct_ids | plan_course_ids


def student_has_course_access(student, course):
    return course.id in enrolled_course_ids(student)
