from common.models import TimeStampedModel
from django.db import models


class Instructor(TimeStampedModel):
    ACCOUNT_STATUS_CHOICES = (
        ('active', 'Active'),
        ('pending_verification', 'Pending Verification'),
        ('suspended', 'Suspended'),
    )
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    PAYOUT_METHOD_CHOICES = (
        ('bank', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('paypal', 'PayPal'),
    )

    member = models.OneToOneField(
        'admin_security.AdminMember', on_delete=models.CASCADE, related_name='instructor_profile'
    )
    instructor_code = models.CharField(max_length=30, unique=True)

    bio = models.TextField(blank=True)
    qualification = models.CharField(max_length=500, blank=True)
    specialization = models.CharField(max_length=500, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    languages_spoken = models.JSONField(default=list, blank=True)

    phone = models.CharField(max_length=20, blank=True)
    profile_picture_url = models.URLField(blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=20, blank=True)

    account_status = models.CharField(max_length=25, choices=ACCOUNT_STATUS_CHOICES, default='pending_verification')
    admin_verified = models.BooleanField(default=False)

    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_ratings = models.PositiveIntegerField(default=0)

    portfolio_url = models.URLField(blank=True)
    video_intro_url = models.URLField(blank=True)
    payout_method = models.CharField(max_length=10, choices=PAYOUT_METHOD_CHOICES, blank=True)
    payout_details = models.JSONField(default=dict, blank=True)
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=70.00,
        help_text='Percent of completed-purchase revenue this instructor earns.',
    )
    timezone = models.CharField(max_length=50, blank=True)
    availability_schedule = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'instructors'
        ordering = ['-created_at']

    def __str__(self):
        return self.member.full_name

    @property
    def course_count(self):
        return self.courses.count()

    @property
    def enrolled_students(self):
        return sum(self.courses.values_list('total_enrollments', flat=True))


class InstructorReview(TimeStampedModel):
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='instructor_reviews'
    )
    course = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='instructor_reviews'
    )
    user_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = 'instructor_reviews'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.instructor} - {self.user_name or "anonymous"}'


class InstructorPayout(TimeStampedModel):
    """A manually-recorded record of an amount already paid to an instructor
    (externally, via their configured payout_method/payout_details) — one
    row per payment, used to compute their remaining pending_balance."""

    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recorded_instructor_payouts',
    )

    class Meta:
        db_table = 'instructor_payouts'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.instructor} - {self.amount}'
