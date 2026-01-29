from .patients import Patient
from django.db.models import CASCADE, PROTECT
from ...users.models import User
from django.db import models


class Appointment(models.Model):
    patient = models.ForeignKey(
        Patient, on_delete=CASCADE, related_name='patient_encounters')
    doctor = models.ForeignKey(
        User, on_delete=PROTECT, related_name='doctor_encounters')
    visit_datetime = models.DateTimeField(db_index=True)
    chief_complaint = models.TextField()
    diagnosis = models.TextField()
    blood_pressure = models.CharField(max_length=20, blank=True, null=True)
    heart_rate = models.IntegerField(blank=True, null=True)
    body_temperature = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True)
    oxygen = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.TimeField(auto_now_add=True)
    updated_at = models.TimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=PROTECT, related_name='created_encounter_by_user')
    updated_by = models.ForeignKey(
        User, on_delete=PROTECT, related_name='updated_encounter_by_user')

    class Meta:
        db_table = 'patient_encounter'
        indexes = [
            models.Index(fields=['patient', 'visit_datetime']),
            models.Index(fields=['doctor', 'visit_datetime']),
            models.Index(fields=['visit_datetime']),
        ]
