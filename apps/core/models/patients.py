import hashlib
from cryptography.fernet import Fernet
from django.db import models
import os


class __EncryptedField:
    def __init__(self):
        key = str(os.getenv("SUPER_SECRET_KEY")).encode()
        self.crypto = Fernet(key)

    def encrypt(self, value):
        if value is None:
            return None
        return self.crypto.encrypt(str(value).encode()).decode("utf-8")

    def decrypt(self, value):
        if value is None:
            return None
        return self.crypto.decrypt(value.encode()).decode("utf-8")

    def hash(self, value):
        if value is None:
            return None
        return hashlib.sha256(str(value).encode()).hexdigest()


crypto = __EncryptedField()


class PatientQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)


class PatientManager(models.Manager):
    def get_queryset(self):
        return PatientQuerySet(self.model, using=self._db).active()

    def all_with_inactive(self):
        return PatientQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def inactive(self):
        return self.all_with_inactive().inactive()


class Patient(models.Model):
    first_name_encrypted = models.TextField()
    last_name_encrypted = models.TextField()
    date_of_birth_encrypted = models.TextField()
    gender_encrypted = models.TextField()
    allergies_encrypted = models.TextField(null=True)
    medical_record_number_encrypted = models.TextField()

    hashed_medical_record_number = models.CharField(unique=True, db_index=True)

    created_at = models.TimeField(auto_now_add=True)
    updated_at = models.TimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    objects = PatientManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'patient'
        indexes = [
            models.Index(fields=['hashed_medical_record_number']),
            models.Index(fields=['is_active'])
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def first_name(self):
        return crypto.decrypt(self.first_name_encrypted)

    @first_name.setter
    def first_name(self, value):
        self.first_name_encrypted = crypto.encrypt(value)

    @property
    def last_name(self):
        return crypto.decrypt(self.last_name_encrypted)

    @last_name.setter
    def last_name(self, value):
        self.last_name_encrypted = crypto.encrypt(value)

    @property
    def date_of_birth(self):
        return crypto.decrypt(self.date_of_birth_encrypted)

    @date_of_birth.setter
    def date_of_birth(self, value):
        self.date_of_birth_encrypted = crypto.encrypt(value)

    @property
    def gender(self):
        return crypto.decrypt(self.gender_encrypted)

    @gender.setter
    def gender(self, value):
        self.gender_encrypted = crypto.encrypt(value)

    @property
    def medical_record_number(self):
        return crypto.decrypt(self.medical_record_number_encrypted)

    @medical_record_number.setter
    def medical_record_number(self, value):
        self.medical_record_number_encrypted = crypto.encrypt(value)
        self.hashed_medical_record_number = crypto.hash(value)

    @property
    def allergies(self):
        if self.allergies_encrypted:
            return crypto.decrypt(self.allergies_encrypted)
        return None

    @allergies.setter
    def allergies(self, value):
        if value:
            self.allergies_encrypted = crypto.encrypt(value)
        else:
            self.allergies_encrypted = None
