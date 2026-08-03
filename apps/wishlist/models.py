from common.models import TimeStampedModel
from django.db import models


class WishlistItem(TimeStampedModel):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='wishlist_items')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='wishlisted_by')

    class Meta:
        db_table = 'wishlist_items'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'course'], name='unique_student_course_wishlist')
        ]

    def __str__(self):
        return f'{self.student} - {self.course}'
