from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from hermandades.models import Devoto


class DevotoForm(forms.ModelForm):
    dia = forms.IntegerField(min_value=1, max_value=31)
    mes = forms.IntegerField(min_value=1, max_value=12)
    anio = forms.IntegerField(min_value=1900, max_value=date.today().year)
    correo2 = forms.EmailField(label="Verifique correo")
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Devoto
        fields = [
            "dpi",
            "primer_nombre",
            "otros_nombres",
            "primer_apellido",
            "otros_apellidos",
            "departamento",
            "municipio",
            "celular",
            "correo",
            "medida_hombro_cm",
            "acepta_privacidad",
        ]
        widgets = {
            "medida_hombro_cm": forms.HiddenInput(),
            "dpi": forms.TextInput(attrs={"inputmode": "numeric", "maxlength": "13", "autocomplete": "off"}),
            "primer_nombre": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "otros_nombres": forms.TextInput(attrs={"autocomplete": "additional-name"}),
            "primer_apellido": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "celular": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
            "correo": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, hermandad=None, **kwargs):
        self.hermandad = hermandad
        super().__init__(*args, **kwargs)
        self.fields["acepta_privacidad"].required = True
        self.fields["acepta_privacidad"].label = (
            "Acepto que estos datos sean almacenados y administrados por la organización seleccionada."
        )
        self.fields["medida_hombro_cm"].required = False
        placeholders = {
            "dpi": "0000000000000",
            "primer_nombre": "Nombre",
            "otros_nombres": "Otros nombres",
            "primer_apellido": "Apellido",
            "otros_apellidos": "Otros apellidos",
            "dia": "DD",
            "mes": "MM",
            "anio": "AAAA",
            "departamento": "Departamento",
            "municipio": "Municipio",
            "celular": "Celular",
            "correo": "Correo",
            "correo2": "Confirmar correo",
        }
        for field_name, placeholder in placeholders.items():
            self.fields[field_name].widget.attrs.setdefault("placeholder", placeholder)

        if self.instance and self.instance.pk and self.instance.fecha_nacimiento:
            self.fields["dia"].initial = self.instance.fecha_nacimiento.day
            self.fields["mes"].initial = self.instance.fecha_nacimiento.month
            self.fields["anio"].initial = self.instance.fecha_nacimiento.year

    def clean_dpi(self):
        dpi = "".join(ch for ch in self.cleaned_data.get("dpi", "") if ch.isdigit())
        if len(dpi) != 13:
            raise ValidationError("El DPI debe contener exactamente 13 dígitos.")
        if self.hermandad:
            existing = Devoto.objects.filter(hermandad=self.hermandad, dpi=dpi)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("Este DPI ya está registrado para esta organización.")
        return dpi

    def clean_correo(self):
        return self.cleaned_data["correo"].strip().lower()

    def clean_celular(self):
        celular = self.cleaned_data.get("celular", "").strip()
        digits = "".join(ch for ch in celular if ch.isdigit())
        if len(digits) < 8:
            raise ValidationError("El celular debe contener al menos 8 dígitos.")
        return celular

    def clean_medida_hombro_cm(self):
        medida = self.cleaned_data.get("medida_hombro_cm")
        if medida in (None, ""):
            return None
        medida = Decimal(medida)
        if medida < Decimal("40") or medida > Decimal("220"):
            raise ValidationError("La medida hasta el hombro debe estar entre 40 y 220 cm.")
        return medida

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            raise ValidationError("No fue posible procesar el formulario.")

        correo = cleaned.get("correo")
        correo2 = cleaned.get("correo2", "").strip().lower()
        if correo and correo2 and correo != correo2:
            self.add_error("correo2", "Los correos no coinciden.")

        dia = cleaned.get("dia")
        mes = cleaned.get("mes")
        anio = cleaned.get("anio")
        if dia and mes and anio:
            try:
                fecha_nacimiento = date(anio, mes, dia)
            except ValueError:
                self.add_error("dia", "La fecha de nacimiento no es válida.")
            else:
                if fecha_nacimiento > date.today():
                    self.add_error("anio", "La fecha de nacimiento no puede estar en el futuro.")
                else:
                    cleaned["fecha_nacimiento"] = fecha_nacimiento

        if not cleaned.get("acepta_privacidad"):
            self.add_error("acepta_privacidad", "Debes aceptar el aviso de privacidad.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.hermandad = self.hermandad
        instance.fecha_nacimiento = self.cleaned_data["fecha_nacimiento"]
        if commit:
            instance.save()
        return instance
