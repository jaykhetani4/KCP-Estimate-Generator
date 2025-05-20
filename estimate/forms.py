from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Estimate, PaverBlockType

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password'
    }))

class PaverBlockTypeForm(forms.ModelForm):
    class Meta:
        model = PaverBlockType
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }

class EstimateForm(forms.ModelForm):
    class Meta:
        model = Estimate
        fields = ['party_name', 'date', 'paver_block_type', 'price', 'gst_percentage', 
                 'transportation_charge', 'loading_unloading_cost', 'notes']
        widgets = {
            'party_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'paver_block_type': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'gst_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'transportation_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'loading_unloading_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter any additional notes or terms and conditions'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paver_block_type'].empty_label = "Select Paver Block Type" 