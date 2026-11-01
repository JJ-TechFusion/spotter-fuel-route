from django.db import models


class City(models.Model):
    """A US place from the Census gazetteer, used to geocode offline."""

    state = models.CharField(max_length=2)
    name = models.CharField(max_length=120)
    key = models.CharField(max_length=120, help_text="Normalized name for lookups.")
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["state", "key"], name="unique_city_per_state")]

    def __str__(self):
        return f"{self.name}, {self.state}"


class FuelStation(models.Model):
    opis_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    retail_price = models.DecimalField(max_digits=8, decimal_places=5)
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField()

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state})"
