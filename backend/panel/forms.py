from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import User

from content.models import Case, Client, Reel, Screen, SiteSettings


class StyledMixin:
    """Ҳар бир майдонга панел CSS классини беради."""

    def style(self):
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs['class'] = 'switch'
            elif isinstance(w, forms.ClearableFileInput):
                w.attrs['class'] = 'file'
            else:
                w.attrs.setdefault('class', 'input')
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault('rows', 4)


class ContentForm(StyledMixin, forms.ModelForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.style()


def content_form(model_cls):
    exclude = ['order']
    return forms.modelform_factory(model_cls, form=ContentForm, exclude=exclude)


CONTENT_FORMS = {m: content_form(m) for m in (Case, Client, Screen, Reel)}


class SettingsForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ['pixel_id', 'tg_token', 'odoo_url', 'odoo_db', 'odoo_api_key']
        widgets = {
            'tg_token': forms.PasswordInput(render_value=True, attrs={'autocomplete': 'off', 'data-reveal': '1'}),
            'odoo_api_key': forms.PasswordInput(render_value=True, attrs={'autocomplete': 'off', 'data-reveal': '1'}),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.style()


ROLES = [('manager', 'Менежер — аризалар ва ҳисоботлар'), ('super', 'Супер админ — ҳамма имкониятлар')]


class UserForm(StyledMixin, forms.ModelForm):
    role = forms.ChoiceField(label='Роли', choices=ROLES, widget=forms.RadioSelect)
    password = forms.CharField(label='Парол', required=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
                               help_text='Камида 8 белги. Таҳрирлашда бўш қолса, парол ўзгармайди.')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'is_active']
        labels = {'username': 'Логин', 'first_name': 'Исм', 'last_name': 'Фамилия', 'is_active': 'Панелга кира олади'}
        help_texts = {'username': 'Лотин ҳарфлари, рақамлар ва @ . + - _ белгилари.',
                      'is_active': 'Ўчирилса, панелга кира олмайди. Маълумотлари сақланади.'}

    def __init__(self, *a, editor=None, **kw):
        super().__init__(*a, **kw)
        self.editor = editor
        self.fields['role'].initial = 'super' if self.instance.is_superuser else 'manager'
        if not self.instance.pk:
            self.fields['password'].required = True
            self.fields['password'].help_text = 'Камида 8 белги.'
        self.style()
        self.fields['role'].widget.attrs = {}

    def clean_password(self):
        pw = self.cleaned_data.get('password')
        if pw:
            password_validation.validate_password(pw, self.instance)
        return pw

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance == self.editor:
            if data.get('role') != 'super' or not data.get('is_active'):
                raise forms.ValidationError('Ўзингизни супер админликдан чиқара олмайсиз ёки ўчира олмайсиз.')
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = self.cleaned_data['role'] == 'super'
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
