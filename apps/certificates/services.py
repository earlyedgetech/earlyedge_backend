"""Certificate issuance logic shared by the manual "Generate Certificate"
dashboard flow and the automatic signal-driven flow (see signals.py) — both
funnel through `issue_certificate()` so a student/course pair is never
awarded two certificates (the DB also enforces this via a unique
constraint, this is just the friendly/idempotent path)."""

from courses.models import Course

from .models import Certificate, CertificateTemplate

COURSE_TYPE_TO_CERT_TYPE = {
    'course': 'online_course',
    'internship': 'internship',
    'workshop': 'workshop',
}


def default_certificate_type_for_course(course):
    return COURSE_TYPE_TO_CERT_TYPE.get(course.course_type, 'completion')


def default_template_for(certificate_type):
    return (
        CertificateTemplate.objects.filter(category=certificate_type, is_default=True).first()
        or CertificateTemplate.objects.filter(category=certificate_type).first()
        or CertificateTemplate.objects.filter(is_default=True).first()
    )


def issue_certificate(student, course, *, issue_type='manual', template=None, certificate_type=None):
    """Idempotent: returns the existing certificate (untouched) if one
    already exists for this student/course, otherwise creates one."""

    existing = Certificate.objects.filter(student=student, course=course).first()
    if existing:
        return existing, False

    resolved_type = certificate_type or default_certificate_type_for_course(course)
    resolved_template = template or default_template_for(resolved_type)

    certificate = Certificate.objects.create(
        student=student,
        course=course,
        template=resolved_template,
        certificate_type=resolved_type,
        issue_type=issue_type,
    )
    return certificate, True


def auto_issue_for_purchase(purchase):
    if not purchase.course.certificate_enabled:
        return None
    certificate, _created = issue_certificate(purchase.student, purchase.course, issue_type='auto')
    return certificate


def auto_issue_for_batch_registration(registration):
    course = registration.batch.course
    if not course.certificate_enabled:
        return None
    certificate, _created = issue_certificate(registration.student, course, issue_type='auto')
    return certificate


def auto_issue_for_batch(batch):
    if not batch.course.certificate_enabled:
        return []
    issued = []
    for registration in batch.registrations.select_related('student').all():
        certificate, created = issue_certificate(registration.student, batch.course, issue_type='auto')
        if created:
            issued.append(certificate)
    return issued


def eligible_students_for_course(course: Course):
    """Students who have completed this course (via purchase enrollment or
    a completed live-class batch registration) and don't already hold a
    certificate for it — the candidate pool for manual generation."""

    from purchases.models import Purchase
    from live_classes.models import BatchRegistration

    already_certified = set(
        Certificate.objects.filter(course=course).values_list('student_id', flat=True)
    )

    candidates = {}

    purchases = Purchase.objects.select_related('student').filter(
        course=course, enrollment_status='completed',
    )
    for purchase in purchases:
        if purchase.student_id in already_certified:
            continue
        candidates[purchase.student_id] = {
            'id': purchase.student_id,
            'full_name': purchase.student.full_name,
            'email': purchase.student.email,
            'reason': 'course_completed',
        }

    registrations = BatchRegistration.objects.select_related('student').filter(
        batch__course=course, status='completed',
    )
    for registration in registrations:
        if registration.student_id in already_certified:
            continue
        candidates.setdefault(registration.student_id, {
            'id': registration.student_id,
            'full_name': registration.student.full_name,
            'email': registration.student.email,
            'reason': 'batch_completed',
        })

    return list(candidates.values())
